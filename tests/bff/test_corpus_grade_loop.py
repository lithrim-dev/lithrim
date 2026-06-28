"""NARR-LOOP — close the ingest→grade loop: list the ingested corpus, grade a SPECIFIC case
by id (no agent repoint), and batch-grade the whole corpus into a cohort matrix.

Diagnosis (live dogfood 2026-06-17): ingest pinned 10 cases, but "load all → evaluate all →
report" had no surface — `/v1/corpus` returns the (unrelated) correction corpus, `run-eval`
had no `case_id` selector, and there was no batch. Evaluating all 10 required manually
repointing the agent's dataset.case_id ten times.

Contract:
  * GET /v1/cases lists the active workspace's ingested corpus (case_id + fidelity flags).
  * POST /v1/run-eval {case_id} grades THAT case via the shared `_grade_case` path (the
    frozen-dataclass override reaches the in-process branch).
  * POST /v1/cases/grade batches the corpus into {matrix, summary}; one bad case is trapped,
    never aborting the batch.

The grade itself is stubbed (monkeypatched `run_eval.run`) — the point under test is the
LOOP plumbing (selection + aggregation), not judge quality (covered elsewhere).
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402


def _envelope(case_id: str, *, context: str, response: str = "S (Subjective): ...") -> dict:
    from lithrim_bench.verification.jute_extractor import _to_envelope

    return _to_envelope({"case_id": case_id, "response": response, "context": context})


def _stub_record(agent, **_kw) -> dict:
    """A minimal grade record shaped so `_grade_case`'s post-processing survives offline."""
    cid = agent.dataset.case_id
    return {
        "case_id": cid,
        "composite": {
            "verdict": "reject" if cid.endswith("bad") else "approve",
            "stage_verdict": "BLOCK" if cid.endswith("bad") else "PASS",
            "active_findings": ["INCOMPLETE_DOCUMENTATION"] if cid.endswith("bad") else [],
        },
        "provenance": {"grade_path": "in_process"},
        "result": {
            "semantic": {"judge_votes": [
                {"judge_role": "risk_judge", "vote": "WARN", "confidence": 0.9, "model": "stub"}
            ]},
            "provenance": {"pipeline_run_id": f"run-{cid}", "council_config": {"judges": []}},
        },
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name="loop_agent"), db_path=db_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    fake_ws = types.SimpleNamespace(
        out_dir=out, pack=bff.workspace.DEFAULT_PACK, packs_dir=None, name="loop_ws"
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: fake_ws)
    # offline grade + calibration (the loop plumbing is under test, not the council)
    captured: list[str] = []

    def _capturing_run(agent, **kw):
        captured.append(agent.dataset.case_id)
        return _stub_record(agent, **kw)

    monkeypatch.setattr(bff.run_eval, "run", _capturing_run)
    monkeypatch.setattr(bff, "calibration_check", lambda recs: {"status": "PASS", "n_cases": len(recs)})
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: tmp_path / "coll.sqlite"
    try:
        yield TestClient(bff.app), out, captured
    finally:
        bff.app.dependency_overrides.clear()


def _write_corpus(out: Path, cases: list[dict]) -> None:
    (out / "ingested_cases.jsonl").write_text(
        "\n".join(json.dumps(c, sort_keys=True) for c in cases) + "\n"
    )


# --------------------------------------------------------------------------- #
# GET /v1/cases — list the ingested corpus
# --------------------------------------------------------------------------- #
def test_list_cases_lists_ingested_corpus(client):
    cli, out, _ = client
    _write_corpus(out, [
        _envelope("c1_ok", context="Doctor: hi\nPatient: cramps"),
        _envelope("c2_ok", context="Doctor: hello"),
    ])
    res = cli.get("/v1/cases")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 2
    ids = {c["case_id"]: c for c in body["cases"]}
    assert set(ids) == {"c1_ok", "c2_ok"}
    assert ids["c1_ok"]["has_context"] is True  # transcript fidelity signal
    assert ids["c1_ok"]["has_artifact"] is True
    assert ids["c1_ok"]["labeled"] is False  # ingested = unlabeled by construction


def test_list_cases_empty_when_no_corpus(client):
    cli, _out, _ = client
    assert cli.get("/v1/cases").json() == {"cases": [], "count": 0}


