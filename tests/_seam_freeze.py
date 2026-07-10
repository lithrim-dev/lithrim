"""Shared frozen-seam helper for the council moat guards (BYOC-1 reconciliation).

``build_judge_lm`` + ``build_trio`` are the AUTHORIZED BYOC-1 provider-seam change (driver
A6 explicitly excludes ``build_judge_lm`` from the frozen set). The UAP-3b / UAP-3b-2 moat
guards therefore no longer whole-file-pin ``judges_dspy.py`` to ``acc4973``; instead they
call :func:`assert_judges_dspy_consensus_seam_frozen`, which proves that every OTHER
top-level symbol — the JudgeSignature (``_build_signature``), the per-judge seam dict
(``class Judge``), the finding shape + normalizers (``Finding`` / ``EvidenceSpan`` /
``_validate_findings`` / …), and ``evaluate_dspy`` (the unchanged ``_apply_consensus``
call) — is byte-identical to ``acc4973``. The consensus seam stays provably frozen; only
the provider binder may evolve. Single-sourced so the two guards can never drift apart.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

_JUDGES_DSPY_REL = "lithrim_bench/runtime/council/judges_dspy.py"
_SEAM_BASELINE = "acc4973"  # the UAP-3b parent — the moat-seam pin
# The ONLY symbols BYOC-1 is authorized to change in judges_dspy.py (the provider binder).
_BYOC1_PROVIDER_SEAM = frozenset({"build_judge_lm", "build_trio"})
# CE-PACK-6b-CLEAN: ``_build_signature`` (the JudgeSignature) is genericized — the 4 clinical
# strings → a domain-agnostic scaffold (S-BS-129). Its I/O field NAMES stay byte-stable, but the
# docstring/desc prose changes, so it joins the authorized-to-evolve set. Everything else —
# ``evaluate_dspy`` (the unchanged ``_apply_consensus`` call), ``Judge``, ``Finding`` + the
# normalizers — stays byte-frozen vs acc4973 (the C4 non-vacuity test proves the rest still fails).
_SIGNATURE_GENERICIZE_SEAM = frozenset({"_build_signature"})
# PROVIDER-CENTER-A (S-BS-MR1a-CROSSPROVIDER): the cross-provider-per-role unlock layers a per-role
# provider override ON TOP of ``build_judge_lm`` (already in the seam) + adds two pure provider-seam
# helpers — ``_litellm_prefix`` (the provider/model prefix) + ``_provider_supports_logprobs`` (the
# honest logprobs gate). They are provider-binder support, NOT the consensus seam; ``_apply_consensus``
# / ``evaluate_dspy`` / ``Judge`` / the finding shape stay byte-frozen vs acc4973 (the C4 non-vacuity
# still fires on any edit to those).
_PROVIDER_CENTER_SEAM = frozenset({"_litellm_prefix", "_provider_supports_logprobs"})
# REPRO-1 R2a (3→N roles): the per-role binding generalizes to AUTHORED roles — two more pure
# provider-binder helpers join the seam: ``_role_provider_keys`` (the generic per-role env names
# for ANY role; the trio keeps its legacy short suffixes) + ``_role_setting`` (settings-then-env
# read, since dynamic role keys are not declared Settings fields). Provider-binder support, NOT
# the consensus seam; ``_apply_consensus`` / ``evaluate_dspy`` / ``Judge`` / the finding shape
# stay byte-frozen vs acc4973 (the C4 non-vacuity still fires on any edit to those).
_ROLE_GENERALIZE_SEAM = frozenset({"_role_provider_keys", "_role_setting"})
# DRYRUN-2026-07-03 (stranger journey, live-caught): logprobs support is MODEL-granular (the
# reasoning families reject the param) — ``_model_supports_logprobs`` is one more pure
# provider-binder helper. The consensus seam stays byte-frozen vs acc4973.
_MODEL_LOGPROBS_SEAM = frozenset({"_model_supports_logprobs"})
_AUTHORIZED_JUDGES_SEAM = (
    _BYOC1_PROVIDER_SEAM | _SIGNATURE_GENERICIZE_SEAM | _PROVIDER_CENTER_SEAM
    | _ROLE_GENERALIZE_SEAM | _MODEL_LOGPROBS_SEAM
)

# PACK-2 (layer 2): the clinical council role prompts relocated into the healthcare pack.
# The live council globs the prompt files ITSELF, so relocating them requires repointing
# its ``_ROLE_PROMPTS_DIR`` class attr — the ONE authorized path-only carve-out in the
# otherwise-frozen ``compliance_council.py``. The baseline carries the prompts at the OLD
# core path; the working tree reads the pack home (a content-identical git R100 move).
_COMPLIANCE_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"
_COUNCIL_ROLES_OLD_DIR = "lithrim_bench/runtime/council/council_roles"
_COUNCIL_ROLES_NEW_DIR = "packs/healthcare/council_roles"
_COUNCIL_ROLE_FILES = (
    "risk_judge",
    "policy_judge",
    "faithfulness_judge",
    "behavior_judge",
    "source_message_judge",
)

# The clinical ontology relocated into the healthcare pack (PACK-1, layer 1a). The
# baseline content lives at the OLD path in ``acc4973``; the working tree reads the
# pack location. Comparing them proves the move is content-identical to the frozen
# baseline (PACK-1 A4) — modulo the additive ``verification_contracts`` carve-out.
_CLINICAL_ONTOLOGY_BASELINE_REL = "data/ontology/clinical_v1.json"
_CLINICAL_ONTOLOGY_REL = "packs/healthcare/ontology.json"

# REL-5a (S-REL-13): DUAL-MODE baseline resolution. The public release is a fresh-cut orphan
# history where ``acc4973`` does not exist, and vendoring the baseline is forbidden (it embeds
# clinical ontology + role prompts). ``_resolve_baseline`` is the ONE resolution seam:
# baseline resolvable → the byte-diff attestation below, UNCHANGED; unresolvable → the guards
# compare the SAME extracted frozen sections against ``_FROZEN_SECTION_SHA256`` ("public-mode
# hash pin"; pins computed from the tree at authoring, provenance-chained by
# tests/test_seam_guard_public_mode.py: pins == acc4973-derived), and the two pack-relocation
# guards (ontology / role prompts) SKIP (the healthcare pack is not part of the public cut).


def _resolve_baseline(repo: Path, rel: str, *, baseline: str = _SEAM_BASELINE) -> str | None:
    """``git show`` the frozen baseline for ``rel``; ``None`` when it is unresolvable
    (public fresh-cut / shallow clone — the baseline commit or path is absent).
    REL-5c (S-REL-19): ``baseline`` defaults to the ``acc4973`` moat pin but may name the
    PLUGIN-1 parent (``_PLUGIN1_PARENT``) — the ONE resolution seam serves BOTH baselines."""
    proc = subprocess.run(
        ["git", "show", f"{baseline}:{rel}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


# REL-5c (S-REL-19): the withstands-gate moat pin. ``signals.py`` / ``withstands.py``
# post-date ``acc4973`` (they did not exist there), so their honest baseline is the PLUGIN-1
# parent (D-2, test_plugin_phase1.py). Baseline resolvable → whole-file byte-identity vs the
# parent (WORKING TREE vs blob — strictly stronger than the old committed-HEAD-only diff);
# unresolvable → the whole-FILE sha256 pins below (provenance-chained by
# tests/test_seam_guard_public_mode.py: pins == parent-derived while the history exists).
_PLUGIN1_PARENT = "6234164"
_FROZEN_FILE_SHA256 = {
    "lithrim_bench/runtime/council/signals.py": (
        "78c458fca34d9fff2d089612163ddae4542d86aa9246ccbfd224b44d3955a94e"
    ),
    "lithrim_bench/runtime/council/withstands.py": (
        "facc261244e7b0b5e598cc366a8cc34e6b8e285187964fafc2099f0a65dd574f"
    ),
}


def assert_withstands_gate_file_frozen(repo: Path, rel: str) -> None:
    """``rel`` (a withstands-gate file) is byte-identical to the PLUGIN-1 parent. Public
    mode falls back to the whole-file sha256 pin — same strength per file as the byte-diff."""
    cur = (repo / rel).read_text()
    base = _resolve_baseline(repo, rel, baseline=_PLUGIN1_PARENT)
    if base is None:
        assert hashlib.sha256(cur.encode("utf-8")).hexdigest() == _FROZEN_FILE_SHA256[rel], (
            f"public-mode hash pin: withstands-gate file drifted vs the PLUGIN-1 parent: {rel}"
        )
        return
    assert cur == base, f"{rel} changed vs the PLUGIN-1 parent (the moat must stay untouched)"


_FROZEN_SECTION_SHA256 = {
    "compliance_council.py::_apply_consensus": "d1b7956e70a8f2efe70dba7f1e8a48c10e4914d24d333791cba6f7476ebbe432",
    "compliance_council.py::extract_verdict_confidence": "ed867bce8be313fda9f5d6f40f97f0c45e527203354cbae2982ab9eb1e7ff26a",
    "judges_dspy.py::EvidenceSpan": "e9763529431ac1428ea5c726c31563c8ac400b43f5036b00a64d4b5350056cfc",
    "judges_dspy.py::Finding": "38739c4c94463fc94d03c830dd58364b54bc869024089b9084285096e2ea8497",
    "judges_dspy.py::Judge": "77f8ebb1f716149271f83d0253d63e9cbc4beae94f631a209c1c94b32ba933d4",
    "judges_dspy.py::_get": "e0c3eff117f9900225891b11dce2512016a77443b2c4fb7e32e8f2ccd698ddba",
    "judges_dspy.py::_norm_decision": "ef344d26d551940804024a26ea678fa0e6e49ecf26150bef3c3bf840e329e9ab",
    "judges_dspy.py::_raw_response_for": "b4286ef7f08f8716f287786ef485bd7621ef384567701f391cf9dc37051fd114",
    "judges_dspy.py::_span_to_dict": "564a00929801b8ae827bd173c898d09717799069aaf7c6e756aca53bd18230bc",
    "judges_dspy.py::_validate_findings": "4af6058a1a28d918bb69323aae96421716d9a16c29c24fb42d3fb113084aea39",
    "judges_dspy.py::default_taxonomy_context": "530d2a2718934e3db55676f3786bd28d5a5fff98f3e576ce225a39a66e183dbb",
    "judges_dspy.py::evaluate_dspy": "68486b17807fe7bb47989a12a4b688bf4319076b1515fd631c5a299c74565fa8",
}
_COUNCIL_FROZEN_SECTION_NAMES = ("_apply_consensus", "extract_verdict_confidence")


def _council_frozen_sections(src_text: str) -> dict[str, str]:
    """Extract the pinned council sections by name (method or top-level def). A duplicated
    name concatenates ALL matches, so a shadowing second def still trips its hash pin."""
    found: dict[str, list[str]] = {}
    for node in ast.walk(ast.parse(src_text)):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in _COUNCIL_FROZEN_SECTION_NAMES
        ):
            found.setdefault(node.name, []).append(ast.get_source_segment(src_text, node))
    return {name: "\n\n".join(srcs) for name, srcs in found.items()}


def _assert_sections_match_hash_pins(file_label: str, sections: dict[str, str]) -> None:
    """Public-mode hash pin — same assertion strength per section as the byte-diff: the
    pinned symbol SET must match exactly (a deleted or smuggled section fails), and every
    section's sha256 must equal its pin (any drift fails)."""
    prefix = f"{file_label}::"
    pins = {k[len(prefix) :]: v for k, v in _FROZEN_SECTION_SHA256.items() if k.startswith(prefix)}
    assert set(sections) == set(pins), (
        f"public-mode hash pin: frozen symbol set changed in {file_label}: "
        f"added={sorted(set(sections) - set(pins))} removed={sorted(set(pins) - set(sections))}"
    )
    drifted = [
        name
        for name, src in sections.items()
        if hashlib.sha256(src.encode("utf-8")).hexdigest() != pins[name]
    ]
    assert not drifted, (
        f"public-mode hash pin: frozen section(s) drifted in {file_label}: {drifted}"
    )


