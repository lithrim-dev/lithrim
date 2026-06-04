"""The agent loop (UAP-5b D2): ClaudeSDKClient over the in-process SDK-MCP tools,
normalized to SSE events for the shell chat pane.

``run_chat`` drives a multi-turn author->process loop and yields plain event dicts
(assistant text deltas, tool-calls, tool-results-as-gen-UI-parts, done/error). The
MESSAGE SOURCE is swappable: the default hosts the real ``ClaudeSDKClient`` on
BYO-Claude (local `claude` CLI / desktop auth — NO API key, proven in D0); tests
inject a STUB source (a pre-baked message list) so the loop + the parts-adapter run
``$0`` with no real Claude (the A2/A4 offline tests). The SDK is imported LAZILY
(only when the loop actually runs), preserving import-isolation (A5).

SSE event shapes (D-B, resolved at plan-review):
    {"event": "assistant_delta", "text": str}
    {"event": "tool_call",       "name": str, "input": dict}
    {"event": "tool_result",     "part": {type, state, output}}   # the gen-UI part
    {"event": "error",           "detail": str}
    {"event": "done",            "cost_usd": float|None, "cost_label": str}
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from .tools import _TOOL_SPECS, ToolContext, build_sdk_tools

_SYSTEM_PROMPT = (
    "You are Lithrim's setup assistant inside an eval-config product. You drive the "
    "product by calling the provided tools: read a judge (get_judge), author a judge "
    "by assigning ontology flag lenses (author_judge — an audited config write), and "
    "run a $0 replay evaluation (run_eval). You can NEVER fire a paid run; a live or "
    "in-process run is the human's explicit cost-confirmed action. If a tool returns "
    "an error (e.g. an off-lens assignment is rejected), surface it plainly and "
    "propose a valid alternative — never claim success you did not get."
)

# The BYO-Claude cost figure the SDK reports is the subscription-EQUIVALENT estimate,
# not a per-loop charge (fold 4 — cost honesty, consistent with the honest-Δ discipline).
COST_LABEL = "subscription-equivalent estimate (BYO-Claude desktop — not a per-call charge)"


def _build_options(ctx: ToolContext):
    """ClaudeAgentOptions for the BYO-Claude loop over the in-process tools (lazy SDK)."""
    from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server

    tools = build_sdk_tools(ctx)
    server = create_sdk_mcp_server(name="lithrim", version="0.1.0", tools=tools)
    allowed = [f"mcp__lithrim__{name}" for _, name, *_ in _TOOL_SPECS]
    return ClaudeAgentOptions(
        mcp_servers={"lithrim": server},
        allowed_tools=allowed,
        permission_mode="bypassPermissions",  # safe: the tools are gate/replay-bounded (A-SAFE)
        system_prompt=_SYSTEM_PROMPT,
        max_turns=8,
    )


async def _real_source(message: str, ctx: ToolContext) -> AsyncIterator[Any]:
    """The default source: the real ClaudeSDKClient on BYO-Claude (no API key)."""
    from claude_agent_sdk import ClaudeSDKClient

    opts = _build_options(ctx)
    async with ClaudeSDKClient(options=opts) as client:
        await client.query(message)
        async for msg in client.receive_response():
            yield msg


async def run_chat(
    message: str,
    ctx: ToolContext,
    *,
    source: Callable[[str, ToolContext], AsyncIterator[Any]] | None = None,
) -> AsyncIterator[dict]:
    """Drive the loop and yield SSE event dicts. ``source`` defaults to the real SDK;
    tests pass a stub async generator factory ``(message, ctx) -> AsyncIterator[msg]``."""
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )

    src = source or _real_source
    cost_usd: float | None = None
    try:
        async for msg in src(message, ctx):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        if block.text.strip():
                            yield {"event": "assistant_delta", "text": block.text}
                    elif isinstance(block, ToolUseBlock):
                        yield {"event": "tool_call", "name": block.name, "input": block.input}
            elif isinstance(msg, ResultMessage):
                cost_usd = getattr(msg, "total_cost_usd", None)
            # Drain any gen-UI parts the tool handlers emitted on this turn.
            while ctx.parts:
                yield {"event": "tool_result", "part": ctx.parts.pop(0)}
    except Exception as exc:  # surface a loop/transport failure to the pane, don't 500
        yield {"event": "error", "detail": str(exc)}
        return
    yield {"event": "done", "cost_usd": cost_usd, "cost_label": COST_LABEL}


def sse_format(event: dict) -> str:
    """One SSE frame (``data: <json>\\n\\n``) for a run_chat event."""
    return f"data: {json.dumps(event, default=str)}\n\n"
