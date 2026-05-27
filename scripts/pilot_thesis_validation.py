"""Pilot — N=12 thesis-validation sweep across 5 packs from bench fixtures.

Loads /tmp/pilot_picklist.json (12 curated picks across scribe / scheduling /
coding / triage / hl7), hydrates each case from the bench's out/*.n10.jsonl
fixtures (NOT the registered UI eval-pack cases — those have stub transcripts;
see audit transcript-length finding), runs each through LithrimPipelineBackend
with pack-appropriate agent_id + validator_id, and writes a full-fidelity
NDJSON + derived-metrics summary.

Validates the per-case data-point checklist:
    - per_judge populated (3 judges with verdict + flags + confidence)
    - findings_rich populated on defect cases (preserves API Finding shape:
      type, severity, detail, field, check_name, code, chunk_id, start_ms,
      end_ms, speaker)
    - structural_findings_rich populated on HL7 cases
    - raw.{pipeline_run_id, gate_decision, duration_ms} carried through
    - expected_* vs actual map (verdict_match, flags_caught/missed)
    - silent_confident (council-layer): unanimous_approve AND defect

Output:
    out/pilot_thesis_n12.ndjson         per-row NDJSON
    out/pilot_thesis_n12.summary.json   aggregate metrics
    out/pilot_thesis_n12.summary.md     human-readable summary

Cost: ~12 cases × 3 judges × ~$0.04 ≈ $1.50. Wall-clock ~4 min.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.backends import LithrimPipelineBackend


# Pack → fixture file + agent_id + validator_id binding.
# agent_id sourced from /agents GET earlier (org 69b82f072c01d1cc481da187).
# validator_id=93 for HL7 (strict ADT^A04 from Jute Copilot, P1-EXP-0).
PACK_BINDING: dict[str, dict] = {
    "scribe_v1":     {"fixture": "out/scribe_v1.n10.jsonl",     "agent_id": "69e8eed80774d8129275bb4a", "validator_id": None},
    "scheduling_v1": {"fixture": "out/scheduling_v1.n10.jsonl", "agent_id": "69e8eed80774d8129275bb47", "validator_id": None},
    "coding_v1":     {"fixture": "out/coding_v1.n10.jsonl",     "agent_id": "69e8eed80774d8129275bb46", "validator_id": None},
    "triage_v1":     {"fixture": "out/triage_v1.n10.jsonl",     "agent_id": "69e8eed80774d8129275bb48", "validator_id": None},
    "hl7_adt_v1":    {"fixture": "out/hl7_adt_v1.jsonl",        "agent_id": None,                       "validator_id": "93"},
}


def _read_live_env(repo_root: Path) -> dict[str, str]:
    env_path = repo_root / ".live_env"
    if not env_path.exists():
        return {}
    return dict(line.split("=", 1) for line in env_path.read_text().splitlines() if "=" in line)


def _live_creds(args: argparse.Namespace, repo_root: Path) -> tuple[str, str]:
    live = _read_live_env(repo_root)
    key = args.api_key or os.environ.get("LITHRIM_API_KEY") or live.get("LITHRIM_API_KEY")
    org = args.org_id or os.environ.get("LITHRIM_ORG_ID") or live.get("LITHRIM_ORG_ID")
    if not key or not org:
        sys.exit("--api-key/--org-id required (or set LITHRIM_API_KEY/LITHRIM_ORG_ID, or .live_env)")
    return key, org


def _load_picklist(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def _hydrate_case(pick: dict, repo_root: Path) -> dict | None:
    """Find the full case JSON in the pack's bench fixture by case_id."""
    binding = PACK_BINDING.get(pick["pack"])
    if not binding:
        return None
    fixture_path = repo_root / binding["fixture"]
    target_id = pick["case_id"]
    with fixture_path.open() as fp:
        for line in fp:
            row = json.loads(line)
            if row.get("case_id") == target_id:
                return row
    return None


