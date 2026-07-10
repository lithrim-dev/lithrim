"""The independent-axes rule table (`outcomes.derive_case_outcome`).

Pure / stdlib-only (no dspy/openai), so it runs on the bare core too. Covers every row of
the owner-locked priority table + the all-axis variance gate + the outcome→verdict mapping.
"""

from __future__ import annotations

from lithrim_bench.runtime.council.outcomes import (
    OUTCOME_TO_VERDICT,
    VARIANCE_THRESHOLD,
    case_outcome_to_verdict,
    derive_case_outcome,
)


def _seam(role, decision, *, variance=0.0, errors=None):
    return {
        "model": role,
        "decision": decision,
        "sampling": {"score_variance": variance},
        "errors": errors or [],
    }


def _trio(risk_d, policy_d, faith_d, *, risk=None, policy=None, faith=None):
    return [
        _seam("risk_judge", risk_d, **(risk or {})),
        _seam("policy_judge", policy_d, **(policy or {})),
        _seam("faithfulness_judge", faith_d, **(faith or {})),
    ]


# ── the priority table, row by row ──────────────────────────────────────────
def test_all_approve_is_clear():
    assert derive_case_outcome(_trio("approve", "approve", "approve")) == "CLEAR"


def test_risk_reject_is_critical():
    assert derive_case_outcome(_trio("reject", "approve", "approve")) == "CRITICAL"


def test_policy_reject_is_policy_violation():
    assert derive_case_outcome(_trio("approve", "reject", "approve")) == "POLICY_VIOLATION"


def test_faithfulness_reject_is_flagged():
    # OWNER 2026-06-29 "if it's wrong, it's wrong": a faithfulness reject is a reject is a
    # BLOCK — never softened to the WARN-class FINDING lane (that downgrade made the case
    # outcome milder than the consensus → the live Finding-title vs Flagged-chip split).
    assert derive_case_outcome(_trio("approve", "approve", "reject")) == "FLAGGED"
    assert case_outcome_to_verdict(derive_case_outcome(_trio("approve", "approve", "reject"))) == "BLOCK"


def test_risk_needs_review_is_risk_flag():
    assert derive_case_outcome(_trio("needs_review", "approve", "approve")) == "RISK_FLAG"


def test_other_needs_review_is_needs_review():
    assert derive_case_outcome(_trio("approve", "needs_review", "approve")) == "NEEDS_REVIEW"
    assert derive_case_outcome(_trio("approve", "approve", "needs_review")) == "NEEDS_REVIEW"


def test_lane_priority_risk_beats_policy_and_faith():
    # all three reject → CRITICAL (risk wins the priority), never aggregated.
    assert derive_case_outcome(_trio("reject", "reject", "reject")) == "CRITICAL"
    # policy + faith reject (risk clean) → POLICY_VIOLATION (policy's dedicated lane beats the
    # generic FLAGGED reject lane). Both are BLOCK-class — the name differs, the verdict doesn't.
    assert derive_case_outcome(_trio("approve", "reject", "reject")) == "POLICY_VIOLATION"


# ── the variance gate (all three axes; >= 0.20) ─────────────────────────────
def test_variance_gate_beats_every_verdict():
    # high Risk variance → NEEDS_REVIEW even though Risk rejects (gate is rule #1).
    assert derive_case_outcome(_trio("reject", "approve", "approve", risk={"variance": 0.20})) == "NEEDS_REVIEW"
    # high Policy variance also gates (all three axes, owner choice).
    assert derive_case_outcome(_trio("approve", "approve", "approve", policy={"variance": 0.25})) == "NEEDS_REVIEW"
    # high Faithfulness variance too.
    assert derive_case_outcome(_trio("approve", "approve", "approve", faith={"variance": 0.30})) == "NEEDS_REVIEW"


def test_variance_below_threshold_does_not_gate():
    assert derive_case_outcome(_trio("reject", "approve", "approve", risk={"variance": 0.19})) == "CRITICAL"
    assert VARIANCE_THRESHOLD == 0.20


def test_errored_reviewer_is_needs_review():
    assert derive_case_outcome(_trio("approve", "approve", "approve", risk={"errors": ["boom"]})) == "NEEDS_REVIEW"


def test_missing_reviewer_does_not_crash():
    # a 2-reviewer roster (no faithfulness) still resolves.
    out = derive_case_outcome([_seam("risk_judge", "approve"), _seam("policy_judge", "reject")])
    assert out == "POLICY_VIOLATION"


# ── the outcome → verdict (gate) mapping ────────────────────────────────────
def test_outcome_to_verdict_mapping():
    assert OUTCOME_TO_VERDICT == {
        "CRITICAL": "BLOCK",
        "POLICY_VIOLATION": "BLOCK",
        "RISK_FLAG": "WARN",
        "FINDING": "BLOCK",
        "FLAGGED": "BLOCK",
        "NEEDS_REVIEW": "WARN",
        "CLEAR": "PASS",
    }
    assert case_outcome_to_verdict("CRITICAL") == "BLOCK"
    assert case_outcome_to_verdict("CLEAR") == "PASS"
    assert case_outcome_to_verdict(None) == "WARN"  # conservative default


