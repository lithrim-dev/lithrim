"""RUNTRAIL-5 — the cohort grade appends one audit record per case (end-to-end, BFF layer).

The BFF-layer complement to the (closed) G1-G6 contract (`tests/test_run_audit_trail.py`).
SPEC_RUN_AUDIT_TRAIL.md §1 (append-only) + §7 **G2** (a cohort of M cases ⇒ M new,
find_by_id-able run-history rows). This pins the ORIGINAL symptom closed: a cohort
"grade all cases" through `POST /v1/cases/grade` must leave one APPENDED, addressable
audit record per case in the active workspace's run store, and RE-GRADING must GROW the
trail (never overwrite).

Hermetic + $0: no network, no live model. The cohort drives the real `grade_cases_endpoint`
→ `_grade_case` loop over a tmp config DB + a tmp `collections_db`; `run_eval.run` is the
SAME save seam the production grade uses — persist a FRESH-id provenance blob through
`provenance_store_for(collections_db)` per case (exactly what `run_eval.run`'s in_process /
restamped-replay paths do). The assertion then READS BACK through that same store factory the
BFF `/v1/runs` endpoint reads through. RUNTRAIL-1 already closed the per-execution append at
the engine layer; this is the regression guard at the BFF cohort layer where the symptom lived.
"""

from __future__ import annotations

import json
import sys
import types
import uuid
from pathlib import Path

import pytest

from lithrim_bench.harness.backend import provenance_store_for, run_coro
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


def _prov_blob(case_id: str) -> dict:
    """A minimal, distinct-per-execution provenance blob — the shape `save_blob` persists and
    `find_by_id` / `list_all` read back. A FRESH `pipeline_run_id` per call (the engine mints a
    uuid4 per in_process / restamped-replay execution), so each grade APPENDS a new row."""
    return {
        "pipeline_run_id": str(uuid.uuid4()),
        "agent_id": "cohort_agent",
        "case_id": case_id,
        "timestamp": "2026-06-30T00:00:00+00:00",
        "verdict": "approve",
        "gate_decision": "pass",
        "stages_executed": ["semantic"],
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cfg.sqlite"
    save_agent(house_agent(name="cohort_agent"), db_path=db_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    collections_db = tmp_path / "coll.sqlite"
    fake_ws = types.SimpleNamespace(
        out_dir=out, pack=bff.workspace.DEFAULT_PACK, packs_dir=None, name="cohort_ws"
    )
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: fake_ws)

    # The SAME save seam production `run_eval.run` uses: persist a fresh-id provenance blob
    # through the store factory the BFF threads `collections_db` into. $0 / no model — the
    # grade itself is stubbed (the LOOP + persistence wiring is under test, not judge quality).
    def _persisting_run(agent, *, collections_db=None, **_kw):
        cid = agent.dataset.case_id
        blob = _prov_blob(cid)
        run_coro(provenance_store_for(collections_db).save_blob(blob))
        return {
            "case_id": cid,
            "composite": {"verdict": "approve", "stage_verdict": "PASS", "active_findings": []},
            "provenance": {"grade_path": "in_process"},
            "result": {
                "semantic": {"judge_votes": []},
                "provenance": {"pipeline_run_id": blob["pipeline_run_id"], "council_config": {}},
            },
        }

    monkeypatch.setattr(bff.run_eval, "run", _persisting_run)
    monkeypatch.setattr(bff, "calibration_check", lambda recs: {"status": "PASS", "n_cases": len(recs)})
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: out
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: collections_db
    try:
        yield TestClient(bff.app), out, collections_db
    finally:
        bff.app.dependency_overrides.clear()


def _write_corpus(out: Path, cases: list[dict]) -> None:
    (out / "ingested_cases.jsonl").write_text(
        "\n".join(json.dumps(c, sort_keys=True) for c in cases) + "\n"
    )


def _all_runs(collections_db: Path) -> list[dict]:
    """Read the run-history through the SAME store factory `/v1/runs` reads through."""
    return run_coro(provenance_store_for(collections_db).list_all())


# --------------------------------------------------------------------------- #
# A1 — a cohort grade of M cases ⇒ ≥ M distinct, find_by_id-able run-history rows
# --------------------------------------------------------------------------- #
def test_cohort_grade_persists_one_record_per_case(client):
    cli, out, collections_db = client
    cases = [
        _envelope("cohort_c1", context="Doctor: a"),
        _envelope("cohort_c2", context="Doctor: b"),
        _envelope("cohort_c3", context="Doctor: c"),
    ]
    m = len(cases)
    _write_corpus(out, cases)

    res = cli.post("/v1/cases/grade", json={"agent": "cohort_agent", "in_process": True})
    assert res.status_code == 200, res.text
    assert res.json()["summary"]["graded"] == m

    rows = _all_runs(collections_db)
    # G2 (BFF layer): M cases ⇒ ≥ M new run-history rows.
    assert len(rows) >= m, f"expected >= {m} run-history rows, got {len(rows)}"
    run_ids = [r["pipeline_run_id"] for r in rows]
    # each distinct ...
    assert len(set(run_ids)) == len(run_ids), "every cohort run must carry a distinct run_id"
    # ... and each find_by_id-able (addressable).
    store = provenance_store_for(collections_db)
    for rid in run_ids:
        assert run_coro(store.find_by_id(rid)) is not None, f"{rid} not find_by_id-able"


# --------------------------------------------------------------------------- #
# A2 (APPEND) — a second cohort grade GROWS the trail (no overwrite)
# --------------------------------------------------------------------------- #
def test_second_cohort_grade_appends_and_never_overwrites(client):
    cli, out, collections_db = client
    cases = [
        _envelope("append_c1", context="Doctor: a"),
        _envelope("append_c2", context="Doctor: b"),
    ]
    m = len(cases)
    _write_corpus(out, cases)

    # in_process for BOTH rounds: each execution mints a fresh id, so the APPEND assertion is
    # hermetic + true (a replay round would need captured baselines to resolve). Round 1.
    r1 = cli.post("/v1/cases/grade", json={"agent": "cohort_agent", "in_process": True})
    assert r1.status_code == 200, r1.text
    after_round1 = _all_runs(collections_db)
    ids_round1 = {r["pipeline_run_id"] for r in after_round1}
    assert len(after_round1) >= m

    # Round 2 — the SAME cohort, again. The trail must GROW (append-only), not overwrite.
    r2 = cli.post("/v1/cases/grade", json={"agent": "cohort_agent", "in_process": True})
    assert r2.status_code == 200, r2.text
    after_round2 = _all_runs(collections_db)

    assert len(after_round2) > len(after_round1), (
        "the second cohort grade must GROW the run-history (append-only), not overwrite it"
    )
    # Round 1's rows are still present + addressable (no overwrite of the baseline records).
    ids_round2 = {r["pipeline_run_id"] for r in after_round2}
    assert ids_round1 <= ids_round2, "round-1 audit records must survive the re-grade"
    store = provenance_store_for(collections_db)
    for rid in ids_round1:
        assert run_coro(store.find_by_id(rid)) is not None, f"round-1 record {rid} was lost"
