"""RUNTRAIL-0: the run audit-trail contract (SPEC_RUN_AUDIT_TRAIL.md §7, gates G1–G6).

The invariant (§1): *every grade execution produces exactly one immutable, uniquely-
identified, timestamped, rehydratable run-history record; the run-history is append-only —
a record is never overwritten or deleted.* This file is the RED contract suite that
RUNTRAIL-1…4 turn GREEN one gate at a time.

Hermetic: no network, no live model, no Synthea. Every gate drives the SQLite default
store (the CE path) directly against a ``tmp_path`` db, or grades the neutral ``_core``
house fixture through ``run_eval.run`` (replay, $0). The Postgres tier has its own gated
contract test (``test_persist2c``); parity is NOT re-asserted here.

RED discipline (driver §2): each gate that current code does NOT satisfy carries
``@pytest.mark.xfail(strict=True, …)`` so the committed suite is GREEN (xfail ≠ fail).
``strict=True`` is mandatory — an accidental pass (a later phase implementing the gate
without removing the marker) FAILS the suite, making the seam handoff mechanical. The
genuine-RED evidence for each xfail gate is captured via ``pytest --runxfail`` and recorded
in the session log; a gate that already HOLDS is asserted truthfully WITHOUT a marker.

xfail → phase mapping:
    G1 (replay overwrite)              → RUNTRAIL-1
    G3 (replay_of lineage)             → RUNTRAIL-1
    G4 (SQLite archive store-parity)   → RUNTRAIL-2
    G5 (projection rebuildable)        → RUNTRAIL-3
    G6 (rehydrate from blob, no model) → RUNTRAIL-4

G2 partially HOLDS on current code: M distinct grades land M find_by_id-able rows (the
append-of-distinct-ids half). Its *rehydratable* half is G6 (xfail-staged there), so G2's
asserted half carries no marker.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

from lithrim_bench.harness import reports_store
from lithrim_bench.harness.replay import provenance_to_result
from lithrim_bench.runtime.pipeline import provenance as provenance_mod
from lithrim_bench.runtime.pipeline.provenance import SqliteProvenanceStore
from tests._house_fixture import (
    HOUSE_CASE_ID,
    HOUSE_CASE_PATH,
    HOUSE_ONTOLOGY_PATH,
    house_agent,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_eval  # noqa: E402


def _prov_doc(run_id: str, *, agent_id: str = "ag", case_id: str = "c1",
              verdict: str = "WARN", **over) -> dict:
    """A minimal valid provenance BLOB (the dict shape ``save_blob`` / the run_eval
    persist helpers carry — not the pydantic model). Self-contained: stamps the
    ``(agent, case_id)`` addressability the store keys lineage on."""
    doc = {
        "pipeline_run_id": run_id,
        "org_id": "orgX",
        "agent_id": agent_id,
        "case_id": case_id,
        "timestamp": "2026-06-30T00:00:00+00:00",
        "request_hash": "h",
        "stages_executed": ["semantic"],
        "verdict": verdict,
        "gate_decision": "pass",
    }
    doc.update(over)
    return doc


def _live_rows(db: Path) -> list[tuple[str, str]]:
    """``(id, json)`` for every row in the live ``pipeline_runs`` table."""
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS pipeline_runs "
                     "(id TEXT PRIMARY KEY, fk TEXT, json TEXT, created_at TEXT)")
        return conn.execute("SELECT id, json FROM pipeline_runs").fetchall()
    finally:
        conn.close()


# ── G1 — N re-grades of one case ⇒ N distinct rows, zero overwrites ────────────


def test_g1_n_regrades_yield_n_distinct_rows(tmp_path):
    """SPEC §7 G1: re-grading one case N times ⇒ N distinct ``pipeline_runs`` rows
    (unique ``run_id``+``created_at``), zero overwrites. RED: the default replay path
    reuses the captured baseline's fixed ``pipeline_run_id`` (``baseline._core_house.json``),
    so PIPELINE_RUNS upserts to one row per baseline — the trail does not grow per run."""
    db = tmp_path / "collections.sqlite"
    agent = house_agent()
    n = 3
    run_ids = []
    for i in range(n):
        rec = run_eval.run(agent, collections_db=db, out_dir=tmp_path / f"o{i}")
        run_ids.append(rec["result"]["provenance"]["pipeline_run_id"])

    rows = asyncio.run(SqliteProvenanceStore(db_path=db).list_all())
    # N executions ⇒ N distinct, append-only rows.
    assert len(rows) == n, f"expected {n} run-history rows, got {len(rows)}"
    assert len({r["pipeline_run_id"] for r in rows}) == n, "run_ids must be distinct per run"


# ── G2 — a cohort of M cases ⇒ M new run-history rows, each find_by_id-able ─────


def test_g2_cohort_of_m_cases_yields_m_findable_rows(tmp_path):
    """SPEC §7 G2 (the asserted half): a cohort grade of M distinct cases lands M new
    run-history rows, each addressable by ``find_by_id``. This HOLDS on current code —
    distinct cases carry distinct ``pipeline_run_id``s, so the doc-shim appends (the
    WS-6d eval-isolation invariant). The cohort routes through ``_grade_case`` →
    ``run_eval`` → ``save_blob`` per case; the hermetic stand-in saves M distinct blobs
    through the SAME store seam the cohort endpoint persists through. The *rehydratable*
    clause of G2 is G6 (xfail-staged there)."""
    db = tmp_path / "collections.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    m = 4
    run_ids = [f"cohort-run-{i}" for i in range(m)]
    for i, rid in enumerate(run_ids):
        asyncio.run(store.save_blob(_prov_doc(rid, case_id=f"case-{i}")))

    rows = asyncio.run(store.list_all())
    assert len(rows) == m, f"expected {m} cohort rows, got {len(rows)}"
    for rid in run_ids:
        assert asyncio.run(store.find_by_id(rid)) is not None, f"{rid} not find_by_id-able"


# ── G3 — a replay row carries replay_of = baseline run_id; baseline unchanged ──


def test_g3_replay_carries_replay_of_and_leaves_baseline_unchanged(tmp_path):
    """SPEC §7 G3: a replay run is a NEW record that POINTS AT its baseline
    (``replay_of`` = the baseline ``run_id``); the baseline row is byte-unchanged after
    the replay. RED: the replay reuses the baseline's id (it does not mint a new one), so
    there is no distinct replay record, and ``PipelineProvenance`` carries no ``replay_of``
    field at all (``models.py``) — the lineage is unrepresentable."""
    db = tmp_path / "collections.sqlite"
    store = SqliteProvenanceStore(db_path=db)

    # Seed an AUTHORITATIVE baseline run for the house agent's (agent, case) lineage and
    # capture its exact persisted bytes. (RUNTRAIL-1 fidelity tweak: a replay's baseline
    # must be a prior grade of the SAME (agent, case) — seeded with the house agent's ids so
    # the append-with-lineage resolver legitimately resolves it. Does not weaken the gate.)
    baseline = _prov_doc("baseline-run", agent_id="house_test",
                         case_id=HOUSE_CASE_ID, verdict="BLOCK")
    asyncio.run(store.save_blob(baseline))
    baseline_before = asyncio.run(store.find_by_id("baseline-run"))

    # Replay-grade it (replay must mint a NEW id pointing at the baseline).
    agent = house_agent()
    rec = run_eval.run(agent, collections_db=db, out_dir=tmp_path / "o")
    replay_run_id = rec["result"]["provenance"]["pipeline_run_id"]

    assert replay_run_id != "baseline-run", "replay must be a distinct record, not a reuse"
    replay_blob = asyncio.run(store.find_by_id(replay_run_id))
    assert replay_blob.get("replay_of") == "baseline-run", "replay must point at its baseline"

    # The baseline row is untouched (append-only: a replay never overwrites its source).
    assert asyncio.run(store.find_by_id("baseline-run")) == baseline_before


# ── G4 — SQLite never loses a record on id reuse (store-level archive parity) ──


def test_g4_sqlite_store_never_loses_a_record_on_id_reuse(tmp_path):
    """SPEC §7 G4: the SQLite store never loses a record on ``run_id`` reuse — archive
    parity with Postgres ``pipeline_runs_history``, READABLE through the store. RED: a
    same-id re-save with different content archives the prior into the raw
    ``pipeline_runs_history`` table (PERSIST-2a ``versioned=True``), BUT no
    ``SqliteProvenanceStore`` method returns it — ``find_by_id`` / ``list_versions`` /
    ``list_all`` all surface only the head, so the prior version is unrecoverable through
    the store's public read interface (no parity with how the trail is consumed)."""
    db = tmp_path / "collections.sqlite"
    store = SqliteProvenanceStore(db_path=db)

    asyncio.run(store.save_blob(_prov_doc("R", verdict="WARN")))
    asyncio.run(store.save_blob(_prov_doc("R", verdict="BLOCK")))

    # The prior (WARN) version must be recoverable through the store, not just raw SQL.
    history = asyncio.run(store.list_history("R"))  # absent today → AttributeError (RED)
    archived_verdicts = {h["verdict"] for h in history}
    assert "WARN" in archived_verdicts, "the prior version must survive store-readably"


