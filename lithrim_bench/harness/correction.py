"""Fine-tuning-ready correction records — the RLVR / data-lake north star.

Every time a verification contract flips a verdict, we emit a structured,
versioned record of the rollout that produced the wrong label and the tool result
that disproved it. The verification contract is the verifiable reward: the record
pairs (judge rollout -> tool-checked ground truth), which is exactly the shape an
RLVR / fine-tuning flywheel consumes later. Append-only NDJSON; lake-bound later
via the etlp file->S3 connector (out of scope to wire here).

The ``rollout`` field is a *list* of per-judge rollouts (the raw-events shape), so
each contributing judge's own confidence is preserved — the same per-rollout
confidence the calibration report reads. A correction with co-voting judges keeps
all of them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "ws0-correction/1"
# No ontology table yet (that is WS-1); the contract set is hardcoded in
# grounding.WS0_CONTRACTS. Pin a sentinel so downstream consumers can tell which
# ontology generation produced the record.
ONTOLOGY_VERSION = "ws0-hardcoded/0"

DEFAULT_CORRECTIONS_PATH = REPO_ROOT / "out" / "ws0" / "corrections.ndjson"


def build_correction(
    *,
    suppressed_entry: dict[str, Any],
    result: dict[str, Any],
    composite_before: str,
    composite_after: str,
) -> dict[str, Any]:
    """Assemble one correction record for a disproved (suppressed) finding."""
    finding = suppressed_entry["finding"]
    verdict = suppressed_entry["verdict"]
    contract = suppressed_entry["contract"]
    code = finding.get("code")

    votes = (result.get("semantic") or {}).get("judge_votes") or []
    rollout = [
        {
            "judge_role": v.get("judge_role"),
            "reason": v.get("reason"),
            "output": {"vote": v.get("vote"), "findings": v.get("findings")},
            "confidence": v.get("confidence"),
            "model": v.get("model"),
        }
        for v in votes
        if code in (v.get("findings") or [])
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "rollout": rollout,
        "tool_call": {
            "contract": contract.__class__.__name__,
            "contract_version": contract.version,
            "flag_code": contract.flag_code,
            "question": contract.question,
        },
        "tool_result": {
            "disproved": verdict.disproved,
            "matched_token": verdict.matched_token,
            "evidence": verdict.evidence,
            "reason": verdict.reason,
        },
        "original_label": code,
        "corrected_label": None,
        "composite_before": composite_before,
        "composite_after": composite_after,
        "ontology_version": ONTOLOGY_VERSION,
        "contract_version": contract.version,
    }


def emit(record: dict[str, Any], *, path: str | Path = DEFAULT_CORRECTIONS_PATH) -> str:
    """Append one record to the corrections NDJSON lake (append-only). Returns path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return str(p)