def _toplevel_defs(src_text: str, *, exclude: frozenset[str]) -> dict[str, str]:
    """Map ``{name: verbatim source}`` for every top-level def/class not in ``exclude``."""
    tree = ast.parse(src_text)
    return {
        node.name: ast.get_source_segment(src_text, node)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name not in exclude
    }


def _assert_judges_dspy_seam_frozen(base_src: str, cur_src: str) -> None:
    """Pure predicate: every top-level symbol in ``judges_dspy.py`` EXCEPT the authorized
    seam (``_AUTHORIZED_JUDGES_SEAM`` — the BYOC-1 provider binder + the CE-PACK-6b-CLEAN
    ``_build_signature`` genericization) is byte-identical between ``base_src`` and
    ``cur_src``. Split out so the C4 non-vacuity can feed a SYNTHESIZED ``cur_src`` (an edit
    to a frozen symbol such as ``evaluate_dspy`` must still raise)."""
    base = _toplevel_defs(base_src, exclude=_AUTHORIZED_JUDGES_SEAM)
    cur = _toplevel_defs(cur_src, exclude=_AUTHORIZED_JUDGES_SEAM)
    assert set(cur) == set(base), (
        "judges_dspy.py consensus-seam symbol set changed: "
        f"added={sorted(set(cur) - set(base))} removed={sorted(set(base) - set(cur))}"
    )
    drifted = [name for name, src in base.items() if cur[name] != src]
    assert not drifted, f"consensus-seam symbol(s) drifted in judges_dspy.py: {drifted}"


