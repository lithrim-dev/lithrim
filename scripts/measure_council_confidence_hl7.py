"""P1-EXP-0: live council sweep on hl7_adt_v1 capturing per-judge confidence.

Runs LithrimPipelineBackend (live council + structural via /v1/pipeline/evaluate)
on each row of out/hl7_adt_v1.jsonl with validator_id=93 (strict HL7 ADT^A04 —
the generated Jute Copilot artifact that catches all 28 defect classes per
STRICT_HL7_VALIDATOR_2026-05-22.md). One round-trip per case; per_judge.confidence
is now captured (commit 32d1bf7 — feat(bench): capture per-judge confidence...).

Output: NDJSON, one row per case, each row contains
    case_id, expected_compliance_verdict, expected_structural_verdict,
    compliance_verdict, artifact_verdict, flags, per_judge (dict of role ->
    {judge_name, verdict, flags, confidence}), structural_verdict,
    structural_findings, raw.

Failed cases write a single error row instead. Script exits 0 if ≥ 38/40
succeed (the driver §2 deliverable-2 resilience gate), 1 otherwise.

The first case doubles as the §8 first-move smoke check: if structural never
runs (validator_id ignored) OR every confidence is 0.0 (wire-shape regression
on lithrim-backend), the script halts and surfaces — no point burning the
remaining $5.
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


def _read_live_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent.parent / ".live_env"
    if not env_path.exists():
        return {}
    return dict(line.split("=", 1) for line in env_path.read_text().splitlines() if "=" in line)


def _live_creds(args: argparse.Namespace) -> tuple[str, str]:
    live = _read_live_env()
    key = args.api_key or os.environ.get("LITHRIM_API_KEY") or live.get("LITHRIM_API_KEY")
    org = args.org_id or os.environ.get("LITHRIM_ORG_ID") or live.get("LITHRIM_ORG_ID")
    if not key or not org:
        sys.exit(
            "--api-key/--org-id required (or set LITHRIM_API_KEY/LITHRIM_ORG_ID, or .live_env)"
        )
    return key, org


def _verdict_to_row(case: dict, verdict) -> dict:
    per_judge_dict = None
    if verdict.per_judge is not None:
        per_judge_dict = {role: dataclasses.asdict(jo) for role, jo in verdict.per_judge.items()}
    return {
        "case_id": case["case_id"],
        "expected_compliance_verdict": case.get("expected_compliance_verdict"),
        "expected_structural_verdict": case.get("expected_structural_verdict"),
        "expected_safety_flags": case.get("expected_safety_flags", []),
        "clean_negative": case.get("clean_negative", False),
        "split": case.get("split"),
        "compliance_verdict": verdict.compliance_verdict,
        "artifact_verdict": verdict.artifact_verdict,
        "flags": verdict.flags,
        "per_judge": per_judge_dict,
        "structural_verdict": verdict.structural_verdict,
        "structural_findings": verdict.structural_findings,
        "raw": verdict.raw,
    }


def _smoke_check_confidence(row: dict) -> str | None:
    """After any case: confirm council ran and confidence is being emitted."""
    pj = row.get("per_judge")
    if not pj:
        return "case has no per_judge — council not running, halt"
    confidences = [judge.get("confidence", 0.0) for judge in pj.values()]
    if all(c == 0.0 for c in confidences):
        return (
            f"all-zero confidences on per_judge ({confidences}) — wire-shape regression "
            "on lithrim-backend JudgeVote.confidence; halt before burning $5"
        )
    return None


def _smoke_check_validator(row: dict) -> str | None:
    """After first defect case: confirm validator_id is actually exercised."""
    if row.get("clean_negative", False):
        return None  # only meaningful on defect-bearing cases
    sv = row.get("structural_verdict")
    sf = row.get("structural_findings") or []
    if sv == "PASS" and not sf:
        return (
            "first defect case structural_verdict=PASS with no findings — "
            "validator_id likely ignored; halt before burning $5"
        )
    if sv is None:
        return "structural_verdict is None on defect case — validator not running, halt"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-path", type=Path, default=Path("out/hl7_adt_v1.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("out/p1_exp_0_council_confidence.ndjson"))
    ap.add_argument(
        "--n", type=int, default=1, help="repeats per case (default 1; N=3 buys variance)"
    )
    ap.add_argument(
        "--validator-id",
        default="93",
        help="etlp-mapper mapping id (default 93 = strict HL7 ADT^A04)",
    )
    ap.add_argument("--base-url", default="http://localhost:8002")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--org-id", default=None)
    args = ap.parse_args()

    if not args.pack_path.exists():
        sys.exit(f"pack not found: {args.pack_path}")
    if args.n != 1:
        print(
            f"NOTE: --n {args.n} — running each case {args.n}x (cost scales linearly)", flush=True
        )

    key, org = _live_creds(args)
    backend = LithrimPipelineBackend(
        base_url=args.base_url,
        api_key=key,
        org_id=org,
        validator_id=args.validator_id,
    )

    cases = [json.loads(line) for line in args.pack_path.read_text().splitlines() if line.strip()]
    print(f"loaded {len(cases)} cases from {args.pack_path}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    successes = 0
    failures = 0
    t0 = time.time()
    confidence_smoke_done = False
    validator_smoke_done = False

    with args.out.open("w") as f:
        for i, case in enumerate(cases):
            for rep in range(args.n):
                try:
                    verdict = backend.evaluate(case)
                    row = _verdict_to_row(case, verdict)
                    if args.n != 1:
                        row["rep"] = rep
                    f.write(json.dumps(row) + "\n")
                    f.flush()
                    successes += 1
                    if not confidence_smoke_done:
                        halt = _smoke_check_confidence(row)
                        if halt is not None:
                            sys.exit(f"smoke (confidence) failed on case {i}: {halt}")
                        confidence_smoke_done = True
                        confs = {
                            r: jd["confidence"] for r, jd in (row.get("per_judge") or {}).items()
                        }
                        print(f"  smoke OK (confidence) on case {i}: {confs}", flush=True)
                    if not validator_smoke_done and not row.get("clean_negative", False):
                        halt = _smoke_check_validator(row)
                        if halt is not None:
                            sys.exit(f"smoke (validator_id) failed on case {i}: {halt}")
                        validator_smoke_done = True
                        print(
                            f"  smoke OK (validator_id={args.validator_id}) on case {i}: "
                            f"structural_verdict={row.get('structural_verdict')}, "
                            f"findings={row.get('structural_findings')}",
                            flush=True,
                        )
                except Exception as exc:
                    f.write(json.dumps({"case_id": case.get("case_id"), "error": repr(exc)}) + "\n")
                    f.flush()
                    failures += 1
                    print(f"  case {i} ({case.get('case_id')}): FAILED — {exc!r}", flush=True)
            if (i + 1) % 5 == 0:
                print(
                    f"  ... {i + 1}/{len(cases)} cases done ({successes} ok, {failures} failed)",
                    flush=True,
                )

    duration = time.time() - t0
    total = successes + failures
    threshold = int(round(0.90 * len(cases) * args.n))
    print(
        json.dumps(
            {
                "output": str(args.out),
                "successes": successes,
                "failures": failures,
                "total": total,
                "duration_s": round(duration, 1),
                "threshold_for_exit_0": threshold,
            },
            indent=2,
        )
    )
    return 0 if successes >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
