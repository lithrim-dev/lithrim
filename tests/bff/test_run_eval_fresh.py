"""RUN-EVAL-FRESH-1: the agent's ``run_eval`` SURFACES the cost-confirm (a FRESH grade), not a replay.

The bug (CONFIRMED live): the chat "run eval on `<case>`" makes the model pick the literal
``run_eval`` tool, whose handler did a **$0 REPLAY** that resolved a STALE stored run (`6649be3a`,
pre-calibration) → a frozen wrong REJECT, while "run live" grades fresh → PASS. The prompt-only
routing (CHAT-FRESH-GRADE-1) FAILED — the model grabs ``run_eval`` for the words "run eval."

The fix is DETERMINISTIC AT THE HANDLER (not the prompt): ``run_eval``, when invoked, SURFACES THE
COST-CONFIRM directive (``tool-propose_live_run``) for a FRESH live grade of the named/active case,
and sets ``ctx.active_case`` so the human's confirm targets it. Whichever tool the model picks
(``run_eval`` OR ``propose_live_run``), and whatever the user types ("run eval"/"run"/"grade"), the
result is a FRESH cost-confirmed grade, never a stale $0 replay.

A-SAFE (NON-NEGOTIABLE — the S-BS-81 floor, re-pinned): ``run_eval`` gains NO paid knob; it emits
the DIRECTIVE only. The human's in-DOM cost-confirm (confirmPaidRun → runEval(in_process,confirm))
is the SOLE spend. The agent has NO path to a paid run.

SDK-free: the handler, schemas, and descriptions are exercised without claude_agent_sdk.
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
from agent.tools import (  # noqa: E402
    PAID_KEYS,
    RUN_EVAL_SCHEMA,
    ToolContext,
    run_eval_handler,
)


def _desc(name: str) -> str:
    for _handler, n, desc, _schema in agent_tools._TOOL_SPECS:
        if n == name:
            return desc
    raise AssertionError(f"{name} not in _TOOL_SPECS")


def _raise_on_call(**_kw):
    """A raise-on-call stub for run_eval_replay: if the handler routes "run eval" through the
    replay op (the bug + the named MUTATION), the test FAILS — non-vacuously pinning the fix."""
    raise AssertionError("run_eval_handler must NOT call run_eval_replay (the stale $0 replay)")


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


# ── the named RED→GREEN: run_eval surfaces the cost-confirm; never replays ──


def test_run_eval_emits_the_cost_confirm_directive_never_replays():
    """RUN-EVAL-FRESH-1 (the named pin): run_eval emits a tool-propose_live_run DIRECTIVE (NOT a
    tool-verdict_card) and does NOT call the bound run_eval_replay. The raise-on-call stub makes
    the negative load-bearing — reverting the handler to call run_eval_replay reddens THIS test."""
    ctx = _stub_ctx(_raise_on_call)
    res = asyncio.run(run_eval_handler(ctx, {"agent": "a", "case_id": "run_002_faithful"}))
    assert not res.get("is_error")
    # exactly the cost-confirm directive — never a verdict card (a verdict card = a rendered replay).
    # CHAT-CASE-TARGET-1: the directive now CARRIES the targeted case_id (the prior `output: {}`
    # assertion encoded the dropped-case bug — the shell graded the stale client activeCase).
    assert ctx.parts == [
        {"type": "tool-propose_live_run", "state": "output-available", "output": {"case_id": "run_002_faithful"}}
    ]
    assert all(p["type"] != "tool-verdict_card" for p in ctx.parts)
    # nothing was stashed for a run_result lift (no $0 replay record exists to lift)
    assert ctx.run_results == []


def test_run_eval_sets_the_active_case_to_the_requested_case():
    """RUN-EVAL-FRESH-1: an explicit case_id updates ctx.active_case so the FRESH grade the human
    confirms (confirmPaidRun runs runEval(case_id=activeCase)) targets the requested case, mirroring
    show_case_handler's active-case update."""
    ctx = _stub_ctx(_raise_on_call)
    asyncio.run(run_eval_handler(ctx, {"agent": "a", "case_id": "run_002_faithful"}))
    assert ctx.active_case == "run_002_faithful"


