"""WS-6c-DSPy-2 A3 (offline-structural): the A/B harness diff + scoring logic.

Deterministic, ``$0``, no network: both arms are fed FIXTURED per-judge seam dicts
and the composite verdict is computed by the SHARED ported ``_apply_consensus``.
This validates the harness's OWN logic — composite-verdict agreement counting,
per-role code-set agreement, ``None``-aware calibration, and per-arm/per-role
``score_judge`` on the lens. It is NOT a real prompt-vs-DSPy comparison (see
``ab_harness.OFFLINE_NOTE``); the live comparison is deferred to a cost-confirmed run.
"""

from __future__ import annotations

import pytest

# ab_harness builds a ComplianceCouncil (the [council] extra) for _apply_consensus;
# the offline path needs no dspy. Skip cleanly on the offline core.
pytest.importorskip("openai")
pytest.importorskip("tenacity")

from lithrim_bench.runtime.council.ab_harness import (  # noqa: E402
    OFFLINE_NOTE,
    _context_payload,
    run_offline_structural,
)


def _seam(role, decision, *, code=None, confidence=0.9):
    findings = (
        [{"taxonomy_code": code, "evidence_spans": [{"quote": f"q::{code}", "turn_ids": [1]}]}]
        if code
        else []
    )
    return {
        "model": role,
        "decision": decision,
        "confidence": confidence,
        "findings": findings,
        "errors": [],
    }


def _arms(*, prompt, dspy):
    return {"prompt": prompt, "dspy": dspy}


# Three fixtured cases. risk approves with a float conf; policy approves with None
# (Mistral); faithfulness carries the signal.
#   A clean       — both arms approve            → agree
#   B missing_all — prompt rejects, dspy misses  → DISAGREE
#   C value_mm    — both reject                  → agree
def _approve_seams(*, faith_conf=0.9):
    return {
        "risk_judge": _seam("risk_judge", "approve", confidence=0.9),
        "policy_judge": _seam("policy_judge", "approve", confidence=None),
        "faithfulness_judge": _seam("faithfulness_judge", "approve", confidence=faith_conf),
    }


CASES = [
    {
        "case_id": "clean",
        "expected_safety_flags": [],
        "arms": _arms(prompt=_approve_seams(), dspy=_approve_seams()),
    },
    {
        "case_id": "missing_allergy",
        "expected_safety_flags": ["MISSING_ALLERGY"],
        "arms": _arms(
            prompt={
                "risk_judge": _seam("risk_judge", "approve"),
                "policy_judge": _seam("policy_judge", "approve", confidence=None),
                "faithfulness_judge": _seam(
                    "faithfulness_judge", "reject", code="MISSING_ALLERGY", confidence=0.9
                ),
            },
            dspy=_approve_seams(),  # dspy arm missed it
        ),
    },
    {
        "case_id": "value_mismatch",
        "expected_safety_flags": ["VALUE_MISMATCH"],
        "arms": _arms(
            prompt={
                "risk_judge": _seam("risk_judge", "approve"),
                "policy_judge": _seam("policy_judge", "approve", confidence=None),
                "faithfulness_judge": _seam(
                    "faithfulness_judge", "reject", code="VALUE_MISMATCH", confidence=0.9
                ),
            },
            dspy={
                "risk_judge": _seam("risk_judge", "approve"),
                "policy_judge": _seam("policy_judge", "approve", confidence=None),
                "faithfulness_judge": _seam(
                    "faithfulness_judge", "reject", code="VALUE_MISMATCH", confidence=0.7
                ),
            },
        ),
    },
]


@pytest.fixture(scope="module")
def result():
    return run_offline_structural(CASES)


def test_mode_and_note_are_surfaced(result):
    assert result["mode"] == "offline-structural"
    assert result["note"] == OFFLINE_NOTE
    assert "HARNESS-LOGIC ONLY" in result["note"]


