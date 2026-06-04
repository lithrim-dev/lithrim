"""The CORE SDK-MCP tools (UAP-5b D3): the 2-3 tool spine the conversation drives.

Each tool is a THIN wrapper over an EXISTING BFF op (FROZEN — wrapped, never
modified). The wrappers run inside the BFF process, so every config write goes
through the same audited path the click-driven UI uses (R0 — the conversation IS
the audit log). The CORE set (D-A, resolved at plan-review):

    author_judge -> the audited PUT /v1/judges/{role} logic (owner<->emit + snapshot
                    + validator-ref gates INTACT — a bad assignment 422s and the
                    agent SURFACES it, never bypasses).
    get_judge    -> the $0 GET /v1/judges/{role} preview (read-only).
    run_eval     -> REPLAY ONLY ($0). The A-SAFE crux: this tool's input schema has
                    NO confirm/in_process/live field and the handler hardcodes
                    replay, so the AGENT HAS NO PATH TO A PAID RUN. A paid run is
                    100% the human's in-DOM modal-confirm calling the existing
                    confirm-gated endpoint. The agent proposes; only the human spends.

The handler bodies + schemas here are SDK-FREE (no claude_agent_sdk import) so the
A-SAFE / audited-write tests exercise them without the SDK. ``build_sdk_tools``
lazy-wraps them with the SDK ``@tool`` decorator (import-isolation, A5).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .adapter import judge_part, verdict_part

# Plain-dict input schemas (SDK-free; the A-SAFE test asserts the paid keys are
# ABSENT from RUN_EVAL_SCHEMA — the agent literally cannot request a paid run).
AUTHOR_JUDGE_SCHEMA: dict[str, Any] = {
    "role": str,
    "assigned_flags": list,
    "rationale": str,
}
GET_JUDGE_SCHEMA: dict[str, Any] = {"role": str}
RUN_EVAL_SCHEMA: dict[str, Any] = {"agent": str}
# The paid knobs the agent must NEVER reach. Asserted absent from RUN_EVAL_SCHEMA by
# the A-SAFE test — a regression that adds one here fails the build.
PAID_KEYS = ("confirm", "in_process", "live")


@dataclass
class ToolContext:
    """The bound BFF ops + a parts sink, injected by the SSE route (so apps/bff/agent/
    never imports app.py -> no circular import). Each callable wraps an EXISTING
    endpoint function with the deps already resolved.

    - ``author_judge(role, assigned_flags, rationale) -> dict``  (raises HTTPException on
      a gate violation; the handler turns that into an output-error tool result)
    - ``get_judge(role) -> dict``
    - ``run_eval_replay(agent) -> dict``  (live=in_process=False, ALWAYS — the A-SAFE crux)
    - ``default_agent``: the agent the tools default to.
    """

    author_judge: Callable[..., dict]
    get_judge: Callable[..., dict]
    run_eval_replay: Callable[..., dict]
    default_agent: str = "ws0_default"
    parts: list[dict] = field(default_factory=list)

    def emit(self, part: dict) -> None:
        self.parts.append(part)


def _text(summary: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": summary}]}


def _error(summary: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": summary}], "is_error": True}


async def author_judge_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    role = str(args.get("role") or "")
    assigned = list(args.get("assigned_flags") or [])
    rationale = str(args.get("rationale") or "authored via the conversational shell")
    try:
        res = ctx.author_judge(role=role, assigned_flags=assigned, rationale=rationale)
    except Exception as exc:  # HTTPException (422/404) or anything the op raises
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not author judge {role!r}: {detail}. The assignment was NOT persisted "
            f"(the owner<->emit / snapshot gate held). Propose a valid lens and retry."
        )
    ctx.emit(judge_part(role, ctx.default_agent))
    return _text(
        f"Authored judge {role!r} with assigned flags {res.get('assigned_flags', assigned)} "
        f"(actor {res.get('actor', {}).get('id', '?')}). The write is audited."
    )


async def get_judge_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    role = str(args.get("role") or "")
    try:
        res = ctx.get_judge(role=role)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Could not read judge {role!r}: {detail}.")
    ctx.emit(judge_part(role, ctx.default_agent))
    return _text(
        f"Judge {role!r}: model={res.get('model') or '(unbound)'}, "
        f"assigned_flags={res.get('assigned_flags', [])}, "
        f"questions={len(res.get('questions') or [])}."
    )


async def run_eval_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # A-SAFE: replay ONLY. No confirm/in_process/live is read or honored — the bound
    # ctx.run_eval_replay hardcodes the $0 path. The agent cannot spend here.
    agent = str(args.get("agent") or ctx.default_agent)
    try:
        record = ctx.run_eval_replay(agent=agent)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Replay run failed for {agent!r}: {detail}.")
    ctx.emit(verdict_part(record))
    composite = record.get("composite") or {}
    return _text(
        f"Ran a $0 REPLAY eval for {agent!r}: verdict={composite.get('verdict', '—')}. "
        f"(A live/in-process PAID run is the human's call — confirm it in the cost modal.)"
    )


# (handler, name, description, schema) — the spine. run_eval's description states the
# replay-only contract so the model does not try to request a paid run through it.
_TOOL_SPECS: list[tuple[Callable, str, str, dict]] = [
    (
        author_judge_handler,
        "author_judge",
        "Author a judge by ASSIGNING ontology flag lenses to a role (audited config "
        "write). Rejects (422) an off-lens / off-snapshot assignment — surface the "
        "error, do not retry blindly.",
        AUTHOR_JUDGE_SCHEMA,
    ),
    (
        get_judge_handler,
        "get_judge",
        "Read a judge's current config + derived questions ($0, no write). Use before "
        "authoring to see the assignable lens.",
        GET_JUDGE_SCHEMA,
    ),
    (
        run_eval_handler,
        "run_eval",
        "Run a $0 REPLAY evaluation and render the verdict card. REPLAY ONLY — this "
        "tool can never fire a paid (live/in-process) run; a paid run is the human's "
        "explicit cost-confirmed action.",
        RUN_EVAL_SCHEMA,
    ),
]


def build_sdk_tools(ctx: ToolContext) -> list[Any]:
    """Lazy-wrap the SDK-free handlers with the Claude Agent SDK ``@tool`` decorator
    (import-isolation, A5 — claude_agent_sdk is imported only here, when the SSE route
    builds the loop). Each SDK tool closes over ``ctx``."""
    from claude_agent_sdk import tool  # lazy — keeps the [agent] dep off default imports

    sdk_tools = []
    for handler, name, desc, schema in _TOOL_SPECS:

        def _make(h):
            async def _wrapped(args):
                return await h(ctx, args)

            return _wrapped

        sdk_tools.append(tool(name, desc, schema)(_make(handler)))
    return sdk_tools


def part_to_json(part: dict) -> str:
    return json.dumps(part, default=str)