def _verdict_to_row(pick: dict, case: dict, verdict, elapsed_s: float) -> dict:
    per_judge_dict = None
    if verdict.per_judge is not None:
        per_judge_dict = {role: dataclasses.asdict(jo) for role, jo in verdict.per_judge.items()}
    return {
        "pick_label": pick["pick_label"],
        "pick_kind": pick["kind"],
        "pick_why": pick.get("why"),
        "case_id": case["case_id"],
        "pack": case.get("pack"),
        "agent_type": case.get("agent_type"),
        "severity": case.get("severity"),
        "clean_negative": case.get("clean_negative", False),
        "multi_defect": case.get("multi_defect", False),
        "split": case.get("split"),
        "transcript_len": len(case.get("transcript", "") or ""),
        "artifact_types": [a.get("type") for a in (case.get("artifacts") or [])],
        # Ground-truth (deterministic-label, fixture-pinned)
        "expected_compliance_verdict": case.get("expected_compliance_verdict"),
        "expected_artifact_verdict": case.get("expected_artifact_verdict"),
        "expected_structural_verdict": case.get("expected_structural_verdict"),
        "expected_safety_flags": case.get("expected_safety_flags") or [],
        "injection_recipes": case.get("injection_recipes") or [],
        # Observed (live pipeline)
        "compliance_verdict": verdict.compliance_verdict,
        "artifact_verdict": verdict.artifact_verdict,
        "structural_verdict": verdict.structural_verdict,
        "flags": verdict.flags,
        "findings_rich": verdict.findings_rich,
        "structural_findings": verdict.structural_findings,
        "structural_findings_rich": verdict.structural_findings_rich,
        "per_judge": per_judge_dict,
        "raw": verdict.raw,
        "elapsed_s": round(elapsed_s, 2),
    }


def _is_match(observed: str, expected) -> bool:
    if expected is None:
        return False
    if isinstance(expected, str):
        return observed == expected
    if isinstance(expected, list):
        return observed in expected
    return False


def _enrich_with_derived(row: dict) -> dict:
    """Compute derived metrics + per-row data-point checklist."""
    pj = row.get("per_judge") or {}
    judges = list(pj.values())
    expected_flags = set(row.get("expected_safety_flags") or [])
    actual_flags = set(row.get("flags") or [])

    # Match metrics
    row["verdict_match"] = _is_match(row["compliance_verdict"], row["expected_compliance_verdict"])
    row["artifact_verdict_match"] = _is_match(row["artifact_verdict"], row["expected_artifact_verdict"])
    if row["expected_structural_verdict"]:
        row["structural_verdict_match"] = row["structural_verdict"] == row["expected_structural_verdict"]
    row["flags_caught"] = sorted(expected_flags & actual_flags)
    row["flags_missed"] = sorted(expected_flags - actual_flags)
    row["flags_extra"] = sorted(actual_flags - expected_flags)

    # Council-layer measurements
    row["n_judges"] = len(judges)
    row["unanimous_judge_approve"] = bool(judges) and all(j.get("verdict") == "approve" for j in judges)
    row["unanimous_judge_reject"] = bool(judges) and all(j.get("verdict") == "reject" for j in judges)
    row["judge_confidences"] = [j.get("confidence", 0.0) for j in judges]
    row["min_confidence"] = min(row["judge_confidences"]) if row["judge_confidences"] else None
    row["max_confidence"] = max(row["judge_confidences"]) if row["judge_confidences"] else None

    # Silent-confident-certification (council-layer per S-P1-6)
    row["silent_confident_council"] = (
        row["unanimous_judge_approve"]
        and not row.get("clean_negative", False)
    )
    # Pipeline-layer silent (council + gate both approve a defect)
    row["silent_confident_pipeline"] = (
        row["unanimous_judge_approve"]
        and row["compliance_verdict"] == "approve"
        and not row.get("clean_negative", False)
    )

    # Per-case data-point checklist
    checks = {}
    checks["has_per_judge_3"] = row["n_judges"] == 3
    checks["all_judges_have_confidence"] = bool(judges) and all(
        "confidence" in j and isinstance(j.get("confidence"), (int, float)) for j in judges
    )
    checks["any_nonzero_confidence"] = any(c > 0 for c in row["judge_confidences"])
    checks["has_pipeline_run_id"] = bool((row.get("raw") or {}).get("pipeline_run_id"))
    checks["has_gate_decision"] = bool((row.get("raw") or {}).get("gate_decision"))
    checks["has_duration_ms"] = (row.get("raw") or {}).get("duration_ms") is not None
    # findings_rich expected when defect AND verdict involved findings
    if not row.get("clean_negative") and (actual_flags or row["flags"]):
        checks["findings_rich_populated"] = bool(row.get("findings_rich"))
    if row["expected_structural_verdict"] in ("WARN", "BLOCK"):
        checks["structural_findings_rich_populated"] = bool(row.get("structural_findings_rich"))
    checks["injection_recipes_present"] = bool(row.get("injection_recipes")) if not row.get("clean_negative") else True
    row["data_checks"] = checks
    row["data_checks_all_pass"] = all(checks.values())
    return row


