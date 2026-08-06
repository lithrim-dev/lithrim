"""RUN-SCOPED-REPORT-1 — GET /v1/runs/{run_id}/report: ONE SPECIFIC past run, report-shaped.

THE GAP (live, 2026-08-06): the Report pane can only ever show the LATEST grade of a case.
``GET /v1/reports/{case_id}`` takes no run id and reads a store keyed ``(workspace, case)``
whose every write is an UPSERT, so an earlier run's result is unreachable — and clicking a
scorecard row runs a fresh replay off the newest head rather than opening the run that row
came from. The immutable provenance blobs hold every run, but the only run-addressable reads
(``/audit``, ``/rehydrate``) return DIFFERENT shapes than the report renderer consumes:
``/rehydrate`` returns the inner ``result`` alone (no composite / grounded / council).

WHY IT MATTERS: comparing the same case across runs under a frozen config is the evidence
that an LLM judge is not deterministic — the argument for a deterministic floor and for
escalating to a human exactly where runs disagree. That comparison needs per-run reads.

THE READ: the blob is self-sufficient (SPEC §4). This endpoint projects it into the SAME
record shape ``/v1/reports/{case_id}`` serves, so ReportTab renders a past run with the
EXACT renderer the in-session run feeds — no parallel projection, $0, no re-grade, no run-row
append.

Hermetic / $0 / offline: TestClient + a tmp collections db; blobs are written through the
same provenance store the grade path uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.backend import provenance_store_for, run_coro

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

AGENT = "run_scope_agent"
CASE = "cv01_hiv"


def _grounded(*, verdict: str, active: list[str], suppressed: list[dict] | None = None,
              floor_blocks: list[dict] | None = None) -> dict:
    return {
        "verdict": verdict,
        "original_verdict": "BLOCK",
        "verdict_no_floor": verdict,
        "active": [{"code": c, "severity": "high"} for c in active],
        "suppressed": suppressed or [],
        "ungrounded": [],
        "skipped_non_gradeable": [],
        "floor_blocks": floor_blocks or [],
    }


def _blob(run_id: str, *, verdict: str, grounded: dict, votes: list[dict],
          ts: str, grade_path: str = "in_process") -> dict:
    return {
        "pipeline_run_id": run_id,
        "replay_of": None,
        "agent_id": AGENT,
        "case_id": CASE,
        "timestamp": ts,
        "verdict": verdict,
        "grounded": grounded,
        "grade_path": grade_path,
        "gate_decision": "regenerate",
        "grade_signature": "sig-frozen-0001",
        "cost_tokens": 1234,
        "findings": [{"code": c["code"]} for c in grounded["active"]],
        "stages_executed": ["semantic"],
        "stage_results": {"semantic": {"judge_votes": votes, "evidence": []}},
    }


# The exhibit this endpoint exists for: ONE frozen config, the same case, two runs that
# disagree. Run A raised the answer-key code; run B (later) missed it.
_VOTES_A = [
    {"judge_role": "openbio_judge", "vote": "BLOCK", "confidence": 0.9, "k": 5,
     "model": "azure/gpt-5.4", "reason": "omits a patient-stated precondition"},
]
_VOTES_B = [
    {"judge_role": "openbio_judge", "vote": "PASS", "confidence": 0.99, "k": 5,
     "model": "azure/gpt-5.4", "reason": "no omitted precondition under this criterion"},
]
RUN_A = "run-aaaa-0001"
RUN_B = "run-bbbb-0002"


@pytest.fixture
def client(tmp_path):
    collections_db = tmp_path / "coll.sqlite"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: collections_db
    store = provenance_store_for(collections_db)
    run_coro(store.save_blob(_blob(
        RUN_A, verdict="reject", ts="2026-08-06T10:00:00+00:00",
        grounded=_grounded(verdict="BLOCK", active=["MISSING_CONTEXT"]), votes=_VOTES_A,
    )))
    run_coro(store.save_blob(_blob(
        RUN_B, verdict="approve", ts="2026-08-06T16:00:00+00:00",
        grounded=_grounded(
            verdict="PASS", active=[],
            floor_blocks=[{"flag": "UPCODED_DIAGNOSIS", "contract_type": "snomed_subsumption_floor",
                           "contract": "", "conforms": None, "disposition": "INCONCLUSIVE",
                           "injected": False, "evidence": {"reason": "cannot ground"}}],
        ),
        votes=_VOTES_B,
    )))
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_an_older_run_is_readable_in_the_report_record_shape(client):
    """The headline: the EARLIER run is served in full, not the latest — the whole point."""
    body = client.get(f"/v1/runs/{RUN_A}/report").json()

    assert body["case_id"] == CASE
    assert body["agent"] == AGENT
    assert body["pipeline_run_id"] == RUN_A
    # the run-scoped truth: run A raised MISSING_CONTEXT (run B did not)
    assert body["composite"]["active_findings"] == ["MISSING_CONTEXT"]
    assert body["composite"]["stage_verdict"] == "BLOCK"
    assert body["grounded"]["verdict"] == "BLOCK"
    # every key the ReportTab renderer consumes is present
    for key in ("result", "composite", "grounded", "council", "grade_path"):
        assert key in body, f"missing {key!r} — ReportTab cannot render this"


def test_two_runs_of_one_case_under_a_frozen_config_read_differently(client):
    """The unreliability exhibit: same case, same grade_signature, opposite verdicts."""
    a = client.get(f"/v1/runs/{RUN_A}/report").json()
    b = client.get(f"/v1/runs/{RUN_B}/report").json()

    assert a["composite"]["stage_verdict"] == "BLOCK"
    assert b["composite"]["stage_verdict"] == "PASS"
    assert a["composite"]["active_findings"] != b["composite"]["active_findings"]
    # same frozen config on both sides — so the difference is the model, not the setup
    assert a["grade_signature"] == b["grade_signature"] == "sig-frozen-0001"


def test_council_votes_are_projected_per_run_with_the_seat_label(client):
    """Votes come from THAT run's blob, and carry the authored seat name (JUDGE-LABEL-1)."""
    votes = client.get(f"/v1/runs/{RUN_A}/report").json()["council"]["votes"]
    assert [v["vote"] for v in votes] == ["BLOCK"]
    assert votes[0]["judge_role"] == "openbio_judge"
    assert "display_name" in votes[0]  # resolved at serve time, may be "" when unnamed

    later = client.get(f"/v1/runs/{RUN_B}/report").json()["council"]["votes"]
    assert [v["vote"] for v in later] == ["PASS"]


def test_a_floor_row_survives_the_projection(client):
    """An INCONCLUSIVE floor row must render as such — never silently dropped."""
    comp = client.get(f"/v1/runs/{RUN_B}/report").json()["composite"]
    assert [(a["flag"], a["action"]) for a in comp["floor_adjustments"]] == [
        ("UPCODED_DIAGNOSIS", "floor_inconclusive")
    ]


def test_unknown_run_id_is_a_clean_404(client):
    res = client.get("/v1/runs/run-does-not-exist/report")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
