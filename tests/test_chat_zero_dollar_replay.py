"""ZERO-DOLLAR-ROUTE — an explicit "$0 replay / stored result" ask routes to the $0 read
(review_runs), NEVER the paid cost-confirm modal.

THE DEFECT (live-verified 2026-07-04): the chat message "run a $0 replay of
cv_mts_002_clean_subsumption_alzheimers and show the report" surfaced the PAID cost-confirm
modal instead of the stored $0 result. Two confirmed causes:

  (1) PROMPT: the shepherd stanza's "'run / grade / evaluate / run eval [this case|case X]'
      ALWAYS means this fresh cost-confirmed grade" clause swallowed the $0 carve-out ("run a
      $0 replay" contains "run"), AND the carve-out itself pointed at run_eval — whose handler
      (RUN-EVAL-FRESH-1) now ALSO emits the paid cost-confirm directive, so even a perfectly
      followed carve-out landed on the paid modal.
  (2) FALLBACK: `_is_run_request("run a $0 replay of … and show the report")` was True (verb
      "run" + object cue "run"), so the litellm post-loop CONFIRM-MODAL-FALLBACK-1
      deterministically emitted the paid directive even when the model routed correctly.

THE FIX (this file pins it): the routing text names the $0 trigger phrases ("$0", "replay",
"stored/last result", "don't spend", "without spending") ADJACENT to the ALWAYS clause and
points them at review_runs (the A-SAFE $0 read); review_runs' own description claims those
phrases affirmatively; and the deterministic run-intent matchers exclude an explicit $0 ask
(credit-safety: a $0 path never escalates to a paid proposal).

REPLAY-HONESTY: when the $0 read refuses (the SIGNATURE-1 stale-grade_signature 409 guard),
the tool result the model sees carries the guard's actionable message VERBATIM — never
swallowed, never silently escalated to a paid proposal.

A-SAFE surface UNCHANGED: no new tool (the 23-tool pin holds), no schema widening — the fix is
prompt text + existing-tool descriptions + the matcher guard only.

Hermetic / $0 / offline: litellm.completion is MOCKED (the confirm-fallback harness pattern);
the 409 test uses a raise-on-call stub ctx. SDK-free.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

from fastapi import HTTPException  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent import loop as agent_loop  # noqa: E402
from agent import tools as agent_tools  # noqa: E402
from agent.loop import _is_grade_all_request, _is_run_request, _litellm_loop  # noqa: E402
from agent.tools import ToolContext, review_runs_handler  # noqa: E402

AGENT = "zero_dollar_route_test"

# the live-verified defect message, verbatim
DEFECT_MESSAGE = "run a $0 replay of cv_mts_002_clean_subsumption_alzheimers and show the report"

# the SIGNATURE-1 stale-replay guard line, in the exact shape run_eval.py raises and the BFF
# surfaces as a 409 detail ("config changed since" is the marker both mappings key on)
STALE_GUARD = (
    "agent 'repro_agent': the config changed since case "
    "'cv_mts_002_clean_subsumption_alzheimers' was last graded — re-grade "
    "(run it live or in_process) to see the new verdict."
)


def _desc(name: str) -> str:
    for _handler, n, desc, _schema in agent_tools._TOOL_SPECS:
        if n == name:
            return desc
    raise AssertionError(f"{name} not in _TOOL_SPECS")


# ── (i) THE PROMPT CONTRACT — the $0 exception is explicit, adjacent, and names the tool ──


def test_always_clause_carries_the_zero_dollar_exception_adjacent():
    """The shepherd stanza's ALWAYS clause must carry an ADJACENT exception naming the $0
    trigger phrases and pointing at review_runs by name — else "run a $0 replay" is swallowed
    by ALWAYS (the live defect).

    MUTATION (named): revert the ALWAYS clause to the bare "'run / grade / evaluate / run eval
    [this case|case X]' ALWAYS means this fresh cost-confirmed grade -- never a stale stored
    replay." → the slice after ALWAYS carries no trigger phrases / no review_runs → RED."""
    stanza = agent_loop._SHEPHERD_STANZA
    idx = stanza.find("ALWAYS means")
    assert idx != -1, "the ALWAYS clause left the shepherd stanza — re-pin this test to the new home"
    adjacent = stanza[idx : idx + 900]
    for phrase in (
        "$0", "replay", "stored", "last result", "don't spend", "without spending",
        "for free", "no cost", "without paying",
    ):
        assert phrase in adjacent, f"the ALWAYS clause lost the {phrase!r} trigger"
    assert "review_runs" in adjacent, "the exception must point at the $0 tool BY NAME"
    assert "cost-confirm" in adjacent  # …and say the modal is NOT the answer for it