def _summarize(rows: list[dict]) -> dict:
    defects = [r for r in rows if not r.get("clean_negative")]
    cleans = [r for r in rows if r.get("clean_negative")]
    sc_council = [r for r in defects if r.get("silent_confident_council")]
    sc_pipeline = [r for r in defects if r.get("silent_confident_pipeline")]
    by_pack = {}
    for r in rows:
        p = r.get("pack", "?")
        by_pack.setdefault(p, []).append(r)
    pack_summary = {}
    for p, rs in by_pack.items():
        pack_summary[p] = {
            "n": len(rs),
            "verdict_match": sum(1 for r in rs if r.get("verdict_match")),
            "artifact_verdict_match": sum(1 for r in rs if r.get("artifact_verdict_match")),
            "silent_confident_council": sum(1 for r in rs if r.get("silent_confident_council")),
            "silent_confident_pipeline": sum(1 for r in rs if r.get("silent_confident_pipeline")),
        }
    all_confidences = [c for r in rows for c in (r.get("judge_confidences") or [])]
    return {
        "n_total": len(rows),
        "n_defects": len(defects),
        "n_cleans": len(cleans),
        "verdict_match_total": sum(1 for r in rows if r.get("verdict_match")),
        "artifact_verdict_match_total": sum(1 for r in rows if r.get("artifact_verdict_match")),
        "silent_confident_council_count": len(sc_council),
        "silent_confident_council_ratio_of_defects": (
            len(sc_council) / len(defects) if defects else None
        ),
        "silent_confident_pipeline_count": len(sc_pipeline),
        "unanimous_approve_on_defects": sum(1 for r in defects if r.get("unanimous_judge_approve")),
        "unanimous_reject_on_defects": sum(1 for r in defects if r.get("unanimous_judge_reject")),
        "mean_judge_confidence_all_rows": (
            round(sum(all_confidences) / len(all_confidences), 4) if all_confidences else None
        ),
        "all_confidences_at_1": all(c == 1.0 for c in all_confidences) if all_confidences else None,
        "data_checks_all_pass_count": sum(1 for r in rows if r.get("data_checks_all_pass")),
        "by_pack": pack_summary,
    }


