"""CHAT-CASE-TARGET-1: the chat-named case is the case the cost-confirm directive carries.

The bug (CONFIRMED live — replayed SSE): the user types "run a live eval on run_001_fabricates"
(with a stale client ``activeCase=run_002_faithful``). The agent CORRECTLY calls
``run_eval{case_id:"run_001_fabricates"}`` → the handler sets ``ctx.active_case`` and emits the
cost-confirm directive — but ``propose_live_run_part()`` dropped the case (``output: {}``). The
shell's ``confirmPaidRun`` then fell back to the stale client ``activeCase`` and graded the WRONG
case. Verbatim:

    toolCalls: [{ name:"run_eval", input:{ case_id:"run_001_fabricates" } }]
    propose_live_run_parts: [{ type:"tool-propose_live_run", ..., output:{} }]   ← case_id dropped

The fix: the directive CARRIES the targeted ``case_id`` (a SELECTOR, not a spend). The shell then
syncs the client active case to it (mirroring the show_case lift) and ``confirmPaidRun`` grades it.

A-SAFE (NON-NEGOTIABLE — the S-BS-81 floor): the directive's ``case_id`` is a case SELECTOR, never
a paid knob. No schema gains a PAID_KEY; the agent still has NO path to a paid run; the directive
carries ONLY ``case_id`` (no agent/run/paid/confirm field).

SDK-free: the handler, the adapter part-builder, and the schemas are exercised without
claude_agent_sdk.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import tools as agent_tools  # noqa: E402
from agent.adapter import propose_live_run_part  # noqa: E402
from agent.tools import (  # noqa: E402
    PAID_KEYS,
    PROPOSE_LIVE_RUN_SCHEMA,
    RUN_EVAL_SCHEMA,
    ToolContext,
    propose_live_run_handler,
    run_eval_handler,
)


def _raise_on_call(**_kw):
    raise AssertionError("the run-eval route must NOT call run_eval_replay (the stale $0 replay)")


def _stub_ctx():
    noop = lambda **_kw: {}  # noqa: E731
    return ToolContext(
        author_judge=noop,
        get_judge=noop,
        run_eval_replay=_raise_on_call,
        get_agent=noop,
        author_flag=noop,
        review_runs=noop,
        run_eval_pack=noop,
        assemble_agent=noop,
        delete_judge=noop,
        create_flag=noop,
        delete_flag=noop,
        put_grounding_contract=noop,
        kb_context=noop,
        ingest_cases=noop,
        list_cases=noop,
        record_meta_verdict=noop,
        default_agent="a",
    )


# ── the adapter: propose_live_run_part carries the case_id (back-compat preserved) ──


def test_propose_live_run_part_carries_the_targeted_case_id():
    """The directive's output carries the targeted case_id when one is passed — the SELECTOR the
    shell syncs + grades. NON-VACUOUS: reverting the part to a no-arg ``output: {}`` reddens this."""
    part = propose_live_run_part("run_001_fabricates")
    assert part["type"] == "tool-propose_live_run"
    assert part["state"] == "output-available"
    assert part["output"] == {"case_id": "run_001_fabricates"}


def test_propose_live_run_part_is_byte_compatible_with_no_argument():
    """Back-compat: no arg → ``output: {}`` (byte-identical for any non-case caller — the TopBar
    path, the _litellm_loop fallback, propose_live_run with no active case)."""
    assert propose_live_run_part()["output"] == {}
    assert propose_live_run_part(None)["output"] == {}


def test_propose_live_run_part_output_carries_only_a_selector_no_paid_knob():
    """A-SAFE: the carried output is a case SELECTOR only — never a paid/agent/run field."""
    out = propose_live_run_part("run_001_fabricates")["output"]
    assert set(out) == {"case_id"}
    assert not any(k in out for k in PAID_KEYS)


# ── run_eval_handler: the emitted directive carries the case the handler just made active ──


def test_run_eval_handler_directive_carries_the_requested_case_id():
    """THE NAMED RED→GREEN (BFF half): run_eval{case_id:X} sets ctx.active_case == X AND emits a
    tool-propose_live_run part whose output.case_id == X (the shell grades exactly the case the chat
    named, not the client's stale activeCase).

    MUTATION (the driver names it): revert the emit to ``propose_live_run_part()`` (no arg) → the
    output.case_id assertion goes RED (output.case_id absent)."""
    ctx = _stub_ctx()
    res = asyncio.run(run_eval_handler(ctx, {"agent": "a", "case_id": "run_001_fabricates"}))
    assert not res.get("is_error")
    assert ctx.active_case == "run_001_fabricates"
    assert len(ctx.parts) == 1
    part = ctx.parts[0]
    assert part["type"] == "tool-propose_live_run"
    assert part["output"].get("case_id") == "run_001_fabricates"
    # never a verdict card / a replay record — the handler only PROPOSES (no spend)
    assert all(p["type"] != "tool-verdict_card" for p in ctx.parts)
    assert ctx.run_results == []


def test_run_eval_handler_without_a_case_id_carries_the_pre_set_active_case():
    """When no case_id arg is given, the directive carries whatever active case the request already
    pinned (the case the human is exploring) — still a SELECTOR, never empty if a case is active."""
    ctx = _stub_ctx()
    ctx.active_case = "already_active"
    asyncio.run(run_eval_handler(ctx, {"agent": "a"}))
    assert ctx.active_case == "already_active"
    assert ctx.parts[0]["output"].get("case_id") == "already_active"


def test_run_eval_handler_with_no_active_case_emits_an_empty_back_compat_output():
    """Back-compat (the TopBar-equivalent server path): no case_id arg AND no active case → the
    directive output is ``{}`` (the shell then falls back to the client activeCase)."""
    ctx = _stub_ctx()
    asyncio.run(run_eval_handler(ctx, {"agent": "a"}))
    assert ctx.active_case is None
    assert ctx.parts[0]["output"] == {}


# ── propose_live_run_handler: carries the request's active case when one is pinned ──


def test_propose_live_run_handler_carries_the_active_case():
    """propose_live_run (the other emit site) carries the request's active case so a directly-
    proposed run targets the case the human is on — not a dropped/empty selector."""
    ctx = _stub_ctx()
    ctx.active_case = "run_003_target"
    res = asyncio.run(propose_live_run_handler(ctx, {}))
    assert not res.get("is_error")
    assert ctx.parts[0]["output"].get("case_id") == "run_003_target"


def test_propose_live_run_handler_with_no_active_case_is_back_compat_empty():
    """Back-compat: propose_live_run with NO active case emits ``output: {}`` (byte-identical to the
    pre-change directive — the CHATBIND-4 / conv-runtime fallback shape is unchanged)."""
    ctx = _stub_ctx()
    res = asyncio.run(propose_live_run_handler(ctx, {}))
    assert not res.get("is_error")
    assert ctx.parts[0]["output"] == {}


# ── A-SAFE re-pin (non-vacuous): the case_id is a selector; no paid knob anywhere ──


def test_run_eval_schema_is_still_a_selector_no_paid_knob():
    """RUN_EVAL_SCHEMA stays {agent, case_id} — a SELECTOR; the agent cannot request a paid run."""
    assert set(RUN_EVAL_SCHEMA) == {"agent", "case_id"}
    assert not any(k in RUN_EVAL_SCHEMA for k in PAID_KEYS)


def test_propose_live_run_schema_carries_no_params():
    """PROPOSE_LIVE_RUN_SCHEMA stays param-free — nothing to smuggle a paid knob through."""
    assert PROPOSE_LIVE_RUN_SCHEMA == {}
    assert not any(k in PROPOSE_LIVE_RUN_SCHEMA for k in PAID_KEYS)


def test_tool_spec_count_is_unchanged_and_no_schema_carries_a_paid_knob():
    """The fix adds NO tool and widens NO schema (the S-BS-81 floor generalized)."""
    assert len(agent_tools._TOOL_SPECS) == 24
    offenders = {
        name: [k for k in PAID_KEYS if k in schema]
        for _h, name, _d, schema in agent_tools._TOOL_SPECS
        if any(k in schema for k in PAID_KEYS)
    }
    assert offenders == {}


def test_run_eval_with_a_targeted_case_reaches_no_paid_op_even_with_injected_knobs():
    """A-SAFE (the load-bearing negative): even with paid keys injected alongside the case_id,
    run_eval fires NO op (run_eval_replay is raise-on-call), emits only the directive, and the
    directive carries ONLY the case selector — no smuggled paid knob reaches the wire."""
    ctx = _stub_ctx()
    res = asyncio.run(
        run_eval_handler(
            ctx,
            {"agent": "a", "case_id": "run_001_fabricates", "in_process": True, "live": True, "confirm": True},
        )
    )
    assert not res.get("is_error")
    assert ctx.parts[0]["output"] == {"case_id": "run_001_fabricates"}
    assert not any(k in ctx.parts[0]["output"] for k in PAID_KEYS)
