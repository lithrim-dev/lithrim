"""FIRST-CONTACT-1: the first chat message on an install without the [agent] extra (the Docker
image) must yield an ACTIONABLE SSE error — "assign the assistant a model in Connect AI" — not a
dead stream the shell renders as "Couldn't reach the server".

The cliff: ``run_chat`` dispatches to ``_run_sdk_chat`` when no chat provider is configured, and
its ``from claude_agent_sdk import …`` raises AFTER the SSE headers are sent. The dispatcher must
convert that into the standard ``{"event": "error", "detail": …}`` the shell already renders.

$0/offline; the SDK path is simulated with a generator that raises the real failure.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

from agent import loop as chat_loop  # noqa: E402


def _events(coro_gen):
    async def collect():
        return [e async for e in coro_gen]

    return asyncio.run(collect())


def test_missing_agent_extra_yields_actionable_error(monkeypatch):
    monkeypatch.delenv("LITHRIM_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async def sdk_unavailable(message, ctx, history=None, source=None):
        raise ModuleNotFoundError("No module named 'claude_agent_sdk'", name="claude_agent_sdk")
        yield  # pragma: no cover — makes this an async generator

    monkeypatch.setattr(chat_loop, "_run_sdk_chat", sdk_unavailable)
    events = _events(chat_loop.run_chat("hello", ctx=object()))
    assert events, "the stream died with no events — the shell shows 'Couldn't reach the server'"
    err = [e for e in events if e.get("event") == "error"]
    assert err, events
    detail = err[0]["detail"]
    assert "Connect AI" in detail and "assistant" in detail, detail
    # friendlyError passthrough contract: short, no slash/brace/path — the shell keeps it verbatim.
    assert len(detail) <= 160 and "/" not in detail and "{" not in detail, detail


def test_unrelated_import_error_still_raises(monkeypatch):
    """Only the SDK-missing case is translated — a different missing module is a real bug and
    must not be masked as a configure-me message."""
    monkeypatch.delenv("LITHRIM_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async def other_import_error(message, ctx, history=None, source=None):
        raise ModuleNotFoundError("No module named 'left_pad'", name="left_pad")
        yield  # pragma: no cover

    monkeypatch.setattr(chat_loop, "_run_sdk_chat", other_import_error)
    try:
        _events(chat_loop.run_chat("hello", ctx=object()))
    except ModuleNotFoundError as exc:
        assert exc.name == "left_pad"
    else:
        raise AssertionError("a non-SDK ModuleNotFoundError was swallowed")
