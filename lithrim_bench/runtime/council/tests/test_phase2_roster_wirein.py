"""PHASE2-B — the roster wire-in: an AUTHORED new role actually builds + votes.

The PROBE (``test_phase2_arbitrary_judge_probe.py``) proved the FROZEN ``_apply_consensus``
admits N≠3 votes with no seam edit. This file proves the *build path* now lets an authored
role reach that consensus:

  * E — ``build_trio(roles=[4 roles], assignments={new_role:[code]}, predictors={…4…})`` returns
        4 ``Judge``s (the ``V2_ROLES`` allowlist was relaxed to the active pack's
        ``pack_production_judges()`` + the explicitly-passed roles), no ``ValueError``.
  * F — ``build_authored_semantic_stage(… roles=4 …)`` with injected predictors → the frozen
        ``_apply_consensus`` returns a CLEAN verdict (NOT ``insufficient_valid_models``) and the
        new role's vote is in ``consensus["models"]``. The frozen consensus is UNCHANGED — we only
        FEED it 4 results.
  * G — the roles-derivation helper unions ``pack_production_judges()`` with the authored
        assignment/model keys, PRODUCTION ORDER FIRST, authored extras appended (dedup-stable).
  * H — back-compat: ``build_trio(roles=None)`` on the default roster is byte-identical to the
        old 3-role trio (the ``selected == V2_ROLES`` byte-identity), so every existing
        trio/consensus test stays green.

Bare-CE, $0 (no dspy/network): every judge is a mocked predictor, the probe's injection pattern.
"""
from __future__ import annotations

import pytest

pytest.importorskip("openai")
pytest.importorskip("tenacity")

from lithrim_bench.harness.judges import derive_roster_order  # noqa: E402
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES, build_trio  # noqa: E402


def _pred(decision, *, code=None):
    """A $0 predictor returning the dspy-pred-ish object Judge.forward consumes
    (``decision`` + ``findings``); no dspy/network. ``code`` raises one grounded finding."""

    def _call(**_kw):
        findings = []
        if code:
            findings = [{"taxonomy_code": code, "evidence_spans": [{"quote": f"q::{code}", "turn_ids": [1]}]}]
        return type("Pred", (), {"decision": decision, "findings": findings, "confidence": 0.9})()

    return _call


# ── E: build_trio admits an authored 4th role when it is passed in `roles=` ────────────────
def test_build_trio_admits_authored_fourth_role():
    new_role = "escalation_judge"
    roster = [*V2_ROLES, new_role]
    predictors = {r: _pred("approve") for r in roster}
    judges = build_trio(
        predictors=predictors,
        assignments={new_role: ["STYLE_VIOLATION"]},
        roles=roster,
    )
    assert [j.role for j in judges] == roster
    assert len(judges) == 4


def test_build_trio_rejects_a_truly_unknown_role():
    """The relaxed allowlist still REFUSES a role that is neither a production judge nor an
    explicitly-derived authored role — it must be a real, validated identity."""
    with pytest.raises(ValueError):
        build_trio(predictors={"not_a_judge": _pred("approve")}, roles=["not_a_judge"])


# ── F: the authored 4-judge stage votes through the UNCHANGED _apply_consensus ─────────────
def test_four_judge_authored_stage_votes_through_frozen_consensus():
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator

    new_role = "escalation_judge"
    roster = [*V2_ROLES, new_role]
    predictors = {r: _pred("approve") for r in roster}
    evaluator = build_authored_evaluator(
        ontology=None,
        assignments={new_role: ["STYLE_VIOLATION"]},
        predictors=predictors,
        roles=roster,
        apply_gate=False,  # isolate the consensus admission from the withstands-gate
    )
    out = evaluator({"call_context": {"transcript": "t"}, "artifacts": [{"content": "a"}]})

    consensus = out["consensus"]
    # NOT the degenerate insufficient_valid_models — 4 valid judges grade cleanly
    assert consensus["decision"] in {"approve", "needs_review", "reject"}
    assert consensus.get("reason") != "insufficient_valid_models"
    # the new role's vote is present in the per-judge models list the consensus saw
    voters = {m["model"] for m in out["models"]}
    assert new_role in voters
    assert voters == set(roster)


# ── G: the roles-derivation helper — production order first, authored extras appended ──────
def test_derive_roster_order_unions_production_then_authored():
    production = ["risk_judge", "policy_judge", "faithfulness_judge"]
    assignments = {"escalation_judge": ["X"], "risk_judge": ["Y"]}
    models = {"triage_judge": "byo-claude"}
    roles = derive_roster_order(production, assignments, models)
    # production order first (deduped), then the authored extras (assignments ∪ models keys)
    assert roles[:3] == production
    assert set(roles[3:]) == {"escalation_judge", "triage_judge"}
    # no duplicates (risk_judge appears once, from production)
    assert len(roles) == len(set(roles))


def test_derive_roster_order_is_none_when_only_production():
    """No authored judges → the helper returns the bare production roster (callers may pass
    ``None`` instead, but the helper is honest: production-only in, production-only out)."""
    production = ["risk_judge", "policy_judge", "faithfulness_judge"]
    assert derive_roster_order(production, {}, {}) == production


# ── H: back-compat — the default roster (roles=None) is byte-identical to V2_ROLES ─────────
def test_build_trio_default_roster_is_v2_roles_byte_identical():
    judges_none = build_trio(predictors={r: _pred("approve") for r in V2_ROLES})
    judges_explicit = build_trio(
        predictors={r: _pred("approve") for r in V2_ROLES}, roles=list(V2_ROLES)
    )
    assert [j.role for j in judges_none] == list(V2_ROLES)
    assert [j.role for j in judges_explicit] == list(V2_ROLES)
