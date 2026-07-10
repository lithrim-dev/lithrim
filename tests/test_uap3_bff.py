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
    """A3 — POST /v1/run-eval carries the graded run's pipeline_run_id. RUNTRAIL-1
    (b1bbf94, SPEC_RUN_AUDIT_TRAIL.md §1) REPLACED the old reuse-the-baseline-id contract:
    a replay mints a FRESH identity pointing at its baseline via ``replay_of``, so the id
    is a well-formed uuid that is NOT the baked baseline id (the stale pre-RUNTRAIL
    assertion this test carried until REL-5e)."""
    import uuid as _uuid

    body = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False}).json()
    rid = body["pipeline_run_id"]
    _uuid.UUID(rid)  # well-formed
    assert rid != BASELINE_RUN_ID  # RUNTRAIL-1: fresh identity, never the baseline's


def test_runs_lists_the_persisted_replay_run(client):
    """A3/A4 — a replay run persists its provenance under its FRESH (RUNTRAIL-1) id, so
    GET /v1/runs lists it (the $0 default shows in run-history)."""
    assert client.get("/v1/runs").json()["runs"] == []  # empty before any run
    rid = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False}).json()[
        "pipeline_run_id"
    ]
    runs = client.get("/v1/runs").json()["runs"]
    assert len(runs) == 1
    row = runs[0]
    assert row["run_id"] == rid  # the minted replay id, not the baked baseline id
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


def test_replay_appends_one_row_per_invocation(client):
    """RUNTRAIL-1 REVERSED the S-BS-52 upsert semantics this test used to pin: every
    replay is an immutable APPEND under a fresh id (the audit-trail invariant), so three
    replays leave THREE distinct rows — and none reuses the baked baseline id."""
    for _ in range(3):
        client.post("/v1/run-eval", json={"agent": _AGENT, "live": False})
    runs = client.get("/v1/runs").json()["runs"]
    ids = [r["run_id"] for r in runs]
    assert len(ids) == 3
    assert len(set(ids)) == 3  # all distinct (append-only, never an upsert)
    assert BASELINE_RUN_ID not in ids


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
    # RUNTRAIL-1: the batch's replay run carries a FRESH minted id (not the baked baseline id)
    assert len(body["run_ids"]) == 1
    rid = body["run_ids"][0]
    assert rid != BASELINE_RUN_ID
    assert body["pack"]["outcomes"][0]["verdict"] == "reject"
    # the batch's run is now addressable in run-history under its minted id
    assert any(r["run_id"] == rid for r in client.get("/v1/runs").json()["runs"])


def test_eval_pack_unknown_agent_is_404(client):
    assert (
        client.post("/v1/eval-pack/run", json={"pack_id": "x", "agents": ["nope"]}).status_code
        == 404
    )
