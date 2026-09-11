"""OPTIMIZE-JOB-1: calibrate as a background job on the grade-job pattern.

Found 2026-09-10 in the 150-per-task report run: POST /v1/judges/{role}/optimize ran the
optimizer subprocess inside the request with a hardcoded ten-minute limit, so a calibration of
315 training and 135 dev cases died with subprocess.TimeoutExpired and a 500; the 90-row runs fit
under the limit, which is why nothing caught it. ``background: true`` now returns 202 with a job
id, the record lives with the grade jobs under the workspace out dir (kind "optimize", the role,
the final result block), GET /v1/jobs/{id} reports it, the list can filter by kind, a process
restart reads as interrupted, and a second calibration of the same role while one runs is 409.
The subprocess limit is LITHRIM_OPTIMIZE_TIMEOUT_S (default four hours), and a timeout is a
clear failed state (504 on the synchronous path), never a 500."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROLE = "risk_judge"
AGENT = "ws0_default"
RESULT = {
    "role": ROLE,
    "n_train": 315,
    "n_heldout": 135,
    "baseline": {"graded": 0.5},
    "optimized": {"graded": 0.7},
    "delta": {"graded": 0.2},
    "pin": {
        "pinned": True,
        "reason": "pinned (no pinned score to compare against)",
        "comparable": True,
    },
    "out_of_sample": True,
    "corpus_source": {
        "split": "calibration",
        "calibration": 315,
        "dev": 135,
        "dev_fraction": 0.3,
        "test_untouched": 450,
    },
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    ws = types.SimpleNamespace(
        out_dir=out,
        pack="_core",
        packs_dir=None,
        name="opt_ws",
        collections_db=tmp_path / "c.sqlite",
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: ws)
    monkeypatch.setattr(bff, "_JOBS", {})
    gate = threading.Event()
    gate.set()
    calls: list[dict] = []
    behaviour = {"raise": None}

    def _fake(**kw):
        calls.append(kw)
        gate.wait(5)
        if behaviour["raise"] is not None:
            raise behaviour["raise"]
        return dict(RESULT)

    monkeypatch.setattr(bff, "_optimize_via_subprocess", _fake)
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "c.sqlite"
    bff.app.dependency_overrides[bff.get_config_db] = lambda: tmp_path / "config.sqlite"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    try:
        yield TestClient(bff.app), out, gate, calls, behaviour
    finally:
        bff.app.dependency_overrides.clear()


def _wait(cli, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = cli.get(f"/v1/jobs/{job_id}").json()
        if job["status"] not in ("running",):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def _start(cli, **extra):
    return cli.post(
        f"/v1/judges/{ROLE}/optimize",
        json={"confirm": True, "background": True, "agent": AGENT, "split": "calibration", **extra},
    )


def test_background_optimize_returns_a_job_and_the_full_result_block(env):
    cli, out, gate, calls, _ = env
    gate.clear()
    res = _start(cli)
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["kind"] == "optimize" and body["role"] == ROLE and body["status"] == "running"
    mid = cli.get(f"/v1/jobs/{body['job_id']}").json()
    assert mid["status"] == "running" and mid["kind"] == "optimize"
    dup = _start(cli)
    assert dup.status_code == 409 and body["job_id"] in dup.json()["detail"]
    assert bff._running_job_for(AGENT) is None, "a running calibration does not block a grade"
    gate.set()
    job = _wait(cli, body["job_id"])
    assert job["status"] == "done" and job["finished"]
    r = job["result"]
    assert r["delta"]["graded"] == 0.2 and r["pin"]["pinned"] is True and r["out_of_sample"] is True
    assert r["corpus_source"]["dev"] == 135
    assert calls[0]["split"] == "calibration" and calls[0]["role"] == ROLE
    on_disk = json.loads((out / "jobs" / f"{body['job_id']}.json").read_text())
    assert on_disk["status"] == "done" and on_disk["kind"] == "optimize"
    listed = cli.get(f"/v1/jobs?agent={AGENT}&kind=optimize").json()["jobs"]
    assert [(j["job_id"], j["kind"], j["role"]) for j in listed] == [
        (body["job_id"], "optimize", ROLE)
    ]
    assert cli.get(f"/v1/jobs?agent={AGENT}&kind=grade").json()["jobs"] == []


def test_a_refusal_inside_the_optimizer_is_a_failed_job_with_its_reason(env):
    cli, _out, _gate, _calls, behaviour = env
    behaviour["raise"] = bff.HTTPException(
        status_code=422, detail="Not enough graded cases to calibrate yet"
    )
    job = _wait(cli, _start(cli).json()["job_id"])
    assert job["status"] == "failed" and "Not enough graded cases" in job["error"]
    assert job["result"] is None


def test_a_restart_leaves_an_optimize_job_interrupted_and_it_cannot_be_resumed_as_a_grade(env):
    cli, out, *_ = env
    (out / "jobs").mkdir(exist_ok=True)
    (out / "jobs" / "job-opt-orphan.json").write_text(
        json.dumps(
            {
                "job_id": "job-opt-orphan",
                "kind": "optimize",
                "role": ROLE,
                "agent": AGENT,
                "status": "running",
                "error": None,
                "result": None,
                "started": "2026-09-10T20:00:00+00:00",
                "finished": None,
            }
        )
    )
    got = cli.get("/v1/jobs/job-opt-orphan").json()
    assert got["status"] == "interrupted" and "restarted" in got["error"]
    res = cli.post(
        "/v1/cases/grade", json={"agent": AGENT, "resume": "job-opt-orphan", "background": True}
    )
    assert res.status_code == 422 and "optimize" in res.json()["detail"]


# ── the subprocess limit: configurable, and a timeout is never a 500 ──────────────────────
def _real(monkeypatch, tmp_path, run):
    monkeypatch.setattr(bff, "_hydrate_role_bindings_into_env", lambda: None)
    monkeypatch.setattr(bff.subprocess, "run", run)
    ws = types.SimpleNamespace(name="ws", pack="_core", packs_dir=None)
    return lambda: bff._optimize_via_subprocess(
        role=ROLE, ws=ws, collections_db=tmp_path / "c.db", out_dir=tmp_path / "out", limit=None
    )


def test_the_optimizer_limit_comes_from_the_environment_with_a_long_default(monkeypatch, tmp_path):
    seen = {}

    def _run(cmd, env=None, **kw):
        seen["timeout"] = kw.get("timeout")
        return types.SimpleNamespace(
            returncode=0, stdout='__OPTIMIZE_JSON__{"error": "stop here"}', stderr=""
        )

    call = _real(monkeypatch, tmp_path, _run)
    monkeypatch.delenv("LITHRIM_OPTIMIZE_TIMEOUT_S", raising=False)
    with pytest.raises(bff.HTTPException):
        call()
    assert seen["timeout"] >= 3600 * 2, "well above an hour by default"
    monkeypatch.setenv("LITHRIM_OPTIMIZE_TIMEOUT_S", "7200")
    with pytest.raises(bff.HTTPException):
        call()
    assert seen["timeout"] == 7200


def test_an_optimizer_timeout_is_a_clear_504_not_a_500(monkeypatch, tmp_path):
    def _run(cmd, env=None, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    monkeypatch.setenv("LITHRIM_OPTIMIZE_TIMEOUT_S", "60")
    with pytest.raises(bff.HTTPException) as exc:
        _real(monkeypatch, tmp_path, _run)()
    assert exc.value.status_code == 504
    assert "60" in exc.value.detail and "LITHRIM_OPTIMIZE_TIMEOUT_S" in exc.value.detail


def test_the_per_case_grade_limit_is_configurable_too(monkeypatch):
    monkeypatch.delenv("LITHRIM_GRADE_TIMEOUT_S", raising=False)
    assert bff._subprocess_timeout("LITHRIM_GRADE_TIMEOUT_S", 600) == 600
    monkeypatch.setenv("LITHRIM_GRADE_TIMEOUT_S", "1200")
    assert bff._subprocess_timeout("LITHRIM_GRADE_TIMEOUT_S", 600) == 1200
    monkeypatch.setenv("LITHRIM_GRADE_TIMEOUT_S", "soon")
    assert bff._subprocess_timeout("LITHRIM_GRADE_TIMEOUT_S", 600) == 600, (
        "a bad value keeps the default"
    )
