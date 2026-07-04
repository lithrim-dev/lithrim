"""CONFIRM-MODAL-FALLBACK-1 — the cost-confirm modal ALWAYS appears for a run-request on the
litellm path (the self-limiting BFF fallback).

The live bug (8 trials vs the running Azure BFF): Azure gpt-4.1 narrates "I will surface the
cost-confirm modal…" ~40-60% of run-requests WITHOUT calling any tool → no directive reaches
the shell → no modal. The fix: ``_litellm_loop`` tracks whether a ``tool-propose_live_run``
directive was emitted this turn and — IF the user asked to run AND the model emitted no directive
— deterministically emits ``propose_live_run_part()`` itself (opens the CostModal). It is
SELF-LIMITING: when the model DOES call run_eval / propose_live_run the handler already emitted the
directive, so the fallback is skipped (no double-open).

Hermetic / $0 / offline: ``litellm.completion`` is MOCKED end-to-end (no network, no Azure). The
SDK / Claude path is UNTOUCHED (the CONV-RUNTIME-1 anthropic byte-identity guard, run separately).

A-SAFE (T6): the fallback emits ONLY the directive (which merely OPENS the modal) — NO paid op, NO
schema widening, NO ``_TOOL_SPECS`` change; the agent still cannot spend.

Non-vacuity: T2 reddens under the named delete-fallback mutation; T3 reddens under the drop-guard
mutation (always-emit). Both mutations are stated in the docstrings (the driver's discipline).
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _is_grade_all_request, _is_run_request, _litellm_loop  # noqa: E402

AGENT = "confirm_fallback_test"


# ── tiny litellm-streaming-chunk stand-ins (attribute-access only) ─────────────────────


class _Fn(types.SimpleNamespace):
    pass


class _TC(types.SimpleNamespace):
    pass


class _Delta(types.SimpleNamespace):
    pass


class _Choice(types.SimpleNamespace):
    pass


class _Chunk(types.SimpleNamespace):
    pass


def _text_chunk(text: str) -> _Chunk:
    return _Chunk(choices=[_Choice(delta=_Delta(content=text, tool_calls=None), finish_reason=None)])


def _toolcall_chunk(*, index: int, name: str | None, arguments: str, call_id: str | None = None) -> _Chunk:
    tc = _TC(index=index, id=call_id, type="function", function=_Fn(name=name, arguments=arguments))
    return _Chunk(choices=[_Choice(delta=_Delta(content=None, tool_calls=[tc]), finish_reason=None)])


def _finish_chunk(reason: str = "stop") -> _Chunk:
    return _Chunk(choices=[_Choice(delta=_Delta(content=None, tool_calls=None), finish_reason=reason)])


def _stub_completion(turns: list[list[_Chunk]]):
    """Return a fake ``litellm.completion`` that streams ``turns[i]`` on the i-th call."""
    state = {"i": 0, "calls": []}

    def _completion(**kwargs):
        state["calls"].append(kwargs)
        idx = state["i"]
        state["i"] += 1
        chunks = turns[idx] if idx < len(turns) else [_finish_chunk()]
        return iter(chunks)

    _completion.state = state
    return _completion


# ── the two model behaviors the fix is about ──────────────────────────────────────────


def _narrate_only_completion():
    """The gpt-4.1 FAILURE: stream plain text claiming the modal, emit ZERO tool calls."""
    return _stub_completion(
        [[_text_chunk("I will surface the cost-confirm modal so you can run a fresh evaluation. "), _finish_chunk("stop")]]
    )


def _calls_tool_completion():
    """The model BEHAVING: stream a propose_live_run tool call (the handler emits the directive)."""
    return _stub_completion(
        [
            [
                _toolcall_chunk(index=0, name="propose_live_run", arguments="{}", call_id="p"),
                _finish_chunk("tool_calls"),
            ],
            [_text_chunk("Done — confirm in the modal."), _finish_chunk("stop")],
        ]
    )


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    """A ToolContext bound to the real (frozen) BFF ops over a tmp config DB, pinned to the
    neutral _core workspace — the SAME fixture the CONV-RUNTIME-1 offline suite uses."""
    db = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    return bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )


def _run_litellm(ctx, completion, *, message, provider="azure", model="gpt-4.1"):
    async def _drain():
        return [
            e
            async for e in _litellm_loop(
                message, ctx, None,
                provider=provider, model=model, api_key="sk-TEST", api_base=None,
                _completion=completion,
            )
        ]

    return asyncio.run(_drain())


def _directive_parts(events: list[dict]) -> list[dict]:
    return [
        e["part"]
        for e in events
        if e["event"] == "tool_result" and e["part"].get("type") == "tool-propose_live_run"
    ]


# ── T1 — the matcher (conservative, question-excluding) ────────────────────────────────


def test_is_run_request_matches_clear_run_intents():
    """_is_run_request is True for an unambiguous imperative grade-the-case request."""
    for msg in (
        "run eval on this case",
        "run eval on this",
        "grade this case",
        "run live eval on this case",
        "evaluate this",
        "re-run this case",
    ):
        assert _is_run_request(msg) is True, msg


def test_is_run_request_excludes_questions_and_empty():
    """A question, an explain/show request, or an empty message is NEVER a run-request (so the
    fallback never over-fires when the human is asking ABOUT the run, not asking to run)."""
    for msg in (
        "how does run eval work?",
        "what's the verdict?",
        "explain this result",
        "tell me about the case",
        "",
    ):
        assert _is_run_request(msg) is False, msg


# ── T2 — THE FALLBACK (headline, non-vacuous) ──────────────────────────────────────────


def test_fallback_surfaces_the_modal_when_the_model_narrates_without_calling_the_tool(ctx):
    """The gpt-4.1 failure mode: the model narrates "I will surface the cost-confirm modal" and
    emits ZERO tool calls. The deterministic post-loop fallback STILL emits exactly one
    ``tool-propose_live_run`` directive (the modal opens reliably). This is the fix.

    MUTATION (the driver names it): delete the post-loop fallback block in ``_litellm_loop`` →
    no directive reaches the stream → this test goes RED."""
    events = _run_litellm(ctx, _narrate_only_completion(), message="run eval on this case")
    directives = _directive_parts(events)
    assert len(directives) == 1, [e["event"] for e in events]
    assert directives[0]["type"] == "tool-propose_live_run"
    assert directives[0]["state"] == "output-available"
    assert events[-1]["event"] == "done"


# ── T3 — self-limiting (no double-open), non-vacuous ───────────────────────────────────


def test_fallback_is_self_limiting_no_double_open_when_the_model_calls_the_tool(ctx):
    """When the model DOES call propose_live_run, the handler already emits the directive, so the
    post-loop fallback is SKIPPED (directive_emitted is True). EXACTLY ONE directive in the
    stream — never two.

    MUTATION (the driver names it): drop the ``directive_emitted`` guard (always emit the
    fallback) → TWO directives in the stream → this test goes RED."""
    events = _run_litellm(ctx, _calls_tool_completion(), message="run eval on this case")
    directives = _directive_parts(events)
    assert len(directives) == 1, [e["event"] for e in events]
    assert events[-1]["event"] == "done"


# ── T4 — no over-fire on a question ────────────────────────────────────────────────────


def test_fallback_does_not_fire_on_a_question(ctx):
    """A QUESTION about the run (not a request to run) → the matcher excludes it → NO directive is
    emitted even when the model narrates without a tool call."""
    for question in ("how does run eval work?", "explain this result"):
        events = _run_litellm(ctx, _narrate_only_completion(), message=question)
        assert _directive_parts(events) == [], question
        assert events[-1]["event"] == "done"


# ── T6 — A-SAFE pin (non-vacuous) ──────────────────────────────────────────────────────


def test_fallback_is_asafe_directive_only_no_paid_op_no_schema_widening(ctx):
    """A-SAFE: the fallback path emits ONLY the directive — NO bound paid op is called, the schemas
    carry NO paid knob, and ``_TOOL_SPECS`` is unchanged (22). The agent gains no spend path.

    NON-VACUOUS: raise-on-call spies on the run/grade bound ops would trip if the fallback routed
    to any paid op; the schema/spec assertions pin the surface against widening."""

    def _raise_run_eval(**_kw):
        raise AssertionError("the fallback must NOT call run_eval_replay (it only surfaces the modal)")

    def _raise_pack(**_kw):
        raise AssertionError("the fallback must NOT call run_eval_pack (it only surfaces the modal)")

    ctx.run_eval_replay = _raise_run_eval
    ctx.run_eval_pack = _raise_pack

    events = _run_litellm(ctx, _narrate_only_completion(), message="run eval on this case")
    # the fallback fired (the directive is present) — and NO paid op was reached (the spies held)
    assert len(_directive_parts(events)) == 1

    # the directive part carries NO agent / run / paid field — emitting it cannot spend
    part = _directive_parts(events)[0]
    assert part["output"] == {}

    # the paid knobs are absent from BOTH run-request schemas (no widening)
    for schema in (agent_tools.RUN_EVAL_SCHEMA, agent_tools.PROPOSE_LIVE_RUN_SCHEMA):
        assert not any(k in schema for k in agent_tools.PAID_KEYS)

    # the tool roster is unchanged — the fix adds no tool
    assert len(agent_tools._TOOL_SPECS) == 24

    # serialize the whole event stream: no paid knob string leaks into the wire shape
    blob = json.dumps(events, default=str)
    for k in agent_tools.PAID_KEYS:
        assert f'"{k}"' not in blob


# ── CHAT-CASE-RESOLVE-1 follow-on: the FALLBACK directive must carry ctx.active_case ───────────


def test_fallback_directive_carries_the_resolved_active_case(ctx):
    """When the model narrates without a tool and the BFF fallback fires, the directive must carry
    ``ctx.active_case`` (the BFF-resolved / chat-named case) — else ``confirmPaidRun`` grades the
    stale CLIENT selection. The handler directives already carry it (CHAT-CASE-TARGET-1); the
    fallback (the ~40-60% narrate-only path) must too, or CHAT-CASE-RESOLVE-1 is silently dropped.

    MUTATION (named): revert the fallback emit to ``propose_live_run_part()`` (no arg) → RED
    (``output.case_id`` absent → grades the wrong case)."""
    ctx.active_case = "run_001_fabricates"
    events = _run_litellm(
        ctx, _narrate_only_completion(), message="run a live eval on run_001_fabricates"
    )
    directives = _directive_parts(events)
    assert len(directives) == 1
    assert directives[0]["output"].get("case_id") == "run_001_fabricates"


def test_fallback_directive_is_empty_back_compat_when_no_active_case(ctx):
    """Back-compat / A-SAFE: with no active case, the fallback directive output is ``{}`` (a case
    selector is present-only — byte-identical to before; emitting it still cannot spend)."""
    ctx.active_case = None
    events = _run_litellm(ctx, _narrate_only_completion(), message="run eval on this case")
    directives = _directive_parts(events)
    assert len(directives) == 1
    assert directives[0]["output"] == {}


# ── RUN-ALL-ROUTE — "grade all cases" deterministically opens the COHORT modal ──────────
# The single-run fallback's sibling. An unambiguous "grade all / run every case" message must
# open the cohort (propose_run_all) modal, NOT a single-case run — which 500s on an ingested-corpus
# agent whose dataset.case_id is empty. Two deterministic layers in _litellm_loop:
#   (a) the model's frequent MIS-PICK of the single tool is UPGRADED to the cohort directive;
#   (b) when the model emits NO directive, the post-loop fallback emits the cohort directive.
# Both are $0 / A-SAFE — the directive only OPENS the modal; the human's confirm is the sole spend.


def _cohort_directive_parts(events: list[dict]) -> list[dict]:
    return [
        e["part"]
        for e in events
        if e["event"] == "tool_result" and e["part"].get("type") == "tool-propose_run_all"
    ]


def _calls_single_run_completion():
    """The MIS-PICK: the model calls propose_live_run (SINGLE) for a 'grade all' message."""
    return _stub_completion(
        [
            [_toolcall_chunk(index=0, name="propose_live_run", arguments="{}", call_id="p"), _finish_chunk("tool_calls")],
            [_text_chunk("Done — confirm in the modal."), _finish_chunk("stop")],
        ]
    )


def test_is_grade_all_request_matches_cohort_intents():
    """_is_grade_all_request is True for an unambiguous 'grade the whole corpus' imperative."""
    for msg in (
        "run all cases",
        "grade all cases",
        "score every case",
        "run the whole suite",
        "grade all the cases",
        "evaluate all ingested cases",
        "run all",
        "grade everything",
        "run all of them",
    ):
        assert _is_grade_all_request(msg) is True, msg


def test_is_grade_all_request_excludes_single_and_questions():
    """A single-case run, a question, or empty text is NEVER a grade-all request (no over-route)."""
    for msg in (
        "run eval on this case",
        "grade this case",
        "how do I grade all cases?",
        "what cases are there?",
        "",
    ):
        assert _is_grade_all_request(msg) is False, msg


def test_grade_all_upgrades_a_mispicked_single_directive_to_cohort(ctx):
    """The headline: the model MIS-PICKS the single tool for "run all cases" → the directive is
    UPGRADED to the cohort one. NO single-run directive leaks (it would 500 on a corpus agent).

    MUTATION: drop the upgrade rewrite → a tool-propose_live_run leaks → this goes RED."""
    events = _run_litellm(ctx, _calls_single_run_completion(), message="run all cases")
    cohort = _cohort_directive_parts(events)
    assert len(cohort) == 1, [e["event"] for e in events]
    assert cohort[0]["output"] == {}
    assert _directive_parts(events) == []  # the single-run directive must NOT reach the shell


def test_grade_all_fallback_emits_cohort_when_model_emits_no_directive(ctx):
    """The narrate-only failure on a grade-all message → the post-loop fallback emits the COHORT
    directive (not the single one).

    MUTATION: route the grade-all fallback to propose_live_run_part → RED (cohort absent)."""
    events = _run_litellm(ctx, _narrate_only_completion(), message="grade all cases")
    assert len(_cohort_directive_parts(events)) == 1
    assert _directive_parts(events) == []
    assert events[-1]["event"] == "done"


def test_single_run_request_still_routes_to_the_single_directive(ctx):
    """Regression guard: a NON-grade-all run request still opens the SINGLE modal, never the cohort."""
    events = _run_litellm(ctx, _narrate_only_completion(), message="run eval on this case")
    assert len(_directive_parts(events)) == 1
    assert _cohort_directive_parts(events) == []


def test_grade_all_directive_is_asafe_empty_output(ctx):
    """A-SAFE: the cohort directive carries NO paid field (output == {}); emitting it cannot spend.
    The tool roster is unchanged (the route adds no tool)."""
    events = _run_litellm(ctx, _calls_single_run_completion(), message="grade all cases")
    cohort = _cohort_directive_parts(events)
    assert cohort and cohort[0]["output"] == {}
    assert len(agent_tools._TOOL_SPECS) == 24