def test_system_prompt_run_eval_bullet_carries_the_zero_dollar_exception():
    """run_eval's system-prompt bullet routes an explicit $0 ask AWAY from itself to
    review_runs (run_eval's handler emits the PAID directive — RUN-EVAL-FRESH-1)."""
    prompt = agent_loop._SYSTEM_PROMPT
    idx = prompt.find("- run_eval:")
    assert idx != -1
    bullet = prompt[idx : prompt.find("\n  - ", idx + 1)]
    assert "review_runs" in bullet
    assert "$0" in bullet


def test_system_prompt_propose_live_run_carve_out_points_at_review_runs_not_run_eval():
    """The stale carve-out "(Reach for run_eval ONLY on an explicit '$0 replay …' ask.)" is
    GONE — it pointed the $0 ask at a tool that surfaces the PAID modal. The carve-out now
    names review_runs."""
    prompt = agent_loop._SYSTEM_PROMPT
    assert "Reach for run_eval ONLY" not in prompt, (
        "the stale carve-out is back — run_eval opens the PAID cost-confirm (RUN-EVAL-FRESH-1); "
        "a $0 ask routed there lands on the paid modal (the live defect)"
    )
    idx = prompt.find("- propose_live_run:")
    assert idx != -1
    bullet = prompt[idx:]
    assert "review_runs" in bullet[:900]
    assert "$0" in bullet[:900]


def test_review_runs_description_claims_the_zero_dollar_phrases_affirmatively():
    """review_runs' own tool description claims the $0 trigger phrases as ITS OWN ("THE way
    to …") so both engines' tool-choice lands on it for an explicit $0 ask."""
    desc = _desc("review_runs")
    assert "THE way" in desc
    for phrase in (
        "$0", "replay", "stored", "last result", "don't spend", "without spending",
        "for free", "no cost", "without paying",
    ):
        assert phrase in desc, f"review_runs' description lost the {phrase!r} claim"


def test_propose_live_run_description_routes_zero_dollar_asks_to_review_runs():
    """propose_live_run's description must NOT point a $0 ask at run_eval (which opens the
    SAME paid modal) — it names review_runs."""
    desc = _desc("propose_live_run")
    assert "use run_eval instead" not in desc
    assert "review_runs" in desc


def test_run_eval_description_routes_zero_dollar_asks_to_review_runs():
    desc = _desc("run_eval")
    assert "review_runs" in desc
    assert "$0" in desc


# ── (ii) the A-SAFE surface is unchanged (the fix is text-only) ────────────────────────────


def test_asafe_surface_unchanged_no_new_tool_no_schema_widening():
    """The tool roster is EXACTLY the d6448d9 set (24 names — record_meta_verdict predates this
    fix; the older 23-pins are a pre-existing base failure from that addition) and no schema
    gained a paid knob — the fix is prompt text + existing-tool descriptions + a matcher guard,
    nothing else. In particular NO new replay/$0 tool was minted: the $0 route reuses
    review_runs."""
    names = [n for _, n, *_ in agent_tools._TOOL_SPECS]
    assert sorted(names) == sorted(
        [
            "author_judge", "get_judge", "run_eval", "get_agent", "author_flag", "review_runs",
            "run_eval_pack", "assemble_agent", "delete_judge", "create_flag", "delete_flag",
            "focus_artifact", "list_cases", "show_case", "propose_live_run", "propose_run_all",
            "add_grounding_contract", "author_contract", "author_tool", "author_criterion",
            "create_judge", "kb_context", "ingest_cases", "record_meta_verdict",
        ]
    ), names
    for _h, n, _d, schema in agent_tools._TOOL_SPECS:
        assert not any(k in schema for k in agent_tools.PAID_KEYS), n
    # RUN-TRAIL-CASE-SCOPE: the $0 tool gains case_id — a SELECTOR (the RUN_EVAL_SCHEMA
    # precedent), never a paid knob. Still no PAID_KEY (asserted above).
    assert {"limit": int, "case_id": str} == agent_tools.REVIEW_RUNS_SCHEMA


# ── (iii) the deterministic matchers — an explicit $0 ask is NEVER a run-request ───────────


def test_is_run_request_excludes_the_live_defect_message():
    """THE defect, pinned verbatim: "run a $0 replay of … and show the report" must NOT match
    the run-intent fallback (it deterministically opened the PAID modal).

    MUTATION (named): drop the zero-dollar guard in _is_run_request → the verb "run" + the
    object cue "run" match again → RED."""
    assert _is_run_request(DEFECT_MESSAGE) is False


def test_is_run_request_excludes_explicit_zero_dollar_phrasings():
    for msg in (
        "run a $0 replay of this case",
        "replay the last stored result",
        "re-run it without spending",
        "grade this case but don't spend anything",
        "show the last result, do not spend",
    ):
        assert _is_run_request(msg) is False, msg


