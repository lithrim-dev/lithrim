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

# NOTE (PERSIST-2a, RED scaffold): the bodies below are stubs so the acceptance tests
# import-and-fail on assertions. The GREEN implementation replaces each.


def provenance_to_result(blob: dict) -> dict:
    raise NotImplementedError


def grade_signature(ontology, *, assignments, models, council_config) -> str:
    raise NotImplementedError


def is_fresh(head: dict, current_signature: str) -> bool:
    raise NotImplementedError
