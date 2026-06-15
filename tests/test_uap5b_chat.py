"""UAP-5b / R11 acceptance: the conversational-shell agent loop (offline / $0).

Hermetic — NO real Claude, NO Azure. The CORE tool HANDLERS run against the real
(frozen) BFF ops over a tmp config DB, proving:
  - A2 the conversation IS the audit log (a tool-call -> an audited write -> GET /v1/audit);
  - A3 the core tools drive real ops (author_judge persists; run_eval is replay $0);
  - A4 the parts-adapter emits the EXISTING gen-UI {type,state,output} shape (no new cards);
  - A-SAFE the agent has NO path to a paid run (no paid key in the schema; the handler
    never forwards one) and a gate violation is SURFACED, never bypassed.
The loop's event serialization is exercised with a STUB message source (pre-baked SDK
messages — no real loop). The fully-integrated loop (the SDK invokes the handler) is
the A-LIVE user-run, by design. Requires the [bff] extra; the loop-shape + isolation
checks additionally need [agent] (skipped cleanly when absent).
"""

from __future__ import annotations

import asyncio
import subprocess
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
from agent import tools as agent_tools  # noqa: E402  (SDK-free handlers/schemas)
from agent.tools import (  # noqa: E402
    PAID_KEYS,
    RUN_EVAL_SCHEMA,
    author_judge_handler,
    get_judge_handler,
    run_eval_handler,
)

AGENT = "uap5b_test"


