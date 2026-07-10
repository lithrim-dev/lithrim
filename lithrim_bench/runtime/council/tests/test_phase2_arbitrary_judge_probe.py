"""PHASE-2 PROBE — does the frozen council admit *arbitrary user-created judges*?

SPEC_COMMUNITY_EDITION §8 gates Phase 2 (arbitrary judges referencing the model pool)
behind a "test cheaply BEFORE committing" question:

    does the frozen `_apply_consensus` handle N≠3 votes, AND does every new judge get a
    lens + a Tier-1 owner (the owner↔emit invariant forbids an inert owner)?

This probe answers it deterministically ($0, no LLM, bare-CE) by driving the FROZEN
``ComplianceCouncil._apply_consensus`` (byte-frozen vs acc4973 — UNTOUCHED here) against a
SYNTHETIC, non-clinical taxonomy (monkeypatched onto the module globals the method reads, so
the probe is pack-agnostic and runs in a bare CE checkout), plus a pack-DATA reading of the
in-repo ``support_ticket_qa`` snapshot for the owner↔emit authoring contract.

It asserts on the TIER BOOKKEEPING (``evidence_summary``) — the direct mechanism output — NOT
the composed final ``decision`` (which the v2 veto / artifact-pillar layer confounds, and which
is not the Phase-2 question). Findings doc:
docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md.

Verdict the probe records: arbitrary-N (N≥2) judges work with NO frozen-seam edit; a new
identity is a first-class vote the moment it runs; but its codes only COUNT when they are in
the active pack's taxonomy, and its SOLO one-strike + its lens only exist once the pack
snapshot authors them (production_judges + tier1_owners + lenses). Phase 2 = a structured
authoring bundle over the snapshot, not free-text.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("openai")
pytest.importorskip("tenacity")

import lithrim_bench.runtime.council.compliance_council as cc  # noqa: E402

_VALID_DECISIONS = {"approve", "needs_review", "reject"}
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SUPPORT_SNAPSHOT = _REPO_ROOT / "packs" / "support_ticket_qa" / "taxonomy_snapshot.json"


@pytest.fixture()
def council():
    return cc.ComplianceCouncil()


@pytest.fixture()
def judge():
    """One per-judge result dict in the shape ``_apply_consensus`` consumes (the conftest
    ``judge`` shape, re-declared locally so this probe is self-contained)."""

    def _make(model, decision, *, code=None, evidence=True, confidence=0.9, errors=None):
        findings = []
        if code:
            spans = [{"quote": f"q::{code}", "turn_ids": [1]}] if evidence else []
            findings = [{"taxonomy_code": code, "evidence_spans": spans}]
        return {"model": model, "decision": decision, "confidence": confidence,
                "errors": errors or [], "findings": findings}

    return _make


@pytest.fixture()
def synthetic_taxonomy(monkeypatch):
    """Inject a minimal, NON-CLINICAL taxonomy onto the module globals ``_apply_consensus``
    reads (resolved from the active pack at import — here we override in-process so the probe
    is pack-agnostic + bare-CE). monkeypatch auto-reverts, so the rest of the suite keeps the
    real ``_core`` taxonomy. ``DEMO_NEVER_EVENT`` is a Tier-1 owned by ``policy_judge``."""
    monkeypatch.setattr(cc, "TIER_1_NEVER_EVENTS", {"DEMO_NEVER_EVENT"}, raising=False)
    monkeypatch.setattr(cc, "TIER_2_HIGH_RISK", {"DEMO_HIGH_RISK"}, raising=False)
    monkeypatch.setattr(cc, "TIER_3_MEDIUM", set(), raising=False)
    monkeypatch.setattr(cc, "KNOWN_TAXONOMY_CODES", {"DEMO_NEVER_EVENT", "DEMO_HIGH_RISK"}, raising=False)
    monkeypatch.setattr(cc, "_TIER1_OWNERS", {"DEMO_NEVER_EVENT": {"policy_judge"}}, raising=False)


def _tier1(r):
    return [f.get("violation") for f in r["evidence_summary"].get("tier1_triggered", [])]


def _tier2_flagged(r):
    return [(f.get("violation"), f.get("reason")) for f in r["evidence_summary"].get("tier2_flagged", [])]


# ── Q1: the frozen consensus is len(valid)-driven — N≠3 (N≥2) needs NO seam edit ──────────

def test_consensus_admits_four_judges_including_a_new_role(council, judge):
    """A 4th, NON-standard role (``clinical_safety_judge``) participates without a crash and
    without a hardcoded len==3 assumption — the roster size is dynamic (``len(valid)``)."""
    r = council._apply_consensus([
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
        judge("clinical_safety_judge", "approve"),  # an arbitrary user-created identity
    ])
    assert r["decision"] in _VALID_DECISIONS
    assert r["consensus"] is True


def test_consensus_admits_five_judges_two_new_roles(council, judge):
    """N=5 with two arbitrary identities — still a clean verdict (no role-count ceiling)."""
    r = council._apply_consensus([
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve"),
        judge("faithfulness_judge", "approve"),
        judge("clinical_safety_judge", "approve"),
        judge("billing_judge", "approve"),
    ])
    assert r["decision"] in _VALID_DECISIONS


def test_two_role_roster_grades_single_role_degenerates(council, judge):
    """The frozen floor: full-council mode requires ``len(valid) >= 2``. N=2 grades; a lone
    valid judge degenerates to ``insufficient_valid_models`` — Phase 2 must reject a <2 roster,
    not let it through (a single user-created judge cannot be the whole council)."""
    r2 = council._apply_consensus([
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve"),
    ])
    assert r2["decision"] in _VALID_DECISIONS

    r1 = council._apply_consensus([judge("risk_judge", "approve")])
    assert r1["decision"] == "needs_review"
    assert r1["reason"] == "insufficient_valid_models"


# ── Q2: a new identity IS aggregated; the taxonomy snapshot is the gate ───────────────────

def test_new_role_finding_is_aggregated_into_tier1(council, judge, synthetic_taxonomy):
    """A NEW role's finding counts toward corroboration — the consensus has NO role-allowlist
    (it dedups by ``model``). ``clinical_safety_judge`` + ``policy_judge`` both flag the Tier-1
    code → ``tier1_triggered`` fires. So a new judge is a first-class vote the moment it runs."""
    r = council._apply_consensus([
        judge("clinical_safety_judge", "needs_review", code="DEMO_NEVER_EVENT"),
        judge("policy_judge", "needs_review", code="DEMO_NEVER_EVENT"),
        judge("risk_judge", "approve"),
    ])
    assert _tier1(r) == ["DEMO_NEVER_EVENT"]


def test_unknown_code_is_dropped_the_snapshot_is_the_contract(council, judge, synthetic_taxonomy):
    """A code NOT in the active taxonomy produces NO tier finding — even with two corroborating
    judges + evidence. So a new judge's codes only count once they are in the pack snapshot's
    ``tiers`` (the by-construction admissibility contract)."""
    r = council._apply_consensus([
        judge("risk_judge", "needs_review", code="NOT_IN_TAXONOMY"),
        judge("policy_judge", "needs_review", code="NOT_IN_TAXONOMY"),
        judge("faithfulness_judge", "approve"),
    ])
    assert _tier1(r) == []
    assert _tier2_flagged(r) == []


# ── Q3: ONE-STRIKE authority needs registered OWNERSHIP; corroboration is absolute-2 ──────

def test_new_role_solo_tier1_downgrades_without_ownership(council, judge, synthetic_taxonomy):
    """A new judge's SOLO Tier-1 finding on a code it does NOT own is withheld → it lands in
    ``tier2_flagged`` with reason ``tier1_off_domain_single_judge`` and does NOT trigger the
    never-event one-strike. So Phase-2 authoring must register the judge as the flag's owner in
    ``tier1_owners`` for its solo finding to carry — the owner↔emit invariant."""
    r = council._apply_consensus([
        judge("clinical_safety_judge", "needs_review", code="DEMO_NEVER_EVENT"),
        judge("risk_judge", "approve"),
        judge("policy_judge", "approve"),
    ])
    assert _tier1(r) == []
    assert _tier2_flagged(r) == [("DEMO_NEVER_EVENT", "tier1_off_domain_single_judge")]


def test_registered_owner_solo_one_strike_fires(council, judge, synthetic_taxonomy):
    """The contrast: the REGISTERED owner (``policy_judge`` owns ``DEMO_NEVER_EVENT``) firing
    solo DOES trigger the never-event one-strike. Ownership in the snapshot is what grants
    unilateral authority — so the owner-map is the load-bearing Phase-2 authoring surface."""
    r = council._apply_consensus([
        judge("policy_judge", "needs_review", code="DEMO_NEVER_EVENT"),
        judge("risk_judge", "approve"),
        judge("faithfulness_judge", "approve"),
    ])
    assert _tier1(r) == ["DEMO_NEVER_EVENT"]


def test_corroboration_is_absolute_two_not_proportional_to_n(council, judge, synthetic_taxonomy):
    """The load-bearing FROZEN caveat: 2 corroborating judges trigger the Tier-1 EVEN at N=5.
    The mechanism's "2+ judges with grounded evidence" is an ABSOLUTE floor, not a proportion —
    a bigger council does NOT raise the corroboration bar, and we cannot make it proportional
    without touching the frozen seam. Phase-2 UX must surface this honestly."""
    r = council._apply_consensus([
        judge("policy_judge", "needs_review", code="DEMO_NEVER_EVENT"),
        judge("clinical_safety_judge", "needs_review", code="DEMO_NEVER_EVENT"),  # 2-of-5
        judge("risk_judge", "approve"),
        judge("faithfulness_judge", "approve"),
        judge("billing_judge", "approve"),
    ])
    assert _tier1(r) == ["DEMO_NEVER_EVENT"]


# ── Q4: the lens authority — an unregistered role is MUTE until a lens is authored ────────

def test_unregistered_role_has_empty_lens():
    """The withstands-gate scope-checks every raised code against the role's lens
    (``LENS_BY_ROLE`` ← the snapshot ``lenses`` block). A new role with no ``lenses`` entry has
    an EMPTY lens → every code it raises is out-of-scope (mute) until Phase-2 authoring adds it.
    The standard trio carries a non-empty lens (the contrast that makes this non-vacuous)."""
    from lithrim_bench.runtime.council.judge_metric import LENS_BY_ROLE

    assert LENS_BY_ROLE.get("escalation_judge", frozenset()) == frozenset()
    assert LENS_BY_ROLE.get("risk_judge", frozenset()) != frozenset()


# ── Q5: the owner↔emit AUTHORING CONTRACT, against a REAL non-clinical pack snapshot ──────

def test_support_pack_owner_emit_invariant_and_new_role_must_be_authored():
    """Read the in-repo ``support_ticket_qa`` snapshot and assert the owner↔emit invariant the
    Phase-2 authoring surface must enforce for a new judge:
      (1) every Tier-1 OWNER role is in ``production_judges`` (NO inert owner — a flag owned by
          a non-running judge is forbidden);
      (2) every ``lenses`` role that owns a flag also runs;
      (3) a hypothetical NEW role is absent from production_judges + lenses + tier1_owners — so
          adding a judge means authoring all three blocks consistently, not a free-text name."""
    snap = json.loads(_SUPPORT_SNAPSHOT.read_text())
    production = set(snap["production_judges"])
    owners = snap["tier1_owners"]
    lenses = snap["lenses"]

    owner_roles = {role for roles in owners.values() for role in roles}
    assert owner_roles <= production, f"inert owner(s): {owner_roles - production}"

    new_role = "escalation_judge"
    assert new_role not in production
    assert new_role not in lenses
    assert new_role not in owner_roles
