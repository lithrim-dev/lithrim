"""The per-role model-binding plane — which {provider, model, endpoint, api_version} each council
role (the 3 judges + the chat assistant) is bound to.

This is the NON-SECRET half of a provider binding, persisted to the config DB (Postgres via
``LITHRIM_DB_URL``, else SQLite — the SAME selector as ``judges``/``agents``/``config_audit``) so a
binding is a first-class, queryable config-plane entity, NOT a loose ``.provider_env`` file. The API
KEY is DELIBERATELY excluded — it stays write-only on ``.provider_env`` (the secret store); a stray
``api_key`` in a binding dict is dropped before the write.

GLOBAL scope (process-wide, mirroring the single ``.provider_env``): the table is keyed by role only.
Per-workspace bindings are a deliberate later enhancement.

Stdlib + the shared ``harness.db`` helpers only (no council/dspy/openai import), so this stays
importable on the default pydantic+pandas core — exactly like ``judges.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lithrim_bench.harness.db import config_db_url, connect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS role_bindings (
    role       TEXT PRIMARY KEY,
    json       TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

# The non-secret binding fields persisted here. ``api_key`` is intentionally NOT in this set — it
# stays write-only on ``.provider_env`` (the secret store). Anything else in a binding dict is dropped.
_BINDING_FIELDS = ("provider", "model", "endpoint", "api_version")


def _clean(binding: dict[str, Any]) -> dict[str, Any]:
    """Keep only the non-secret binding fields — NEVER let a key (or any extra) reach the DB."""
    return {k: binding[k] for k in _BINDING_FIELDS if binding.get(k) is not None}


def save_binding(role: str, binding: dict[str, Any], *, db_path: str | Path) -> None:
    """Upsert a role's non-secret binding into the config DB (idempotent on role). The portable
    ``ON CONFLICT … EXCLUDED`` upsert works on Postgres AND SQLite (not the SQLite-only
    ``INSERT … OR REPLACE`` form). The ``api_key`` (and any non-binding field) is stripped by
    :func:`_clean`."""
    payload = json.dumps(_clean(binding), sort_keys=True)
    created_at = datetime.now(timezone.utc).isoformat()
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT INTO role_bindings (role, json, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(role) DO UPDATE SET json=excluded.json",
            (role, payload, created_at),
        )


def load_bindings(*, db_path: str | Path) -> dict[str, dict[str, Any]]:
    """All saved role bindings keyed by role (empty dict before any bind). Provisions the table."""
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_SCHEMA)
        rows = conn.execute("SELECT role, json FROM role_bindings ORDER BY role").fetchall()
    return {role: json.loads(j) for role, j in rows}


def delete_binding(role: str, *, db_path: str | Path) -> bool:
    """Remove a role's binding. Returns ``True`` iff a row existed (idempotent no-op → ``False``)."""
    with connect(config_db_url(db_path)) as conn:
        conn.executescript(_SCHEMA)
        existed = conn.execute("SELECT 1 FROM role_bindings WHERE role = ?", (role,)).fetchone()
        conn.execute("DELETE FROM role_bindings WHERE role = ?", (role,))
    return existed is not None