def test_composite_verdicts_per_arm(result):
    by_id = {r["case_id"]: r for r in result["per_case"]}
    assert (by_id["clean"]["prompt_verdict"], by_id["clean"]["dspy_verdict"]) == (
        "approve",
        "approve",
    )
    # faithfulness owns MISSING_ALLERGY → prompt one-strike rejects; dspy missed it
    assert by_id["missing_allergy"]["prompt_verdict"] == "reject"
    assert by_id["missing_allergy"]["dspy_verdict"] == "approve"
    assert by_id["value_mismatch"]["prompt_verdict"] == "reject"
    assert by_id["value_mismatch"]["dspy_verdict"] == "reject"


def test_verdict_agreement_counting(result):
    by_id = {r["case_id"]: r for r in result["per_case"]}
    assert by_id["clean"]["verdict_agree"] is True
    assert by_id["missing_allergy"]["verdict_agree"] is False
    assert by_id["value_mismatch"]["verdict_agree"] is True
    assert result["verdict_agreement_pct"] == round(100.0 * 2 / 3, 2)  # 66.67


def test_per_role_code_set_agreement(result):
    by_id = {r["case_id"]: r for r in result["per_case"]}
    b = by_id["missing_allergy"]["per_role"]["faithfulness_judge"]
    assert b["prompt_codes"] == ["MISSING_ALLERGY"]
    assert b["dspy_codes"] == []
    assert b["codes_agree"] is False
    c = by_id["value_mismatch"]["per_role"]["faithfulness_judge"]
    assert c["prompt_codes"] == c["dspy_codes"] == ["VALUE_MISMATCH"]
    assert c["codes_agree"] is True


def test_per_role_score_uses_the_lens(result):
    # prompt arm faithfulness: caught both in-lens labels, no FP → accepted
    pf = result["per_role_score"]["prompt"]["faithfulness_judge"]
    assert (pf["tp"], pf["fp"], pf["fn"]) == (2, 0, 0)
    assert pf["accepted"] is True
    # dspy arm faithfulness: missed MISSING_ALLERGY → one fn, not accepted
    df = result["per_role_score"]["dspy"]["faithfulness_judge"]
    assert (df["tp"], df["fp"], df["fn"]) == (1, 0, 1)
    assert df["accepted"] is False and df["recall"] == 0.5
    # risk/policy: no in-lens truth, no raises → vacuously accepted
    for arm in ("prompt", "dspy"):
        for role in ("risk_judge", "policy_judge"):
            s = result["per_role_score"][arm][role]
            assert (s["tp"], s["fp"], s["fn"]) == (0, 0, 0)
            assert s["accepted"] is True


def test_calibration_is_none_aware(result):
    cal = result["calibration"]
    # policy is Mistral (None confidence) on every case → no paired deltas
    assert cal["policy_judge"]["n_paired"] == 0
    assert cal["policy_judge"]["mean_delta"] is None
    # risk: 0.9 vs 0.9 across the cases it reported → zero mean delta
    assert cal["risk_judge"]["mean_delta"] == 0.0
    # faithfulness: only value_mismatch differs (0.7 − 0.9 = −0.2) over 3 paired
    assert cal["faithfulness_judge"]["n_paired"] == 3
    assert cal["faithfulness_judge"]["mean_delta"] == round(-0.2 / 3, 4)


def test_context_payload_nests_transcript_under_call_context():
    """The live-only payload-shape guard (the bug the cost-confirm smoke caught):
    the prompt-council reads the transcript ONLY from call_context.transcript
    (_prepare_full_analysis_payload, compliance_council:1159-1161). A top-level
    transcript is silently dropped → empty transcript + artifact → the COMPLETE
    FABRICATION RULE false-rejects every case. Artifacts stay top-level (:552).
    This offline guard means the control arm can't silently re-break without a
    paid live call surfacing it."""
    case = {
        "transcript": "Patient: reschedule to Tuesday.",
        "artifacts": [{"type": "clinical_note", "content": "Type 2 diabetes E11.9"}],
    }
    payload = _context_payload(case)

    assert payload["call_context"]["transcript"] == "Patient: reschedule to Tuesday."
    assert "transcript" not in payload, "transcript must NOT be top-level (it'd be dropped)"
    assert payload["artifacts"] == case["artifacts"], "artifacts stay top-level"

    # missing transcript degrades to "" (not None / KeyError), still nested
    assert _context_payload({})["call_context"]["transcript"] == ""
