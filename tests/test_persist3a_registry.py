"""PERSIST-3a slice 3 — the workspaces registry into the single SSOT.

The registry stops being ``WORKSPACES_DIR/<name>/workspace.json`` files + a ``.active`` pointer:
the workspace MANIFEST is a row in the one SSOT DB (``LITHRIM_DB_URL`` → Postgres, else a global
``registry.sqlite``) and the active pointer is an ``active_workspace`` singleton. The per-workspace
DIR stays (it still holds ontology drafts + the SQLite-mode config/collections files); only the
REGISTRY (list + active) moves into the DB. Written RED.

Back-compat is the hard constraint: an EMPTY registry must behave exactly like before (read the
legacy ``workspace.json`` / ``.active`` files), so the ~every-test ``get_active_workspace`` path
is unchanged. New writes dual-write DB + file during the transition.

A1 (registry store): save/load/list workspaces + set/get active round-trip on SQLite.
A2 (workspace.py DB-backed): create_workspace + set_active_workspace land in the registry DB and
    read back through list_workspaces / active_workspace_name / get_active_workspace.
A2b (file fallback): a legacy workspace.json with NO registry row still resolves (transition).
A3 (SINGLE SSOT — gated on a live Postgres): create + activate under LITHRIM_DB_URL=postgres land
    in PG workspaces / active_workspace; the local registry.sqlite is untouched.
"""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

# ── A1 (the registry store round-trips on SQLite) ─────────────────────────────


def test_registry_store_round_trips(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import registry_store

    db = tmp_path / "registry.sqlite"
    manifest = {
        "name": "alpha", "pack": "_core", "packs_dir": None,
        "actor": "you@local", "owner": None, "created_at": "2026-01-01T00:00:00+00:00",
    }
    registry_store.save_workspace("alpha", manifest, db_path=db)
    assert registry_store.load_workspace("alpha", db_path=db) == manifest

    registry_store.save_workspace("beta", {"name": "beta", "pack": "_core"}, db_path=db)
    assert set(registry_store.list_workspace_ids(db_path=db)) == {"alpha", "beta"}

    assert registry_store.get_active(db_path=db) is None
    registry_store.set_active("beta", db_path=db)
    assert registry_store.get_active(db_path=db) == "beta"
    registry_store.set_active("alpha", db_path=db)  # singleton — moves, never duplicates
    assert registry_store.get_active(db_path=db) == "alpha"


# ── A2 (workspace.py reads/writes the registry through the DB) ─────────────────


def test_create_and_active_round_trip_via_db(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import registry_store, workspace

    monkeypatch.setattr(workspace, "WORKSPACES_DIR", tmp_path / "ws")
    reg_db = (tmp_path / "ws") / "registry.sqlite"

    ws = workspace.create_workspace("alpha", pack="_core", seed=False)
    assert ws.name == "alpha"
    assert registry_store.load_workspace("alpha", db_path=reg_db) is not None  # in the registry DB
    assert "alpha" in workspace.list_workspaces()

    workspace.set_active_workspace("alpha")
    assert registry_store.get_active(db_path=reg_db) == "alpha"
    assert workspace.active_workspace_name() == "alpha"
    assert workspace.get_active_workspace().name == "alpha"


def test_legacy_file_only_workspace_still_resolves(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import workspace

    monkeypatch.setattr(workspace, "WORKSPACES_DIR", tmp_path / "ws")
    d = tmp_path / "ws" / "legacy"
    d.mkdir(parents=True)
    (d / "workspace.json").write_text(
        json.dumps({"name": "legacy", "pack": "_core", "created_at": "2026-01-01T00:00:00+00:00"})
    )
    # no registry row written — the pre-3a shape must still resolve (DB-empty → file fallback)
    assert "legacy" in workspace.list_workspaces()
    assert workspace.read_workspace("legacy").name == "legacy"


# ── A3 (SINGLE SSOT — the headline, gated on a live Postgres) ─────────────────


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… for the single-SSOT check)",
)
def test_registry_single_ssot_in_postgres(tmp_path, monkeypatch):
    pytest.importorskip("psycopg")
    import psycopg

    from lithrim_bench.harness import workspace

    url = os.environ["LITHRIM_DB_URL"]
    with psycopg.connect(url, autocommit=True) as c:
        for t in ("workspaces", "active_workspace"):
            try:
                c.execute(f"TRUNCATE {t}")
            except Exception:
                pass

    monkeypatch.setattr(workspace, "WORKSPACES_DIR", tmp_path / "ws")
    workspace.create_workspace("pgws", pack="_core", seed=False)
    workspace.set_active_workspace("pgws")

    with psycopg.connect(url) as c:
        assert c.execute("SELECT count(*) FROM workspaces WHERE workspace_id='pgws'").fetchone()[0] == 1
        assert c.execute("SELECT workspace_id FROM active_workspace").fetchone()[0] == "pgws"

    reg = tmp_path / "ws" / "registry.sqlite"
    if reg.exists():
        tbls = sqlite3.connect(reg).execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('workspaces','active_workspace')"
        ).fetchall()
        assert tbls == [], f"SQLite registry was written under LITHRIM_DB_URL=postgres: {tbls}"
