"""ONB-0 (S-BS-87) acceptance: conversational memory on POST /v1/chat (offline / $0).

Phase 0 of SPEC_ONBOARDING_JOURNEY: the chat loop gains a client-replayed `history`
array, threaded into a transcript PREAMBLE on the fresh ClaudeSDKClient query. These
tests re-prove the A-SAFE floor as the request surface widens:

  - A2/A3  history threads end-to-end (ChatRequest -> run_chat -> the source);
  - back-compat: no history behaves exactly as before;
  - A-SAFE text-only: ChatTurn REJECTS any smuggled paid knob/tool arg (extra=forbid);
  - A4 NO RE-EXECUTION (the load-bearing negative): replaying a history that DESCRIBES a
    prior tool-call triggers ZERO new audited writes — run_chat never iterates history
    into tool calls, and the real source folds it into a plain str (proof by construction).

Hermetic — NO real Claude, NO Azure. The loop runs with a STUB source; the audit check
runs the real (frozen) BFF ops over a tmp config DB. Requires the [bff] extra; the
loop/fold checks additionally need [agent] (skipped cleanly when absent).
"""

from __future__ import annotations

import asyncio
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

AGENT = "onb0_test"


def _fixture_agent(name: str = AGENT):
    return house_agent(name=name)


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "bench_config.sqlite"
    save_agent(_fixture_agent(), db_path=db)
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


# ── The contract: ChatTurn is text-only; ChatRequest carries history, default empty ──


def test_chat_request_history_defaults_empty_back_compatible():
    """A2: an old client sending only {message, agent} still validates (history defaults
    to []), so the contract is back-compatible."""
    req = bff.ChatRequest(message="hi", agent=AGENT)
    assert req.history == []


def test_chat_turn_rejects_a_smuggled_paid_knob():
    """A-SAFE (text-only): ChatTurn forbids extra fields, so a paid knob (confirm/live/
    in_process) or any tool arg cannot ride in on a history turn — it is REJECTED, not
    silently dropped. History can never widen the A-SAFE surface."""
    from pydantic import ValidationError

    bff.ChatTurn(role="user", content="ok")  # the only legal shape
    for smuggled in ({"confirm": True}, {"live": True}, {"in_process": True}, {"agent": "x"}):
        with pytest.raises(ValidationError):
            bff.ChatTurn(role="user", content="x", **smuggled)


def test_chat_turn_role_is_constrained():
    """Text-only contract: role is the {user, assistant} Literal — no arbitrary role."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        bff.ChatTurn(role="system", content="x")


# ── The fold: prior turns -> a plain str preamble (no tool_use, current ask last) ──


def test_fold_history_is_plain_text_with_the_current_ask_last():
    """D-A proof-by-construction: _fold_history returns a str carrying the prior turns as
    TEXT (no tool_use / assistant-message structures), with the current message foregrounded
    LAST. A str cannot re-invoke a tool — that IS the no-re-execution guarantee."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent.loop import _fold_history

    folded = _fold_history(
        "what did we just do?",
        [
            {"role": "user", "content": "my domain is radiology"},
            {"role": "assistant", "content": "I authored the risk_judge."},
            {"role": "assistant", "content": ""},  # empty -> dropped
        ],
    )
    assert isinstance(folded, str)
    assert "radiology" in folded and "I authored the risk_judge." in folded
    assert folded.rstrip().endswith("[User] what did we just do?")  # current ask last
    assert "tool_use" not in folded and "ToolUseBlock" not in folded
    # an empty-content turn contributes nothing
    assert folded.count("[Assistant]") == 1


def test_fold_history_empty_returns_the_bare_message():
    """Back-compat: no history -> no preamble -> the exact message string as before."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent.loop import _fold_history

    assert _fold_history("hello", None) == "hello"
    assert _fold_history("hello", []) == "hello"


# ── Threading + the load-bearing no-re-execution negative (run through run_chat) ──


def test_history_threads_to_the_source(env):
    """A3: run_chat delivers `history` to the message source unchanged (the stub captures
    it). This is the offline proof the thread reaches the loop."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent import run_chat

    ctx, _client = env
    captured = {}

    async def _stub(message, _c, history):
        captured["message"] = message
        captured["history"] = history
        yield _result_message()

    hist = [
        {"role": "user", "content": "my domain is radiology"},
        {"role": "assistant", "content": "Noted — radiology."},
    ]

    async def _drain():
        return [e async for e in run_chat("continue", ctx, history=hist, source=_stub)]

    asyncio.run(_drain())
    assert captured["history"] == hist  # the prior turns reached the source verbatim
    assert captured["message"] == "continue"


def test_back_compat_no_history_still_yields_done(env):
    """Back-compat: run_chat with no history still drives the loop and yields `done`
    (the widened signature is additive)."""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent import run_chat

    ctx, _client = env

    async def _stub(_message, _c, _history=None):
        yield _result_message()

    async def _drain():
        return [e async for e in run_chat("hi", ctx, source=_stub)]

    events = asyncio.run(_drain())
    assert events[-1]["event"] == "done"


def test_replaying_history_triggers_no_new_audited_write(env):
    """A4 / A-SAFE(c) — THE load-bearing negative: a history that DESCRIBES a prior
    audited tool-call, replayed through run_chat, produces ZERO new audited writes. run_chat
    folds history into the source's message arg; it never iterates history into tool calls,
    so replay cannot duplicate the write or re-spend. (Offline proxy of the live A4 check;
    the live ≥6-turn run asserts GET /v1/audit shows exactly one record, not duplicated.)"""
    pytest.importorskip("claude_agent_sdk", reason="needs the [agent] extra")
    from agent import run_chat

    ctx, client = env
    before = len(client.get("/v1/audit", params={"target_type": "judge"}).json()["records"])

    async def _benign_stub(_message, _c, _history):
        # the assistant only TALKS about a prior write; it runs no tool this turn
        yield _assistant_text("Earlier I authored the risk_judge for you.")
        yield _result_message()

    history = [
        {"role": "user", "content": "author a risk judge"},
        {"role": "assistant", "content": "Done — I called author_judge and audited it."},
        {"role": "user", "content": "thanks, what's next?"},
    ]

    async def _drain():
        return [e async for e in run_chat("ok", ctx, history=history, source=_benign_stub)]

    asyncio.run(_drain())
    after = len(client.get("/v1/audit", params={"target_type": "judge"}).json()["records"])
    assert after == before  # replaying a described write makes NO new audited write


# ── tiny SDK-message helpers (built only when [agent] is present) ──


def _assistant_text(text: str):
    import claude_agent_sdk as sdk

    return sdk.AssistantMessage(content=[sdk.TextBlock(text=text)], model="claude")


def _result_message():
    import claude_agent_sdk as sdk

    return sdk.ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="s",
        total_cost_usd=0.0,
    )
