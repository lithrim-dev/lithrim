"""VOTE-MODEL-1 — each per-judge vote carries the REAL deployment it graded on.

On the authored DSPy path (the live product path) ``_judge_votes_from_models`` runs with an
empty ``model_lookup`` (the trio is DI-injected, so the prompt-council's role→model map is
absent). Before this cycle ``JudgeVote.model`` then fell back to the seam dict's own ``model``
field — which is the ROLE NAME ("risk_judge"), not the deployment — so the UI's per-reviewer
"model" line just echoed the role.

The fix RESPECTS THE FROZEN ``Judge`` SEAM: ``Judge.forward`` is byte-frozen (the moat), so the
resolved model is captured in ``build_trio`` (the sanctioned BYOC provider-binder carve-out) as
``judge.llm_model`` and stamped onto each seam dict in ``authored_stage`` (not frozen). The
orchestrator's ``_judge_votes_from_models`` then prefers it. Captured at grade time → lands in
the provenance blob, so the JudgeTab + run audit show e.g. ``azure/gpt-4.1`` per reviewer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

pytest.importorskip("dspy", reason="build_trio constructs a dspy.Predict")

import lithrim_bench.harness.pack as packmod  # noqa: E402
import lithrim_bench.runtime.council.judges_dspy as jd  # noqa: E402
from lithrim_bench.runtime.council import authored_stage as astage  # noqa: E402
from lithrim_bench.runtime.pipeline.stages import _judge_votes_from_models  # noqa: E402


class _FakeLM:
    """Stand-in for ``dspy.LM`` / ``ClaudeCliLM`` — only ``.model`` is read for attribution."""

    def __init__(self, model: str) -> None:
        self.model = model


# ── the consumer: _judge_votes_from_models prefers the seam's llm_model ──────────────────────


def test_votes_prefer_llm_model_over_role_name_on_the_authored_path():
    """An empty lookup (the authored path) projects the seam's ``llm_model`` as JudgeVote.model —
    the real deployment, not the role name."""
    seam = [{"model": "risk_judge", "llm_model": "azure/gpt-4.1",
             "decision": "approve", "confidence": 0.9, "findings": []}]
    votes = _judge_votes_from_models(seam, model_lookup={})
    assert votes[0].judge_role == "risk_judge"
    assert votes[0].model == "azure/gpt-4.1"


def test_votes_fall_back_to_role_name_when_no_llm_model():
    """Back-compat: a seam with no ``llm_model`` (a fixtured/legacy result) still degrades to the
    role name — never blank."""
    seam = [{"model": "policy_judge", "decision": "needs_review", "confidence": None, "findings": []}]
    assert _judge_votes_from_models(seam, model_lookup={})[0].model == "policy_judge"


def test_model_lookup_is_the_fallback_when_the_seam_carries_no_binding():
    """VOTE-ERRORS (b): the seam's ``llm_model`` is the LM actually bound at build_trio time,
    so it wins over the prompt-council's roster/config lookup when present; the lookup applies
    only to seams that carry no binding (the frozen prompt-council rows never do, so that path
    is byte-identical)."""
    bound = [{"model": "faithfulness_judge", "llm_model": "azure/ACTUALLY-RAN",
              "decision": "approve", "confidence": 1.0, "findings": []}]
    votes = _judge_votes_from_models(bound, model_lookup={"faithfulness_judge": "azure/Llama-4-Maverick"})
    assert votes[0].model == "azure/ACTUALLY-RAN"
    unbound = [{"model": "faithfulness_judge", "decision": "approve", "confidence": 1.0, "findings": []}]
    votes = _judge_votes_from_models(unbound, model_lookup={"faithfulness_judge": "azure/Llama-4-Maverick"})
    assert votes[0].model == "azure/Llama-4-Maverick"


# ── the capture: build_trio stamps the resolved model on each judge (the carve-out) ──────────


def test_build_trio_stamps_the_resolved_deployment(monkeypatch):
    """build_trio binds each role's LM via build_judge_lm and stamps its ``.model`` onto the judge
    as ``llm_model`` — without touching the frozen Judge symbol. Pack deps mocked → offline/$0."""
    monkeypatch.setattr(packmod, "pack_production_judges", lambda: ("risk_judge",))
    monkeypatch.setattr(jd, "load_role_prompt", lambda role: "PROMPT")
    monkeypatch.setattr(jd, "build_judge_lm", lambda role, **kw: _FakeLM("azure/gpt-4.1"))
    trio = jd.build_trio(roles=["risk_judge"], taxonomy_context="ctx")
    assert trio[0].role == "risk_judge"
    assert trio[0].llm_model == "azure/gpt-4.1"


def test_build_trio_predictor_path_binds_no_model(monkeypatch):
    """The offline predictor path binds no LM → ``llm_model`` is None (the role-name fallback
    above then applies — byte-identical to before for fixtured tests)."""
    monkeypatch.setattr(packmod, "pack_production_judges", lambda: ("risk_judge",))
    monkeypatch.setattr(jd, "load_role_prompt", lambda role: "PROMPT")
    trio = jd.build_trio(roles=["risk_judge"], predictors={"risk_judge": lambda **kw: None},
                         taxonomy_context="ctx")
    assert trio[0].llm_model is None


# ── the glue: the authored evaluator stamps llm_model onto every seam dict ────────────────────


class _FakeJudge:
    def __init__(self, role: str, model: str | None) -> None:
        self.role = role
        self.llm_model = model

    def forward(self, *, transcript: str, artifact: str) -> dict:
        return {"model": self.role, "decision": "approve", "confidence": 0.9, "findings": [], "errors": []}


class _FakeCouncil:
    def _apply_consensus(self, results, gate_mode=False):  # noqa: ARG002
        return {"decision": "approve", "evidence_summary": {}}


def test_authored_evaluator_attributes_each_vote_to_its_model(monkeypatch):
    """``build_authored_evaluator`` stamps each per-judge seam dict with the judge's resolved
    ``llm_model`` (keyed by role, so it survives the withstands gate's rewrites)."""
    fake_trio = [_FakeJudge("risk_judge", "azure/gpt-4.1"),
                 _FakeJudge("policy_judge", "azure/Mistral-Large-3")]
    monkeypatch.setattr(jd, "build_trio", lambda **kw: fake_trio)

    evaluator = astage.build_authored_evaluator(
        ontology=None, assignments=None, council=_FakeCouncil(), apply_gate=False
    )
    out = evaluator({"call_context": {"transcript": "t"}, "artifacts": []})
    by_role = {m["model"]: m["llm_model"] for m in out["models"]}
    assert by_role == {"risk_judge": "azure/gpt-4.1", "policy_judge": "azure/Mistral-Large-3"}
