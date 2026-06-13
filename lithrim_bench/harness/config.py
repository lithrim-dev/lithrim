"""The SQLite config plane — an Agent + eval-profile that drives a run.

This is the move that makes the harness a product: *what to run and how* is config,
not code. An :class:`Agent` carries an :class:`EvalProfile`
``{judges, council_config, ontology_ref, tools, kb_bindings, severity_map_ref}`` and
a :class:`Dataset` (the run target). The runner loads an agent and reads everything
off it — no hardcoded ``--case/--baseline/contracts/severity-map``.

Source-of-truth split (WS-1 plan-review decision 2):
  - The committed, reviewable seed is ``data/config/agents/<name>.json`` (and the
    ontology it references is ``packs/healthcare/ontology.json``).
  - The config ``.sqlite`` is *built* from those JSONs (gitignored), separate from
    the WS-0 *results* DB ``out/ws0/ws0.sqlite``.

``council_config`` STORES the compose-over-live-v2 disposition (S-BS-6 ratified).
It is stored only — injecting ``council_config`` into the backend ``PipelineRequest``
is WS-2; nothing here touches ``../lithrim-backend/``.

Doc-shim table (S-BS-4): a single JSON column keyed by agent name; see
``collections.py`` for the rationale this mirrors.
"""

from __future__ import annotations

