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
