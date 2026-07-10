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

def _audit_schema(dialect: Any) -> str:
    """The ``config_audit`` schema, dialect-aware (the ``seq`` PK differs — SQLite ``AUTOINCREMENT``
    vs Postgres ``BIGSERIAL``). PERSIST-3a slice 4: an additive ``workspace_id`` (append-only ledger,
    serial PK unchanged) so ``query`` is workspace-scoped under a shared DB."""
    return (
        "CREATE TABLE IF NOT EXISTS config_audit (\n"
        f"    seq          {dialect.serial_pk},\n"
        "    workspace_id TEXT,\n"
        "    ts          TEXT NOT NULL,\n"
        "    actor_type  TEXT NOT NULL,\n"
        "    actor_id    TEXT NOT NULL,\n"
        "    action      TEXT NOT NULL,\n"
        "    target_type TEXT NOT NULL,\n"
        "    target_id   TEXT NOT NULL,\n"
        "    json        TEXT NOT NULL\n"
        ")"
    )


def _ensure_audit(conn: Any, workspace_id: str) -> None:
    """Provision config_audit + idempotently add its ``workspace_id`` column to an old-shape table
    (additive — the ledger is append-only, the serial PK is untouched). PERSIST-3a slice 4."""
    from lithrim_bench.harness.db import migrate_workspace_scope

    conn.executescript(_audit_schema(conn.dialect))
    migrate_workspace_scope(
        conn, "config_audit", new_schema=_audit_schema(conn.dialect), copy_cols=[], key_cols=[],
        stamp_workspace_id=workspace_id, rebuild_pk=False,
    )


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

    def record(self, rec: AuditRecord, *, conn: Any | None = None) -> None:
        """Append one immutable record. When ``conn`` (a ``db.DbConn``) is given the INSERT
        rides the caller's open transaction (the caller owns the commit) so the config write +
        its audit row are atomic (N4); otherwise a private connection is opened, committed, and
        closed — routed through the factory (LITHRIM_DB_URL → Postgres, else local SQLite)."""
        from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

        wsid = workspace_id_of(self._db_path)
        row = (
            wsid,
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
            "(workspace_id, ts, actor_type, actor_id, action, target_type, target_id, json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        if conn is not None:
            _ensure_audit(conn, wsid)
            conn.execute(sql, row)
            return
        with connect(config_db_url(self._db_path)) as own:
            _ensure_audit(own, wsid)
            own.execute(sql, row)

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
        from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

        wsid = workspace_id_of(self._db_path)
        clauses: list[str] = ["workspace_id = ?"]  # PERSIST-3a: the ledger read is workspace-scoped
        params: list[Any] = [wsid]
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
        where = " WHERE " + " AND ".join(clauses)

        with connect(config_db_url(self._db_path)) as conn:
            _ensure_audit(conn, wsid)
            rows = conn.execute(
                f"SELECT json FROM config_audit{where} ORDER BY seq", tuple(params)
            ).fetchall()
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
    version_spec: dict[str, str] | None = None,
    workspace_id: str | None = None,
    migrate: dict[str, Any] | None = None,
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

    PERSIST-2b: when ``version_spec`` (``{table, id_col, id_val}``) is given the prior
    row is archived into ``{table}_history`` (copy-on-write) inside the SAME txn —
    INDEPENDENT of ``audit_log`` (so seed/un-attributed writes version too). The caller's
    upsert SQL drops the ``created_at`` re-stamp, so the live row keeps first-write
    ``created_at`` and the prior is preserved in the shadow (the *prove-what-the-config-was*
    object-version timeline; the ledger stays the why/who change-stream).
    """
    from lithrim_bench.harness.db import config_db_url, connect

    with connect(config_db_url(db_path)) as conn:
        conn.executescript(schema_sql)
        if migrate is not None and workspace_id is not None and version_spec is not None:
            from lithrim_bench.harness.db import migrate_workspace_scope

            migrate_workspace_scope(
                conn, version_spec["table"], new_schema=schema_sql,
                stamp_workspace_id=workspace_id, **migrate,
            )
        before: dict[str, Any] | None = None
        if audit_log is not None:
            row = conn.execute(select_before_sql, select_before_params).fetchone()
            before = json.loads(row[0]) if row is not None else None
        if version_spec is not None:
            from lithrim_bench.harness.versioning import archive_prior

            archive_prior(conn, archived_at=now_iso(), **version_spec)
        conn.execute(upsert_sql, upsert_params)
        if audit_log is not None and record_factory is not None:
            audit_log.record(record_factory(before), conn=conn)


def delete_with_audit(
    db_path: str | Path,
    *,
    schema_sql: str,
    select_before_sql: str,
    select_before_params: tuple[Any, ...],
    delete_sql: str,
    delete_params: tuple[Any, ...],
    record_factory: Callable[[dict[str, Any]], AuditRecord] | None = None,
    audit_log: AuditLog | None = None,
    version_spec: dict[str, str] | None = None,
    workspace_id: str | None = None,
    migrate: dict[str, Any] | None = None,
) -> bool:
    """Delete one config-plane doc-shim row and (optionally) its immutable delete
    :class:`AuditRecord` in ONE connection / ONE transaction — the removal mirror of
    :func:`upsert_with_audit` (so the config plane's delete primitives, CRUD-1's
    ``config.delete_agent`` / ``judges.delete_judge``, share the transaction discipline
    rather than copy-pasting it). Returns ``True`` iff a row was actually removed.

    The §2B trail is CHANGE-ONLY: deleting a row that does not exist is a no-op that
    writes NO audit record (``record_factory`` is invoked only when a prior row was
    read inside the txn) — the immutable history is never polluted with non-events.
    When ``audit_log`` is None the audit machinery is skipped entirely (a plain delete,
    byte-equivalent to a pre-audit removal). When given, the prior row is read inside
    the txn, ``record_factory(before)`` builds the §2B record (``before=<the row>``,
    ``after=None``), and the DELETE + the audit INSERT commit together — no config
    deletion escapes a record.
    """
    from lithrim_bench.harness.db import config_db_url, connect

    with connect(config_db_url(db_path)) as conn:
        conn.executescript(schema_sql)
        if migrate is not None and workspace_id is not None and version_spec is not None:
            from lithrim_bench.harness.db import migrate_workspace_scope

            migrate_workspace_scope(
                conn, version_spec["table"], new_schema=schema_sql,
                stamp_workspace_id=workspace_id, **migrate,
            )
        before: dict[str, Any] | None = None
        if audit_log is not None:
            row = conn.execute(select_before_sql, select_before_params).fetchone()
            before = json.loads(row[0]) if row is not None else None
        if version_spec is not None:
            # PERSIST-2b: archive the final state before removal, so the lifecycle is fully
            # versioned (the deleted object's last version is recoverable from the shadow).
            from lithrim_bench.harness.versioning import archive_prior

            archive_prior(conn, archived_at=now_iso(), **version_spec)
        cur = conn.execute(delete_sql, delete_params)
        removed = cur.rowcount > 0
        if audit_log is not None and record_factory is not None and before is not None:
            audit_log.record(record_factory(before), conn=conn)
        return removed
