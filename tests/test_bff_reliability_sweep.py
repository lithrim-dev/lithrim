"""RIGOR-1 / Q1 (NEW-G3): GET /v1/reliability/{agent}/sweep — the K-sweep read endpoint.

Proves the single-reviewer self-consistency curve is COMPUTED from THIS agent's OWN persisted
runs (the `scores_raw` already captured on each judge vote), agent-scoped, with the honest 404 +
insufficiency contract (no fabricated values). Placed ADJACENT to the reliability endpoint.

RED-before-code. Hermetic: the run store is the ``coll_db`` override. $0 read — no grade, no
model call, no gold dependency (the sweep measures the reviewer against ITSELF).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "reliability_sweep_bff_test"


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name=_AGENT), db_path=p)
    return p


@pytest.fixture
def coll_db(tmp_path):
    return tmp_path / "coll.sqlite"


@pytest.fixture
def client(tmp_path, db_path, coll_db, monkeypatch):
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


def _blob(run_id, case_id, role, scores_raw):
    """A persisted blob carrying ONE reviewer's per-sample scores on a case (the K-split source)."""
    return {
        "pipeline_run_id": run_id,
        "agent_id": _AGENT,
        "case_id": case_id,
        "timestamp": f"2026-07-04T00:00:{run_id[-2:]:0>2}Z",
        "verdict": "PASS",
        "stage_results": {
            "semantic": {
                "judge_votes": [
                    {"judge_role": role, "vote": "PASS", "confidence": None,
                     "model": "m", "scores_raw": scores_raw, "k": len(scores_raw)},
                ],
            }
        },
        "grounded": None,
    }


def _persist(coll_db, blobs):
    store = bff.provenance_store_for(coll_db)
    for b in blobs:
        asyncio.run(store.save_blob(b))


# ── 404 convention ────────────────────────────────────────────────────────────


def test_unknown_agent_is_404(client):
    r = client.get("/v1/reliability/nope_not_an_agent/sweep")
    assert r.status_code == 404


# ── honest empty state ────────────────────────────────────────────────────────


def test_no_runs_is_insufficient_not_zeros(client):
    r = client.get(f"/v1/reliability/{_AGENT}/sweep")
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == _AGENT
    assert body["sweep"]["insufficient"] is True
    assert body["sweep"]["series"] == []


# ── real curve over sampled runs ──────────────────────────────────────────────


def test_sweep_curve_over_sampled_runs(client, coll_db):
    # one reviewer, two cases: c1 flips (B B P P P -> K1 BLOCK, K5 PASS), c2 unanimous PASS.
    _persist(coll_db, [
        _blob("run0001", "c1", "j1", [0.0, 0.0, 1.0, 1.0, 1.0]),
        _blob("run0002", "c2", "j1", [1.0, 1.0, 1.0, 1.0, 1.0]),
    ])
    body = client.get(f"/v1/reliability/{_AGENT}/sweep").json()
    sweep = body["sweep"]
    assert sweep["insufficient"] is False
    by_k = {row["k"]: row for row in sweep["series"]}
    assert set(by_k) == {1, 2, 3, 4, 5}
    # at K=1 c1's BLOCK flips vs its K=5 PASS; c2 never flips -> flip_rate = 1/2
    assert abs(by_k[1]["flip_rate"]["value"] - 0.5) < 1e-9
    # at K=5 nothing flips (K_max is the reference)
    assert by_k[5]["flip_rate"]["value"] == 0.0
    # a real proportion carries a Wilson CI
    assert isinstance(by_k[1]["flip_rate"]["ci"], (list, tuple))


def test_sweep_respects_k_max_query_cap(client, coll_db):
    _persist(coll_db, [_blob("run0001", "c1", "j1", [1.0, 1.0, 1.0, 1.0, 1.0])])
    body = client.get(f"/v1/reliability/{_AGENT}/sweep?k_max=3").json()
    ks = [row["k"] for row in body["sweep"]["series"]]
    assert ks == [1, 2, 3]


def test_sweep_agent_scoped(client, coll_db):
    other = _blob("run9999", "c1", "j1", [0.0, 1.0])
    other["agent_id"] = "some_other_agent"
    _persist(coll_db, [other])
    body = client.get(f"/v1/reliability/{_AGENT}/sweep").json()
    # the other agent's samples must not feed THIS agent's curve
    assert body["sweep"]["insufficient"] is True
