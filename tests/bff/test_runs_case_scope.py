"""RUN-TRAIL-CASE-SCOPE — the $0 review path is case-scoped, and narration is dual-layer.

THE DEFECT (live trace, 2026-07-04): "run a $0 replay of cv_mts_002… and show the report"
structurally DROPPED the named case — REVIEW_RUNS_SCHEMA had no case_id, `_review_runs`
scoped to the agent only (latest run of ANY case), and the narration quoted ONLY the
pre-floor `verdict` field ("verdict=BLOCK") when the same payload carried
grounded_verdict=PASS + floor_suppressed=3 (the LAYER0-READ-1 projection).

This file pins the fix at three layers:
  E*  GET /v1/runs gains OPTIONAL agent/case_id filters (additive: the bare call is
      unchanged; agent+case_id prefers the store's case-scoped `list_versions` lineage
      query — Postgres + SQLite twins). case_id is EXACT-match: the existing conventions
      (GET /v1/reports/{case_id}, `latest_authoritative_for(agent, case_id)`) are exact,
      so no prefix matching is invented here.
  O*  the bound `_review_runs` op gains case_id: latest_run_id = the latest run OF THAT
      CASE (still agent-scoped); omitted → byte-identical behavior.
  N*  review_runs narration states BOTH verdict layers whenever they differ
      ("council flagged (BLOCK); the grounding floor cleared 3 false alarms; final:
      PASS.") and NEVER quotes the pre-floor verdict alone; agreeing layers narrate a
      single verdict (grounded preferred). The audit card gets caseId so AuditView can
      scope its trail.

Hermetic + $0: TestClient + tmp collections DB (the test_run_audit_api.py pattern); the
handler tests use a stub ctx (the chat-fresh-grade pattern). No network, no model.
"""

from __future__ import annotations

import asyncio
import sys
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
from agent.tools import ToolContext, review_runs_handler  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

AGENT = "case_scope_agent"
OTHER = "case_scope_other"
CASE_A = "cv_mts_002_clean_subsumption_alzheimers"
CASE_B = "cv_mts_104_offpmh_fabrication"


def _blob(run_id: str, *, agent: str = AGENT, case_id: str = CASE_A,
          verdict: str = "approve", grounded: dict | None = None,
          replay_of: str | None = None, ts: str = "2026-07-04T00:00:00+00:00") -> dict:
    return {
        "pipeline_run_id": run_id,
        "replay_of": replay_of,
        "agent_id": agent,
        "case_id": case_id,
        "timestamp": ts,
        "verdict": verdict,
        "grounded": grounded,
        "gate_decision": "pass",
        "stages_executed": ["semantic"],
        "stage_results": {"semantic": {"judge_votes": [], "evidence": []}},
    }


def _floor_cleared_grounded(n: int = 3) -> dict:
    # the cv_mts_002 shape: council BLOCK, floor PASS, 3 suppressions
    return {
        "verdict": "PASS",
        "original_verdict": "BLOCK",
        "active": [],
        "suppressed": [
            {"code": "FABRICATED_HISTORY", "contract": "snomed-subsumption/v1",
             "disproved": True, "reason": f"subsumed term {i}"}
            for i in range(n)
        ],
    }


@pytest.fixture
def client(tmp_path):
    collections_db = tmp_path / "coll.sqlite"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: collections_db
    try:
        yield TestClient(bff.app), collections_db
    finally:
        bff.app.dependency_overrides.clear()


def _save(collections_db: Path, blob: dict) -> None:
    run_coro(provenance_store_for(collections_db).save_blob(blob))


def _seed(collections_db: Path) -> dict[str, str]:
    """Newest-first insertion order: a1 (oldest) → a2 → b1 → o1 (newest)."""
    ids = {"a1": str(uuid.uuid4()), "a2": str(uuid.uuid4()),
           "b1": str(uuid.uuid4()), "o1": str(uuid.uuid4())}
    _save(collections_db, _blob(ids["a1"], case_id=CASE_A, verdict="BLOCK",
                                grounded=_floor_cleared_grounded()))
    _save(collections_db, _blob(ids["a2"], case_id=CASE_A, replay_of=ids["a1"]))
    _save(collections_db, _blob(ids["b1"], case_id=CASE_B))
    _save(collections_db, _blob(ids["o1"], agent=OTHER, case_id=CASE_A))
    return ids


