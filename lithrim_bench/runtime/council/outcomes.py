"""Independent-axes case outcome — the explicit rule table over the three reviewers.

The three reviewers (risk_judge, policy_judge, faithfulness_judge) are INDEPENDENT
evaluation axes, NOT a voting council: their verdicts/confidences/variances are never
averaged into a single score. The case-level outcome is derived from this EXPLICIT,
priority-ordered rule table over each reviewer's OWN modal verdict (from ``judge_call``),
its sampling ``score_variance``, and whether it errored.

This lives strictly ABOVE the frozen consensus seam: it consumes the per-judge seam dicts
(``{model(=role), decision, confidence, findings, errors, sampling{...}}``) that the
authored evaluator already holds before ``_apply_consensus`` is called. The frozen
``_apply_consensus`` is still invoked (for findings/evidence_summary) but its aggregated
*decision* is no longer the case verdict — :func:`derive_case_outcome` is.

The rule table (owner-locked; first matching rule wins):

    1. any reviewer errored  OR  any reviewer score_variance >= VARIANCE_THRESHOLD  -> NEEDS_REVIEW
    2. risk_judge          = reject                                                 -> CRITICAL
    3. policy_judge        = reject                                                 -> POLICY_VIOLATION
    4. any AUTHORED judge  = reject                                                 -> FLAGGED
    5. faithfulness_judge  = reject                                                 -> FINDING
    6. risk_judge          = needs_review                                           -> RISK_FLAG
    7. any reviewer        = needs_review                                           -> NEEDS_REVIEW
    8. all                 = approve                                                -> CLEAR

S-BS-167: rules 2/3/5/6 key on the three V2 roles, which each have a dedicated lane.
Rule 4 generalizes the table to AUTHORED judges (any role outside that trio — exactly
the reviewers the product invites users to create): an authored ``reject`` drives a
flagged-class (BLOCK) outcome so the case-outcome headline is never milder than the
frozen consensus the moment a custom reviewer drives the verdict. It sits ABOVE the
faithfulness FINDING lane (BLOCK outranks that WARN-class outcome) but BELOW the
risk/policy reject lanes (those keep their dedicated, more-specific names).

Pure / stdlib-only (no dspy/openai/council import) so it stays importable on the default
core and is offline-testable against synthesized seam dicts.
"""

from __future__ import annotations

from typing import Any, Literal

CaseOutcome = Literal[
    "CRITICAL",
    "POLICY_VIOLATION",
    "RISK_FLAG",
    "FINDING",
    "FLAGGED",
    "NEEDS_REVIEW",
    "CLEAR",
]

# The three V2 roles with dedicated lanes; any reviewer OUTSIDE this set is an AUTHORED judge
# (PHASE2-B / the ClinVerdict suite). An authored reject drives the generic FLAGGED lane.
_KNOWN_ROLES = frozenset({"risk_judge", "policy_judge", "faithfulness_judge"})

# The variance gate (owner-locked): ALL three axes; a reviewer whose sampled verdict is this
# unstable trips NEEDS_REVIEW regardless of its modal verdict. Scores are 0.0/0.5/1.0 per
# sample, so population variance peaks ~0.25; 0.20 ≈ a meaningful split across the samples.
VARIANCE_THRESHOLD = 0.20

# The 6-value outcome → the pipeline's PASS/WARN/BLOCK verdict (the gate/calibration layer
# that downstream code depends on). The named outcome is PRIMARY; this mapping keeps the gate
# coherent underneath. CRITICAL / POLICY_VIOLATION block; the rest warn; only CLEAR passes.
OUTCOME_TO_VERDICT: dict[str, str] = {
    "CRITICAL": "BLOCK",
    "POLICY_VIOLATION": "BLOCK",
    "RISK_FLAG": "WARN",
    "FINDING": "WARN",
    "FLAGGED": "BLOCK",
    "NEEDS_REVIEW": "WARN",
    "CLEAR": "PASS",
}


def case_outcome_to_verdict(outcome: str | None) -> str:
    """Map a named case outcome to PASS/WARN/BLOCK (defaults to WARN — conservative)."""
    return OUTCOME_TO_VERDICT.get(outcome or "", "WARN")


def _decision(seam: dict[str, Any] | None) -> str | None:
    return (seam or {}).get("decision")


def _variance(seam: dict[str, Any] | None) -> float:
    samp = (seam or {}).get("sampling") or {}
    v = samp.get("score_variance")
    return float(v) if isinstance(v, (int, float)) else 0.0


def _errored(seam: dict[str, Any] | None) -> bool:
    return bool((seam or {}).get("errors"))


def derive_case_outcome(
    results: list[dict[str, Any]],
    *,
    variance_threshold: float = VARIANCE_THRESHOLD,
) -> CaseOutcome:
    """Apply the explicit rule table to the per-reviewer seam dicts → the case outcome.

    ``results`` is the list of per-judge seam dicts (each keyed by ``model`` = its role).
    Reviewers are looked up by role; a missing reviewer is treated as absent (its rules just
    don't fire). The reviewers are never aggregated — this picks ONE named outcome by priority.
    """
    by_role = {r.get("model"): r for r in results if isinstance(r, dict)}
    risk = by_role.get("risk_judge")
    policy = by_role.get("policy_judge")
    faith = by_role.get("faithfulness_judge")

    # 1. instability / failure → NEEDS_REVIEW (all three axes gate on variance).
    if any(_errored(r) for r in results) or any(
        _variance(r) >= variance_threshold for r in results
    ):
        return "NEEDS_REVIEW"
    # 2-3. a hard reject in a known lane (severity priority: Risk > Policy).
    if _decision(risk) == "reject":
        return "CRITICAL"
    if _decision(policy) == "reject":
        return "POLICY_VIOLATION"
    # 4. an AUTHORED judge (any role outside the V2 trio) rejects → FLAGGED (BLOCK). Above the
    #    faithfulness FINDING lane so a custom reviewer's block is never under-stated (S-BS-167).
    if any(
        _decision(r) == "reject" and r.get("model") not in _KNOWN_ROLES
        for r in results
        if isinstance(r, dict)
    ):
        return "FLAGGED"
    # 5. faithfulness reject is its own (WARN-class) finding.
    if _decision(faith) == "reject":
        return "FINDING"
    # 6. Risk uncertainty is its own flag.
    if _decision(risk) == "needs_review":
        return "RISK_FLAG"
    # 7. any other reviewer uncertain → NEEDS_REVIEW.
    if any(_decision(r) == "needs_review" for r in results):
        return "NEEDS_REVIEW"
    # 8. nothing fired → CLEAR.
    return "CLEAR"
