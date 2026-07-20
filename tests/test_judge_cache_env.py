"""CACHE-TRAP-1 (live-caught, 2026-07-19): "Run live" re-grades silently replayed the DSPy LM
disk cache — same (model, prompt, seed=42, temp=0) → same cache key → byte-identical verdicts at
tokens=0, so a re-run never actually re-graded. The fix is env-gated and default-off:

  * ``build_judge_lm`` reads ``LITHRIM_JUDGE_CACHE`` at CALL time — ``"0"`` disables the LM
    cache; unset/anything-else keeps the pre-fix ``cache=True`` (offline tests + $0 paths are
    byte-identical).
  * The BFF grade subprocess sets ``LITHRIM_JUDGE_CACHE=0`` when (and only when) the grade is
    LIVE, so a paid "Run live" genuinely re-samples while nothing else changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lithrim_bench.runtime.council import judges_dspy as J
from lithrim_bench.runtime.council.settings import settings


class _FakeLM:
    def __init__(self, model, **kwargs):
        self.model = model
        self.kwargs = kwargs


@pytest.fixture
def fake_dspy_lm(monkeypatch):
    import dspy

    monkeypatch.setattr(dspy, "LM", _FakeLM)
    return _FakeLM


def _clear_per_role(monkeypatch):
    for role in ("RISK", "POLICY", "FAITHFULNESS"):
        for kind in ("PROVIDER", "MODEL", "API_KEY", "API_BASE"):
            monkeypatch.setattr(settings, f"LITHRIM_LLM_{kind}_{role}", "", raising=False)


def _bind_per_role_risk(monkeypatch):
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER_RISK", "openai")
    monkeypatch.setattr(settings, "LITHRIM_LLM_MODEL_RISK", "gpt-4o")
    monkeypatch.setattr(settings, "LITHRIM_LLM_API_KEY_RISK", "sk-risk")


def test_default_cache_stays_on(fake_dspy_lm, monkeypatch):
    _clear_per_role(monkeypatch)
    monkeypatch.delenv("LITHRIM_JUDGE_CACHE", raising=False)
    _bind_per_role_risk(monkeypatch)
    assert J.build_judge_lm("risk_judge").kwargs["cache"] is True


def test_env_zero_disables_cache_per_role_path(fake_dspy_lm, monkeypatch):
    _clear_per_role(monkeypatch)
    monkeypatch.setenv("LITHRIM_JUDGE_CACHE", "0")
    _bind_per_role_risk(monkeypatch)
    assert J.build_judge_lm("risk_judge").kwargs["cache"] is False


def test_env_zero_disables_cache_global_openai_path(fake_dspy_lm, monkeypatch):
    _clear_per_role(monkeypatch)
    monkeypatch.setenv("LITHRIM_JUDGE_CACHE", "0")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-global")
    monkeypatch.setattr(settings, "OPENAI_MODEL_RISK", "gpt-4o")
    lm = J.build_judge_lm("risk_judge")
    assert lm.model == "openai/gpt-4o"
    assert lm.kwargs["cache"] is False


def test_env_zero_disables_cache_global_azure_path(fake_dspy_lm, monkeypatch):
    _clear_per_role(monkeypatch)
    monkeypatch.setenv("LITHRIM_JUDGE_CACHE", "0")
    monkeypatch.setattr(settings, "LITHRIM_LLM_PROVIDER", "azure")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "az-key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://x.example")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
    monkeypatch.setattr(settings, "AZURE_OPENAI_DEPLOYMENT_COUNCIL", "gpt-4.1")
    lm = J.build_judge_lm("risk_judge")
    assert lm.model == "azure/gpt-4.1"
    assert lm.kwargs["cache"] is False


# ── the BFF wire: a LIVE grade subprocess carries LITHRIM_JUDGE_CACHE=0; a $0 one does not ──

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def _run_grade_subprocess(monkeypatch, *, live: bool) -> dict:
    captured = {}

    def _fake_run(cmd, env=None, **kw):
        captured["env"] = env
        return SimpleNamespace(returncode=0, stdout="__GRADE_JSON__" + json.dumps({"ok": True}), stderr="")

    monkeypatch.setattr(bff.subprocess, "run", _fake_run)
    ws = SimpleNamespace(pack="clinverdict", packs_dir=None)
    bff._grade_via_subprocess(
        agent_name="ws0_default", config_db=Path("cfg.db"), ontology_path=None,
        collections_db=None, out_dir=None, live=live, in_process=True, ws=ws,
    )
    return captured["env"]


def test_live_grade_subprocess_disables_judge_cache(monkeypatch):
    env = _run_grade_subprocess(monkeypatch, live=True)
    assert env["LITHRIM_JUDGE_CACHE"] == "0"


def test_replay_grade_subprocess_keeps_cache_default(monkeypatch):
    monkeypatch.delenv("LITHRIM_JUDGE_CACHE", raising=False)
    env = _run_grade_subprocess(monkeypatch, live=False)
    assert env.get("LITHRIM_JUDGE_CACHE") != "0"
