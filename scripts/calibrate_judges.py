"""Per-judge accuracy calibration from one or more NDJSON run files.

For each judge that appears in `per_judge` across the run rows, compute:

- accuracy:  fraction of (case,run) tuples where the judge's verdict
             matches the expected verdict at the same vote-space
             granularity. We compare vote -> expected via
             {BLOCK/reject, WARN/needs_review, PASS/approve} normalization.
- per-class precision/recall:
             treating reject as positive, computes how often the judge
             flags reject when the case is genuinely defective vs how
             often it flags clean cases as reject (FP).
- flag attachment rate:
             of cases where the judge votes reject AND the expected_flag
             matches an injected defect, what fraction of the expected
             flags appear in the judge's reported findings.

The output is the empirical anchor for TunedMockBackend's
per_member_semantic_accuracy parameter — the simulation's calibration
to live behavior.

Usage:
    python scripts/calibrate_judges.py \\
        --runs out/scribe_v1.live.v3.ndjson out/scheduling_v1.live.ndjson \\
               out/coding_v1.live.ndjson out/triage_v1.live.ndjson \\
        --packs out/scribe_v1.live.jsonl out/scheduling_v1.live.jsonl \\
                out/coding_v1.live.jsonl out/triage_v1.live.jsonl \\
        --out out/judge_calibration.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_VOTE_TO_COMPLIANCE = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}


def _matches(judge_vote: str, expected_compliance) -> bool:
    judge_compliance = _VOTE_TO_COMPLIANCE.get(judge_vote, "approve")
    if isinstance(expected_compliance, list):
        return judge_compliance in expected_compliance
    return judge_compliance == expected_compliance


def _is_defective(expected_compliance) -> bool:
    if isinstance(expected_compliance, list):
        return "reject" in expected_compliance
    return expected_compliance == "reject"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, type=Path,
                    help="NDJSON files emitted by run_determinism.py")
    ap.add_argument("--packs", nargs="+", required=True, type=Path,
                    help="Pack JSONL files (one per --runs, same order)")
    ap.add_argument("--out", type=Path, default=Path("out/judge_calibration.json"))
    ap.add_argument("--md-out", type=Path, default=Path("out/judge_calibration.md"))
    args = ap.parse_args()

    if len(args.runs) != len(args.packs):
        sys.exit(f"--runs and --packs must have the same length; got {len(args.runs)} vs {len(args.packs)}")

    # Aggregate: judge -> list of (judge_vote, expected_compliance, expected_flags, judge_findings)
    judge_obs: dict[str, list[dict]] = defaultdict(list)
    pack_summaries: list[dict] = []
    total_runs = 0

    for run_path, pack_path in zip(args.runs, args.packs):
        pack = {row["case_id"]: row for row in
                (json.loads(l) for l in pack_path.read_text().splitlines() if l.strip())}
        rows = [json.loads(l) for l in run_path.read_text().splitlines() if l.strip()]
        pack_name = rows[0].get("pack", "?") if rows else "?"
        pack_summaries.append({"pack": pack_name, "runs": len(rows), "cases": len(pack)})
        total_runs += len(rows)

        for r in rows:
            case = pack.get(r["case_id"])
            if case is None:
                continue
            expected = case.get("expected_compliance_verdict")
            expected_flags = set(case.get("expected_safety_flags") or [])
            per_judge = r.get("per_judge") or {}
            for judge_name, judge_payload in per_judge.items():
                judge_vote_raw = judge_payload.get("verdict")
                # We persisted verdict as the lifted form (reject/needs_review/approve);
                # convert back to vote space for canonical accuracy measurement.
                vote = {"reject": "BLOCK", "needs_review": "WARN", "approve": "PASS"}.get(
                    judge_vote_raw, "PASS"
                )
                judge_obs[judge_name].append({
                    "vote": vote,
                    "expected": expected,
                    "expected_flags": expected_flags,
                    "judge_findings": set(judge_payload.get("flags") or []),
                })

    # Per-judge metrics
    judge_metrics: dict[str, dict] = {}
    for judge_name, obs in judge_obs.items():
        n = len(obs)
        n_correct = sum(1 for o in obs if _matches(o["vote"], o["expected"]))
        defective = [o for o in obs if _is_defective(o["expected"])]
        clean = [o for o in obs if not _is_defective(o["expected"])]
        tp = sum(1 for o in defective if o["vote"] == "BLOCK")
        fn = sum(1 for o in defective if o["vote"] != "BLOCK")
        fp = sum(1 for o in clean if o["vote"] == "BLOCK")
        tn = sum(1 for o in clean if o["vote"] != "BLOCK")
        flag_attach_rates: list[float] = []
        for o in defective:
            if o["vote"] != "BLOCK" or not o["expected_flags"]:
                continue
            attached = len(o["expected_flags"] & o["judge_findings"]) / len(o["expected_flags"])
            flag_attach_rates.append(attached)
        judge_metrics[judge_name] = {
            "n": n,
            "accuracy": round(n_correct / n, 4) if n else 0,
            "recall_reject": round(tp / len(defective), 4) if defective else None,
            "precision_reject": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "false_block_rate": round(fp / len(clean), 4) if clean else None,
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "flag_attachment_rate_mean": round(statistics.fmean(flag_attach_rates), 4) if flag_attach_rates else None,
            "flag_attachment_n": len(flag_attach_rates),
        }

    # Ensemble accuracy (majority vote across all judges in each row, against expected)
    by_row: dict[tuple[str, int], list[str]] = defaultdict(list)
    expected_by_row: dict[tuple[str, int], object] = {}
    for run_path, pack_path in zip(args.runs, args.packs):
        pack = {row["case_id"]: row for row in
                (json.loads(l) for l in pack_path.read_text().splitlines() if l.strip())}
        for r in (json.loads(l) for l in run_path.read_text().splitlines() if l.strip()):
            key = (r["case_id"], r.get("run_index", 0))
            for judge_payload in (r.get("per_judge") or {}).values():
                vote = {"reject": "BLOCK", "needs_review": "WARN", "approve": "PASS"}.get(
                    judge_payload.get("verdict"), "PASS"
                )
                by_row[key].append(vote)
            case = pack.get(r["case_id"])
            if case is not None:
                expected_by_row[key] = case.get("expected_compliance_verdict")

    ensemble_correct = 0
    ensemble_total = 0
    for key, votes in by_row.items():
        if not votes:
            continue
        ensemble_total += 1
        counts = {v: votes.count(v) for v in set(votes)}
        modal_vote = max(counts, key=counts.get)
        if _matches(modal_vote, expected_by_row[key]):
            ensemble_correct += 1

    pack_summary = {
        "packs": pack_summaries,
        "total_runs": total_runs,
        "ensemble_accuracy_majority_vote": round(ensemble_correct / ensemble_total, 4) if ensemble_total else None,
        "ensemble_size_observed": (
            statistics.fmean(len(v) for v in by_row.values()) if by_row else None
        ),
        "judges": judge_metrics,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack_summary, indent=2, default=str))

    md = [
        "# Judge calibration (live council, gpt-4.1)",
        "",
        f"- packs scanned: {len(args.packs)}",
        f"- total rows: {total_runs}",
        f"- ensemble accuracy (majority vote): "
        f"**{pack_summary['ensemble_accuracy_majority_vote']}**",
        f"- mean ensemble size observed: {pack_summary['ensemble_size_observed']:.2f}"
        if pack_summary["ensemble_size_observed"] is not None
        else "- mean ensemble size: n/a",
        "",
        "## Per-judge",
        "",
        "| judge | n | accuracy | recall (reject) | precision (reject) | false_block_rate | flag_attach |",
        "|---|---|---|---|---|---|---|",
    ]
    for j, m in sorted(judge_metrics.items()):
        fa = m["flag_attachment_rate_mean"]
        md.append(
            f"| `{j}` | {m['n']} | {m['accuracy']:.3f} | "
            f"{m['recall_reject'] if m['recall_reject'] is not None else '—'} | "
            f"{m['precision_reject'] if m['precision_reject'] is not None else '—'} | "
            f"{m['false_block_rate'] if m['false_block_rate'] is not None else '—'} | "
            f"{fa if fa is not None else '—'} |"
        )
    md.append("")
    md.append("## TunedMockBackend calibration")
    md.append("")
    if judge_metrics:
        per_member = statistics.fmean(m["accuracy"] for m in judge_metrics.values())
        per_flag = statistics.fmean(
            m["flag_attachment_rate_mean"]
            for m in judge_metrics.values()
            if m["flag_attachment_rate_mean"] is not None
        ) if any(m["flag_attachment_rate_mean"] is not None for m in judge_metrics.values()) else None
        md.append(f"- mean per-member accuracy across judges: **{per_member:.3f}**")
        md.append(f"- mean per-member flag attachment rate: "
                  f"**{per_flag:.3f}**" if per_flag is not None else "- mean per-member flag attachment rate: n/a")
        md.append("")
        md.append("Suggested TunedMockBackend invocation:")
        md.append("")
        md.append("```")
        md.append(
            f"TunedMockBackend(ensemble_size=3, "
            f"per_member_semantic_accuracy={per_member:.3f}, "
            + (f"per_member_flag_attachment_rate={per_flag:.3f})" if per_flag is not None else "per_member_flag_attachment_rate=...)")
        )
        md.append("```")

    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text("\n".join(md) + "\n")

    print(json.dumps(pack_summary, indent=2, default=str))
    print(f"\nwrote {args.out}")
    print(f"wrote {args.md_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
