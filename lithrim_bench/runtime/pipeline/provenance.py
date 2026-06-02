"""Provenance persistence for the in-process pipeline.

``ProvenanceStore`` is the repository interface the orchestrator persists through
(the template is the backend ``app/services/pipeline/provenance.py`` Protocol —
``save`` + ``find_by_id``). ``NoOpProvenanceStore`` drops writes on the floor: the
hermetic default for bare construction and unit tests.

``SqliteProvenanceStore`` (WS-6d) is the real product-path store — it persists each
``PipelineProvenance`` to SQLite via the stdlib ``harness/collections`` doc-shim, so
the product/grade path carries **no Mongo dependency and no new dependency**.
PG/Aurora drops in later behind this same interface (VPC tier, future phase).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProvenanceStore:
    async def save(self, provenance: Any, *, agent_id: str | None = None) -> None:
        return None

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        return None


class NoOpProvenanceStore(ProvenanceStore):
    async def save(self, provenance: Any, *, agent_id: str | None = None) -> None:
        return None

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        return None


class SqliteProvenanceStore(ProvenanceStore):
    """Persist ``PipelineProvenance`` to SQLite via the stdlib doc-shim.

    The in-process pipeline's ``save(provenance)`` seam writes one row per run to
    the ``pipeline_runs`` doc-shim collection, keyed on the run's
    ``pipeline_run_id`` — a fresh ``uuid4`` per ``evaluate()``, so re-running the
    same case writes a **distinct, non-colliding** row, while persisting the same
    ``pipeline_run_id`` twice **upserts** to one row (the doc-shim's idempotent
    ``ON CONFLICT(id) DO UPDATE``). ``agent_id`` is stored as an extra doc field
    (faithful to the backend store), not a ``PipelineProvenance`` field.

    Fail-soft by contract: the call site is fire-and-forget — the evaluation has
    already completed — so a write failure is logged and swallowed, never raised
    (mirrors the backend ``MongoProvenanceStore.save``). ``kb_retrievals`` persists
    as the existing 4-field summary; no expansion (KB is WS-6d-KB).

    The doc-shim import is **lazy** (inside the methods) to avoid the
    ``harness/__init__ -> grade`` import cycle, the same posture as the backend
    store's lazy ``get_database`` resolution.
    """

    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self._db_path = db_path

    async def save(self, provenance: Any, *, agent_id: str | None = None) -> None:
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        try:
            doc: dict = provenance.model_dump(mode="json")
            if agent_id is not None:
                doc["agent_id"] = agent_id
            PIPELINE_RUNS.insert(doc, db_path=self._db_path or DEFAULT_COLLECTIONS_DB)
        except Exception:
            logger.exception(
                "pipeline_provenance_write_failed",
                extra={"pipeline_run_id": getattr(provenance, "pipeline_run_id", None)},
            )

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        return PIPELINE_RUNS.get(pipeline_run_id, db_path=self._db_path or DEFAULT_COLLECTIONS_DB)


# Transitional alias — retired in the next WS-6d commit (the orchestrator default
# moves to NoOpProvenanceStore; the "Mongo" name leaves the product path entirely).
MongoProvenanceStore = NoOpProvenanceStore
