"""Offline consensus oracle for the ported v2 council (WS-6c, A3).

Each test drives ``ComplianceCouncil._apply_consensus`` with synthesized
per-judge result dicts and asserts the verdict + the tier bookkeeping. Every
expectation was captured from the ACTUAL ported logic (re-derived from
``lithrim-backend@493b533``) and cross-checked against the source it cites — the
oracle documents the ported behavior, it is not a guess.

v2 trio (default): risk_judge (gpt-4.1) · policy_judge (Mistral) ·
faithfulness_judge (Llama, the veto judge). Source anchors are
``compliance_council.py`` line numbers @493b533.

Note on isolating tier rules from the v2 composition: under v2 the FINAL verdict
is the llama-veto composition over RAW votes UNLESS a Tier-1 fires (safety
floor) or the artifact pillar BLOCK/WARN-overrides. So Tier-2/Tier-3 rules are
exercised with ``needs_review`` raw votes (not ``reject``), so the verdict is
driven by the tier→pillar logic rather than a raw ``reject`` vote.
"""
from __future__ import annotations

import pytest

# The council module imports openai + tenacity at top level (the [council]
# extra). Skip the whole oracle cleanly on the offline pydantic+pandas core.
pytest.importorskip("openai")
pytest.importorskip("tenacity")


# ── Tier-1 never-events (:2050) ─────────────────────────────────────────────

