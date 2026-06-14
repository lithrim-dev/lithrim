#!/usr/bin/env python
"""Seed the clinical ontology from the council seed sources → clinical_v1.json.

This is the *seed-not-import* boundary (WS-1 §3.1). The eval path depends only on
the committed ``packs/healthcare/ontology.json``; this script reads the values out
of ``lithrim_bench/runtime/council/`` ONCE, at seed-build time, and emits a
human-reviewable, byte-deterministic JSON.

Extraction strategy (forced by the runtime's import chain):
  - ``safety_flags`` imports only pydantic, so we import it directly to read the
    23 ``SafetyFlagDefinition`` rows (flag, category, definition, when_to_use,
    when_NOT_to_use, reliability_pillar).
  - ``compliance_council`` does ``import openai`` at module top, which is NOT
    installed in the seed/eval environment — so we CANNOT import it. Post-PACK-1b/2b its
    ``TIER_1_NEVER_EVENTS`` / ``TIER_2_HIGH_RISK`` / ``TIER_3_MEDIUM`` sets AND its
    ``_TIER1_OWNERS`` map are no longer literals (the council resolves them FROM the
    snapshot via ``pack_tiers()`` / ``pack_tier1_owners()``), so we read the tier→label
    map and the owner-map straight from ``taxonomy_snapshot.json`` (the source of truth) —
    no council-source AST parse at all.
  - ``council_roles/*.txt`` numbered "KEY QUESTIONS TO ANSWER" blocks are parsed
    as plain text. Only 3 of the 5 role files carry that block (policy / risk /
    source_message); behavior / faithfulness use a different prose structure and
    contribute no questions this cycle (recorded, not fabricated).

Two non-source values are ratified here AS DATA (not in any seed source):
  - ``severity_map`` — the WS-0 ``_rescore`` thresholds (HIGH/MEDIUM→BLOCK via
    weight>=0.5, LOW→WARN) — WS-0 critique Q4.2.
  - the med presence-check ``verification_contract`` — the promoted WS-0
    ``MedPresenceCheck`` with its extraction strategy as explicit params — Q4.3.

owner_roles policy: populated ONLY from ``_TIER1_OWNERS`` (the authoritative
single-judge-BLOCK ownership map, 8 Tier-1 codes). The role files' "CODES YOU MAY
RAISE" lists are a looser *eligible-raiser* notion and are deliberately NOT merged
in — conflating them would be exactly the story-shaped labeling this repo exists to
prevent. Flags with no entry get ``owner_roles: []``; the full owner set is kept
verbatim (incl. source_message_judge) — the invariant-#4 exclusion is a WS-4
scoring-time rule, not a seed-time edit.

gradeable policy (S-BS-10, Option A — snapshot-authoritative + lint gate): a flag
is ``gradeable`` iff the runtime council assigns it a tier (``bool(tier)`` — i.e.
the council would actually score it). The snapshot
(``packs/healthcare/taxonomy_snapshot.json``, the CLAUDE.md contract-of-record) is the
*gate*: ``--check`` / a fresh build FAILS if any gradeable flag is outside the
snapshot's 19-code tier union. In steady state runtime-tier and the snapshot agree,
so gradeable == in-snapshot; the lint fires only when the council tiers a flag the
snapshot has not blessed (the fix is to re-snapshot, never to hand-edit — CLAUDE.md
§"Taxonomy snapshot is the contract"). Out-of-snapshot flags (the 4 fork flags
FABRICATED_CONSENT_SCOPE / MALAFFI_CODE_PROPAGATION / MISSING_DUAL_CODING /
WRONG_PATIENT_INFO) carry ``gradeable=false, tier=null`` and are skip-logged by
grounding, never scored.

    python scripts/seed_ontology.py            # writes packs/healthcare/ontology.json
    python scripts/seed_ontology.py --check     # fail if the committed seed is stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# CE-PACK-6b-CLEAN D2-a: the safety-flag seed relocated OUT of the core into the pack
# (the core ``safety_flags.py`` is deleted in this cycle with build_prompt). The seed is
# now read BY FILE PATH from its pack home (the pack-code-by-path convention).
SAFETY_FLAGS_SEED_PY = REPO_ROOT / "packs" / "healthcare" / "safety_flags_seed.py"
ROLE_DIR = REPO_ROOT / "packs" / "healthcare" / "council_roles"  # PACK-2: relocated into the pack
OUT_PATH = REPO_ROOT / "packs" / "healthcare" / "ontology.json"
SNAPSHOT_PATH = REPO_ROOT / "packs" / "healthcare" / "taxonomy_snapshot.json"

ONTOLOGY_VERSION = "clinical/1"
DOMAIN = "clinical"

# Role files that carry a numbered "KEY QUESTIONS TO ANSWER" block (drift note:
# the WS-1 driver §1 said all 5; only these 3 actually do).
QUESTION_ROLE_FILES = ("policy_judge", "risk_judge", "source_message_judge")

# WS-0 critique Q4.2 — ratified severity→verdict thresholds, recorded as data.
SEVERITY_MAP = {
    "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2},
    "block_at_or_above": 0.5,
    "warn_above": 0.0,
}

# WS-0 critique Q4.3 — the promoted MedPresenceCheck, extraction strategy as
# explicit params (mirrors the WS-0 grounding constants verbatim).
MED_PRESENCE_CONTRACT = {
    "flag_code": "MEDICATION_NOT_IN_TRANSCRIPT",
    "question": "Is the flagged medication actually present in the transcript?",
    "contract_type": "presence_check",
    "version": "med-presence-check/v1",
    "params": {
        "med_source": "patient_profile.active_medications",
        "token_min_len": 4,
        "dosage_regex": r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|%)\b",
        "noise_tokens": [
            "oral",
            "tablet",
            "tablets",
            "capsule",
            "capsules",
            "extended",
            "release",
            "mucosal",
            "spray",
            "injection",
            "solution",
            "suspension",
            "hr",
            "er",
            "xr",
            "actuat",
            "mg",
            "mcg",
            "ml",
        ],
    },
}

# TERMINOLOGY-1 (TOOL-2): the FABRICATED_HISTORY grounding contract evolved from the
# GROUND-FLOOR-1 record_presence (snomed_core STRING set-membership) to snomed_subsumption —
# code-based grounding over the Hermes SNOMED MCP server. The executor (healthcare/floors.py
# SnomedSubsumptionGrounding, contract_type="snomed_subsumption") resolves each documented PMH
# item AND each record condition to a SNOMED concept and clears the item iff it is == or
# subsumed-by (is-a) a record concept, so a clinically-valid SPECIFICITY (note "Type 2 diabetes"
# vs record general "Diabetes mellitus") is correctly grounded where the string match wrongly
# flagged it. This literal mirrors the live pack ontology so a future re-seed reproduces the
# supersession (record_presence -> snomed_subsumption). NOTE: this script is independently
# PACK-DIST-2-stale (OUT_PATH/SAFETY_FLAGS_SEED_PY/SNAPSHOT_PATH still point at the relocated
# in-repo packs/healthcare/); re-point before any re-seed.
FABRICATED_HISTORY_CONTRACT = {
    "flag_code": "FABRICATED_HISTORY",
    "question": "Is each documented history item grounded in the patient record?",
    "contract_type": "snomed_subsumption",
    "version": "snomed-subsumption/v1",
    "params": {
        "oracle_path": "patient_profile.conditions",
        "extractor": "soap_pmh_items",
        "tool": "hermes_snomed",
    },
}


def load_snapshot_codes(path: Path = SNAPSHOT_PATH) -> set[str]:
    """The 19-code tier union from ``taxonomy_snapshot.json`` — the gradeable gate.

    The snapshot is the CLAUDE.md contract-of-record; its ``tiers`` union (tier_1 +
    tier_2 + tier_3) is the authoritative set of codes the harness may score.
    """
    data = json.loads(path.read_text())
    codes: set[str] = set()
    for tier_codes in data["tiers"].values():
        codes.update(tier_codes)
    return codes


def gradeable_flags_outside_snapshot(flags: list[dict], snapshot_codes: set[str]) -> list[str]:
    """S-BS-10 lint: gradeable flags that the snapshot has NOT blessed (a failure).

    Pure so it is unit-testable on a crafted (flags, snapshot) pair. A non-empty
    return is a hard seed error: the runtime council tiers a flag the snapshot does
    not carry — re-snapshot (``scripts/snapshot_taxonomy.py``), never hand-edit.
    """
    return sorted(
        f["flag"] for f in flags if f.get("gradeable") and f["flag"] not in snapshot_codes
    )


def parse_tiers_and_owners(
    snapshot_path: Path = SNAPSHOT_PATH,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """The tier→label map + the Tier-1 owner-map, both read from ``taxonomy_snapshot.json``.

    Post-PACK-1b/2b the FROZEN council resolves BOTH its tier sets AND its ``_TIER1_OWNERS``
    map FROM the snapshot (the source of truth), so neither is literal-evalable from the council
    source any more — we read both straight from ``taxonomy_snapshot.json`` (no council import;
    ``openai`` is absent in the seed env)."""
    snap = json.loads(snapshot_path.read_text())
    tiers = snap["tiers"]
    tier_of: dict[str, str] = {}
    for tier_name, label in (
        ("TIER_1_NEVER_EVENTS", "TIER_1"),
        ("TIER_2_HIGH_RISK", "TIER_2"),
        ("TIER_3_MEDIUM", "TIER_3"),
    ):
        for code in tiers[tier_name]:
            tier_of[code] = label

    owners = {code: sorted(roles) for code, roles in snap["tier1_owners"].items()}
    return tier_of, owners


def parse_questions(role_file: Path) -> list[tuple[int, str]]:
    """Parse a numbered 'KEY QUESTIONS TO ANSWER' block → [(ordinal, text)]."""
    lines = role_file.read_text(encoding="utf-8").splitlines()
    out: list[tuple[int, str]] = []
    started = False
    cur_ord: int | None = None
    cur_parts: list[str] = []

    def flush() -> None:
        if cur_ord is not None and cur_parts:
            out.append((cur_ord, " ".join(p.strip() for p in cur_parts).strip()))

    for line in lines:
        if not started:
            if line.strip().upper().startswith("KEY QUESTIONS TO ANSWER"):
                started = True
            continue
        if not line.strip():
            if cur_ord is not None:  # blank AFTER the first question ends the block
                break
            continue  # leading blank(s) between the header and the first item
        m = re.match(r"^\s*(\d+)\.\s*(.*)$", line)
        if m:
            flush()
            cur_ord, cur_parts = int(m.group(1)), [m.group(2)]
        elif cur_ord is not None:
            cur_parts.append(line)
    flush()
    return out


def _load_safety_flags_seed():
    """Load the pack-resident healthcare safety-flag seed BY FILE PATH — the
    pack-code-by-path convention (cf. ``harness.pack.load_pack_floors``). Pydantic-only
    (no ``openai``); the seed relocated OUT of the core in CE-PACK-6b-CLEAN (D2-a)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "healthcare_safety_flags_seed", SAFETY_FLAGS_SEED_PY
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load the safety-flag seed from {SAFETY_FLAGS_SEED_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_seed() -> dict:
    # 1) flags from the pack-resident safety-flag seed (pydantic-only import is safe).
    sf = _load_safety_flags_seed()

    tier_of, owners = parse_tiers_and_owners()

    flags = []
    for d in sf.SAFETY_FLAG_DEFINITIONS:
        flags.append(
            {
                "flag": d.flag,
                "category": d.category.value,
                "definition": d.definition,
                "when_to_use": d.when_to_use,
                "when_NOT_to_use": d.when_NOT_to_use,
                "owner_roles": owners.get(d.flag, []),
                "tier": tier_of.get(d.flag),
                "gradeable": bool(tier_of.get(d.flag)),
                "reliability_pillar": d.reliability_pillar,
            }
        )
    flags.sort(key=lambda f: f["flag"])

    # 2) questions from the 3 role files that carry the numbered block.
    questions = []
    for role in QUESTION_ROLE_FILES:
        for ordinal, text in parse_questions(ROLE_DIR / f"{role}.txt"):
            questions.append({"role": role, "ordinal": ordinal, "text": text})
    questions.sort(key=lambda q: (q["role"], q["ordinal"]))

    return {
        "ontology_version": ONTOLOGY_VERSION,
        "domain": DOMAIN,
        "taxonomy_version": sf.TAXONOMY_VERSION,
        "severity_map": SEVERITY_MAP,
        "flags": flags,
        "questions": questions,
        "verification_contracts": [MED_PRESENCE_CONTRACT, FABRICATED_HISTORY_CONTRACT],
        "_provenance": {
            "seeded_by": "scripts/seed_ontology.py",
            # D2-a: the AUTHORING-ORIGIN record. The seed relocated to
            # packs/healthcare/safety_flags_seed.py in CE-PACK-6b-CLEAN; this literal is
            # kept VERBATIM so the regenerated ontology stays byte-frozen vs the moat
            # baseline (assert_clinical_ontology_seam_frozen) — it is NOT a live import path.
            "flag_source": "lithrim_bench/runtime/council/safety_flags.py:SAFETY_FLAG_DEFINITIONS",
            "tier_source": "lithrim_bench/runtime/council/compliance_council.py:TIER_1/2/3",
            "owner_source": "lithrim_bench/runtime/council/compliance_council.py:_TIER1_OWNERS",
            "question_source": "lithrim_bench/runtime/council/council_roles/{policy,risk,source_message}_judge.txt",
            "owner_note": (
                "owner_roles is _TIER1_OWNERS only (authoritative single-judge-BLOCK "
                "ownership, 8 Tier-1 codes); role-file CODES-YOU-MAY-RAISE lists are a "
                "looser eligible-raiser notion and are NOT merged. Flags without an "
                "entry have owner_roles=[] by ground truth, not omission."
            ),
            "gradeable_note": (
                "gradeable=bool(tier) (S-BS-10 Option A): a flag is gradeable iff "
                "the runtime council tiers it. The snapshot packs/healthcare/taxonomy_snapshot.json "
                "is the gate — the seed FAILS if a gradeable flag is outside its 19-code "
                "tier union. In steady state gradeable == in-snapshot."
            ),
            "untiered_note": (
                "4 flags are defined but not in any tier set (tier=null, gradeable=false): "
                "they are outside the snapshot tier union (the contract-of-record) and are "
                "reference-only — skip-logged by grounding, never scored."
            ),
        },
    }


def _serialize(seed: dict) -> str:
    return json.dumps(seed, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed clinical_v1 ontology")
    parser.add_argument("--out", default=str(OUT_PATH))
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed seed differs from a fresh build",
    )
    args = parser.parse_args()

    seed = build_seed()

    # Self-check: every tiered/owned code must be a known flag (catches a stale
    # AST-parse against a renamed source).
    flag_codes = {f["flag"] for f in seed["flags"]}
    for f in seed["flags"]:
        if f["owner_roles"] and f["flag"] not in flag_codes:
            raise SystemExit(f"owner for unknown flag {f['flag']}")

    # S-BS-10 gate: the snapshot is the membership authority. A gradeable flag
    # outside the snapshot's 19-code tier union is a hard error — re-snapshot
    # (scripts/snapshot_taxonomy.py), never hand-edit the seed past this.
    snapshot_codes = load_snapshot_codes()
    offenders = gradeable_flags_outside_snapshot(seed["flags"], snapshot_codes)
    if offenders:
        raise SystemExit(
            "S-BS-10 LINT FAIL: gradeable flag(s) outside the taxonomy snapshot "
            f"({SNAPSHOT_PATH.name}): {', '.join(offenders)}. Re-snapshot the taxonomy; "
            "do not hand-edit the seed."
        )
    serialized = _serialize(seed)

    out = Path(args.out)
    if args.check:
        current = out.read_text() if out.exists() else ""
        if current != serialized:
            sys.stderr.write("STALE: committed ontology seed differs from a fresh build.\n")
            return 1
        print(f"OK: {out} is up to date ({len(seed['flags'])} flags).")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(serialized)
    n_owned = sum(1 for f in seed["flags"] if f["owner_roles"])
    n_gradeable = sum(1 for f in seed["flags"] if f["gradeable"])
    n_reference = len(seed["flags"]) - n_gradeable
    print(
        f"wrote {out}: {len(seed['flags'])} flags "
        f"({n_gradeable} gradeable, {n_reference} reference, {n_owned} owner-mapped), "
        f"{len(seed['questions'])} questions, "
        f"{len(seed['verification_contracts'])} contract(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
