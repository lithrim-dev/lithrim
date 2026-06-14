"""Emit the label -> tier -> owning judges -> "owner runs in production?" matrix.

Closes EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md defect D3: declarative
ownership references judges that do not run.

For every flag observed in the golden set, resolves owners via the
snapshotted taxonomy, then asks: does at least one owner appear in
production_judges? If not, the flag has no scoring path and must be
either reassigned, the production config widened, or the case excluded.

Usage:
    python scripts/build_label_owner_matrix.py \
        --golden /path/to/eval_golden.jsonl \
        [--snapshot /path/to/taxonomy_snapshot.json] \
        [--out docs/label_owner_matrix.md]

``--snapshot`` defaults to the active pack's snapshot (resolved via the pack
discovery seam — set ``LITHRIM_BENCH_PACKS_DIR`` / ``LITHRIM_BENCH_PACK`` for an
external pack). With no pack discoverable, resolution fail-closes — there is no
in-repo default to fall back to (the clinical realm relocated out per PACK-DIST-1).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.harness.pack import pack_taxonomy_path
from lithrim_bench.taxonomy import load_taxonomy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", required=True, type=Path)
    ap.add_argument("--snapshot", default=None, type=Path)
    ap.add_argument(
        "--out",
        default=Path(__file__).resolve().parent.parent / "docs" / "label_owner_matrix.md",
        type=Path,
    )
    args = ap.parse_args()

    snapshot = args.snapshot or pack_taxonomy_path()
    taxonomy = load_taxonomy(snapshot)

    code_to_cases: dict[str, list[str]] = defaultdict(list)
    with args.golden.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            case_id = row.get("scenario_id") or row.get("case_id") or "<unknown>"
            for flag in row.get("expected_safety_flags") or []:
                code_to_cases[flag].append(case_id)

    lines: list[str] = []
    lines.append("# Label -> Owner Matrix")
    lines.append("")
    lines.append(f"- Golden set: `{args.golden}`")
    lines.append(f"- Taxonomy snapshot: `{snapshot}`")
    lines.append(f"- Production judges: {sorted(taxonomy.production_judges)}")
    lines.append(f"- Declared but not running: {sorted(taxonomy.declared_but_not_running)}")
    lines.append("")
    lines.append("| Flag | Tier | Declared owners | Production owners | Cases | Production owner runs? |")
    lines.append("|---|---|---|---|---|---|")

    no_owner_rows = 0
    for code in sorted(code_to_cases.keys()):
        tier = taxonomy.tier_of(code) or "UNKNOWN"
        declared = sorted(taxonomy.owners_of(code))
        production = sorted(taxonomy.production_owners_of(code))
        ok = "Y" if (tier in ("TIER_2", "TIER_3") or production) else "**N**"
        if tier == "UNKNOWN":
            ok = "**N (code not in taxonomy)**"
        if tier == "TIER_1" and not production:
            no_owner_rows += 1
        lines.append(
            f"| `{code}` | {tier} | {declared or '(no Tier-1 entry)'} | "
            f"{production or '(none)'} | {len(code_to_cases[code])} | {ok} |"
        )

    lines.append("")
    if no_owner_rows:
        lines.append(
            f"**FAIL:** {no_owner_rows} Tier-1 flag(s) have no production owner. "
            "Per EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md §1.3, resolve by adding "
            "the declared judge to the production config, reassigning ownership "
            "to a running judge, or excluding affected cases."
        )
    else:
        lines.append("OK: every Tier-1 flag in the golden set has at least one production owner.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out}")
    if no_owner_rows:
        print(f"WARN: {no_owner_rows} Tier-1 flag(s) without a production owner")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