# ── E — GET /v1/runs: additive agent/case_id filters ─────────────────────────


def test_e1_bare_runs_call_is_unchanged(client):
    """No filter → every persisted run, newest-first, same shape as today."""
    cli, collections_db = client
    ids = _seed(collections_db)
    rows = cli.get("/v1/runs").json()["runs"]
    assert [r["run_id"] for r in rows] == [ids["o1"], ids["b1"], ids["a2"], ids["a1"]]
    assert {r["agent"] for r in rows} == {AGENT, OTHER}


def test_e2_agent_filter(client):
    cli, collections_db = client
    ids = _seed(collections_db)
    res = cli.get("/v1/runs", params={"agent": AGENT})
    assert res.status_code == 200, res.text
    rows = res.json()["runs"]
    assert {r["agent"] for r in rows} == {AGENT}
    assert ids["o1"] not in {r["run_id"] for r in rows}


def test_e3_agent_and_case_filter_newest_first(client):
    """agent+case_id → only that case's runs for that agent, newest-first (the store's
    case-scoped list_versions lineage query, not a python filter)."""
    cli, collections_db = client
    ids = _seed(collections_db)
    rows = cli.get("/v1/runs", params={"agent": AGENT, "case_id": CASE_A}).json()["runs"]
    assert [r["run_id"] for r in rows] == [ids["a2"], ids["a1"]]
    assert all(r["case_id"] == CASE_A for r in rows)


def test_e4_unknown_case_is_an_empty_list_not_an_error(client):
    cli, collections_db = client
    _seed(collections_db)
    res = cli.get("/v1/runs", params={"agent": AGENT, "case_id": "no_such_case"})
    assert res.status_code == 200, res.text
    assert res.json()["runs"] == []


def test_e5_case_id_is_exact_match_no_prefix(client):
    """The repo convention is EXACT case-id match (GET /v1/reports/{case_id}, the replay
    resolver) — a prefix must NOT match."""
    cli, collections_db = client
    _seed(collections_db)
    rows = cli.get("/v1/runs", params={"agent": AGENT, "case_id": "cv_mts_002"}).json()["runs"]
    assert rows == []


def test_e6_case_filter_without_agent(client):
    cli, collections_db = client
    ids = _seed(collections_db)
    rows = cli.get("/v1/runs", params={"case_id": CASE_B}).json()["runs"]
    assert [r["run_id"] for r in rows] == [ids["b1"]]


# ── O — the bound _review_runs op gains case_id ──────────────────────────────


@pytest.fixture
def ctx_env(tmp_path, monkeypatch):
    db = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    collections_db = tmp_path / "coll.sqlite"
    ctx = bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=collections_db,
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )
    return ctx, collections_db


def test_o1_review_runs_with_case_id_scopes_latest_to_that_case(ctx_env):
    """case_id → latest_run_id is the latest run OF THAT CASE (still agent-scoped) — not
    the agent's newest run on ANY case (the live defect: case B graded later stole the
    'latest' slot)."""
    ctx, collections_db = ctx_env
    ids = _seed(collections_db)
    listing = ctx.review_runs(limit=10, case_id=CASE_A)
    assert listing["latest_run_id"] == ids["a2"]
    assert [r["run_id"] for r in listing["runs"]] == [ids["a2"], ids["a1"]]
    assert {r["agent"] for r in listing["runs"]} == {AGENT}  # OTHER's CASE_A run excluded
    assert listing["case_id"] == CASE_A  # the scope echoes so the handler can narrate it


def test_o2_review_runs_without_case_id_is_unchanged(ctx_env):
    ctx, collections_db = ctx_env
    ids = _seed(collections_db)
    listing = ctx.review_runs(limit=10)
    assert listing["latest_run_id"] == ids["b1"]  # the agent's newest run on ANY case
    assert {r["agent"] for r in listing["runs"]} == {AGENT}
    assert listing.get("case_id") in (None, "")


# ── N — dual-layer narration + the caseId-threaded audit card ────────────────


