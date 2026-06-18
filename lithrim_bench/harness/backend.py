"""The storage-backend seam — PERSIST-2c (the PG/SQLite adapter split).

The OSS core is stdlib-`sqlite3` + offline by construction; this module is the one place
the backend is chosen, so a managed Postgres tier "drops in behind the same interface"
(the ``ProvenanceStore`` Protocol's standing promise) without the core ever importing a
DB driver:

  * :func:`resolve_db_url` — the ``LITHRIM_DB_URL`` connection string (the etlp ``JDBC_URL``
    analogue); unset → the local SQLite default. :func:`backend_of` classifies it.
  * :class:`Dialect` — the SQL dialect boundary (param style ``?``/``%s``, JSON column
    ``TEXT``/``JSONB``, encode/decode) so one handler can run on either backend.
  * :func:`make_provenance_store` — the factory: a ``SqliteProvenanceStore`` (default,
    100% tested) or a ``PostgresProvenanceStore`` (``[pg]`` extra, tier:pro, license-gated,
    contract-tested).

Stdlib only. ``psycopg``/``yoyo`` are imported lazily inside the Postgres path, never at
module load — the core install stays pydantic+pandas, the SQLite path stays dependency-free.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# The plugin id under which the Postgres provenance store is tier:pro license-gated.
PG_STORE_PLUGIN_ID = "store.postgres_provenance"


def _default_sqlite_url() -> str:
    from lithrim_bench.harness.collections import DEFAULT_COLLECTIONS_DB

    return f"sqlite:///{Path(DEFAULT_COLLECTIONS_DB).resolve()}"


def resolve_db_url(url: str | Path | None = None) -> str:
    """The effective DB url. An explicit ``url`` (str or Path) wins — a bare path / Path
    becomes a ``sqlite:///`` url; a scheme url passes through. ``None`` → ``LITHRIM_DB_URL``
    (the env, the etlp ``JDBC_URL`` analogue) → the local SQLite default."""
    if url is not None:
        if isinstance(url, Path):
            return f"sqlite:///{url.resolve()}"
        if "://" not in url:
            return f"sqlite:///{Path(url).resolve()}"
        return url
    env = os.environ.get("LITHRIM_DB_URL", "").strip()
    return env or _default_sqlite_url()


def backend_of(url: str | Path) -> str:
    """``'postgres'`` | ``'sqlite'`` for a resolved url. A bare path is SQLite."""
    u = str(url)
    if u.startswith("postgres://") or u.startswith("postgresql://"):
        return "postgres"
    if u.startswith("sqlite:") or "://" not in u:
        return "sqlite"
    raise ValueError(f"unsupported db url scheme: {url!r}")


def sqlite_path_of(url: str | Path) -> Path:
    """The filesystem path behind a ``sqlite:///…`` url (or a bare path)."""
    u = str(url)
    for prefix in ("sqlite:///", "sqlite://"):
        if u.startswith(prefix):
            return Path(u[len(prefix):])
    return Path(u)


class Dialect:
    """The per-backend SQL dialect boundary — the ``pgtypes``/``sqlitetypes`` split ported
    to Python: the param placeholder, the JSON column type, and the JSON value codec
    (SQLite stores canonical TEXT; Postgres uses ``JSONB`` via ``psycopg`` ``Jsonb``)."""

    def __init__(self, backend: str) -> None:
        self.backend = backend

    @property
    def placeholder(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    @property
    def json_type(self) -> str:
        return "JSONB" if self.backend == "postgres" else "TEXT"

    def encode_json(self, obj: Any) -> Any:
        if self.backend == "postgres":
            from psycopg.types.json import Jsonb  # lazy — [pg] extra

            return Jsonb(obj)
        return json.dumps(obj, sort_keys=True)

    def decode_json(self, raw: Any) -> Any:
        if raw is None:
            return None
        if isinstance(raw, (dict, list)):  # psycopg returns JSONB already parsed
            return raw
        return json.loads(raw)

    # ── PERSIST-2c-3: the config-plane dialect bits (json query, serial PK, insertion order) ──
    def json_extract(self, col: str, key: str) -> str:
        """A SQL expression selecting json field ``key`` from column ``col`` AS TEXT — the one
        structurally-different query between the backends (SQLite ``json_extract`` vs PG ``->>``)."""
        return f"json_extract({col}, '$.{key}')" if self.backend == "sqlite" else f"{col}->>'{key}'"

    @property
    def serial_pk(self) -> str:
        return (
            "INTEGER PRIMARY KEY AUTOINCREMENT"
            if self.backend == "sqlite"
            else "BIGSERIAL PRIMARY KEY"
        )

    @property
    def serial_col(self) -> str:
        """A monotonic insertion-order column. SQLite leans on the implicit ``rowid`` (so the
        column is unused there); Postgres needs an explicit ``BIGSERIAL``."""
        return "INTEGER" if self.backend == "sqlite" else "BIGSERIAL"

    @property
    def insertion_order(self) -> str:
        """The column to ORDER BY for newest-first by insertion: SQLite's implicit ``rowid`` vs
        the Postgres ``seq`` serial."""
        return "rowid" if self.backend == "sqlite" else "seq"


def make_provenance_store(url: str | Path | None = None) -> Any:
    """Resolve the backend and return a ``ProvenanceStore``. SQLite is the default + never
    gated; the Postgres backend is **tier:pro** — license-gated (fail-closed under a denying
    ``LITHRIM_BENCH_LICENSE``) and built lazily (``psycopg`` is needed only to USE it)."""
    resolved = resolve_db_url(url)
    if backend_of(resolved) == "postgres":
        from lithrim_bench.harness.plugins import License, is_gated

        if is_gated("pro") and not License.from_env().permits(PG_STORE_PLUGIN_ID):
            raise PermissionError(
                f"the Postgres provenance store is tier:pro — {PG_STORE_PLUGIN_ID} is not "
                f"licensed (set LITHRIM_BENCH_LICENSE to permit it)"
            )
        from lithrim_bench.runtime.pipeline.provenance import PostgresProvenanceStore

        return PostgresProvenanceStore(resolved)
    from lithrim_bench.runtime.pipeline.provenance import SqliteProvenanceStore

    return SqliteProvenanceStore(db_path=sqlite_path_of(resolved))


def run_coro(coro):
    """Run an async ProvenanceStore call to completion from EITHER a sync caller or one
    already inside a running event loop (``asyncio.run`` raises there → complete it in a
    worker thread). The BFF's sync read endpoints AND the async chat-tool handlers that call
    them both rely on this; PERSIST-2c."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def provenance_store_for(local_sqlite_path: str | Path | None = None) -> Any:
    """The grade path's store, with the managed-tier precedence: ``LITHRIM_DB_URL`` (the
    Postgres tier) when set, else the caller's local SQLite path (the default — byte-identical
    to constructing ``SqliteProvenanceStore`` directly). The single call ``run_eval`` / the BFF
    use, so pointing the grade at Postgres is one env var, zero code change."""
    env = os.environ.get("LITHRIM_DB_URL", "").strip()
    return make_provenance_store(env or local_sqlite_path)
