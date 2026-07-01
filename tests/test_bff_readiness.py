"""BFF wiring for the readiness preflight.

Three surfaces, proven end-to-end over the FastAPI app (hermetic, $0 replay):
  1. GET /v1/agents/{agent}/readiness  — the setup-time preflight endpoint.
  2. record["readiness"]               — every grade is annotated (honesty: a degraded config
                                          can never grade silently, even if nobody asked).
  3. strict opt-in                     — LITHRIM_BENCH_STRICT_READINESS / ?strict → 409 (no PASS).

The resolver's CORRECTNESS is covered hermetically in ``test_readiness.py`` (pure) + the live
clinverdict smoke; here the ERROR-path tests monkeypatch the shared ``_compute_readiness`` seam so
the WIRING is deterministic, and one test drives the REAL resolver against ``_core`` end-to-end.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent
from lithrim_bench.harness.readiness import ReadinessFinding, ReadinessReport

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "readiness_bff_test"


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name=_AGENT), db_path=p)
    return p


@pytest.fixture
def client(tmp_path, db_path, monkeypatch):
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def _degraded():
    return ReadinessReport(
        ok=False,
        pack="clinverdict",
        agent=_AGENT,
        ontology_source="committed",
        findings=(
            ReadinessFinding(
                check="CONTRACT_COVERAGE",
                severity="ERROR",
                code="snomed_subsumption(FABRICATED_CLAIM)",
                message="the floor will silently never fire",
                remediation="add the fact-check",
            ),
        ),
    )


# ── the endpoint ───────────────────────────────────────────────────────────────────────


def test_readiness_endpoint_real_core_is_wellformed(client):
    """The REAL resolver, end-to-end against _core (no mismatch expected) — proves the endpoint
    runs the resolver and returns a well-formed report, no monkeypatch."""
    r = client.get(f"/v1/agents/{_AGENT}/readiness")
    assert r.status_code == 200
    b = r.json()
    assert isinstance(b["ok"], bool)
    assert isinstance(b["findings"], list)
    assert b["agent"] == _AGENT


def test_readiness_endpoint_surfaces_the_report(client, monkeypatch):
    monkeypatch.setattr(bff, "_compute_readiness", lambda *a, **k: _degraded())
    b = client.get(f"/v1/agents/{_AGENT}/readiness").json()
    assert b["ok"] is False
    assert any(f["check"] == "CONTRACT_COVERAGE" for f in b["findings"])


# ── grade annotation (always-on) ─────────────────────────────────────────────────────────


def test_grade_annotates_readiness(client, monkeypatch):
    monkeypatch.setattr(bff, "_compute_readiness", lambda *a, **k: _degraded())
    b = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False}).json()
    assert b["readiness"]["ok"] is False
    assert b["readiness"]["findings"][0]["check"] == "CONTRACT_COVERAGE"
    # the grade still ran (default = annotate, not block)
    assert b["pipeline_run_id"]


# ── strict mode (opt-in) ─────────────────────────────────────────────────────────────────


def test_strict_env_refuses_degraded_grade(client, monkeypatch):
    monkeypatch.setattr(bff, "_compute_readiness", lambda *a, **k: _degraded())
    monkeypatch.setenv("LITHRIM_BENCH_STRICT_READINESS", "1")
    r = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False})
    assert r.status_code == 409
    assert r.json()["detail"]["readiness"]["ok"] is False


def test_strict_request_field_refuses_degraded_grade(client, monkeypatch):
    monkeypatch.setattr(bff, "_compute_readiness", lambda *a, **k: _degraded())
    r = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False, "strict": True})
    assert r.status_code == 409


def test_default_is_annotate_not_block(client, monkeypatch):
    monkeypatch.setattr(bff, "_compute_readiness", lambda *a, **k: _degraded())
    r = client.post("/v1/run-eval", json={"agent": _AGENT, "live": False})
    assert r.status_code == 200
    assert r.json()["readiness"]["ok"] is False  # annotated, grade proceeded
