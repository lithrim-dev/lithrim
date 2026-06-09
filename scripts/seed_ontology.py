#!/usr/bin/env python
"""Seed the clinical ontology from the council seed sources → clinical_v1.json.

This is the *seed-not-import* boundary (WS-1 §3.1). The eval path depends only on
the committed ``data/ontology/clinical_v1.json``; this script reads the values out
of ``lithrim_bench/runtime/council/`` ONCE, at seed-build time, and emits a
human-reviewable, byte-deterministic JSON.

Extraction strategy (forced by the runtime's import chain):
  - ``safety_flags`` imports only pydantic, so we import it directly to read the
    23 ``SafetyFlagDefinition`` rows (flag, category, definition, when_to_use,
    when_NOT_to_use, reliability_pillar).
  - ``compliance_council`` does ``import openai`` at module top, which is NOT
    installed in the seed/eval environment — so we CANNOT import it. We
    ``ast.literal_eval`` the ``TIER_1_NEVER_EVENTS`` / ``TIER_2_HIGH_RISK`` /
    ``TIER_3_MEDIUM`` set literals and the ``_TIER1_OWNERS`` dict literal straight
    out of the source file.
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
(``taxonomy/taxonomy_snapshot.json``, the CLAUDE.md contract-of-record) is the
*gate*: ``--check`` / a fresh build FAILS if any gradeable flag is outside the
snapshot's 19-code tier union. In steady state runtime-tier and the snapshot agree,
so gradeable == in-snapshot; the lint fires only when the council tiers a flag the
snapshot has not blessed (the fix is to re-snapshot, never to hand-edit — CLAUDE.md
§"Taxonomy snapshot is the contract"). Out-of-snapshot flags (the 4 fork flags
FABRICATED_CONSENT_SCOPE / MALAFFI_CODE_PROPAGATION / MISSING_DUAL_CODING /
WRONG_PATIENT_INFO) carry ``gradeable=false, tier=null`` and are skip-logged by
grounding, never scored.

    python scripts/seed_ontology.py            # writes data/ontology/clinical_v1.json
    python scripts/seed_ontology.py --check     # fail if the committed seed is stale
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNCIL_DIR = REPO_ROOT / "lithrim_bench" / "runtime" / "council"
SAFETY_FLAGS_PY = COUNCIL_DIR / "safety_flags.py"
COMPLIANCE_PY = COUNCIL_DIR / "compliance_council.py"
ROLE_DIR = COUNCIL_DIR / "council_roles"
OUT_PATH = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"
SNAPSHOT_PATH = REPO_ROOT / "taxonomy" / "taxonomy_snapshot.json"

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

# GROUND-FLOOR-1: the record-grounded suppress contract — the S-BS-7 presence-check
# generalized from the transcript to the patient record. The executor (grounding.py
# RecordPresence, contract_type="record_presence") grounds the artifact's documented
# PMH against patient_profile.conditions; a fully-grounded history SUPPRESSES a false
# FABRICATED_HISTORY, a genuinely injected condition leaves it to stand. P0 match is
# the snomed_core STRING set-membership — sound only because the synthetic bench mints
# note PMH and conditions from identical FSN strings; code-based resolution is
# TERMINOLOGY-1. artifact_decode is informational (the plaintext FHIR DocumentReference
# decode is in the executor).
RECORD_PRESENCE_CONTRACT = {
    "flag_code": "FABRICATED_HISTORY",
    "question": "Is each documented history item grounded in the patient record?",
    "contract_type": "record_presence",
    "version": "record-presence/v1",
    "params": {
        "oracle_path": "patient_profile.conditions",
        "extractor": "soap_pmh_items",
        "match": "snomed_core",
        "artifact_decode": "fhir_documentreference",
    },
}


def _module_assign(source: str, name: str) -> ast.expr:
    """Return the value node of a top-level ``name = <literal>`` assignment."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return node.value
    raise KeyError(f"top-level assignment {name!r} not found in source")


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


def parse_tiers_and_owners(source: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """AST-literal-parse the tier sets + _TIER1_OWNERS (no import — openai absent)."""
    tier_of: dict[str, str] = {}
    for tier_name, label in (
        ("TIER_1_NEVER_EVENTS", "TIER_1"),
        ("TIER_2_HIGH_RISK", "TIER_2"),
        ("TIER_3_MEDIUM", "TIER_3"),
    ):
        codes = ast.literal_eval(_module_assign(source, tier_name))
        for code in codes:
            tier_of[code] = label

    owners_raw = ast.literal_eval(_module_assign(source, "_TIER1_OWNERS"))
    owners = {code: sorted(roles) for code, roles in owners_raw.items()}
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


def build_seed() -> dict:
    # 1) flags from the light safety_flags module (pydantic-only import is safe).
    sys.path.insert(0, str(REPO_ROOT))
    from lithrim_bench.runtime.council import safety_flags as sf  # noqa: E402

    tier_of, owners = parse_tiers_and_owners(COMPLIANCE_PY.read_text())

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
        "verification_contracts": [MED_PRESENCE_CONTRACT, RECORD_PRESENCE_CONTRACT],
        "_provenance": {
            "seeded_by": "scripts/seed_ontology.py",
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
                "the runtime council tiers it. The snapshot taxonomy/taxonomy_snapshot.json "
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
