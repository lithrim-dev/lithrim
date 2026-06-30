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
    workspace_id TEXT NOT NULL,
    name         TEXT NOT NULL,
    json         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (workspace_id, name)
)
"""

# PERSIST-3a slice 4: the migration spec carrying an OLD-shape (name-PK) agents table forward to
# the composite (workspace_id, name) PK — so the same agent name can live in two workspaces.
_AGENTS_MIGRATE = {"copy_cols": ["name", "json", "created_at"], "key_cols": ["name"], "rebuild_pk": True}


def _ensure_agents(conn: Any, workspace_id: str) -> None:
    """Provision the agents table (new-shape) + idempotently migrate an old-shape one (PERSIST-3a)."""
    from lithrim_bench.harness.db import migrate_workspace_scope

    conn.executescript(_SCHEMA)
    migrate_workspace_scope(
        conn, "agents", new_schema=_SCHEMA, stamp_workspace_id=workspace_id, **_AGENTS_MIGRATE
    )


# PERSIST-CONV: the durable conversation store — the chat thread (the conversational prose)
# survives a browser refresh. Mirrors the agents table (a per-(workspace, agent) JSON blob)
# but is a PLAIN upsert, NOT upsert_with_audit: the thread is high-frequency per-turn UX
# state, not an audited config change (auditing every turn would bloat the §2B log; the config
# WRITES inside a conversation are already audited on their own routes). No _history shadow.
_CONVERSATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    workspace_id TEXT NOT NULL,
    agent        TEXT NOT NULL,
    thread       TEXT NOT NULL,
    updated_at   TEXT,
    PRIMARY KEY (workspace_id, agent)
)
"""


def _ensure_conversations(conn: Any, workspace_id: str) -> None:  # noqa: ARG001
    """Provision the conversations table. workspace_id is taken on the same param as
    _ensure_agents (a uniform signature) though the plain table needs no migration."""
    conn.executescript(_CONVERSATIONS_SCHEMA)


def init_config_db(db_path: str | Path = DEFAULT_CONFIG_DB) -> None:
    """Create an EMPTY config DB (the agents schema, no rows). A fresh workspace starts
    blank so its isolation is visible ('create your first agent'); the existing-but-empty
    DB also stops the BFF's seed-if-missing guards from re-seeding it. Idempotent."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    with connect(config_db_url(db_path)) as conn:
        _ensure_agents(conn, workspace_id_of(db_path))


@dataclass(frozen=True)
class EvalProfile:
    judges: tuple[str, ...]
    council_config: dict[str, Any]
    ontology_ref: str
    ontology_path: str
    # TOOL-1: ``tools`` / ``kb_bindings`` are LEGACY-INERT — they round-trip into the audited
    # config blob but have NO grade-time consumer. The live tool plane is the plugin registry
    # (``harness/plugins.py`` ``kind: tool`` — declaration + the CE/Pro ``tier`` gate) bound to a
    # flag via the ontology's ``verification_contracts`` (the executed criterion). Retiring /
    # repurposing these two is a deferred audit-blob migration; kept as-is here for back-compat.
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
    from lithrim_bench.harness.db import workspace_id_of

    db_path = Path(db_path)
    wsid = workspace_id_of(db_path)
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
        select_before_sql="SELECT json FROM agents WHERE workspace_id = ? AND name = ?",
        select_before_params=(wsid, agent.name),
        upsert_sql=(
            "INSERT INTO agents (workspace_id, name, json, created_at) VALUES (?, ?, ?, ?) "
            # PERSIST-2b: first-write-wins created_at — the live row keeps its authored
            # timestamp; the prior version is preserved in agents_history (version_spec).
            "ON CONFLICT(workspace_id, name) DO UPDATE SET json=excluded.json"
        ),
        upsert_params=(wsid, agent.name, payload, created_at),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
        version_spec={"table": "agents", "id_col": "name", "id_val": agent.name, "workspace_id": wsid},
        workspace_id=wsid,
        migrate=_AGENTS_MIGRATE,
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
    from lithrim_bench.harness.db import workspace_id_of

    db_path = Path(db_path)
    wsid = workspace_id_of(db_path)

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
        select_before_sql="SELECT json FROM agents WHERE workspace_id = ? AND name = ?",
        select_before_params=(wsid, name),
        delete_sql="DELETE FROM agents WHERE workspace_id = ? AND name = ?",
        delete_params=(wsid, name),
        record_factory=_record if audit_log is not None else None,
        audit_log=audit_log,
        version_spec={"table": "agents", "id_col": "name", "id_val": name, "workspace_id": wsid},
        workspace_id=wsid,
        migrate=_AGENTS_MIGRATE,
    )


def list_agents(*, db_path: str | Path = DEFAULT_CONFIG_DB) -> list[str]:
    """All saved agent names, sorted (empty before any seed/author). Backs ``GET
    /v1/agents`` (the rail switcher) + the BFF last-agent delete-guard."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    wsid = workspace_id_of(db_path)
    with connect(config_db_url(db_path)) as conn:
        _ensure_agents(conn, wsid)
        rows = conn.execute(
            "SELECT name FROM agents WHERE workspace_id = ? ORDER BY name", (wsid,)
        ).fetchall()
    return [r[0] for r in rows]


