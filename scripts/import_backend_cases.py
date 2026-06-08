#!/usr/bin/env python3
"""Import the DOGFOOD-1 starter cases from ``lithrim-backend`` onto the bench.

Reads a fixed set of pre-labeled scenarios from the (READ-ONLY) ``../lithrim-backend``
demo dataset, maps each to a SECOND-CLASS bench row via
:func:`lithrim_bench.importers.backend_demo.load_backend_record`, and writes:

  * ``examples/imported_demo_<pack>.jsonl`` — the imported corpus (lint-exempt; these
    rows carry no by-construction recipe and are stamped ``ground_truth_basis=imported_demo``).
  * ``data/config/agents/imported_<pack>_<scenario>.json`` — one Agent seed per case,
    bound to the committed clinical/1 ontology and the in-process v2 trio.

Taxonomy-lints every flag against the frozen snapshot and prints a drop/rename report.
The snapshot + the first-class ``examples/*.jsonl`` are NEVER touched.

Usage:
  python scripts/import_backend_cases.py [--backend-path ../lithrim-backend] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.importers.backend_demo import load_backend_record  # noqa: E402
from lithrim_bench.taxonomy import load_taxonomy  # noqa: E402

# (pack/domain, source file relative to the backend repo, scenario_id) — the 5 starters.
STARTERS: list[tuple[str, str, str]] = [
    ("scribe", "demo_dataset/scribe_scenarios.jsonl", "scribe_diabetes_soap_clean_compliant"),
    ("scribe", "demo_dataset/scribe_scenarios.jsonl", "scribe_diabetes_soap_clean_violation"),
    ("scribe", "tests/eval_packs/council_v2_smoke.jsonl", "council_v2_smoke_nka_clean"),
    ("coding", "demo_dataset/coding_scenarios.jsonl", "coding_followup_99213_violation"),
    ("scheduling", "demo_dataset/eval_golden.jsonl", "gold_scheduling_clean_booking_comp"),
]

EXAMPLES_DIR = REPO_ROOT / "examples"
AGENTS_DIR = REPO_ROOT / "data" / "config" / "agents"
ONTOLOGY_REF = "clinical/1"
ONTOLOGY_PATH = "data/ontology/clinical_v1.json"


def _find_row(src: Path, scenario_id: str) -> dict | None:
    if not src.exists():
        return None
    for line in src.open():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if (row.get("scenario_id") or row.get("id") or row.get("case_id")) == scenario_id:
            return row
    return None


def _agent_seed(bench_row: dict) -> dict:
    pack = bench_row["pack"]
    scenario = bench_row["source_scenario_id"]
    return {
        "name": f"imported_{pack}_{scenario}",
        "eval_profile": {
            "judges": ["risk_judge", "policy_judge", "faithfulness_judge"],
            "council_config": {
                "disposition": "in-process-v2",
                "compliance_council_version": "v2",
                "note": (
                    "DOGFOOD-1 imported demo case (second-class; ground_truth_basis="
                    "imported_demo). Graded in-process by the v2 trio. Same trio as "
                    "ws0_default; the judge-set ladder varies models/roles at call time."
                ),
            },
            "ontology_ref": ONTOLOGY_REF,
            "ontology_path": ONTOLOGY_PATH,
            "tools": [],
            "kb_bindings": {},
            "severity_map_ref": f"ontology:{ONTOLOGY_REF}",
        },
        "dataset": {
            "case_id": bench_row["case_id"],
            "source": f"examples/imported_demo_{pack}.jsonl",
            "baseline": None,
            "mode": "in_process",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import lithrim-backend demo cases onto the bench")
    parser.add_argument(
        "--backend-path",
        default=str(REPO_ROOT.parent / "lithrim-backend"),
        help="Path to the (read-only) lithrim-backend repo (default: ../lithrim-backend)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the report without writing files"
    )
    args = parser.parse_args(argv)

    backend = Path(args.backend_path).resolve()
    if not backend.exists():
        print(f"ERROR: backend repo not found at {backend}", file=sys.stderr)
        return 1

    taxonomy = load_taxonomy()
    by_pack: dict[str, list[dict]] = {}
    seeds: list[dict] = []
    drops: list[tuple[str, list[str]]] = []
    missing: list[str] = []

    for pack, rel_src, scenario_id in STARTERS:
        row = _find_row(backend / rel_src, scenario_id)
        if row is None:
            missing.append(f"{scenario_id} ({rel_src})")
            continue
        bench_row = load_backend_record(row, pack=pack, taxonomy=taxonomy)
        by_pack.setdefault(pack, []).append(bench_row)
        seeds.append(_agent_seed(bench_row))
        if bench_row["quarantined_flags"]:
            drops.append((bench_row["case_id"], bench_row["quarantined_flags"]))

    if missing:
        print("ERROR: could not locate these starter scenarios:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1

    # ── Report ──────────────────────────────────────────────────────────
    total = sum(len(v) for v in by_pack.values())
    print(f"Imported {total} case(s) across {len(by_pack)} pack(s): {sorted(by_pack)}")
    for pack, rows in sorted(by_pack.items()):
        for r in rows:
            tag = "clean" if r["clean_negative"] else f"flags={r['expected_safety_flags']}"
            print(f"  [{pack}] {r['case_id']}  {r['expected_compliance_verdict']}  {tag}")
    if drops:
        print("\nTAXONOMY DROPS (quarantined — code not in the frozen snapshot):")
        for cid, flags in drops:
            print(f"  - {cid}: {flags}")
    else:
        print("\nTAXONOMY DROPS: none — every imported flag resolves against the snapshot.")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return 0

    # ── Write the imported corpus + agent seeds ─────────────────────────
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    for pack, rows in sorted(by_pack.items()):
        out = EXAMPLES_DIR / f"imported_demo_{pack}.jsonl"
        out.write_text("".join(json.dumps(r) + "\n" for r in rows))
        print(f"wrote {out.relative_to(REPO_ROOT)} ({len(rows)} row(s))")
    for seed in seeds:
        out = AGENTS_DIR / f"{seed['name']}.json"
        out.write_text(json.dumps(seed, indent=2) + "\n")
        print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
