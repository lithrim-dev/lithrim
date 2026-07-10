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

from .ontology import Ontology, load_ontology

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "ws0-correction/1"
FLOOR_SCHEMA_VERSION = "ws3-floor-correction/1"
WITHSTANDS_SCHEMA_VERSION = "uap3b-withstands-correction/1"

DEFAULT_CORRECTIONS_PATH = REPO_ROOT / "out" / "ws0" / "corrections.ndjson"


def build_correction(
    *,
    suppressed_entry: dict[str, Any],
    result: dict[str, Any],
    composite_before: str,
    composite_after: str,
    ontology: Ontology | None = None,
) -> dict[str, Any]:
    """Assemble one correction record for a disproved (suppressed) finding.

    ``ontology_version`` and the corrected flag's ``owner_roles`` are read from the
    ontology (default: the committed clinical ontology). The owners are recorded so
    a later, role-aware calibration (WS-0 critique Q4.1, fixed in WS-4) can tell
    whose vote was corrected — WS-1 only *records* them.
    """
    ontology = ontology or load_ontology()
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
            # REL-OPS-1 O2: absent (not null) for non-terminology contracts.
            **(
                {"terminology_edition": edition}
                if (edition := getattr(verdict, "terminology_edition", None)) is not None
                else {}
            ),
        },
        "original_label": code,
        "corrected_label": None,
        "owner_roles": list(ontology.owners_of(code)),
        "composite_before": composite_before,
        "composite_after": composite_after,
        "ontology_version": ontology.ontology_version,
        "contract_version": contract.version,
    }


def build_floor_correction(
    *,
    floor_block: dict[str, Any],
    result: dict[str, Any],
    composite_before: str,
    composite_after: str,
    ontology: Ontology | None = None,
) -> dict[str, Any]:
    """Assemble one correction record for a WS-3 structural-FLOOR flip.

    This is the inverse of :func:`build_correction`. Where the suppress record pairs
    (a confident judge rollout that RAISED a wrong flag → a tool that disproved it),
    the floor record pairs (a council rollout that voted PASS and MISSED a real
    structural violation → a deterministic verifier that caught it). Because no judge
    raised the injected flag, the ``rollout`` keeps EVERY judge vote (the whole
    miss), not the raisers-only subset the suppress record filters to.

    ``floor_block`` is a ``GroundedResult.floor_blocks`` entry: ``{decl, result,
    injected_finding}``. Only call this for an entry whose ``injected_finding`` is
    non-None (a real flip); an inconclusive floor never produces a correction.
    """
    ontology = ontology or load_ontology()
    decl = floor_block["decl"]
    vr = floor_block["result"]
    injected = floor_block["injected_finding"]
    code = injected["code"] if injected else decl.params.get("inject_flag_code")

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
    ]

    return {
        "schema_version": FLOOR_SCHEMA_VERSION,
        "direction": "floor_inject",
        "rollout": rollout,
        "tool_call": {
            "contract_type": decl.contract_type,
            "contract_version": decl.version,
            "flag_code": code,
            "question": decl.question,
        },
        "tool_result": {
            "conforms": vr.conforms,
            "disposition": vr.disposition,
            "evidence": vr.evidence,
            "manifest": vr.manifest,
        },
        "injected_label": code,
        "original_label": None,
        "owner_roles": list(ontology.owners_of(code)),
        "composite_before": composite_before,
        "composite_after": composite_after,
        "ontology_version": ontology.ontology_version,
        "contract_version": decl.version,
    }


def build_withstands_correction(
    *,
    role: str,
    what_failed: list[dict[str, Any]],
    decision_before: str | None,
    decision_after: str | None,
    result: dict[str, Any],
    composite_before: str | None,
    composite_after: str | None,
    ontology: Ontology | None = None,
) -> dict[str, Any]:
    """Assemble one correction record for a per-judge withstands-gate correction (UAP-3b).

    The third correction direction (after :func:`build_correction`'s suppress and
    :func:`build_floor_correction`'s inverse floor): the PRE-consensus withstands-gate
    corrected one judge's verdict — it either suppressed a validator-disproved finding
    or rejected an out-of-lens finding no owning judge corroborated. The record pairs
    (the corrected judge's rollout) with (the deterministic signal that corrected it,
    ``what_failed``), the RLVR shape for the per-judge critique floor.

    ``what_failed`` is the gate's per-finding ruling list (``{code, mode, reason}``).
    ``role`` is the corrected judge. The rollout keeps that judge's vote (the wrong
    raise being corrected). ``owner_roles`` is recorded per corrected code from the
    ontology, mirroring the other correction builders.
    """
    ontology = ontology or load_ontology()
    corrected_codes = [w.get("code") for w in (what_failed or []) if w.get("code")]
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
        if v.get("judge_role") == role
    ]

    return {
        "schema_version": WITHSTANDS_SCHEMA_VERSION,
        "direction": "withstands_correct",
        "role": role,
        "rollout": rollout,
        "what_failed": list(what_failed or []),
        "decision_before": decision_before,
        "decision_after": decision_after,
        "corrected_labels": corrected_codes,
        "owner_roles": {c: list(ontology.owners_of(c)) for c in corrected_codes},
        "composite_before": composite_before,
        "composite_after": composite_after,
        "ontology_version": ontology.ontology_version,
    }


def emit(record: dict[str, Any], *, path: str | Path = DEFAULT_CORRECTIONS_PATH) -> str:
    """Append one record to the corrections NDJSON lake (append-only). Returns path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return str(p)
