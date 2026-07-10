"""RUNTRAIL-7 — `grade_path` is stamped on the persisted blob + surfaced in the read API.

SPEC_RUN_AUDIT_TRAIL.md §3 (Identity: `grade_path` records HOW each verdict was produced —
`replay|in_process|live`). Closes seam S-RUNTRAIL-6-1: `grade_path` was computed in
`run_eval.run` but written ONLY to the API-response dict (`build_record`), never to the
persisted `PipelineProvenance` blob, so the trail did not record the grade path.

Hermetic + $0: the replay path grades the neutral `_core` house fixture through
`run_eval.run` against a tmp db (no model, no network). The live/in_process paths are
PAID end-to-end, so they are exercised at the unit level against the SAME persist helpers
`run()` calls (`_persist_run_provenance` for live; `_enrich_run_blob` post-save for
in_process) — proving the stamp reaches the persisted doc without a paid grade.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from lithrim_bench.runtime.pipeline.provenance import SqliteProvenanceStore
from tests._house_fixture import HOUSE_CASE_ID, house_agent

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_eval  # noqa: E402


# ── A1 — a replay grade persists grade_path == "replay" (end-to-end, $0) ────────
def test_replay_persists_grade_path(tmp_path):
    """A1: a persisted blob from a replay grade carries ``grade_path == 'replay'``.
    Grades the house fixture through ``run_eval.run`` (replay, $0) and reads the blob back
    from the store the run persisted to."""
    db = tmp_path / "collections.sqlite"
    agent = house_agent()
    rec = run_eval.run(agent, collections_db=db, out_dir=tmp_path / "o")
    run_id = rec["result"]["provenance"]["pipeline_run_id"]

    blob = asyncio.run(SqliteProvenanceStore(db_path=db).find_by_id(run_id))
    assert blob is not None, "the replay grade must have persisted a run-history row"
    assert blob.get("grade_path") == "replay", (
        "the persisted blob must record grade_path='replay' (SPEC §3 Identity)"
    )


# ── A1 — live: the live persist helper stamps grade_path == "live" ──────────────
def test_live_persist_helper_stamps_grade_path(tmp_path):
    """A1 (live): ``_persist_run_provenance`` — the helper ``run()`` calls on the live
    path — writes ``grade_path`` into the persisted doc. Unit-level (live grading is paid),
    against the SAME store seam."""
    db = tmp_path / "collections.sqlite"
    agent = house_agent()
    result = {
        "provenance": {
            "pipeline_run_id": "live-run-1",
            "verdict": "WARN",
            "gate_decision": "pass",
        }
    }
    run_eval._persist_run_provenance(
        result, agent, grade_sig="sig", grade_path="live", collections_db=db
    )
    blob = asyncio.run(SqliteProvenanceStore(db_path=db).find_by_id("live-run-1"))
    assert blob is not None
    assert blob.get("grade_path") == "live"


# ── A3 — in_process: the post-save enrich patch stamps grade_path == "in_process" ─
def test_in_process_enrich_stamps_grade_path(tmp_path):
    """A3: the in_process path persists via the orchestrator (fire-and-forget) then
    ``run_eval`` patches the saved blob POST-save in ``_enrich_run_blob`` (above the frozen
    seam — it already re-stamps agent_id/case_id/grade_signature). That patch must also
    write ``grade_path == 'in_process'``. Seed the orchestrator's bare blob, then enrich."""
    db = tmp_path / "collections.sqlite"
    store = SqliteProvenanceStore(db_path=db)
    asyncio.run(
        store.save_blob(
            {"pipeline_run_id": "ip-run-1", "verdict": "BLOCK", "gate_decision": "fail"}
        )
    )
    run_eval._enrich_run_blob(
        "ip-run-1",
        [],
        in_process=True,
        case_id=HOUSE_CASE_ID,
        agent_id="house_test",
        grade_sig="sig",
        grade_path="in_process",
        collections_db=db,
    )
    blob = asyncio.run(store.find_by_id("ip-run-1"))
    assert blob is not None
    assert blob.get("grade_path") == "in_process"


# ── model: PipelineProvenance carries grade_path (additive, optional) ───────────
def test_pipeline_provenance_model_has_grade_path():
    from lithrim_bench.runtime.pipeline.models import PipelineProvenance

    fields = PipelineProvenance.model_fields
    assert "grade_path" in fields, "PipelineProvenance must declare grade_path (additive)"
    # additive + optional: an existing blob with no grade_path still parses.
    inst = PipelineProvenance(
        pipeline_run_id="x",
        org_id="o",
        timestamp="2026-06-30T00:00:00+00:00",
        request_hash="h",
        stages_executed=[],
    )
    assert inst.grade_path is None
