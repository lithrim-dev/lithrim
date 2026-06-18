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
    async def save(
        self, provenance: Any, *, agent_id: str | None = None, case_id: str | None = None
    ) -> None:
        return None

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        return None

    async def latest_for(self, agent_id: str, case_id: str) -> dict | None:
        """The head (most-recent) version blob for a ``(agent, case_id)`` lineage."""
        return None

    async def list_versions(self, agent_id: str, case_id: str) -> list[dict]:
        """All version blobs for a ``(agent, case_id)`` lineage, newest-first."""
        return []


class NoOpProvenanceStore(ProvenanceStore):
    async def save(
        self, provenance: Any, *, agent_id: str | None = None, case_id: str | None = None
    ) -> None:
        return None

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        return None

    async def latest_for(self, agent_id: str, case_id: str) -> dict | None:
        return None

    async def list_versions(self, agent_id: str, case_id: str) -> list[dict]:
        return []


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
    (mirrors the backend provenance store's fail-soft ``save``). ``kb_retrievals``
    persists as the existing 4-field summary; no expansion (KB is WS-6d-KB).

    The doc-shim import is **lazy** (inside the methods) to avoid the
    ``harness/__init__ -> grade`` import cycle, the same posture as the backend
    store's lazy ``get_database`` resolution.
    """

    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self._db_path = db_path

    async def save(
        self, provenance: Any, *, agent_id: str | None = None, case_id: str | None = None
    ) -> None:
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        try:
            doc: dict = provenance.model_dump(mode="json")
            if agent_id is not None:
                doc["agent_id"] = agent_id
            if case_id is not None:
                doc["case_id"] = case_id
            PIPELINE_RUNS.insert(doc, db_path=self._db_path or DEFAULT_COLLECTIONS_DB)
        except Exception:
            logger.exception(
                "pipeline_provenance_write_failed",
                extra={"pipeline_run_id": getattr(provenance, "pipeline_run_id", None)},
            )

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        return PIPELINE_RUNS.get(pipeline_run_id, db_path=self._db_path or DEFAULT_COLLECTIONS_DB)

    async def list_versions(self, agent_id: str, case_id: str) -> list[dict]:
        """All persisted run blobs for a ``(agent, case_id)`` lineage, newest-first —
        the calibration history. A ``json_extract`` query over the live ``PIPELINE_RUNS``
        table (append-only across distinct ``pipeline_run_id`` rows), no indexed column."""
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        return PIPELINE_RUNS.find_by_json(
            {"agent_id": agent_id, "case_id": case_id},
            db_path=self._db_path or DEFAULT_COLLECTIONS_DB,
        )

    async def latest_for(self, agent_id: str, case_id: str) -> dict | None:
        """The head (most-recent) version blob for a ``(agent, case_id)`` lineage — the
        replay-from-provenance baseline."""
        versions = await self.list_versions(agent_id, case_id)
        return versions[0] if versions else None


class PostgresProvenanceStore(ProvenanceStore):
    """The managed/VPC-tier ProvenanceStore (PERSIST-2c, plugin ``tier: pro``).

    A PARALLEL impl behind the same ``ProvenanceStore`` Protocol — the S-BS-38 "PG/Aurora
    drops in behind this same interface" promise realized — persisting the run blob into a
    Postgres ``pipeline_runs`` (JSONB) + ``pipeline_runs_history`` schema with the SAME
    versioned copy-on-write semantics as the SQLite tier. ``psycopg`` is imported lazily
    (the ``[pg]`` extra), so this class is importable on the stdlib core; only USING it
    needs the driver + a reachable Postgres (``LITHRIM_DB_URL=postgresql://…``).

    Contract-shaped + SQLite-proven: the shared ``run_provenance_contract`` runs the SAME
    assertions against SQLite (always) and this store (skipped unless a live PG is
    configured). Honesty bar: this path is not CI-live-verified offline — the gated
    contract test is its proof.
    """

    # RED scaffold — GREEN implements the psycopg-backed versioned blob store.
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save(
        self, provenance: Any, *, agent_id: str | None = None, case_id: str | None = None
    ) -> None:
        raise NotImplementedError

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        raise NotImplementedError

    async def list_versions(self, agent_id: str, case_id: str) -> list[dict]:
        raise NotImplementedError

    async def latest_for(self, agent_id: str, case_id: str) -> dict | None:
        raise NotImplementedError
