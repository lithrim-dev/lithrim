"""The judge-config plane — a judge = (role + assigned ontology flags + model +
attached validator refs), persisted to the config DB (UAP-2 R2, §12.2).

A judge is authored by ASSIGNING an ontology flag subset to a role (the assigned
flags' lens + the role's ``JudgeQuestion``s become its refinement questions — §2A);
this store holds the *binding* side of that authoring: the model deployment, the
assigned flag codes, and the **references** to persisted smart-contract validators
the judge EXECUTES (never generates — generation is `verification/jute_dspy.py`,
a separate concern). The questions themselves stay in the ontology (one source of
truth, §12.2); this store does not duplicate them.

Mirrors ``config.py``'s ``agents`` doc-shim (a single JSON column keyed by role),
and shares the **single-transaction config-write + immutable audit-row** discipline
via ``audit.upsert_with_audit`` (N4) — no copy-paste of the txn dance. ``target.type``
is ``"judge"`` (§2B). Stdlib ``sqlite3`` only — no council/dspy import, so this stays
importable on the default pydantic+pandas core.

Validator-ref EXECUTION (running the attached validators as a judge's signals during
an eval) is the §2A withstands-gate = UAP-3b; this cycle persists + surfaces the refs
only (the attachment), not their per-evaluation execution.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lithrim_bench.harness.audit import (
    AuditRecord,
    Target,
    delete_with_audit,
    make_actor,
    upsert_with_audit,
)
from lithrim_bench.harness.config import DEFAULT_CONFIG_DB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS judges (
    role       TEXT PRIMARY KEY,
    json       TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class JudgeConfig:
    role: str
    model: str
    assigned_flags: tuple[str, ...]
    validator_refs: tuple[str, ...]


def judge_from_dict(data: dict[str, Any]) -> JudgeConfig:
    return JudgeConfig(
        role=data["role"],
        model=data.get("model", "") or "",
        assigned_flags=tuple(data.get("assigned_flags") or ()),
        validator_refs=tuple(data.get("validator_refs") or ()),
    )


def judge_to_dict(jc: JudgeConfig) -> dict[str, Any]:
    return {
        "role": jc.role,
        "model": jc.model,
        "assigned_flags": list(jc.assigned_flags),
        "validator_refs": list(jc.validator_refs),
    }


def save_judge(
    jc: JudgeConfig,
    *,
    db_path: str | Path = DEFAULT_CONFIG_DB,
    actor: Any = None,
    audit_log: Any = None,
    rationale: str = "",
) -> str:
    """Upsert a judge-config into the config DB (idempotent on role). Returns the db
    path. When ``audit_log`` is passed (the BFF write path, R0) the judge upsert and
    its immutable ``AuditRecord`` (``target.type='judge'``) land in ONE transaction
    via :func:`audit.upsert_with_audit` (N4). ``actor`` is the §2B "who"; absent
    ``audit_log`` the write is byte-equivalent to a plain upsert (back-compat)."""
    db_path = Path(db_path)
    after = judge_to_dict(jc)
    payload = json.dumps(after, sort_keys=True)
    created_at = datetime.now(timezone.utc).isoformat()

    def _record(before: dict[str, Any] | None) -> AuditRecord:
        return AuditRecord(
            actor=make_actor(actor) if not hasattr(actor, "type") else actor,
            action="edit" if before is not None else "author",
            target=Target(type="judge", id=jc.role),
            why={"rationale": rationale},
            before=before,
            after=after,
        )

    upsert_with_audit(
        db_path,
        schema_sql=_SCHEMA,
        select_before_sql="SELECT json FROM judges WHERE role = ?",
        select_before_params=(jc.role,),
        upsert_sql=(
            "INSERT INTO judges (role, json, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(role) DO UPDATE SET json=excluded.json, created_at=excluded.created_at"
        ),
        upsert_params=(jc.role, payload, created_at),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
    )
    return str(db_path)


def delete_judge(
    role: str,
    *,
    db_path: str | Path = DEFAULT_CONFIG_DB,
    actor: Any = None,
    audit_log: Any = None,
    rationale: str = "",
) -> bool:
    """Delete a judge-config row so the role REVERTS to its default lens. The role
    itself is fixed by ``LENS_BY_ROLE`` (judge_metric) and never disappears — "deleting
    a judge" removes only the authored ``JudgeConfig`` binding, so no flag is orphaned
    (CRUD-1 §0). Returns ``True`` iff an authored row was removed; deleting an
    unauthored role is an idempotent no-op that returns ``False`` and writes NO audit
    record (the §2B trail is change-only).

    When ``audit_log`` is passed (the BFF delete path) the row removal and its immutable
    ``AuditRecord`` (``action="delete"``, ``target.type="judge"``, ``before=<the row>``,
    ``after=None``) land in ONE transaction via :func:`audit.delete_with_audit`. ``actor``
    is the §2B "who". Absent ``audit_log`` it is a plain delete (back-compat). This
    primitive does NOT validate ``role`` against ``LENS_BY_ROLE`` — that 404 stays at the
    BFF edge (judges.py is council/dspy-free by construction)."""
    db_path = Path(db_path)

    def _record(before: dict[str, Any]) -> AuditRecord:
        return AuditRecord(
            actor=make_actor(actor) if not hasattr(actor, "type") else actor,
            action="delete",
            target=Target(type="judge", id=role),
            why={"rationale": rationale},
            before=before,
            after=None,
        )

    return delete_with_audit(
        db_path,
        schema_sql=_SCHEMA,
        select_before_sql="SELECT json FROM judges WHERE role = ?",
        select_before_params=(role,),
        delete_sql="DELETE FROM judges WHERE role = ?",
        delete_params=(role,),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
    )


def load_judge(role: str, *, db_path: str | Path = DEFAULT_CONFIG_DB) -> JudgeConfig | None:
    """Load a saved judge-config by role, or ``None`` if the role was never authored
    (the BFF then serves a derived default — the role's lens, unbound model)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        row = conn.execute("SELECT json FROM judges WHERE role = ?", (role,)).fetchone()
    finally:
        conn.close()
    return judge_from_dict(json.loads(row[0])) if row is not None else None


def list_judges(*, db_path: str | Path = DEFAULT_CONFIG_DB) -> dict[str, JudgeConfig]:
    """All saved judge-configs keyed by role (empty before any authoring)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        rows = conn.execute("SELECT json FROM judges ORDER BY role").fetchall()
    finally:
        conn.close()
    out: dict[str, JudgeConfig] = {}
    for (j,) in rows:
        jc = judge_from_dict(json.loads(j))
        out[jc.role] = jc
    return out