def assert_judges_dspy_consensus_seam_frozen(repo: Path) -> None:
    """The consensus seam in ``judges_dspy.py`` (everything except the BYOC-1 provider
    binder ``build_judge_lm``/``build_trio`` and the CE-PACK-6b-CLEAN ``_build_signature``
    genericization) is byte-identical to ``acc4973``."""
    base_src = _resolve_baseline(repo, _JUDGES_DSPY_REL)
    cur_src = (repo / _JUDGES_DSPY_REL).read_text()
    if base_src is None:
        _assert_sections_match_hash_pins(
            "judges_dspy.py", _toplevel_defs(cur_src, exclude=_AUTHORIZED_JUDGES_SEAM)
        )
        return
    _assert_judges_dspy_seam_frozen(base_src, cur_src)


def assert_clinical_ontology_seam_frozen(repo: Path) -> None:
    """The consensus/owner seam in ``clinical_v1.json`` — flags, tiers, owners,
    questions, severity_map, versions — is byte-identical to ``acc4973``; only the
    grounding ``verification_contracts`` array may grow ADDITIVELY.

    GROUND-FLOOR-1 onward, ``verification_contracts`` is the grounding surface that
    evolves phase by phase (med presence_check → record_presence → terminology → …);
    whole-file-pinning it was overly broad. This mirrors the BYOC-1 provider-binder
    carve-out: the moat seam stays provably frozen, only the authorized surface may
    evolve — and even there, existing contracts may not be edited or removed (purely
    additive).

    PACK-DIST-1: the healthcare ontology relocated to the external pack, so the CURRENT side
    resolves through the discovery SEAM (``pack.pack_ontology_path('healthcare')``) instead of a
    hardcoded ``repo / packs/healthcare/ontology.json`` — it reads the ACTIVE-pack ontology
    wherever it now lives (in-repo, LITHRIM_BENCH_PACKS_DIR, or installed). Raises
    ``FileNotFoundError`` in a bare CE checkout (healthcare nowhere); its callers carry
    ``requires_healthcare_pack`` so they skip-when-absent."""
    from lithrim_bench.harness import pack as _pack

    base_text = _resolve_baseline(repo, _CLINICAL_ONTOLOGY_BASELINE_REL)
    if base_text is None:
        pytest.skip(
            "public-mode: the acc4973 ontology baseline needs the private history "
            "(the healthcare pack is not part of the public cut)"
        )
    base = json.loads(base_text)
    cur = json.loads(_pack.pack_ontology_path("healthcare").read_text())
    _assert_clinical_ontology_frozen(base, cur)