def _to_markdown(rows: list[dict], summary: dict) -> str:
    lines = ["# Pilot — N=12 thesis-validation summary", "",
             f"_Generated {time.strftime('%Y-%m-%d %H:%M')}_ — {summary['n_total']} cases, "
             f"{summary['n_defects']} defects, {summary['n_cleans']} clean negatives."]
    lines += ["", "## Headline"]
    lines.append(f"- **Silent-confident (council-layer):** {summary['silent_confident_council_count']}/{summary['n_defects']} defects "
                 f"({(summary['silent_confident_council_ratio_of_defects'] or 0)*100:.1f}%)")
    lines.append(f"- **Silent-confident (pipeline-layer):** {summary['silent_confident_pipeline_count']}/{summary['n_defects']} defects")
    lines.append(f"- **Council verdict match (vs deterministic label):** {summary['verdict_match_total']}/{summary['n_total']}")
    lines.append(f"- **Artifact verdict match:** {summary['artifact_verdict_match_total']}/{summary['n_total']}")
    if summary.get("all_confidences_at_1") is not None:
        lines.append(f"- **All judge confidences == 1.0:** {summary['all_confidences_at_1']}")
    if summary.get("mean_judge_confidence_all_rows") is not None:
        lines.append(f"- **Mean per-judge confidence:** {summary['mean_judge_confidence_all_rows']}")
    lines.append(f"- **Data-point checklist pass:** {summary['data_checks_all_pass_count']}/{summary['n_total']}")
    lines += ["", "## Per-case results"]
    lines.append("| Pick | Pack | Defect? | Compliance | Artifact | Structural | Expected | Unanim≈ | min/max conf | Silent (C/P) | Match | DataOK |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        kind = r.get("pick_kind")
        defect_marker = "clean" if r.get("clean_negative") else ("multi" if r.get("multi_defect") else "defect")
        exp_cv = r.get("expected_compliance_verdict")
        exp_cv_str = "/".join(exp_cv) if isinstance(exp_cv, list) else (exp_cv or "-")
        unanim = "✓A" if r.get("unanimous_judge_approve") else ("✓R" if r.get("unanimous_judge_reject") else "split")
        confs = r.get("judge_confidences") or []
        conf_str = f"{r.get('min_confidence',0):.2f}/{r.get('max_confidence',0):.2f}" if confs else "-"
        sc = f"{int(bool(r.get('silent_confident_council')))}/{int(bool(r.get('silent_confident_pipeline')))}"
        match = "✓" if r.get("verdict_match") else "✗"
        data_ok = "✓" if r.get("data_checks_all_pass") else "✗"
        lines.append(f"| {r['pick_label']} | {r.get('pack')} | {defect_marker} | {r.get('compliance_verdict')} | {r.get('artifact_verdict')} | {r.get('structural_verdict') or '-'} | {exp_cv_str} | {unanim} | {conf_str} | {sc} | {match} | {data_ok} |")
    lines += ["", "## Data-point checklist failures"]
    any_fail = False
    for r in rows:
        failed = [k for k, v in (r.get("data_checks") or {}).items() if not v]
        if failed:
            any_fail = True
            lines.append(f"- **{r['pick_label']}** ({r.get('case_id')}): {', '.join(failed)}")
    if not any_fail:
        lines.append("- _All picks passed the data-point checklist._")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api-key")
    p.add_argument("--org-id")
    p.add_argument("--base-url", default="http://localhost:8002")
    p.add_argument("--picklist", default="/tmp/pilot_picklist.json")
    p.add_argument("--out-prefix", default="out/pilot_thesis_n12")
    p.add_argument("--timeout", type=float, default=180.0)
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    key, org = _live_creds(args, repo_root)
    picklist = _load_picklist(Path(args.picklist))

    print(f"Loaded {len(picklist)} picks from {args.picklist}", file=sys.stderr)

    out_ndjson = repo_root / f"{args.out_prefix}.ndjson"
    out_ndjson.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    n_ok = 0
    n_err = 0

    with out_ndjson.open("w") as out_fp:
        for i, pick in enumerate(picklist):
            case = _hydrate_case(pick, repo_root)
            if case is None:
                print(f"[{i+1:02d}/{len(picklist)}] {pick['pick_label']} {pick['case_id']}: CASE NOT FOUND in fixture", file=sys.stderr)
                n_err += 1
                continue
            binding = PACK_BINDING[pick["pack"]]
            backend = LithrimPipelineBackend(
                base_url=args.base_url,
                api_key=key,
                org_id=org,
                agent_id=binding["agent_id"],
                validator_id=binding["validator_id"],
                timeout=args.timeout,
            )
            t0 = time.monotonic()
            try:
                verdict = backend.evaluate(case)
                elapsed = time.monotonic() - t0
                row = _verdict_to_row(pick, case, verdict, elapsed)
                row = _enrich_with_derived(row)
                rows.append(row)
                out_fp.write(json.dumps(row) + "\n")
                out_fp.flush()
                n_ok += 1
                sc = "SILENT" if row.get("silent_confident_council") else ("MATCH" if row.get("verdict_match") else "MISS")
                print(f"[{i+1:02d}/{len(picklist)}] {pick['pick_label']} {pick['case_id'][:50]} → compliance={row['compliance_verdict']:<13} art={row['artifact_verdict']:<5} struct={(row.get('structural_verdict') or '-'):<5} | {sc} | {elapsed:.1f}s", file=sys.stderr)
            except Exception as e:
                err_row = {
                    "pick_label": pick["pick_label"],
                    "case_id": pick["case_id"],
                    "pack": pick["pack"],
                    "error": str(e),
                    "elapsed_s": round(time.monotonic() - t0, 2),
                }
                out_fp.write(json.dumps(err_row) + "\n")
                out_fp.flush()
                n_err += 1
                print(f"[{i+1:02d}/{len(picklist)}] {pick['pick_label']} {pick['case_id']}: ERROR — {e}", file=sys.stderr)

    summary = _summarize(rows)
    summary["n_ok"] = n_ok
    summary["n_err"] = n_err

    (repo_root / f"{args.out_prefix}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (repo_root / f"{args.out_prefix}.summary.md").write_text(_to_markdown(rows, summary))

    print("", file=sys.stderr)
    print(f"=== Pilot complete: {n_ok} ok, {n_err} err ===", file=sys.stderr)
    print(f"NDJSON: {out_ndjson}", file=sys.stderr)
    print(f"Summary: {repo_root / (args.out_prefix + '.summary.md')}", file=sys.stderr)
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
