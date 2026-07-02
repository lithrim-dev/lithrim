"""FINDING-UNITS-1 BFF wiring — the batch grade's dual-report scorecard.

POST /v1/cases/grade rows gain ``units`` (the span-cluster consolidation of each rec's
post-floor findings) and the cohort scorecard gains a ``units`` block NEXT TO the strict
``flag`` block — dual-report, the strict number is never replaced. The clerk's CORRECTNESS
is covered hermetically in ``test_finding_units.py``; here the WIRING is proven over the
FastAPI app with ``_grade_case`` + the ``_agent_code_families`` seam monkeypatched (the
readiness-test pattern), so the tests are deterministic and $0.
"""

from __future__ import annotations

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

_AGENT = "units_bff_test"
_FAMILIES = {
    "fabrication": ["FABRICATED_CLAIM", "HALLUCINATED_DETAIL", "INTERNAL_INCONSISTENCY"]
}


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


def _rec(case_id, codes_quotes, verdict="BLOCK"):
    """A canned grade record: post-floor active codes + per-judge evidence quotes."""
    return {
        "case_id": case_id,
        "composite": {
            "verdict": verdict,
            "stage_verdict": verdict,
            "active_findings": sorted(c for c, _ in codes_quotes),
        },
        "council": {"votes": []},
        "grounded": {
            "verdict": verdict,
            "active": [{"code": c} for c, _ in codes_quotes],
            "suppressed": [],
        },
        "result": {
            "semantic": {
                "evidence": [
                    {"judge": f"judge_{i}", "violation_code": c, "spans": [{"quote": q}]}
                    for i, (c, q) in enumerate(codes_quotes)
                ]
            }
        },
        "pipeline_run_id": f"run_{case_id}",
    }


def _corpus():
    return [
        {"case_id": "c1", "expected_safety_flags": ["FABRICATED_CLAIM"]},
        {"case_id": "c2", "expected_safety_flags": ["HISTORY_OMISSION"]},
    ]


_RECS = {
    # c1: gold code + its twin on the SAME span -> one unit, twin FP vanishes under units
    "c1": _rec(
        "c1",
        [
            ("FABRICATED_CLAIM", "mild pitting edema noted bilaterally"),
            ("HALLUCINATED_DETAIL", "pitting edema noted bilaterally"),
        ],
    ),
    # c2: judges raised nothing -> the gold HISTORY_OMISSION is an FN on both scorings
    "c2": _rec("c2", [], verdict="PASS"),
}


@pytest.fixture
def graded(monkeypatch):
    monkeypatch.setattr(bff, "_read_ingested_corpus", _corpus)
    monkeypatch.setattr(
        bff, "_grade_case", lambda *, case_id, **kw: _RECS[case_id]
    )


def test_units_scorecard_dual_report(client, graded, monkeypatch):
    monkeypatch.setattr(bff, "_agent_code_families", lambda agent, workdir: _FAMILIES)
    # this test pins strict/unit SCORING, not the LAYER3 gradeable filter — keep it inert
    monkeypatch.setattr(bff, "_agent_gradeable_codes", lambda agent, workdir: None)
    r = client.post("/v1/cases/grade", json={"agent": _AGENT})
    assert r.status_code == 200
    body = r.json()
    row = next(x for x in body["matrix"] if x["case_id"] == "c1")
    assert row["units"] == [["FABRICATED_CLAIM", "HALLUCINATED_DETAIL"]]
    sc = body["scorecard"]
    # strict block UNTOUCHED: twin counts as FP (tp=1 fp=1 fn=1)
    assert (sc["flag"]["tp"], sc["flag"]["fp"], sc["flag"]["fn"]) == (1, 1, 1)
    # units block NEXT TO it: the twin merged into the gold unit (tp=1 fp=0 fn=1)
    assert (sc["units"]["tp"], sc["units"]["fp"], sc["units"]["fn"]) == (1, 0, 1)
    assert sc["units"]["precision"] == 1.0


def test_units_inert_without_code_families(client, graded, monkeypatch):
    monkeypatch.setattr(bff, "_agent_code_families", lambda agent, workdir: {})
    monkeypatch.setattr(bff, "_agent_gradeable_codes", lambda agent, workdir: None)
    r = client.post("/v1/cases/grade", json={"agent": _AGENT})
    assert r.status_code == 200
    body = r.json()
    row = next(x for x in body["matrix"] if x["case_id"] == "c1")
    assert row["units"] == [["FABRICATED_CLAIM"], ["HALLUCINATED_DETAIL"]]
    sc = body["scorecard"]
    # no families declared -> unit scoring degenerates to the strict numbers (dual == honest)
    assert (sc["units"]["tp"], sc["units"]["fp"], sc["units"]["fn"]) == (
        sc["flag"]["tp"],
        sc["flag"]["fp"],
        sc["flag"]["fn"],
    )


def test_agent_code_families_reads_the_draft_ontology(tmp_path, db_path):
    """Critic finding (FINDING-UNITS-1 close): the REAL ontology-JSON read — un-monkeypatched.
    The except→{} guard means a key/shape drift would silently make the clerk permanently
    inert (recall-safe but invisible); this pins the round-trip so that failure is loud."""
    import json as _json

    agent = bff._load_agent(_AGENT, db_path)
    workdir = tmp_path / "ont"
    workdir.mkdir()
    (workdir / f"{_AGENT}.json").write_text(
        _json.dumps({"version": "t/1", "code_families": _FAMILIES})
    )
    assert bff._agent_code_families(agent, workdir) == _FAMILIES
    # and the inert default: a draft WITHOUT the block -> {}
    (workdir / f"{_AGENT}.json").write_text(_json.dumps({"version": "t/1"}))
    assert bff._agent_code_families(agent, workdir) == {}
