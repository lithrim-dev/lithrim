"""PERSIST-2c: the PG/SQLite adapter split (connection-factory + dialect + tier:pro
PostgresProvenanceStore + yoyo migrations). A1–A6, written RED before the implementation.

A1 (url resolution + factory): resolve_db_url defaults to SQLite (unset LITHRIM_DB_URL),
    honours the env + an explicit path; make_provenance_store yields a SqliteProvenanceStore
    by default and a PostgresProvenanceStore for a postgres url (psycopg only needed to USE it).
A2 (dialect): the SQL dialect boundary — param style ?/%s, JSON column TEXT/JSONB, the
    SQLite JSON codec round-trips (canonical), decode(None)→None.
A3 (the ProvenanceStore contract): the SAME save/find/latest_for/list_versions + versioning
    assertions run against SQLite (always) and Postgres (skipped unless LITHRIM_DB_URL → a
    reachable PG) — the faithfulness guarantee across two impls.
A4 (tier:pro gating): the Postgres backend is license-gated (fail-closed under a denying
    LITHRIM_BENCH_LICENSE); SQLite is NEVER gated.
A5 (PG store is contract-shaped + importable without psycopg): PostgresProvenanceStore
    implements the Protocol + imports on the stdlib core (psycopg is lazy).
A6 (frozen / scope + no new core dep): SqliteProvenanceStore byte-identical; the core does
    not import psycopg/yoyo at load; the core deps are unchanged; _apply_consensus 0-delta.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lithrim_bench.harness.backend import (
    Dialect,
    backend_of,
    make_provenance_store,
    resolve_db_url,
)
from lithrim_bench.runtime.pipeline.models import PipelineProvenance, StageResult
from lithrim_bench.runtime.pipeline.provenance import (
    PostgresProvenanceStore,
    ProvenanceStore,
    SqliteProvenanceStore,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _prov(run_id: str, *, org_id: str = "orgX", verdict: str = "WARN", **over) -> PipelineProvenance:
    fields = {
        "pipeline_run_id": run_id,
        "org_id": org_id,
        "timestamp": datetime(2026, 6, 18, tzinfo=timezone.utc),
        "request_hash": "h",
        "stages_executed": ["semantic"],
        "stage_results": {"semantic": StageResult(status="WARN", evidence=[])},
        "verdict": verdict,
        "gate_decision": "pass",
        "findings": [],
    }
    fields.update(over)
    return PipelineProvenance(**fields)


# ── A1 (url resolution + factory) ─────────────────────────────────────────────


def test_resolve_db_url_and_backend_of(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    assert backend_of(resolve_db_url(None)) == "sqlite"  # default
    assert backend_of("postgresql://u@h/db") == "postgres"
    assert backend_of("postgres://u@h/db") == "postgres"
    assert backend_of(resolve_db_url(tmp_path / "x.sqlite")) == "sqlite"  # explicit path
    monkeypatch.setenv("LITHRIM_DB_URL", "postgresql://x@y/z")
    assert backend_of(resolve_db_url(None)) == "postgres"  # env override


def test_factory_sqlite_default_and_postgres_construction(tmp_path, monkeypatch):
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    monkeypatch.delenv("LITHRIM_BENCH_LICENSE", raising=False)
    assert isinstance(make_provenance_store(tmp_path / "p.sqlite"), SqliteProvenanceStore)
    # a postgres url constructs the PG store; psycopg is only needed to USE it
    assert isinstance(make_provenance_store("postgresql://u@h/db"), PostgresProvenanceStore)


def test_provenance_store_for_precedence(tmp_path, monkeypatch):
    """The grade-path helper: LITHRIM_DB_URL (managed PG) wins, else the local SQLite path
    (byte-identical to before — the default grade path is unchanged)."""
    from lithrim_bench.harness.backend import provenance_store_for

    monkeypatch.delenv("LITHRIM_BENCH_LICENSE", raising=False)
    monkeypatch.delenv("LITHRIM_DB_URL", raising=False)
    assert isinstance(provenance_store_for(tmp_path / "p.sqlite"), SqliteProvenanceStore)
    monkeypatch.setenv("LITHRIM_DB_URL", "postgresql://u@h/db")
    assert isinstance(provenance_store_for(tmp_path / "p.sqlite"), PostgresProvenanceStore)


# ── A2 (dialect) ──────────────────────────────────────────────────────────────


def test_dialect_param_and_json():
    s, p = Dialect("sqlite"), Dialect("postgres")
    assert s.placeholder == "?" and p.placeholder == "%s"
    assert s.json_type == "TEXT" and p.json_type == "JSONB"
    obj = {"b": 1, "a": [2, 3]}
    assert s.encode_json(obj) == json.dumps(obj, sort_keys=True)  # canonical TEXT
    assert s.decode_json(s.encode_json(obj)) == obj
    assert s.decode_json(None) is None


# ── A3 (the ProvenanceStore contract — SQLite always, Postgres gated) ──────────


def _run_provenance_contract(make_store):
    """The faithfulness contract every ProvenanceStore impl must satisfy."""
    store = make_store()
    asyncio.run(store.save(_prov("r1", verdict="WARN"), agent_id="ag", case_id="c1"))
    asyncio.run(store.save(_prov("r2", verdict="BLOCK"), agent_id="ag", case_id="c1"))
    asyncio.run(store.save(_prov("r3"), agent_id="ag", case_id="c2"))

    got = asyncio.run(store.find_by_id("r2"))
    assert got["verdict"] == "BLOCK" and got["agent_id"] == "ag" and got["case_id"] == "c1"

    head = asyncio.run(store.latest_for("ag", "c1"))
    assert head["pipeline_run_id"] == "r2"  # newest version of the lineage
    assert [v["pipeline_run_id"] for v in asyncio.run(store.list_versions("ag", "c1"))] == ["r2", "r1"]
    assert [v["pipeline_run_id"] for v in asyncio.run(store.list_versions("ag", "c2"))] == ["r3"]
    assert asyncio.run(store.latest_for("ag", "nope")) is None

    # same-id re-save (the withstands re-embed / replay re-run path) — both backends UPDATE
    # the live row in place (the latest write wins) and keep ONE live version of that id; the
    # lineage addressing is unchanged. (Critic OQ: lock the same-id versioning, not just the
    # distinct-id live path the calibration history uses.)
    asyncio.run(store.save(_prov("r2", verdict="WARN"), agent_id="ag", case_id="c1"))
    assert asyncio.run(store.find_by_id("r2"))["verdict"] == "WARN"  # last same-id write wins
    assert [v["pipeline_run_id"] for v in asyncio.run(store.list_versions("ag", "c1"))] == ["r2", "r1"]


def test_contract_sqlite(tmp_path):
    _run_provenance_contract(lambda: SqliteProvenanceStore(db_path=tmp_path / "contract.sqlite"))


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… to run the PG contract)",
)
def test_contract_postgres():
    pytest.importorskip("psycopg")
    from lithrim_bench.harness.migrations import apply_migrations, reset_provenance

    url = os.environ["LITHRIM_DB_URL"]
    apply_migrations(url)
    reset_provenance(url)  # clean the pipeline_runs/_history tables for the fixed ids
    _run_provenance_contract(lambda: make_provenance_store(url))


# ── A4 (tier:pro gating) ──────────────────────────────────────────────────────


def test_postgres_backend_is_tier_pro_gated(monkeypatch):
    monkeypatch.delenv("LITHRIM_BENCH_LICENSE", raising=False)  # permit-all default
    assert isinstance(make_provenance_store("postgresql://u@h/db"), PostgresProvenanceStore)

    monkeypatch.setenv("LITHRIM_BENCH_LICENSE", "deny-all")
    with pytest.raises(PermissionError, match="tier:pro|licensed|Pro"):
        make_provenance_store("postgresql://u@h/db")
    # SQLite is NEVER gated
    assert isinstance(make_provenance_store("sqlite:///x.db"), SqliteProvenanceStore)


# ── A5 (PG store is contract-shaped + importable without psycopg) ──────────────


def test_postgres_store_implements_the_protocol():
    """The PG store is contract-shaped — a ProvenanceStore with the full method set (psycopg
    is needed only to USE it; the no-driver-AT-LOAD invariant is the subprocess test below)."""
    store = PostgresProvenanceStore("postgresql://u@h/db")
    for m in ("save", "find_by_id", "latest_for", "list_versions"):
        assert callable(getattr(store, m))
    assert isinstance(store, ProvenanceStore)


# ── A6 (frozen / scope + no new core dep) ─────────────────────────────────────


def test_sqlite_store_byte_identical_back_compat(tmp_path):
    store = SqliteProvenanceStore(db_path=tmp_path / "bc.sqlite")
    asyncio.run(store.save(_prov("run-A", org_id="orgX"), agent_id="agent-7"))
    got = asyncio.run(store.find_by_id("run-A"))
    assert got == {**_prov("run-A", org_id="orgX").model_dump(mode="json"), "agent_id": "agent-7"}


def test_core_does_not_import_a_db_driver_at_load():
    # the "no DB driver at LOAD" invariant — checked in a CLEAN subprocess so it is robust to
    # whether another test (the gated PG contract) already imported psycopg in this session
    # (the [pg] extra may be installed; the core must still not pull it at import time).
    code = (
        "import lithrim_bench.harness.backend, lithrim_bench.runtime.pipeline.provenance, sys;"
        "assert 'psycopg' not in sys.modules, 'psycopg imported at load';"
        "assert 'yoyo' not in sys.modules, 'yoyo imported at load';"
        "print('clean')"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "clean" in r.stdout, (r.stdout, r.stderr)


def test_core_dependencies_unchanged():
    # text-scan (tomllib is 3.11+; the bench runs on 3.10) — the core `dependencies = [...]`
    # block must NOT carry a DB driver; the `[pg]` extra carries psycopg + yoyo instead.
    text = (REPO_ROOT / "pyproject.toml").read_text()
    # split on the closing bracket on its own line ("\n]") — a dep like psycopg[binary] has
    # an inner "]" that a bare "]" split would truncate on.
    core_block = text.split("\ndependencies = [", 1)[1].split("\n]", 1)[0]
    assert "psycopg" not in core_block and "yoyo" not in core_block, core_block
    assert "\npg = [" in text, "missing the [pg] optional-dependencies extra"
    pg_block = text.split("\npg = [", 1)[1].split("\n]", 1)[0]
    assert "psycopg" in pg_block and "yoyo" in pg_block, pg_block


def test_consensus_seam_is_zero_delta_vs_acc4973():
    from tests._seam_freeze import assert_compliance_council_carveouts_only

    assert_compliance_council_carveouts_only(REPO_ROOT)


# ── A8 (read-side routing — run-history/audit reflect the active backend) ──────


def test_list_all_round_trips_sqlite(tmp_path):
    """``list_all`` (the run-history read the BFF endpoints now route through the factory)."""
    store = SqliteProvenanceStore(db_path=tmp_path / "la.sqlite")
    for rid in ("r1", "r2"):
        blob = {**_prov(rid).model_dump(mode="json"), "agent_id": "a", "case_id": "c"}
        asyncio.run(store.save_blob(blob))
    ids = {d["pipeline_run_id"] for d in asyncio.run(store.list_all(limit=10))}
    assert ids == {"r1", "r2"}


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… for the PG read seam)",
)
def test_list_all_reads_postgres():
    pytest.importorskip("psycopg")
    from lithrim_bench.harness.migrations import apply_migrations, reset_provenance

    url = os.environ["LITHRIM_DB_URL"]
    apply_migrations(url)
    reset_provenance(url)
    store = make_provenance_store(url)
    for rid in ("rP1", "rP2"):
        blob = {**_prov(rid).model_dump(mode="json"), "agent_id": "a", "case_id": "c"}
        asyncio.run(store.save_blob(blob))
    ids = [d["pipeline_run_id"] for d in asyncio.run(store.list_all(limit=10))]
    assert ids[:2] == ["rP2", "rP1"]  # newest-first (ins_seq DESC)


# ── A7 (grade-path PG routing — the seam goes end-to-end) ─────────────────────


def test_save_blob_round_trips_sqlite(tmp_path):
    """The raw-dict blob seam (what run_eval's persist/enrich helpers carry) round-trips +
    carries the extra addressability fields."""
    store = SqliteProvenanceStore(db_path=tmp_path / "blob.sqlite")
    doc = {
        **_prov("rB").model_dump(mode="json"),
        "agent_id": "ag",
        "case_id": "c1",
        "grade_signature": "sig",
    }
    asyncio.run(store.save_blob(doc))
    got = asyncio.run(store.find_by_id("rB"))
    assert got["agent_id"] == "ag" and got["case_id"] == "c1" and got["grade_signature"] == "sig"


@pytest.mark.skipif(
    not os.environ.get("LITHRIM_DB_URL", "").startswith("postgres"),
    reason="no live Postgres (set LITHRIM_DB_URL=postgresql://… to run the e2e grade→PG)",
)
def test_replay_grade_round_trips_to_postgres(tmp_path):
    """END-TO-END: a $0 replay grade with LITHRIM_DB_URL set persists its provenance blob to
    Postgres (not the local SQLite) — the grade path is routed through the factory."""
    pytest.importorskip("psycopg")
    import psycopg

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_eval

    from lithrim_bench.harness.migrations import apply_migrations, reset_provenance
    from tests._house_fixture import house_agent

    url = os.environ["LITHRIM_DB_URL"]
    apply_migrations(url)
    reset_provenance(url)
    collections_db = tmp_path / "collections.sqlite"
    rec = run_eval.run(house_agent(), collections_db=collections_db, out_dir=tmp_path / "out")
    run_id = rec["result"]["provenance"]["pipeline_run_id"]

    with psycopg.connect(url) as c:
        in_pg = c.execute("SELECT count(*) FROM pipeline_runs WHERE id=%s", (run_id,)).fetchone()[0]
    assert in_pg == 1, "the replay grade's provenance blob did not land in Postgres"