# Owner-authorized post-acc4973 ADDITIVE flags (2026-06-30): new flag entries the external
# healthcare pack added BEYOND the acc4973 baseline, ratified as authorized pack evolution (the same
# spirit as the additive ``verification_contracts`` carve-out). They are dropped from BOTH sides
# before the seam compare, so the consensus/owner seam is checked on the FROZEN flag set — an EDIT
# to an existing flag, an UNLISTED new flag, or any tiers/owners/questions/severity/_provenance
# drift still raises (the non-vacuity guards in test_6bclean_seam_guard.py pin this).
_AUTHORIZED_ADDITIVE_FLAGS = frozenset({"PROXY_MISATTRIBUTION", "HISTORY_OMISSION"})


def _assert_clinical_ontology_frozen(base: dict, cur: dict) -> None:
    """Pure predicate behind :func:`assert_clinical_ontology_seam_frozen` — the
    consensus/owner seam (everything except the additive ``verification_contracts`` and the
    owner-authorized additive flags) is byte-identical. Split out so the C4 non-vacuity can feed a
    SYNTHESIZED tampered ``cur`` (a flags / owner / ``_provenance`` edit must still raise — this is
    what pins the CE-PACK-6b-CLEAN D2-a decision to keep ``flag_source`` VERBATIM). Mutates its args."""
    base_contracts = base.pop("verification_contracts", [])
    cur_contracts = cur.pop("verification_contracts", [])

    def _drop_authorized(d: dict) -> None:
        flags = d.get("flags")
        if isinstance(flags, list):
            d["flags"] = [
                f
                for f in flags
                if (f.get("flag") if isinstance(f, dict) else f) not in _AUTHORIZED_ADDITIVE_FLAGS
            ]

    _drop_authorized(base)
    _drop_authorized(cur)
    assert cur == base, (
        "clinical_v1.json consensus/owner seam drifted outside verification_contracts "
        "(flags/tiers/owners/questions/severity_map must stay frozen vs acc4973)"
    )
    for c in base_contracts:
        assert c in cur_contracts, (
            "a baseline verification_contract was removed or edited (must be additive): "
            f"{c.get('flag_code')}"
        )


