"""CHATBIND-2: the chat drives the artifact pane (the BFF half).

The conversational loop gains a $0 pane-control channel:
  A1  focus_artifact emits a valid tool-open_artifact DIRECTIVE part for each of the 4
      tabs; an unknown tab is REJECTED (surfaced, no part) — the 4-tab contract holds.
  A-SAFE  the new tool adds NO paid path: FOCUS_ARTIFACT_SCHEMA carries no PAID_KEY; the
      allowlist (derived from _TOOL_SPECS) grows by EXACTLY mcp__lithrim__focus_artifact;
      the deny-hook + isolation + max_turns in _build_options are byte-identical.
  D4  the run_result LIFT: run_eval (replay-only) stashes its $0 record via ctx.emit_run,
      and run_chat drains it as a run_result event (byte-same to the manual Run-eval
      result) — only the replay-only run_eval emits it, so no paid run is ever lifted.

Hermetic — NO real Claude, NO Azure. Requires the [bff] extra; the _build_options +
run_chat checks additionally need [agent] (skipped cleanly when absent).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import Agent, Dataset, EvalProfile, save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ws0"
ONTOLOGY_SEED = REPO_ROOT / "data" / "ontology" / "clinical_v1.json"
CASE_ID = "bench_scribe_v1_inject_condition_1bd0f10dc7b5"

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402  (SDK-free handlers/schemas)
from agent.tools import (  # noqa: E402
    _ARTIFACT_TABS,
    FOCUS_ARTIFACT_SCHEMA,
    PAID_KEYS,
    focus_artifact_handler,
    run_eval_handler,
)

AGENT = "chatbind2_test"


def _fixture_agent(name: str = AGENT) -> Agent:
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
def ctx(tmp_path):
    db = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db)
    return bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )


# ── A1 — focus_artifact emits a valid directive per tab; invalid is rejected ──


def test_focus_artifact_emits_a_directive_for_each_tab(ctx):
    """A1: each of the 5 tabs yields exactly one tool-open_artifact DIRECTIVE part with the
    tab in its output. The part is NOT a gen-UI card type (the shell special-cases it out of
    renderTool); here we assert the wire shape the shell honors. CHATBIND-3 added "case" (the
    source-input view) — a $0 read tab, no paid knob (the A-SAFE tests below still hold)."""
    assert _ARTIFACT_TABS == ("case", "report", "judges", "config", "corpus")
    for tab in _ARTIFACT_TABS:
        ctx.parts.clear()
        res = asyncio.run(focus_artifact_handler(ctx, {"tab": tab}))
        assert not res.get("is_error"), (tab, res)
        assert ctx.parts == [
            {"type": "tool-open_artifact", "state": "output-available", "output": {"tab": tab}}
        ], tab
        assert tab in res["content"][0]["text"]


def test_focus_artifact_rejects_an_unknown_tab(ctx):
    """A1 (the negative, non-vacuous): an off-contract tab is REJECTED — the handler surfaces
    an error and emits NO directive, so a bogus tab can never open the pane."""
    res = asyncio.run(focus_artifact_handler(ctx, {"tab": "bogus"}))
    assert res.get("is_error") is True
    assert "must be one of" in res["content"][0]["text"]
    assert ctx.parts == []  # nothing emitted on a rejected tab


def test_propose_live_run_emits_a_no_paid_knob_directive(ctx):
    """A-SAFE (CHATBIND-4): propose_live_run emits a $0 tool-propose_live_run DIRECTIVE the shell
    honors by OPENING the cost-confirm modal. It carries NO agent/run/paid field, so emitting it
    can never spend — the human's modal-confirm is the only paid path. NON-VACUOUS: assert the
    emitted output is empty (no smuggled knob) and the schema has no PAID_KEY."""
    ctx.parts.clear()
    res = asyncio.run(agent_tools.propose_live_run_handler(ctx, {}))
    assert not res.get("is_error")
    assert ctx.parts == [{"type": "tool-propose_live_run", "state": "output-available", "output": {}}]
    assert agent_tools.PROPOSE_LIVE_RUN_SCHEMA == {}  # no params -> nothing to smuggle
    assert not any(k in agent_tools.PROPOSE_LIVE_RUN_SCHEMA for k in PAID_KEYS)
    assert not any(k in ctx.parts[0]["output"] for k in PAID_KEYS)  # output carries no paid knob


# ── A-SAFE — no paid path; the allowlist grows by exactly one ─────────────────


def test_focus_artifact_schema_carries_no_paid_knob():
    """A-SAFE: the schema is {tab} ONLY (ref dropped) — no confirm/in_process/live, so the
    agent literally cannot request a paid run through this tool."""
    assert {"tab": str} == FOCUS_ARTIFACT_SCHEMA
    assert not any(k in FOCUS_ARTIFACT_SCHEMA for k in PAID_KEYS)


def test_focus_artifact_joins_the_tool_set_exactly_once():
    """A-SAFE: focus_artifact is in _TOOL_SPECS exactly once and NO schema (including the new
    one) gains a paid knob — the S-BS-81 guarantee generalized across the +1 surface."""
    names = [name for _, name, *_ in agent_tools._TOOL_SPECS]
    assert names.count("focus_artifact") == 1
    assert names.count("show_case") == 1
    assert names.count("propose_live_run") == 1
    assert len(names) == 14  # +show_case (CHATBIND-3) +propose_live_run (CHATBIND-4); both $0, no paid knob
    for _h, name, _d, schema in agent_tools._TOOL_SPECS:
        assert not any(k in schema for k in PAID_KEYS), name


def test_build_options_allowlist_grows_by_exactly_focus_artifact_and_gate_is_byte_identical(ctx):
    """A-SAFE (HARD-GATE): the allowlist is EXACTLY the _TOOL_SPECS-derived set (mcp__lithrim__<name>)
    — no extra surface — and the deny-hook + isolation + max_turns are byte-identical. NON-VACUOUS:
    drop a tool from _TOOL_SPECS and the set-equality fails. CHATBIND-3 adds show_case ($0 card);
    CHATBIND-2 added focus_artifact — both $0 read, no paid knob (asserted above)."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent.loop import _build_options, _deny_non_lithrim

    opts = _build_options(ctx)
    allowed = list(opts.allowed_tools)
    derived = {f"mcp__lithrim__{n}" for _, n, *_ in agent_tools._TOOL_SPECS}
    assert set(allowed) == derived  # exactly the tool set — no extra, no paid surface
    assert len(allowed) == len(set(allowed)) == 14
    assert {
        "mcp__lithrim__focus_artifact",
        "mcp__lithrim__show_case",
        "mcp__lithrim__propose_live_run",
    } <= set(allowed)
    assert all(a.startswith("mcp__lithrim__") for a in allowed)
    # the gate + isolation + turn budget are byte-identical (CHATBIND-1 discipline)
    callbacks = [cb for m in opts.hooks["PreToolUse"] for cb in m.hooks]
    assert _deny_non_lithrim in callbacks
    assert opts.permission_mode == "bypassPermissions"
    assert opts.setting_sources == []
    assert opts.skills == []
    assert opts.max_turns == 12


