"""CONV-RUNTIME-1 — the provider-agnostic conversation runtime (the litellm OpenAI-tools loop).

Hermetic / $0 / offline: ``litellm.completion`` is MOCKED end-to-end (no network), so the
litellm conversation loop, the tool-schema converter, the A-SAFE whitelist, the one-step
pacing, and the provider-config dispatch all run with no real LM and no Azure.

The Anthropic / BYO-Claude SDK path is the REGRESSION GUARD (it lives in
``tests/test_uap5b_chat.py`` + ``tests/test_asafe_tool_gate.py`` — byte-identical for the
anthropic/unset case). This file proves the NEW non-anthropic engine emits the SAME SSE event
contract and carries the same A-SAFE floor by construction (whitelist dispatch + pacing).

Non-vacuity: each A-SAFE / pacing assertion names the mutation that reddens it (the driver's
discipline), and the secret-hygiene assertion is the typed key string ABSENT from the response.
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
from agent.loop import (  # noqa: E402
    _chat_provider_config,
    _litellm_loop,
    _openai_tool_schemas,
    run_chat,
)

AGENT = "conv_runtime_test"


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
    """Return a fake ``litellm.completion`` that streams ``turns[i]`` on the i-th call.

    Each turn is a list of streamed chunks (the i-th ``completion(stream=True)`` returns an
    iterator over them). Records the calls so the loop's message-threading can be asserted.
    """
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
    neutral _core workspace (the isolation seam) — the SAME fixture the UAP-5b offline suite uses."""
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


def _run_litellm(ctx, completion, *, message="hello", provider="openai", model="gpt-4o"):
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


# ── 1. the tool-schema converter ───────────────────────────────────────────────────────


def test_openai_tool_schemas_covers_every_tool_spec():
    """One OpenAI function-tool per ``_TOOL_SPECS`` entry; names match; all params optional."""
    schemas = _openai_tool_schemas()
    names = [s["function"]["name"] for s in schemas]
    spec_names = [n for _, n, *_ in agent_tools._TOOL_SPECS]
    assert names == spec_names  # one per tool, same order
    assert len(schemas) == 24
    for s in schemas:
        assert s["type"] == "function"
        fn = s["function"]
        assert isinstance(fn["description"], str) and fn["description"]
        params = fn["parameters"]
        assert params["type"] == "object"
        # ALL params optional — the handlers default omitted args (mirror the SDK plain-dict schema)
        assert params.get("required", []) == []


def test_openai_tool_schemas_maps_python_types():
    """str→string, int→integer, bool→boolean, list→array, dict→object. Spot-check the
    spine: show_case (str), run_eval (str selector, NO paid knob), create_judge (str)."""
    by_name = {s["function"]["name"]: s["function"]["parameters"]["properties"] for s in _openai_tool_schemas()}
    # run_eval: {agent: str, case_id: str} — both strings, NO paid knob in the JSON-schema
    run_props = by_name["run_eval"]
    assert run_props["agent"]["type"] == "string"
    assert run_props["case_id"]["type"] == "string"
    assert not any(k in run_props for k in agent_tools.PAID_KEYS)
    # author_flag: gradeable is a bool → "boolean"; tier str → "string"
    flag_props = by_name["author_flag"]
    assert flag_props["gradeable"]["type"] == "boolean"
    assert flag_props["tier"]["type"] == "string"
    # add_grounding_contract: params is a dict → "object"
    assert by_name["add_grounding_contract"]["params"]["type"] == "object"
    # review_runs: limit is an int → "integer"
    assert by_name["review_runs"]["limit"]["type"] == "integer"
    # create_judge is present (PHASE2-WIRE) with its role str param
    assert by_name["create_judge"]["role"]["type"] == "string"


# ── 2. the litellm conversation loop — happy path ──────────────────────────────────────


