#!/usr/bin/env python
"""WS-0 end-to-end runner: one case through the walking-skeleton spine.

    ingest(case) -> grade(replay|live) -> persist -> ground -> composite + calibration

Prints the composite verdict, the suppressed-finding correction (the S-BS-7
tool-grounded verdict correction), and the report-only calibration summary.

Defaults run the captured-baseline REPLAY path (zero new paid calls). ``--live``
opts into a real, paid ``:8002 /v1/pipeline/evaluate`` call and is OFF by default.

    python scripts/run_ws0.py
    python scripts/run_ws0.py --case <case_id> --baseline <path>
    python scripts/run_ws0.py --live          # paid; opt-in only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lithrim_bench.harness.correction import build_correction, emit
from lithrim_bench.harness.grade import grade_live, grade_replay
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.persist import persist
from lithrim_bench.harness.report import calibration, composite
from lithrim_bench.picklist import resolve_case_fixtures

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
# Pin the driver's cited source (§1 item 6). NOTE: picklist.resolve_case_fixtures
# tries out/scribe_v1.n10.jsonl FIRST, and that file carries the SAME case_id with
# a DIFFERENT expected_compliance_verdict shape (accept-set list vs the string
# "reject" here) — see S-BS-9. We load the driver-cited row directly so the runner
# and the vendored test fixture agree.
DEFAULT_SOURCE = REPO_ROOT / "out" / "scribe_v1.jsonl"
DEFAULT_BASELINE = (
    REPO_ROOT
    / "out"
    / "scribe_v1.live_pipeline_evaluate.bench_scribe_v1_inject_condition_1bd0f10dc7b5.json"
)


def _load_case(case_id: str, source: str | Path) -> dict | None:
    """Load a case row by id from ``source`` (driver-cited file); fall back to picklist."""
    source = Path(source)
    if source.exists():
        for line in source.open():
            row = json.loads(line)
            if (row.get("case_id") or row.get("id")) == case_id:
                return row
    return resolve_case_fixtures({case_id}).get(case_id)


def expected_block(case: dict) -> bool:
    """True when 'reject' is (or is among) the case's expected compliance verdict.

    Tolerates both the string shape (out/scribe_v1.jsonl: "reject") and the
    accept-set list shape (out/scribe_v1.n10.jsonl: ["needs_review", "reject"]).
    """
    expected = case.get("expected_compliance_verdict")
    if isinstance(expected, list):
        return "reject" in expected
    return expected == "reject"


def build_record(case, result, grounded, comp, cal, corrections, *, grade_path):
    return {
        "case_id": case.get("case_id"),
        "result": result,
        "grounded": {
            "verdict": grounded.verdict,
            "original_verdict": grounded.original_verdict,
            "active": grounded.active,
            "suppressed": [
                {
                    "code": s["finding"].get("code"),
                    "contract": s["contract"].version,
                    "disproved": s["verdict"].disproved,
                    "matched_token": s["verdict"].matched_token,
                    "evidence": s["verdict"].evidence,
                    "reason": s["verdict"].reason,
                }
                for s in grounded.suppressed
            ],
            "ungrounded": grounded.ungrounded,
        },
        "composite": comp,
        "calibration": cal,
        "corrections": corrections,
        "provenance": {
            "expected_compliance_verdict": case.get("expected_compliance_verdict"),
            "expected_safety_flags": case.get("expected_safety_flags"),
            "grade_path": grade_path,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WS-0 one-case-over-live runner")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument(
        "--live",
        action="store_true",
        help="opt into a real, PAID :8002 call (default: replay the baseline)",
    )
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    case = _load_case(args.case, args.source)
    if case is None:
        sys.stderr.write(f"ERROR: case {args.case!r} not found in {args.source} or pack files.\n")
        return 2

    if args.live:
        sys.stderr.write("WARNING: --live makes a real paid council call.\n")
        result = grade_live(case)
    else:
        result = grade_replay(case, args.baseline)

    grounded = ground(result, case)
    comp = composite(grounded)
    cal = calibration(result, expected_block=expected_block(case))

    corrections = []
    for entry in grounded.suppressed:
        rec = build_correction(
            suppressed_entry=entry,
            result=result,
            composite_before=grounded.original_verdict or comp["stage_verdict"],
            composite_after=grounded.verdict,
        )
        emit(rec)
        corrections.append(rec)

    out_dir = args.out_dir or (REPO_ROOT / "out" / "ws0")
    grade_path = "live" if args.live else "replay"
    record = build_record(case, result, grounded, comp, cal, corrections, grade_path=grade_path)
    paths = persist(args.case, record, out_dir=out_dir)

    print(f"=== WS-0 one case end-to-end ({'live' if args.live else 'replay'}) ===")
    print(f"case: {args.case}")
    print(
        f"verdict: {comp['verdict']} (stage {comp['stage_verdict']}, was "
        f"{grounded.original_verdict}; expected {case.get('expected_compliance_verdict')})"
    )
    print(f"composite score: {comp['score']}")
    print(f"active findings: {comp['active_findings']}")
    print(f"ungrounded (null-code, skip-logged): {comp['ungrounded_count']}")
    print("--- grounded corrections (S-BS-7) ---")
    if not corrections:
        print("  (none)")
    for rec in corrections:
        print(
            f"  {rec['original_label']} -> SUPPRESSED via {rec['contract_version']}: "
            f"{rec['tool_result']['reason']}"
        )
    print("--- calibration (REPORT-ONLY, not a gate) ---")
    print(f"  ECE: {cal['ece']} over {cal['n_with_confidence']} non-null confidence(s)")
    if cal["caveat"]:
        print(f"  caveat: {cal['caveat']}")
    print(f"persisted: {paths['blob']} | {paths['sqlite']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
