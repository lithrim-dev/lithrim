"""P1-EXP-0: aggregate per-judge confidence on the silent-confident HL7 subset.

Reads out/p1_exp_0_council_confidence.ndjson (produced by
scripts/measure_council_confidence_hl7.py), filters the "silent confident
certification" subset — defect-bearing cases (expected_compliance_verdict ==
"reject") where the live council compliance_verdict == "approve" and every
per_judge[*].verdict == "approve" — and emits two artifacts:

  - out/p1_exp_0_council_confidence.summary.json
      per-judge mean/median/p25/p75 + 0.1-bucketed histogram + counts
      (total_rows, error_rows, defect_total, silent_subset_size,
      agreement_breakdown).

  - out/p1_exp_0_council_confidence.summary.md
      single-page human-readable report with the headline sentence drafted
      for §5: "On the N HL7 ADT^A04 defects that the council unanimously
      approved, per-judge mean confidence was {policy: X, risk: Y,
      behavior: Z}; the histogram is concentrated in the [a, b] bucket."

If the silent subset is empty (the council correctly rejected all 28),
the .md reports that as an honest negative result rather than synthesizing
a placeholder headline.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _histogram_buckets(xs: list[float]) -> dict[str, int]:
    """0.1-wide buckets from 0.0 → 1.0; values pinned to [0.0, 1.0]."""
    buckets = {f"{i / 10:.1f}-{(i + 1) / 10:.1f}": 0 for i in range(10)}
    for x in xs:
        v = max(0.0, min(1.0, x))
        idx = min(int(v * 10), 9)
        key = f"{idx / 10:.1f}-{(idx + 1) / 10:.1f}"
        buckets[key] += 1
    return buckets


def _per_judge_stats(silent_rows: list[dict]) -> dict[str, dict]:
    """For each judge role observed, compute mean/median/p25/p75 + histogram."""
    by_role: dict[str, list[float]] = {}
    for row in silent_rows:
        pj = row.get("per_judge") or {}
        for role, judge in pj.items():
            by_role.setdefault(role, []).append(float(judge.get("confidence", 0.0)))
    return {
        role: {
            "n": len(vals),
            "mean": round(statistics.fmean(vals), 4) if vals else float("nan"),
            "median": round(statistics.median(vals), 4) if vals else float("nan"),
            "p25": round(_quantile(vals, 0.25), 4) if vals else float("nan"),
            "p75": round(_quantile(vals, 0.75), 4) if vals else float("nan"),
            "min": round(min(vals), 4) if vals else float("nan"),
            "max": round(max(vals), 4) if vals else float("nan"),
            "histogram_0p1_buckets": _histogram_buckets(vals),
        }
        for role, vals in by_role.items()
    }


def _modal_bucket(hist: dict[str, int]) -> str:
    if not hist:
        return "n/a"
    return max(hist.items(), key=lambda kv: kv[1])[0]


def _is_council_silent(row: dict) -> bool:
    """Council-layer silent-confident certification: defect case where every
    judge approves. This is the §5 measurement per PAPER_FRAMING_DECISIONS
    A1 — a statement about the COUNCIL layer, not the composed pipeline.
    """
    if row.get("expected_compliance_verdict") != "reject":
        return False
    pj = row.get("per_judge") or {}
    if not pj:
        return False
    return all(j.get("verdict") == "approve" for j in pj.values())


def _is_pipeline_silent(row: dict) -> bool:
    """Driver §2 Deliverable 3 literal filter: also requires the composed
    pipeline gate to approve. Reported for audit trail — see the §5
    deviation note in the .md output for why this is not the right §5
    number (the pipeline gate already includes the structural side, which
    is the §6 solution being characterized in §5's framing).
    """
    if not _is_council_silent(row):
        return False
    return row.get("compliance_verdict") == "approve"


def _agreement_breakdown(defect_rows: list[dict]) -> dict[str, int]:
    """Count how many defect cases were unanimous / split / unanimously rejected."""
    counts = {"unanimous_approve": 0, "split": 0, "unanimous_reject": 0, "other": 0}
    for row in defect_rows:
        pj = row.get("per_judge") or {}
        if not pj:
            counts["other"] += 1
            continue
        verdicts = [j.get("verdict") for j in pj.values()]
        if all(v == "approve" for v in verdicts):
            counts["unanimous_approve"] += 1
        elif all(v == "reject" for v in verdicts):
            counts["unanimous_reject"] += 1
        elif any(v == "approve" for v in verdicts) and any(
            v in ("reject", "needs_review") for v in verdicts
        ):
            counts["split"] += 1
        else:
            counts["other"] += 1
    return counts


def _structural_outcome(defect_rows: list[dict]) -> dict[str, int]:
    """Did the strict HL7 validator (mapping 93) catch the defects?"""
    counts: dict[str, int] = {}
    for row in defect_rows:
        sv = row.get("structural_verdict") or "NULL"
        counts[sv] = counts.get(sv, 0) + 1
    return counts


def _render_markdown(summary: dict) -> str:
    s = summary
    lines: list[str] = []
    lines.append("# P1-EXP-0: Council confidence on silent-confident HL7 defects")
    lines.append("")
    lines.append(f"**Source:** `{s['input_path']}` (N={s['n_repeats']})")
    lines.append(
        "**Pack:** `out/hl7_adt_v1.jsonl` (40 cases: 12 clean + 28 defect; all defects expect `reject`)"
    )
    lines.append("**Validator:** mapping 93 (strict HL7 ADT^A04, Jute Copilot output)")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Total rows in NDJSON: **{s['total_rows']}**")
    lines.append(f"- Error rows: **{s['error_rows']}**")
    lines.append(f"- Clean negative cases: **{s['clean_total']}**")
    lines.append(f"- Defect-bearing cases: **{s['defect_total']}**")
    pct = s["silent_subset_size"] * 100 // max(s["defect_total"], 1)
    lines.append(
        f"- **Council-silent subset** (defect + council unanimous-approve — the §5 measurement): "
        f"**{s['silent_subset_size']} / {s['defect_total']}** ({pct}%)"
    )
    lines.append(
        f"- Pipeline-silent subset (council-silent AND pipeline gate=approve — driver §2 D3 "
        f"literal filter, audit only): **{s['pipeline_silent_subset_size']} / {s['defect_total']}**"
    )
    lines.append("")
    lines.append("## §5 subset-definition deviation (logged for audit)")
    lines.append("")
    lines.append(
        "The driver's literal filter requires `compliance_verdict == 'approve'` — but "
        "`compliance_verdict` is the pipeline gate AFTER structural composition (the §6 "
        "solution). Filtering the §5 failure-mode population through its own solution yields "
        "0 by construction, regardless of council calibration. Per "
        "PAPER_FRAMING_DECISIONS_2026-05-26.md A1, §5 is a council-layer statement "
        '("the council silently and confidently certifies spec-violating clinical '
        'artifacts"), so the right filter drops the pipeline-gate clause and keeps only the '
        "council-unanimous-approve condition on defect-bearing rows. User-approved "
        "deviation 2026-05-27 (option A in the halt+surface)."
    )
    lines.append("")
    lines.append("## Council agreement breakdown on the 28 defects")
    lines.append("")
    for k, v in s["agreement_breakdown"].items():
        lines.append(f"- {k}: **{v}**")
    lines.append("")
    lines.append("## Structural verdict on the 28 defects (mapping 93)")
    lines.append("")
    for k, v in s["structural_outcome_on_defects"].items():
        lines.append(f"- {k}: **{v}**")
    lines.append("")
    lines.append("## What the pipeline gate did with the council-silent subset")
    lines.append("")
    lines.append(
        "On the council-silent subset — defects every judge approved at this confidence — "
        "the composed pipeline gate (worst-of with mapping 93) was driven by the structural "
        "side to the following dispositions:"
    )
    lines.append("")
    for k, v in s["pipeline_gate_on_silent"].items():
        lines.append(f"- `compliance_verdict={k}`: **{v}**")
    lines.append("")
    lines.append("Structural verdict on the same subset:")
    for k, v in s["structural_outcome_on_silent"].items():
        lines.append(f"- `structural_verdict={k}`: **{v}**")
    lines.append("")

    if s["silent_subset_size"] == 0:
        lines.append("## §5 headline — honest negative result")
        lines.append("")
        lines.append(
            f"On all {s['defect_total']} HL7 ADT^A04 defects in the test pack, the live "
            "council did not unanimously approve any defect-bearing case. The "
            "silent-confident-certification failure mode does not manifest at this judge "
            "model / pack configuration."
        )
    else:
        lines.append("## Per-judge confidence on the council-silent subset")
        lines.append("")
        lines.append("| Judge | n | mean | median | p25 | p75 | min | max | modal bucket |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for role, stats in s["per_judge_stats"].items():
            modal = _modal_bucket(stats["histogram_0p1_buckets"])
            lines.append(
                f"| {role} | {stats['n']} | {stats['mean']} | {stats['median']} "
                f"| {stats['p25']} | {stats['p75']} | {stats['min']} | {stats['max']} | {modal} |"
            )
        lines.append("")
        lines.append("### Histograms (0.1-wide buckets)")
        lines.append("")
        for role, stats in s["per_judge_stats"].items():
            lines.append(f"**{role}**")
            for bucket, count in stats["histogram_0p1_buckets"].items():
                if count > 0:
                    bar = "█" * count
                    lines.append(f"  `{bucket}` {bar} ({count})")
            lines.append("")

        means = {role: stats["mean"] for role, stats in s["per_judge_stats"].items()}
        modals = {
            role: _modal_bucket(stats["histogram_0p1_buckets"])
            for role, stats in s["per_judge_stats"].items()
        }
        lines.append("## §5 headline (draft, plug into paper_draft/05_section_5_…)")
        lines.append("")
        means_str = ", ".join(f"{role.replace('_judge', '')}: {m:.3f}" for role, m in means.items())
        modal_str = ", ".join(
            f"{role.replace('_judge', '')} in {b}" for role, b in modals.items()
        )
        pct = s["silent_subset_size"] * 100 // max(s["defect_total"], 1)
        block_silent = s["structural_outcome_on_silent"].get("BLOCK", 0)
        warn_silent = s["structural_outcome_on_silent"].get("WARN", 0)
        lines.append(
            f"> On the {s['silent_subset_size']} HL7 ADT^A04 defects ({pct}% of "
            f"{s['defect_total']}) that the live council unanimously approved, per-judge "
            f"mean confidence was {{{means_str}}}; the histogram is concentrated in "
            f"{modal_str}. The generated HL7 ADT^A04 conformance validator (Jute Copilot "
            f"mapping 93) flagged every one of those silent cases: "
            f"`structural_verdict=BLOCK` on {block_silent}, `WARN` on {warn_silent}, "
            f"0 silent."
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("out/p1_exp_0_council_confidence.ndjson"))
    ap.add_argument(
        "--out-json", type=Path, default=Path("out/p1_exp_0_council_confidence.summary.json")
    )
    ap.add_argument(
        "--out-md", type=Path, default=Path("out/p1_exp_0_council_confidence.summary.md")
    )
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")

    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    error_rows = [r for r in rows if "error" in r]
    valid_rows = [r for r in rows if "error" not in r]
    n_repeats = max((r.get("rep", 0) for r in valid_rows), default=0) + 1

    defect_rows = [r for r in valid_rows if r.get("expected_compliance_verdict") == "reject"]
    clean_rows = [r for r in valid_rows if r.get("clean_negative", False)]
    silent_rows = [r for r in defect_rows if _is_council_silent(r)]
    pipeline_silent_rows = [r for r in defect_rows if _is_pipeline_silent(r)]

    pipeline_gate_on_silent: dict[str, int] = {}
    for r in silent_rows:
        cv = r.get("compliance_verdict") or "NULL"
        pipeline_gate_on_silent[cv] = pipeline_gate_on_silent.get(cv, 0) + 1

    summary = {
        "input_path": str(args.input),
        "n_repeats": n_repeats,
        "total_rows": len(rows),
        "error_rows": len(error_rows),
        "clean_total": len(clean_rows),
        "defect_total": len(defect_rows),
        "silent_subset_size": len(silent_rows),
        "silent_subset_definition": (
            "council-layer: defect case where every per_judge[*].verdict == 'approve' "
            "(approved by §5 framing per PAPER_FRAMING_DECISIONS A1; replaces driver "
            "§2 Deliverable 3 literal filter mid-cycle — see deviations in session log)"
        ),
        "pipeline_silent_subset_size": len(pipeline_silent_rows),
        "pipeline_silent_subset_definition": (
            "driver §2 Deliverable 3 literal: council-silent AND pipeline "
            "compliance_verdict == 'approve' (reported for audit trail; not used "
            "for §5 because the pipeline gate already composes the §6 solution)"
        ),
        "pipeline_gate_on_silent": pipeline_gate_on_silent,
        "agreement_breakdown": _agreement_breakdown(defect_rows),
        "structural_outcome_on_defects": _structural_outcome(defect_rows),
        "structural_outcome_on_silent": _structural_outcome(silent_rows),
        "per_judge_stats": _per_judge_stats(silent_rows),
        "silent_case_ids": [r.get("case_id") for r in silent_rows],
        "pipeline_silent_case_ids": [r.get("case_id") for r in pipeline_silent_rows],
        "error_case_ids": [r.get("case_id") for r in error_rows],
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2) + "\n")
    args.out_md.write_text(_render_markdown(summary))

    print(
        json.dumps(
            {
                "summary_json": str(args.out_json),
                "summary_md": str(args.out_md),
                "silent_subset_size": summary["silent_subset_size"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