# ── G5 — reports_store (projection) is rebuildable from the run-history alone ──


def test_g5_projection_rebuildable_from_run_history_alone(tmp_path):
    """SPEC §7 G5: ``reports_store`` is a DERIVED PROJECTION (latest result per
    ``(workspace, case_id)``), rebuildable from the run-history alone. RED: there is no
    ``rebuild_projection()`` — the projection is only ever written inline at grade time
    (``persist.py`` → ``reports_store.save_report``). We assert the PROPERTY: given a
    run-history with two runs for one case, a rebuild from the run-history reconstructs the
    latest-per-case ``reports`` row WITHOUT re-grading. The function does not exist."""
    db = tmp_path / "collections.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    asyncio.run(store.save_blob(_prov_doc("run-old", case_id="caseA", verdict="WARN")))
    asyncio.run(store.save_blob(_prov_doc("run-new", case_id="caseA", verdict="BLOCK")))

    # absent today → AttributeError (RED): no rebuild path exists.
    rebuild = reports_store.rebuild_projection
    rebuild(run_history_db=db, db_path=tmp_path / "reports.sqlite")

    latest = reports_store.load_report("caseA", db_path=tmp_path / "reports.sqlite")
    assert latest is not None, "projection must be reconstructable from the run-history"
    assert latest.get("verdict") == "BLOCK", "the latest run's verdict must win the projection"