def _stub_ctx(review_runs_fn):
    noop = lambda **_kw: {}  # noqa: E731
    return ToolContext(
        author_judge=noop, get_judge=noop, run_eval_replay=noop, get_agent=noop,
        author_flag=noop, review_runs=review_runs_fn, run_eval_pack=noop,
        assemble_agent=noop, delete_judge=noop, create_flag=noop, delete_flag=noop,
        put_grounding_contract=noop, kb_context=noop, ingest_cases=noop, list_cases=noop,
        record_meta_verdict=noop, default_agent=AGENT,
    )


def _floor_cleared_listing(case_id=CASE_A):
    """The cv_mts_002-shaped listing: council BLOCK, floor PASS, 3 suppressions."""
    row = {"run_id": "aaaa1111-0000", "case_id": case_id, "verdict": "BLOCK",
           "grounded_verdict": "PASS", "floor_suppressed": 3, "agent": AGENT,
           "replay_of": None, "grade_path": "in_process", "ts": "2026-07-04T00:00:00Z"}
    return {"runs": [row], "latest_run_id": row["run_id"], "case_id": case_id,
            "latest_audit": {"verdict": "BLOCK", "grounded_verdict": "PASS",
                             "grounded": _floor_cleared_grounded()}}


def test_n1_narration_states_both_layers_when_they_differ():
    """The pinned string shape on the floor-cleared fixture — and the pre-floor verdict is
    NEVER quoted alone."""
    ctx = _stub_ctx(lambda **_kw: _floor_cleared_listing())
    res = asyncio.run(review_runs_handler(ctx, {"case_id": CASE_A}))
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert "council flagged (BLOCK); the grounding floor cleared 3 false alarms; final: PASS." in text
    assert "verdict=BLOCK" not in text  # the misleading pre-floor-only reading is gone


def test_n2_agreeing_layers_narrate_a_single_verdict_preferring_grounded():
    listing = _floor_cleared_listing()
    listing["runs"][0].update(verdict="PASS", grounded_verdict="PASS", floor_suppressed=0)
    listing["latest_audit"] = {"verdict": "PASS", "grounded_verdict": "PASS", "grounded": None}
    ctx = _stub_ctx(lambda **_kw: listing)
    res = asyncio.run(review_runs_handler(ctx, {}))
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert "verdict=PASS" in text
    assert "council flagged" not in text and "grounding floor" not in text


def test_n3_legacy_row_without_grounded_projection_still_narrates():
    """A legacy blob (grounded_verdict=None) has only ONE known layer — narrating it is
    honest, not the defect."""
    listing = _floor_cleared_listing()
    listing["runs"][0].update(verdict="BLOCK", grounded_verdict=None, floor_suppressed=None)
    listing["latest_audit"] = {"verdict": "BLOCK", "grounded_verdict": None, "grounded": None}
    ctx = _stub_ctx(lambda **_kw: listing)
    res = asyncio.run(review_runs_handler(ctx, {}))
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert "verdict=BLOCK" in text


def test_n4_case_id_threads_tool_to_op_to_audit_card_and_stays_zero_dollar():
    """The handler passes case_id through to the op, narrates the case, and the audit_log
    part carries caseId (so AuditView scopes its trail). $0: NO cost-confirm part kind is
    emitted — the only part is the audit card."""
    seen: dict = {}

    def _spy(**kw):
        seen.update(kw)
        return _floor_cleared_listing()

    ctx = _stub_ctx(_spy)
    res = asyncio.run(review_runs_handler(ctx, {"case_id": CASE_A}))
    assert seen.get("case_id") == CASE_A
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert CASE_A in text  # the narration names the case it scoped to
    assert [p.get("type") for p in ctx.parts] == ["tool-audit_log"]  # no paid directive
    assert ctx.parts[0]["output"].get("caseId") == CASE_A
    assert ctx.parts[0]["output"].get("runId") == "aaaa1111-0000"


def test_n5_without_case_id_the_audit_card_carries_no_caseId():
    ctx = _stub_ctx(lambda **_kw: _floor_cleared_listing(case_id=None))
    asyncio.run(review_runs_handler(ctx, {}))
    assert [p.get("type") for p in ctx.parts] == ["tool-audit_log"]
    assert not ctx.parts[0]["output"].get("caseId")
