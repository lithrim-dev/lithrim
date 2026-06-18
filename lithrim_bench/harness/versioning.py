"""Config-object versioning — the etlp-mapper ``live + _history`` copy-on-write pattern
for the table-backed config plane (PERSIST-2b).

The ``config_audit`` ledger is the why/when/who change-stream; this module is the
*"prove what the config WAS"* object-version timeline:

  * :func:`archive_prior` — copy-on-write: on a write that replaces a config row, snapshot
    the prior row into a ``{table}_history`` shadow (preserving first-write ``created_at``),
    in the caller's transaction. Portable Python (no SQLite trigger), runs the same on PG
    later — mirrors 2a's ``pipeline_runs_history``.
  * :func:`list_versions` / :func:`version_at` — the read API over the live head + the
    ``_history`` shadow (table-backed: agent / judge).
  * :func:`ledger_history` — the read API for the file-backed ``ontology`` (no table to
    shadow): a projection of the immutable ``config_audit`` ``after``-snapshots.

Stdlib ``sqlite3`` only.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def _history_table(table: str) -> str:
    return f"{table}_history"


def _history_schema(table: str) -> str:
    h = _history_table(table)
    return (
        f"CREATE TABLE IF NOT EXISTS {h} (\n"
        "    hist_id     INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    original_id TEXT NOT NULL,\n"
        "    txnid       TEXT NOT NULL,\n"
        "    seq         INTEGER NOT NULL,\n"
        "    json        TEXT NOT NULL,\n"
        "    created_at  TEXT NOT NULL,\n"
        "    archived_at TEXT NOT NULL\n"
        ");\n"
        f"CREATE INDEX IF NOT EXISTS idx_{h}_orig ON {h}(original_id)"
    )


def archive_prior(conn: Any, *, table: str, id_col: str, id_val: str, archived_at: str) -> None:
    """In the caller's transaction: if a row for ``id_val`` exists in ``table``, snapshot its
    ``(json, created_at)`` into ``{table}_history`` with a monotonic ``seq`` + a ``txnid``
    surrogate, ``created_at`` PRESERVED. No-op on the first write (nothing to archive)."""
    h = _history_table(table)
    conn.executescript(_history_schema(table))
    prior = conn.execute(
        f"SELECT json, created_at FROM {table} WHERE {id_col} = ?", (id_val,)
    ).fetchone()
    if prior is None:
        return
    prior_json, prior_created = prior
    seq = conn.execute(
        f"SELECT COUNT(*) FROM {h} WHERE original_id = ?", (id_val,)
    ).fetchone()[0] + 1
    conn.execute(
        f"INSERT INTO {h} (original_id, txnid, seq, json, created_at, archived_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (id_val, f"{archived_at}#{seq}", seq, prior_json, prior_created, archived_at),
    )


def list_versions(db_path: str | Path, *, table: str, id_col: str, id_val: str) -> list[dict]:
    """The version timeline for a table-backed config object, newest-first: the live head
    (``version = len(history)+1``, ``status='current'``) followed by every ``_history`` row
    (``status='superseded'``). ``[]`` when the id is unknown (no head, no history)."""
    conn = sqlite3.connect(Path(db_path))
    try:
        conn.executescript(_history_schema(table))
        try:
            live = conn.execute(
                f"SELECT json, created_at FROM {table} WHERE {id_col} = ?", (id_val,)
            ).fetchone()
        except sqlite3.OperationalError:  # the live table itself has never been created
            live = None
        hist = conn.execute(
            f"SELECT seq, json, created_at, archived_at FROM {_history_table(table)} "
            "WHERE original_id = ? ORDER BY seq",
            (id_val,),
        ).fetchall()
    finally:
        conn.close()
    if live is None and not hist:
        return []
    versions: list[dict] = []
    if live is not None:
        versions.append(
            {
                "version": len(hist) + 1,
                "status": "current",
                "object": json.loads(live[0]),
                "created_at": live[1],
                "archived_at": None,
            }
        )
    for seq, j, created, archived in reversed(hist):  # newest superseded first
        versions.append(
            {
                "version": seq,
                "status": "superseded",
                "object": json.loads(j),
                "created_at": created,
                "archived_at": archived,
            }
        )
    return versions


def version_at(
    db_path: str | Path, *, table: str, id_col: str, id_val: str, version: int
) -> dict | None:
    """The object dict at a specific version (the head when ``version == len(history)+1``,
    else the ``_history`` row ``seq=version``). ``None`` when the version does not exist."""
    conn = sqlite3.connect(Path(db_path))
    try:
        conn.executescript(_history_schema(table))
        n = conn.execute(
            f"SELECT COUNT(*) FROM {_history_table(table)} WHERE original_id = ?", (id_val,)
        ).fetchone()[0]
        if version == n + 1:
            try:
                live = conn.execute(
                    f"SELECT json FROM {table} WHERE {id_col} = ?", (id_val,)
                ).fetchone()
            except sqlite3.OperationalError:
                live = None
            return json.loads(live[0]) if live else None
        row = conn.execute(
            f"SELECT json FROM {_history_table(table)} WHERE original_id = ? AND seq = ?",
            (id_val, version),
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def ledger_history(db_path: str | Path, *, target_type: str, target_id: str) -> list[dict]:
    """The file-backed / ledger version timeline (for ``ontology``, which has no table to
    shadow): each ``config_audit`` record's ``after`` is a version, newest-first, carrying
    the ledger's ``ts``/``actor``/``action``. ``[]`` when the target has no records."""
    from lithrim_bench.harness.audit import AuditLog

    records = AuditLog(db_path=db_path).query(target_type=target_type, target_id=target_id)
    out: list[dict] = []
    n = len(records)
    for i, rec in enumerate(reversed(records)):  # newest-first
        out.append(
            {
                "version": n - i,  # 1-based, chronological
                "status": "current" if i == 0 else "superseded",
                "object": rec.get("after"),
                "ts": rec.get("ts"),
                "actor": rec.get("actor"),
                "action": rec.get("action"),
            }
        )
    return out
