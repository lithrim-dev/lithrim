"""RUNTRAIL-7 (read-surface) — the run audit READ-API surfaces `grade_path`.

Complement to the persist work (`tests/test_run_audit_trail_grade_path.py`): once the blob
carries `grade_path`, `GET /v1/runs/{id}/audit` and `GET /v1/runs` must project it so a
consumer can see HOW each verdict was produced (SPEC_RUN_AUDIT_TRAIL.md §3 Identity).

Hermetic + $0: TestClient + a tmp `collections_db`, blobs persisted through the SAME store
factory the BFF reads through (mirror of `test_run_audit_api.py`). No network, no model.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

from lithrim_bench.harness.backend import provenance_store_for, run_coro

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _blob(run_id: str, *, grade_path: str | None = None, verdict: str = "approve") -> dict:
    return {
        "pipeline_run_id": run_id,
        "replay_of": None,
        "grade_path": grade_path,
        "agent_id": "audit_agent",
        "case_id": "audit_case",
        "timestamp": "2026-06-30T00:00:00+00:00",
        "verdict": verdict,
        "gate_decision": "pass",
        "stages_executed": ["semantic"],
        "stage_results": {"semantic": {"judge_votes": [], "evidence": []}},
    }


@pytest.fixture
def client(tmp_path):
    collections_db = tmp_path / "coll.sqlite"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: collections_db
    try:
        yield TestClient(bff.app), collections_db
    finally:
        bff.app.dependency_overrides.clear()


def _save(collections_db: Path, blob: dict) -> None:
    run_coro(provenance_store_for(collections_db).save_blob(blob))


def test_audit_report_surfaces_grade_path(client):
    cli, collections_db = client
    rid = str(uuid.uuid4())
    _save(collections_db, _blob(rid, grade_path="live"))

    body = cli.get(f"/v1/runs/{rid}/audit").json()
    assert "grade_path" in body, "audit report must carry grade_path"
    assert body["grade_path"] == "live"


def test_runs_list_rows_surface_grade_path(client):
    cli, collections_db = client
    live = str(uuid.uuid4())
    replay = str(uuid.uuid4())
    _save(collections_db, _blob(live, grade_path="live"))
    _save(collections_db, _blob(replay, grade_path="replay"))

    rows = cli.get("/v1/runs").json()["runs"]
    by_id = {r["run_id"]: r for r in rows}
    assert by_id[live]["grade_path"] == "live"
    assert by_id[replay]["grade_path"] == "replay"
