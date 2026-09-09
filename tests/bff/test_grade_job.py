"""GRADE-JOB-1: a cohort grade as a resumable background job with progress.

POST /v1/cases/grade is one synchronous request; 90 cases on a live judge is ~10 minutes in
one HTTP call, which the shell cannot survive and a CLI only survives with a long timeout.
``background: true`` returns a job id at once, GET /v1/jobs/{id} reports done/total and the
rows so far, the job file under the workspace out dir survives a BFF restart, and
``resume: <job_id>`` grades only the cases that have no verdict yet. The final ``result`` is
the SAME {matrix, summary, scorecard} envelope the synchronous call returns."""

from __future__ import annotations

import json
import sys
import threading
import time
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
from tests.bff.test_corpus_grade_loop import _envelope, _stub_record, _write_corpus  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name="job_agent"), db_path=db_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    fake_ws = types.SimpleNamespace(
        out_dir=out, pack=bff.workspace.DEFAULT_PACK, packs_dir=None, name="job_ws"
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: fake_ws)
    captured: list[str] = []
    gate = threading.Event()
    gate.set()

    def _capturing_run(agent, **kw):
        gate.wait(5)
        captured.append(agent.dataset.case_id)
        return _stub_record(agent, **kw)

    monkeypatch.setattr(bff.run_eval, "run", _capturing_run)
    monkeypatch.setattr(
        bff, "calibration_check", lambda recs: {"status": "PASS", "n_cases": len(recs)}
    )
    monkeypatch.setattr(bff, "_JOBS", {})
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app), out, captured, gate
    finally:
        bff.app.dependency_overrides.clear()


def _wait_done(cli, job_id, timeout=10) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = cli.get(f"/v1/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_background_grade_returns_a_job_and_the_same_envelope_when_done(client):
    cli, out, captured, _gate = client
    _write_corpus(
        out,
        [_envelope("case_a_bad", context="Doctor: a"), _envelope("case_b_ok", context="Doctor: b")],
    )
    res = cli.post(
        "/v1/cases/grade", json={"agent": "job_agent", "in_process": True, "background": True}
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "running" and body["total"] == 2 and body["job_id"]
    job = _wait_done(cli, body["job_id"])
    assert job["status"] == "done" and job["done"] == 2 and job["total"] == 2
    result = job["result"]
    assert {r["case_id"] for r in result["matrix"]} == {"case_a_bad", "case_b_ok"}
    assert result["summary"]["graded"] == 2 and "scorecard" in result
    assert set(captured) == {"case_a_bad", "case_b_ok"}
    # the job file survives on disk under the workspace out dir
    on_disk = json.loads((out / "jobs" / f"{body['job_id']}.json").read_text())
    assert on_disk["status"] == "done" and len(on_disk["rows"]) == 2


def test_progress_is_visible_while_a_job_runs_and_a_second_job_is_refused(client):
    cli, out, _captured, gate = client
    _write_corpus(
        out,
        [_envelope("case_a_bad", context="Doctor: a"), _envelope("case_b_ok", context="Doctor: b")],
    )
    gate.clear()  # hold every grade call
    body = cli.post("/v1/cases/grade", json={"agent": "job_agent", "background": True}).json()
    mid = cli.get(f"/v1/jobs/{body['job_id']}").json()
    assert mid["status"] == "running" and mid["done"] == 0 and mid["total"] == 2
    dup = cli.post("/v1/cases/grade", json={"agent": "job_agent", "background": True})
    assert dup.status_code == 409 and body["job_id"] in dup.json()["detail"]
    gate.set()
    assert _wait_done(cli, body["job_id"])["done"] == 2


def test_resume_grades_only_the_cases_without_a_verdict(client):
    cli, out, captured, _gate = client
    _write_corpus(
        out,
        [_envelope("case_a_bad", context="Doctor: a"), _envelope("case_b_ok", context="Doctor: b")],
    )
    # a job that died after one case: one graded row, one errored row, status failed
    job_id = "job-interrupted"
    (out / "jobs").mkdir()
    (out / "jobs" / f"{job_id}.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "agent": "job_agent",
                "status": "failed",
                "error": "process died",
                "targets": ["case_a_bad", "case_b_ok"],
                "total": 2,
                "done": 1,
                "rows": [
                    {
                        "case_id": "case_a_bad",
                        "verdict": "reject",
                        "findings": ["INCOMPLETE_DOCUMENTATION"],
                        "votes": [],
                        "run_id": "run-case_a_bad",
                    },
                    {"case_id": "case_b_ok", "error": "connection reset"},
                ],
                "request": {"live": False, "in_process": True, "strict": False},
            }
        )
    )
    res = cli.post(
        "/v1/cases/grade", json={"agent": "job_agent", "resume": job_id, "background": True}
    )
    assert res.status_code == 202 and res.json()["job_id"] == job_id and res.json()["done"] == 1
    job = _wait_done(cli, job_id)
    assert captured == ["case_b_ok"], "only the case without a verdict is graded again"
    rows = {r["case_id"]: r for r in job["result"]["matrix"]}
    assert rows["case_a_bad"]["verdict"] == "reject" and rows["case_b_ok"]["verdict"] == "approve"
    assert job["result"]["summary"]["graded"] == 2


def test_unknown_job_is_404(client):
    cli, _out, _c, _g = client
    assert cli.get("/v1/jobs/nope").status_code == 404
    assert (
        cli.post("/v1/cases/grade", json={"agent": "job_agent", "resume": "nope"}).status_code
        == 404
    )
