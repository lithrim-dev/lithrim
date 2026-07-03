"""Replay-from-provenance: turn a persisted run blob back into a replay-ready result.

PERSIST-2a. The in_process/live grade already persists a full ``PipelineProvenance``
blob; this module is the thin, pure layer above the frozen seam that makes that blob
*be* the replay baseline:

  * :func:`provenance_to_result` re-shapes the persisted ``provenance`` sub-tree into the
    ``PipelineResult``-shaped dict that ``ground``/``composite``/``calibration`` consume
    (no model edit, no consensus touch).
  * :func:`grade_signature` is a stable hash of the grade-determining config (ontology +
    authored assignments/models + council_config), stamped on each persisted version.
  * :func:`is_fresh` is the swappable freshness predicate (drift-aware default): a head is
    served only when its stamped signature matches the current config's.

Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_NOT_APPLICABLE = {"status": "not_applicable", "findings": [], "evidence": [], "judge_votes": []}


def provenance_to_result(
    blob: dict, *, pipeline_run_id: str | None = None, replay_of: str | None = None
) -> dict:
    """Re-shape a persisted ``PipelineProvenance`` blob into a ``PipelineResult``-shaped
    dict the grade-downstream stages (``ground``/``composite``/``calibration``) consume.

    Lifts ``verdict``/``gate_decision``/``findings`` to the top level, promotes
    ``stage_results['semantic']`` (and ``structural``) to top-level stages, and re-nests the
    blob under ``provenance`` (so ``pipeline_run_id`` + the withstands/audit legs are intact).
    A pure function above the frozen seam — the moat path never sees it.

    RUNTRAIL-1 (append-with-lineage): when ``pipeline_run_id`` is supplied, the replayed
    result carries a FRESH identity — the blob is copied (the baseline is left
    byte-unchanged), its ``pipeline_run_id`` overwritten with the minted id, and
    ``replay_of`` stamped to point at the baseline. This is the single place a replayed
    blob's identity is assembled, so a re-grade APPENDS a new audit row that points at its
    baseline rather than overwriting it. Absent the override (e.g. RUNTRAIL-4 rehydrate) the
    blob's own identity is preserved verbatim — back-compatible.
    """
    blob = dict(blob)
    if pipeline_run_id is not None:
        blob["pipeline_run_id"] = pipeline_run_id
        blob["replay_of"] = replay_of
    stage_results = blob.get("stage_results") or {}
    return {
        "verdict": blob.get("verdict"),
        "gate_decision": blob.get("gate_decision"),
        "findings": blob.get("findings") or [],
        "structural": stage_results.get("structural") or dict(_NOT_APPLICABLE),
        "semantic": stage_results.get("semantic") or dict(_NOT_APPLICABLE),
        "provenance": blob,
    }


def demo_digests(out_dir: Any) -> dict[str, str]:
    """SIGNATURE-1: content digests of the DEMO-PIN-1 compiled few-shot demo files under
    ``out_dir`` (``compiled_demos_*.json``) — pinned demos grade-affect, so they must move
    the grade signature. Filename-glob (no pack/council import: the $0 replay path stays
    import-light); ``{}`` when absent/None. Deterministic: sorted filenames → sha256 bytes."""
    if out_dir is None:
        return {}
    root = Path(out_dir)
    if not root.is_dir():
        return {}
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.glob("compiled_demos_*.json"))
    }


def grade_signature(
    ontology: Any,
    *,
    assignments: Any,
    models: Any,
    council_config: Any,
    criteria: Any = None,
    samples: Any = None,
    temperatures: Any = None,
    demo_digests: Any = None,
) -> str:
    """A stable ``sha256`` over the grade-DETERMINING config: the ontology + the AUTHORED
    (pre-default) per-role ``assignments``/``models`` + the ``council_config`` +
    (SIGNATURE-1) the per-judge ``criteria``/``samples``/``temperatures`` and the pinned
    demo digests. Stamped on each persisted version and recomputed at replay-resolve; a
    mismatch means the config drifted since the head was graded (the freshness guard's input).

    SIGNATURE-1 closes the stale-served-as-fresh P0: criterion/k/temperature + DEMO-PIN-1
    demos all thread into the grade but escaped the hash, so an edited criterion replayed
    the pre-edit verdict labeled fresh. Widening makes every pre-widening head stale by
    construction — CORRECT (those heads genuinely don't pin these inputs); the freshness
    guard's 409 says how to re-grade.

    Hashing the authored (not full-lens-defaulted) assignments keeps grade-time and
    resolve-time in agreement: the full-lens default is derived from the ontology + roster,
    and the ontology is already in the hash, so excluding the derived default is safe.
    """
    payload = {
        "ontology": ontology,
        "assignments": assignments,
        "models": models,
        "council_config": council_config,
        "criteria": criteria or {},
        "samples": samples or {},
        "temperatures": temperatures or {},
        "demo_digests": demo_digests or {},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def is_fresh(head: dict, current_signature: str) -> bool:
    """The freshness predicate — DRIFT-AWARE default (PERSIST-2a Decision 1): a head is
    fresh iff it carries a grade signature equal to the current config's. An un-signed head
    is never fresh. Swap this one function for pure-cache (``return True``) or no-cache
    (``return False``) once the owner settles the policy."""
    sig = head.get("grade_signature")
    return bool(sig) and sig == current_signature