def test_is_run_request_still_matches_plain_run_intents():
    """Regression guard: the guard is trigger-phrase-scoped — a plain run request still opens
    the modal path."""
    for msg in ("run eval on this case", "grade this case", "run live eval on this case"):
        assert _is_run_request(msg) is True, msg


def test_is_run_request_excludes_the_for_free_family():
    """Critic-verified reds (cold review of this branch): the "for free"-family phrasings are
    as explicit a $0 ask as '$0' itself — they must NOT hit the deterministic PAID fallback.

    MUTATION (named): drop the for-free / no-cost / without-paying alternates from
    _ZERO_DOLLAR_RE → every probe here matches the run-intent again → RED."""
    for msg in (
        "run it for free",
        "rerun it for free",
        "run it at no cost",
        "run this case free of charge",
        "rerun this without paying",
    ):
        assert _is_run_request(msg) is False, msg


def test_is_grade_all_request_excludes_the_for_free_family():
    assert _is_grade_all_request("grade all cases for free") is False


def test_free_guard_is_word_bounded_no_freeform_over_match():
    """'free' counts only inside the explicit phrases — a 'freeform'/'free-text' token in a
    case description must NOT be swallowed into the $0 route (an over-exclusion would silently
    drop legitimate paid proposals)."""
    assert _is_run_request("run eval on the freeform case") is True
    assert _is_run_request("grade the free-text case") is True


def test_paid_run_table_is_not_excluded_by_the_zero_dollar_guard():
    """The PAID table stays paid: none of these carry a $0 trigger, so the deterministic
    cost-confirm fallback still serves them (the guard never over-reaches)."""
    for msg in ("run it live", "fresh grade", "run eval", "run this case"):
        assert _is_run_request(msg) is True, msg
    for msg in ("grade all the cases", "run the whole suite"):
        assert _is_grade_all_request(msg) is True, msg


def test_is_grade_all_request_excludes_zero_dollar_cohort_asks():
    assert _is_grade_all_request("run a $0 replay of all cases") is False
    assert _is_grade_all_request("grade all cases") is True  # non-vacuous


# ── the litellm loop end-to-end: no paid directive on a $0 ask ─────────────────────────────


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


def _stub_completion(turns):
    state = {"i": 0, "calls": []}

    def _completion(**kwargs):
        state["calls"].append(kwargs)
        idx = state["i"]
        state["i"] += 1
        chunks = turns[idx] if idx < len(turns) else [_finish_chunk()]
        return iter(chunks)

    _completion.state = state
    return _completion


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    """A ToolContext bound to the real (frozen) BFF ops over a tmp config DB, pinned to the
    neutral _core workspace — the confirm-fallback fixture pattern."""
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


def _run_litellm(ctx, completion, *, message):
    async def _drain():
        return [
            e
            async for e in _litellm_loop(
                message, ctx, None,
                provider="azure", model="gpt-4.1", api_key="sk-TEST", api_base=None,
                _completion=completion,
            )
        ]

    return asyncio.run(_drain())


def _paid_directives(events):
    return [
        e["part"]
        for e in events
        if e["event"] == "tool_result"
        and e["part"].get("type") in ("tool-propose_live_run", "tool-propose_run_all")
    ]


def test_litellm_fallback_never_opens_the_paid_modal_on_the_defect_message(ctx):
    """End-to-end on the litellm engine: the model narrates without a tool call (the fallback's
    trigger condition) on the VERBATIM defect message → NO paid cost-confirm directive reaches
    the stream. Before the fix this emitted tool-propose_live_run (the live defect)."""
    narrate_only = _stub_completion(
        [[_text_chunk("Here is the stored result. "), _finish_chunk("stop")]]
    )
    events = _run_litellm(ctx, narrate_only, message=DEFECT_MESSAGE)
    assert _paid_directives(events) == [], [e["event"] for e in events]
    assert events[-1]["event"] == "done"


