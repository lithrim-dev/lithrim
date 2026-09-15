"""GRADE-ABORT-1: a grade whose judge calls all fail on auth/config stops instead of billing on.

Found 2026-09-15 reviewing v0.1.30 (and hit live during the reproduction run, when the Azure key
started returning 401 mid-run): every judge call failed, each case recorded a WARN vote with no
served model, and the job ran to completion and reported a scorecard built from nothing. An
auth/config failure is the same for every case — the key, the deployment or the endpoint is
wrong — so the honest move is to stop and say which. A provider REFUSAL (a content filter) is
case-specific, stays a miss, and never aborts the cohort."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402
from tests.bff.test_corpus_grade_loop import _envelope, _write_corpus  # noqa: E402

AGENT = "abort_agent"


def _row(cid, *, errors, verdict="needs_review"):
    """A row as _grade_row builds it: the case graded, but every judge call failed."""
    return {
        "case_id": cid, "verdict": verdict, "findings": [], "units": [],
        "votes": [{"judge_role": "risk_judge", "vote": "WARN", "served_model": None, "errors": errors}],
        "judge_errors": 1, "run_id": f"run-{cid}",
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        bff.workspace, "get_active_workspace",
        lambda: types.SimpleNamespace(out_dir=out, pack=bff.workspace.DEFAULT_PACK, packs_dir=None, name="abort_ws"),
    )
    monkeypatch.setattr(bff, "calibration_check", lambda recs: {"status": "PASS", "n_cases": len(recs)})
    monkeypatch.setattr(bff, "_JOBS", {})
    _write_corpus(out, [_envelope(f"c{i}", context=f"Doctor: {i}") for i in range(8)])
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app), out, monkeypatch
    finally:
        bff.app.dependency_overrides.clear()


def _wait(cli, job_id, timeout=10):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        job = cli.get(f"/v1/jobs/{job_id}").json()
        if job["status"] not in ("running",):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def _run(cli, monkeypatch, rows_for):
    graded = []

    def _fake_row(cid, **kw):
        graded.append(cid)
        return rows_for(cid)

    monkeypatch.setattr(bff, "_grade_row", _fake_row)
    res = cli.post(
        "/v1/cases/grade",
        json={"agent": AGENT, "in_process": True, "background": True, "confirm": True},
    )
    assert res.status_code == 202, res.text
    return _wait(cli, res.json()["job_id"]), graded


@pytest.mark.parametrize(
    "message",
    [
        "AuthenticationError: Error code: 401 - Access denied due to invalid subscription key",
        "Error code: 403 - PermissionDenied",
        "DeploymentNotFound: The API deployment for this resource does not exist",
    ],
)
def test_a_run_of_auth_failures_fails_the_job_with_the_reason(client, message):
    cli, _out, monkeypatch = client
    job, graded = _run(cli, monkeypatch, lambda cid: _row(cid, errors=[message]))
    assert job["status"] == "failed", job
    assert len(graded) < 8, "the cohort stopped instead of billing through every case"
    assert "judge" in job["error"].lower() and str(bff._AUTH_ABORT_AFTER) in job["error"]
    assert message.split(":")[0] in job["error"] or message[:20] in job["error"]


def test_a_content_filter_refusal_is_a_miss_and_never_aborts(client):
    cli, _out, monkeypatch = client
    job, graded = _run(
        cli, monkeypatch,
        lambda cid: _row(cid, errors=["content_filter: the response was filtered by the provider"]),
    )
    assert job["status"] == "done" and len(graded) == 8


def test_an_auth_failure_that_recovers_does_not_abort(client):
    cli, _out, monkeypatch = client

    def rows(cid):
        if cid in ("c0", "c1"):
            return _row(cid, errors=["Error code: 401 - invalid api key"])
        return {"case_id": cid, "verdict": "approve", "findings": [], "votes": [], "judge_errors": 0}

    job, graded = _run(cli, monkeypatch, rows)
    assert job["status"] == "done" and len(graded) == 8


def test_the_partial_rows_are_kept_so_the_job_can_be_resumed(client):
    cli, out, monkeypatch = client
    job, _graded = _run(
        cli, monkeypatch, lambda cid: _row(cid, errors=["Error code: 401 - invalid api key"])
    )
    import json

    on_disk = json.loads((out / "jobs" / f"{job['job_id']}.json").read_text())
    assert on_disk["status"] == "failed" and on_disk["rows"], "the graded rows survive the abort"
