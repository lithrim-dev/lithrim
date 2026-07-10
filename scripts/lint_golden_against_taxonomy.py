"""Lint a golden JSONL against the snapshotted taxonomy.

Closes EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md defect D1: golden cases
referencing codes the system cannot emit.

For each case, asserts every code in `expected_safety_flags` is in
KNOWN_TAXONOMY_CODES (the union of TIER_1, TIER_2, TIER_3 in the
snapshot). Unknown codes are reported with the case_id; the script
exits non-zero if any case fails.

Usage:
    python scripts/lint_golden_against_taxonomy.py \
        --golden /path/to/eval_golden.jsonl \
        [--snapshot /path/to/taxonomy_snapshot.json]

``--snapshot`` defaults to the active pack's snapshot (resolved via the pack
discovery seam — set ``LITHRIM_BENCH_PACKS_DIR`` / ``LITHRIM_BENCH_PACK`` for an
external pack). With no pack discoverable, resolution fail-closes with a
FileNotFoundError/PackConsistencyError — there is no in-repo default to fall
back to (the clinical realm relocated out per PACK-DIST-1).
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
    args = ap.parse_args()

    snapshot = args.snapshot or pack_taxonomy_path()
    taxonomy = load_taxonomy(snapshot)
    known = taxonomy.known_codes | taxonomy.structural_codes

    bad_cases: list[tuple[str, str, str]] = []
    verdict_flag_violations: list[tuple[str, str, str, object]] = []
    code_use: dict[str, int] = defaultdict(int)
    total = 0
    excluded = 0

    with args.golden.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            row = json.loads(line)
            case_id = row.get("scenario_id") or row.get("case_id") or "<unknown>"
            if row.get("reconciliation", {}).get("excluded") or row.get("is_eval_golden") is False:
                excluded += 1
                continue
            flags = row.get("expected_safety_flags") or []
            for flag in flags:
                code_use[flag] += 1
                if flag not in known:
                    bad_cases.append((case_id, flag, row.get("agent_type", "?")))

            verdict = row.get("expected_compliance_verdict")
            tier1_flags = [f for f in flags if f in taxonomy.tier_1]
            if tier1_flags:
                if isinstance(verdict, str):
                    if verdict != "reject":
                        verdict_flag_violations.append((case_id, tier1_flags[0], "verdict_not_reject", verdict))
                elif isinstance(verdict, list):
                    if not row.get("verdict_set_rationale"):
                        verdict_flag_violations.append(
                            (case_id, tier1_flags[0], "set_valued_without_rationale", verdict)
                        )

    print(f"lint_golden_against_taxonomy: {total} cases scanned in {args.golden}")
    print(f"  taxonomy snapshot: {snapshot}")
    print(f"  excluded (not scored): {excluded}")
    print(f"  scored: {total - excluded}")
    print(f"  unique codes seen: {len(code_use)}")
    print()
    print("code usage:")
    for code, n in sorted(code_use.items(), key=lambda kv: (-kv[1], kv[0])):
        status = "OK" if code in known else "UNKNOWN"
        tier = taxonomy.tier_of(code) or "-"
        print(f"  [{status:7}] {tier:7} {code:40} x{n}")

    failed = False

    if bad_cases:
        print()
        print(f"FAIL (D1): {len(bad_cases)} case-flag pairs reference codes not in taxonomy snapshot:")
        for case_id, flag, agent in bad_cases:
            print(f"  - {case_id} ({agent}): {flag!r}")
        print()
        print("Resolution (per EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md §1.2):")
        print("  1. Fix taxonomy: add the code to the right tier in compliance_council.py")
        print("     and re-snapshot via scripts/snapshot_taxonomy.py.")
        print("  2. Relabel: change the case's expected_safety_flags to a code the system can emit.")
        print("  3. Exclude: drop the case from the scored set and record why.")
        failed = True

    if verdict_flag_violations:
        print()
        print(f"FAIL (D8): {len(verdict_flag_violations)} verdict-flag-inconsistent case(s):")
        for case_id, flag, kind, verdict in verdict_flag_violations:
            if kind == "verdict_not_reject":
                print(f"  - {case_id}: Tier-1 flag {flag!r} but expected_compliance_verdict={verdict!r}")
                print("      (Tier-1 routes to reject on any single grounded firing)")
            else:
                print(f"  - {case_id}: set-valued verdict {verdict!r} without verdict_set_rationale")
        print()
        print("Resolution: rewrite the verdict, rewrite the flag, or set-value with rationale (§1.4).")
        failed = True

    if failed:
        return 1

    print()
    print("OK: every expected_safety_flags code resolves to the snapshotted taxonomy,")
    print("    and every Tier-1 flag is paired with a reject verdict or rationalized set-value.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