# PACK-1b/2b/2c: the council's clinical DATA + roster IDENTITY un-froze in stages — the taxonomy
# (1b), the Tier-1 owner-map (2b), then the roster identity (2c). The 3 tier-set LITERALS
# (TIER_1_NEVER_EVENTS/TIER_2_HIGH_RISK/TIER_3_MEDIUM, PACK-1b), the ``_TIER1_OWNERS`` map (PACK-2b),
# and the v2 roster (PACK-2c) now resolve from the active pack's snapshot via inline ``__import__``s
# of ``harness.pack.pack_tiers()`` / ``pack_tier1_owners()`` / ``pack_production_judges()`` — the
# source-of-truth flip (the council reads its codes + owners + roster identity FROM the pack; the
# values are 0-delta). PACK-2c is the identity↔deployment SPLIT: the pack carries WHICH judges run
# (``pack_production_judges()``), the CORE keeps HOW each runs (``_ROLE_DEPLOYMENT`` — provider /
# Azure model id / capability flags; infra ∉ a domain pack). The CouncilModel deployment literals
# are byte-preserved, so ``council_roster()``'s AST name-collect is untouched. So the FROZEN council
# carries FOUR authorized carve-outs vs ``acc4973``: the PACK-2 ``_ROLE_PROMPTS_DIR`` line, the
# PACK-1b taxonomy block, the PACK-2b owner-map block, AND the PACK-2c roster block. The guard
# admits exactly these, byte-freezing all else.
_COUNCIL_AUTHORIZED_MARKERS = (
    "_ROLE_PROMPTS_DIR",     # PACK-2 prompts-dir carve-out
    "TIER_1_NEVER_EVENTS",   # PACK-1b taxonomy carve-out
    "TIER_2_HIGH_RISK",
    "TIER_3_MEDIUM",
    "KNOWN_TAXONOMY_CODES",
    "pack_tiers",
    "_TIER1_OWNERS",         # PACK-2b owner-map carve-out
    "pack_tier1_owners",
    "_ROLE_DEPLOYMENT",      # PACK-2c roster carve-out (core deployment table; matches _ROLE_DEPLOYMENT_ALL too)
    "pack_production_judges",
    "6b-CLEAN",              # CE-PACK-6b-CLEAN: the transcript-branch raise sentinel (see below)
    "CE-PACK-6c",            # CE-PACK-6c: the source_message-branch raise sentinel (see below)
    "_CONSENSUS_PILLAR_1",   # CONSENSUS-PILLAR-INVARIANT-1 freeze amendment: the pillar-invariant
                             # carve-out — a module-level, pack-derived dual-pillar default for
                             # tiered codes the hardcoded healthcare pillar sets never covered (the
                             # DATA-classification completion the acc4973 freeze predated; in-spirit
                             # with the TIER_* carve-out, _apply_consensus's BODY stays byte-frozen).
)
# CE-PACK-6b-CLEAN: the FROZEN council sheds its last clinical residue. ``build_prompt`` (the
# legacy clinical default-council prompt builder) + its ``safety_flags`` import are DELETED, and
# ``evaluate()``'s transcript branch raises (the authored stage is the single live prompt source,
# OQ-1). This adds TWO authorizations to the carve-out guard, kept non-vacuous by the C4 tests:
#  (a) a ``delete`` hunk is admitted IFF its REMOVED block carries an authorized-deletion marker
#      below (an unauthorized deletion — e.g. ``_apply_consensus`` — carries none, so it FAILS);
#  (b) the transcript-branch ``replace`` carries the cycle sentinel ``6b-CLEAN`` on its raise line
#      (a normal authorized replace under the S-BS-124 per-line bar — no extra line can ride along).
# CE-PACK-6c extends this with the source_message clinical prompt builder. ``evaluate()``'s
# source_message branch reroutes to the authored stage (stages.run_semantic_source_message),
# so ``build_source_message_prompt`` is bench-dead and DELETED; the branch body becomes a
# ``CE-PACK-6c``-marked raise (a normal authorized replace under the per-line bar). An
# unauthorized method deletion (e.g. ``_format_kb_citations``, ``_apply_consensus``) carries
# none of these markers, so it still FAILS — the auth is keyed to the SPECIFIC marker.
_COUNCIL_AUTHORIZED_DELETION_MARKERS = (
    "def build_prompt",                 # the build_prompt method block (compliance_council.py:517-788)
    "from .safety_flags import",        # its get_flag_prompt_section import (compliance_council.py:27)
    "def build_source_message_prompt",  # CE-PACK-6c: the source_message clinical prompt builder
)
# The exact carve-out CALL signatures that must be present (revert-detection). Reverting
# any carve-out removes its line, so the lower-bound assertion below FAILS — non-vacuous.
_COUNCIL_REQUIRED_CARVEOUTS = (
    '__import__("lithrim_bench.harness.pack", fromlist=["pack_tiers"]).pack_tiers()',
    '__import__("lithrim_bench.harness.pack", fromlist=["pack_prompts_path"]).pack_prompts_path()',
    '__import__("lithrim_bench.harness.pack", fromlist=["pack_tier1_owners"]).pack_tier1_owners()',
    '__import__("lithrim_bench.harness.pack", fromlist=["pack_production_judges"]).pack_production_judges()',
)