import json
import sqlite3
import sys
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

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DB = REPO_ROOT / "out" / "config" / "bench_config.sqlite"
DEFAULT_AGENT_SEED_DIR = REPO_ROOT / "data" / "config" / "agents"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    name       TEXT PRIMARY KEY,
    json       TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def init_config_db(db_path: str | Path = DEFAULT_CONFIG_DB) -> None:
    """Create an EMPTY config DB (the agents schema, no rows). A fresh workspace starts
    blank so its isolation is visible ('create your first agent'); the existing-but-empty
    DB also stops the BFF's seed-if-missing guards from re-seeding it. Idempotent."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


@dataclass(frozen=True)
class EvalProfile:
    judges: tuple[str, ...]
    council_config: dict[str, Any]
    ontology_ref: str
    ontology_path: str
    tools: tuple[str, ...]
    kb_bindings: dict[str, Any]
    severity_map_ref: str
    # UAP-3b-2 (the deferred UAP-3b A6): the flag codes promoted to first-class
    # INDEPENDENT GroundingCheck entities (§2A) — an additive view over the ontology's
    # ``verification_contracts``, run + audited at the post-consensus locus. Default ()
    # → every existing committed agent is byte-unchanged (the post-consensus path is a
    # no-op without a declaration). See ``harness/grounding_check.py``.
    grounding_checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Dataset:
    case_id: str
    source: str
    baseline: str
    mode: str = "replay"


@dataclass(frozen=True)
class Agent:
    name: str
    eval_profile: EvalProfile
    dataset: Dataset

    def ontology_abspath(self) -> Path:
        p = Path(self.eval_profile.ontology_path)
        abspath = p if p.is_absolute() else REPO_ROOT / p
        if abspath.exists():
            return abspath
        # S-BS-128: a persisted ontology_path can predate a pack relocation (an agent
        # seeded before the clinical ontology moved into its pack). Self-heal by resolving
        # via the ACTIVE pack so a relocated literal path still loads; warn so the
        # substitution is never silent. A valid literal path above is returned as-is
        # (byte-unchanged for every current agent). The core names no relocated path
        # itself (the literal lives only in stale runtime config) — see test_pack_layer1a.
        from lithrim_bench.harness.pack import pack_ontology_path

        pack_onto = pack_ontology_path()
        if pack_onto.exists():
            print(
                f"WARNING: ontology_path {abspath} not found; resolving via the active "
                f"pack -> {pack_onto} (S-BS-128 self-heal).",
                file=sys.stderr,
            )
            return pack_onto
        return abspath  # nothing to fall back to -> the caller raises the original error

    def source_abspath(self) -> Path:
        p = Path(self.dataset.source)
        return p if p.is_absolute() else REPO_ROOT / p

    def baseline_abspath(self) -> Path:
        p = Path(self.dataset.baseline)
        return p if p.is_absolute() else REPO_ROOT / p


def agent_from_dict(data: dict[str, Any]) -> Agent:
    ep = data["eval_profile"]
    ds = data["dataset"]
    return Agent(
        name=data["name"],
        eval_profile=EvalProfile(
            judges=tuple(ep.get("judges") or ()),
            council_config=ep.get("council_config") or {},
            ontology_ref=ep["ontology_ref"],
            ontology_path=ep["ontology_path"],
            tools=tuple(ep.get("tools") or ()),
            kb_bindings=ep.get("kb_bindings") or {},
            severity_map_ref=ep.get("severity_map_ref", ""),
            grounding_checks=tuple(ep.get("grounding_checks") or ()),
        ),
        dataset=Dataset(
            case_id=ds["case_id"],
            source=ds["source"],
            baseline=ds["baseline"],
            mode=ds.get("mode", "replay"),
        ),
    )


def agent_to_dict(agent: Agent) -> dict[str, Any]:
    ep = agent.eval_profile
    eval_profile: dict[str, Any] = {
        "judges": list(ep.judges),
        "council_config": ep.council_config,
        "ontology_ref": ep.ontology_ref,
        "ontology_path": ep.ontology_path,
        "tools": list(ep.tools),
        "kb_bindings": ep.kb_bindings,
        "severity_map_ref": ep.severity_map_ref,
    }
    # Additive + back-compat: only serialize ``grounding_checks`` when declared, so an
    # agent that does not use the UAP-3b-2 surface round-trips byte-identically (and the
    # committed seeds + their audit before/after diffs are unchanged).
    if ep.grounding_checks:
        eval_profile["grounding_checks"] = list(ep.grounding_checks)
    return {
        "name": agent.name,
        "eval_profile": eval_profile,
        "dataset": {
            "case_id": agent.dataset.case_id,
            "source": agent.dataset.source,
            "baseline": agent.dataset.baseline,
            "mode": agent.dataset.mode,
        },
    }


def save_agent(
    agent: Agent,
    *,
    db_path: str | Path = DEFAULT_CONFIG_DB,
    actor: Any = None,
    audit_log: Any = None,
    rationale: str = "",
) -> str:
    """Upsert an agent into the config DB (idempotent on name). Returns the db path.

    When ``audit_log`` is passed (the BFF product write path, R0), the agent upsert
    and an immutable :class:`~lithrim_bench.harness.audit.AuditRecord` are written on
    ONE connection in ONE transaction (monitor N4) — no config write escapes a record
    by construction. ``actor`` is the §2B "who" (``None`` → the {system, seed} default,
    keeping ``seed_config_db`` + existing tests un-attributed-but-honest, not a fake
    SME). The record carries the canonical ``before``→``after`` diff (the prior
    ``agent_to_dict`` if the row existed) + ``why={rationale}`` (N2: the diff is NOT
    duplicated into ``why``). Absent ``audit_log`` the behavior is byte-identical to
    before (A5 back-compat)."""
    db_path = Path(db_path)
    after = agent_to_dict(agent)
    payload = json.dumps(after, sort_keys=True)
    created_at = datetime.now(timezone.utc).isoformat()

    def _record(before: dict[str, Any] | None) -> AuditRecord:
        return AuditRecord(
            actor=make_actor(actor) if not hasattr(actor, "type") else actor,
            action="edit" if before is not None else "author",
            target=Target(type="agent", id=agent.name),
            why={"rationale": rationale},
            before=before,
            after=after,
        )

    upsert_with_audit(
        db_path,
        schema_sql=_SCHEMA,
        select_before_sql="SELECT json FROM agents WHERE name = ?",
        select_before_params=(agent.name,),
        upsert_sql=(
            "INSERT INTO agents (name, json, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET json=excluded.json, created_at=excluded.created_at"
        ),
        upsert_params=(agent.name, payload, created_at),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
    )
    return str(db_path)


def delete_agent(
    name: str,
    *,
    db_path: str | Path = DEFAULT_CONFIG_DB,
    actor: Any = None,
    audit_log: Any = None,
    rationale: str = "",
) -> bool:
    """Delete an agent eval-profile row from the config plane. Returns ``True`` iff a
    row was removed; deleting an absent agent is an idempotent no-op that returns
    ``False`` and writes NO audit record (the §2B trail is change-only).

    This is a PURE capability: the policy guards (refuse the seed default / the last
    remaining agent) live at the BFF edge (``DELETE /v1/agent``), not here, so the
    primitive stays reusable. When ``audit_log`` is passed the removal and its immutable
    ``AuditRecord`` (``action="delete"``, ``target.type="agent"``, ``before=<the row>``,
    ``after=None``) land in ONE transaction via :func:`audit.delete_with_audit`. Runs /
    provenance are a SEPARATE immutable store keyed by ``run_id`` — deleting an agent's
    config row never touches its run blobs (they remain auditable history)."""
    db_path = Path(db_path)

    def _record(before: dict[str, Any]) -> AuditRecord:
        return AuditRecord(
            actor=make_actor(actor) if not hasattr(actor, "type") else actor,
            action="delete",
            target=Target(type="agent", id=name),
            why={"rationale": rationale},
            before=before,
            after=None,
        )

    return delete_with_audit(
        db_path,
        schema_sql=_SCHEMA,
        select_before_sql="SELECT json FROM agents WHERE name = ?",
        select_before_params=(name,),
        delete_sql="DELETE FROM agents WHERE name = ?",
        delete_params=(name,),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
    )


def list_agents(*, db_path: str | Path = DEFAULT_CONFIG_DB) -> list[str]:
    """All saved agent names, sorted (empty before any seed/author). Backs ``GET
    /v1/agents`` (the rail switcher) + the BFF last-agent delete-guard."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        rows = conn.execute("SELECT name FROM agents ORDER BY name").fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def load_agent(name: str, *, db_path: str | Path = DEFAULT_CONFIG_DB) -> Agent:
    """Load an agent eval-profile from the config DB by name."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        row = conn.execute("SELECT json FROM agents WHERE name = ?", (name,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise KeyError(f"agent {name!r} not found in config DB {db_path}")
    return agent_from_dict(json.loads(row[0]))


def seed_config_db(
    *,
    seed_dir: str | Path = DEFAULT_AGENT_SEED_DIR,
    db_path: str | Path = DEFAULT_CONFIG_DB,
) -> list[str]:
    """Build the config DB from the committed agent seed JSONs. Returns agent names."""
    seed_dir = Path(seed_dir)
    names: list[str] = []
    for seed_file in sorted(seed_dir.glob("*.json")):
        agent = agent_from_dict(json.loads(seed_file.read_text()))
        save_agent(agent, db_path=db_path)
        names.append(agent.name)
    return names
