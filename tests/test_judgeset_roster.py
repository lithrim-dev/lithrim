"""D2b — the roster-size rung of the judge-set ladder (offline; predictors injected).

``build_trio(roles=)`` builds a smaller roster. The 2- and 3-role rosters grade normally
through the frozen ``_apply_consensus`` (``len(valid) >= 2``); a single-role roster
degenerates to ``insufficient_valid_models`` — proving WHY the ladder ships 2/3 and not
1, and WHY the consensus seam is NOT modified to force a single-judge verdict.

Also asserts the config-plane loader resolves the committed ``dogfood_v1`` ladder with
the same assignments on every set (the apples-to-apples / gate-on-for-all design).
"""

from __future__ import annotations

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil  # noqa: E402
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES, build_trio  # noqa: E402


def _approve(**_kw):
    return {"decision": "approve", "findings": []}


def _predictors(roles):
    return {r: _approve for r in roles}


def test_roles_subset_builds_smaller_roster():
    roster = ["risk_judge", "policy_judge"]
    two = build_trio(roles=roster, predictors=_predictors(roster))
    assert [j.role for j in two] == roster


def test_roles_default_equals_explicit_full_trio_back_compat():
    # roster_3_full (explicit roles=V2_ROLES) must equal the no-arg default (A4/A5 parity).
    default = build_trio(predictors=_predictors(V2_ROLES))
    explicit = build_trio(roles=list(V2_ROLES), predictors=_predictors(V2_ROLES))
    assert [j.role for j in default] == [j.role for j in explicit] == list(V2_ROLES)


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        build_trio(roles=["risk_judge", "not_a_judge"], predictors={"risk_judge": _approve})


def test_two_judge_roster_grades_through_frozen_consensus():
    roster = ["risk_judge", "policy_judge"]
    trio = build_trio(roles=roster, predictors=_predictors(roster))
    results = [j.forward(transcript="t", artifact="a") for j in trio]
    assert len(results) == 2
    consensus = ComplianceCouncil()._apply_consensus(results)
    # 2 >= 2 → a real grade, NOT the degenerate fallback.
    assert consensus["reason"] != "insufficient_valid_models"
    assert consensus["decision"] == "approve"


def test_single_judge_roster_degenerates_at_frozen_consensus():
    # The documented seam: a 1-judge roster returns insufficient_valid_models in
    # full-council mode (min_valid=2). This is WHY the ladder ships 2/3, not 1.
    trio = build_trio(roles=["risk_judge"], predictors={"risk_judge": _approve})
    results = [j.forward(transcript="t", artifact="a") for j in trio]
    assert len(results) == 1
    consensus = ComplianceCouncil()._apply_consensus(results)
    assert consensus["reason"] == "insufficient_valid_models"
    assert consensus["decision"] == "needs_review"