def assert_compliance_council_carveouts_only(repo: Path) -> None:
    """``compliance_council.py`` is byte-identical to ``acc4973`` EXCEPT four AUTHORIZED
    carve-outs: the PACK-2 ``_ROLE_PROMPTS_DIR`` line (role prompts → the pack), the PACK-1b
    taxonomy block (the 3 tier sets → ``pack_tiers()``), the PACK-2b owner-map block
    (``_TIER1_OWNERS`` → ``pack_tier1_owners()``) — the clinical-DATA source-of-truth flips —
    and the PACK-2c roster block (the v2 roster IDENTITY → ``pack_production_judges()``, the
    identity↔deployment split: the per-role ``CouncilModel`` DEPLOYMENT literals stay byte-frozen
    in core, only the SELECTION moves to the pack).

    Everything else — the consensus engine, the ``CouncilModel`` deployment literals, the v1
    legacy roster, ``LENS_BY_ROLE``'s readers, the ``KNOWN_TAXONOMY_CODES`` union line (unchanged),
    ``_apply_consensus``, ``_load_role_prompts`` — stays FROZEN. The carve-outs are class-/module-level statements,
    so the top-level-symbol freeze (used for ``judges_dspy``) is too coarse; a ``difflib``
    line-diff is used instead.

    Non-vacuous in BOTH directions: (upper bound) every changed hunk must be a ``replace`` whose
    every added CODE line carries an authorized marker (comments/blanks — e.g. the relocated
    provenance — are exempt), so an unauthorized edit anywhere else FAILS *and* a malicious code
    line smuggled inside an authorized hunk FAILS (the PACK-2b per-line hardening, S-BS-124 —
    closes the prior 'a marker-bearing hunk can hide an extra line' residual); (lower bound) all
    three carve-out call signatures must be present, so reverting ANY carve-out FAILS."""
    base_text = _resolve_baseline(repo, _COMPLIANCE_COUNCIL_REL)
    cur_text = (repo / _COMPLIANCE_COUNCIL_REL).read_text()
    if base_text is None:
        _assert_sections_match_hash_pins(
            "compliance_council.py", _council_frozen_sections(cur_text)
        )
        return
    assert_council_carveouts_only(base_text.splitlines(keepends=True), cur_text)


