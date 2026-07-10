"""REVIEWER-MODE (single vs multiple reviewers) — the per-agent ``council_config
['reviewer_roster']`` override resolution. A single-element roster is the supported
minimal council (its lone vote drives ``derive_case_outcome``; ``gate_mode`` — derived
from ``len(roles) == 1`` at the grade site — lets the frozen ``_apply_consensus`` populate
findings). Panel (absent/empty) leaves the derived roster untouched.

These pin the pure selection logic (no council import) so both grade paths
(``apps/bff/app.py`` in-process + ``scripts/run_eval.py`` subprocess) share one tested rule.
"""

import json
from pathlib import Path

from lithrim_bench.harness.judges import apply_reviewer_roster, resolve_grade_roster

PROD = ["risk_judge", "policy_judge", "faithfulness_judge", "erasure_judge"]

_CLINVERDICT = Path(__file__).resolve().parent.parent / "packs-dropin" / "clinverdict"


def test_panel_default_leaves_derived_untouched():
    # no council_config / no override → the panel default (derived roster, unchanged)
    assert apply_reviewer_roster(None, None, production=PROD) is None
    assert apply_reviewer_roster(PROD, {}, production=PROD) == PROD
    assert apply_reviewer_roster(None, {"reviewer_roster": []}, production=PROD) is None


def test_single_reviewer_override():
    # a single-element roster runs EXACTLY that reviewer (the "single reviewer" mode)
    out = apply_reviewer_roster(None, {"reviewer_roster": ["faithfulness_judge"]}, production=PROD)
    assert out == ["faithfulness_judge"]
    assert len(out) == 1  # → gate_mode at the grade site


def test_explicit_multi_subset_override():
    # an explicit multi-reviewer subset is honored too (panel of 2)
    out = apply_reviewer_roster(None, {"reviewer_roster": ["risk_judge", "faithfulness_judge"]}, production=PROD)
    assert out == ["risk_judge", "faithfulness_judge"]


def test_roster_filtered_to_production():
    # a stored roster can't invent a reviewer the active pack doesn't run
    out = apply_reviewer_roster(None, {"reviewer_roster": ["faithfulness_judge", "ghost_judge"]}, production=PROD)
    assert out == ["faithfulness_judge"]
    # if the override resolves to nothing valid → fall back to the derived default
    assert apply_reviewer_roster(PROD, {"reviewer_roster": ["ghost_judge"]}, production=PROD) == PROD


def test_no_production_filter_passthrough():
    # production=None disables the membership filter (caller didn't supply the pack roster)
    out = apply_reviewer_roster(None, {"reviewer_roster": ["x_judge"]}, production=None)
    assert out == ["x_judge"]


# ── GENERALIST-1: the shared grade-site roster resolution (both grade paths) ──────────
# resolve_grade_roster composes derive_roster_order (production ∪ authored extras) then the
# per-agent reviewer_roster override, with the allow-set = the DERIVED roster so an AUTHORED
# extra role (a single generalist reviewer) the agent rosters survives the override filter.


def test_resolve_grade_roster_panel_default():
    # no authored extras, no override → None (the full derived default = the panel)
    assert resolve_grade_roster(PROD, None, None, None) is None
    assert resolve_grade_roster(PROD, {}, {}, {}) is None


def test_resolve_grade_roster_authored_extra_no_override():
    # an authored extra (not in the pack panel) joins the derived roster; no override → that N-tet
    assigns = {"generalist_reviewer": ["HISTORY_OMISSION"]}
    assert resolve_grade_roster(PROD, assigns, None, None) == [*PROD, "generalist_reviewer"]


def test_resolve_grade_roster_single_generalist_survives():
    # GENERALIST: the roster names the authored extra → it survives (allow-set = derived roster).
    # Regression guard: passing only the raw panel as the allow-set would drop it (the bug fixed).
    assigns = {"generalist_reviewer": ["HISTORY_OMISSION", "VALUE_MISMATCH"]}
    out = resolve_grade_roster(PROD, assigns, None, {"reviewer_roster": ["generalist_reviewer"]})
    assert out == ["generalist_reviewer"]
    assert len(out) == 1  # → gate_mode (single generalist reviewer) at the grade site


