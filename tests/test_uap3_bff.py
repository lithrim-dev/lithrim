"""UAP-3 BFF acceptance: run ids + run-history + replay-provenance + eval-pack batch
+ the authored-assignment thread (A3/A4/A5/S-BS-52/S-BS-56/S-BS-63).

Hermetic + replay-only ($0): drives the FastAPI BFF over the WS-0 fixtures via a tmp
config DB + a tmp run-history DB (FastAPI dependency overrides). The in-process
authored→flip itself is proven $0/offline in ``test_uap3_grade.py``; here we prove the
BFF THREADS the persisted assignments into the grade call (so the authoring is wired
end-to-end) without paying for a real trio.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
ONTOLOGY_SEED = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"
BASELINE_RUN_ID = "a57bd49d-94cd-4397-8c53-f8cbaad3aec2"  # the fixture baseline's provenance id

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "uap3_bff_test"


def _fixture_agent(name: str = _AGENT) -> Agent:
    return Agent(
        name=name,
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={"disposition": "compose-over-live-v2"},
            ontology_ref="clinical/1",
            ontology_path=str(ONTOLOGY_SEED),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:clinical/1",
        ),
        dataset=Dataset(
            case_id=CASE_ID,
            source=str(FIXTURES / f"case.{CASE_ID}.jsonl"),
            baseline=str(FIXTURES / f"baseline.{CASE_ID}.json"),
        ),
    )


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=p)
    return p


@pytest.fixture
def coll_db(tmp_path):
    return tmp_path / "coll.sqlite"


@pytest.fixture
def client(tmp_path, db_path, coll_db):
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: coll_db
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


# ── S-BS-56: pipeline_run_id surfaced + run-history list ──────────────────────


def test_run_eval_surfaces_pipeline_run_id(client):
    """A3 — POST /v1/run-eval carries the graded run's pipeline_run_id (replay → the
    captured baseline's id)."""
    body = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False}).json()
    assert body["pipeline_run_id"] == BASELINE_RUN_ID


def test_runs_lists_the_persisted_replay_run(client):
    """A3/A4 (S-BS-52) — a replay run persists its provenance, so GET /v1/runs lists
    it (the $0 default shows in run-history)."""
    assert client.get("/v1/runs").json()["runs"] == []  # empty before any run
    client.post("/v1/run-eval", json={"agent": _AGENT, "live": False})
    runs = client.get("/v1/runs").json()["runs"]
    assert len(runs) == 1
    row = runs[0]
    assert row["run_id"] == BASELINE_RUN_ID
    assert row["verdict"] == "BLOCK"
    assert row["agent"] == _AGENT  # backfilled from the eval-profile


def test_run_id_round_trips_to_audit(client):
    """A3 — a listed run_id round-trips to GET /v1/runs/{id}/audit (no 404 for a
    persisted run); the report projects the per-judge votes + verdict."""
    rid = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False}).json()["pipeline_run_id"]
    rep = client.get(f"/v1/runs/{rid}/audit")
    assert rep.status_code == 200
    body = rep.json()
    assert body["run_id"] == rid
    assert body["verdict"] == "BLOCK"
    assert isinstance(body["judges"], list)


def test_replay_run_id_is_idempotent_in_history(client):
    """S-BS-52 by-design: deterministic replay reuses the baseline's fixed id, so
    re-running replay upserts ONE row per baseline (not one-per-invocation)."""
    for _ in range(3):
        client.post("/v1/run-eval", json={"agent": _AGENT, "live": False})
    runs = client.get("/v1/runs").json()["runs"]
    assert len([r for r in runs if r["run_id"] == BASELINE_RUN_ID]) == 1


# ── R6: POST /v1/eval-pack/run ────────────────────────────────────────────────


def test_eval_pack_run_batches_and_surfaces_run_ids(client):
    """A5 — POST /v1/eval-pack/run runs a pack via build_pack and returns the frozen
    pack + run ids; the batch's runs persist to run-history."""
    res = client.post("/v1/eval-pack/run", json={"pack_id": "uap3", "agents": [_AGENT], "live": False})
    assert res.status_code == 200
    body = res.json()
    assert body["pack"]["schema_version"] == "evalpack/1"
    assert body["pack"]["pack_id"] == "uap3"
    assert body["run_ids"] == [BASELINE_RUN_ID]
    assert body["pack"]["outcomes"][0]["verdict"] == "reject"
    # the batch's run is now addressable in run-history
    assert any(r["run_id"] == BASELINE_RUN_ID for r in client.get("/v1/runs").json()["runs"])


def test_eval_pack_unknown_agent_is_404(client):
    assert client.post("/v1/eval-pack/run", json={"pack_id": "x", "agents": ["nope"]}).status_code == 404


# ── S-BS-63: the authored assignment is threaded into the grade ───────────────


def test_authored_assignment_threads_into_the_grade(client, db_path, monkeypatch):
    """A1 wiring (A3) — authoring a judge (PUT /v1/judges) makes the BFF pass that
    role's assigned flags to run_eval.run, so the in-process council is built with the
    authored lens. We capture the kwarg (no paid trio) — the verdict-flip itself is
    proven $0/offline in test_uap3_grade.py."""
    client.put(
        "/v1/judges/risk_judge",
        json={"model": "", "assigned_flags": ["WRONG_DOSAGE"], "validator_refs": []},
    )

    captured: dict = {}

    def _fake_run(agent, **kwargs):
        captured.update(kwargs)
        return {
            "case_id": CASE_ID,
            "result": {"provenance": {"pipeline_run_id": "fake"}, "semantic": {"judge_votes": []}},
            "composite": {"verdict": "reject"},
            "calibration": {"ece": 0.0, "n_with_confidence": 0, "caveat": None},
            "provenance": {
                "grade_path": "in_process",
                "expected_compliance_verdict": "reject",
                "expected_safety_flags": ["WRONG_DOSAGE"],
            },
            "grounded": {},
        }

    monkeypatch.setattr(bff.run_eval, "run", _fake_run)
    client.post("/v1/run-eval", json={"agent": _AGENT, "in_process": True})
    assert captured["assignments"] == {"risk_judge": ("WRONG_DOSAGE",)}
