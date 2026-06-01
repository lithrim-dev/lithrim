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