def test_run_eval_guidance_text_is_a_fresh_grade_not_a_replay_verdict():
    """RUN-EVAL-FRESH-1: the returned text names a FRESH/LIVE grade + the cost-confirm. It does NOT
    narrate a STORED replay VERDICT — no "Ran a $0 REPLAY eval" framing and no "VERDICT =" line (the
    handler produced no verdict; it only surfaced the cost-confirm). The driver-specified text may
    mention "$0 replay" to NEGATE it ("no longer the default"), which is the honest framing."""
    ctx = _stub_ctx(_raise_on_call)
    res = asyncio.run(run_eval_handler(ctx, {"agent": "a", "case_id": "run_002_faithful"}))
    text = res["content"][0]["text"]
    low = text.lower()
    assert "fresh" in low
    assert "cost-confirm" in low or "cost confirm" in low
    assert "live" in low
    # the handler does NOT claim a replay verdict was rendered (it produced no verdict at all)
    assert "ran a $0 replay eval" not in low
    assert "VERDICT =" not in text


def test_run_eval_without_a_case_id_keeps_the_active_case_and_still_proposes():
    """RUN-EVAL-FRESH-1 back-compat: with NO case_id, ctx.active_case is unchanged (the case the
    human is exploring) and the handler still emits the cost-confirm directive (never a replay).
    CHAT-CASE-TARGET-1: the directive now carries that active case so confirmPaidRun targets it."""
    ctx = _stub_ctx(_raise_on_call)
    ctx.active_case = "already_active"
    asyncio.run(run_eval_handler(ctx, {"agent": "a"}))
    assert ctx.active_case == "already_active"  # an omitted case_id never clears the active case
    assert ctx.parts == [
        {"type": "tool-propose_live_run", "state": "output-available", "output": {"case_id": "already_active"}}
    ]


# ── A-SAFE re-pin (non-vacuous): no paid knob; the agent only PROPOSES ──


def test_run_eval_schema_carries_no_paid_knob_and_stays_a_selector():
    """A-SAFE (S-BS-81 floor): RUN_EVAL_SCHEMA gains NO paid key — it is still {agent, case_id},
    a SELECTOR for which case to fresh-grade. The agent literally cannot request a paid run."""
    assert not any(k in RUN_EVAL_SCHEMA for k in PAID_KEYS)
    assert set(RUN_EVAL_SCHEMA) == {"agent", "case_id"}


def test_run_eval_never_reaches_a_paid_op_even_with_an_injected_knob():
    """A-SAFE (the load-bearing negative): even if a paid key is injected into the args, run_eval
    fires NO op at all (it only PROPOSES) — run_eval_replay (raise-on-call) is never reached, so
    there is no path for a smuggled live/in_process/confirm to spend. CHAT-CASE-TARGET-1: the
    directive carries ONLY the case SELECTOR (no injected paid knob ever reaches the wire)."""
    ctx = _stub_ctx(_raise_on_call)
    res = asyncio.run(
        run_eval_handler(
            ctx, {"agent": "a", "case_id": "c", "in_process": True, "live": True, "confirm": True}
        )
    )
    assert not res.get("is_error")
    assert ctx.parts == [
        {"type": "tool-propose_live_run", "state": "output-available", "output": {"case_id": "c"}}
    ]
    assert not any(k in ctx.parts[0]["output"] for k in PAID_KEYS)


def test_no_tool_schema_carries_a_paid_knob_after_the_change():
    """A-SAFE generalized across ALL tools (the all-_TOOL_SPECS sweep stays clean — non-vacuous):
    no tool's input schema exposes confirm/in_process/live after RUN-EVAL-FRESH-1."""
    offenders = {
        name: [k for k in PAID_KEYS if k in schema]
        for _h, name, _d, schema in agent_tools._TOOL_SPECS
        if any(k in schema for k in PAID_KEYS)
    }
    assert offenders == {}


# ── the new semantics: run_eval = grade fresh / surfaces the cost-confirm / not a replay ──


def test_run_eval_description_is_grade_fresh_surfaces_the_cost_confirm_not_a_replay():
    """The description must route "run / grade / evaluate / run eval a case" to a FRESH grade: it
    says run_eval GRADES a case FRESH, surfaces the cost-confirm, and does NOT replay a stored run.
    NON-VACUOUS vs the OLD description: the old text told the model to use propose_live_run INSTEAD
    and called run_eval "REPLAY ONLY" — those routing-away phrasings must be GONE."""
    desc = _desc("run_eval").lower()
    assert "fresh" in desc
    assert "cost-confirm" in desc or "cost confirm" in desc
    # explicitly: run_eval does NOT replay a stored run (it is the way to GRADE a case)
    assert "does not replay" in desc or "not replay" in desc
    assert "grade" in desc
    # the OLD route-away wording is gone — run_eval IS the way to grade, not a hand-off to another tool
    assert "use propose_live_run instead" not in desc
    assert "replay only" not in desc
    # A-SAFE wording — the agent only proposes; the human authorizes the spend
    assert "no paid knob" in desc or "human" in desc
