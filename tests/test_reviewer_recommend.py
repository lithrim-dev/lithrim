"""Stage 3 (CE-JUDGE-RECOMMEND-1): the panel-vs-single-Generalist recommendation.

The calibration thesis (reviewer-mode-and-onboarding-friction): differentiated specialist
reviewers (the panel) BEAT one full-lens generalist when the domain spans multiple failure-mode
families; a single generalist with k 3-8 sampling is enough for a NARROW domain (one review lens).
The pack's reviewer structure is the domain proxy — recommend from it, deterministically.
"""

from __future__ import annotations

from lithrim_bench.harness.judges import recommend_reviewer_mode


def test_multi_specialist_pack_recommends_the_panel():
    rec = recommend_reviewer_mode(
        panel=["risk_judge", "policy_judge", "faithfulness_judge"],
        selectable=["risk_judge", "policy_judge", "faithfulness_judge", "generalist_reviewer"],
    )
    assert rec["mode"] == "panel"
    assert rec["reviewer"] is None
    assert rec["k"] is None
    assert "specialist" in rec["rationale"].lower()


def test_single_lens_pack_recommends_a_generalist_with_k():
    """One specialist + an opt-in generalist lens → recommend the single Generalist with k in 3-8."""
    rec = recommend_reviewer_mode(
        panel=["reviewer"],
        selectable=["reviewer", "generalist_reviewer"],
    )
    assert rec["mode"] == "single"
    assert rec["reviewer"] == "generalist_reviewer"  # prefer the opt-in full-lens generalist
    assert 3 <= rec["k"] <= 8
    assert "generalist" in rec["rationale"].lower()


def test_single_role_pack_no_generalist_recommends_that_role():
    rec = recommend_reviewer_mode(panel=["reviewer"], selectable=["reviewer"])
    assert rec["mode"] == "single"
    assert rec["reviewer"] == "reviewer"
    assert 3 <= rec["k"] <= 8


def test_empty_panel_is_safe():
    rec = recommend_reviewer_mode(panel=[], selectable=[])
    assert rec["mode"] == "single"
    assert rec["reviewer"] is None
    assert isinstance(rec["rationale"], str) and rec["rationale"]