def test_resolve_grade_roster_unknown_role_still_dropped():
    # a roster naming a role that is neither a panel member nor authored is still dropped → fall back
    assert resolve_grade_roster(PROD, None, None, {"reviewer_roster": ["ghost_judge"]}) is None


def test_resolve_grade_roster_single_panel_member():
    # selecting one EXISTING panel reviewer still works (no authored extra needed)
    out = resolve_grade_roster(PROD, None, None, {"reviewer_roster": ["faithfulness_judge"]})
    assert out == ["faithfulness_judge"]


# ── GENERALIST-1: the clinverdict pack carries the generalist role (file-shape pins) ──


def test_clinverdict_generalist_lens_is_full_coverage_union():
    snap = json.loads((_CLINVERDICT / "taxonomy_snapshot.json").read_text())
    gen = set(snap["lenses"]["generalist_reviewer"])
    union = set().union(
        *(set(v) for k, v in snap["lenses"].items() if k != "generalist_reviewer")
    )
    # the generalist's lens is EXACTLY the union of the specialist lenses → 100% coverage
    assert gen == union


def test_clinverdict_generalist_is_owner_resident_for_its_tier1_codes():
    snap = json.loads((_CLINVERDICT / "taxonomy_snapshot.json").read_text())
    gen = set(snap["lenses"]["generalist_reviewer"])
    tier1 = set(snap["tiers"]["TIER_1_NEVER_EVENTS"])
    # owner-consistency (mirrors test_every_tier1_lens_code_is_owner_resident): every Tier-1
    # code in the generalist lens must list generalist_reviewer as an owner
    for code in gen & tier1:
        assert "generalist_reviewer" in snap["tier1_owners"].get(code, []), code


def test_clinverdict_generalist_is_not_a_panel_member():
    snap = json.loads((_CLINVERDICT / "taxonomy_snapshot.json").read_text())
    # the panel stays the 4 specialists — the generalist runs ONLY via an explicit single-roster
    assert "generalist_reviewer" not in snap["production_judges"]


def test_clinverdict_generalist_role_prompt_seed_exists():
    p = _CLINVERDICT / "council_roles" / "generalist_reviewer.txt"
    assert p.exists() and p.read_text(encoding="utf-8").strip()


# ── GENERALIST-1: the pack-consistency roster admits a lens-declared non-panel role ──


def test_roster_admits_a_lens_declared_nonpanel_role():
    # a pack-declared lens role with a relocated prompt but NOT in production_judges is
    # roster-known when the roster unions the pack's lens roles (the additive extension) — so a
    # generalist prompt is not a "stray prompt for an unknown role".
    import pytest

    from lithrim_bench.harness.pack import PackConsistencyError, assert_judges_known

    roster = frozenset({*PROD, "generalist_reviewer"})  # council ∪ panel ∪ lens roles
    # declared judges = the 4 panel; the generalist prompt stem is roster-known, so NO raise
    assert_judges_known(PROD, [*PROD, "generalist_reviewer"], roster=roster, pack="x")
    # non-vacuous: a stray prompt for a role with NO lens declaration still fails closed
    with pytest.raises(PackConsistencyError):
        assert_judges_known(PROD, [*PROD, "ghost_judge"], roster=frozenset(PROD), pack="x")


# ── GENERALIST-1: a non-default-pack role's prompt resolves against an EXPLICIT prompts dir ──
# (the fix for the in-process "judge not set up" 500 — the BFF boots on the default pack, so a
# clinverdict role's .txt only resolves when the caller passes that pack's council_roles dir.)


def test_load_role_prompt_resolves_against_an_explicit_prompts_dir():
    from lithrim_bench.runtime.council.judge_assignment import load_role_prompt

    pd = _CLINVERDICT / "council_roles"
    txt = load_role_prompt("generalist_reviewer", prompts_dir=pd)
    assert "GENERALIST REVIEWER" in txt
    # non-vacuous: a role with no .txt under that dir still raises (not a silent empty prompt)
    import pytest

    with pytest.raises(FileNotFoundError):
        load_role_prompt("nonexistent_role", prompts_dir=pd)
