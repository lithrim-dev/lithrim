"""Root conftest — the PACK-DIST clinical skip-when-absent demarcation for the WHOLE suite.

After PACK-DIST-1 the clinical realm (the ``healthcare`` pack + the by-construction
``examples/*.jsonl`` corpora + the clinical demo seeds) lives in the external
``lithrim-pack-healthcare`` repo, NOT in this CE tree. After PACK-DIST-2 the RELOCATED-class
demarcation is fully retired — every whole clinical-only module and every MIXED module's
clinical (RELOCATED) func physically MOVED into the pack repo's ``tests/`` (as a whole module
or a ``tests/test_<module>_relocated.py``), so there is nothing in the CE tree left to
skip-on-relocation. What remains here is the ONE bare-CE demarcation, in one auditable place
(a root conftest so it reaches every subtree — ``tests/`` AND ``lithrim_bench/runtime/*/tests/``):

- **dev / CI** — ``healthcare`` is discoverable (``LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare``
  or the pack pip-installed). The suite pins ``healthcare`` (the subtree conftests) and runs
  everything; the clinical tests live in the pack repo.
- **bare CE** — ``healthcare`` is nowhere. The neutral ``_core`` pack is active; every test that
  grades / pins THROUGH the healthcare pack (``NEEDS_PACK``) skips, and the genuinely
  domain-agnostic proofs (``test_standalone_ce`` / ``test_neutral_default`` / ``test_pack_dist`` +
  the generic unit + interface tests) stay GREEN — proving the core is standalone-domain-agnostic.

One skip trigger (``_NEEDS_PACK_FUNCS``) + one ignore-collect set (``_IGNORE_MODULES_WHEN_BARE_CE``,
for bare-CE modules whose module-level pack reads fail at collection). The lists ARE the
enumeration of what needs the pack.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lithrim_bench.harness import pack as _pack


def _healthcare_discoverable() -> bool:
    try:
        _pack._pack_root("healthcare")
        return True
    except FileNotFoundError:
        return False


def _pack_discoverable(name: str) -> bool:
    try:
        _pack._pack_root(name)
        return True
    except FileNotFoundError:
        return False


def _clinverdict_sample_data_present() -> bool:
    return (Path(__file__).parent / "examples" / "clinverdict" / "clinverdict_mts_v1.jsonl").exists()


# OSS-PREP: narrative/story_audit were archived out of the CE tree (kept under ``_archive/``) to trim
# the public surface. Tests that load them skip/ignore when the pack is absent (mirrors NEEDS_PACK),
# and run again if you restore ``packs/<name>``. Unlike the healthcare demarcation this applies in
# BOTH dev and bare-CE, since these packs are absent regardless of healthcare discoverability.
_IGNORE_MODULES_WHEN_NARRATIVE_ABSENT = {
    "test_narrative_floor",
    "test_narrative_pack",
}
# The clinical-sample corpus (examples/clinverdict/) was archived too; its one reader ignores when absent.
_IGNORE_MODULES_WHEN_CLINVERDICT_DATA_ABSENT = {
    "test_clinverdict_mts_sample",
}
_NEEDS_NARRATIVE_FUNCS = {
    "test_value_presence_floor": {
        "test_value_presence_grades_under_pack_narrative",
        "test_value_presence_is_a_core_floor_available_to_every_pack",
    },
    "test_value_presence_case10": {"test_value_presence_flips_case10_approve_to_block"},
    "test_governed_flip_case10": {
        "test_without_a_mint_the_code_is_inadmissible",
        "test_mint_makes_dissent_erasure_admissible",
        "test_governed_value_presence_flips_case10_approve_to_block",
    },
    "test_narrative_corpus_bridge": {"test_pack_files_first_precedence_preserved_on_collision"},
    "test_pack_layer2c": {
        "test_pack_lenses_accessor_follows_the_named_pack",
        "test_pack_production_judges_accessor_follows_the_named_pack",
    },
    "test_connectors_registry": {
        "test_connectors_list_lists_ingest_sources_only_no_secret",
        "test_connectors_list_follows_active_workspace_pack_not_process_env",
    },
    "test_fauth3_value_presence": {"test_value_presence_skeleton_grades_valid_and_injects"},
    "test_jute_extractor": {"test_proven_template_yields_five_admissible_cases"},
    "test_jute_extractor_newsource": {"test_github_golden_yields_six_admissible_cases"},
}
_NEEDS_STORY_AUDIT_FUNCS = {
    "test_pack_layer2c": {
        "test_council_roster_stays_canonical_under_story_audit_subprocess",
        "test_council_follows_story_audit_roster_and_lens_subprocess",
    },
}


# PACK-DIST-2 (cleanup batch C1): the RELOCATED-class demarcation is now FULLY RETIRED. Every whole
# clinical-only test module MOVED to the pack repo (``../lithrim-pack-healthcare/tests/``) in batch 2,
# and every MIXED module's RELOCATED funcs were EXTRACTED into the pack
# (``tests/test_<module>_relocated.py``) and deleted from the CE module — the named batch-2 set
# (test_audit, test_pack_layer1a/2/3/5a/5b, test_uap3b_withstands, test_ws5_bff) PLUS the final 8
# unlisted MIXED modules in C1 (test_crud_delete, test_judgeset_roster, test_flag_crud, test_uap3_bff,
# test_uap3b2_provenance, test_uap5b_chat, test_uap5c_journey, test_ws2). So there is no in-CE module
# or func left to skip-on-relocation: ``_IGNORE_MODULES_WHEN_RELOCATED`` + ``_RELOCATED_FUNCS`` + the
# ``_clinical_content_present``/relocated branch are GONE. The MIXED modules keep only their generic +
# NEEDS_PACK funcs. ``_IGNORE_MODULES_WHEN_BARE_CE`` + ``_NEEDS_PACK_FUNCS`` (the bare-CE demarcation)
# are KEPT byte-unchanged so a bare CE checkout stays green on the neutral _core pack.
# Whole modules that load the pack's GENERATORS/floors at import (``load_pack_generators()`` etc.)
# — green in dev, but ``None`` at module import in a bare CE checkout → skip-collect when the pack
# is not discoverable (their in-pack-repo home is PACK-DIST-2).
_IGNORE_MODULES_WHEN_BARE_CE = {
    "test_coding_pack",
    "test_hl7_pack",
    "test_scheduling_pack",
    "test_triage_pack",
    "test_fabricated_consent_injector",
    "test_fabricated_history_injector",
    "test_hallucinated_detail_injector",
    "test_missing_allergy_injector",
    "test_value_mismatch_injector",
    "test_wrong_dosage_injector",
    "test_packager",
    "test_structural_backend",
    "test_dosage_floor",
    "test_toolbox",
}
# NEEDS_PACK — the function grades / pins THROUGH the loaded healthcare pack via discovery → green
# in dev (pack discoverable), skip in a bare CE checkout (active pack is the neutral _core).
_NEEDS_PACK_FUNCS = {
    "test_ab_harness": {"test_per_role_score_uses_the_lens"},
    "test_byoc_provider": {
        "test_model_composition_effect_a_claude_seat_flips_the_verdict",
        "test_risk_judge_on_byo_claude_grades_a_case",
    },
    "test_consensus": {
        "test_artifact_block_overrides_clean_conversation",
        "test_llama_veto_off_under_tier1_safety_floor",
        "test_nka_guidance_present_in_role_prompt",
        "test_s_bs_31_fabricated_consent_policy_one_strike",
        "test_s_bs_31_missing_allergy_faithfulness_one_strike",
        "test_s_bs_31_ownership_gate_still_holds_for_nonowner",
        "test_s_bs_31_value_mismatch_faithfulness_one_strike",
        "test_tier1_corroborated_two_judges_rejects_regardless_of_ownership",
        "test_tier1_off_domain_single_judge_downgrades",
        "test_tier1_owner_one_strike_rejects",
        "test_tier2_corroborated_two_judges_rejects",
        "test_tier2_single_judge_needs_review",
    },
    # PACK-DIST-2 D5 (batch-1 fold): the route-revert func seeds the BFF config DB, whose seed path
    # loads the healthcare pack ontology → bare-CE FileNotFoundError; it NEEDS the pack (dev-green).
    "test_grade_wire": {"test_inprocess_reproduces_baseline_semantic_and_composite_verdict"},
    "test_judge_bridge": {
        "test_render_authored_lens_and_questions_reach_the_prompt",
        "test_render_lens_only_when_role_has_no_ontology_questions",
    },
    "test_judge_metric": {
        "test_co_raise_of_expected_code_is_fp_by_default",
        "test_co_raise_of_expected_code_is_neutral_when_aware",
        "test_dspy_metric_hard_accept_under_trace_else_graded",
        "test_false_positive_on_clean_negative_fails_the_gate",
        "test_missed_in_lens_label_fails_the_gate",
        "test_out_of_lens_raise_counts_as_false_positive",
        "test_perfect_in_lens_judge_is_accepted",
    },
    "test_judge_optimize": {
        "test_example_raises_in_lens_distinguishes_positive_from_clean_and_other_lens",
        "test_order_positive_first_surfaces_positives_preserving_order",
        "test_role_relevant_drops_other_lens_only_keeps_clean",
    },
    "test_judges_dspy": {
        "test_a3_artifact_block_overrides_clean_conversation",
        "test_a3_tier1_corroborated_two_judges_reject_regardless_of_ownership",
        "test_a3_tier1_off_domain_single_judge_downgrades",
        "test_a3_tier1_owner_one_strike_rejects",
        "test_a3_tier1_safety_floor_overrides_veto",
        "test_a3_tier2_corroborated_two_judges_reject",
        "test_a3_tier2_single_judge_needs_review",
        "test_seam_shape_is_exactly_what_apply_consensus_reads",
        "test_unknown_code_and_evidenceless_findings_are_dropped",
    },
    "test_pack_layer1a": {
        "test_active_pack_defaults_to_healthcare",
        "test_council_codes_resolve_from_the_pack_without_importing_openai",
        "test_council_known_codes_tracks_active_pack_flip",
        "test_healthcare_pack_is_council_consistent",
        "test_loaded_ontology_is_the_clinical_domain",
    },
    "test_pack_layer1b": {
        "test_council_taxonomy_equals_the_pack_snapshot",
        "test_dspy_taxonomy_prompt_is_byte_identical",
        "test_pack_import_is_heavy_dep_free",
        "test_pack_tiers_accessor_follows_the_named_pack",
        "test_pack_tiers_default_is_the_active_pack",
        "test_snapshot_equals_taxonomy_loader",
    },
    "test_pack_layer2": {
        "test_healthcare_pack_is_judge_consistent",
        "test_pack_prompts_path_resolves_to_the_pack",
    },
    "test_pack_layer2b": {
        "test_council_consensus_membership_is_frozenset_value_stable",
        "test_council_owners_equal_the_pack_snapshot",
        "test_pack_tier1_owners_accessor_follows_the_named_pack",
        "test_pack_tier1_owners_default_is_the_active_pack",
        "test_snapshot_owners_equal_the_acc4973_literal",
    },
    "test_pack_layer2c": {
        "test_lens_by_role_equals_the_acc4973_values_under_healthcare",
        "test_pack_lenses_accessor_follows_the_named_pack",
        "test_pack_lenses_default_is_the_active_pack",
        "test_pack_production_judges_accessor_follows_the_named_pack",
    },
    "test_pack_layer3": {"test_pack_floors_register_the_clinical_executors"},
    "test_pack_layer5a": {
        "test_active_packs_resolves_scribe_from_pack",
        "test_load_pack_generators_cache_identity",
    },
    "test_pack_layer5b": {"test_active_packs_all_five_pack_sourced_and_core_empty"},
    "test_taxonomy": {
        "test_snapshot_loads_and_has_known_codes",
        "test_wrong_dosage_has_production_owners",
    },
    "test_trio_dspy": {
        "test_faithfulness_lens_in_scope_perfect_but_corroboration_is_out_of_lens_fp",
        "test_faithfulness_lens_owner_consistent_judge_accepted",
        "test_faithfulness_off_domain_tier1_single_judge_downgrades",
        "test_faithfulness_owns_missing_allergy_one_strike",
        "test_faithfulness_owns_value_mismatch_one_strike",
        "test_policy_lens_perfect_judge_accepted",
        "test_policy_owns_fabricated_consent_one_strike",
        "test_policy_owns_phi_disclosure_one_strike",
    },
    "test_uap3b2_grounding_check": {"test_declared_groundingcheck_audited_as_independent_entity"},
    "test_uap3b2_provenance": {
        "test_gate_cannot_relabel_true_case",
        "test_frozen_seam_zero_delta",  # the seam guard resolves clinical ontology via discovery
    },
    "test_uap3b_withstands": {
        "test_by_construction_guard_corroborated_owner_not_dropped",
        "test_by_construction_guard_in_lens_true_finding_withstands",
        "test_signals_bus_assembles_ontology_and_validator_signals",
        "test_validator_disproved_finding_suppressed",
        "test_frozen_seam_zero_delta",  # the seam guard resolves clinical ontology via discovery
    },
    "test_ws0": {
        "test_correction_record_emitted",
        "test_med_fp_suppressed_history_retained",
        "test_run_ws0_end_to_end_replay_exit_zero",
    },
    "test_ws1": {
        "test_config_driven_run_reproduces_ws0",
        "test_correction_records_owner_roles_and_real_version",
    },
    "test_ws2": {"test_run_eval_passes_agent_config_to_live_grade"},
    "test_ws5_bff": {
        "test_judges_list_returns_the_v2_trio",
        "test_ontology_read",
        "test_put_ontology_rejects_malformed",
        "test_run_eval_replay_returns_composite_and_calibration_check",
        # GET /v1/case READS the clinical case fixture (relocated to the pack, PACK-DIST-2), so it
        # 404s in a bare CE checkout. It passed in a dev tree only because pack_ws0_dir_or_none()
        # reaches the SIBLING ../lithrim-pack-healthcare (path-based, not discovery-based) — a clean
        # clone under /tmp can't, which the clean-clone smoke caught. NEEDS the pack.
        "test_get_case_reports_labeled_flag",
    },
    # CYCLE-0 (release bare-CE green): the grounding-contract gate/route tests operate on healthcare
    # flags (MEDICATION_NOT_IN_TRANSCRIPT / WRONG_DOSAGE) + the pack's contract types — a bare CE
    # checkout has neither, so the handler errors / pack-load FileNotFoundErrors → NEEDS the pack.
    "test_grounding_contract_gate": {
        "test_grounding_contract_types_endpoint_is_pack_registered",
        "test_accessors_optional_pack_arg_is_additive",
        "test_gate_resolves_the_active_workspace_pack_not_the_process_pack",
    },
    "test_eval_flow": {
        "test_grounding_contract_persists_audited_and_404s",
        "test_grounding_contract_route_reuses_the_bound_op",
        "test_add_grounding_contract_tool_is_bounded_by_the_endpoint_guards",
    },
    # CRITERION-JUTE-1d: the generate/gate/pin endpoint pins an mcp_call contract onto a healthcare
    # flag (UPCODING_RISK) through the FROZEN put path — a bare CE checkout has neither the flag nor
    # the pack ontology seed, so it NEEDS the pack (dev-green, bare-CE skip).
    "test_criterion_jute_1d": {
        "test_preview_returns_argshape_and_gate_report_no_write",
        "test_commit_gate_pass_pins_contract_with_jute_and_sha",
        "test_commit_gate_fail_422_and_no_write",
        "test_commit_unknown_flag_404_no_write",
    },
    # the CORE-FLOOR-1 merge reaching the EXTERNAL healthcare pack (the _core + in-repo narrative
    # halves stay green in bare CE — they prove the floor is domain-agnostic standalone).
    # binds the council from the sibling pack via discovery — already self-skips without the sibling;
    # also skip when healthcare is undiscoverable so a local env-unset run matches the stranger.
    "test_pack_dist": {"test_a1_council_binds_from_external_pack"},
    # REL-5d (fresh-cut sim): these stub the ACTIVE WORKSPACE to ``pack="healthcare"`` inside the
    # test itself (test_tools_endpoint.py:40, test_uap4_optimize_bff.py:74/131,
    # test_optimize_subset.py:113/162 — "the test env discovers ``healthcare``"), so the endpoint's
    # pack resolution FileNotFoundErrors in a bare public clone → NEEDS the pack (dev-green).
    "test_tools_endpoint": {
        "test_post_authors_a_tool_then_get_lists_it",
        "test_get_lists_declared_core_tools_when_none_authored",
        "test_delete_removes_the_authored_tool",
    },
    "test_optimize_subset": {
        "test_endpoint_threads_case_ids_to_the_subprocess",
        "test_endpoint_none_case_ids_is_whole_workspace",
        "test_case_ids_does_not_weaken_the_cost_gate",
    },
    "test_uap4_optimize_bff": {
        "test_optimize_refuses_without_confirm",
        "test_optimize_returns_the_honest_delta_shape",
        "test_optimize_unknown_role_is_404",
        "test_optimize_wires_role_and_limit_to_the_subprocess",
    },
}

# REL-5d: the clinverdict DROP-IN pack (packs-dropin/clinverdict) is deliberately gitignored
# (local-only clinical content; docs/guides/CLINVERDICT_SETUP_GUIDE.md) — absent in any public
# clone. The reviewer-roster funcs that READ it skip when it is not on disk (dev has it → runs).
_CLINVERDICT_DROPIN = Path(__file__).parent / "packs-dropin" / "clinverdict"
_NEEDS_CLINVERDICT_DROPIN_FUNCS = {
    "test_reviewer_roster": {
        "test_clinverdict_generalist_is_not_a_panel_member",
        "test_clinverdict_generalist_is_owner_resident_for_its_tier1_codes",
        "test_clinverdict_generalist_lens_is_full_coverage_union",
        "test_clinverdict_generalist_role_prompt_seed_exists",
        "test_load_role_prompt_resolves_against_an_explicit_prompts_dir",
    },
}


def pytest_ignore_collect(collection_path, config):
    stem = Path(str(collection_path)).stem
    if not _healthcare_discoverable() and stem in _IGNORE_MODULES_WHEN_BARE_CE:
        return True
    if not _pack_discoverable("narrative") and stem in _IGNORE_MODULES_WHEN_NARRATIVE_ABSENT:
        return True
    if not _clinverdict_sample_data_present() and stem in _IGNORE_MODULES_WHEN_CLINVERDICT_DATA_ABSENT:
        return True
    return None


def pytest_collection_modifyitems(config, items):
    # OSS-PREP parked-pack skips (narrative/story_audit under _archive/) — apply in BOTH dev and
    # bare-CE, before the healthcare early-return, since these packs are absent either way.
    narr = _pack_discoverable("narrative")
    story = _pack_discoverable("story_audit")
    if not narr or not story:
        skip_narr = pytest.mark.skip(
            reason="OSS-PREP: pack 'narrative' parked under _archive/ — restore packs/narrative to run"
        )
        skip_story = pytest.mark.skip(
            reason="OSS-PREP: pack 'story_audit' parked under _archive/ — restore packs/story_audit to run"
        )
        for item in items:
            stem = Path(str(item.fspath)).stem
            name = item.originalname or item.name
            if not narr and name in _NEEDS_NARRATIVE_FUNCS.get(stem, ()):
                item.add_marker(skip_narr)
            if not story and name in _NEEDS_STORY_AUDIT_FUNCS.get(stem, ()):
                item.add_marker(skip_story)

    # REL-5d: clinverdict drop-in demarcation — applies in BOTH dev and bare-CE (the drop-in is
    # gitignored local content, so its presence is orthogonal to healthcare discoverability).
    if not _CLINVERDICT_DROPIN.is_dir():
        skip_dropin = pytest.mark.skip(
            reason="clinverdict drop-in pack absent (packs-dropin/clinverdict is gitignored, "
            "local-only clinical content — not part of the public cut)"
        )
        for item in items:
            stem = Path(str(item.fspath)).stem
            name = item.originalname or item.name
            if name in _NEEDS_CLINVERDICT_DROPIN_FUNCS.get(stem, ()):
                item.add_marker(skip_dropin)

    bare_ce = not _healthcare_discoverable()
    if not bare_ce:
        return  # the pack is discoverable — run everything
    skip_bare_ce = pytest.mark.skip(
        reason="PACK-DIST-1: healthcare pack not discoverable (bare CE checkout) — set "
        "LITHRIM_BENCH_PACKS_DIR or install lithrim-pack-healthcare"
    )
    for item in items:
        stem = Path(str(item.fspath)).stem
        name = item.originalname or item.name
        if name in _NEEDS_PACK_FUNCS.get(stem, ()):
            item.add_marker(skip_bare_ce)