# --------------------------------------------------------------------------- #
# POST /v1/run-eval {case_id} — grade a specific case without repointing the agent
# --------------------------------------------------------------------------- #
def test_run_eval_case_id_selects_the_case(client):
    cli, _out, captured = client
    res = cli.post("/v1/run-eval", json={"agent": "loop_agent", "case_id": "clinical_scribe_07"})
    assert res.status_code == 200, res.text
    assert res.json()["case_id"] == "clinical_scribe_07"
    assert captured[-1] == "clinical_scribe_07"  # the override reached run_eval.run's agent


def test_run_eval_without_case_id_uses_agent_default(client):
    cli, _out, captured = client
    cli.post("/v1/run-eval", json={"agent": "loop_agent"})
    assert captured[-1] != "clinical_scribe_07"  # the agent's own dataset.case_id, not an override


# --------------------------------------------------------------------------- #
# POST /v1/cases/grade — batch the corpus into a cohort matrix
# --------------------------------------------------------------------------- #
def test_grade_cases_batches_corpus_into_matrix(client):
    cli, out, captured = client
    _write_corpus(out, [
        _envelope("case_a_bad", context="Doctor: a"),
        _envelope("case_b_ok", context="Doctor: b"),
        _envelope("case_c_bad", context="Doctor: c"),
    ])
    res = cli.post("/v1/cases/grade", json={"agent": "loop_agent", "in_process": True})
    assert res.status_code == 200, res.text
    body = res.json()
    assert {r["case_id"] for r in body["matrix"]} == {"case_a_bad", "case_b_ok", "case_c_bad"}
    assert set(captured) >= {"case_a_bad", "case_b_ok", "case_c_bad"}  # each graded
    summ = body["summary"]
    assert summ["n"] == 3 and summ["graded"] == 3 and summ["errors"] == 0
    assert summ["verdicts"] == {"reject": 2, "approve": 1}
    # the matrix carries per-case findings + votes for the report
    bad = next(r for r in body["matrix"] if r["case_id"] == "case_a_bad")
    assert bad["verdict"] == "reject" and "INCOMPLETE_DOCUMENTATION" in bad["findings"]
    assert bad["votes"] and bad["votes"][0]["judge_role"] == "risk_judge"


def test_grade_cases_subset_and_empty(client):
    cli, out, _ = client
    _write_corpus(out, [_envelope("only_one", context="Doctor: x")])
    # explicit subset overrides the corpus scan
    res = cli.post("/v1/cases/grade", json={"agent": "loop_agent", "case_ids": ["only_one"]})
    assert res.json()["summary"]["n"] == 1
    # empty corpus + no subset → a clean 400, not a crash
    (out / "ingested_cases.jsonl").unlink()
    res2 = cli.post("/v1/cases/grade", json={"agent": "loop_agent"})
    assert res2.status_code == 400 and "no ingested cases" in res2.json()["detail"]


def test_grade_cases_traps_a_failing_case_without_aborting(client, monkeypatch):
    """A per-case grade failure rides into THAT row as ``error`` and never aborts the batch —
    the other cases still grade (the contract's resilience guarantee; the widened trap)."""
    cli, out, _ = client
    _write_corpus(out, [
        _envelope("case_ok", context="Doctor: a"),
        _envelope("case_boom", context="Doctor: b"),
    ])

    def _maybe_boom(agent, **kw):
        if agent.dataset.case_id == "case_boom":
            raise RuntimeError("grade exploded")  # not an HTTPException → exercises the catch-all
        return _stub_record(agent, **kw)

    monkeypatch.setattr(bff.run_eval, "run", _maybe_boom)
    body = cli.post("/v1/cases/grade", json={"agent": "loop_agent"}).json()
    summ = body["summary"]
    assert summ["n"] == 2 and summ["graded"] == 1 and summ["errors"] == 1
    boom = next(r for r in body["matrix"] if r["case_id"] == "case_boom")
    assert "exploded" in boom["error"] and "verdict" not in boom
    ok = next(r for r in body["matrix"] if r["case_id"] == "case_ok")
    assert ok["verdict"] == "approve"  # the good case still graded despite the sibling failure
