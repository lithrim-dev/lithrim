"""PERSIST-3a slice 4 — workspace_id isolation on the config plane (the HARD-GATE).

The config tables (agents / judges / config_audit / *_history) gain a ``workspace_id`` so that
under ONE shared DB (``LITHRIM_DB_URL=postgres``) two workspaces stay isolated — the bug a global
table would have. agents / judges get a composite PK ``(workspace_id, name|role)`` (so the SAME
agent name can exist in two workspaces); config_audit / *_history get an additive ``workspace_id``
column + a query filter (append-only, no PK rebuild). Under SQLite the config is already isolated
by per-workspace files, so the column is redundant-but-correct.

An idempotent migration carries an OLD-shape table forward, stamping its existing rows with the
file's OWN workspace (``workspace_id_of(db_path)``) — NOT a literal 'default', else the scoped
reads would hide them. Written RED before the threading + migration.

A1 (back-compat): save/load agent + judge still round-trip on a fresh (new-schema) SQLite DB.
A1-mig (migration preserves + stamps): an OLD-shape agents table (name PK, no workspace_id) is
    carried forward on next access — the legacy row survives, stamped with the file's workspace.
A4 (SINGLE-DB isolation — gated on a live Postgres): two workspaces sharing one PG do NOT see
    each other's agents / judges (same name, isolated), and config_audit.query is workspace-scoped.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import replace

import pytest

from lithrim_bench.harness.audit import Actor, AuditLog, AuditRecord, Target
from lithrim_bench.harness.config import list_agents, load_agent, save_agent
from lithrim_bench.harness.judges import JudgeConfig, list_judges, load_judge, save_judge
from tests._house_fixture import house_agent


def _judge(role: str = "risk_judge", model: str = "azure") -> JudgeConfig:
    return JudgeConfig(role=role, model=model, assigned_flags=("A",), validator_refs=())


# ── A1 (back-compat on a fresh new-schema SQLite DB) ──────────────────────────


def test_config_plane_round_trips_on_fresh_db(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    db = tmp_path / "myws" / "config.sqlite"
    save_agent(replace(house_agent(), name="iso_a"), db_path=db)
    save_judge(_judge(), db_path=db)

    assert "iso_a" in list_agents(db_path=db)
    assert load_agent("iso_a", db_path=db).name == "iso_a"
    assert "risk_judge" in list_judges(db_path=db)
    assert load_judge("risk_judge", db_path=db).model == "azure"

    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(agents)").fetchall()}
    assert "workspace_id" in cols
    wsid = sqlite3.connect(db).execute("SELECT workspace_id FROM agents WHERE name='iso_a'").fetchone()[0]
    assert wsid == "myws"  # derived from .../myws/config.sqlite


# ── A1-mig (an old-shape table is carried forward, rows stamped with the file's workspace) ──


def test_old_shape_agents_table_migrates_and_stamps(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    db = tmp_path / "clinic" / "config.sqlite"
    db.parent.mkdir(parents=True)
    # the PRE-slice4 shape: name PK, NO workspace_id column
    c = sqlite3.connect(db)
    c.executescript("CREATE TABLE agents (name TEXT PRIMARY KEY, json TEXT NOT NULL, created_at TEXT NOT NULL)")
    c.execute("INSERT INTO agents VALUES (?, ?, ?)", ("legacy", '{"name": "legacy"}', "2026-01-01T00:00:00+00:00"))
    c.commit()
    c.close()

    # accessing via the store triggers the idempotent migration
    assert "legacy" in list_agents(db_path=db)  # the legacy row SURVIVED

    info = sqlite3.connect(db).execute("PRAGMA table_info(agents)").fetchall()
    cols = {r[1] for r in info}
    assert "workspace_id" in cols
    pk_cols = {r[1] for r in info if r[5] > 0}  # r[5] = pk position (0 = not pk)
    assert pk_cols == {"workspace_id", "name"}  # composite PK now
    wsid = sqlite3.connect(db).execute("SELECT workspace_id FROM agents WHERE name='legacy'").fetchone()[0]
    assert wsid == "clinic"  # stamped with the file's OWN workspace, not 'default'


def test_same_name_in_two_sqlite_files_independent(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    a = tmp_path / "wsA" / "config.sqlite"
    b = tmp_path / "wsB" / "config.sqlite"
    save_agent(replace(house_agent(), name="shared"), db_path=a)
    save_agent(replace(house_agent(), name="shared"), db_path=b)  # same name, different workspace
    assert list_agents(db_path=a) == ["shared"]
    assert list_agents(db_path=b) == ["shared"]


# ── A4 (SINGLE-DB isolation — the headline, gated on a live Postgres) ─────────


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… for the isolation check)",
)
def test_two_workspaces_isolated_in_one_postgres(tmp_path):
    pytest.importorskip("psycopg")
    import psycopg

    url = os.environ["LITHRIM_DB_URL"]
    with psycopg.connect(url, autocommit=True) as c:
        for t in ("agents", "judges", "config_audit", "agents_history", "judges_history"):
            try:
                c.execute(f"DROP TABLE IF EXISTS {t} CASCADE")  # rebuild clean for the new schema
            except Exception:
                pass

    a = tmp_path / "wsA" / "config.sqlite"  # IGNORED under PG; only the workspace_id differs
    b = tmp_path / "wsB" / "config.sqlite"
    save_agent(replace(house_agent(), name="shared"), db_path=a)
    save_agent(replace(house_agent(), name="shared"), db_path=b)
    save_judge(_judge(role="policy_judge"), db_path=a)
    AuditLog(db_path=a).record(
        AuditRecord(actor=Actor(type="user", id="sme"), action="author",
                    target=Target(type="agent", id="shared"), after={"x": 1})
    )

    # agents/judges are isolated by workspace even though they share the one PG
    assert list_agents(db_path=a) == ["shared"]
    assert list_agents(db_path=b) == ["shared"]
    assert "policy_judge" in list_judges(db_path=a)
    assert "policy_judge" not in list_judges(db_path=b)  # wsA's judge invisible to wsB

    # config_audit.query is workspace-scoped
    assert AuditLog(db_path=a).query(target_type="agent")  # wsA sees its row
    assert AuditLog(db_path=b).query(target_type="agent") == []  # wsB sees none

    # and BOTH rows live in the one PG, distinguished by workspace_id
    with psycopg.connect(url) as c:
        assert c.execute("SELECT count(*) FROM agents WHERE name='shared'").fetchone()[0] == 2
        wsids = {r[0] for r in c.execute("SELECT workspace_id FROM agents WHERE name='shared'").fetchall()}
    assert wsids == {"wsA", "wsB"}


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… for the PG-migration check)",
)
def test_old_shape_postgres_table_migrates_in_place(tmp_path):
    """The risky path: an EXISTING old-shape PG table (name-PK, no workspace_id) — as the live PG
    carries from 2c-3 — is ALTERed in place (add column + stamp + PK-swap), row preserved."""
    pytest.importorskip("psycopg")
    import psycopg

    url = os.environ["LITHRIM_DB_URL"]
    with psycopg.connect(url, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS agents CASCADE")
        c.execute("CREATE TABLE agents (name TEXT PRIMARY KEY, json TEXT NOT NULL, created_at TEXT NOT NULL)")
        c.execute("INSERT INTO agents VALUES ('legacy_pg', '{\"name\": \"legacy_pg\"}', '2026-01-01T00:00:00+00:00')")

    db = tmp_path / "clinicpg" / "config.sqlite"  # IGNORED under PG; workspace_id = 'clinicpg'
    assert "legacy_pg" in list_agents(db_path=db)  # survived the in-place ALTER migration

    with psycopg.connect(url) as c:
        wsid = c.execute("SELECT workspace_id FROM agents WHERE name='legacy_pg'").fetchone()[0]
        pk = c.execute(
            "SELECT a.attname FROM pg_index i JOIN pg_attribute a "
            "ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = 'agents'::regclass AND i.indisprimary"
        ).fetchall()
    assert wsid == "clinicpg"  # stamped with the accessing workspace, not 'default'
    assert {r[0] for r in pk} == {"workspace_id", "name"}  # PK swapped to composite