# ── D4 — the run_result lift (replay-only; byte-same to the manual Run-eval) ───


def test_run_eval_handler_stashes_the_replay_record_for_the_lift(ctx):
    """D4: run_eval lifts its $0 replay into ctx.run_results — the SAME record run_eval_replay
    returned (byte-same to the manual Run-eval result the shell renders). A spy stands in for
    the bound op so the asserted identity is exact."""
    record = {"composite": {"verdict": "reject"}, "council": {"votes": []}, "case_id": CASE_ID}
    ctx.run_eval_replay = lambda *, agent, **kw: record  # noqa: ARG005
    res = asyncio.run(run_eval_handler(ctx, {"agent": AGENT}))
    assert not res.get("is_error")
    # the EXACT replay record is queued for the lift (identity, not a copy/projection)
    assert ctx.run_results == [record]
    assert ctx.run_results[0] is record


def test_run_chat_drains_a_run_result_event_after_the_parts(ctx):
    """D4 (the loop wire): run_chat drains ctx.run_results into a run_result event, AFTER the
    tool_result parts of the same turn. NON-VACUOUS — the stub populates run_results exactly
    as run_eval would; without the drain there is no run_result event."""
    sdk = pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent import run_chat

    record = {"composite": {"verdict": "reject"}, "council": {"votes": [{"vote": "reject"}]}}
    verdict_part = {"type": "tool-verdict_card", "state": "output-available", "output": {"id": "r"}}

    async def _stub(_message, c, _history=None):
        yield sdk.AssistantMessage(
            content=[
                sdk.TextBlock(text="Running a $0 replay and focusing the council."),
                sdk.ToolUseBlock(id="t1", name="mcp__lithrim__run_eval", input={"agent": AGENT}),
            ],
            model="claude",
        )
        c.parts.append(verdict_part)  # the verdict card streams as a tool_result...
        c.run_results.append(record)  # ...and run_eval stashes the record for the lift
        yield sdk.ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="s",
            total_cost_usd=0.0,
        )

    async def _drain():
        return [e async for e in run_chat("run + show the council", ctx, source=_stub)]

    events = asyncio.run(_drain())
    kinds = [e["event"] for e in events]
    assert kinds == ["assistant_delta", "tool_call", "tool_result", "run_result", "done"]
    # the run_result carries the EXACT replay record (byte-same to the manual Run-eval result)
    assert events[3]["result"] == record
    # ordering: the run_result follows the verdict tool_result of the same turn
    assert events[2]["part"] == verdict_part
