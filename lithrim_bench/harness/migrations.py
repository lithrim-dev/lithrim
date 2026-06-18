"""Schema migrations for the managed (Postgres) tier — PERSIST-2c.

``yoyo-migrations`` (the ``[pg]`` extra) is the migration framework for the managed/VPC
tier; the SQLite OSS core self-provisions via the stores' inline ``CREATE TABLE IF NOT
EXISTS`` and needs no framework (the offline, dependency-free path). ``apply_migrations``
runs the ``migrations/`` set against a url (yoyo supports both sqlite + postgres).

``yoyo`` + ``psycopg`` are imported LAZILY — never a core dependency. These helpers back the
gated Postgres contract test (``LITHRIM_DB_URL=postgresql://…``); the offline core never
calls them.
"""

from __future__ import annotations

from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _yoyo_url(url: str) -> str:
    """yoyo selects its driver by URL SCHEME: ``postgresql://`` → psycopg2 (which the bench
    does NOT ship), ``postgresql+psycopg://`` → psycopg3 (the store's driver, the ``[pg]``
    extra). Translate so yoyo uses psycopg3 while the store/factory keep the plain
    ``postgresql://`` (what ``psycopg.connect`` + ``backend_of`` expect)."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def apply_migrations(url: str, *, migrations_dir: Path | None = None) -> None:
    """Apply the pending ``migrations/`` against ``url`` via yoyo (the managed-tier schema
    source). Lazy yoyo import — the ``[pg]`` extra."""
    from yoyo import get_backend, read_migrations

    backend = get_backend(_yoyo_url(url))
    migrations = read_migrations(str(migrations_dir or MIGRATIONS_DIR))
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))


def reset_provenance(url: str) -> None:
    """Truncate the provenance tables — the gated PG contract test's clean slate (the fixed
    ``r1``/``r2``/``r3`` ids must not collide across runs). Lazy psycopg import."""
    import psycopg

    with psycopg.connect(url) as conn:
        conn.execute("TRUNCATE pipeline_runs, pipeline_runs_history")