def test_tier1_owner_one_strike_rejects(council, judge):
    """Tier-1 + single owning judge + grounded evidence → reject (:2071-2092).

    risk_judge owns FABRICATED_ALLERGY (_TIER1_OWNERS:240); solo firing with a
    span is the never-event one-strike.
    """
    r = council._apply_consensus([
        judge("risk_judge", "reject", code="FABRICATED_ALLERGY"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["FABRICATED_ALLERGY"]
    assert r["artifact_verdict"] == "BLOCK"


def test_tier1_off_domain_single_judge_downgrades(council, judge):
    """Tier-1 fired solo by a NON-owner → downgrade to needs_review (:2093-2111).

    policy_judge does not own WRONG_DOSAGE (owners: behavior/source_message/risk),
    so the one-strike is withheld and the finding lands in tier2_flagged. The raw
    vote is needs_review so the v2 composition does not independently force reject.
    """
    r = council._apply_consensus([
        judge("policy_judge", "needs_review", code="WRONG_DOSAGE"),
        judge("risk_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "needs_review"
    assert r["evidence_summary"]["tier1_triggered"] == []
    flagged = r["evidence_summary"]["tier2_flagged"]
    assert [f["violation"] for f in flagged] == ["WRONG_DOSAGE"]
    assert flagged[0]["reason"] == "tier1_off_domain_single_judge"


def test_tier1_corroborated_two_judges_rejects_regardless_of_ownership(council, judge):
    """2+ judges with grounded evidence → reject even if neither owns it (:2060-2070).

    policy_judge + faithfulness_judge both flag FABRICATED_ALLERGY with spans;
    corroboration overrides ownership.
    """
    r = council._apply_consensus([
        judge("policy_judge", "needs_review", code="FABRICATED_ALLERGY"),
        judge("faithfulness_judge", "needs_review", code="FABRICATED_ALLERGY"),
        judge("risk_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["FABRICATED_ALLERGY"]


# ── S-BS-31: v2 owner reassignment restores one-strike (WS-6c-AGENTIC, A0) ──
# After the D0 _TIER1_OWNERS reassignment, the 3 codes orphaned under v2-only
# (no production owner) get a production-trio owner that ALSO emits the code, so a
# solo grounded fire one-strikes again. Each firing judge votes needs_review (NOT
# reject) so the reject is driven purely by the tier-1 ownership one-strike (the
# safety floor), not by a raw reject vote — isolating exactly the S-BS-31 fix.
# Pre-D0 these solo fires downgraded to needs_review (tier1_off_domain_single_judge).

def test_s_bs_31_missing_allergy_faithfulness_one_strike(council, judge):
    """faithfulness_judge owns+emits MISSING_ALLERGY → solo grounded fire rejects.

    _TIER1_OWNERS['MISSING_ALLERGY'] gained faithfulness_judge (D0); the role prompt
    already emits it (faithfulness_judge.txt:14). risk/policy approve → without the
    one-strike the worst-of would be needs_review; the ownership floor pulls reject.
    """
    r = council._apply_consensus([
        judge("faithfulness_judge", "needs_review", code="MISSING_ALLERGY"),
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["MISSING_ALLERGY"]
    assert r["artifact_verdict"] == "BLOCK"


def test_s_bs_31_value_mismatch_faithfulness_one_strike(council, judge):
    """faithfulness_judge owns+emits VALUE_MISMATCH → solo grounded fire rejects (D0)."""
    r = council._apply_consensus([
        judge("faithfulness_judge", "needs_review", code="VALUE_MISMATCH"),
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["VALUE_MISMATCH"]


def test_s_bs_31_fabricated_consent_policy_one_strike(council, judge):
    """policy_judge owns+emits FABRICATED_CONSENT → solo grounded fire rejects (D0).

    faithfulness(Llama) votes approve here, so absent the one-strike the v2
    llama-veto would compose to approve — the ownership floor still pulls reject.
    """
    r = council._apply_consensus([
        judge("policy_judge", "needs_review", code="FABRICATED_CONSENT"),
        judge("risk_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["FABRICATED_CONSENT"]


def test_s_bs_31_ownership_gate_still_holds_for_nonowner(council, judge):
    """The fix is targeted, not a blanket open: a NON-owner solo fire still downgrades.

    risk_judge is deliberately NOT an owner of MISSING_ALLERGY (it emits
    FABRICATED_ALLERGY, never MISSING_ALLERGY), so a solo risk_judge MISSING_ALLERGY
    fire still withholds the one-strike — proving D0 narrowed ownership by domain
    rather than weakening the gate.
    """
    r = council._apply_consensus([
        judge("risk_judge", "needs_review", code="MISSING_ALLERGY"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "needs_review"
    assert r["evidence_summary"]["tier1_triggered"] == []
    flagged = r["evidence_summary"]["tier2_flagged"]
    assert [f["violation"] for f in flagged] == ["MISSING_ALLERGY"]
    assert flagged[0]["reason"] == "tier1_off_domain_single_judge"


# ── Tier-2 high-risk (:2170) ────────────────────────────────────────────────

def test_tier2_corroborated_two_judges_rejects(council, judge):
    """Tier-2 + 2 judges → tier2_triggered → artifact BLOCK → reject (:2171-2180)."""
    r = council._apply_consensus([
        judge("risk_judge", "needs_review", code="HALLUCINATED_DETAIL"),
        judge("policy_judge", "needs_review", code="HALLUCINATED_DETAIL"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier2_triggered"]] == ["HALLUCINATED_DETAIL"]
    assert r["artifact_verdict"] == "BLOCK"


def test_tier2_single_judge_needs_review(council, judge):
    """Tier-2 + 1 judge → tier2_flagged → artifact WARN → needs_review (:2181-2190)."""
    r = council._apply_consensus([
        judge("risk_judge", "needs_review", code="HALLUCINATED_DETAIL"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "needs_review"
    assert [f["violation"] for f in r["evidence_summary"]["tier2_flagged"]] == ["HALLUCINATED_DETAIL"]
    assert r["artifact_verdict"] == "WARN"


# ── PHI false-positive suppression (:2031-2039) ─────────────────────────────

def test_phi_false_positive_suppressed_when_others_approve(council, judge):
    """Lone policy_judge IMPLICIT_CONFIRMATION_OF_RECORD + others approve → suppressed.

    The known over-trigger pattern is dropped, so no tier fires and the v2
    composition returns approve despite policy's needs_review vote.
    """
    r = council._apply_consensus([
        judge("policy_judge", "needs_review", code="IMPLICIT_CONFIRMATION_OF_RECORD"),
        judge("risk_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "approve"
    assert r["evidence_summary"]["tier3_flagged"] == []
    assert r["evidence_summary"]["tier2_flagged"] == []


# ── v2 llama-veto-approve composition (:1812, :2347) ────────────────────────

def test_llama_veto_approves_over_overstrict_judge(council, judge):
    """faithfulness(Llama)=approve AND no other judge rejects → approve (:1848).

    gpt-4.1 risk_judge is over-strict (needs_review) on a clean; the veto restores
    approve. This is the measured C1/C2 false-positive elimination path.
    """
    r = council._apply_consensus([
        judge("risk_judge", "needs_review"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "approve"


def test_llama_veto_off_when_another_judge_rejects(council, judge):
    """A non-faithfulness reject disables the veto → worst-of → reject (:1848-1851)."""
    r = council._apply_consensus([
        judge("risk_judge", "reject"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "reject"


def test_llama_veto_off_under_tier1_safety_floor(council, judge):
    """Tier-1 triggered → veto skipped, evidence_decision wins (:2349-2350).

    Even though faithfulness votes approve and is the only non-finding judge, the
    grounded Tier-1 never-event pulls to reject — the safety floor.
    """
    r = council._apply_consensus([
        judge("risk_judge", "reject", code="FABRICATED_ALLERGY"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert [f["violation"] for f in r["evidence_summary"]["tier1_triggered"]] == ["FABRICATED_ALLERGY"]


# ── Always-applied artifact-BLOCK override (:2359-2372) ─────────────────────

def test_artifact_block_overrides_clean_conversation(council, judge):
    """conversation approve + artifact BLOCK → final reject (P0-2 / :2363).

    MEDICATION_NOT_IN_TRANSCRIPT is Tier-2 / ARTIFACT; 2 judges → artifact BLOCK.
    The conversation pillar is clean, but the override forces reject.
    """
    r = council._apply_consensus([
        judge("risk_judge", "needs_review", code="MEDICATION_NOT_IN_TRANSCRIPT"),
        judge("policy_judge", "needs_review", code="MEDICATION_NOT_IN_TRANSCRIPT"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "reject"
    assert r["conversation_verdict"] == "approve"
    assert r["artifact_verdict"] == "BLOCK"


# ── None-confidence (Mistral) tolerance (:2306-2325) ────────────────────────

def test_none_confidence_skipped_in_average(council, judge):
    """[0.92, None, None] → avg 0.92 (None skipped, never coerced to 0.0) (:2319-2325)."""
    r = council._apply_consensus([
        judge("risk_judge", "approve", confidence=0.92),
        judge("policy_judge", "approve", confidence=None),   # Mistral: no logprobs
        judge("faithfulness_judge", "approve", confidence=0.92),
    ])
    assert r["decision"] == "approve"
    assert r["confidence"] == 0.92


def test_all_none_confidence_falls_back_to_zero(council, judge):
    """Degenerate all-None council → 0.0 so uncertainty fires, not NaN (:2325)."""
    r = council._apply_consensus([
        judge("risk_judge", "approve", confidence=None),
        judge("policy_judge", "approve", confidence=None),
        judge("faithfulness_judge", "approve", confidence=None),
    ])
    assert r["confidence"] == 0.0
    assert r["uncertainty"] is True


# ── Degenerate / clean paths ────────────────────────────────────────────────

def test_insufficient_valid_models(council, judge):
    """<2 non-errored judges (full-council) → needs_review (:1880-1888)."""
    r = council._apply_consensus([
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve", errors=["boom"]),
        judge("faithfulness_judge", "approve", errors=["boom"]),
    ])
    assert r["decision"] == "needs_review"
    assert r["reason"] == "insufficient_valid_models"


def test_clean_negative_all_approve(council, judge):
    """No findings + all approve → approve (the by-construction clean negative)."""
    r = council._apply_consensus([
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert r["decision"] == "approve"


# ── NKA exception lives in the PROMPT layer, not consensus math ─────────────

def test_nka_guidance_present_in_role_prompt(council):
    """NKA/NKDA "no-known-allergies ≠ FABRICATED_ALLERGY" is prompt-resident.

    The NKA exception is not consensus arithmetic — it is carried in the
    faithfulness_judge role prompt (the v2 owner). With the legacy ``build_prompt``
    retired (CE-PACK-6b-CLEAN), the role prompt is the single source for this guidance;
    assert it is carried faithfully.
    """
    assert "NKDA" in council._role_prompts["faithfulness_judge"] or \
        "NKA" in council._role_prompts["faithfulness_judge"]


# ── v1 branch is ported verbatim too (differential; driver tests v2 only) ───

def test_v1_branch_diverges_from_v2_on_the_veto_case(council, judge, monkeypatch):
    """Same input, v1 vs v2 diverge → both branches are live and ported (:2347/:2353).

    No findings, votes [needs_review, needs_review, approve]:
      v2 → llama-veto-approve (faithfulness approves, no reject)  → approve
      v1 → majority vote                                          → needs_review
    """
    from lithrim_bench.runtime.council import compliance_council as cc

    results = [
        judge("risk_judge", "needs_review"),
        judge("policy_judge", "needs_review"),
        judge("faithfulness_judge", "approve"),
    ]
    assert council._apply_consensus(results)["decision"] == "approve"  # v2 default

    monkeypatch.setattr(cc.settings, "COMPLIANCE_COUNCIL_VERSION", "v1")
    assert council._apply_consensus(results)["decision"] == "needs_review"  # v1 majority
