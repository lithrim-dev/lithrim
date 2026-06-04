"""The audit substrate — why/when/who/what, immutable + append-only (UAP-1 R0).

Every authoring action over the config plane (a ``save_agent`` / ``PUT /v1/agent`` /
``PUT /v1/ontology``) emits an immutable :class:`AuditRecord` to an append-only
``config_audit`` table. In a regulated domain the audit *is* the product
(SPEC_UNIFIED_AUTHORING_PRODUCT §2B): the record answers, for any config change,
**why** (the rationale + the before→after diff), **when** (UTC ISO8601), **who**
(an attributable actor handle), **what** (the object acted upon).

Design (matches the stack — CLAUDE.md "Pydantic v2, stdlib sqlite3, doc-shim posture"):
  - :class:`AuditRecord` is the universal §2B shape. ``before``/``after`` are the
    CANONICAL top-level diff fields; ``why`` carries the action-typed justification
    (for a user edit: ``{rationale}``) — the diff is NOT duplicated into ``why``
    (monitor N2; OQ back to the spec author re the §2B ``{rationale, before→after}``
    phrasing).
  - :class:`AuditLog` is an **INSERT-only** table. There is deliberately NO update or
    delete method — immutability is the invariant (§2B), enforced by absence.
  - ``record(rec, *, conn=...)`` can reuse a caller's open connection so the config
    write + its audit row land in ONE transaction (monitor N4): no config write
    escapes a record by construction.

Stdlib ``sqlite3`` only — no new dependency.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DB = REPO_ROOT / "out" / "config" / "bench_config.sqlite"

# The dev-default actor: an honest, non-SME handle (monitor N5). A real SME
# attributes via the BFF X-Actor header; the low-level seed path uses {system, seed}.
SYSTEM_SEED_ACTOR = {"type": "system", "id": "seed"}

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS config_audit (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor_type  TEXT NOT NULL,
    actor_id    TEXT NOT NULL,
    action      TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    json        TEXT NOT NULL
)
"""


def now_iso() -> str:
    """UTC ISO8601 wall-clock — the §2B ``when``. Real time (config.py:133 posture);
    this is not a workflow script, so the Date.now ban does not apply."""
    return datetime.now(timezone.utc).isoformat()


class Actor(BaseModel):
    """The §2B ``who`` — an attributable handle (full multi-tenant auth is out, §8)."""

    type: str  # user | judge | validator | grounding_check | critique | agent | system
    id: str


class Target(BaseModel):
    """The §2B ``what`` — the object acted upon."""

    type: str  # judge | flag | ontology | agent | case | verdict | finding | validator
    id: str


class AuditRecord(BaseModel):
    """The universal immutable record (§2B). ``before``/``after`` are the canonical
    diff; ``why`` is the action-typed justification (NOT a duplicate of the diff)."""

    ts: str = Field(default_factory=now_iso)
    actor: Actor
    action: str  # author | edit | assign | run | raise | suppress | flip | withstand | ...
    target: Target
    why: dict[str, Any] = Field(default_factory=dict)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    run_id: str | None = None
    case_id: str | None = None


def make_actor(handle: str | None, *, type: str = "user") -> Actor:
    """Build an Actor from a handle. ``None``/empty → the {system, seed} default
    (the low-level seed path; the BFF passes a real handle or its dev-default)."""
    if not handle:
        return Actor(**SYSTEM_SEED_ACTOR)
    return Actor(type=type, id=handle)


class AuditLog:
    """Append-only config-change log over the ``config_audit`` table (INSERT-only).

    Immutability is enforced by construction: there is no update/delete method. A
    second write to the same target APPENDS a new row (a fresh ``seq``); history is
    never rewritten.
    """

    def __init__(self, *, db_path: str | Path = DEFAULT_CONFIG_DB) -> None:
        self._db_path = Path(db_path)

    def record(self, rec: AuditRecord, *, conn: sqlite3.Connection | None = None) -> None:
        """Append one immutable record. When ``conn`` is given the INSERT rides the
        caller's open transaction (the caller owns the commit) so the config write +
        its audit row are atomic (N4); otherwise a private connection is opened,
        committed, and closed."""
        row = (
            rec.ts,
            rec.actor.type,
            rec.actor.id,
            rec.action,
            rec.target.type,
            rec.target.id,
            rec.model_dump_json(),
        )
        sql = (
            "INSERT INTO config_audit "
            "(ts, actor_type, actor_id, action, target_type, target_id, json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        if conn is not None:
            conn.execute(_AUDIT_SCHEMA)
            conn.execute(sql, row)
            return
        own = sqlite3.connect(self._db_path)
        try:
            own.execute(_AUDIT_SCHEMA)
            own.execute(sql, row)
            own.commit()
        finally:
            own.close()

    def query(
        self,
        *,
        actor: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read the config-change stream (§2B stream 1), oldest-first. Filters are
        ANDed; ``actor`` matches ``actor_id``; ``since`` is an inclusive ISO8601 lower
        bound on ``ts`` (lexicographic, valid for ISO8601 UTC)."""
        clauses: list[str] = []
        params: list[Any] = []
        if actor is not None:
            clauses.append("actor_id = ?")
            params.append(actor)
        if target_type is not None:
            clauses.append("target_type = ?")
            params.append(target_type)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        if since is not None:
            clauses.append("ts >= ?")
            params.append(since)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(_AUDIT_SCHEMA)
            rows = conn.execute(
                f"SELECT json FROM config_audit{where} ORDER BY seq", params
            ).fetchall()
        finally:
            conn.close()
        return [json.loads(r[0]) for r in rows]


def upsert_with_audit(
    db_path: str | Path,
    *,
    schema_sql: str,
    select_before_sql: str,
    select_before_params: tuple[Any, ...],
    upsert_sql: str,
    upsert_params: tuple[Any, ...],
    record_factory: Callable[[dict[str, Any] | None], AuditRecord] | None = None,
    audit_log: AuditLog | None = None,
) -> None:
    """Upsert one config-plane doc-shim row and (optionally) its immutable
    :class:`AuditRecord` in ONE connection / ONE transaction (monitor N4).

    The single place the config-write + audit-row atomicity lives, so the config
    plane's stores (``config.save_agent``, ``judges.save_judge``) share the
    transaction discipline rather than copy-pasting it. When ``audit_log`` is None
    the audit machinery is skipped entirely — a plain upsert, byte-equivalent to a
    pre-audit write (the un-attributed ``seed_*`` path; A5 back-compat). When given,
    the prior row is read inside the txn, ``record_factory(before)`` builds the §2B
    record (so the caller owns the before→after diff + the action-typed ``why``), and
    the upsert + the audit INSERT commit together — no config write escapes a record.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(schema_sql)
        before: dict[str, Any] | None = None
        if audit_log is not None:
            row = conn.execute(select_before_sql, select_before_params).fetchone()
            before = json.loads(row[0]) if row is not None else None
        conn.execute(upsert_sql, upsert_params)
        if audit_log is not None and record_factory is not None:
            audit_log.record(record_factory(before), conn=conn)
        conn.commit()
    finally:
        conn.close()