def load_agent(name: str, *, db_path: str | Path = DEFAULT_CONFIG_DB) -> Agent:
    """Load an agent eval-profile from the config DB by name."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    wsid = workspace_id_of(db_path)
    with connect(config_db_url(db_path)) as conn:
        _ensure_agents(conn, wsid)
        row = conn.execute(
            "SELECT json FROM agents WHERE workspace_id = ? AND name = ?", (wsid, name)
        ).fetchone()
    if row is None:
        raise KeyError(f"agent {name!r} not found in config DB {db_path}")
    return agent_from_dict(json.loads(row[0]))


def save_conversation(
    agent: str, thread: list[Any], *, db_path: str | Path = DEFAULT_CONFIG_DB
) -> str:
    """Upsert a conversation thread for ``agent`` into the config DB (PERSIST-CONV).

    A portable upsert (INSERT … ON CONFLICT DO UPDATE — works on Postgres AND SQLite, unlike
    ``INSERT OR REPLACE``) on (workspace_id, agent) — the latest thread wins (per-turn UX state,
    NOT an audited config change; see ``_CONVERSATIONS_SCHEMA``). ``thread`` is the shell's
    message list (``[{role, text?, parts?}]``); stored as ``json.dumps``. Returns the db path."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    wsid = workspace_id_of(db_path)
    payload = json.dumps(thread)
    updated_at = datetime.now(timezone.utc).isoformat()
    with connect(config_db_url(db_path)) as conn:
        _ensure_conversations(conn, wsid)
        conn.execute(
            "INSERT INTO conversations (workspace_id, agent, thread, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (workspace_id, agent) DO UPDATE SET "
            "thread = EXCLUDED.thread, updated_at = EXCLUDED.updated_at",
            (wsid, agent, payload, updated_at),
        )
    return str(db_path)


