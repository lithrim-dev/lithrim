"""P1-EXP-0: verify LithrimPipelineBackend._parse captures per-judge confidence.

The lithrim-backend API contract (lithrim-backend/app/services/pipeline/models.py
JudgeVote.confidence: float = 0.0) emits confidence on the wire, but the bench's
_parse used to drop it. This test pins the new capture behavior and the
backward-compatible default for legacy payloads.
"""

from __future__ import annotations

from lithrim_bench.backends.lithrim_pipeline import _parse


def _payload_with_confidence(confidence_value: float | None) -> dict:
    judge_vote: dict = {
        "judge_role": "policy_judge",
        "vote": "PASS",
        "findings": [],
    }
    if confidence_value is not None:
        judge_vote["confidence"] = confidence_value
    return {
        "verdict": "PASS",
        "gate_decision": "allow",
        "semantic": {
            "status": "PASS",
            "findings": [],
            "judge_votes": [judge_vote],
        },
        "structural": {"status": "PASS", "findings": []},
    }


def test_captures_confidence_when_present():
    verdict = _parse(_payload_with_confidence(0.87))
    assert verdict.per_judge is not None
    assert verdict.per_judge["policy_judge"].confidence == 0.87


def test_confidence_defaults_to_zero_when_absent():
    verdict = _parse(_payload_with_confidence(None))
    assert verdict.per_judge is not None
    assert verdict.per_judge["policy_judge"].confidence == 0.0
