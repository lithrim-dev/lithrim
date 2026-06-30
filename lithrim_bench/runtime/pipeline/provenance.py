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

    async def save_blob(self, doc: dict) -> None:
        """Persist an already-built provenance blob DICT (the run_eval persist/enrich helpers
        carry a dict, not a model) — versioned like :meth:`save`. PERSIST-2c-2: the backend-
        agnostic blob seam so the grade path routes through the factory, not PIPELINE_RUNS."""
        return None

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        return None

    async def latest_for(self, agent_id: str, case_id: str) -> dict | None:
        """The head (most-recent) version blob for a ``(agent, case_id)`` lineage."""
        return None

    async def latest_authoritative_for(self, agent_id: str, case_id: str) -> dict | None:
        """RUNTRAIL-1: the most-recent AUTHORITATIVE (``replay_of`` falsy) blob for a
        ``(agent, case_id)`` lineage — the replay-lineage baseline."""
        return None

    async def list_versions(self, agent_id: str, case_id: str) -> list[dict]:
        """All version blobs for a ``(agent, case_id)`` lineage, newest-first."""
        return []

    async def list_all(self, *, limit: int | None = None) -> list[dict]:
        """All persisted run blobs, newest-first — the run-history list (S-BS-52). PERSIST-2c-2:
        the backend-agnostic read so the BFF run-history/audit reflect the active backend."""
        return []

    async def list_history(self, pipeline_run_id: str) -> list[dict]:
        """RUNTRAIL-2 / SPEC §7 G4: the archived prior versions for a ``pipeline_run_id``,
        newest-first — read-back parity at the store interface. Archival already exists
        (the ``versioned=True`` copy-on-write); this surfaces it so a same-id re-save's
        prior is recoverable through the store, not just via raw SQL."""
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

    async def list_all(self, *, limit: int | None = None) -> list[dict]:
        return []

    async def list_history(self, pipeline_run_id: str) -> list[dict]:
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

    async def save_blob(self, doc: dict) -> None:
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        try:
            PIPELINE_RUNS.insert(dict(doc), db_path=self._db_path or DEFAULT_COLLECTIONS_DB)
        except Exception:
            logger.exception(
                "pipeline_provenance_blob_write_failed",
                extra={"pipeline_run_id": (doc or {}).get("pipeline_run_id")},
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

    async def latest_authoritative_for(self, agent_id: str, case_id: str) -> dict | None:
        """RUNTRAIL-1: the most-recent AUTHORITATIVE (in_process/live) blob for a
        ``(agent, case_id)`` lineage — i.e. the newest version whose ``replay_of`` is falsy.

        This is the replay-LINEAGE baseline (distinct from ``latest_for``, the freshness
        head). Once replays append their own rows (append-with-lineage), the head becomes a
        replay; resolving the lineage baseline to the newest authoritative grade keeps every
        replay's ``replay_of`` pointing at the REAL grade rather than chaining replay→replay
        (driver §4 decision). Returns None when no authoritative grade exists yet."""
        for v in await self.list_versions(agent_id, case_id):
            if not v.get("replay_of"):
                return v
        return None

    async def list_all(self, *, limit: int | None = None) -> list[dict]:
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        return PIPELINE_RUNS.list_all(db_path=self._db_path or DEFAULT_COLLECTIONS_DB, limit=limit)

    async def list_history(self, pipeline_run_id: str) -> list[dict]:
        """RUNTRAIL-2 / G4: the archived prior versions of ``pipeline_run_id`` (the
        ``pipeline_runs_history`` shadow), newest-first — read-back parity for the
        versioned copy-on-write archive. Read-only; the archival write path is unchanged."""
        from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB, PIPELINE_RUNS

        return PIPELINE_RUNS.history(
            pipeline_run_id, db_path=self._db_path or DEFAULT_COLLECTIONS_DB
        )


def rehydrate(pipeline_run_id: str, *, db_path: str | Path | None = None) -> dict:
    """RUNTRAIL-4 / SPEC §4 + §7 G6: reconstruct a graded result from the stored run blob
    ALONE — no live model call, no re-grade. The named entrypoint over the existing
    ``find_by_id`` (the immutable audit blob) + ``provenance_to_result`` (the pure
    blob→result adapter above the frozen seam) pieces, proving the record is self-sufficient
    (§3): a stored blob suffices to reconstruct its verdict.

    Resolves the store via the same ``provenance_store_for`` precedence the grade path uses
    (``LITHRIM_DB_URL`` → Postgres, else the local SQLite ``db_path``) and the same
    ``run_coro`` sync-bridge. Raises ``LookupError`` when the run id is absent. The adapter
    import is lazy to keep ``provenance`` ↔ ``harness.replay`` cycle-free. $0 by construction.
    """
    from lithrim_bench.harness.backend import provenance_store_for, run_coro

    store = provenance_store_for(db_path)
    blob = run_coro(store.find_by_id(pipeline_run_id))
    if blob is None:
        raise LookupError(f"no run-history record for pipeline_run_id={pipeline_run_id!r}")

    from lithrim_bench.harness.replay import provenance_to_result

    return provenance_to_result(blob)


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

    # The Postgres schema (idempotent self-provision, mirroring the SQLite doc-shim posture;
    # yoyo migrations are the managed-tier schema source, this is the defensive fallback).
    # ``ins_seq`` gives a monotonic insertion order (the analogue of SQLite ``rowid``) for the
    # newest-first lineage query; ``created_at`` is first-write-wins (kept on UPDATE).
    _SCHEMA: tuple[str, ...] = (
        "CREATE TABLE IF NOT EXISTS pipeline_runs ("
        " id TEXT PRIMARY KEY, org_id TEXT, agent_id TEXT, case_id TEXT,"
        " doc JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        " ins_seq BIGSERIAL)",
        "CREATE TABLE IF NOT EXISTS pipeline_runs_history ("
        " hist_id BIGSERIAL PRIMARY KEY, original_id TEXT NOT NULL, txnid TEXT, seq INT,"
        " doc JSONB NOT NULL, created_at TIMESTAMPTZ, archived_at TIMESTAMPTZ NOT NULL DEFAULT now())",
        "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_lineage ON pipeline_runs(agent_id, case_id)",
        "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_history_orig ON pipeline_runs_history(original_id)",
    )

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self):
        import psycopg  # lazy — the [pg] extra; never imported by the stdlib core

        return psycopg.connect(self._dsn)

    async def save(
        self, provenance: Any, *, agent_id: str | None = None, case_id: str | None = None
    ) -> None:
        doc: dict = provenance.model_dump(mode="json")
        if agent_id is not None:
            doc["agent_id"] = agent_id
        if case_id is not None:
            doc["case_id"] = case_id
        await self.save_blob(doc)

    async def save_blob(self, doc: dict) -> None:
        from psycopg.types.json import Jsonb

        doc = dict(doc)
        run_id = str(doc["pipeline_run_id"])
        try:
            with self._connect() as conn:
                for stmt in self._SCHEMA:
                    conn.execute(stmt)
                prior = conn.execute(
                    "SELECT created_at, doc FROM pipeline_runs WHERE id = %s", (run_id,)
                ).fetchone()
                if prior is not None:
                    seq = conn.execute(
                        "SELECT count(*) FROM pipeline_runs_history WHERE original_id = %s",
                        (run_id,),
                    ).fetchone()[0] + 1
                    conn.execute(
                        "INSERT INTO pipeline_runs_history "
                        "(original_id, txnid, seq, doc, created_at) VALUES (%s, %s, %s, %s, %s)",
                        (run_id, f"{run_id}#{seq}", seq, Jsonb(prior[1]), prior[0]),
                    )
                    # first-write-wins: keep created_at, update the doc + the lineage columns
                    conn.execute(
                        "UPDATE pipeline_runs SET doc=%s, org_id=%s, agent_id=%s, case_id=%s "
                        "WHERE id=%s",
                        (Jsonb(doc), doc.get("org_id"), doc.get("agent_id"), doc.get("case_id"),
                         run_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO pipeline_runs (id, org_id, agent_id, case_id, doc) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (run_id, doc.get("org_id"), doc.get("agent_id"), doc.get("case_id"),
                         Jsonb(doc)),
                    )
        except Exception:  # fire-and-forget parity with the SQLite store
            logger.exception(
                "pipeline_provenance_pg_write_failed",
                extra={"pipeline_run_id": run_id},
            )

    async def find_by_id(self, pipeline_run_id: str) -> dict | None:
        with self._connect() as conn:
            for stmt in self._SCHEMA:
                conn.execute(stmt)
            row = conn.execute(
                "SELECT doc FROM pipeline_runs WHERE id = %s", (pipeline_run_id,)
            ).fetchone()
        return row[0] if row else None  # psycopg returns JSONB already parsed

    async def list_versions(self, agent_id: str, case_id: str) -> list[dict]:
        with self._connect() as conn:
            for stmt in self._SCHEMA:
                conn.execute(stmt)
            rows = conn.execute(
                "SELECT doc FROM pipeline_runs WHERE agent_id = %s AND case_id = %s "
                "ORDER BY ins_seq DESC",
                (agent_id, case_id),
            ).fetchall()
        return [r[0] for r in rows]

    async def latest_for(self, agent_id: str, case_id: str) -> dict | None:
        versions = await self.list_versions(agent_id, case_id)
        return versions[0] if versions else None

    async def latest_authoritative_for(self, agent_id: str, case_id: str) -> dict | None:
        """RUNTRAIL-1 parity: the most-recent ``replay_of``-falsy blob for the lineage."""
        for v in await self.list_versions(agent_id, case_id):
            if not v.get("replay_of"):
                return v
        return None

    async def list_all(self, *, limit: int | None = None) -> list[dict]:
        sql = "SELECT doc FROM pipeline_runs ORDER BY ins_seq DESC"
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT %s"
            params = (limit,)
        with self._connect() as conn:
            for stmt in self._SCHEMA:
                conn.execute(stmt)
            rows = conn.execute(sql, params).fetchall()
        return [r[0] for r in rows]

    async def list_history(self, pipeline_run_id: str) -> list[dict]:
        """RUNTRAIL-2 / G4 parity: the archived prior versions of ``pipeline_run_id`` from
        ``pipeline_runs_history``, newest-first (``seq DESC``) — read-back of the same
        versioned copy-on-write archive the SQLite tier exposes. Read-only."""
        with self._connect() as conn:
            for stmt in self._SCHEMA:
                conn.execute(stmt)
            rows = conn.execute(
                "SELECT doc FROM pipeline_runs_history WHERE original_id = %s "
                "ORDER BY seq DESC",
                (pipeline_run_id,),
            ).fetchall()
        return [r[0] for r in rows]
