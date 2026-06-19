"""The backend-agnostic DB-access layer — PERSIST-2c-3 (the config-plane single SSOT).

ONE ``connect()`` + ``Dialect`` so EVERY persistence module (the doc-shim collections, the
``agents``/``judges`` config tables, the ``config_audit`` ledger, the ``_history`` shadows)
follows ``LITHRIM_DB_URL``: SQLite (the offline OSS default) OR Postgres (the managed tier,
the ``[pg]`` extra). The ProvenanceStore (run blobs) already routes through the same
``LITHRIM_DB_URL`` via its own factory; this adds the config plane to the SAME selection, so
there is exactly ONE source-of-truth DB at a time — no split between run blobs and config.

``psycopg`` is imported lazily (the ``[pg]`` extra) — the SQLite path stays stdlib-only + offline.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from lithrim_bench.harness.backend import (
    Dialect,
    backend_of,
    resolve_db_url,
    sqlite_path_of,
)


def config_db_url(local_path: str | Path | None = None) -> str:
    """The config-plane backend url: ``LITHRIM_DB_URL`` (the managed Postgres tier) when set,
    else the caller's local SQLite path (the default — byte-identical to before). Mirrors
    ``provenance_store_for`` so the WHOLE persistence plane follows ONE selector."""
    env = os.environ.get("LITHRIM_DB_URL", "").strip()
    return resolve_db_url(env or local_path)


def workspace_id_of(local_path: str | Path | None = None) -> str:
    """The ``workspace_id`` scope derived from a per-workspace db path (PERSIST-3a). A workspace
    is a directory ``<WORKSPACES_DIR>/<name>/`` holding ``config.sqlite`` / ``collections.sqlite``
    / ``out/`` — all DIRECT children of ``<name>/`` — so the parent dir name IS the scope. Under a
    single shared DB (``LITHRIM_DB_URL`` set, the path otherwise ignored) this is what keeps one
    workspace's rows isolated from another's; a non-workspace path (the default global config db,
    a tmp test path) yields its own stable parent name. ``None`` → ``'default'``. Pure path op —
    no import of ``workspace`` (avoids the config→db→workspace cycle)."""
    if local_path is None:
        return "default"
    return Path(local_path).parent.name or "default"


class DbConn:
    """A thin uniform wrapper over a ``sqlite3`` or ``psycopg`` connection.

    ``execute`` takes the bench's ``?``-style SQL and translates ``?``→``%s`` for Postgres
    (the bench's SQL never embeds a literal ``?`` in a string — verified). ``executescript``
    runs a multi-statement string (SQLite-native; per-statement on Postgres). As a context
    manager it commits on clean exit, rolls back on error, and always closes — the same
    transaction discipline both backends get."""

    def __init__(self, raw: Any, backend: str) -> None:
        self._raw = raw
        self.backend = backend
        self.dialect = Dialect(backend)

    def execute(self, sql: str, params: tuple = ()) -> Any:
        if self.backend == "postgres":
            sql = sql.replace("?", "%s")
        return self._raw.execute(sql, params)

    def executescript(self, sql: str) -> None:
        if self.backend == "postgres":
            for stmt in sql.split(";"):
                if stmt.strip():
                    self._raw.execute(stmt)
        else:
            self._raw.executescript(sql)

    def commit(self) -> None:
        self._raw.commit()

    def __enter__(self) -> DbConn:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self._raw.commit()
            else:
                self._raw.rollback()
        finally:
            self._raw.close()


def _has_column(conn: DbConn, table: str, col: str) -> bool:
    if conn.backend == "sqlite":
        return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})").fetchall())
    row = conn.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
        (table, col),
    ).fetchone()
    return row is not None


def _table_exists(conn: DbConn, table: str) -> bool:
    if conn.backend == "sqlite":
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
            ).fetchone()
            is not None
        )
    return (
        conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?", (table,)
        ).fetchone()
        is not None
    )


def migrate_workspace_scope(
    conn: DbConn,
    table: str,
    *,
    new_schema: str,
    copy_cols: list[str],
    key_cols: list[str],
    stamp_workspace_id: str,
    rebuild_pk: bool,
) -> None:
    """Idempotently carry an OLD-shape config table (pre slice-4, no ``workspace_id``) forward.

    No-op when the table is ABSENT (a fresh DB — the caller's ``CREATE … IF NOT EXISTS`` already
    makes it new-shape) or already carries ``workspace_id`` (already migrated). Existing rows are
    stamped with ``stamp_workspace_id`` — the file's OWN workspace (``workspace_id_of(db_path)``),
    NOT a literal 'default', so the scoped reads still see them.

    ``rebuild_pk=True`` (agents / judges): the PK becomes composite ``(workspace_id, *key_cols)``
    so the same name can exist in two workspaces — SQLite rebuilds the table (the only portable PK
    change), Postgres adds the column + swaps the PK. ``rebuild_pk=False`` (config_audit / *_history,
    append-only serial PK): a plain additive column + a one-shot stamp. PERSIST-3a slice 4."""
    if not _table_exists(conn, table) or _has_column(conn, table, "workspace_id"):
        return
    cols = ", ".join(copy_cols)
    if not rebuild_pk:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN workspace_id TEXT")
        conn.execute(
            f"UPDATE {table} SET workspace_id = ? WHERE workspace_id IS NULL", (stamp_workspace_id,)
        )
        return
    if conn.backend == "sqlite":
        # `execute` (NOT executescript) keeps the whole rebuild in ONE transaction — executescript
        # forces an implicit COMMIT, which would land the RENAME before the rows are copied (a
        # crash-only durability gap). Safe here: the rebuild path only ever runs the single-statement
        # agents/judges CREATE; the multi-statement _history schema is the additive path above.
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}__pre3a")
        conn.execute(new_schema)  # recreate `table` new-shape (single CREATE; atomic with the copy)
        conn.execute(
            f"INSERT INTO {table} (workspace_id, {cols}) SELECT ?, {cols} FROM {table}__pre3a",
            (stamp_workspace_id,),
        )
        conn.execute(f"DROP TABLE {table}__pre3a")
    else:  # postgres: add the column, stamp, then swap the PK to composite
        conn.execute(f"ALTER TABLE {table} ADD COLUMN workspace_id TEXT")
        conn.execute(f"UPDATE {table} SET workspace_id = ?", (stamp_workspace_id,))
        conn.execute(f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL")
        conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_pkey")
        conn.execute(f"ALTER TABLE {table} ADD PRIMARY KEY (workspace_id, {', '.join(key_cols)})")


def connect(url: str | Path | None = None) -> DbConn:
    """Open a ``DbConn`` for the resolved backend. SQLite is the default + never gated;
    Postgres lazy-imports ``psycopg`` (the ``[pg]`` extra). Use ``config_db_url(db_path)`` to
    apply the ``LITHRIM_DB_URL``-wins precedence."""
    resolved = resolve_db_url(url)
    if backend_of(resolved) == "postgres":
        import psycopg

        return DbConn(psycopg.connect(resolved), "postgres")
    path = Path(sqlite_path_of(resolved))
    path.parent.mkdir(parents=True, exist_ok=True)
    return DbConn(sqlite3.connect(path), "sqlite")