# ── G6 — rehydrate(run_id) reconstructs the verdict from the blob, zero models ─


def test_g6_rehydrate_reconstructs_verdict_with_no_model_call(tmp_path):
    """SPEC §7 G6 / §4: a ``rehydrate(run_id)`` path reconstructs the graded result from
    the stored blob alone — no live model call, no re-grade — yielding the SAME verdict.
    This is the proof the record is self-sufficient (§3). RED: the pieces exist
    (``find_by_id`` + ``provenance_to_result``) but no ``rehydrate`` entrypoint ties them
    into a run_id → verdict reconstruction. We assert the PROPERTY against that absent
    function."""
    db = tmp_path / "collections.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    # A blob whose stage_results carry enough for the adapter to reconstruct a verdict.
    blob = _prov_doc(
        "rehydrate-run",
        verdict="BLOCK",
        stage_results={
            "semantic": {
                "status": "BLOCK",
                "findings": [{"type": "semantic", "severity": "HIGH",
                              "detail": "d", "code": "X"}],
                "evidence": [],
                "judge_votes": [{"judge_role": "j", "vote": "BLOCK", "confidence": 0.9,
                                 "model": "m", "findings": ["X"]}],
            }
        },
        findings=[],
    )
    asyncio.run(store.save_blob(blob))

    # absent today → AttributeError (RED): no rehydrate entrypoint exists.
    rehydrate = provenance_mod.rehydrate
    result = rehydrate("rehydrate-run", db_path=db)
    assert result["verdict"] == "BLOCK", "rehydrate must reconstruct the stored verdict"
    # And it must use the blob, not a re-grade — the adapter is the only legal path.
    adapted = provenance_to_result(asyncio.run(store.find_by_id("rehydrate-run")))
    assert result["verdict"] == adapted["verdict"]


def test_house_fixture_paths_exist():
    """Guard: the neutral house fixture the replay gates lean on is present + hermetic
    (no network/pack). Keeps the xfail gates non-vacuous — they fail on the CONTRACT, not a
    missing fixture. (Not a SPEC gate; a fixture tripwire for G1/G3.)"""
    assert HOUSE_CASE_PATH.exists()
    assert HOUSE_ONTOLOGY_PATH.exists()
    assert HOUSE_CASE_ID == "_core_house_v1"
