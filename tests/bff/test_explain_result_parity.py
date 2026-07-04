"""EXPLAIN-RESULT-PARITY-1 — every chat provider explains "this result" by deterministic
context injection (not model proactivity).

The bug (CONFIRMED — code + a live screenshot): after a grade, "explain this result" works
on Claude (the SDK path) but on Azure gpt-4.1 (the litellm path) the agent replies "I don't
see a verdict or findings …". Root cause: the verdict renders as an INLINE gen-UI card, not
text, and the replayed history is text-only — so the verdict is NEVER in the model's text
context. Claude proactively calls ``review_runs``; gpt-4.1 at temperature 0 / tool_choice auto
answers from the verdict-less text and does NOT. Same model-proactivity gap the prompt-only
run_eval fix hit — so the fix is DETERMINISTIC context injection.

The fix: ``_latest_run_context(ctx)`` reads the latest run for the active agent (the $0
``ctx.review_runs`` it already has ``ctx`` for) and ``_system_prompt`` appends it as a trailing
stanza — injected at BOTH the SDK (``_build_options``) and litellm (``_litellm_loop``) call
sites. Then "explain this result" works identically on every provider with NO tool call.

A-SAFE (NON-NEGOTIABLE): a $0 read + context injection ONLY. ``_latest_run_context`` calls ONLY
``ctx.review_runs`` (the existing $0 op) and NEVER any paid/run/grade op; no new tool, no
``_TOOL_SPECS`` change, no schema widening, no PAID_KEYS. The agent still cannot spend.

Hermetic / $0 / offline: the helper reads a stubbed ``ctx.review_runs``; the litellm parity test
mocks ``litellm.completion`` end-to-end (no network, no Azure). Each parity assertion names the
mutation that reddens it (the driver's discipline)."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import tools as agent_tools  # noqa: E402
from agent.loop import (  # noqa: E402  (SDK-free: helper + prompt + litellm loop)
    _SYSTEM_PROMPT,
    _latest_run_context,
    _litellm_loop,
    _system_prompt,
)

AGENT = "ws0_default"


# ── a realistic review_runs payload (the driver's named shape) ─────────────────────────

_AUDIT = {
    "verdict": "REJECT",
    "findings": [
        {"code": "SOURCE_CONTRADICTION", "reason": "answer asserts unlimited storage absent from source"},
        {"code": "MISSING_CONTEXT", "reason": "omitted the support channel"},
    ],
    "judges": [
        {"judge_role": "faithfulness_judge", "vote": "BLOCK", "confidence": 0.998},
        {"judge_role": "policy_judge", "vote": "PASS", "confidence": None},
    ],
}
_REVIEW_RES = {
    "runs": [{"run_id": "6649be3a1234", "agent": AGENT, "verdict": "REJECT"}],
    "latest_run_id": "6649be3a1234",
    "latest_audit": _AUDIT,
}


def _raise_on_call(*_a, **_kw):
    raise AssertionError("a PAID op must NEVER be called by _latest_run_context (A-SAFE)")


def _stub_ctx(review_runs, *, default_agent=AGENT, active_case=None):
    """A light ToolContext-shaped stub. Every PAID-capable bound op is a raise-on-call spy so
    A-SAFE is enforced by construction: if the helper touches a paid op the test fails."""
    return types.SimpleNamespace(
        review_runs=review_runs,
        default_agent=default_agent,
        active_case=active_case,
        # every paid / run / grade bound op raises if touched
        run_eval_replay=_raise_on_call,
        run_eval_pack=_raise_on_call,
        author_judge=_raise_on_call,
        get_agent=_raise_on_call,
        author_flag=_raise_on_call,
        get_judge=_raise_on_call,
        assemble_agent=_raise_on_call,
        delete_judge=_raise_on_call,
        create_flag=_raise_on_call,
        delete_flag=_raise_on_call,
        put_grounding_contract=_raise_on_call,
        kb_context=_raise_on_call,
        ingest_cases=_raise_on_call,
        list_cases=_raise_on_call,
        record_meta_verdict=_raise_on_call,
        parts=[],
        run_results=[],
    )


# ── T1 — the helper renders the real run ───────────────────────────────────────────────


def test_latest_run_context_renders_the_real_run():
    """T1: ``_latest_run_context`` returns a non-empty block carrying the REAL verdict + findings
    + run id + a judge role — so the model has them in context without a tool call."""
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES)
    block = _latest_run_context(ctx)
    assert block  # non-empty when a run exists
    assert "REJECT" in block
    assert "SOURCE_CONTRADICTION" in block
    assert "MISSING_CONTEXT" in block
    assert "6649be3a" in block  # the run id prefix
    assert "faithfulness_judge" in block
    assert AGENT in block  # named via ctx.default_agent


def test_latest_run_context_empty_when_no_runs():
    """T1: a ``review_runs`` returning ``{"runs": []}`` → ``""`` (a fresh agent ⇒ NO block ⇒ the
    prompt stays byte-identical — this is what keeps the regression guard green)."""
    ctx = _stub_ctx(lambda **kw: {"runs": [], "latest_run_id": None, "latest_audit": None})
    assert _latest_run_context(ctx) == ""


def test_latest_run_context_never_raises():
    """T1: a ``review_runs`` that RAISES → ``""`` (a read failure NEVER breaks chat)."""

    def _boom(**_kw):
        raise RuntimeError("the run store is down")

    ctx = _stub_ctx(_boom)
    assert _latest_run_context(ctx) == ""


def test_latest_run_context_is_defensive_on_shapes():
    """T1 (defensive): a bare-string finding + a missing-key judge + a no-findings (approved)
    audit render without raising; the approved case says so."""
    res = {
        "runs": [{"run_id": "abcd1234", "agent": AGENT, "verdict": "APPROVE"}],
        "latest_run_id": "abcd1234",
        "latest_audit": {"verdict": "APPROVE", "findings": [], "judges": []},
    }
    block = _latest_run_context(_stub_ctx(lambda **kw: res))
    assert "APPROVE" in block
    low = block.lower()
    assert "none" in low or "approved" in low  # the empty-findings rendering
    # a bare-string finding + a judge missing confidence do not crash
    res2 = {
        "runs": [{"run_id": "ef561234", "verdict": "REJECT"}],
        "latest_run_id": "ef561234",
        "latest_audit": {
            "verdict": "REJECT",
            "findings": ["a free-form finding string"],
            "judges": [{"judge_role": "risk_judge", "vote": "BLOCK"}],
        },
    }
    block2 = _latest_run_context(_stub_ctx(lambda **kw: res2))
    assert "a free-form finding string" in block2
    assert "risk_judge" in block2


# ── GROUNDED-EXPLAIN-1 — the explanation is grounded in the artifact + the answer key ──
# The bug (CONFIRMED live on clinverdict_case06): asked "what's wrong with this case", the agent
# free-narrates hypotheticals ("if the transcript says…") and enumerates the over-fire finding as
# a confirmed problem — because the context carries only finding CODES, never the transcript/note
# or the gold. Fix: inject the active case's artifact + gold + grounding rules so every provider
# explains FROM the evidence, names over-fires honestly, and never invents examples.

_CASE06 = {
    "transcript": (
        "Doctor: How are your sugar numbers? Patient: consistently one hundred and thirty five "
        "or under it. Doctor: Your reading says one hundred and twenty, I will write it down."
    ),
    "artifacts": [
        {"content": "O (Objective): discussions regarding glucose monitoring, but no specific measurements or findings are mentioned."}
    ],
    "expected_safety_flags": ["VALUE_MISMATCH", "HISTORY_OMISSION"],
}


def _load_case06(case_id):
    assert case_id == "clinverdict_case06"
    return _CASE06


def test_context_injects_case_artifact_and_answer_key():
    """The active case's transcript + note + GOLD are in context so the model grounds in the
    real artifact (the 135/120 values, the 'no specific measurements' claim) and knows the answer
    key. MUTATION: drop the artifact injection → the values + note text vanish → RED."""
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES, active_case="clinverdict_case06")
    block = _latest_run_context(ctx, _load_case=_load_case06)
    assert "one hundred and thirty five" in block  # transcript value, verbatim
    assert "no specific measurements" in block  # the note's false claim, verbatim
    assert "VALUE_MISMATCH" in block and "HISTORY_OMISSION" in block  # the gold answer key


def test_context_carries_grounding_and_overfire_rules():
    """The injected case block instructs: quote the artifact, never invent hypotheticals, and
    treat a finding NOT in the answer key as a likely over-fire (not a confirmed problem)."""
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES, active_case="clinverdict_case06")
    low = _latest_run_context(ctx, _load_case=_load_case06).lower()
    assert "quote" in low or "verbatim" in low  # ground-in-artifact
    assert "answer key" in low or "over-fire" in low  # gold reconciliation
    assert "hypothetical" in low or "never invent" in low or "do not invent" in low  # no story-shaping


def test_context_grounds_case_even_with_no_run():
    """The artifact is about the CASE, not the run — so "what's wrong with this case" grounds in
    the transcript/note/gold even when there is NO latest run (the early-return must NOT swallow
    the case block). MUTATION: restore the no-run `return ""` before the case block → RED."""
    ctx = _stub_ctx(
        lambda **kw: {"runs": [], "latest_run_id": None, "latest_audit": None},
        active_case="clinverdict_case06",
    )
    block = _latest_run_context(ctx, _load_case=_load_case06)
    assert "no specific measurements" in block  # grounded despite no run
    assert "VALUE_MISMATCH" in block
    # and with NO active case, no run + no case ⇒ still byte-identical empty (regression guard)
    assert _latest_run_context(_stub_ctx(lambda **kw: {"runs": []}), _load_case=_load_case06) == ""


def test_context_no_case_block_without_active_case():
    """active_case=None → NO artifact/answer-key section (T1 byte-identity preserved)."""
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES, active_case=None)
    block = _latest_run_context(ctx, _load_case=_load_case06)
    assert "no specific measurements" not in block
    assert "VALUE_MISMATCH" not in block


def test_context_unlabeled_case_makes_no_answer_key_claim():
    """An UNLABELED case (no gold) still grounds in the artifact but asserts NO answer key — we
    must not fabricate which findings are false when there is no ground truth (honesty)."""
    unl = {**_CASE06, "expected_safety_flags": []}
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES, active_case="clinverdict_case06")
    block = _latest_run_context(ctx, _load_case=lambda cid: unl)
    assert "no specific measurements" in block  # still grounded in the artifact
    assert "VALUE_MISMATCH" not in block  # no gold → no answer-key reconciliation


def test_context_uses_ctx_bound_loader_when_present():
    """Production wiring: with NO _load_case arg, _latest_run_context uses ``ctx.load_case_full``
    (the request-context loader the BFF binds), so the artifact resolves in the LIVE chat — the
    source-less default can't reach the workspace corpus from loop.py's context. MUTATION: drop
    the ctx.load_case_full preference in _latest_run_context → the block loses the artifact → RED."""
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES, active_case="clinverdict_case06")
    ctx.load_case_full = _load_case06  # the loader the BFF binds in _build_tool_context
    block = _latest_run_context(ctx)  # NO _load_case arg — must fall to ctx.load_case_full
    assert "no specific measurements" in block
    assert "VALUE_MISMATCH" in block


def test_context_never_raises_on_case_load_failure():
    """A case-load that raises must NOT break chat — the block degrades to the findings/votes
    section (defensive, like the review_runs read)."""
    def _boom(_cid):
        raise RuntimeError("case store down")

    ctx = _stub_ctx(lambda **kw: _REVIEW_RES, active_case="clinverdict_case06")
    block = _latest_run_context(ctx, _load_case=_boom)
    assert "REJECT" in block  # the run block still renders


def test_system_prompt_forbids_hypothetical_examples():
    """The static base carries the always-on ground-in-the-case / no-hypothetical rule (so it
    applies even on the no-run path). MUTATION: revert the _SYSTEM_PROMPT rule → RED."""
    low = _SYSTEM_PROMPT.lower()
    assert "never invent" in low or "do not invent" in low or "hypothetical" in low
    assert "quote" in low or "verbatim" in low


# ── T5 — A-SAFE pin (non-vacuous: the paid ops are raise-on-call spies) ─────────────────


def test_latest_run_context_uses_only_review_runs_no_paid_op():
    """T5: ``_latest_run_context`` touches ONLY ``ctx.review_runs``. The stub ctx's every paid /
    run / grade bound op is a raise-on-call spy — if the helper reaches one this raises and the
    test fails. NON-VACUOUS: a wrong implementation that called e.g. run_eval_replay reddens here."""
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES)
    block = _latest_run_context(ctx)  # must not raise (no paid op touched)
    assert "REJECT" in block


def test_no_new_tool_or_paid_knob_added():
    """T5: the fix adds NO tool to ``_TOOL_SPECS`` and NO paid knob anywhere — the agent surface
    is unchanged. (22 tools today; the parity fix is a context-injection read, not a new tool.)"""
    assert len(agent_tools._TOOL_SPECS) == 24
    for _h, name, _d, schema in agent_tools._TOOL_SPECS:
        assert not any(k in schema for k in agent_tools.PAID_KEYS), name


# ── T2 — no-run byte-identity (the regression guard, non-vacuous) ──────────────────────


def test_system_prompt_no_run_is_byte_identical():
    """T2: with NO latest_run (omitted / None / ""), ``_system_prompt`` is byte-identical, and
    none of the three carries the latest-run stanza. Injecting a block DOES add it — proving the
    injection is present-only (the regression guard is non-vacuous in both directions)."""
    base = _system_prompt(AGENT, "case_x")
    assert base == _system_prompt(AGENT, "case_x", latest_run=None)
    assert base == _system_prompt(AGENT, "case_x", latest_run="")
    assert "LATEST RUN CONTEXT" not in base
    # the static base never carried it either (so the stanza is genuinely net-new)
    assert "LATEST RUN CONTEXT" not in _SYSTEM_PROMPT
    block = _latest_run_context(_stub_ctx(lambda **kw: _REVIEW_RES))
    with_run = _system_prompt(AGENT, "case_x", latest_run=block)
    assert "LATEST RUN CONTEXT" in with_run
    assert with_run.startswith(base)  # the block is APPENDED; the base is preserved verbatim


# ── T3 — THE PARITY TEST (the headline; litellm / Azure path) ──────────────────────────


class _Delta(types.SimpleNamespace):
    pass


class _Choice(types.SimpleNamespace):
    pass


class _Chunk(types.SimpleNamespace):
    pass


def _text_chunk(text: str) -> _Chunk:
    return _Chunk(choices=[_Choice(delta=_Delta(content=text, tool_calls=None), finish_reason="stop")])


def _record_completion():
    """A mock ``litellm.completion`` that records the messages it's called with and returns a
    single plain-text assistant chunk (no tool_calls → the loop ends in ONE turn)."""
    state = {"calls": []}

    def _completion(**kwargs):
        state["calls"].append(kwargs)
        return iter([_text_chunk("Here is the breakdown of the verdict.")])

    _completion.state = state
    return _completion


def test_litellm_system_message_carries_the_latest_run_no_tool_call():
    """T3 (PARITY, non-vacuous): driving ``_litellm_loop`` with "explain this result" over the
    Azure/litellm path, the SYSTEM message passed to ``completion`` carries the verdict + findings
    WITHOUT the model having called any tool — so Azure explains "this result" exactly like Claude.

    MUTATION the driver names: revert deliverable 3's litellm injection (drop
    ``latest_run=_latest_run_context(ctx)``, pass the bare ``_system_prompt(...)``) → the verdict
    is no longer in the system message → this test goes RED."""
    ctx = _stub_ctx(lambda **kw: _REVIEW_RES)
    completion = _record_completion()

    async def _drain():
        return [
            e
            async for e in _litellm_loop(
                "explain this result", ctx, None,
                provider="azure", model="gpt-4.1",
                api_key="k", api_base="https://x",
                _completion=completion,
            )
        ]

    events = asyncio.run(_drain())
    assert events[-1]["event"] == "done"
    # the model never called a tool — there is no tool_call event, yet it has the verdict
    assert not any(e["event"] == "tool_call" for e in events)
    sys_msg = completion.state["calls"][0]["messages"][0]
    assert sys_msg["role"] == "system"
    assert "verdict=REJECT" in sys_msg["content"]
    assert "SOURCE_CONTRADICTION" in sys_msg["content"]


def test_litellm_system_message_has_no_latest_run_when_no_run():
    """T3 (the negative): a no-run ctx → the system message carries NO latest-run stanza (the
    no-run path is byte-identical on the litellm engine too)."""
    ctx = _stub_ctx(lambda **kw: {"runs": [], "latest_run_id": None, "latest_audit": None})
    completion = _record_completion()

    async def _drain():
        return [
            e
            async for e in _litellm_loop(
                "explain this result", ctx, None,
                provider="azure", model="gpt-4.1",
                api_key="k", api_base="https://x",
                _completion=completion,
            )
        ]

    asyncio.run(_drain())
    sys_msg = completion.state["calls"][0]["messages"][0]
    assert "LATEST RUN CONTEXT" not in sys_msg["content"]


# ── T4 — the SDK path carries it too (Claude path parity) ──────────────────────────────


def test_sdk_options_carry_the_latest_run_when_a_run_exists():
    """T4: ``_build_options(ctx).system_prompt`` carries the verdict when a run exists; a no-run
    ctx does NOT (byte-identity preserved on the Claude path). Needs the [agent] extra."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent.loop import _build_options

    ctx = _stub_ctx(lambda **kw: _REVIEW_RES)
    opts = _build_options(ctx)
    assert "verdict=REJECT" in opts.system_prompt
    assert "LATEST RUN CONTEXT" in opts.system_prompt

    ctx_norun = _stub_ctx(lambda **kw: {"runs": [], "latest_run_id": None, "latest_audit": None})
    opts_norun = _build_options(ctx_norun)
    assert "LATEST RUN CONTEXT" not in opts_norun.system_prompt
    # the no-run SDK prompt is byte-identical to the un-injected prompt
    assert opts_norun.system_prompt == _system_prompt(ctx_norun.default_agent, ctx_norun.active_case)
