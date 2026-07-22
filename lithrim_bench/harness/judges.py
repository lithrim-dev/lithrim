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
    workspace_id TEXT NOT NULL,
    role         TEXT NOT NULL,
    json         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (workspace_id, role)
)
"""

# PERSIST-3a slice 4: the migration carrying an OLD-shape (role-PK) judges table forward to the
# composite (workspace_id, role) PK — so the same role can be authored in two workspaces.
_JUDGES_MIGRATE = {"copy_cols": ["role", "json", "created_at"], "key_cols": ["role"], "rebuild_pk": True}


def _ensure_judges(conn: Any, workspace_id: str) -> None:
    """Provision the judges table (new-shape) + idempotently migrate an old-shape one (PERSIST-3a)."""
    from lithrim_bench.harness.db import migrate_workspace_scope

    conn.executescript(_SCHEMA)
    migrate_workspace_scope(
        conn, "judges", new_schema=_SCHEMA, stamp_workspace_id=workspace_id, **_JUDGES_MIGRATE
    )


@dataclass(frozen=True)
class JudgeConfig:
    role: str
    model: str
    assigned_flags: tuple[str, ...]
    validator_refs: tuple[str, ...]
    # Sampling layer (per-reviewer): how many completions this reviewer samples per grade (k),
    # its sampling temperature, and the single injected criterion sentence. ``None`` k/temperature
    # mean "use the per-role default" (resolved at grade time, never here) so an unauthored judge
    # is byte-identical to before. ``criterion`` is appended to the reviewer's role prompt.
    temperature: float | None = None
    k: int | None = None
    criterion: str = ""
    # WS-JUDGE-BIND: the WORKSPACE-scoped half of a provider binding, sitting next to the ``model``
    # this record already carried. ``role_bindings`` is keyed on role ALONE (one global row), so two
    # workspaces using the same roles could not resolve to different deployments; a bare ``model``
    # selector cannot express a per-workspace base URL. Empty = "this workspace binds nothing for
    # this role" → the global row still wins, byte-identically. The api_key is DELIBERATELY absent,
    # exactly as in ``role_bindings``: secrets stay write-only on ``.provider_env``.
    provider: str = ""
    endpoint: str = ""
    api_version: str = ""
    # JUDGE-LABEL-1: the SME-authored label for this seat. The UI otherwise derives a label from
    # the role id (``copy.js:roleLabel``), which names a MODEL for historical ids like
    # ``openbio_reviewer`` — actively wrong once a workspace can bind any model to any seat. The
    # ID stays load-bearing (``tier1_owners`` + lens authority key on it, and every graded record
    # carries it); only the LABEL is authorable. Empty = derive it, as before.
    display_name: str = ""


def judge_from_dict(data: dict[str, Any]) -> JudgeConfig:
    raw_k = data.get("k")
    raw_temp = data.get("temperature")
    return JudgeConfig(
        role=data["role"],
        model=data.get("model", "") or "",
        assigned_flags=tuple(data.get("assigned_flags") or ()),
        validator_refs=tuple(data.get("validator_refs") or ()),
        temperature=float(raw_temp) if isinstance(raw_temp, (int, float)) else None,
        k=int(raw_k) if isinstance(raw_k, (int, float)) else None,
        criterion=data.get("criterion", "") or "",
        # absent on every row written before WS-JUDGE-BIND → "" (unbound), never a KeyError
        provider=data.get("provider", "") or "",
        endpoint=data.get("endpoint", "") or "",
        api_version=data.get("api_version", "") or "",
        display_name=data.get("display_name", "") or "",
    )


def judge_to_dict(jc: JudgeConfig) -> dict[str, Any]:
    return {
        "role": jc.role,
        "model": jc.model,
        "assigned_flags": list(jc.assigned_flags),
        "validator_refs": list(jc.validator_refs),
        "temperature": jc.temperature,
        "k": jc.k,
        "criterion": jc.criterion,
        "provider": jc.provider,
        "endpoint": jc.endpoint,
        "api_version": jc.api_version,
        "display_name": jc.display_name,
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
    from lithrim_bench.harness.db import workspace_id_of

    db_path = Path(db_path)
    wsid = workspace_id_of(db_path)
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
        select_before_sql="SELECT json FROM judges WHERE workspace_id = ? AND role = ?",
        select_before_params=(wsid, jc.role),
        upsert_sql=(
            "INSERT INTO judges (workspace_id, role, json, created_at) VALUES (?, ?, ?, ?) "
            # PERSIST-2b: first-write-wins created_at; the prior version → judges_history.
            "ON CONFLICT(workspace_id, role) DO UPDATE SET json=excluded.json"
        ),
        upsert_params=(wsid, jc.role, payload, created_at),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
        version_spec={"table": "judges", "id_col": "role", "id_val": jc.role, "workspace_id": wsid},
        workspace_id=wsid,
        migrate=_JUDGES_MIGRATE,
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
    from lithrim_bench.harness.db import workspace_id_of

    db_path = Path(db_path)
    wsid = workspace_id_of(db_path)

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
        select_before_sql="SELECT json FROM judges WHERE workspace_id = ? AND role = ?",
        select_before_params=(wsid, role),
        delete_sql="DELETE FROM judges WHERE workspace_id = ? AND role = ?",
        delete_params=(wsid, role),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
        version_spec={"table": "judges", "id_col": "role", "id_val": role, "workspace_id": wsid},
        workspace_id=wsid,
        migrate=_JUDGES_MIGRATE,
    )


def load_judge(role: str, *, db_path: str | Path = DEFAULT_CONFIG_DB) -> JudgeConfig | None:
    """Load a saved judge-config by role, or ``None`` if the role was never authored
    (the BFF then serves a derived default — the role's lens, unbound model)."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    wsid = workspace_id_of(db_path)
    with connect(config_db_url(db_path)) as conn:
        _ensure_judges(conn, wsid)
        row = conn.execute(
            "SELECT json FROM judges WHERE workspace_id = ? AND role = ?", (wsid, role)
        ).fetchone()
    return judge_from_dict(json.loads(row[0])) if row is not None else None


def list_judges(*, db_path: str | Path = DEFAULT_CONFIG_DB) -> dict[str, JudgeConfig]:
    """All saved judge-configs keyed by role (empty before any authoring)."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    wsid = workspace_id_of(db_path)
    with connect(config_db_url(db_path)) as conn:
        _ensure_judges(conn, wsid)
        rows = conn.execute(
            "SELECT json FROM judges WHERE workspace_id = ? ORDER BY role", (wsid,)
        ).fetchall()
    out: dict[str, JudgeConfig] = {}
    for (j,) in rows:
        jc = judge_from_dict(json.loads(j))
        out[jc.role] = jc
    return out


def derive_roster_order(
    production: list[str],
    assignments: dict[str, Any] | None,
    models: dict[str, Any] | None,
) -> list[str]:
    """The grade-call-site roster order (PHASE2-B): the active pack's ``production_judges``
    FIRST (in pack order — load-bearing), then any AUTHORED extra role (a key in
    ``assignments`` or ``models`` that is not already a production judge) appended.

    Stdlib-only (no pack/council import): the caller passes ``pack_production_judges()`` in,
    so this module stays importable on the default core. Dedup-stable — a production role that
    is ALSO authored appears once (from ``production``). The result is what ``run(roles=)``
    threads → ``build_authored_semantic_stage`` → ``build_trio``, so an authored judge actually
    joins the trio→N-tet that the frozen ``_apply_consensus`` grades."""
    authored = set(assignments or {}) | set(models or {})
    extras = [r for r in sorted(authored) if r not in production]
    return [*production, *extras]


def apply_reviewer_roster(
    derived_roles: list[str] | None,
    council_config: dict[str, Any] | None,
    *,
    production: list[str] | None = None,
) -> list[str] | None:
    """REVIEWER-MODE (single vs multiple reviewers): a per-agent
    ``council_config['reviewer_roster']`` — a non-empty, ordered list of reviewer roles —
    OVERRIDES the derived roster so the grade runs EXACTLY those reviewers. A single-element
    roster ("single reviewer") is the supported minimal council: its lone vote drives
    ``derive_case_outcome``, and — with ``gate_mode`` on (the grade site derives it from
    ``len(roles) == 1``, the frozen ``_apply_consensus``'s single-judge consensus path) —
    that one judge's findings populate. Absent/empty → the panel default (``derived_roles``
    unchanged).

    A role not in ``production`` (when given) is dropped — a stored roster can't invent a
    reviewer the active pack doesn't run; if the override resolves to nothing valid, fall back
    to ``derived_roles``. Stdlib-only (no pack/council import), so both grade paths
    (``apps/bff/app.py`` in-process + ``scripts/run_eval.py`` subprocess) share one rule."""
    rr = (council_config or {}).get("reviewer_roster")
    if not rr:
        return derived_roles
    roles = [r for r in rr if production is None or r in production]
    return roles or derived_roles


def resolve_grade_roster(
    production: list[str],
    assignments: dict[str, Any] | None,
    models: dict[str, Any] | None,
    council_config: dict[str, Any] | None,
) -> list[str] | None:
    """The grade-site roster resolution, shared by both grade paths (``apps/bff/app.py``
    in-process + ``scripts/run_eval.py`` subprocess). Compose :func:`derive_roster_order`
    (the active pack's ``production_judges`` ∪ any AUTHORED extra role) then apply the
    per-agent :func:`apply_reviewer_roster` override.

    The override's allow-set is the **DERIVED** roster, not the raw ``production`` panel —
    so an authored extra role (e.g. a single ``generalist_reviewer`` carrying its own full
    lens, GENERALIST-1) that the agent rosters survives the membership filter, while a roster
    naming a truly-unknown role is still dropped → falls back to the derived default. Returns
    the ``roles`` to thread into ``build_authored_semantic_stage`` (``None`` = the full derived
    default / panel; a single-element list → ``gate_mode`` single-judge grade at the caller).

    Byte-identical to the prior inline two-step when there is no authored extra (``derived ==
    production`` → ``None``) and when there is one but no override (returns the derived N-tet);
    the ONLY behavioural change is that an authored-extra roster now resolves to that role."""
    derived = derive_roster_order(production, assignments, models)
    roles = derived if derived != production else None
    return apply_reviewer_roster(roles, council_config, production=derived)


def recommend_reviewer_mode(
    panel: list[str], selectable: list[str], *, single_k: int = 5
) -> dict[str, Any]:
    """CE-JUDGE-RECOMMEND-1: recommend a reviewer configuration from the pack's structure.

    The calibration thesis: differentiated SPECIALISTS (the panel) beat one full-lens generalist
    when the domain spans multiple failure-mode families; a single Generalist with k 3-8 sampling
    is enough for a NARROW domain (one review lens). The pack's reviewer count is the domain proxy
    — pure + deterministic, so the UI can render the recommendation with no model call.

    Returns ``{mode, reviewer, k, rationale}``: ``panel`` mode has ``reviewer``/``k`` None; ``single``
    mode names the reviewer (the opt-in full-lens generalist if present, else the sole role) and a
    recommended k in 3-8."""
    generalists = [r for r in selectable if r not in panel]
    if len(panel) >= 2:
        return {
            "mode": "panel",
            "reviewer": None,
            "k": None,
            "rationale": (
                f"{len(panel)} specialist reviewers cover distinct failure modes — differentiated "
                "lenses beat one generalist when the domain spans several review concerns."
            ),
        }
    reviewer = generalists[0] if generalists else (panel[0] if panel else None)
    via_generalist = bool(generalists)
    return {
        "mode": "single",
        "reviewer": reviewer,
        "k": single_k,
        "rationale": (
            f"A single {'Generalist' if via_generalist else 'reviewer'} with k={single_k} sampling "
            "is enough for a narrow domain (one review lens) — add specialists as the domain grows."
        ),
    }