def assert_council_carveouts_only(base_lines: list[str], cur_text: str) -> None:
    """The pure predicate behind :func:`assert_compliance_council_carveouts_only` — split out
    so the non-vacuity (layer-1b A3) can be pinned on SYNTHESIZED ``cur`` variants without a
    fake git repo: feed the real ``acc4973`` base + a tampered ``cur`` and assert it raises.
    Raises ``AssertionError`` unless ``cur`` is ``base`` plus ONLY the two authorized carve-outs."""
    cur = cur_text.splitlines(keepends=True)
    changed = [
        op for op in difflib.SequenceMatcher(None, base_lines, cur).get_opcodes() if op[0] != "equal"
    ]
    # Upper bound: every changed hunk is an authorized replace OR an authorized delete.
    for tag, i1, i2, j1, j2 in changed:
        changed_base = "".join(base_lines[i1:i2])
        changed_cur = "".join(cur[j1:j2])
        # CE-PACK-6b-CLEAN: an authorized DELETION (build_prompt + its safety_flags import) is a
        # ``delete`` opcode — admitted IFF its REMOVED block carries an authorized-deletion marker.
        # An unauthorized deletion (e.g. ``_apply_consensus``) carries none, so it FAILS here. A
        # pure delete adds no lines, so the per-line hardening below is a no-op for it.
        if tag == "delete":
            assert any(m in changed_base for m in _COUNCIL_AUTHORIZED_DELETION_MARKERS), (
                f"unauthorized DELETION in compliance_council.py at base L{i1 + 1}-{i2} "
                f"(no authorized-deletion marker):\n  removed={changed_base!r}"
            )
            continue
        assert tag == "replace", (
            f"compliance_council.py change at base L{i1 + 1}-{i2} must be a replace or an "
            f"authorized delete, got {tag!r}"
        )
        assert any(m in changed_base or m in changed_cur for m in _COUNCIL_AUTHORIZED_MARKERS), (
            "unauthorized changed hunk in compliance_council.py (no taxonomy / prompts-dir / "
            f"owner-map / 6b-CLEAN marker):\n  base={changed_base!r}\n  cur={changed_cur!r}"
        )
        # PACK-2b hardening (S-BS-124): within an authorized hunk, every ADDED *code* line must
        # itself carry a marker — comments (the relocated clinical provenance) and blank lines are
        # exempt. Closes the prior residual where a malicious line could ride inside a marker-bearing
        # hunk: a smuggled code line carries no marker, so it FAILS here. (All real carve-out code
        # lines — the _ROLE_PROMPTS_DIR / _PACK_TIERS / TIER_* / _TIER1_OWNERS assignments — carry
        # one, so the real tree passes.)
        for line in cur[j1:j2]:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert any(m in line for m in _COUNCIL_AUTHORIZED_MARKERS), (
                "unauthorized code line inside an authorized compliance_council.py carve-out "
                f"hunk (no marker): {line!r}"
            )
    # Lower bound: all carve-outs ARE applied (rejects reverting any).
    for sig in _COUNCIL_REQUIRED_CARVEOUTS:
        assert sig in cur_text, (
            f"compliance_council.py is missing an authorized carve-out (reverted?): {sig!r}"
        )


