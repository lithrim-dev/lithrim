"""Read an NDJSON output from run_determinism.py and print/emit metrics.

Per-case and pack-level metrics per eval spec §2.3. Adds a Markdown
summary with the layer-1 + layer-2 decomposition + bootstrap CI on
verdict_match_rate.

Usage:
    python scripts/analyze_runs.py --runs out/scribe_v1.runs.ndjson
    python scripts/analyze_runs.py --runs out/scribe_v1.runs.ndjson \
        --pack out/scribe_v1.jsonl   # adds false_block_rate
    python scripts/analyze_runs.py --runs out/scribe_v1.runs.ndjson \
        --pack out/scribe_v1.jsonl --split test   # paper-reportable subset
    python scripts/analyze_runs.py --runs a.runs.ndjson b.runs.ndjson
        # comparison mode; refuses mismatched §1.6 pins unless --allow-cross-pin
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.analysis import (
    CrossPinError,
    analyze_pack,
    analyze_per_case,
    compare_runs,
    distinct_pins,
    read_runs,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, type=Path, nargs="+")
    ap.add_argument("--pack", type=Path, default=None)
    ap.add_argument("--split", choices=["calibration", "test", "all"], default="all",
                    help="restrict analysis to one split (requires --pack); "
                         "paper §7 numbers use --split test")
    ap.add_argument("--allow-cross-pin", action="store_true",
                    help="compare runs with mismatched §1.6 pinned tuples anyway; "
                         "the output is labeled cross_pin=true")
    ap.add_argument("--out-json", type=Path, default=None)
    ap.add_argument("--out-md", type=Path, default=None)
    args = ap.parse_args()

    for runs_path in args.runs:
        if not runs_path.exists():
            sys.exit(f"runs file not found: {runs_path}")

    pack_rows = None
    if args.pack is not None and args.pack.exists():
        pack_rows = [json.loads(line) for line in args.pack.read_text().splitlines() if line.strip()]

    rows_by_file = {str(p): read_runs(p) for p in args.runs}

    if args.split != "all":
        if pack_rows is None:
            sys.exit("--split requires --pack (the split label lives in the pack rows)")
        keep = {r["case_id"] for r in pack_rows if r.get("split") == args.split}
        if not keep:
            sys.exit(f"no cases with split={args.split!r} in {args.pack} "
                     "(regenerate the pack — pre-split packs have no split field)")
        rows_by_file = {
            label: [r for r in rows if r["case_id"] in keep]
            for label, rows in rows_by_file.items()
        }
        pack_rows = [r for r in pack_rows if r["case_id"] in keep]

    if len(args.runs) > 1:
        try:
            comparison = compare_runs(
                rows_by_file, allow_cross_pin=args.allow_cross_pin, pack_rows=pack_rows,
            )
        except CrossPinError as e:
            sys.exit(str(e))
        out_json = args.out_json or args.runs[0].with_suffix(".comparison.json")
        out_json.write_text(json.dumps(comparison, indent=2))
        print(json.dumps({k: comparison[k] for k in ("cross_pin", "pins")}, indent=2))
        for label, entry in comparison["runs"].items():
            print(f"\n## {label}")
            print(json.dumps(entry["pack_summary"], indent=2))
        print(f"\nwrote {out_json}")
        return 0

    rows = rows_by_file[str(args.runs[0])]
    pins = distinct_pins(rows)
    if len(pins) > 1 and not args.allow_cross_pin:
        sys.exit(str(CrossPinError(pins)))

    per_case = analyze_per_case(rows)
    pack_summary = analyze_pack(per_case, pack_rows=pack_rows)

    out_json = args.out_json or args.runs[0].with_suffix(".analysis.json")
    out_md = args.out_md or args.runs[0].with_suffix(".analysis.md")

    payload = {
        "pack_summary": pack_summary,
        "per_case": per_case,
        "cross_pin": len(pins) > 1,
        "pins": pins,
    }
    out_json.write_text(json.dumps(payload, indent=2))

    md = ["# Determinism analysis", "", f"- runs file: `{args.runs[0]}`",
          f"- split: `{args.split}`", f"- rows: {len(rows)}", ""]
    if len(pins) > 1:
        md.append("**CROSS-PIN**: this file mixes multiple pinned tuples; "
                  "metrics aggregate across pins.")
        md.append("")
    md.append("## Pack summary")
    for k, v in pack_summary.items():
        md.append(f"- **{k}**: `{v}`")
    md.append("")
    md.append("## Per-case (top 20 by instability)")
    md.append("")
    md.append("| case_id | n | modal | instability | match_rate | flag_attachment | κ | structural |")
    md.append("|---|---|---|---|---|---|---|---|")
    sorted_cases = sorted(per_case, key=lambda c: -c["verdict_instability"])
    for c in sorted_cases[:20]:
        attach = ", ".join(f"{k}={v:.2f}" for k, v in c["flag_attachment_rate"].items()) or "(none)"
        kappa = f"{c['decision_layer_kappa']:.3f}" if c["decision_layer_kappa"] is not None else "—"
        s = c.get("structural") or {}
        s_str = (
            f"exp={s.get('expected')} match={s.get('match_rate')}"
            if s.get("expected") is not None
            else "—"
        )
        md.append(
            f"| `{c['case_id']}` | {c['n']} | {c['modal_verdict']} | "
            f"{c['verdict_instability']:.2f} | {c['verdict_match_rate']:.2f} | "
            f"{attach} | {kappa} | {s_str} |"
        )
    out_md.write_text("\n".join(md) + "\n")

    print(json.dumps(pack_summary, indent=2))
    print(f"\nwrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
