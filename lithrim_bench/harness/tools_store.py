"""The per-workspace authored-tools store — TOOL-AUTHOR-1 (Stage 1).

A user-authored tool (an MCP server, an API connector, a KB query, a terminology service) stops
being a maintainer-edited pack ``tools.json`` and becomes a row in the one SSOT DB
(``LITHRIM_DB_URL`` → Postgres, else local SQLite — the SAME selector as the config plane, the
cases corpus, and the run blobs), scoped by ``workspace_id``:

    authored_tools(workspace_id, tool_id, manifest_json, bind_json, created_at)  PK(workspace_id, tool_id)

``manifest_json`` is the ``kind: tool`` :class:`~lithrim_bench.harness.plugins.PluginManifest` as a
dict (NO secrets — the connector key rides env via the existing ``/v1/connector/config`` surface).
``bind_json`` is the OPTIONAL flag-bind ``{flag_code, authority, contract_type, params}`` that wires
the tool into a judge's flag at the grounding plane. Mirrors ``cases_store.py`` exactly; routed
through the shared ``db`` layer so it follows the one DB selector. Per-workspace isolation is the
invariant. Stdlib + the db layer only — no council/dspy import.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of


def _schema(dialect: Any) -> str:
    return (
        "CREATE TABLE IF NOT EXISTS authored_tools (\n"
        "    workspace_id  TEXT NOT NULL,\n"
        "    tool_id       TEXT NOT NULL,\n"
        f"    manifest_json {dialect.json_type},\n"
        f"    bind_json     {dialect.json_type},\n"
        "    created_at    TEXT NOT NULL,\n"
        "    PRIMARY KEY (workspace_id, tool_id)\n"
        ")"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scope(db_path: str | Path | None, workspace_id: str | None) -> str:
    return workspace_id if workspace_id is not None else workspace_id_of(db_path)


def save_tool(
    tool_id: str,
    manifest: dict[str, Any],
    *,
    bind: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> str:
    """Upsert one authored tool into the SSOT (idempotent on ``(workspace_id, tool_id)`` — a
    re-author overwrites, never duplicates). ``manifest`` carries no secrets. Returns the resolved
    backend url. ``created_at`` is set on first write."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        conn.execute(
            "INSERT INTO authored_tools (workspace_id, tool_id, manifest_json, bind_json, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(workspace_id, tool_id) DO UPDATE SET "
            "manifest_json=excluded.manifest_json, bind_json=excluded.bind_json",
            (
                wsid,
                tool_id,
                conn.dialect.encode_json(manifest),
                conn.dialect.encode_json(bind) if bind is not None else None,
                _now(),
            ),
        )
    return config_db_url(db_path)


def load_tool(
    tool_id: str,
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any] | None:
    """The ``{manifest, bind}`` for ``(workspace_id, tool_id)``, or ``None`` if absent."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        row = conn.execute(
            "SELECT manifest_json, bind_json FROM authored_tools "
            "WHERE workspace_id = ? AND tool_id = ?",
            (wsid, tool_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "manifest": conn.dialect.decode_json(row[0]),
            "bind": conn.dialect.decode_json(row[1]) if row[1] is not None else None,
        }


def list_tools(
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Every authored tool in the workspace, oldest-first:
    ``{tool_id, manifest, bind, created_at}``."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        rows = conn.execute(
            "SELECT tool_id, manifest_json, bind_json, created_at FROM authored_tools "
            "WHERE workspace_id = ? ORDER BY created_at, tool_id",
            (wsid,),
        ).fetchall()
        return [
            {
                "tool_id": tid,
                "manifest": conn.dialect.decode_json(manifest),
                "bind": conn.dialect.decode_json(bind) if bind is not None else None,
                "created_at": created,
            }
            for tid, manifest, bind, created in rows
        ]


def delete_tool(
    tool_id: str,
    *,
    db_path: str | Path | None = None,
    workspace_id: str | None = None,
) -> bool:
    """Delete one authored tool. Returns ``True`` if a row was removed, ``False`` if absent."""
    wsid = _scope(db_path, workspace_id)
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_schema(conn.dialect))
        cur = conn.execute(
            "DELETE FROM authored_tools WHERE workspace_id = ? AND tool_id = ?", (wsid, tool_id)
        )
        return (cur.rowcount or 0) > 0
