"""PERSIST-2c-3: the config-plane single SSOT — LITHRIM_DB_URL selects ONE backend for
EVERYTHING (run blobs + agents + judges + ontology + audit + _history), or all-SQLite when
unset. Written before the per-module port (the invariant test is the cycle's gate).

A1 (db layer): connect() defaults to SQLite; config_db_url honours LITHRIM_DB_URL else the
    local path; the Dialect's config bits (json_extract / serial_pk / insertion_order) are
    per-backend.
A2 (SQLite back-compat): the config-plane stores (save_agent/save_judge/AuditLog) still work
    on SQLite after the port — byte-behaviour preserved.
A3 (SINGLE SSOT — the headline): with LITHRIM_DB_URL=postgres, authoring an agent + a judge +
    an audit record lands them ALL in Postgres and leaves the local SQLite config DB untouched
    (gated on a live PG).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from lithrim_bench.harness.audit import Actor, AuditLog, AuditRecord, Target
from lithrim_bench.harness.backend import Dialect
from lithrim_bench.harness.config import list_agents, load_agent, save_agent
from lithrim_bench.harness.db import config_db_url, connect
from lithrim_bench.harness.judges import JudgeConfig, list_judges, save_judge
from tests._house_fixture import house_agent

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── A1 (the db layer) ─────────────────────────────────────────────────────────


def test_connect_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    with connect(tmp_path / "x.sqlite") as conn:
        assert conn.backend == "sqlite"
        conn.executescript("CREATE TABLE IF NOT EXISTS t (id TEXT)")
        conn.execute("INSERT INTO t (id) VALUES (?)", ("a",))
    with connect(tmp_path / "x.sqlite") as conn:
        assert conn.execute("SELECT id FROM t").fetchone()[0] == "a"


def test_config_db_url_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    assert config_db_url(tmp_path / "c.sqlite").startswith("sqlite:")
    monkeypatch.setenv("LITHRIM_DB_URL", "postgresql://u@h/db")
    assert config_db_url(tmp_path / "c.sqlite").startswith("postgresql://")  # env wins


def test_dialect_config_bits():
    s, p = Dialect("sqlite"), Dialect("postgres")
    assert s.json_extract("json", "agent_id") == "json_extract(json, '$.agent_id')"
    assert p.json_extract("json", "agent_id") == "json->>'agent_id'"
    assert "AUTOINCREMENT" in s.serial_pk and "BIGSERIAL" in p.serial_pk
    assert s.insertion_order == "rowid" and p.insertion_order == "seq"


# ── A2 (SQLite back-compat after the port) ────────────────────────────────────


def _judge(role="risk_judge", model="azure"):
    return JudgeConfig(role=role, model=model, assigned_flags=("A",), validator_refs=())


def test_config_plane_round_trips_on_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    db = tmp_path / "config.sqlite"
    from dataclasses import replace

    agent = replace(house_agent(), name="ssot_sqlite")
    save_agent(agent, db_path=db)
    save_judge(_judge(), db_path=db)
    AuditLog(db_path=db).record(
        AuditRecord(actor=Actor(type="user", id="sme"), action="edit",
                    target=Target(type="agent", id="ssot_sqlite"), after={"x": 1})
    )
    assert "ssot_sqlite" in list_agents(db_path=db)
    assert load_agent("ssot_sqlite", db_path=db).name == "ssot_sqlite"
    assert "risk_judge" in list_judges(db_path=db)
    assert AuditLog(db_path=db).query(target_type="agent", target_id="ssot_sqlite")


# ── A3 (SINGLE SSOT — the headline, gated on a live Postgres) ─────────────────


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… for the single-SSOT check)",
)
def test_single_ssot_everything_in_postgres(tmp_path):
    pytest.importorskip("psycopg")
    from dataclasses import replace

    import psycopg

    url = os.environ["LITHRIM_DB_URL"]
    # clean the config-plane tables (isolated lithrim_bench DB)
    with psycopg.connect(url, autocommit=True) as c:
        for t in ("agents", "judges", "config_audit"):
            try:
                c.execute(f"TRUNCATE {t}")
            except Exception:  # table not created until the store provisions it
                pass

    sqlite_db = tmp_path / "should_stay_empty.sqlite"  # the local path, IGNORED under PG
    save_agent(replace(house_agent(), name="ssot_pg"), db_path=sqlite_db)
    save_judge(_judge(role="policy_judge"), db_path=sqlite_db)
    AuditLog(db_path=sqlite_db).record(
        AuditRecord(actor=Actor(type="user", id="sme"), action="author",
                    target=Target(type="judge", id="policy_judge"), after={"model": "azure"})
    )

    # EVERYTHING is in Postgres …
    with psycopg.connect(url) as c:
        assert c.execute("SELECT count(*) FROM agents WHERE name='ssot_pg'").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM judges WHERE role='policy_judge'").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM config_audit").fetchone()[0] >= 1

    # … and the local SQLite config DB was never written (one SSOT, not both).
    if sqlite_db.exists():
        names = sqlite3.connect(sqlite_db).execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('agents','judges','config_audit')"
        ).fetchall()
        assert names == [], f"SQLite was written under LITHRIM_DB_URL=postgres: {names}"
