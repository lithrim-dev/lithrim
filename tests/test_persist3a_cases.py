"""PERSIST-3a slice 1 — the ``cases`` corpus into the single linked SSOT.

The corpus stops being loose ``ingested_cases.jsonl`` files: a case is a row in the one
SSOT DB (``LITHRIM_DB_URL`` → Postgres, else local SQLite), scoped by ``workspace_id`` and
carrying its content as linked JSON (``payload``), with a reserved ``storage_ref`` column for
the future object-store move (PERSIST-3b). Written RED before the store + the picklist reroute.

A1 (store round-trip): ``save_case`` → ``load_case_row`` / ``list_cases`` preserve the payload
    on SQLite; the ``storage_ref`` column exists and is NULL for inline content.
A2 (picklist reads the SSOT): ``picklist.load_case`` resolves a case from the ``cases`` table
    of the active workspace — no ``ingested_cases.jsonl`` on disk (the legacy file stays a
    fallback, not the source of truth).
A4 (workspace isolation by column): two ``workspace_id``s in ONE table do not see each other's
    cases — the isolation that one shared DB needs (the bug a global table would have).
A3 (SINGLE SSOT — gated on a live Postgres): a case authored under ``LITHRIM_DB_URL=postgres``
    lands in PG ``cases`` with its ``workspace_id`` + JSON ``payload``, local SQLite untouched.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from lithrim_bench.harness.db import workspace_id_of

# ── A1 (the cases store round-trips on SQLite) ────────────────────────────────


def test_save_load_round_trips_payload(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import cases_store

    db = tmp_path / "myws" / "collections.sqlite"
    payload = {"case_id": "c1", "transcript": "…", "expected_safety_flags": ["A"], "n": 3}
    cases_store.save_case("c1", payload, source="ingested", db_path=db)

    assert cases_store.load_case_row("c1", db_path=db) == payload
    rows = cases_store.list_cases(db_path=db)
    assert [r["case_id"] for r in rows] == ["c1"]
    assert rows[0]["source"] == "ingested"


def test_save_is_idempotent_on_case_id(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import cases_store

    db = tmp_path / "myws" / "collections.sqlite"
    cases_store.save_case("c1", {"v": 1}, db_path=db)
    cases_store.save_case("c1", {"v": 2}, db_path=db)  # re-ingest overwrites, not duplicates
    assert cases_store.load_case_row("c1", db_path=db) == {"v": 2}
    assert len(cases_store.list_cases(db_path=db)) == 1


def test_storage_ref_column_present_and_null_inline(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import cases_store

    db = tmp_path / "myws" / "collections.sqlite"
    cases_store.save_case("c1", {"v": 1}, db_path=db)
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(cases)").fetchall()}
    assert {"workspace_id", "case_id", "source", "payload", "storage_ref", "created_at"} <= cols
    ref = sqlite3.connect(db).execute("SELECT storage_ref FROM cases WHERE case_id='c1'").fetchone()[0]
    assert ref is None  # inline JSON in 3a; the object-store ref is reserved for 3b


# ── A4 (workspace isolation by the workspace_id column) ───────────────────────


def test_two_workspaces_in_one_table_are_isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import cases_store

    db = tmp_path / "shared.sqlite"  # ONE file/table, two explicit scopes
    cases_store.save_case("cX", {"w": "A"}, db_path=db, workspace_id="wsA")
    cases_store.save_case("cY", {"w": "B"}, db_path=db, workspace_id="wsB")

    assert cases_store.load_case_row("cX", db_path=db, workspace_id="wsA") == {"w": "A"}
    assert cases_store.load_case_row("cX", db_path=db, workspace_id="wsB") is None
    assert [r["case_id"] for r in cases_store.list_cases(db_path=db, workspace_id="wsA")] == ["cX"]
    assert [r["case_id"] for r in cases_store.list_cases(db_path=db, workspace_id="wsB")] == ["cY"]


def test_workspace_id_derived_from_path():
    # the per-workspace db path .../<name>/<file> → <name> is the scope (the registry is dir-per-ws)
    assert workspace_id_of(Path("/x/out/workspaces/clinical_scribe/collections.sqlite")) == "clinical_scribe"
    assert workspace_id_of(Path("/x/out/workspaces/clinical_scribe/config.sqlite")) == "clinical_scribe"
    assert workspace_id_of(None) == "default"


# ── A2 (picklist resolves a case from the SSOT, not a jsonl file) ─────────────


def test_picklist_reads_case_from_db_not_jsonl(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench import picklist
    from lithrim_bench.harness import cases_store, workspace

    monkeypatch.setattr(workspace, "WORKSPACES_DIR", tmp_path / "ws")
    ws = workspace.create_workspace("myws", seed=False)
    workspace.set_active_workspace("myws")

    cases_store.save_case("case_42", {"case_id": "case_42", "x": 1}, db_path=ws.collections_db)

    assert not (ws.out_dir / "ingested_cases.jsonl").exists()  # nothing on disk
    assert picklist.load_case("case_42") == {"case_id": "case_42", "x": 1}


# ── A3 (SINGLE SSOT — the headline, gated on a live Postgres) ─────────────────


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… for the single-SSOT check)",
)
def test_cases_single_ssot_in_postgres(tmp_path):
    pytest.importorskip("psycopg")
    import psycopg

    from lithrim_bench.harness import cases_store

    url = os.environ["LITHRIM_DB_URL"]
    with psycopg.connect(url, autocommit=True) as c:
        try:
            c.execute("TRUNCATE cases")
        except Exception:  # not provisioned until the store creates it
            pass

    sqlite_db = tmp_path / "myws" / "collections.sqlite"  # the local path, IGNORED under PG
    cases_store.save_case("pg_case", {"case_id": "pg_case", "k": "v"}, db_path=sqlite_db)

    with psycopg.connect(url) as c:
        row = c.execute(
            "SELECT workspace_id, payload FROM cases WHERE case_id='pg_case'"
        ).fetchone()
    assert row is not None
    assert row[0] == "myws"  # workspace_id derived from .../myws/collections.sqlite
    assert row[1] == {"case_id": "pg_case", "k": "v"}  # JSONB, parsed

    if sqlite_db.exists():
        tbls = sqlite3.connect(sqlite_db).execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cases'"
        ).fetchall()
        assert tbls == [], f"SQLite was written under LITHRIM_DB_URL=postgres: {tbls}"
