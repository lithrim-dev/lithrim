"""N-run eval loop with NDJSON persistence.

For each case in a pack, calls backend.evaluate(case) N times and
writes one NDJSON row per (case, run_index). Order of cases in the
output follows the input pack JSONL; order within a case is 0..N-1.

Output schema (one NDJSON row per run):

    {
      "case_id": str,
      "pack": str,
      "agent_type": str,
      "run_index": int,
      "started_at": ISO8601,
      "duration_ms": int,
      "compliance_verdict": str,
      "artifact_verdict": str,
      "flags": list[str],
      "per_judge": dict[str, {"verdict": str, "flags": list[str], "confidence": float, "reason": str}] | null,
      "findings_rich": list[dict],          # full Finding.model_dump() (detail/code/severity/chunk_id/spans)
      "structural_findings_rich": list[dict],
      "pin": dict,      # BackendPin fields + dataset_sha256 (eval spec §1.6 pinned block)
      "expected_compliance_verdict": str | list[str],
      "expected_safety_flags": list[str]
    }

per_judge.reason + findings_rich.detail are the offline root-cause surface: a
calibration miss (e.g. a false MEDICATION_NOT_IN_TRANSCRIPT) can be diagnosed
from the persisted row without re-issuing the paid council call.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends.base import BackendClient, BackendVerdict


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verdict_row(
    case: dict[str, Any],
    run_index: int,
    started_at: str,
    duration_ms: int,
    v: BackendVerdict,
    pin: dict[str, Any],
) -> dict[str, Any]:
    per_judge = None
    if v.per_judge is not None:
        per_judge = {
            name: {
                "verdict": j.verdict,
                "flags": list(j.flags),
                "confidence": j.confidence,
                "reason": j.reason,
            }
            for name, j in v.per_judge.items()
        }
    return {
        "case_id": case["case_id"],
        "pack": case.get("pack"),
        "agent_type": case.get("agent_type"),
        "run_index": run_index,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "compliance_verdict": v.compliance_verdict,
        "artifact_verdict": v.artifact_verdict,
        "flags": list(v.flags),
        "per_judge": per_judge,
        "structural_verdict": v.structural_verdict,
        "structural_findings": list(v.structural_findings),
        "findings_rich": list(v.findings_rich),
        "structural_findings_rich": list(v.structural_findings_rich),
        "pin": pin,
        "expected_compliance_verdict": case.get("expected_compliance_verdict"),
        "expected_safety_flags": case.get("expected_safety_flags") or [],
        "expected_structural_verdict": case.get("expected_structural_verdict"),
    }


def read_pack(path: Path) -> Iterator[dict[str, Any]]:
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def run_pack(
    *,
    pack_path: Path,
    backend: BackendClient,
    n: int,
    out_path: Path,
    case_filter: set[str] | None = None,
    on_case: callable | None = None,
) -> dict[str, int]:
    """Run the pack N times per case. Writes one NDJSON row per run.

    Returns a summary dict with totals.
    """
    pin = asdict(backend.pin)
    pin["dataset_sha256"] = hashlib.sha256(pack_path.read_bytes()).hexdigest()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cases = list(read_pack(pack_path))
    if case_filter is not None:
        cases = [c for c in cases if c["case_id"] in case_filter]

    written = 0
    with out_path.open("w") as f:
        for case in cases:
            for run_index in range(n):
                t0 = time.perf_counter()
                started_at = _utcnow_iso()
                v = backend.evaluate(case)
                duration_ms = int((time.perf_counter() - t0) * 1000)
                row = _verdict_row(case, run_index, started_at, duration_ms, v, pin)
                f.write(json.dumps(row) + "\n")
                written += 1
            if on_case is not None:
                on_case(case["case_id"])

    return {"cases": len(cases), "runs_per_case": n, "rows_written": written}
