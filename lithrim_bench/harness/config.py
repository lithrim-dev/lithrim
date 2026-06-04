"""The SQLite config plane — an Agent + eval-profile that drives a run.

This is the move that makes the harness a product: *what to run and how* is config,
not code. An :class:`Agent` carries an :class:`EvalProfile`
``{judges, council_config, ontology_ref, tools, kb_bindings, severity_map_ref}`` and
a :class:`Dataset` (the run target). The runner loads an agent and reads everything
off it — no hardcoded ``--case/--baseline/contracts/severity-map``.

Source-of-truth split (WS-1 plan-review decision 2):
  - The committed, reviewable seed is ``data/config/agents/<name>.json`` (and the
    ontology it references is ``data/ontology/clinical_v1.json``).
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lithrim_bench.harness.audit import (
    AuditRecord,
    Target,
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


@dataclass(frozen=True)
class EvalProfile:
    judges: tuple[str, ...]
    council_config: dict[str, Any]
    ontology_ref: str
    ontology_path: str
    tools: tuple[str, ...]
    kb_bindings: dict[str, Any]
    severity_map_ref: str


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
        return p if p.is_absolute() else REPO_ROOT / p

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
    return {
        "name": agent.name,
        "eval_profile": {
            "judges": list(ep.judges),
            "council_config": ep.council_config,
            "ontology_ref": ep.ontology_ref,
            "ontology_path": ep.ontology_path,
            "tools": list(ep.tools),
            "kb_bindings": ep.kb_bindings,
            "severity_map_ref": ep.severity_map_ref,
        },
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
