"""PERSIST-3a slice 2 — the per-case grade result (``reports``) into the single SSOT.

A grade result stops being a loose ``out/<case>.json`` blob + a per-workspace ``ws0.sqlite``
``records`` row: it becomes a row in the one SSOT DB, scoped by ``workspace_id``, with the small
queryable columns projected out (``verdict`` / ``run_id`` / ``scores``) and the full record as
linked JSON (``report``), ``storage_ref`` reserved for the 3b object-store move. Written RED.

A1 (store round-trip + projection): ``save_report`` → ``load_report`` preserves the full record;
    ``list_reports`` exposes the projected ``verdict`` / ``run_id`` / ``scores`` without parsing
    the blob. ``storage_ref`` present + NULL inline.
A2 (persist routes to the SSOT): ``persist()`` dual-writes the record to ``reports``, and
    ``persist.load`` reads it back from the SSOT (the fs blob stays a transition mirror).
A4 (workspace isolation by column): two ``workspace_id``s in ONE table stay isolated.
A3 (SINGLE SSOT — gated on a live Postgres): a report authored under ``LITHRIM_DB_URL=postgres``
    lands in PG ``reports`` with its ``workspace_id`` + projected verdict + JSONB report, local
    SQLite untouched.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest


def _record(verdict: str = "approve", run_id: str = "run-1") -> dict:
    """A minimal grade record in ``run_eval.build_record`` shape (the fields the projection reads)."""
    return {
        "case_id": "c1",
        "agent": "ws0_default",
        "result": {"provenance": {"pipeline_run_id": run_id}},
        "grounded": {"verdict": verdict, "original_verdict": "reject"},
        "composite": {"verdict": "reject"},
        "calibration": {"ece": 0.1, "brier": 0.2},
    }


# ── A1 (the reports store round-trips + projects on SQLite) ───────────────────


def test_save_load_round_trips_and_projects(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import reports_store

    db = tmp_path / "myws" / "ws0.sqlite"
    rec = _record(verdict="approve", run_id="run-7")
    reports_store.save_report("c1", rec, db_path=db, workspace_id="myws")

    assert reports_store.load_report("c1", db_path=db, workspace_id="myws") == rec
    rows = reports_store.list_reports(db_path=db, workspace_id="myws")
    assert len(rows) == 1
    assert rows[0]["case_id"] == "c1"
    assert rows[0]["verdict"] == "approve"  # the GROUNDED (final) verdict, projected
    assert rows[0]["run_id"] == "run-7"
    assert rows[0]["scores"] == {"ece": 0.1, "brier": 0.2}


def test_storage_ref_column_present_and_null_inline(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import reports_store

    db = tmp_path / "myws" / "ws0.sqlite"
    reports_store.save_report("c1", _record(), db_path=db, workspace_id="myws")
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(reports)").fetchall()}
    assert {"workspace_id", "case_id", "run_id", "verdict", "scores", "report", "storage_ref"} <= cols
    ref = sqlite3.connect(db).execute("SELECT storage_ref FROM reports WHERE case_id='c1'").fetchone()[0]
    assert ref is None


def test_report_is_idempotent_on_case_id(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import reports_store

    db = tmp_path / "myws" / "ws0.sqlite"
    reports_store.save_report("c1", _record(verdict="reject"), db_path=db, workspace_id="myws")
    reports_store.save_report("c1", _record(verdict="approve"), db_path=db, workspace_id="myws")
    rows = reports_store.list_reports(db_path=db, workspace_id="myws")
    assert len(rows) == 1 and rows[0]["verdict"] == "approve"  # re-grade overwrites


# ── A4 (workspace isolation by the workspace_id column) ───────────────────────


def test_two_workspaces_in_one_table_are_isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import reports_store

    db = tmp_path / "shared.sqlite"
    reports_store.save_report("c1", _record(verdict="approve"), db_path=db, workspace_id="wsA")
    reports_store.save_report("c1", _record(verdict="reject"), db_path=db, workspace_id="wsB")

    assert reports_store.load_report("c1", db_path=db, workspace_id="wsA")["grounded"]["verdict"] == "approve"
    assert reports_store.load_report("c1", db_path=db, workspace_id="wsB")["grounded"]["verdict"] == "reject"
    assert len(reports_store.list_reports(db_path=db, workspace_id="wsA")) == 1


# ── A2 (persist routes the grade result to the SSOT) ──────────────────────────


def test_persist_writes_report_to_ssot_and_load_reads_it(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    from lithrim_bench.harness import reports_store
    from lithrim_bench.harness.persist import load, persist

    out_dir = tmp_path / "myws" / "out"  # ws.out_dir shape → workspace_id "myws"
    rec = _record(verdict="needs_review", run_id="run-9")
    paths = persist("c1", rec, out_dir=out_dir)

    # the SSOT reports table got the row, workspace_id derived from out_dir
    assert reports_store.load_report("c1", db_path=Path(paths["sqlite"]), workspace_id="myws") == rec
    # persist.load resolves it from the SSOT
    assert load("c1", db_path=Path(paths["sqlite"])) == rec


# ── A3 (SINGLE SSOT — the headline, gated on a live Postgres) ─────────────────


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… for the single-SSOT check)",
)
def test_reports_single_ssot_in_postgres(tmp_path):
    pytest.importorskip("psycopg")
    import psycopg

    from lithrim_bench.harness import reports_store

    url = os.environ["LITHRIM_DB_URL"]
    with psycopg.connect(url, autocommit=True) as c:
        try:
            c.execute("TRUNCATE reports")
        except Exception:  # not provisioned until the store creates it
            pass

    sqlite_db = tmp_path / "myws" / "ws0.sqlite"  # IGNORED under PG
    reports_store.save_report("pg_case", _record(verdict="approve", run_id="r1"),
                              db_path=sqlite_db, workspace_id="myws")

    with psycopg.connect(url) as c:
        row = c.execute(
            "SELECT workspace_id, verdict, run_id, report FROM reports WHERE case_id='pg_case'"
        ).fetchone()
    assert row is not None
    assert row[0] == "myws" and row[1] == "approve" and row[2] == "r1"
    assert row[3]["grounded"]["verdict"] == "approve"  # JSONB, parsed

    if sqlite_db.exists():
        tbls = sqlite3.connect(sqlite_db).execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reports'"
        ).fetchall()
        assert tbls == [], f"SQLite was written under LITHRIM_DB_URL=postgres: {tbls}"
