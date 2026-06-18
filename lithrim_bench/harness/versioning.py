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

from pathlib import Path
from typing import Any

# NOTE (PERSIST-2b, RED scaffold): stubbed so the acceptance tests import-and-fail on
# assertions. The GREEN implementation replaces each.


def archive_prior(conn: Any, *, table: str, id_col: str, id_val: str, archived_at: str) -> None:
    raise NotImplementedError


def list_versions(
    db_path: str | Path, *, table: str, id_col: str, id_val: str
) -> list[dict]:
    return []


def version_at(
    db_path: str | Path, *, table: str, id_col: str, id_val: str, version: int
) -> dict | None:
    return None


def ledger_history(db_path: str | Path, *, target_type: str, target_id: str) -> list[dict]:
    return []
