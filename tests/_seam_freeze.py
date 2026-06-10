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
import json
import subprocess
from pathlib import Path

_JUDGES_DSPY_REL = "lithrim_bench/runtime/council/judges_dspy.py"
_SEAM_BASELINE = "acc4973"  # the UAP-3b parent — the moat-seam pin
# The ONLY symbols BYOC-1 is authorized to change in judges_dspy.py (the provider binder).
_BYOC1_PROVIDER_SEAM = frozenset({"build_judge_lm", "build_trio"})

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


def _toplevel_defs(src_text: str, *, exclude: frozenset[str]) -> dict[str, str]:
    """Map ``{name: verbatim source}`` for every top-level def/class not in ``exclude``."""
    tree = ast.parse(src_text)
    return {
        node.name: ast.get_source_segment(src_text, node)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name not in exclude
    }


def assert_judges_dspy_consensus_seam_frozen(repo: Path) -> None:
    """The consensus seam in ``judges_dspy.py`` (everything except the BYOC-1 provider
    binder ``build_judge_lm``/``build_trio``) is byte-identical to ``acc4973``."""
    base_src = subprocess.run(
        ["git", "show", f"{_SEAM_BASELINE}:{_JUDGES_DSPY_REL}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    cur_src = (repo / _JUDGES_DSPY_REL).read_text()
    base = _toplevel_defs(base_src, exclude=_BYOC1_PROVIDER_SEAM)
    cur = _toplevel_defs(cur_src, exclude=_BYOC1_PROVIDER_SEAM)
    assert set(cur) == set(base), (
        "judges_dspy.py consensus-seam symbol set changed: "
        f"added={sorted(set(cur) - set(base))} removed={sorted(set(base) - set(cur))}"
    )
    drifted = [name for name, src in base.items() if cur[name] != src]
    assert not drifted, f"consensus-seam symbol(s) drifted in judges_dspy.py: {drifted}"


def assert_seed_ontology_path_relocated_only(repo: Path, seed_rel: str) -> None:
    """An agent seed is byte-frozen vs ``acc4973`` EXCEPT its
    ``eval_profile.ontology_path``, which relocated ``data/ontology/clinical_v1.json``
    → ``packs/healthcare/ontology.json`` (PACK-1 A5 re-scope: the seeds get a
    behavior-preserving, path-only update — every other field stays frozen)."""
    base = json.loads(
        subprocess.run(
            ["git", "show", f"{_SEAM_BASELINE}:{seed_rel}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    cur = json.loads((repo / seed_rel).read_text())
    assert base["eval_profile"]["ontology_path"] == _CLINICAL_ONTOLOGY_BASELINE_REL, (
        f"{seed_rel}: baseline ontology_path was not the pre-move clinical path"
    )
    assert cur["eval_profile"]["ontology_path"] == _CLINICAL_ONTOLOGY_REL, (
        f"{seed_rel}: working ontology_path is not the relocated pack path"
    )
    base["eval_profile"]["ontology_path"] = cur["eval_profile"]["ontology_path"]
    assert cur == base, (
        f"{seed_rel} drifted beyond ontology_path (the seed update must be path-only)"
    )


def assert_clinical_ontology_seam_frozen(repo: Path) -> None:
    """The consensus/owner seam in ``clinical_v1.json`` — flags, tiers, owners,
    questions, severity_map, versions — is byte-identical to ``acc4973``; only the
    grounding ``verification_contracts`` array may grow ADDITIVELY.

    GROUND-FLOOR-1 onward, ``verification_contracts`` is the grounding surface that
    evolves phase by phase (med presence_check → record_presence → terminology → …);
    whole-file-pinning it was overly broad. This mirrors the BYOC-1 provider-binder
    carve-out: the moat seam stays provably frozen, only the authorized surface may
    evolve — and even there, existing contracts may not be edited or removed (purely
    additive)."""
    base = json.loads(
        subprocess.run(
            ["git", "show", f"{_SEAM_BASELINE}:{_CLINICAL_ONTOLOGY_BASELINE_REL}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    cur = json.loads((repo / _CLINICAL_ONTOLOGY_REL).read_text())
    base_contracts = base.pop("verification_contracts", [])
    cur_contracts = cur.pop("verification_contracts", [])
    assert cur == base, (
        "clinical_v1.json consensus/owner seam drifted outside verification_contracts "
        "(flags/tiers/owners/questions/severity_map must stay frozen vs acc4973)"
    )
    for c in base_contracts:
        assert c in cur_contracts, (
            "a baseline verification_contract was removed or edited (must be additive): "
            f"{c.get('flag_code')}"
        )


# PACK-1b (layer 1b): the council's taxonomy un-froze. The 3 tier-set LITERALS
# (TIER_1_NEVER_EVENTS/TIER_2_HIGH_RISK/TIER_3_MEDIUM) now resolve from the active pack's
# snapshot via an inline ``__import__`` of ``harness.pack.pack_tiers()`` — the source-of-truth
# flip (the council reads its codes FROM the pack; the values are 0-delta). So the FROZEN
# council now carries TWO authorized carve-outs vs ``acc4973``: the PACK-2 ``_ROLE_PROMPTS_DIR``
# line AND the PACK-1b taxonomy block. The guard admits exactly these, byte-freezing all else.
_COUNCIL_AUTHORIZED_MARKERS = (
    "_ROLE_PROMPTS_DIR",     # PACK-2 prompts-dir carve-out
    "TIER_1_NEVER_EVENTS",   # PACK-1b taxonomy carve-out
    "TIER_2_HIGH_RISK",
    "TIER_3_MEDIUM",
    "KNOWN_TAXONOMY_CODES",
    "pack_tiers",
)
# The exact carve-out CALL signatures that must be present (revert-detection). Reverting
# either carve-out removes its line, so the lower-bound assertion below FAILS — non-vacuous.
_COUNCIL_REQUIRED_CARVEOUTS = (
    '__import__("lithrim_bench.harness.pack", fromlist=["pack_tiers"]).pack_tiers()',
    '__import__("lithrim_bench.harness.pack", fromlist=["pack_prompts_path"]).pack_prompts_path()',
)


def assert_compliance_council_carveouts_only(repo: Path) -> None:
    """``compliance_council.py`` is byte-identical to ``acc4973`` EXCEPT two AUTHORIZED
    carve-outs: the PACK-2 ``_ROLE_PROMPTS_DIR`` line (role prompts → the pack) and the
    PACK-1b taxonomy block (the 3 tier sets → ``pack_tiers()``; the source-of-truth flip).

    Everything else — the consensus engine, the ``CouncilModel`` roster (``:485-516``),
    ``_TIER1_OWNERS``, the ``KNOWN_TAXONOMY_CODES`` union line (unchanged), ``_apply_consensus``,
    ``_load_role_prompts`` — stays FROZEN. The carve-outs are class-/module-level statements,
    so the top-level-symbol freeze (used for ``judges_dspy``) is too coarse; a ``difflib``
    line-diff is used instead.

    Non-vacuous in BOTH directions: (upper bound) every changed hunk must be a ``replace``
    carrying an authorized marker, so an unauthorized edit anywhere else FAILS; (lower bound)
    both carve-out call signatures must be present, so reverting EITHER carve-out FAILS. Honest
    residual (parity with the single-hunk PACK-2 guard this replaces): a malicious line added
    INSIDE an authorized hunk that still carries a marker would pass — the marker bar is not
    lowered, only widened from one carve-out to two."""
    base = subprocess.run(
        ["git", "show", f"{_SEAM_BASELINE}:{_COMPLIANCE_COUNCIL_REL}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines(keepends=True)
    cur_text = (repo / _COMPLIANCE_COUNCIL_REL).read_text()
    assert_council_carveouts_only(base, cur_text)


def assert_council_carveouts_only(base_lines: list[str], cur_text: str) -> None:
    """The pure predicate behind :func:`assert_compliance_council_carveouts_only` — split out
    so the non-vacuity (layer-1b A3) can be pinned on SYNTHESIZED ``cur`` variants without a
    fake git repo: feed the real ``acc4973`` base + a tampered ``cur`` and assert it raises.
    Raises ``AssertionError`` unless ``cur`` is ``base`` plus ONLY the two authorized carve-outs."""
    cur = cur_text.splitlines(keepends=True)
    changed = [
        op for op in difflib.SequenceMatcher(None, base_lines, cur).get_opcodes() if op[0] != "equal"
    ]
    # Upper bound: every changed hunk is an authorized replace (rejects edits elsewhere).
    for tag, i1, i2, j1, j2 in changed:
        assert tag == "replace", (
            f"compliance_council.py change at base L{i1 + 1}-{i2} must be a replace, got {tag!r}"
        )
        changed_base = "".join(base_lines[i1:i2])
        changed_cur = "".join(cur[j1:j2])
        assert any(m in changed_base or m in changed_cur for m in _COUNCIL_AUTHORIZED_MARKERS), (
            "unauthorized changed hunk in compliance_council.py (no taxonomy / prompts-dir "
            f"marker):\n  base={changed_base!r}\n  cur={changed_cur!r}"
        )
    # Lower bound: both carve-outs ARE applied (rejects reverting either).
    for sig in _COUNCIL_REQUIRED_CARVEOUTS:
        assert sig in cur_text, (
            f"compliance_council.py is missing an authorized carve-out (reverted?): {sig!r}"
        )


def assert_council_roles_relocated_only(repo: Path) -> None:
    """The 5 council role prompts are byte-identical to ``acc4973``'s pre-move copies —
    the PACK-2 relocation (D2/A4) is a content-preserving MOVE (git R100). Compares each
    file at its new pack home to the frozen baseline at the old core path."""
    for name in _COUNCIL_ROLE_FILES:
        base = subprocess.run(
            ["git", "show", f"{_SEAM_BASELINE}:{_COUNCIL_ROLES_OLD_DIR}/{name}.txt"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        cur = (repo / _COUNCIL_ROLES_NEW_DIR / f"{name}.txt").read_text()
        assert cur == base, (
            f"{name}.txt drifted vs {_SEAM_BASELINE} (the relocation must be content-identical)"
        )
