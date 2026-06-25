"""CHAT-FRESH-GRADE-1: chat "run eval" routes to a FRESH cost-confirmed grade, NOT a $0 replay.

The bug (CONFIRMED live): "run eval on case X" called the agent's ``run_eval`` tool = a $0
REPLAY of a STALE stored run. The fix reframes the AGENT's routing (prompt + tool descriptions)
so its DEFAULT response to "run / grade / evaluate / run eval [case X]" is to PROPOSE a fresh
(live) grade via ``propose_live_run`` (which opens the cost-confirm) — ``run_eval`` ($0 replay)
is reserved for an EXPLICIT "replay / show the last result without paying" ask.

A-SAFE (NON-NEGOTIABLE — the S-BS-81 floor, re-pinned here): NO schema change. ``run_eval``
stays paid-knob-free + replay-only, and ``propose_live_run`` still emits the directive only.
The agent PROPOSES; the human's in-DOM cost-confirm spends. These are PROMPT + DESCRIPTION
edits — the handler bodies are unchanged.

SDK-free: the schemas + descriptions + the prompt string are exercised without claude_agent_sdk.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import loop as agent_loop  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from agent.tools import (  # noqa: E402
    PAID_KEYS,
    PROPOSE_LIVE_RUN_SCHEMA,
    RUN_EVAL_SCHEMA,
    ToolContext,
    propose_live_run_handler,
    run_eval_handler,
)


def _desc(name: str) -> str:
    for _handler, n, desc, _schema in agent_tools._TOOL_SPECS:
        if n == name:
            return desc
    raise AssertionError(f"{name} not in _TOOL_SPECS")


# ── A-SAFE re-pin (non-vacuous): the schemas stay paid-knob-free + replay-only ──


def test_run_eval_schema_still_carries_no_paid_knob():
    """The S-BS-81 floor: no confirm/in_process/live key on RUN_EVAL_SCHEMA — the agent
    literally cannot request a paid run through run_eval (the fix is prompt/description-only)."""
    assert not any(k in RUN_EVAL_SCHEMA for k in PAID_KEYS)
    # the only keys are the agent + the case SELECTOR (NARR-CHAT-LOOP) — nothing paid.
    assert set(RUN_EVAL_SCHEMA) == {"agent", "case_id"}


def test_propose_live_run_schema_still_takes_no_params():
    """propose_live_run only OPENS the cost-confirm; it carries no paid knob, nothing to smuggle."""
    assert PROPOSE_LIVE_RUN_SCHEMA == {}
    assert not any(k in PROPOSE_LIVE_RUN_SCHEMA for k in PAID_KEYS)


def test_run_eval_handler_is_still_replay_only_and_drops_paid_knobs():
    """Even if a paid key is injected into the tool args, the handler drops it — the bound
    run_eval_replay receives the agent + the case_id SELECTOR but NO paid knob (the agent
    cannot silently spend through run_eval)."""
    seen: dict = {}

    def _spy(*, agent, **kw):
        seen["agent"] = agent
        seen["extra"] = kw
        return {"composite": {"verdict": "reject"}, "council": {"votes": []}}

    ctx = _stub_ctx(_spy)
    asyncio.run(
        run_eval_handler(ctx, {"agent": "a", "in_process": True, "live": True, "confirm": True})
    )
    assert seen["agent"] == "a"
    assert not any(k in seen["extra"] for k in PAID_KEYS)
    assert set(seen["extra"]) <= {"case_id"}


def test_propose_live_run_handler_emits_the_directive_only_never_spends():
    """propose_live_run surfaces the cost-confirm DIRECTIVE and returns guidance; it fires NO
    run (the human's modal-confirm is the sole paid path)."""
    ran: dict = {"called": False}

    def _spy(**_kw):
        ran["called"] = True
        return {}

    ctx = _stub_ctx(_spy)
    res = asyncio.run(propose_live_run_handler(ctx, {}))
    assert not res.get("is_error")
    assert ran["called"] is False  # never fired a run
    assert len(ctx.parts) == 1
    assert ctx.parts[0]["type"] == "tool-propose_live_run"


# ── the new semantics: run_eval = explicit $0 replay; propose_live_run = grade fresh ──


def test_run_eval_description_is_an_explicit_stored_replay_not_a_fresh_grade():
    """The agent must route "run / grade a case" to a FRESH grade, so run_eval's description
    states it is a $0 REPLAY of the LAST STORED run (a frozen past result), used only on an
    EXPLICIT replay ask — NOT a fresh judgment."""
    desc = _desc("run_eval").lower()
    assert "$0 replay" in desc
    assert "stored" in desc  # "the last stored run" — a frozen past result, not fresh
    assert "fresh" in desc  # it contrasts itself against a fresh grade


def test_propose_live_run_description_is_the_way_to_grade_a_case_fresh():
    """propose_live_run is the DEFAULT path for "run / grade a case": its description says it
    is the way to GRADE A CASE FRESH (surfacing the cost-confirm; the human's confirm runs the
    fresh paid grade)."""
    desc = _desc("propose_live_run").lower()
    assert "fresh" in desc
    assert "grade" in desc
    assert "cost-confirm" in desc or "cost confirm" in desc


def test_system_prompt_routes_run_grade_to_a_fresh_proposal_not_a_replay():
    """The system prompt reframes the run_eval + propose_live_run bullets so the agent's
    DEFAULT for "run / grade / evaluate / run eval [case X]" is to PROPOSE a fresh (live) grade
    via propose_live_run; run_eval ($0 replay) is the EXPLICIT replay path and the agent SAYS it
    is replaying a stored past run when it uses it."""
    prompt = agent_loop._SYSTEM_PROMPT.lower()
    # run_eval is described as a $0 replay of a STORED past run (not a fresh judgment)
    assert "$0 replay" in prompt
    assert "stored" in prompt
    # propose_live_run is the way to grade a case fresh (the default for "run/grade a case")
    assert "fresh" in prompt
    # the routing rule is present: run/grade -> propose a fresh grade
    assert "grade" in prompt


def _stub_ctx(run_fn):
    """A minimal ToolContext whose ops are no-op spies (SDK-free, no real BFF)."""
    noop = lambda **_kw: {}  # noqa: E731
    return ToolContext(
        author_judge=noop,
        get_judge=noop,
        run_eval_replay=run_fn,
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