def assert_council_roles_relocated_only(repo: Path) -> None:
    """The 5 council role prompts are byte-identical to ``acc4973``'s pre-move copies —
    the PACK-2 relocation (D2/A4) is a content-preserving MOVE (git R100). Compares each
    file at its CURRENT pack home to the frozen baseline at the old core path.

    PACK-DIST-1: the prompts relocated to the external pack, so the CURRENT side resolves
    through the discovery SEAM (``pack.pack_prompts_path('healthcare')``) — wherever the active
    healthcare pack now lives. Raises ``FileNotFoundError`` in a bare CE checkout WITH the
    private history; callers carry ``requires_healthcare_pack``.

    REL-5d (S-REL-22): the public-mode skip is decided BEFORE any pack discovery. A fresh-cut
    clone lacks BOTH the baseline history AND the pack; discovery-first raised
    ``FileNotFoundError`` from harness/pack.py instead of the honest public-mode skip."""
    bases: dict[str, str] = {}
    for name in _COUNCIL_ROLE_FILES:
        base = _resolve_baseline(repo, f"{_COUNCIL_ROLES_OLD_DIR}/{name}.txt")
        if base is None:
            pytest.skip(
                "public-mode: the acc4973 role-prompt baselines need the private history "
                "(the healthcare pack is not part of the public cut)"
            )
        bases[name] = base

    from lithrim_bench.harness import pack as _pack

    prompts_dir = _pack.pack_prompts_path("healthcare")
    for name, base in bases.items():
        cur = (prompts_dir / f"{name}.txt").read_text()
        assert cur == base, (
            f"{name}.txt drifted vs {_SEAM_BASELINE} (the relocation must be content-identical)"
        )
