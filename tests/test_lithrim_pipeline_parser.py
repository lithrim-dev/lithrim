"""Tests for the PipelineResult -> BackendVerdict mapping.

Pure unit tests against the _parse function; no live HTTP. Verifies
that the live-response shapes documented in the openapi spec map
correctly onto BackendVerdict fields.
"""

from lithrim_bench.backends.lithrim_pipeline import _parse


def test_block_reject_with_three_judges():
    payload = {
        "verdict": "BLOCK",
        "gate_decision": "escalate",
        "duration_ms": 21000,
        "semantic": {
            "status": "BLOCK",
            "findings": [
                {"type": "semantic", "code": "WRONG_DOSAGE", "severity": "HIGH", "detail": "..."},
                {
                    "type": "semantic",
                    "code": "FABRICATED_HISTORY",
                    "severity": "HIGH",
                    "detail": "...",
                },
            ],
            "judge_votes": [
                {
                    "judge_role": "policy_judge",
                    "vote": "BLOCK",
                    "confidence": 1.0,
                    "model": "gpt-4.1",
                    "findings": ["WRONG_DOSAGE", "FABRICATED_HISTORY"],
                },
                {
                    "judge_role": "risk_judge",
                    "vote": "BLOCK",
                    "confidence": 1.0,
                    "model": "gpt-4.1",
                    "findings": ["WRONG_DOSAGE"],
                },
                {
                    "judge_role": "behavior_judge",
                    "vote": "BLOCK",
                    "confidence": 1.0,
                    "model": "gpt-4.1",
                    "findings": ["FABRICATED_HISTORY"],
                },
            ],
        },
        "structural": {"status": "PASS", "findings": []},
        "provenance": {"pipeline_run_id": "test-run-1"},
    }
    v = _parse(payload)
    assert v.artifact_verdict == "BLOCK"
    assert v.compliance_verdict == "reject"
    assert v.flags == ["FABRICATED_HISTORY", "WRONG_DOSAGE"]
    assert set(v.per_judge.keys()) == {"policy_judge", "risk_judge", "behavior_judge"}
    assert v.per_judge["policy_judge"].verdict == "reject"
    assert v.per_judge["policy_judge"].flags == ["WRONG_DOSAGE", "FABRICATED_HISTORY"]
    assert v.structural_verdict == "PASS"


def test_pass_approve_with_no_findings():
    payload = {
        "verdict": "PASS",
        "gate_decision": "allow",
        "duration_ms": 1200,
        "semantic": {"status": "PASS", "findings": [], "judge_votes": []},
        "structural": {"status": "PASS", "findings": []},
        "provenance": {"pipeline_run_id": "test-run-2"},
    }
    v = _parse(payload)
    assert v.artifact_verdict == "PASS"
    assert v.compliance_verdict == "approve"
    assert v.flags == []
    assert v.per_judge is None or v.per_judge == {}


def test_warn_with_structural_findings_only():
    payload = {
        "verdict": "WARN",
        "gate_decision": "regenerate",
        "duration_ms": 800,
        "semantic": {"status": "PASS", "findings": []},
        "structural": {
            "status": "WARN",
            "findings": [
                {
                    "type": "structural",
                    "check_name": "attending-physician",
                    "severity": "MEDIUM",
                    "detail": "Attending physician missing",
                },
            ],
        },
        "provenance": {"pipeline_run_id": "test-run-3"},
    }
    v = _parse(payload)
    assert v.artifact_verdict == "WARN"
    assert v.compliance_verdict == "needs_review"
    assert v.structural_verdict == "WARN"
    assert v.structural_findings == ["attending-physician"]


def test_structural_not_applicable_preserved_through_backend_verdict():
    """BRS-0b: _parse must surface structural.status='not_applicable' as
    BackendVerdict.structural_verdict='not_applicable', not collapsed to 'PASS'.

    The orchestrator emits 'not_applicable' at the per-stage level when
    no artifact_profile resolves for the artifact_type. Future runs with
    absent profiles must now report that distinction; the previous
    `_STAGE_STATUS_NORMALIZE: not_applicable -> PASS` collapse silently
    hid validator-coverage gaps in the reporting chain.

    artifact_verdict (top-level pipeline `verdict`) is independent: the
    orchestrator never emits 'not_applicable' at the overall verdict
    level (only per-stage), so artifact_verdict stays PASS here.
    """
    payload = {
        "verdict": "PASS",
        "gate_decision": "allow",
        "duration_ms": 100,
        "semantic": {"status": "not_applicable", "findings": []},
        "structural": {"status": "not_applicable", "findings": []},
        "provenance": {"pipeline_run_id": "test-run-4"},
    }
    v = _parse(payload)
    assert v.artifact_verdict == "PASS"
    assert v.structural_verdict == "not_applicable"
