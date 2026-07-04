"""CHAT-CASE-TOKEN-RESOLVE end-to-end — a $0 ask naming the SHORT token ``cv_mts_002`` with
NOTHING armed resolves to the full case_id, serves the stored runs, and narrates the dual-layer
PASS/flip — NOT "no runs on record".

This is the live 2026-07-04 regression, pinned end-to-end on the litellm engine: the model
narrates without a tool call (the ZERO-DOLLAR-ROUTE fallback's trigger), the fallback serves
review_runs with the short token, and the tool-layer resolver maps it to the full id BEFORE the
exact-match GET /v1/runs query — so the seeded runs surface and the narration is honest.

Also pins the exact-match consumer is UNTOUCHED: GET /v1/runs with the short prefix still returns
0 runs (the shared exact-match query the replay-baseline resolver depends on is not loosened).

Hermetic / $0 / offline: litellm.completion is MOCKED; the store is a tmp SQLite seeded directly;
the known-case source is stubbed. SDK-free.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.backend import provenance_store_for, run_coro
from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent.loop import _litellm_loop  # noqa: E402

AGENT = "repro_agent"
FULL = "cv_mts_002_clean_subsumption_alzheimers"
SHORT_MESSAGE = "run a $0 replay of cv_mts_002 and show the report"


def _floor_cleared_blob(run_id: str) -> dict:
    """The cv_mts_002 shape: council BLOCK, grounding floor PASS, 3 suppressions."""
    return {
        "pipeline_run_id": run_id,
        "replay_of": None,
        "agent_id": AGENT,
        "case_id": FULL,
        "timestamp": "2026-07-04T00:00:00+00:00",
        "verdict": "approve",
        "grounded": {
            "verdict": "PASS",
            "original_verdict": "BLOCK",
            "suppressed": [
                {"code": "FABRICATED_HISTORY", "contract": "snomed-subsumption/v1",
                 "disproved": True, "reason": f"subsumed term {i}"}
                for i in range(3)
            ],
        },
        "gate_decision": "pass",
        "stages_executed": ["semantic"],
        "stage_results": {"semantic": {"judge_votes": [], "evidence": []}},
    }


# ── the exact-match consumer stays EXACT (the endpoint is not loosened) ────────


def test_exact_match_endpoint_still_requires_the_full_id(tmp_path):
    """GET /v1/runs?case_id=<short prefix> still returns 0 (the shared exact-match query the
    replay-baseline resolver depends on is UNTOUCHED); the full id returns the seeded run."""
    collections_db = tmp_path / "coll.sqlite"
    run_coro(provenance_store_for(collections_db).save_blob(_floor_cleared_blob("r1")))
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: collections_db
    try:
        cli = TestClient(bff.app)
        short = cli.get("/v1/runs", params={"agent": AGENT, "case_id": "cv_mts_002"}).json()
        full = cli.get("/v1/runs", params={"agent": AGENT, "case_id": FULL}).json()
    finally:
        bff.app.dependency_overrides.clear()
    assert short["runs"] == []  # exact-match on the prefix — unchanged
    assert [r["run_id"] for r in full["runs"]] == ["r1"]


def test_latest_authoritative_for_still_requires_exact_match(tmp_path):
    """The replay-baseline resolver stays EXACT: a prefix resolves to None (no head), the full id
    resolves the seeded head. This is the consumer the fix MUST NOT loosen — the resolution lives
    in the chat/tool layer, never in the shared store query.

    MUTATION (named): if latest_authoritative_for were made prefix-tolerant, the prefix probe
    below would return the head → RED."""
    collections_db = tmp_path / "coll.sqlite"
    store = provenance_store_for(collections_db)
    run_coro(store.save_blob(_floor_cleared_blob("r1")))
    assert run_coro(store.latest_authoritative_for(AGENT, "cv_mts_002")) is None
    head = run_coro(store.latest_authoritative_for(AGENT, FULL))
    assert head is not None and head.get("pipeline_run_id") == "r1"


# ── the litellm end-to-end: short token resolves + dual-layer narration ────────


class _Fn(types.SimpleNamespace):
    pass


class _Delta(types.SimpleNamespace):
    pass


class _Choice(types.SimpleNamespace):
    pass


class _Chunk(types.SimpleNamespace):
    pass


def _text_chunk(text: str) -> _Chunk:
    return _Chunk(choices=[_Choice(delta=_Delta(content=text, tool_calls=None), finish_reason=None)])


def _finish_chunk(reason: str = "stop") -> _Chunk:
    return _Chunk(choices=[_Choice(delta=_Delta(content=None, tool_calls=None), finish_reason=reason)])


def _narrate_only_completion(**_kwargs):
    return iter([_text_chunk("Here is the stored result. "), _finish_chunk("stop")])


def _ctx(tmp_path, monkeypatch, *, active_case=None):
    db = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db)
    collections_db = tmp_path / "coll.sqlite"
    run_coro(provenance_store_for(collections_db).save_blob(_floor_cleared_blob("r1")))
    monkeypatch.setattr(
        bff.workspace, "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    # stub the known-case source (the same list the browser enumerates) so the resolver sees
    # the full id without loading the pack/corpus on disk
    monkeypatch.setattr(bff, "_agent_known_case_ids", lambda *a, **k: [FULL])
    return bff._build_tool_context(
        req_agent=AGENT, db_path=db, out_dir=tmp_path / "out", workdir=tmp_path / "ont",
        collections_db=collections_db, actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None, active_case=active_case,
    )


def _run(ctx, message):
    async def _drain():
        return [
            e async for e in _litellm_loop(
                message, ctx, None,
                provider="azure", model="gpt-4.1", api_key="sk-TEST", api_base=None,
                _completion=_narrate_only_completion,
            )
        ]

    return asyncio.run(_drain())


def _paid_directives(events):
    return [
        e["part"] for e in events
        if e["event"] == "tool_result"
        and e["part"].get("type") in ("tool-propose_live_run", "tool-propose_run_all")
    ]


def test_short_token_nothing_armed_resolves_and_narrates_dual_layer(tmp_path, monkeypatch):
    """The live regression, end-to-end: nothing armed, "$0 replay of cv_mts_002" → the fallback
    serves review_runs, the resolver maps cv_mts_002 → the full id, the seeded run surfaces, and
    the narration is dual-layer (council flagged; floor cleared; final PASS) — NOT "no runs"."""
    ctx = _ctx(tmp_path, monkeypatch)
    events = _run(ctx, SHORT_MESSAGE)
    calls = [e for e in events if e["event"] == "tool_call" and e["name"] == "review_runs"]
    assert len(calls) == 1, [e["event"] for e in events]
    # the EFFECTIVE scope is the resolved full id: the read surfaced the seeded run (the token
    # cv_mts_002 mapped to FULL before the exact-match query, else this would be "0 run(s)"), and
    # the dual-layer narration is honest — NOT "no runs on record".
    narration = "".join(
        e["text"] for e in events if e["event"] == "assistant_delta"
    )
    assert "1 run(s) on record" in narration
    assert FULL in narration  # the honest scope names the resolved full id, not the prefix
    assert "no runs on record" not in narration.lower()
    assert "cleared" in narration.lower() or "false alarm" in narration.lower()
    # the audit card carries the resolved full id (the scope the tool layer actually applied)
    cards = [
        e["part"] for e in events
        if e["event"] == "tool_result" and e["part"].get("type") == "tool-audit_log"
    ]
    assert cards and cards[0]["output"].get("caseId") == FULL
    # $0 invariant: no paid cost-confirm directive
    assert _paid_directives(events) == []
    assert events[-1]["event"] == "done"


def test_armed_full_id_wins_over_the_short_token_end_to_end(tmp_path, monkeypatch):
    """ARMED beats typed, end-to-end: the armed full id is the scope even though the prose names
    a token that would (here) resolve to the same id — the armed id is used directly."""
    ctx = _ctx(tmp_path, monkeypatch, active_case=FULL)
    events = _run(ctx, SHORT_MESSAGE)
    calls = [e for e in events if e["event"] == "tool_call" and e["name"] == "review_runs"]
    assert len(calls) == 1
    # the armed full id is the effective scope (the seeded run surfaces + the card names it)
    narration = "".join(e["text"] for e in events if e["event"] == "assistant_delta")
    assert "1 run(s) on record" in narration
    assert FULL in narration
    cards = [
        e["part"] for e in events
        if e["event"] == "tool_result" and e["part"].get("type") == "tool-audit_log"
    ]
    assert cards and cards[0]["output"].get("caseId") == FULL
    assert _paid_directives(events) == []
