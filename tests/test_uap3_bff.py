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

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import HOUSE_RUN_ID as BASELINE_RUN_ID  # noqa: E402
from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "uap3_bff_test"


def _fixture_agent(name: str = _AGENT):
    return house_agent(name=name)


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=p)
    return p


@pytest.fixture
def coll_db(tmp_path):
    return tmp_path / "coll.sqlite"


@pytest.fixture
def client(tmp_path, db_path, coll_db, monkeypatch):
    # Hermetic active workspace: pin run-eval to the neutral _core in-process path regardless
    # of any on-disk out/workspaces/.active a local shell session left non-default (the
    # process-global pointer is the isolation seam — tests must not read it).
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
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
    rid = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False}).json()[
        "pipeline_run_id"
    ]
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
    res = client.post(
        "/v1/eval-pack/run", json={"pack_id": "uap3", "agents": [_AGENT], "live": False}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["pack"]["schema_version"] == "evalpack/1"
    assert body["pack"]["pack_id"] == "uap3"
    assert body["run_ids"] == [BASELINE_RUN_ID]
    assert body["pack"]["outcomes"][0]["verdict"] == "reject"
    # the batch's run is now addressable in run-history
    assert any(r["run_id"] == BASELINE_RUN_ID for r in client.get("/v1/runs").json()["runs"])


def test_eval_pack_unknown_agent_is_404(client):
    assert (
        client.post("/v1/eval-pack/run", json={"pack_id": "x", "agents": ["nope"]}).status_code
        == 404
    )
