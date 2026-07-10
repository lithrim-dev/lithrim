"""feat-reliability-card: GET /v1/reliability/{agent} — the pure-READ reliability endpoint.

Proves the statistical-rigour metrics are COMPUTED from the workspace's OWN persisted runs +
gold, agent-scoped, with the honest 404 + insufficiency contract (no fabricated values).

RED-before-code. Hermetic: the run store is the ``coll_db`` override; the ingested-corpus gold
is monkeypatched via ``_read_ingested_corpus`` (its own correctness is covered in
``test_bff_units``/``test_persist3a_cases``). $0 read — no grade, no model call.
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

_AGENT = "reliability_bff_test"


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


def _blob(run_id, case_id, verdict, votes, *, grounded=None):
    """A persisted provenance blob in the shape run_eval writes (the shape the read endpoints
    project): per-judge votes live on stage_results.semantic.judge_votes; the floor on
    ``grounded``."""
    return {
        "pipeline_run_id": run_id,
        "agent_id": _AGENT,
        "case_id": case_id,
        "timestamp": f"2026-07-04T00:00:{run_id[-2:]:0>2}Z",
        "verdict": verdict,
        "gate_decision": "pass",
        "findings": [],
        "stage_results": {
            "semantic": {
                "status": verdict,
                "evidence": [],
                "judge_votes": votes,
            }
        },
        "grounded": grounded,
    }


def _vote(role, vote, conf, model="m"):
    return {"judge_role": role, "vote": vote, "confidence": conf, "model": model}


def _persist(coll_db, blobs):
    store = bff.provenance_store_for(coll_db)
    for b in blobs:
        asyncio.run(store.save_blob(b))


def _set_corpus(monkeypatch, corpus):
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: corpus)


# ── 404 convention ────────────────────────────────────────────────────────────


def test_unknown_agent_is_404(client):
    r = client.get("/v1/reliability/nope_not_an_agent")
    assert r.status_code == 404


# ── honest empty state (non-fabrication) ──────────────────────────────────────


def test_no_runs_yields_insufficient_not_zeros(client, monkeypatch):
    _set_corpus(monkeypatch, [])
    r = client.get(f"/v1/reliability/{_AGENT}")
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == _AGENT
    assert body["n_runs"] == 0
    m = body["metrics"]
    for key in ("inter_judge_kappa", "cohen_kappa_vs_gold", "ece", "brier",
                "error_phi", "effective_votes", "intra_judge_stability"):
        assert m[key]["insufficient"] is True, key
        assert m[key]["value"] is None, key  # NOT 0.0-as-data
    assert m["selective_prediction"]["insufficient"] is True


def test_runs_without_gold_are_calibration_insufficient(client, coll_db, monkeypatch):
    # runs exist, but the corpus carries NO gold -> gold-dependent metrics are insufficient,
    # and they say so honestly (never a fabricated ECE/kappa).
    _set_corpus(monkeypatch, [{"case_id": "c1"}])  # no expected flags/verdict = unlabeled
    _persist(coll_db, [
        _blob("run0001", "c1", "PASS", [_vote("j1", "PASS", 0.9), _vote("j2", "PASS", 0.8)]),
    ])
    body = client.get(f"/v1/reliability/{_AGENT}").json()
    assert body["n_runs"] == 1
    m = body["metrics"]
    # cohen kappa vs gold + ECE + Brier need gold -> insufficient, honest
    assert m["cohen_kappa_vs_gold"]["insufficient"] is True
    assert m["cohen_kappa_vs_gold"]["value"] is None
    assert m["ece"]["insufficient"] is True
    assert m["ece"]["value"] is None


# ── real computation over a labeled fixture ───────────────────────────────────


def test_real_metrics_over_labeled_runs(client, coll_db, monkeypatch):
    _set_corpus(monkeypatch, [
        {"case_id": "c1", "expected_safety_flags": ["FABRICATED_HISTORY"]},  # gold BLOCK
        # a DECLARED clean-negative (gold PASS) — an empty-flags-only case is unlabeled
        # (HONEST-1), so the gold-PASS must be a declared verdict to count.
        {"case_id": "c2", "expected_safety_flags": [], "expected_compliance_verdict": "approve"},
    ])
    _persist(coll_db, [
        _blob("run0001", "c1", "BLOCK",
              [_vote("j1", "BLOCK", 0.9), _vote("j2", "BLOCK", 0.85)],
              grounded={"verdict": "BLOCK", "suppressed": [], "floor_blocks": ["FABRICATED_HISTORY"]}),
        _blob("run0002", "c2", "PASS",
              [_vote("j1", "PASS", 0.7), _vote("j2", "BLOCK", 0.6)],
              grounded={"verdict": "PASS", "suppressed": [], "floor_blocks": []}),
    ])
    body = client.get(f"/v1/reliability/{_AGENT}").json()
    assert body["n_runs"] == 2
    m = body["metrics"]
    # inter-judge kappa computed over 2 items x 2 raters
    assert m["inter_judge_kappa"]["n"] == 2
    # ECE/Brier computed over the 4 (conf, correct) pairs
    assert m["ece"]["n"] == 4
    assert m["ece"]["value"] is not None
    assert m["brier"]["value"] is not None
    # cohen kappa vs gold is defined (both BLOCK and PASS gold present)
    assert m["cohen_kappa_vs_gold"]["insufficient"] is False


def test_agent_scoped_ignores_other_agents_runs(client, coll_db, monkeypatch):
    _set_corpus(monkeypatch, [{"case_id": "c1", "expected_safety_flags": ["FABRICATED_HISTORY"]}])
    other = _blob("run9999", "c1", "PASS", [_vote("j1", "PASS", 0.9)])
    other["agent_id"] = "some_other_agent"
    _persist(coll_db, [other])
    body = client.get(f"/v1/reliability/{_AGENT}").json()
    # the other agent's run must not count toward THIS agent's reliability
    assert body["n_runs"] == 0


def test_intra_judge_stability_measured_when_repeats_exist(client, coll_db, monkeypatch):
    # two runs of the SAME case by the same judge, with DIFFERING votes -> stability < 1,
    # and no longer insufficient.
    _set_corpus(monkeypatch, [{"case_id": "c1", "expected_safety_flags": ["FABRICATED_HISTORY"]}])
    _persist(coll_db, [
        _blob("run0001", "c1", "BLOCK", [_vote("j1", "BLOCK", 0.9)]),
        _blob("run0002", "c1", "PASS", [_vote("j1", "PASS", 0.6)]),
    ])
    body = client.get(f"/v1/reliability/{_AGENT}").json()
    m = body["metrics"]
    assert m["intra_judge_stability"]["insufficient"] is False
    assert m["intra_judge_stability"]["value"] is not None
