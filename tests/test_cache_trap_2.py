"""CACHE-TRAP-2 (live-caught, 2026-07-21): a LIVE grade completed with ZERO model calls and
reported normal success.

CACHE-TRAP-1 fixed the per-LM flag (``build_judge_lm`` passes ``cache=False`` when
``LITHRIM_JUDGE_CACHE=0``). That is not enough: dspy keeps its OWN process-global disk and
memory caches, which serve hits regardless of the per-LM flag. Observed: a full 14-case solo
arm returning 14/14 at ~2s per case with ``cost_tokens.total == 0``, and a 5-judge ensemble
batch the same afternoon. Only a container restart cleared it.

Three properties, all pinned here:

  1. **Defeat every layer.** ``LITHRIM_JUDGE_CACHE=0`` disables dspy's global disk AND memory
     caches, not just the LM flag. Unset leaves them ALONE, so every $0/replay/offline path
     stays byte-identical.
  2. **Fail loud.** A grade that PAID and came back at zero tokens is flagged ``cache_replay``,
     never reported as a silent success. This is the load-bearing half: if property 1 ever
     regresses, a replayed number can still never be quoted unknowingly.
  3. **Gate on SPEND, not on ``live``.** The first fix keyed both halves off ``live``, which in
     ``_resolve_run_backend`` means "route to the :8002 HTTP backend" — NOT "spends money". On
     the OSS default the paying path is ``in_process=True, live=False``, so on the one path the
     product actually clicks, the cache was never defeated and a replay could never be flagged
     (caught 2026-07-22 against v0.1.11, on a batch whose only protection was a cold container).
     The predicate is ``_grade_spends``; replay stays ``(live=False, in_process=False)``.

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


# ── property 2: a PAID grade at zero tokens is FLAGGED, never a silent success ──

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


def test_paid_grade_at_zero_tokens_is_flagged_a_cache_replay():
    """THE regression: 14/14 cases at ~2s and tokens=0, reported as a successful live grade."""
    assert bff._cache_replay_flag(_record(0), spends=True) is True


def test_paid_grade_that_actually_spent_is_not_flagged():
    assert bff._cache_replay_flag(_record(14949), spends=True) is False


def test_a_replay_grade_at_zero_tokens_is_not_flagged():
    """A $0 replay SHOULD cost nothing. Flagging it would cry wolf on the normal path."""
    assert bff._cache_replay_flag(_record(0), spends=False) is False


def test_absent_cost_tokens_is_not_asserted_either_way():
    """No spend record is unknown, not proof of replay: never fabricate the accusation."""
    assert bff._cache_replay_flag({"result": {"provenance": {}}}, spends=True) is False
    assert bff._cache_replay_flag({}, spends=True) is False


# ── property 3: the gate keys on SPEND, not on the :8002-routing flag ──


def test_in_process_is_a_paying_path():
    """``live`` means "route to :8002"; the OSS default pays via ``in_process``. Both spend."""
    assert bff._grade_spends(live=False, in_process=True) is True
    assert bff._grade_spends(live=True, in_process=False) is True
    assert bff._grade_spends(live=True, in_process=True) is True


def test_replay_is_the_only_free_path():
    """Neither flag set is the $0 replay — it must stay unaccused and uncached-gated."""
    assert bff._grade_spends(live=False, in_process=False) is False


def test_an_in_process_grade_at_zero_tokens_is_accused():
    """THE v0.1.11 gap: this is the exact shape the product's own Run-live button produces."""
    assert bff._cache_replay_flag(_record(0), spends=bff._grade_spends(
        live=False, in_process=True)) is True


@pytest.fixture
def captured_subprocess_env(monkeypatch):
    """Capture the env a pack-bound grade subprocess would be launched with."""
    seen: dict = {}

    class _Proc:
        returncode = 0
        stdout = '__GRADE_JSON__{"case_id": "x"}'
        stderr = ""

    def _fake_run(cmd, env=None, **kw):
        seen.update(env or {})
        return _Proc()

    monkeypatch.setattr(bff.subprocess, "run", _fake_run)
    monkeypatch.delenv("LITHRIM_JUDGE_CACHE", raising=False)
    return seen


def _run_subprocess_grade(*, live, in_process):
    from types import SimpleNamespace

    return bff._grade_via_subprocess(
        agent_name="ws0_default", config_db=Path("/tmp/c.sqlite"), ontology_path=None,
        collections_db=None, out_dir=None, live=live, in_process=in_process,
        ws=SimpleNamespace(pack="clinverdict", packs_dir=None), case_id="cv06_diabetes",
    )


def test_the_pack_subprocess_defeats_the_cache_on_an_in_process_grade(captured_subprocess_env):
    """The clinverdict/healthcare workspaces grade in a SUBPROCESS, whose memory cache is cold
    but whose DISK cache (/root/.dspy_cache) is shared with every prior grade — so this env var
    is the ONLY lever on the path the research corpus actually runs through."""
    _run_subprocess_grade(live=False, in_process=True)

    assert captured_subprocess_env.get("LITHRIM_JUDGE_CACHE") == "0"


def test_the_pack_subprocess_leaves_a_replay_cache_alone(captured_subprocess_env):
    _run_subprocess_grade(live=False, in_process=False)

    assert "LITHRIM_JUDGE_CACHE" not in captured_subprocess_env


def test_no_cache_gate_anywhere_keys_off_live_alone():
    """The defect was a NAME: three sites read ``live`` meaning "spends". Pin that none does.

    Structural rather than behavioral because the in-process gate sits inline in ``_grade_case``
    (a large endpoint-side function with no separately callable seam), and an inline gate that
    silently reverts to ``if live:`` is exactly how this regressed once already.
    """
    import ast

    src = Path(bff.__file__).read_text()
    tree = ast.parse(src)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Name):
            continue
        if node.test.id != "live":
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        if "LITHRIM_JUDGE_CACHE" in body or "set_global_judge_cache" in body:
            offenders.append(node.lineno)

    assert not offenders, f"cache gate still keyed off `live` alone at line(s) {offenders}"


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
