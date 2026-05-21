"""Read an NDJSON output from run_determinism.py and print/emit metrics.

Per-case and pack-level metrics per eval spec §2.3. Adds a Markdown
summary with the layer-1 + layer-2 decomposition + bootstrap CI on
verdict_match_rate.

Usage:
    python scripts/analyze_runs.py --runs out/scribe_v1.runs.ndjson
    python scripts/analyze_runs.py --runs out/scribe_v1.runs.ndjson \
        --pack out/scribe_v1.jsonl   # adds false_block_rate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.analysis import analyze_pack, analyze_per_case, read_runs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, type=Path)
    ap.add_argument("--pack", type=Path, default=None)
    ap.add_argument("--out-json", type=Path, default=None)
    ap.add_argument("--out-md", type=Path, default=None)
    args = ap.parse_args()

    if not args.runs.exists():
        sys.exit(f"runs file not found: {args.runs}")

    rows = read_runs(args.runs)
    pack_rows = None
    if args.pack is not None and args.pack.exists():
        pack_rows = [json.loads(line) for line in args.pack.read_text().splitlines() if line.strip()]

    per_case = analyze_per_case(rows)
    pack_summary = analyze_pack(per_case, pack_rows=pack_rows)

    out_json = args.out_json or args.runs.with_suffix(".analysis.json")
    out_md = args.out_md or args.runs.with_suffix(".analysis.md")

    payload = {"pack_summary": pack_summary, "per_case": per_case}
    out_json.write_text(json.dumps(payload, indent=2))

    md = ["# Determinism analysis", "", f"- runs file: `{args.runs}`",
          f"- rows: {len(rows)}", ""]
    md.append("## Pack summary")
    for k, v in pack_summary.items():
        md.append(f"- **{k}**: `{v}`")
    md.append("")
    md.append("## Per-case (top 20 by instability)")
    md.append("")
    md.append("| case_id | n | modal | instability | match_rate | flag_attachment | κ |")
    md.append("|---|---|---|---|---|---|---|")
    sorted_cases = sorted(per_case, key=lambda c: -c["verdict_instability"])
    for c in sorted_cases[:20]:
        attach = ", ".join(f"{k}={v:.2f}" for k, v in c["flag_attachment_rate"].items()) or "(none)"
        kappa = f"{c['decision_layer_kappa']:.3f}" if c["decision_layer_kappa"] is not None else "—"
        md.append(
            f"| `{c['case_id']}` | {c['n']} | {c['modal_verdict']} | "
            f"{c['verdict_instability']:.2f} | {c['verdict_match_rate']:.2f} | "
            f"{attach} | {kappa} |"
        )
    out_md.write_text("\n".join(md) + "\n")

    print(json.dumps(pack_summary, indent=2))
    print(f"\nwrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