def test_litellm_loop_happy_path_streams_text_then_runs_a_tool(ctx):
    """A streamed text delta + ONE show_case tool_call (then a no-tool finish) → the loop emits
    assistant_delta(text) → tool_call(show_case) → tool_result(a tool-case_summary part) → done.
    The handler ACTUALLY ran (a part was drained). MOCKED litellm — no network."""
    completion = _stub_completion(
        [
            # turn 1: stream prose, then a show_case tool call, then finish
            [
                _text_chunk("Let me open that case. "),
                _toolcall_chunk(index=0, name="show_case", arguments='{"case_id": "c-1"}', call_id="call_1"),
                _finish_chunk("tool_calls"),
            ],
            # turn 2: a plain text reply, no tool calls → loop stops
            [_text_chunk("Here it is."), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, completion)
    kinds = [e["event"] for e in events]
    assert kinds == ["assistant_delta", "tool_call", "tool_result", "assistant_delta", "done"]
    assert events[0]["text"] == "Let me open that case. "
    assert events[1]["name"] == "show_case" and events[1]["input"] == {"case_id": "c-1"}
    part = events[2]["part"]
    assert part["type"] == "tool-case_summary" and part["output"]["case_id"] == "c-1"
    assert events[-1]["event"] == "done"
    # the model targets the configured provider/model — litellm sees the prefixed model id
    first_call = completion.state["calls"][0]
    assert first_call["model"] == "openai/gpt-4o"
    assert first_call["tool_choice"] == "auto"
    assert first_call["stream"] is True
    # the api_key is forwarded to litellm but never logged into an event
    assert first_call["api_key"] == "sk-TEST"
    assert all("sk-TEST" not in str(e) for e in events)


def test_litellm_loop_threads_the_system_prompt_and_message(ctx):
    """The first completion call carries a proper chat-completions message list:
    [system(_system_prompt), user(message)] — NOT the _fold_history preamble hack."""
    completion = _stub_completion([[_text_chunk("hi"), _finish_chunk("stop")]])
    _run_litellm(ctx, completion, message="what cases are there?")
    msgs = completion.state["calls"][0]["messages"]
    assert msgs[0]["role"] == "system" and AGENT in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "what cases are there?"}


def test_litellm_loop_malformed_tool_args_do_not_crash(ctx):
    """A malformed arguments JSON string feeds back an error tool-result, the loop finishes
    cleanly (does not raise / 500). NON-VACUOUS: the loop emits a done event, not an error-abort."""
    completion = _stub_completion(
        [
            [
                _toolcall_chunk(index=0, name="show_case", arguments="{not json", call_id="c"),
                _finish_chunk("tool_calls"),
            ],
            [_text_chunk("ok"), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, completion)
    assert events[-1]["event"] == "done"  # finished cleanly, no error-abort
    # the malformed call never produced a tool_result part (the handler never ran on bad args)
    assert not any(e["event"] == "tool_result" for e in events)


# ── 3. A-SAFE whitelist (non-vacuous) ──────────────────────────────────────────────────


def test_asafe_whitelist_blocks_bash_and_unknown_tools(ctx):
    """A tool_call for ``Bash`` and one for an unknown ``mcp__lithrim__nope`` → NEITHER dispatches
    (no handler runs, no part is emitted for either); an error tool-result is fed back and the loop
    finishes cleanly. MUTATION (the driver): remove the whitelist membership guard in
    ``_litellm_loop`` and a Bash/unknown call attempts dispatch → this test goes RED."""
    completion = _stub_completion(
        [
            [
                _toolcall_chunk(index=0, name="Bash", arguments='{"command": "rm -rf /"}', call_id="b"),
                _toolcall_chunk(index=1, name="mcp__lithrim__nope", arguments="{}", call_id="n"),
                _finish_chunk("tool_calls"),
            ],
            [_text_chunk("done"), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, completion)
    assert events[-1]["event"] == "done"
    # NO tool_call / tool_result was streamed for the non-lithrim names (nothing executed)
    assert not any(e["event"] == "tool_call" for e in events)
    assert not any(e["event"] == "tool_result" for e in events)
    assert ctx.parts == []  # no handler ran → no gen-UI part
    # the loop fed each blocked call back to the model as a tool-result error message
    second_call_msgs = completion.state["calls"][1]["messages"]
    tool_msgs = [m for m in second_call_msgs if m.get("role") == "tool"]
    assert len(tool_msgs) == 2  # both blocked calls answered (so the model isn't left hanging)
    assert all("not a Lithrim tool" in m["content"] for m in tool_msgs)


def test_asafe_whitelist_resolves_the_mcp_prefix(ctx):
    """A whitelisted tool referenced by its ``mcp__lithrim__show_case`` qualified name (the SDK
    naming) still dispatches — the whitelist resolves a bare OR prefixed name to the bare tool."""
    completion = _stub_completion(
        [
            [
                _toolcall_chunk(index=0, name="mcp__lithrim__show_case", arguments='{"case_id": "x"}', call_id="c"),
                _finish_chunk("tool_calls"),
            ],
            [_text_chunk("shown"), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, completion)
    assert any(e["event"] == "tool_result" and e["part"]["type"] == "tool-case_summary" for e in events)


# ── 4. A-SAFE: no paid run on the litellm engine ───────────────────────────────────────


def test_litellm_engine_run_eval_surfaces_the_cost_confirm_reaches_no_paid_op(ctx):
    """A-SAFE (RUN-EVAL-FRESH-1): the litellm engine drives run_eval as a FRESH-GRADE PROPOSAL —
    even if the model emits confirm/in_process/live in the tool arguments, run_eval reaches NO bound
    op at all (it only surfaces the cost-confirm directive), so no paid knob can reach a paid run.
    NON-VACUOUS: a raise-on-call spy for run_eval_replay would trip if the engine routed to a replay."""

    def _raise(**_kw):
        raise AssertionError("run_eval must NOT call run_eval_replay (the stale $0 replay)")

    ctx.run_eval_replay = _raise
    completion = _stub_completion(
        [
            [
                _toolcall_chunk(
                    index=0, name="run_eval",
                    arguments=json.dumps(
                        {"agent": AGENT, "in_process": True, "live": True, "confirm": True}
                    ),
                    call_id="r",
                ),
                _finish_chunk("tool_calls"),
            ],
            [_text_chunk("graded"), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, completion)
    # the engine surfaced the cost-confirm directive as a tool_result part (no paid op was reached)
    assert any(
        e["event"] == "tool_result" and e["part"]["type"] == "tool-propose_live_run"
        for e in events
    )


# ── 5. one-step pacing (non-vacuous) ───────────────────────────────────────────────────


def test_one_step_pacing_paces_the_second_step_write(ctx):
    """Two step-proposing writes in ONE turn → the FIRST runs, the SECOND is PACED (not executed;
    the verbatim one-step-per-turn message is fed back as its tool-result). Mirrors _pace_one_step.
    MUTATION: drop the turn-local write counter and BOTH writes execute → this goes RED."""
    ran = []

    def _author_judge_spy(*, role, assigned_flags, rationale, model=""):
        ran.append(role)
        return {"assigned_flags": assigned_flags, "actor": {"id": "t"}}

    def _create_flag_spy(*, flag_code, **kw):
        ran.append(flag_code)
        return {"flag_code": flag_code}

    ctx.author_judge = _author_judge_spy
    ctx.create_flag = _create_flag_spy
    completion = _stub_completion(
        [
            [
                _toolcall_chunk(
                    index=0, name="author_judge",
                    arguments='{"role": "risk_judge", "assigned_flags": [], "rationale": "x"}', call_id="j",
                ),
                _toolcall_chunk(
                    index=1, name="create_flag",
                    arguments='{"flag_code": "REF_FOO", "definition": "d"}', call_id="f",
                ),
                _finish_chunk("tool_calls"),
            ],
            [_text_chunk("paced"), _finish_chunk("stop")],
        ]
    )
    events = _run_litellm(ctx, completion)
    # only the FIRST step-proposing write executed; the 2nd was paced (no handler ran for it)
    assert ran == ["risk_judge"]
    # the paced call's tool-result carries the verbatim one-step pacing message
    second_call_msgs = completion.state["calls"][1]["messages"]
    tool_msgs = [m["content"] for m in second_call_msgs if m.get("role") == "tool"]
    assert any("One setup step per turn" in c for c in tool_msgs)
    assert events[-1]["event"] == "done"


def test_one_step_pacing_never_counts_reads_or_runs(ctx):
    """A read (get_agent) + a $0 replay (run_eval) in the same turn as a write are NEVER counted —
    the write still runs (it is the FIRST and only proposal), proving reads/runs are free."""
    ran = []

    def _author_judge_spy(*, role, **kw):
        ran.append(role)
        return {"assigned_flags": [], "actor": {"id": "t"}}

    def _get_agent_spy(*, name, **kw):
        return {"eval_profile": {}}

    def _run_eval_spy(*, agent, **kw):
        return {"composite": {"verdict": "approve"}, "council": {"votes": []}}

    ctx.author_judge = _author_judge_spy
    ctx.get_agent = _get_agent_spy
    ctx.run_eval_replay = _run_eval_spy
    completion = _stub_completion(
        [
            [
                _toolcall_chunk(index=0, name="get_agent", arguments="{}", call_id="g"),
                _toolcall_chunk(index=1, name="run_eval", arguments="{}", call_id="r"),
                _toolcall_chunk(
                    index=2, name="author_judge",
                    arguments='{"role": "risk_judge", "assigned_flags": [], "rationale": "x"}', call_id="j",
                ),
                _finish_chunk("tool_calls"),
            ],
            [_text_chunk("ok"), _finish_chunk("stop")],
        ]
    )
    _run_litellm(ctx, completion)
    assert ran == ["risk_judge"]  # the write ran — reads/runs ahead of it did NOT consume the budget


# ── 6. provider-config resolver + dispatch ─────────────────────────────────────────────


def test_chat_provider_config_is_none_for_unset_and_anthropic(monkeypatch, tmp_path):
    """The credit-safe default: no LITHRIM_CHAT_PROVIDER (or =anthropic) → None → the SDK path.
    Read from os.environ at turn time. No repo-root .env exists under the tmp-pointed root."""
    monkeypatch.delenv("LITHRIM_CHAT_PROVIDER", raising=False)
    # point the loop's repo-root .env/.live_env read at an empty tmp dir so a real .env can't leak in
    import agent.loop as loop_mod

    monkeypatch.setattr(loop_mod, "_provider_config_root", lambda: tmp_path, raising=False)
    assert _chat_provider_config() is None
    monkeypatch.setenv("LITHRIM_CHAT_PROVIDER", "anthropic")
    assert _chat_provider_config() is None


def test_chat_provider_config_returns_a_dict_for_openai(monkeypatch, tmp_path):
    """LITHRIM_CHAT_PROVIDER=openai (a non-anthropic provider) → {provider, model, api_key, api_base}
    read from LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY,API_BASE}."""
    import agent.loop as loop_mod

    monkeypatch.setattr(loop_mod, "_provider_config_root", lambda: tmp_path, raising=False)
    monkeypatch.setenv("LITHRIM_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("LITHRIM_CHAT_MODEL", "gpt-4o")
    monkeypatch.setenv("LITHRIM_CHAT_API_KEY", "sk-CHAT-KEY")
    cfg = _chat_provider_config()
    assert cfg["provider"] == "openai"
    assert cfg["model"] == "gpt-4o"
    assert cfg["api_key"] == "sk-CHAT-KEY"


def test_run_chat_dispatches_to_the_sdk_for_anthropic_unset(ctx, monkeypatch):
    """Dispatch: when _chat_provider_config() is None (anthropic/unset) → run_chat uses the EXISTING
    SDK source path (here a stub source standing in for the SDK), NOT the litellm loop."""
    import agent.loop as loop_mod

    monkeypatch.setattr(loop_mod, "_chat_provider_config", lambda: None)
    monkeypatch.setattr(
        loop_mod, "_litellm_loop",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("litellm must NOT run for anthropic/unset")),
    )

    async def _stub(_m, _c, _h=None):
        # a single no-content turn → the SDK consumer path runs and closes with done
        return
        yield  # pragma: no cover

    async def _drain():
        return [e async for e in run_chat("hi", ctx, source=_stub)]

    events = asyncio.run(_drain())
    assert events[-1]["event"] == "done"  # the SDK consumer path completed


def test_run_chat_dispatches_to_litellm_for_a_non_anthropic_provider(ctx, monkeypatch):
    """Dispatch: when _chat_provider_config() returns an openai dict → run_chat routes to
    _litellm_loop (the SDK source is NOT used)."""
    import agent.loop as loop_mod

    monkeypatch.setattr(
        loop_mod, "_chat_provider_config",
        lambda: {"provider": "openai", "model": "gpt-4o", "api_key": "sk-X", "api_base": None},
    )
    called = {"v": False}

    async def _fake_litellm(message, c, history, **kw):
        called["v"] = True
        called["provider"] = kw.get("provider")
        yield {"event": "done", "cost_usd": None, "cost_label": "x"}

    monkeypatch.setattr(loop_mod, "_litellm_loop", _fake_litellm)

    async def _sdk_must_not_run(_m, _c, _h=None):
        raise AssertionError("the SDK source must NOT run for a non-anthropic provider")
        yield  # pragma: no cover

    async def _drain():
        return [e async for e in run_chat("hi", ctx, source=_sdk_must_not_run)]

    events = asyncio.run(_drain())
    assert called["v"] is True and called["provider"] == "openai"
    assert events[-1]["event"] == "done"
