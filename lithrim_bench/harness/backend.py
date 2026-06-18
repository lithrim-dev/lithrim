"""The storage-backend seam — PERSIST-2c (the PG/SQLite adapter split).

The OSS core is stdlib-`sqlite3` + offline by construction; this module is the one place
the backend is chosen, so a managed Postgres tier "drops in behind the same interface"
(the ``ProvenanceStore`` Protocol's standing promise) without the core ever importing a
DB driver:

  * :func:`resolve_db_url` — the ``LITHRIM_DB_URL`` connection string (the etlp ``JDBC_URL``
    analogue); unset → the local SQLite default. ``sqlite`` is always available; ``postgres``
    needs the ``[pg]`` extra (psycopg, tier:pro).
  * :class:`Dialect` — the SQL dialect boundary (param style ``?``/``%s``, JSON column
    ``TEXT``/``JSONB``, encode/decode) so one handler runs on either backend.
  * :func:`make_provenance_store` — the factory: a ``SqliteProvenanceStore`` (default,
    100% tested) or a ``PostgresProvenanceStore`` ([pg], tier:pro, contract-tested).

Stdlib only. ``psycopg``/``yoyo`` are imported lazily inside the Postgres path, never at
module load — the core install stays pydantic+pandas, the SQLite path stays dependency-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# NOTE (PERSIST-2c, RED scaffold): stubbed so the acceptance tests import-and-fail on
# assertions. The GREEN implementation replaces each.


def resolve_db_url(url: str | Path | None = None) -> str:
    raise NotImplementedError


def backend_of(url: str) -> str:
    raise NotImplementedError


class Dialect:
    """The per-backend SQL dialect (param style + JSON column type + JSON codec)."""

    def __init__(self, backend: str) -> None:
        self.backend = backend

    @property
    def placeholder(self) -> str:
        raise NotImplementedError

    @property
    def json_type(self) -> str:
        raise NotImplementedError

    def encode_json(self, obj: Any) -> Any:
        raise NotImplementedError

    def decode_json(self, raw: Any) -> Any:
        raise NotImplementedError


def make_provenance_store(url: str | Path | None = None) -> Any:
    raise NotImplementedError