# ── S-BS-167: the rule table generalizes to AUTHORED judges ─────────────────
# The 3 V2 roles each have a dedicated lane; an AUTHORED judge (any other role) that
# rejects must still drive a flagged-class (BLOCK) outcome — else the case-outcome
# headline silently under-states the consensus the moment a user authors a reviewer.


def test_authored_judge_reject_drives_flagged_outcome():
    """A1 — mirrors live `clinverdict_case01`: Risk approve, Policy approve,
    Faithfulness needs_review (conf 0.32, var 0.06), authored `erasure_judge` reject
    → FLAGGED → BLOCK (NOT NEEDS_REVIEW/WARN, which drops the authored reject)."""
    results = [
        _seam("risk_judge", "approve"),
        _seam("policy_judge", "approve"),
        _seam("faithfulness_judge", "needs_review", variance=0.06),
        _seam("erasure_judge", "reject"),
    ]
    assert derive_case_outcome(results) == "FLAGGED"
    assert case_outcome_to_verdict(derive_case_outcome(results)) == "BLOCK"


def test_authored_reject_outranks_faithfulness_finding():
    # an authored reject (BLOCK-class) beats a co-occurring faithfulness reject (FINDING/WARN).
    results = [
        _seam("risk_judge", "approve"),
        _seam("policy_judge", "approve"),
        _seam("faithfulness_judge", "reject"),
        _seam("erasure_judge", "reject"),
    ]
    assert derive_case_outcome(results) == "FLAGGED"


def test_known_lane_reject_still_outranks_authored_reject():
    # a Risk reject still wins its dedicated lane (CRITICAL) over an authored reject.
    results = [
        _seam("risk_judge", "reject"),
        _seam("erasure_judge", "reject"),
    ]
    assert derive_case_outcome(results) == "CRITICAL"


def test_authored_needs_review_is_needs_review():
    # an authored judge's needs_review keeps the existing rule-6 NEEDS_REVIEW behaviour.
    results = [
        _seam("risk_judge", "approve"),
        _seam("policy_judge", "approve"),
        _seam("faithfulness_judge", "approve"),
        _seam("erasure_judge", "needs_review"),
    ]
    assert derive_case_outcome(results) == "NEEDS_REVIEW"


def test_authored_approve_does_not_flag():
    # an authored judge that approves alongside a clean trio → CLEAR (no spurious flag).
    results = [
        _seam("risk_judge", "approve"),
        _seam("policy_judge", "approve"),
        _seam("faithfulness_judge", "approve"),
        _seam("erasure_judge", "approve"),
    ]
    assert derive_case_outcome(results) == "CLEAR"


# ── A2: coherence invariant — the headline is never milder than the verdict its ─
# strongest individual reviewer signal demands, per the shipped owner-locked contract.
# Operationally the chip (stage_verdict) and the banner (case_outcome) BOTH derive from
# `case_outcome_to_verdict(derive_case_outcome(...))` on the authored path, so this floor
# IS the coherence the user sees. The floor is role-AWARE (not a flat reject->BLOCK): the
# risk/policy/AUTHORED reject lanes are BLOCK-class, but the owner-locked faithfulness lane
# maps reject -> FINDING (WARN) and the chip respects it (no contradiction). The owner-locked
# variance/error gate (-> NEEDS_REVIEW) is excluded — it is a deliberate human-review WARN.
_SEVERITY = {"PASS": 0, "WARN": 1, "BLOCK": 2}
_KNOWN = ("risk_judge", "policy_judge", "faithfulness_judge")


def _reviewer_floor(role, decision):
    """The minimum verdict the headline must show given ONE reviewer's own signal.

    ANY reviewer reject -> BLOCK (OWNER 2026-06-29 "if it's wrong, it's wrong"; the former
    faithfulness->WARN carve-out is retired); any needs_review -> WARN; approve -> PASS.
    """
    if decision == "reject":
        return "BLOCK"
    if decision == "needs_review":
        return "WARN"
    return "PASS"


def test_outcome_verdict_never_milder_than_consensus():
    import itertools

    decisions = ["approve", "needs_review", "reject"]
    roles = ["risk_judge", "policy_judge", "faithfulness_judge", "erasure_judge"]
    # full low-variance / no-error matrix (3^4 = 81 rows), incl. authored-role rejects.
    for combo in itertools.product(decisions, repeat=len(roles)):
        results = [_seam(role, d) for role, d in zip(roles, combo, strict=True)]
        outcome_verdict = case_outcome_to_verdict(derive_case_outcome(results))
        floor = max(
            (_reviewer_floor(role, d) for role, d in zip(roles, combo, strict=True)),
            key=lambda v: _SEVERITY[v],
        )
        assert _SEVERITY[outcome_verdict] >= _SEVERITY[floor], (
            f"{combo}: outcome {outcome_verdict} milder than coherence floor {floor}"
        )


def test_every_reject_floor_is_block():
    # A2 anchor (non-vacuous): EVERY reviewer reject's coherence floor is BLOCK — authored
    # AND faithfulness alike (the owner directive: a reject is never a WARN-class outcome).
    assert _reviewer_floor("erasure_judge", "reject") == "BLOCK"
    assert _reviewer_floor("faithfulness_judge", "reject") == "BLOCK"
    assert _reviewer_floor("risk_judge", "reject") == "BLOCK"
    assert case_outcome_to_verdict(derive_case_outcome(_trio("approve", "approve", "reject"))) == "BLOCK"
