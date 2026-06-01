"""WS-5-BFF acceptance: the shell BFF round-trip smoke (the shell's first test).

Hermetic + replay-only: no network, no live :8002. Drives the FastAPI BFF over the
vendored WS-0 fixtures (the tests/test_ws4a.py pattern) via a tmp config DB +
FastAPI dependency overrides, and asserts the response carries a well-formed
``composite`` + folded ``calibration_check`` (driver §5 A4). Requires the `[bff]`
extra (fastapi/httpx); skipped cleanly if absent so the default suite stays green.
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

# apps/bff on path so the test imports the BFF app the same way run_eval is imported.
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def _fixture_agent(name: str = "ws5_bff_test") -> Agent:
    """A fixture-pointing agent (absolute paths → hermetic; the test_ws4a shape)."""
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
def client(tmp_path):
    db_path = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db_path)
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    # PUT writes go to a tmp working dir, never the committed seed (clobber-safety).
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_run_eval_replay_returns_composite_and_calibration_check(client):
    """A4 — the round trip: POST /v1/run-eval (replay) → well-formed composite + calibration_check."""
    res = client.post("/v1/run-eval", json={"agent": "ws5_bff_test", "live": False})
    assert res.status_code == 200
    body = res.json()

    assert body["grade_path"] == "replay"
    assert body["case_id"] == CASE_ID

    comp = body["composite"]
    # the real grounded outcome of the WS-0 baseline (not mock data.jsx TILES)
    assert comp["verdict"] == "reject"
    assert comp["stage_verdict"] == "BLOCK"
    assert comp["score"] == 1.0
    assert "FABRICATED_HISTORY" in comp["active_findings"]
    # the S-BS-7 exhibit: the confident MED FP is contract-suppressed
    assert any(a["flag"] == "MEDICATION_NOT_IN_TRANSCRIPT" for a in comp["grounded_adjustments"])

    cal = body["calibration_check"]
    assert cal["verdict_match_rate"] == 1.0
    assert cal["status"] == "PASS"
    assert cal["n_cases"] == 1
    assert cal["ece"] == 0.5  # degenerate N=1 diagnostic, NOT the WS-4b gate
    assert cal["caveat"] is not None and "small N" in cal["caveat"]


def test_corpus_is_listable(client):
    body = client.get("/v1/corpus").json()
    assert isinstance(body["rows"], list)  # graceful empty until a correction is written


def test_ontology_read(client):
    body = client.get("/v1/ontology", params={"agent": "ws5_bff_test"}).json()
    assert body["domain"] == "clinical"
    assert len(body["flags"]) == 23
    assert "severity_map" in body


def test_unknown_agent_is_404(client):
    assert client.post("/v1/run-eval", json={"agent": "nope"}).status_code == 404


# ── D0: the judge-council view folded into /v1/run-eval ──────────────────────


def test_run_eval_carries_realized_council_votes(client):
    """D0 — the run response surfaces the REALIZED per-judge votes for the JudgeTab."""
    body = client.post("/v1/run-eval", json={"agent": "ws5_bff_test", "live": False}).json()
    council = body["council"]
    votes = council["votes"]
    # the WS-0 baseline cast 3 real votes (risk / policy / faithfulness)
    assert {v["judge_role"] for v in votes} == {"risk_judge", "policy_judge", "faithfulness_judge"}
    for v in votes:
        assert v["vote"] in {"PASS", "WARN", "FAIL", "BLOCK"}
        # confidence is float | null (WS-6a D-E) — the reader must tolerate either
        assert v["confidence"] is None or isinstance(v["confidence"], (int, float))
        assert "model" in v
    assert isinstance(council["configured"], list)


# ── D1: PUT /v1/ontology — clobber-safe + validated ──────────────────────────


def _seed_body() -> dict:
    import json

    return json.loads(ONTOLOGY_SEED.read_text())


def test_put_ontology_accepts_and_round_trips(client):
    """A3 — a valid PUT lands on the working copy; a subsequent GET reflects the edit."""
    ont = _seed_body()
    ont["severity_map"]["block_at_or_above"] = 0.75  # a benign, valid edit
    res = client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=ont)
    assert res.status_code == 200
    assert "working_copy" in res.json()

    got = client.get("/v1/ontology", params={"agent": "ws5_bff_test"}).json()
    assert got["severity_map"]["block_at_or_above"] == 0.75  # the working copy is served


def test_put_ontology_rejects_malformed(client):
    """A3 — a structurally malformed ontology is rejected (422), nothing persists."""
    res = client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json={"not": "an ontology"})
    assert res.status_code == 422
    # GET still serves the committed seed (no working copy was written)
    assert client.get("/v1/ontology", params={"agent": "ws5_bff_test"}).json()["domain"] == "clinical"


def test_put_ontology_rejects_snapshot_violation(client):
    """A3 — a gradeable flag outside the taxonomy snapshot is rejected loudly (S-BS-10/12)."""
    ont = _seed_body()
    ont["flags"].append(
        {
            "flag": "NOT_IN_SNAPSHOT_CODE",
            "category": "fidelity",
            "definition": "x",
            "when_to_use": "x",
            "when_NOT_to_use": "x",
            "owner_roles": [],
            "tier": "TIER_1",
            "gradeable": True,  # gradeable + not in the snapshot → must 422
        }
    )
    res = client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=ont)
    assert res.status_code == 422
    assert "NOT_IN_SNAPSHOT_CODE" in res.text


def test_put_ontology_never_clobbers_the_committed_seed(client):
    """A3 — the committed clinical_v1.json is byte-unchanged after a PUT (clobber-safety)."""
    before = ONTOLOGY_SEED.read_bytes()
    ont = _seed_body()
    ont["severity_map"]["warn_above"] = 0.123
    assert client.put("/v1/ontology", params={"agent": "ws5_bff_test"}, json=ont).status_code == 200
    assert ONTOLOGY_SEED.read_bytes() == before  # the seed on disk did not move
