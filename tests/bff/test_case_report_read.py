"""REPORT-HYDRATE-1 — GET /v1/reports/{case_id}: the LATEST persisted report for a case as a
pure $0 READ.

THE GAP (live, 2026-07-04): the shell's Report tab showed "No evaluation yet" for an ARMED
case that HAS persisted runs — the tab only renders the in-session ``runResult``, and no BFF
read serves the full report-record shape for a case (``GET /v1/runs`` rows carry no
``composite``; ``/v1/runs/{id}/audit`` is the provenance projection, a different shape).

THE READ: ``persist()`` upserts the FULL graded record per ``case_id`` (SSOT reports row +
the ``records`` doc-shim) on EVERY grade path (replay / in_process / live), so the newest
record for a case is already stored. The endpoint loads it (``harness.persist.load``) and
applies the SAME read-side folds POST /v1/run-eval applies (``calibration_check`` /
``grade_path`` / ``council`` / ``pipeline_run_id``) — so the shell's ReportTab renders the
hydrated record with the EXACT renderer the in-session run feeds, no parallel projection.

HONESTY: 404 when nothing is persisted, and 404 when the stored record belongs to a DIFFERENT
agent (never serve another agent's verdict under this agent's name). A pure read — it never
re-grades, never appends a run row, and never trips the SIGNATURE-1 freshness guard (the
record is honestly labeled by its stored ``grade_path``; staleness policy stays on the
replay/grade paths).

Hermetic / $0 / offline: TestClient + a tmp out_dir; the record is written through the SAME
``persist()`` the grade path uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.persist import persist

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CASE = "cv_mts_002_clean_subsumption_alzheimers"
AGENT = "repro_agent"


def _record(case_id: str = CASE, agent: str = AGENT) -> dict:
    """A build_record-shaped graded record (the exact shape run_eval.run persists)."""
    return {
        "case_id": case_id,
        "agent": agent,
        "result": {
            "verdict": "reject",
            "gate_decision": "block",
            "findings": [{"code": "FABRICATED_CLAIM"}],
            "semantic": {
                "judge_votes": [
                    {
                        "judge_role": "faithfulness_judge",
                        "vote": "BLOCK",
                        "confidence": 0.9,
                        "model": "gpt-test",
                        "reason": "claim not in the source",
                    }
                ]
            },
            "provenance": {
                "pipeline_run_id": "run-hydrate-0001",
                "council_config": {"judges": ["faithfulness_judge"]},
            },
        },
        "grounded": {
            "verdict": "BLOCK",
            "original_verdict": "BLOCK",
            "active": [{"code": "FABRICATED_CLAIM", "severity": "high"}],
            "suppressed": [],
            "ungrounded": [],
            "skipped_non_gradeable": [],
            "floor_blocks": [],
        },
        "composite": {
            "verdict": "reject",
            "stage_verdict": "BLOCK",
            "score": 0.9,
            "reasoning": "1 active finding(s) after grounding.",
            "grounded_adjustments": [],
            "floor_adjustments": [],
            "active_findings": ["FABRICATED_CLAIM"],
            "ungrounded_count": 0,
            "skipped_non_gradeable_count": 0,
            "floor_block_count": 0,
        },
        "calibration": {
            "reliability_bins": [],
            "ece": None,
            "n_total": 1,
            "n_with_confidence": 1,
            "label_status": "unlabeled",
        },
        "corrections": [],
        "provenance": {
            "ontology_ref": "content_review/1",
            "council_config": {},
            "expected_compliance_verdict": None,
            "expected_safety_flags": [],
            "grade_path": "in_process",
        },
    }


@pytest.fixture
def client(tmp_path):
    out_dir = tmp_path / "out"
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out_dir
    try:
        yield TestClient(bff.app), out_dir
    finally:
        bff.app.dependency_overrides.clear()


def test_latest_persisted_report_round_trips_in_the_run_eval_record_shape(client):
    """The headline: a record persisted by the grade path is served back with the SAME
    read-side folds run-eval applies — composite + calibration_check + council.votes +
    grade_path + pipeline_run_id — so ReportTab's renderer consumes it unchanged."""
    cli, out_dir = client
    persist(CASE, _record(), out_dir=out_dir)

    res = cli.get(f"/v1/reports/{CASE}", params={"agent": AGENT})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["case_id"] == CASE
    assert body["composite"]["verdict"] == "reject"
    assert body["composite"]["active_findings"] == ["FABRICATED_CLAIM"]
    # the read-side folds (the run-eval response contract)
    assert body["grade_path"] == "in_process"  # honest: labeled by HOW it was produced
    assert body["pipeline_run_id"] == "run-hydrate-0001"
    votes = body["council"]["votes"]
    assert [v["judge_role"] for v in votes] == ["faithfulness_judge"]
    assert votes[0]["vote"] == "BLOCK"
    cal = body["calibration_check"]
    assert cal["label_status"] == "unlabeled"  # HONEST-1: no fabricated accuracy on unlabeled


def test_upserted_record_serves_the_latest_grade_for_the_case(client):
    """persist() is an UPSERT per case_id — a re-grade replaces the stored record, so the
    read serves the LATEST verdict, never a shadowed older one."""
    cli, out_dir = client
    persist(CASE, _record(), out_dir=out_dir)
    newer = _record()
    newer["composite"] = {**newer["composite"], "verdict": "approve", "stage_verdict": "PASS",
                          "score": 0.0, "active_findings": []}
    newer["provenance"] = {**newer["provenance"], "grade_path": "replay"}
    persist(CASE, newer, out_dir=out_dir)

    body = cli.get(f"/v1/reports/{CASE}", params={"agent": AGENT}).json()
    assert body["composite"]["verdict"] == "approve"
    assert body["grade_path"] == "replay"


def test_unknown_case_is_a_clean_404_not_a_500(client):
    cli, _out = client
    res = cli.get("/v1/reports/never_graded_case", params={"agent": AGENT})
    assert res.status_code == 404
    assert "never_graded_case" in res.json()["detail"]


def test_another_agents_record_is_refused_never_served_under_this_agent(client):
    """HONESTY: the store is keyed by case_id alone, so a case last graded by ANOTHER agent
    must 404 for this agent — serving it would show another agent's verdict under this
    agent's name."""
    cli, out_dir = client
    persist(CASE, _record(agent="someone_else"), out_dir=out_dir)
    res = cli.get(f"/v1/reports/{CASE}", params={"agent": AGENT})
    assert res.status_code == 404
    assert "someone_else" in res.json()["detail"]


def test_legacy_agent_less_record_is_refused_not_served_under_any_agent(client):
    """Critic tighten: a legacy record with NO ``agent`` stamp is UNATTRIBUTABLE — serving it
    under whatever agent happens to ask is the same silent mis-attribution the mismatch guard
    exists to stop. It 404s with a 'legacy' detail (re-grading stamps + reclaims it).

    MUTATION (named): revert the guard to ``stored_agent and stored_agent != agent`` → the
    agent-less record is served under AGENT → RED."""
    cli, out_dir = client
    rec = _record()
    del rec["agent"]
    persist(CASE, rec, out_dir=out_dir)
    res = cli.get(f"/v1/reports/{CASE}", params={"agent": AGENT})
    assert res.status_code == 404
    assert "legacy" in res.json()["detail"]
