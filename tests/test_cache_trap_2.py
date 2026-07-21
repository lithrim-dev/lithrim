"""CACHE-TRAP-2 (live-caught, 2026-07-21): a LIVE grade completed with ZERO model calls and
reported normal success.

CACHE-TRAP-1 fixed the per-LM flag (``build_judge_lm`` passes ``cache=False`` when
``LITHRIM_JUDGE_CACHE=0``). That is not enough: dspy keeps its OWN process-global disk and
memory caches, which serve hits regardless of the per-LM flag. Observed: a full 14-case solo
arm returning 14/14 at ~2s per case with ``cost_tokens.total == 0``, and a 5-judge ensemble
batch the same afternoon. Only a container restart cleared it.

Two properties, both pinned here:

  1. **Defeat every layer.** ``LITHRIM_JUDGE_CACHE=0`` disables dspy's global disk AND memory
     caches, not just the LM flag. Unset leaves them ALONE, so every $0/replay/offline path
     stays byte-identical.
  2. **Fail loud.** A grade requested LIVE that comes back at zero tokens is flagged
     ``cache_replay``, never reported as a silent success. This is the load-bearing half: if
     property 1 ever regresses, a replayed number can still never be quoted unknowingly.

Offline: no network, no model calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.judge_cache import set_global_judge_cache
from lithrim_bench.runtime.council import judges_dspy as J
from lithrim_bench.runtime.council.settings import settings


class _FakeLM:
    def __init__(self, model, **kwargs):
        self.model = model
        self.kwargs = kwargs


@pytest.fixture
def dspy_probe(monkeypatch):
    """Record every global cache reconfiguration build_judge_lm performs."""
    import dspy

    calls: list[dict] = []
    monkeypatch.setattr(dspy, "LM", _FakeLM)
    monkeypatch.setattr(dspy, "configure_cache", lambda **kw: calls.append(kw), raising=False)
    return calls


def _bind_risk(monkeypatch):
    for role in ("RISK", "POLICY", "FAITHFULNESS"):
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE"):
            monkeypatch.setattr(settings, f"LITHRIM_LLM_{kind}_{role}", "", raising=False)
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "gpt-4o")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "sk-risk")


# ── property 1: the env gate reaches dspy's GLOBAL caches, not just the LM flag ──


def test_live_gate_disables_the_global_disk_and_memory_caches(dspy_probe, monkeypatch):
    monkeypatch.setenv("LITHRIM_JUDGE_CACHE", "0")
    _bind_risk(monkeypatch)

    lm = J.build_judge_lm("risk_judge")

    assert lm.kwargs["cache"] is False  # CACHE-TRAP-1, still holds
    assert dspy_probe, "the global dspy cache was never reconfigured (CACHE-TRAP-2)"
    assert dspy_probe[-1]["enable_disk_cache"] is False
    assert dspy_probe[-1]["enable_memory_cache"] is False


def test_default_leaves_the_global_caches_untouched(dspy_probe, monkeypatch):
    """Unset must be byte-identical to pre-fix: $0/replay/offline paths keep their cache."""
    monkeypatch.delenv("LITHRIM_JUDGE_CACHE", raising=False)
    _bind_risk(monkeypatch)

    lm = J.build_judge_lm("risk_judge")

    assert lm.kwargs["cache"] is True
    assert dspy_probe == [], "the default path must not touch dspy's global cache config"


def test_missing_configure_cache_degrades_instead_of_crashing(monkeypatch):
    """An older dspy without configure_cache must still grade, not detonate the run."""
    import dspy

    monkeypatch.setattr(dspy, "LM", _FakeLM)
    monkeypatch.delattr(dspy, "configure_cache", raising=False)
    monkeypatch.setenv("LITHRIM_JUDGE_CACHE", "0")
    _bind_risk(monkeypatch)

    assert J.build_judge_lm("risk_judge").kwargs["cache"] is False


def test_set_global_judge_cache_is_idempotent_and_restorable(dspy_probe):
    set_global_judge_cache(False)
    set_global_judge_cache(False)
    set_global_judge_cache(True)

    assert [c["enable_disk_cache"] for c in dspy_probe] == [False, False, True]
    assert [c["enable_memory_cache"] for c in dspy_probe] == [False, False, True]


# ── property 2: a live grade at zero tokens is FLAGGED, never a silent success ──

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def _record(total):
    return {
        "result": {"provenance": {"cost_tokens": {"prompt": 0, "completion": 0, "total": total}}}
    }


def test_live_grade_at_zero_tokens_is_flagged_a_cache_replay():
    """THE regression: 14/14 cases at ~2s and tokens=0, reported as a successful live grade."""
    assert bff._cache_replay_flag(_record(0), live=True) is True


def test_live_grade_that_actually_spent_is_not_flagged():
    assert bff._cache_replay_flag(_record(14949), live=True) is False


def test_a_replay_grade_at_zero_tokens_is_not_flagged():
    """A $0 replay SHOULD cost nothing. Flagging it would cry wolf on the normal path."""
    assert bff._cache_replay_flag(_record(0), live=False) is False


def test_absent_cost_tokens_is_not_asserted_either_way():
    """No spend record is unknown, not proof of replay: never fabricate the accusation."""
    assert bff._cache_replay_flag({"result": {"provenance": {}}}, live=True) is False
    assert bff._cache_replay_flag({}, live=True) is False


# ── the wiring: the helper must actually be CALLED, or the fix is inert ──


def test_the_grade_record_and_cohort_row_carry_the_flag():
    """A helper nobody calls is the same defect in a new place: pin every hop it must ride.

    Read the endpoint source rather than a hand-built row, because the row builder and the
    record finaliser are inline in large endpoints with no separately callable seam.
    """
    import ast
    from pathlib import Path as _Path

    src = _Path(bff.__file__).read_text()
    tree = ast.parse(src)

    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "_cache_replay_flag" in called, "the record finaliser never calls the flag helper"

    keys = {
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    assert "cache_replay" in keys, "the per-case replay tell never reaches a record or row"
    assert "cache_replays" in keys, "the batch summary never reports its replay count"


def test_the_live_grade_restores_the_global_cache_afterwards():
    """Leaving dspy's global cache OFF would make every later $0 grade pay full price."""
    import ast
    from pathlib import Path as _Path

    src = _Path(bff.__file__).read_text()
    assert "set_global_judge_cache" in src, "the live grade never restores dspy's global cache"
    # and it must sit in a finally, not the happy path, or an erroring grade leaks the state
    tree = ast.parse(src)
    in_finally = any(
        isinstance(node, ast.Try)
        and "set_global_judge_cache" in ast.dump(ast.Module(body=node.finalbody, type_ignores=[]))
        for node in ast.walk(tree)
    )
    assert in_finally, "the global-cache restore must run in a finally block"
