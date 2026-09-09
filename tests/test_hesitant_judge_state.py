"""HESITANT-JUDGE-1: a WARN vote with no code is a stated hesitation; a floor pass on the
numbers does not clear it.

Observed 2026-09-09 (RAGTruth v3): two human-labeled defects landed CLEARED because the single
judge voted WARN with no code, the severity rescore flattened that to PASS, and value grounding
passed one or two numbers. Nothing refuted the hesitation."""

from __future__ import annotations

from types import SimpleNamespace

from lithrim_bench.harness.report import review_state


def _grounded(votes, *, suppressed=()):
    passes = [
        {
            "decl": SimpleNamespace(contract_type="value_grounding"),
            "result": SimpleNamespace(evidence={"checked": 2}),
        }
    ]
    return SimpleNamespace(
        verdict="PASS",
        verdict_no_floor="PASS",
        coverage={"floor_backstopped": True, "grounded": 1},
        active=[],
        floor_blocks=[],
        floor_passes=passes,
        suppressed=list(suppressed),
        judge_votes=votes,
    )


def test_uncoded_warn_plus_numeric_pass_escalates_with_the_confirmed_part_attached():
    out = review_state(
        _grounded([{"judge_role": "ragtruth_detector", "vote": "WARN", "findings": []}])
    )
    assert out["state"] == "ESCALATED"
    assert "hesitated (WARN, no code)" in out["reason"] and "ragtruth_detector" in out["reason"]
    assert "value_grounding confirmed 2 value(s) present" in out["evidence"]


def test_silent_pass_votes_still_clear_on_a_floor_pass():
    out = review_state(_grounded([{"judge_role": "r", "vote": "PASS", "findings": []}]))
    assert out["state"] == "CLEARED"


def test_a_hesitation_the_floor_refuted_still_clears():
    sup = [
        {
            "contract": SimpleNamespace(contract_type="value_grounding"),
            "finding": {"code": "X"},
            "verdict": SimpleNamespace(reason="grounded"),
        }
    ]
    g = _grounded([{"judge_role": "r", "vote": "WARN", "findings": []}], suppressed=sup)
    g.floor_passes = []
    assert review_state(g)["state"] == "CLEARED"


def test_legacy_grounded_without_votes_is_unchanged():
    g = _grounded([])
    del g.judge_votes
    assert review_state(g)["state"] == "CLEARED"