def test_litellm_zero_dollar_ask_served_by_review_runs_stays_zero_dollar(ctx):
    """The model routes CORRECTLY (calls review_runs) on the $0 ask → the read runs and the
    post-loop fallback still appends NO paid directive."""
    routes_to_review = _stub_completion(
        [
            [_toolcall_chunk(index=0, name="review_runs", arguments="{}", call_id="r"), _finish_chunk("tool_calls")],
            [_text_chunk("Here is the stored report."), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, routes_to_review, message=DEFECT_MESSAGE)
    assert any(e["event"] == "tool_call" and e["name"] == "review_runs" for e in events)
    assert _paid_directives(events) == []
    assert events[-1]["event"] == "done"


# ── RUN-TRAIL-CASE-SCOPE — the $0 route carries the case the user NAMED ────────────────────


def test_zero_dollar_case_token_extracts_the_named_case():
    """The deterministic fallback must not drop the case the user named: a cv_/case-id-shaped
    (underscore-carrying) token is extracted from the message; prose without one → None; a
    Lithrim tool name echoed in prose is never mistaken for a case id."""
    from agent.loop import _zero_dollar_case_token

    assert _zero_dollar_case_token(DEFECT_MESSAGE) == "cv_mts_002_clean_subsumption_alzheimers"
    assert _zero_dollar_case_token("run a $0 replay and show the report") is None
    assert _zero_dollar_case_token("replay it via review_runs for free") is None


def test_litellm_zero_dollar_fallback_serves_review_runs_with_the_case_token(ctx):
    """The narrate-only failure on the VERBATIM defect message → the deterministic
    ZERO-DOLLAR-ROUTE fallback serves the $0 read itself, WITH the named case: a review_runs
    tool_call carrying case_id, the caseId-threaded audit card, and still NO paid directive."""
    narrate_only = _stub_completion(
        [[_text_chunk("Here is the stored result. "), _finish_chunk("stop")]]
    )
    events = _run_litellm(ctx, narrate_only, message=DEFECT_MESSAGE)
    calls = [e for e in events if e["event"] == "tool_call" and e["name"] == "review_runs"]
    assert len(calls) == 1, [e["event"] for e in events]
    assert calls[0]["input"] == {"case_id": "cv_mts_002_clean_subsumption_alzheimers"}
    cards = [
        e["part"] for e in events
        if e["event"] == "tool_result" and e["part"].get("type") == "tool-audit_log"
    ]
    assert cards and cards[0]["output"].get("caseId") == "cv_mts_002_clean_subsumption_alzheimers"
    assert _paid_directives(events) == []
    assert events[-1]["event"] == "done"


def test_litellm_zero_dollar_fallback_is_self_limiting(ctx):
    """When the model DID call review_runs itself, the fallback is SKIPPED — exactly one
    review_runs call reaches the stream (no double-serve)."""
    routes_to_review = _stub_completion(
        [
            [_toolcall_chunk(index=0, name="review_runs", arguments="{}", call_id="r"), _finish_chunk("tool_calls")],
            [_text_chunk("Here is the stored report."), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, routes_to_review, message=DEFECT_MESSAGE)
    calls = [e for e in events if e["event"] == "tool_call" and e["name"] == "review_runs"]
    assert len(calls) == 1
    assert _paid_directives(events) == []


def test_litellm_plain_run_request_does_not_trigger_the_zero_dollar_fallback(ctx):
    """A plain (paid-table) run request still routes to the cost-confirm fallback, never the
    $0 read — the new fallback is trigger-phrase-scoped exactly like the guard."""
    narrate_only = _stub_completion(
        [[_text_chunk("I will surface the modal. "), _finish_chunk("stop")]]
    )
    events = _run_litellm(ctx, narrate_only, message="run eval on this case")
    assert len(_paid_directives(events)) == 1
    assert not any(e["event"] == "tool_call" and e["name"] == "review_runs" for e in events)


def test_review_runs_description_asks_for_the_named_case():
    """The tool description tells the model to pass case_id when the human names a case —
    the model-behavioral half of the fix (the deterministic half is the fallback above)."""
    desc = _desc("review_runs")
    assert "case_id" in desc


# ── REPLAY-HONESTY — the 409 stale-signature refusal propagates VERBATIM ───────────────────


def _stub_ctx(review_runs_fn):
    """A minimal ToolContext whose ops are no-op spies (SDK-free; the chat-fresh-grade
    pattern) with review_runs injectable."""
    noop = lambda **_kw: {}  # noqa: E731
    return ToolContext(
        author_judge=noop,
        get_judge=noop,
        run_eval_replay=noop,
        get_agent=noop,
        author_flag=noop,
        review_runs=review_runs_fn,
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
        default_agent=AGENT,
    )


def test_review_runs_tool_result_carries_the_stale_signature_guard_verbatim():
    """REPLAY-HONESTY: when the $0 read refuses with the SIGNATURE-1 stale-grade_signature 409,
    the tool result the model sees carries the guard's actionable message VERBATIM — never
    swallowed into a generic error, and never silently escalated to a paid proposal (no
    cost-confirm directive is emitted).

    MUTATION (named): swallow the detail (`_error("Could not read run history.")`) or emit
    propose_live_run_part on the failure path → RED."""

    def _refuse(**_kw):
        raise HTTPException(status_code=409, detail=STALE_GUARD)

    ctx = _stub_ctx(_refuse)
    res = asyncio.run(review_runs_handler(ctx, {}))
    assert res.get("is_error")
    text = "".join(b.get("text", "") for b in res.get("content", []))
    assert STALE_GUARD in text, "the guard's actionable message must ride the tool result VERBATIM"
    # no silent escalation: the failure emits NO gen-UI part — in particular no paid directive
    assert ctx.parts == []
    assert ctx.run_results == []
