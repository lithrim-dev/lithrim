"""WS-6c-DSPy A1 + A3: the DSPy judge emits the §6 seam, and DSPy-judge outputs
fed through the UNCHANGED ``_apply_consensus`` reproduce the WS-6c consensus oracle.

A1 — the per-judge dict the DSPy ``Judge`` emits is the EXACT seam shape
``_apply_consensus`` consumes (``{model, decision, confidence, findings:[{taxonomy_code,
evidence_spans}], errors}``), with a ``confidence=None`` round-trip that is never
coerced and ``errors:[…]`` on a simulated judge failure.

A3 — the SAME oracle scenarios as ``test_consensus.py`` (Tier-1 one-strike, Tier-2
2+, PHI-FP suppression, llama-veto, Tier-1 safety floor, artifact-BLOCK,
None-confidence) produce IDENTICAL verdicts when the per-judge dicts are built by
the DSPy ``Judge`` rather than the hand-built ``judge()`` fixture — proving the
ported consensus wraps DSPy or non-DSPy judges identically (the §6 hybrid).

No network: the ``Judge`` is built with an injected predictor; confidence is read
from a synthesized response payload (the dict shape ``extract_verdict_confidence``
accepts), exactly as the live path reads it from the LM's logprobs.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

# judges_dspy imports compliance_council (the [council] extra: openai + tenacity)
# and uses dspy lazily; skip the whole module cleanly on the offline core.
pytest.importorskip("dspy")
pytest.importorskip("openai")
pytest.importorskip("tenacity")

from lithrim_bench.runtime.council.judges_dspy import (  # noqa: E402
    Judge,
    evaluate_dspy,
)


def _raw_for_conf(conf):
    """A synthesized chat-completion carrying (or lacking) the verdict-token
    logprob — the same shape the live LM returns and ``extract_verdict_confidence``
    reads. ``None`` => a response with no logprobs (Mistral-style)."""
    if conf is None:
        return {"choices": [{"logprobs": None}]}
    lp = math.log(conf) if 0 < conf <= 1 else 0.0
    return {"choices": [{"logprobs": {"content": [{"token": "reject", "logprob": lp}]}}]}


def dspy_judge(role, decision, *, code=None, evidence=True, confidence=0.9, fail=False):
    """A real DSPy ``Judge`` whose injected predictor yields the given
    decision/finding, routed through ``Judge.forward`` so the seam dict is built by
    the production path (not hand-assembled). ``fail=True`` makes the predictor
    raise, simulating a judge transport/parse failure → ``errors:[…]``."""
    findings = []
    if code:
        spans = [{"quote": f"q::{code}", "turn_ids": [1]}] if evidence else []
        findings = [{"taxonomy_code": code, "evidence_spans": spans}]
    raw = _raw_for_conf(confidence)

    def _predict(**_kw):
        if fail:
            raise RuntimeError("simulated judge failure: upstream 500")
        return SimpleNamespace(decision=decision, findings=findings, reason="", _raw_response=raw)

    return Judge(role, predictor=_predict, role_prompt=f"({role})")


def _run(judges, council):
    return evaluate_dspy(judges, transcript="t", artifact="a", council=council)


# ── A1: the seam shape the DSPy judge emits ─────────────────────────────────

def test_seam_shape_is_exactly_what_apply_consensus_reads():
    """Keys + types match the §6 boundary and the _apply_consensus read-sites."""
    seam = dspy_judge(
        "risk_judge", "reject", code="WRONG_DOSAGE", confidence=0.92
    ).forward(transcript="t", artifact="a")

    assert set(seam) == {"model", "decision", "confidence", "findings", "errors"}
    assert seam["model"] == "risk_judge"  # the role name (_TIER1_OWNERS / llama-veto key)
    assert seam["decision"] in {"approve", "needs_review", "reject"}
    assert isinstance(seam["errors"], list) and seam["errors"] == []
    # findings: [{taxonomy_code, evidence_spans:[{quote, turn_ids}]}] (:1899/:1911/:1914)
    assert seam["findings"] == [
        {"taxonomy_code": "WRONG_DOSAGE", "evidence_spans": [{"quote": "q::WRONG_DOSAGE", "turn_ids": [1]}]}
    ]
    assert seam["confidence"] == 0.92  # float from logprobs (:1979-1982)


def test_confidence_none_round_trips_uncoerced():
    """A response with no logprobs => confidence is None, NEVER 0.0/1.0."""
    seam = dspy_judge("policy_judge", "approve", confidence=None).forward(transcript="t", artifact="a")
    assert seam["confidence"] is None


def test_errors_populated_on_simulated_failure_and_judge_excluded(council):
    """A predictor exception becomes errors:[…]; the errored judge is excluded so
    two clean approves still drive the verdict (not <2-valid needs_review)."""
    failed = dspy_judge("risk_judge", "reject", code="WRONG_DOSAGE", fail=True)
    seam = failed.forward(transcript="t", artifact="a")
    assert seam["errors"] and "simulated judge failure" in seam["errors"][0]
    assert set(seam) == {"model", "decision", "confidence", "findings", "errors"}

    r = _run([failed, dspy_judge("policy_judge", "approve"), dspy_judge("faithfulness_judge", "approve")], council)
    assert r["decision"] == "approve"
    assert r["reason"] != "insufficient_valid_models"


def test_unknown_code_and_evidenceless_findings_are_dropped():
    """The _normalize_result discipline: an off-taxonomy code or an evidence-less
    finding never enters the seam (so it can't fabricate a Tier-1 strike)."""

    def _predict(**_kw):
        return SimpleNamespace(
            decision="reject",
            findings=[
                {"taxonomy_code": "NOT_A_REAL_CODE", "evidence_spans": [{"quote": "x"}]},
                {"taxonomy_code": "WRONG_DOSAGE", "evidence_spans": []},
                {"taxonomy_code": "WRONG_DOSAGE", "evidence_spans": [{"quote": "real"}]},
            ],
            reason="",
            _raw_response=_raw_for_conf(None),
        )

    seam = Judge("risk_judge", predictor=_predict).forward(transcript="t", artifact="a")
    assert [f["taxonomy_code"] for f in seam["findings"]] == ["WRONG_DOSAGE"]
    assert seam["findings"][0]["evidence_spans"] == [{"quote": "real", "turn_ids": []}]


# ── A3: DSPy judges + the ported _apply_consensus reproduce the oracle ───────

def test_a3_tier1_owner_one_strike_rejects(council):
    r = _run([
        dspy_judge("risk_judge", "reject", code="FABRICATED_ALLERGY"),
        dspy_judge("policy_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["FABRICATED_ALLERGY"]
    assert r["artifact_verdict"] == "BLOCK"


def test_a3_tier1_off_domain_single_judge_downgrades(council):
    r = _run([
        dspy_judge("policy_judge", "needs_review", code="WRONG_DOSAGE"),
        dspy_judge("risk_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "needs_review"
    assert r["evidence_summary"]["tier1_triggered"] == []
    flagged = r["evidence_summary"]["tier2_flagged"]
    assert [f["violation"] for f in flagged] == ["WRONG_DOSAGE"]
    assert flagged[0]["reason"] == "tier1_off_domain_single_judge"


def test_a3_tier1_corroborated_two_judges_reject_regardless_of_ownership(council):
    r = _run([
        dspy_judge("policy_judge", "needs_review", code="FABRICATED_ALLERGY"),
        dspy_judge("faithfulness_judge", "needs_review", code="FABRICATED_ALLERGY"),
        dspy_judge("risk_judge", "approve"),
    ], council)
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["FABRICATED_ALLERGY"]


def test_a3_tier2_corroborated_two_judges_reject(council):
    r = _run([
        dspy_judge("risk_judge", "needs_review", code="HALLUCINATED_DETAIL"),
        dspy_judge("policy_judge", "needs_review", code="HALLUCINATED_DETAIL"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier2_triggered"]] == ["HALLUCINATED_DETAIL"]
    assert r["artifact_verdict"] == "BLOCK"


def test_a3_tier2_single_judge_needs_review(council):
    r = _run([
        dspy_judge("risk_judge", "needs_review", code="HALLUCINATED_DETAIL"),
        dspy_judge("policy_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "needs_review"
    assert [f["violation"] for f in r["evidence_summary"]["tier2_flagged"]] == ["HALLUCINATED_DETAIL"]
    assert r["artifact_verdict"] == "WARN"


def test_a3_phi_false_positive_suppressed(council):
    r = _run([
        dspy_judge("policy_judge", "needs_review", code="IMPLICIT_CONFIRMATION_OF_RECORD"),
        dspy_judge("risk_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "approve"
    assert r["evidence_summary"]["tier3_flagged"] == []
    assert r["evidence_summary"]["tier2_flagged"] == []


def test_a3_llama_veto_approves_over_overstrict_judge(council):
    r = _run([
        dspy_judge("risk_judge", "needs_review"),
        dspy_judge("policy_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "approve"


def test_a3_llama_veto_off_when_another_judge_rejects(council):
    r = _run([
        dspy_judge("risk_judge", "reject"),
        dspy_judge("policy_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "reject"


def test_a3_tier1_safety_floor_overrides_veto(council):
    r = _run([
        dspy_judge("risk_judge", "reject", code="FABRICATED_ALLERGY"),
        dspy_judge("policy_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["FABRICATED_ALLERGY"]


def test_a3_artifact_block_overrides_clean_conversation(council):
    r = _run([
        dspy_judge("risk_judge", "needs_review", code="MEDICATION_NOT_IN_TRANSCRIPT"),
        dspy_judge("policy_judge", "needs_review", code="MEDICATION_NOT_IN_TRANSCRIPT"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "reject"
    assert r["conversation_verdict"] == "approve"
    assert r["artifact_verdict"] == "BLOCK"


def test_a3_none_confidence_skipped_in_average(council):
    """[0.92, None, None] → 0.92 (Mistral None skipped, never coerced to 0.0)."""
    r = _run([
        dspy_judge("risk_judge", "approve", confidence=0.92),
        dspy_judge("policy_judge", "approve", confidence=None),
        dspy_judge("faithfulness_judge", "approve", confidence=0.92),
    ], council)
    assert r["decision"] == "approve"
    assert r["confidence"] == 0.92


def test_a3_all_none_confidence_falls_back_to_zero(council):
    r = _run([
        dspy_judge("risk_judge", "approve", confidence=None),
        dspy_judge("policy_judge", "approve", confidence=None),
        dspy_judge("faithfulness_judge", "approve", confidence=None),
    ], council)
    assert r["confidence"] == 0.0
    assert r["uncertainty"] is True


def test_a3_clean_negative_all_approve(council):
    r = _run([
        dspy_judge("risk_judge", "approve"),
        dspy_judge("policy_judge", "approve"),
        dspy_judge("faithfulness_judge", "approve"),
    ], council)
    assert r["decision"] == "approve"
