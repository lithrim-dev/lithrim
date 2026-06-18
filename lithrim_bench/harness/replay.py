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
from typing import Any

_NOT_APPLICABLE = {"status": "not_applicable", "findings": [], "evidence": [], "judge_votes": []}


def provenance_to_result(blob: dict) -> dict:
    """Re-shape a persisted ``PipelineProvenance`` blob into a ``PipelineResult``-shaped
    dict the grade-downstream stages (``ground``/``composite``/``calibration``) consume.

    Lifts ``verdict``/``gate_decision``/``findings`` to the top level, promotes
    ``stage_results['semantic']`` (and ``structural``) to top-level stages, and re-nests the
    blob under ``provenance`` (so ``pipeline_run_id`` + the withstands/audit legs are intact).
    A pure function above the frozen seam — the moat path never sees it.
    """
    stage_results = blob.get("stage_results") or {}
    return {
        "verdict": blob.get("verdict"),
        "gate_decision": blob.get("gate_decision"),
        "findings": blob.get("findings") or [],
        "structural": stage_results.get("structural") or dict(_NOT_APPLICABLE),
        "semantic": stage_results.get("semantic") or dict(_NOT_APPLICABLE),
        "provenance": blob,
    }


def grade_signature(
    ontology: Any, *, assignments: Any, models: Any, council_config: Any
) -> str:
    """A stable ``sha256`` over the grade-DETERMINING config: the ontology + the AUTHORED
    (pre-default) per-role ``assignments``/``models`` + the ``council_config``. Stamped on
    each persisted version and recomputed at replay-resolve; a mismatch means the config
    drifted since the head was graded (the freshness guard's input).

    Hashing the authored (not full-lens-defaulted) assignments keeps grade-time and
    resolve-time in agreement: the full-lens default is derived from the ontology + roster,
    and the ontology is already in the hash, so excluding the derived default is safe.
    """
    payload = {
        "ontology": ontology,
        "assignments": assignments,
        "models": models,
        "council_config": council_config,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def is_fresh(head: dict, current_signature: str) -> bool:
    """The freshness predicate — DRIFT-AWARE default (PERSIST-2a Decision 1): a head is
    fresh iff it carries a grade signature equal to the current config's. An un-signed head
    is never fresh. Swap this one function for pure-cache (``return True``) or no-cache
    (``return False``) once the owner settles the policy."""
    sig = head.get("grade_signature")
    return bool(sig) and sig == current_signature
