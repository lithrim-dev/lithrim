"""GRADE-CONFIRM-1: a paid grade crosses the service boundary only with an explicit confirm.

Found 2026-09-15 reviewing v0.1.30: POST /v1/judges/{role}/optimize refuses without
``confirm``, but POST /v1/cases/grade had no confirm field at all — the shell's cost dialog was
the only thing standing between a click and a paid cohort, and the job-resume button bypassed
it entirely (``resumeJob`` posts straight through, and the resumed job keeps the ORIGINAL job's
live/in_process flags, so it bills whatever the first round billed). The service now refuses a
paid grade — new or resumed — without ``confirm: true``. The $0 replay path (neither ``live``
nor ``in_process``) spends nothing and stays confirm-free."""

from __future__ import annotations

import sys
import threading
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

AGENT = "confirm_agent"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: types.SimpleNamespace(
            out_dir=out, pack=bff.workspace.DEFAULT_PACK, packs_dir=None, name="confirm_ws"
        ),
    )
    graded: list[str] = []
    gate = threading.Event()
    gate.set()

    def _run(agent, **kw):
        gate.wait(5)
        graded.append(agent.dataset.case_id)
        return _stub_record(agent, **kw)

    monkeypatch.setattr(bff.run_eval, "run", _run)
    monkeypatch.setattr(bff, "calibration_check", lambda recs: {"status": "PASS", "n_cases": len(recs)})
    monkeypatch.setattr(bff, "_JOBS", {})
    _write_corpus(out, [_envelope("c1", context="Doctor: x"), _envelope("c2", context="Doctor: y")])
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app), out, graded, gate
    finally:
        bff.app.dependency_overrides.clear()


def _grade(cli, **body):
    return cli.post("/v1/cases/grade", json={"agent": AGENT, **body})


def test_a_paid_grade_without_confirm_is_refused_and_nothing_is_graded(client):
    cli, _out, graded, _gate = client
    res = _grade(cli, in_process=True)
    assert res.status_code == 422, res.text
    assert "confirm" in res.json()["detail"].lower()
    assert graded == [], "not one case may be graded by a request that never confirmed the cost"


def test_the_live_backend_is_refused_without_confirm_too(client):
    cli, _out, graded, _gate = client
    assert _grade(cli, live=True).status_code == 422
    assert graded == []


def test_a_background_paid_grade_without_confirm_leaves_no_job_behind(client):
    cli, _out, graded, _gate = client
    assert _grade(cli, in_process=True, background=True).status_code == 422
    assert bff._JOBS == {} and graded == []


def test_a_confirmed_paid_grade_runs(client):
    cli, _out, graded, _gate = client
    res = _grade(cli, in_process=True, confirm=True)
    assert res.status_code == 200, res.text
    assert sorted(graded) == ["c1", "c2"]


def test_the_zero_dollar_replay_needs_no_confirm(client):
    cli, _out, graded, _gate = client
    assert _grade(cli).status_code == 200
    assert sorted(graded) == ["c1", "c2"], "replay spends nothing, so it is not gated"


def _finished_paid_job(cli, gate) -> str:
    """A paid job whose second case never got a verdict — what Resume picks up."""
    gate.clear()
    job_id = _grade(cli, in_process=True, background=True, confirm=True).json()["job_id"]
    gate.set()
    import time

    deadline = time.time() + 10
    while time.time() < deadline:
        if cli.get(f"/v1/jobs/{job_id}").json()["status"] != "running":
            return job_id
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_resuming_a_paid_job_without_confirm_is_refused(client):
    """The finding itself: the resumed job keeps the original paid flags, so a resume that
    never confirmed the cost is a paid run nobody agreed to."""
    cli, _out, graded, gate = client
    job_id = _finished_paid_job(cli, gate)
    graded.clear()
    res = _grade(cli, resume=job_id)
    assert res.status_code == 422 and "confirm" in res.json()["detail"].lower()
    assert graded == []


def test_a_confirmed_resume_runs(client):
    cli, _out, graded, gate = client
    job_id = _finished_paid_job(cli, gate)
    graded.clear()
    assert _grade(cli, resume=job_id, confirm=True).status_code == 202
