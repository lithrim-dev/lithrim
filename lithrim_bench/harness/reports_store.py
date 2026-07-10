"""The per-case grade result (``reports``) in the single linked SSOT — PERSIST-3a slice 2.

A grade result stops being a loose ``out/<case>.json`` blob + a ``ws0.sqlite`` ``records`` row
and becomes a row in the one SSOT DB (``LITHRIM_DB_URL`` → Postgres, else local SQLite), scoped
by ``workspace_id``. The blob+projection shape the user asked for:

    reports(workspace_id, case_id, run_id, verdict, scores, report, storage_ref, created_at)
            PK(workspace_id, case_id)

``report`` carries the full record as linked JSON; the small **projected** columns ``verdict``
(the grounded/final verdict), ``run_id`` and ``scores`` (calibration) are queryable WITHOUT
parsing the blob. ``storage_ref`` is RESERVED for the 3b object-store move (the blob relocates
to a per-workspace bucket, the row + key stay) — always NULL in 3a.

The projection reads ``run_eval.build_record`` shape defensively (``.get`` chains) so a partial
record degrades to NULLs rather than raising. Routed through ``db.connect`` / ``config_db_url``
— one DB selector for the whole plane. Stdlib + the db layer only.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of


def _schema(dialect: Any) -> str:
    return (
        "CREATE TABLE IF NOT EXISTS reports (\n"
        "    workspace_id TEXT NOT NULL,\n"
        "    case_id      TEXT NOT NULL,\n"
        "    run_id       TEXT,\n"
        "    verdict      TEXT,\n"
        f"    scores       {dialect.json_type},\n"
        f"    report       {dialect.json_type},\n"
        "    storage_ref  TEXT,\n"
        "    created_at   TEXT NOT NULL,\n"
        "    PRIMARY KEY (workspace_id, case_id)\n"
        ")"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scope(db_path: str | Path | None, workspace_id: str | None) -> str:
    return workspace_id if workspace_id is not None else workspace_id_of(db_path)


def _project(record: dict[str, Any]) -> tuple[str | None, str | None, Any]:
    """The small queryable columns lifted out of a grade record: the GROUNDED (final, post-
    grounding) verdict — falling back to the composite verdict — the run id, and the calibration
    ``scores``. Defensive ``.get`` chains: a partial record yields NULLs, never an exception."""
    grounded = record.get("grounded") or {}
    composite = record.get("composite") or {}
    verdict = grounded.get("verdict") or composite.get("verdict")
    run_id = ((record.get("result") or {}).get("provenance") or {}).get("pipeline_run_id")
    return verdict, run_id, record.get("calibration")


def save_report(
    case_id: str,
    record: dict[str, Any],
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> str:
    """Upsert one grade result into the SSOT (idempotent on ``(workspace_id, case_id)`` — a
    re-grade overwrites, never duplicates). The full record rides inline in ``report``; the
    projected ``verdict``/``run_id``/``scores`` are lifted out; ``storage_ref`` stays NULL (3a)."""
    wsid = _scope(db_path, workspace_id)
    verdict, run_id, scores = _project(record)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        conn.execute(
            "INSERT INTO reports "
            "(workspace_id, case_id, run_id, verdict, scores, report, storage_ref, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, ?) "
            "ON CONFLICT(workspace_id, case_id) DO UPDATE SET "
            "run_id=excluded.run_id, verdict=excluded.verdict, scores=excluded.scores, "
            "report=excluded.report",
            (
                wsid,
                case_id,
                run_id,
                verdict,
                conn.dialect.encode_json(scores),
                conn.dialect.encode_json(record),
                _now(),
            ),
        )
    return config_db_url(db_path)


def load_report(
    case_id: str,
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any] | None:
    """The full grade record for ``(workspace_id, case_id)``, or ``None``."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        row = conn.execute(
            "SELECT report FROM reports WHERE workspace_id = ? AND case_id = ?", (wsid, case_id)
        ).fetchone()
        return conn.dialect.decode_json(row[0]) if row is not None else None


def rebuild_projection(
    *,
    run_history_db: str | Path,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> int:
    """Reconstruct the ``reports`` projection from the run-history alone (SPEC §2: the
    projection is a DERIVED view, rebuildable from ``pipeline_runs``; it is never the trail
    of record). Reads every run blob from the append-only run-history at ``run_history_db``,
    keeps the LATEST blob per ``(workspace_id, case_id)``, and ``save_report``s each into the
    projection at ``db_path``. Idempotent via ``save_report``'s UPSERT.

    "Latest" = the run-history's own newest-first order (``list_all`` returns blobs ordered by
    ``created_at`` then insertion order, newest-first); since the history is append-only
    (post-RUNTRAIL-1, distinct ``pipeline_run_id`` per run), the FIRST blob seen per case is
    the most recent. Each blob projects into its own ``workspace_id`` (the blob field, falling
    back to the rebuild's resolved scope when the blob carries none). Returns the number of
    cases written. The grade-time inline ``save_report`` is untouched; this adds the rebuild
    path beside it."""
    from lithrim_bench.runtime.pipeline.provenance import SqliteProvenanceStore  # lazy: no cycle

    default_wsid = _scope(db_path, workspace_id)
    blobs = asyncio.run(SqliteProvenanceStore(db_path=run_history_db).list_all())

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for blob in blobs:  # newest-first → first seen per key is the latest
        case_id = blob.get("case_id")
        if case_id is None:
            continue
        wsid = blob.get("workspace_id") or default_wsid
        key = (wsid, case_id)
        if key not in latest:
            latest[key] = blob

    for (wsid, case_id), blob in latest.items():
        save_report(case_id, blob, db_path=db_path, workspace_id=wsid)
    return len(latest)


def list_reports(
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Every report in the workspace, oldest-first, as the projection (no blob parse needed):
    ``{case_id, run_id, verdict, scores, created_at}``."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        rows = conn.execute(
            "SELECT case_id, run_id, verdict, scores, created_at FROM reports "
            "WHERE workspace_id = ? ORDER BY created_at, case_id",
            (wsid,),
        ).fetchall()
        return [
            {
                "case_id": cid,
                "run_id": run_id,
                "verdict": verdict,
                "scores": conn.dialect.decode_json(scores),
                "created_at": created,
            }
            for cid, run_id, verdict, scores, created in rows
        ]