def load_conversation(agent: str, *, db_path: str | Path = DEFAULT_CONFIG_DB) -> list[Any]:
    """Load ``agent``'s persisted conversation thread (PERSIST-CONV). An absent thread returns
    ``[]`` (benign default — a brand-new agent has no stored prose; unlike ``load_agent`` this
    never raises)."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    wsid = workspace_id_of(db_path)
    with connect(config_db_url(db_path)) as conn:
        _ensure_conversations(conn, wsid)
        row = conn.execute(
            "SELECT thread FROM conversations WHERE workspace_id = ? AND agent = ?", (wsid, agent)
        ).fetchone()
    return json.loads(row[0]) if row is not None else []


def delete_conversation(agent: str, *, db_path: str | Path = DEFAULT_CONFIG_DB) -> bool:
    """Clear ``agent``'s persisted conversation thread (PERSIST-CONV). Returns ``True`` iff a
    row was removed; clearing an absent thread is an idempotent no-op returning ``False``.

    A PLAIN delete (per-turn UX state), NOT an audited config change — no ``AuditRecord``,
    mirroring :func:`save_conversation`. This clears the chat PROSE only; the config WRITES made
    inside the conversation were audited on their own routes and are untouched. Presence is read
    before the delete (portable, no driver-specific ``rowcount`` dependency)."""
    from lithrim_bench.harness.db import config_db_url, connect, workspace_id_of

    wsid = workspace_id_of(db_path)
    with connect(config_db_url(db_path)) as conn:
        _ensure_conversations(conn, wsid)
        existed = (
            conn.execute(
                "SELECT 1 FROM conversations WHERE workspace_id = ? AND agent = ?", (wsid, agent)
            ).fetchone()
            is not None
        )
        conn.execute(
            "DELETE FROM conversations WHERE workspace_id = ? AND agent = ?", (wsid, agent)
        )
    return existed


def _seed_pack_agents(
    db_path: str | Path, *, already: set[str]
) -> list[str]:
    """PACK-DROPIN-1: AFTER the committed core agents, seed the PORTABLE agents declared by every
    DISCOVERABLE pack (its ``pack.json`` ``seed_agents`` — pack-relative paths to agent JSONs).

    The CONTRACT this seeds (the pack-side build conforms): each ``seed_agents`` entry's JSON uses
    LOGICAL refs, not host/repo-absolute paths — an ``ontology_ref`` + a pack-relative ``dataset``.
    Here the seed RESOLVES those refs to the CURRENT environment so a dropped pack's agent is valid
    wherever it landed (container or local):
      - ``eval_profile.ontology_path`` is overwritten with ``pack_ontology_path(pack)`` (absolute,
        ``check_consistency=False`` — we resolve the PATH of a non-active pack; the codes gate still
        fires for real at grade time), NEVER a stale ``packs/<x>/...`` literal;
      - a pack-relative ``dataset.source`` / ``dataset.baseline`` is resolved against the pack ROOT
        (an absolute or ``mode: in_process`` ref is left as-is).

    Collision-safe: a seed-agent whose name is ``already`` seeded (a core agent OR an earlier pack's
    agent) is SKIPPED with a stderr log — a pack NEVER clobbers ``ws0_default`` or any existing agent.
    Pack names are the pack's responsibility (e.g. ``healthcare_default``). A pack that declares no
    ``seed_agents`` contributes nothing — so a bare CE (no discoverable pack, or only packs without
    ``seed_agents``) seeds ONLY the core agent, unchanged."""
    from lithrim_bench.harness.pack import discover_packs, pack_ontology_path, pack_root

    names: list[str] = []
    for entry in discover_packs():
        pack = entry["id"]
        try:
            manifest = json.loads((pack_root(pack) / "pack.json").read_text())
        except (OSError, ValueError):
            continue
        refs = manifest.get("seed_agents") or []
        if not refs:
            continue
        try:
            root = pack_root(pack)
            ontology_path = str(pack_ontology_path(pack, check_consistency=False))
        except Exception as exc:  # noqa: BLE001 - a malformed/denied pack must not break the seed
            print(
                f"WARNING: pack {pack!r} seed_agents skipped — cannot resolve ontology path: {exc}",
                file=sys.stderr,
            )
            continue
        for ref in refs:
            agent_file = (root / ref) if not Path(ref).is_absolute() else Path(ref)
            try:
                data = json.loads(agent_file.read_text())
            except (OSError, ValueError) as exc:
                print(
                    f"WARNING: pack {pack!r} seed-agent {ref!r} skipped — unreadable: {exc}",
                    file=sys.stderr,
                )
                continue
            name = data.get("name")
            if not name or name in already:
                print(
                    f"WARNING: pack {pack!r} seed-agent {name!r} skipped — "
                    f"{'name collides with an existing agent' if name else 'no name'} "
                    "(a pack never clobbers an existing agent).",
                    file=sys.stderr,
                )
                continue
            ep = data.setdefault("eval_profile", {})
            ep["ontology_path"] = ontology_path
            ds = data.get("dataset") or {}
            for key in ("source", "baseline"):
                val = ds.get(key)
                if val and not Path(val).is_absolute():
                    ds[key] = str((root / val).resolve())
            data["dataset"] = ds
            save_agent(agent_from_dict(data), db_path=db_path)
            already.add(name)
            names.append(name)
    return names


def seed_config_db(
    *,
    seed_dir: str | Path = DEFAULT_AGENT_SEED_DIR,
    db_path: str | Path = DEFAULT_CONFIG_DB,
) -> list[str]:
    """Build the config DB from the committed agent seed JSONs, then (PACK-DROPIN-1) the portable
    ``seed_agents`` of every discoverable pack. Returns the seeded agent names.

    The core (committed) seeds run FIRST and own their names — a pack seed-agent can never clobber
    them (the collision check). A bare CE (no discoverable pack declaring ``seed_agents``) seeds
    ONLY the core agent — the clean-by-construction CE default is unchanged."""
    seed_dir = Path(seed_dir)
    # IDEMPOTENT (POSTGRES-DEADLOCK-FIX): skip agents already in the config DB so re-running the
    # seed is a zero-write no-op. Under the Postgres plane (LITHRIM_DB_URL) the local sqlite
    # ``db_path`` never exists, so callers re-seed on every request — re-archiving every agent each
    # time, which deadlocked two concurrent requests on ``agents_history``. Seeding only the
    # ABSENT agents makes the steady state write nothing (and never clobbers an existing agent —
    # the prior unconditional save also re-applied seed-content edits, which now require an
    # explicit delete+reseed; an acceptable trade for concurrency safety).
    try:
        existing = set(list_agents(db_path=db_path))
    except Exception:  # noqa: BLE001 — a fresh/unreadable DB → nothing seeded yet
        existing = set()
    names: list[str] = list(existing)
    for seed_file in sorted(seed_dir.glob("*.json")):
        agent = agent_from_dict(json.loads(seed_file.read_text()))
        if agent.name in existing:
            continue
        save_agent(agent, db_path=db_path)
        existing.add(agent.name)
        names.append(agent.name)
    names.extend(_seed_pack_agents(db_path, already=existing))
    return names