def _fixture_agent(name: str = AGENT):
    return house_agent(name=name)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A tmp config plane + a ToolContext bound to the real (frozen) BFF ops, plus a
    TestClient over the SAME db so GET /v1/audit reads what the tools wrote (A2). The agent
    is the NEUTRAL _core house fixture and the active workspace is pinned to _core (the
    isolation seam) so the $0 replay runs in-process on the neutral pack in a bare CE checkout."""
    db = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    ctx = bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    try:
        yield ctx, TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


def test_run_eval_tool_is_replay_only_and_renders_the_verdict_card(env):
    """A1 + A4 + A-SAFE: run_eval drives a real $0 REPLAY grade and renders the verdict
    card; the schema carries NO paid knob."""
    ctx, _client = env
    res = asyncio.run(run_eval_handler(ctx, {"agent": AGENT}))
    assert not res.get("is_error")
    assert "REPLAY" in res["content"][0]["text"]
    assert len(ctx.parts) == 1
    part = ctx.parts[0]
    assert part["type"] == "tool-verdict_card" and part["state"] == "output-available"
    assert part["output"]["verdict"] == "REJECT"  # the WS-0 baseline grounded outcome
    # A-SAFE — the agent literally cannot ask for a paid run through this tool.
    assert not any(k in RUN_EVAL_SCHEMA for k in PAID_KEYS)


def test_run_eval_handler_never_forwards_a_paid_knob(env):
    """A-SAFE (the load-bearing negative): even if a paid key is injected into the tool
    args, the handler drops it — ctx.run_eval_replay is called with the agent ONLY."""
    ctx, _client = env
    seen = {}

    def _spy(*, agent, **kw):
        seen["agent"] = agent
        seen["extra"] = kw
        return {"composite": {"verdict": "reject"}, "council": {"votes": []}}

    ctx.run_eval_replay = _spy
    asyncio.run(
        run_eval_handler(ctx, {"agent": AGENT, "in_process": True, "live": True, "confirm": True})
    )
    assert seen == {"agent": AGENT, "extra": {}}  # no live/in_process/confirm reached the op


def test_off_lens_assignment_is_surfaced_not_bypassed(env):
    """A3 + A-SAFE: an off-lens assignment is REJECTED (the owner↔emit gate holds); the
    tool surfaces the error, emits NO card, and nothing is persisted."""
    ctx, client = env
    res = asyncio.run(
        author_judge_handler(
            ctx, {"role": "risk_judge", "assigned_flags": ["FABRICATED_HISTORY"], "rationale": "x"}
        )
    )
    assert res.get("is_error") is True
    assert "owner" in res["content"][0]["text"].lower()
    assert ctx.parts == []  # no card emitted on a rejected write
    records = client.get("/v1/audit", params={"target_type": "judge"}).json()["records"]
    assert records == []  # nothing persisted -> nothing audited (no silent bypass)


def test_get_judge_tool_returns_a_summary_not_a_fieldinfo_crash(env):
    """S-BS-82 regression: the bound _get_judge closure must pass assigned_flags=None
    explicitly. The UAP-5b offline suite never exercised ctx.get_judge, so the live
    `FieldInfo.split` crash slipped past 8/8 green. Drive BOTH the handler (which catches
    + surfaces) and the raw bound closure (which must NOT raise) — pre-fix, the raw call
    raised AttributeError('Query' object has no attribute 'split')."""
    ctx, _client = env
    res = asyncio.run(get_judge_handler(ctx, {"role": "risk_judge"}))
    assert not res.get("is_error"), res  # the handler surfaced a real summary, not an error
    assert "assigned_flags=" in res["content"][0]["text"]
    summary = ctx.get_judge(role="risk_judge")  # the raw closure: a dict, never a crash
    assert isinstance(summary, dict) and "assigned_flags" in summary


def test_loop_event_shapes_with_a_stub_source(env):
    """A1 (offline half): run_chat normalizes a STUB SDK message stream into the SSE
    event shapes — assistant_delta / tool_call / tool_result(part) / done — with no real
    Claude. The done cost is labelled the BYO-Claude subscription-equivalent (fold 4)."""
    sdk = pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent import run_chat

    ctx, _client = env
    a_part = {
        "type": "tool-judge_editor",
        "state": "output-available",
        "output": {"role": "risk_judge", "agent": AGENT},
    }

    async def _stub(_message, c, _history=None):
        yield sdk.AssistantMessage(
            content=[
                sdk.TextBlock(text="Authoring the risk judge."),
                sdk.ToolUseBlock(
                    id="t1", name="mcp__lithrim__author_judge", input={"role": "risk_judge"}
                ),
            ],
            model="claude",
        )
        c.parts.append(a_part)  # the tool "ran" (its part is queued for the next drain)
        yield sdk.ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="s",
            total_cost_usd=0.12,
        )

    async def _drain():
        return [e async for e in run_chat("author a risk judge", ctx, source=_stub)]

    events = asyncio.run(_drain())
    kinds = [e["event"] for e in events]
    assert kinds == ["assistant_delta", "tool_call", "tool_result", "done"]
    assert events[0]["text"] == "Authoring the risk judge."
    assert events[1]["name"] == "mcp__lithrim__author_judge"
    assert events[2]["part"] == a_part
    assert events[3]["cost_usd"] == 0.12
    assert "subscription-equivalent" in events[3]["cost_label"]  # fold 4: not a literal charge


# ── CONV-UX-1 (W0): the chat default_agent resolves against the ACTIVE workspace ──────


def test_resolve_chat_agent_coerces_an_invalid_agent_to_the_workspace_agent(tmp_path):
    """W0 / A1: a stale/invalid supplied agent (the live ws0_default-in-demo-clinical bug) is
    COERCED to the active workspace's first agent — no dead ws0_default 404 in a non-default
    workspace whose only agents are e.g. eval-1/snomed-demo."""
    db = tmp_path / "config.sqlite"
    save_agent(house_agent(name="eval-1"), db_path=db)
    save_agent(house_agent(name="snomed-demo"), db_path=db)
    resolved = bff._resolve_chat_agent("ws0_default", db)
    assert resolved == "eval-1"  # the first agent (sorted), never the dead literal


def test_resolve_chat_agent_honors_a_valid_supplied_agent(tmp_path):
    """W0 GUARDRAIL: a VALID supplied non-default agent is HONORED verbatim — legitimate
    multi-agent targeting must NOT be pinned to the workspace default."""
    db = tmp_path / "config.sqlite"
    save_agent(house_agent(name="eval-1"), db_path=db)
    save_agent(house_agent(name="snomed-demo"), db_path=db)
    assert bff._resolve_chat_agent("snomed-demo", db) == "snomed-demo"


def test_resolve_chat_agent_back_compat_default_workspace(tmp_path):
    """W0 / A1 back-compat: in a workspace that DOES hold ws0_default, the literal still
    resolves to itself (the neutral `default` workspace path is unchanged)."""
    db = tmp_path / "config.sqlite"
    save_agent(house_agent(name="ws0_default"), db_path=db)
    assert bff._resolve_chat_agent("ws0_default", db) == "ws0_default"


def test_a_no_agent_arg_handler_targets_the_resolved_agent(tmp_path, monkeypatch):
    """W0: a tool that OMITS the agent arg defaults to ctx.default_agent — and that default is
    the RESOLVED workspace agent (the ToolContext built off the coerced value), so the agent-keyed
    read targets the live agent, not the dead ws0_default."""
    db = tmp_path / "config.sqlite"
    save_agent(house_agent(name="eval-1"), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    resolved = bff._resolve_chat_agent("ws0_default", db)  # coerced -> eval-1
    ctx = bff._build_tool_context(
        req_agent=resolved,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="t"),
        x_actor=None,
    )
    seen = {}

    def _spy(*, name, **kw):
        seen["name"] = name
        return {"eval_profile": {}}

    ctx.get_agent = _spy
    from agent.tools import get_agent_handler

    asyncio.run(get_agent_handler(ctx, {}))  # NO agent arg -> defaults to ctx.default_agent
    assert seen["name"] == "eval-1"  # the resolved workspace agent, not ws0_default


def test_sse_format_frames_one_event():
    from agent import sse_format

    frame = sse_format({"event": "done", "cost_usd": None})
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    assert '"event": "done"' in frame


def test_agent_package_does_not_pull_the_sdk_at_import():
    """A5: importing apps/bff/agent must NOT pull claude_agent_sdk (lazy import). Run in a
    fresh subprocess so an earlier test that imported the SDK can't pollute the check."""
    code = (
        f"import sys; sys.path.insert(0, {str(_BFF)!r}); import agent; "
        "assert 'claude_agent_sdk' not in sys.modules, 'SDK leaked into the agent import'; "
        "print('OK')"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


def test_tool_set_is_the_uap5c_journey_set():
    """The complete set (16 tools): the UAP-5b spine (author_judge/get_judge/run_eval) + the
    UAP-5c journey tools (get_agent/author_flag/review_runs) + the UAP-5c-2 split
    (run_eval_pack batch + assemble_agent edit-one-facet) + the CRUD-1 delete_judge revert +
    the FLAG-1 reference-flag create_flag/delete_flag + the CHATBIND-2 focus_artifact pane
    directive + the CHATBIND-3 show_case (source-input card) + the CHATBIND-4 propose_live_run
    (the consented paid-run hand-off -- $0 directive, the human's confirm spends). The exact-bound
    + no-paid-knob assertions live in tests/test_uap5c_journey.py (S-BS-81); the focus_artifact /
    show_case / propose_live_run A-SAFE bounds live in tests/test_chatbind2_pane.py."""
    names = {name for _, name, *_ in agent_tools._TOOL_SPECS}
    assert names == {
        "author_judge",
        "get_judge",
        "run_eval",
        "get_agent",
        "author_flag",
        "review_runs",
        "run_eval_pack",
        "assemble_agent",
        "delete_judge",
        "create_flag",
        "delete_flag",
        "focus_artifact",
        "show_case",
        "propose_live_run",
        "add_grounding_contract",
        "kb_context",
    }
