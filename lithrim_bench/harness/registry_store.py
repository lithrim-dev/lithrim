"""The workspaces registry in the single SSOT — PERSIST-3a slice 3.

The workspace MANIFEST stops being a ``WORKSPACES_DIR/<name>/workspace.json`` file and the active
pointer stops being a ``.active`` file: both become rows in the one SSOT DB (``LITHRIM_DB_URL`` →
Postgres, else a GLOBAL ``registry.sqlite``):

    workspaces(workspace_id, manifest, created_at)   PK(workspace_id)
    active_workspace(k, workspace_id)                k='active' singleton

This table is GLOBAL (it IS the workspace list) — unlike ``cases``/``reports`` it is NOT
``workspace_id``-scoped; ``workspace_id`` is its PRIMARY KEY. The manifest is small metadata, so
there is no ``storage_ref`` (it never moves to object storage). The per-workspace DIR still exists
for the SQLite-mode config/collections files + ontology drafts; only the registry moves here.

``workspace.py`` reads DB-FIRST and falls back to the legacy files, and dual-writes both during the
transition — so an EMPTY registry behaves byte-identically to pre-3a. Routed through ``db.connect``
/ ``config_db_url`` (one DB selector). Stdlib + the db layer only — no import of ``workspace``
(``workspace`` passes the registry db path in; avoids the import cycle)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lithrim_bench.harness.db import config_db_url, connect

_ACTIVE_KEY = "active"


def _workspaces_schema(dialect: Any) -> str:
    return (
        "CREATE TABLE IF NOT EXISTS workspaces (\n"
        "    workspace_id TEXT PRIMARY KEY,\n"
        f"    manifest     {dialect.json_type},\n"
        "    created_at   TEXT NOT NULL\n"
        ")"
    )


def _active_schema() -> str:
    return (
        "CREATE TABLE IF NOT EXISTS active_workspace (\n"
        "    k            TEXT PRIMARY KEY,\n"
        "    workspace_id TEXT NOT NULL\n"
        ")"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_workspace(workspace_id: str, manifest: dict[str, Any], *, db_path: str | Path | None) -> None:
    """Upsert one workspace manifest (idempotent on ``workspace_id``; first-write ``created_at``)."""
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_workspaces_schema(conn.dialect))
        conn.execute(
            "INSERT INTO workspaces (workspace_id, manifest, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(workspace_id) DO UPDATE SET manifest=excluded.manifest",
            (workspace_id, conn.dialect.encode_json(manifest), _now()),
        )


def load_workspace(workspace_id: str, *, db_path: str | Path | None) -> dict[str, Any] | None:
    """The manifest dict for ``workspace_id``, or ``None`` if not in the registry."""
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_workspaces_schema(conn.dialect))
        row = conn.execute(
            "SELECT manifest FROM workspaces WHERE workspace_id = ?", (workspace_id,)
        ).fetchone()
        return conn.dialect.decode_json(row[0]) if row is not None else None


def list_workspace_ids(*, db_path: str | Path | None) -> list[str]:
    """Every registered workspace id (sorted)."""
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_workspaces_schema(conn.dialect))
        rows = conn.execute("SELECT workspace_id FROM workspaces ORDER BY workspace_id").fetchall()
    return [r[0] for r in rows]


def set_active(workspace_id: str, *, db_path: str | Path | None) -> None:
    """Point the active-workspace singleton at ``workspace_id`` (moves, never duplicates)."""
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_active_schema())
        conn.execute(
            "INSERT INTO active_workspace (k, workspace_id) VALUES (?, ?) "
            "ON CONFLICT(k) DO UPDATE SET workspace_id=excluded.workspace_id",
            (_ACTIVE_KEY, workspace_id),
        )


def get_active(*, db_path: str | Path | None) -> str | None:
    """The active workspace id, or ``None`` if the singleton was never set."""
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_active_schema())
        row = conn.execute(
            "SELECT workspace_id FROM active_workspace WHERE k = ?", (_ACTIVE_KEY,)
        ).fetchone()
    return row[0] if row is not None else None
