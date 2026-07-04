"""Provider-drift canary (REL-OPS-1 O1).

Detects a provider silently changing model behavior behind a pinned model
string by re-grading a small frozen golden set and diffing verdicts
case-by-case against a pinned baseline.

Two modes:

- ``--record`` mints the baseline JSON: per-case verdicts + flags, the run's
  configured pin identifiers (the backend ``BackendPin``), and a timestamp.
- default re-runs the SAME set through the SAME grading path
  (``eval_runner.run_pack`` + ``analysis.analyze_per_case`` — no second
  grading path) and diffs verdict-by-verdict, printing a per-case table and
  exiting non-zero iff any verdict flipped. Flag deltas are reported in the
  table but do not flip the exit code.

Known limitation (documented, not hacked around): response-side provider
fingerprints (e.g. OpenAI's ``system_fingerprint``) surface below the frozen
``runtime/council/judges_dspy.py`` seam, which this cut must not touch. The
baseline therefore records CONFIGURED model identifiers only (the pin the
backend was constructed with); per-response fingerprint capture into
``PipelineProvenance`` is a follow-up requiring an owner decision on a seam
carve-out.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis import analyze_per_case, read_runs
from .backends.base import BackendClient
from .eval_runner import run_pack

PIN_IDENTITY_FIELDS = ("backend", "backend_version", "judge_model", "judge_model_version")


def grade_golden_set(
    *, pack_path: Path, backend: BackendClient, n: int, runs_out: Path
) -> dict[str, dict[str, Any]]:
    """One pass over the golden set via the existing eval_runner path.

    Returns ``{case_id: {"verdict": modal_verdict, "flags": majority_flags}}``.
    """
    run_pack(pack_path=pack_path, backend=backend, n=n, out_path=runs_out)
    rows = read_runs(runs_out)
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_case[r["case_id"]].append(r)
    cases: dict[str, dict[str, Any]] = {}
    for c in analyze_per_case(rows):
        case_rows = by_case[c["case_id"]]
        counts = Counter(f for r in case_rows for f in (r.get("flags") or []))
        flags = sorted(f for f, k in counts.items() if k * 2 > len(case_rows))
        cases[c["case_id"]] = {"verdict": c["modal_verdict"], "flags": flags}
    return cases


def record_baseline(
    *, pack_path: Path, backend: BackendClient, n: int, runs_out: Path
) -> dict[str, Any]:
    return {
        "canary_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "pack_path": str(pack_path),
        "n": n,
        "pin": asdict(backend.pin),
        "cases": grade_golden_set(pack_path=pack_path, backend=backend, n=n, runs_out=runs_out),
    }


def _flag_delta(base: list[str], curr: list[str]) -> str:
    added = sorted(set(curr) - set(base))
    removed = sorted(set(base) - set(curr))
    parts = [f"+{f}" for f in added] + [f"-{f}" for f in removed]
    return " ".join(parts)


def diff_verdicts(
    baseline_cases: dict[str, dict[str, Any]], current_cases: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for case_id in sorted(set(baseline_cases) | set(current_cases)):
        base = baseline_cases.get(case_id)
        curr = current_cases.get(case_id)
        base_v = base["verdict"] if base else "ABSENT"
        curr_v = curr["verdict"] if curr else "ABSENT"
        rows.append(
            {
                "case_id": case_id,
                "baseline_verdict": base_v,
                "current_verdict": curr_v,
                "flipped": base_v != curr_v,
                "flag_delta": _flag_delta(
                    (base or {}).get("flags") or [], (curr or {}).get("flags") or []
                ),
            }
        )
    return rows


def _print_diff(rows: list[dict[str, Any]], baseline_pin: dict, current_pin: dict) -> None:
    changed_identity = {
        f: (baseline_pin.get(f), current_pin.get(f))
        for f in PIN_IDENTITY_FIELDS
        if baseline_pin.get(f) != current_pin.get(f)
    }
    if changed_identity:
        print(
            "notice: configured pin identity changed since the baseline "
            f"({changed_identity}) — this diff reflects a CONFIG change, "
            "not silent provider drift behind a pinned model string."
        )
    print(f"{'case':<34} {'baseline':<14} {'current':<14} {'':<6} flags")
    for r in rows:
        status = "DRIFT" if r["flipped"] else "ok"
        print(
            f"{r['case_id']:<34} {r['baseline_verdict']:<14} "
            f"{r['current_verdict']:<14} {status:<6} {r['flag_delta']}"
        )


def _build_backend(args: argparse.Namespace) -> BackendClient:
    if args.backend == "mock":
        from .backends import MockBackend

        return MockBackend(
            decision_flip_rate=args.decision_flip_rate,
            flag_attachment_rate=args.flag_attachment_rate,
            noise_seed=args.noise_seed,
        )
    if args.backend == "lithrim-pipeline":
        from .backends import LithrimPipelineBackend

        key = args.api_key or os.environ.get("LITHRIM_API_KEY")
        org = args.org_id or os.environ.get("LITHRIM_ORG_ID")
        if not key or not org:
            raise SystemExit("--api-key/--org-id required (or LITHRIM_API_KEY/LITHRIM_ORG_ID)")
        return LithrimPipelineBackend(base_url=args.base_url, api_key=key, org_id=org)
    from .backends import LithrimHttpBackend

    return LithrimHttpBackend(
        base_url=args.base_url,
        api_key=args.api_key or os.environ.get("LITHRIM_API_KEY"),
        judge_model=args.judge_model,
        judge_model_version=args.judge_model_version,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="provider-drift canary (REL-OPS-1 O1)")
    ap.add_argument("--pack-path", required=True, type=Path, help="the frozen golden set (JSONL)")
    ap.add_argument("--baseline", required=True, type=Path, help="the pinned baseline JSON")
    ap.add_argument(
        "--record", action="store_true", help="mint the baseline instead of diffing against it"
    )
    ap.add_argument("--n", type=int, default=1, help="runs per case (modal verdict when >1)")
    ap.add_argument("--runs-out", type=Path, default=None)
    ap.add_argument(
        "--backend", choices=["mock", "http", "lithrim-pipeline"], default="lithrim-pipeline"
    )
    ap.add_argument("--decision-flip-rate", type=float, default=0.0)
    ap.add_argument("--flag-attachment-rate", type=float, default=1.0)
    ap.add_argument("--noise-seed", type=int, default=0)
    ap.add_argument("--base-url", default="http://localhost:8002")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--org-id", default=None)
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--judge-model-version", default=None)
    args = ap.parse_args(argv)

    if not args.pack_path.exists():
        raise SystemExit(f"golden set not found: {args.pack_path}")
    backend = _build_backend(args)
    runs_out = args.runs_out or args.pack_path.with_name(
        args.pack_path.stem + (".baseline" if args.record else ".canary") + ".runs.ndjson"
    )

    if args.record:
        doc = record_baseline(
            pack_path=args.pack_path, backend=backend, n=args.n, runs_out=runs_out
        )
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"baseline recorded: {args.baseline} ({len(doc['cases'])} cases)")
        return 0

    if not args.baseline.exists():
        raise SystemExit(f"baseline not found: {args.baseline} — mint it with --record first")
    baseline = json.loads(args.baseline.read_text())
    current_cases = grade_golden_set(
        pack_path=args.pack_path, backend=backend, n=args.n, runs_out=runs_out
    )
    rows = diff_verdicts(baseline["cases"], current_cases)
    _print_diff(rows, baseline.get("pin") or {}, asdict(backend.pin))
    flipped = [r["case_id"] for r in rows if r["flipped"]]
    if flipped:
        print(f"drift: {len(flipped)} verdict flip(s): {', '.join(flipped)}")
        return 1
    print(f"canary: no drift — {len(rows)} case verdict(s) match the baseline")
    return 0
