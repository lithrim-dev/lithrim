"""The cases corpus in the single linked SSOT — PERSIST-3a slice 1.

A case stops being a line in a loose ``ingested_cases.jsonl`` file and becomes a row in the
one source-of-truth DB (``LITHRIM_DB_URL`` → Postgres, else local SQLite — the SAME selector
as the config plane and the run blobs), scoped by ``workspace_id`` and carrying its content as
linked JSON:

    cases(workspace_id, case_id, source, payload, storage_ref, created_at)   PK(workspace_id, case_id)

``payload`` holds the case inline (JSONB on Postgres, canonical TEXT on SQLite). ``storage_ref``
is RESERVED for the object-store move (PERSIST-3b): the link is the row + its key, so the bytes
can later relocate to a per-workspace bucket without breaking it; in 3a it is always NULL.

Routed through ``db.connect`` / ``db.config_db_url`` so the whole thing follows the one DB
selector. ``workspace_id`` is derived from the per-workspace ``db_path`` (``workspace_id_of``)
unless passed explicitly (the BFF passes the active workspace name; tests pass a fixed scope).
Stdlib + the existing db layer only — no council/dspy import.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of


def _schema(dialect: Any) -> str:
    return (
        "CREATE TABLE IF NOT EXISTS cases (\n"
        "    workspace_id TEXT NOT NULL,\n"
        "    case_id      TEXT NOT NULL,\n"
        "    source       TEXT,\n"
        f"    payload      {dialect.json_type},\n"
        "    storage_ref  TEXT,\n"
        "    created_at   TEXT NOT NULL,\n"
        "    PRIMARY KEY (workspace_id, case_id)\n"
        ")"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scope(db_path: str | Path | None, workspace_id: str | None) -> str:
    return workspace_id if workspace_id is not None else workspace_id_of(db_path)


def save_case(
    case_id: str,
    payload: dict[str, Any],
    *,
    source: str = "ingested",
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> str:
    """Upsert one case into the SSOT (idempotent on ``(workspace_id, case_id)`` — a re-ingest
    overwrites, never duplicates). Content rides inline in ``payload``; ``storage_ref`` stays
    NULL (3a). Returns the resolved backend url. ``created_at`` is set on first write."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        conn.execute(
            "INSERT INTO cases (workspace_id, case_id, source, payload, storage_ref, created_at) "
            "VALUES (?, ?, ?, ?, NULL, ?) "
            "ON CONFLICT(workspace_id, case_id) DO UPDATE SET "
            "payload=excluded.payload, source=excluded.source",
            (wsid, case_id, source, conn.dialect.encode_json(payload), _now()),
        )
    return config_db_url(db_path)


def load_case_row(
    case_id: str,
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any] | None:
    """The case payload for ``(workspace_id, case_id)``, or ``None`` if absent. (3a reads inline
    ``payload``; the 3b ``storage_ref`` fetch is added with the object-store mover.)"""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        row = conn.execute(
            "SELECT payload FROM cases WHERE workspace_id = ? AND case_id = ?", (wsid, case_id)
        ).fetchone()
        return conn.dialect.decode_json(row[0]) if row is not None else None


def list_cases(
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Every case in the workspace, oldest-first: ``{case_id, source, payload, created_at}``."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        rows = conn.execute(
            "SELECT case_id, source, payload, created_at FROM cases "
            "WHERE workspace_id = ? ORDER BY created_at, case_id",
            (wsid,),
        ).fetchall()
        return [
            {
                "case_id": cid,
                "source": src,
                "payload": conn.dialect.decode_json(payload),
                "created_at": created,
            }
            for cid, src, payload, created in rows
        ]
