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
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .ontology import Ontology, load_ontology

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "ws0-correction/1"
FLOOR_SCHEMA_VERSION = "ws3-floor-correction/1"
WITHSTANDS_SCHEMA_VERSION = "uap3b-withstands-correction/1"
GOLD_SCHEMA_VERSION = "gold-mismatch/1"

DEFAULT_CORRECTIONS_PATH = REPO_ROOT / "out" / "ws0" / "corrections.ndjson"


def _identity(case_id: str | None, agent_id: str | None, pipeline_run_id: str | None) -> dict[str, Any]:
    """CORRECTION-IDENTITY-1: which case/agent/run a correction row belongs to, and when it was
    written. Rows before this carried none of it, so a case's before/after rows could not be
    selected from the log (observed 2026-09-09 on ragtruth_5827). None-safe for callers that
    have no run identity (offline builders) — the keys are always present, never fabricated."""
    from datetime import datetime, timezone

    return {
        "case_id": case_id,
        "agent_id": agent_id,
        "pipeline_run_id": pipeline_run_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def build_correction(
    *,
    suppressed_entry: dict[str, Any],
    result: dict[str, Any],
    composite_before: str,
    composite_after: str,
    ontology: Ontology | None = None,
    case_id: str | None = None,
    agent_id: str | None = None,
    pipeline_run_id: str | None = None,
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
        **_identity(case_id, agent_id, pipeline_run_id),
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
    case_id: str | None = None,
    agent_id: str | None = None,
    pipeline_run_id: str | None = None,
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
        **_identity(case_id, agent_id, pipeline_run_id),
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
    case_id: str | None = None,
    agent_id: str | None = None,
    pipeline_run_id: str | None = None,
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
        **_identity(case_id, agent_id, pipeline_run_id),
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


def corrections_path(out_dir: str | Path | None) -> Path:
    """CORRECTIONS-SCOPE-1: the corrections log is WORKSPACE state. Given the workspace out
    dir a grade persists to, its log lives beside the run blobs (``<out_dir>/corrections.ndjson``);
    with no out dir (the bare CLI default) the legacy repo-level file is kept. Two arms in two
    workspaces no longer interleave in one file."""
    return Path(out_dir) / "corrections.ndjson" if out_dir else DEFAULT_CORRECTIONS_PATH


def build_gold_mismatch(
    *,
    case: dict[str, Any],
    result: dict[str, Any],
    final_verdict: str | None,
    active_codes: Iterable[str],
    ontology: Ontology | None = None,
    contract_versions: Iterable[str] = (),
    case_id: str | None = None,
    agent_id: str | None = None,
    pipeline_run_id: str | None = None,
) -> dict[str, Any] | None:
    """One ``gold-mismatch/1`` record per graded LABELED case: what the label says, what the
    system raised (the judges' own codes and the codes standing after the floor), the miss
    and the spurious sets, whether the verdict agrees, and the judge rollout, with the human
    evidence spans when the case carries them. Written for EVERY labeled case (agreement is a
    row too, so the log is a queryable scorecard), never for an unlabeled one (returns None:
    ``expected_safety_flags`` absent means no answer key, not a clean negative).

    ``agrees_with_gold`` is the strict read: no missed code, no spurious code, verdict match.
    The label basis rides the row (``by_construction`` | ``human_annotated``) so a training
    export can tier on it; ``split`` rides too when the case carries one, so a test-side row
    is never mistaken for a calibration row."""
    expected_raw = case.get("expected_safety_flags")
    if not isinstance(expected_raw, list):
        return None
    ontology = ontology or load_ontology()
    expected = sorted({str(c) for c in expected_raw if c})
    votes = (result.get("semantic") or {}).get("judge_votes") or []
    judge_codes = sorted({str(c) for v in votes for c in (v.get("findings") or []) if c})
    final = sorted({str(c) for c in active_codes if c})
    missed = sorted(set(expected) - set(final))
    spurious = sorted(set(final) - set(expected))
    gold_verdict = str(case.get("expected_artifact_verdict") or ("BLOCK" if expected else "PASS")).upper()
    final_v = str(final_verdict or "").upper()
    blocked = final_v in ("BLOCK", "REJECT", "WARN", "NEEDS_REVIEW")
    verdict_match = (gold_verdict in ("BLOCK", "REJECT")) == blocked
    gold_spans = case.get("gold_spans")
    if gold_spans is None:
        gold_spans = ((case.get("ragtruth") or {}).get("labels")) or None
    return {
        "schema_version": GOLD_SCHEMA_VERSION,
        **_identity(case_id, agent_id, pipeline_run_id),
        "direction": "gold_compare",
        "ground_truth_basis": case.get("ground_truth_basis"),
        "split": case.get("split"),
        "expected_codes": expected,
        "judge_codes": judge_codes,
        "raised_codes": final,
        "missed": missed,
        "spurious": spurious,
        "gold_verdict": gold_verdict,
        "final_verdict": final_v or None,
        "verdict_match": verdict_match,
        "agrees_with_gold": verdict_match and not missed and not spurious,
        "gold_spans": gold_spans,
        "rollout": [
            {
                "judge_role": v.get("judge_role"),
                "reason": v.get("reason"),
                "output": {"vote": v.get("vote"), "findings": v.get("findings")},
                "confidence": v.get("confidence"),
                "model": v.get("model"),
                "served_model": v.get("served_model"),
            }
            for v in votes
        ],
        "ontology_version": ontology.ontology_version,
        "contract_versions": sorted({str(v) for v in contract_versions if v}),
    }


def emit(record: dict[str, Any], *, path: str | Path = DEFAULT_CORRECTIONS_PATH) -> str:
    """Append one record to the corrections NDJSON lake (append-only). Returns path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return str(p)
