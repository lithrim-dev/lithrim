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

from .adapter import agent_part, audit_part, flag_part, judge_part, verdict_part

# Plain-dict input schemas (SDK-free; the A-SAFE test asserts the paid keys are
# ABSENT from RUN_EVAL_SCHEMA — the agent literally cannot request a paid run).
AUTHOR_JUDGE_SCHEMA: dict[str, Any] = {
    "role": str,
    "assigned_flags": list,
    "rationale": str,
}
GET_JUDGE_SCHEMA: dict[str, Any] = {"role": str}
RUN_EVAL_SCHEMA: dict[str, Any] = {"agent": str}
# UAP-5c — the journey-completing tools (each SDK-free, paid-knob-free; the S-BS-81
# A-SAFE test asserts NO schema below carries a PAID_KEY):
GET_AGENT_SCHEMA: dict[str, Any] = {"name": str}
AUTHOR_FLAG_SCHEMA: dict[str, Any] = {
    "flag_code": str,
    "tier": str,
    "gradeable": bool,
    "rationale": str,
}
REVIEW_RUNS_SCHEMA: dict[str, Any] = {"limit": int}
# UAP-5c-2 — the eval-pack BATCH (the first tool over a PAID-CAPABLE op). The schema
# carries NO live/confirm/in_process knob; the bound _run_eval_pack hardcodes live=False,
# so the agent has no path to a paid batch (the A-SAFE re-proof, S-BS-81 generalized).
RUN_EVAL_PACK_SCHEMA: dict[str, Any] = {"pack_id": str, "agents": list}
# The paid knobs the agent must NEVER reach. Asserted absent from EVERY tool schema by
# the A-SAFE test (S-BS-81 generalization) — a regression that adds one here fails the build.
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
    - ``get_agent(name) -> dict``  (UAP-5c Domain read, $0)
    - ``author_flag(flag_code, tier, gradeable, rationale) -> dict``  (UAP-5c Flag; an
      audited ontology edit of an EXISTING flag; raises on 404/422 — the handler surfaces it)
    - ``review_runs(limit) -> dict``  (UAP-5c Review, $0 — run history + latest provenance)
    - ``run_eval_pack(pack_id, agents) -> dict``  (UAP-5c-2 batch Run; ALWAYS live=False —
      the wrapper over the paid-capable eval-pack op hardcodes the $0 path, the A-SAFE crux)
    - ``default_agent``: the agent the tools default to.
    """

    author_judge: Callable[..., dict]
    get_judge: Callable[..., dict]
    run_eval_replay: Callable[..., dict]
    get_agent: Callable[..., dict]
    author_flag: Callable[..., dict]
    review_runs: Callable[..., dict]
    run_eval_pack: Callable[..., dict]
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


async def get_agent_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # The Domain leg ($0 read): establish the agent/domain before authoring.
    name = str(args.get("name") or ctx.default_agent)
    try:
        res = ctx.get_agent(name=name)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Could not read agent {name!r}: {detail}.")
    ctx.emit(agent_part(name))
    profile = res.get("eval_profile") or {}
    return _text(
        f"Domain/agent {name!r}: judges={list(profile.get('judges') or [])}, "
        f"ontology_ref={profile.get('ontology_ref') or '(none)'}, "
        f"tools={list(profile.get('tools') or [])}."
    )


async def author_flag_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # The Flag leg (audited WRITE): edit an EXISTING flag's tier/gradeable. Never creates
    # a flag or invents owner_roles; an out-of-snapshot gradeable edit 422s and is surfaced.
    flag_code = str(args.get("flag_code") or "")
    tier = args.get("tier")
    gradeable = args.get("gradeable")
    rationale = str(args.get("rationale") or "edited via the conversational shell")
    try:
        res = ctx.author_flag(
            flag_code=flag_code, tier=tier, gradeable=gradeable, rationale=rationale
        )
    except Exception as exc:  # HTTPException (404 unknown flag / 422 snapshot) or anything
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not edit flag {flag_code!r}: {detail}. The ontology was NOT changed "
            f"(the snapshot/structural gate held). Edit an existing flag's tier/gradeable; "
            f"do not invent a flag or re-grade one outside the taxonomy snapshot."
        )
    ctx.emit(flag_part(ctx.default_agent))
    return _text(
        f"Edited flag {flag_code!r} (tier={res.get('tier')}, gradeable={res.get('gradeable')}) "
        f"for agent {ctx.default_agent!r}. The ontology working copy is audited."
    )


async def review_runs_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # The Review leg ($0 read): run history + the latest run's provenance + the config
    # audit trail (rendered by AuditView). No paid surface.
    limit = args.get("limit")
    try:
        res = ctx.review_runs(limit=int(limit) if limit else 5)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Could not read run history: {detail}.")
    runs = res.get("runs") or []
    latest = res.get("latest_run_id") or ""
    ctx.emit(audit_part(latest))
    latest_audit = res.get("latest_audit") or {}
    verdict = latest_audit.get("verdict") or (runs[0].get("verdict") if runs else "—")
    return _text(
        f"{len(runs)} run(s) on record. Latest {latest[:8] or '—'}: verdict={verdict}. "
        f"The config-change audit trail (your flag + judge edits) and this run's "
        f"provenance are shown."
    )


async def run_eval_pack_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # The batch Run leg ($0 replay). A-SAFE: NO live/confirm/in_process is read or honored —
    # the bound ctx.run_eval_pack hardcodes live=False, so the agent cannot fire a paid batch.
    # Each batched run persists provenance, so its run id round-trips to GET /v1/runs.
    pack_id = str(args.get("pack_id") or "chat-pack")
    agents = list(args.get("agents") or [ctx.default_agent])
    try:
        res = ctx.run_eval_pack(pack_id=pack_id, agents=agents)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Eval-pack batch {pack_id!r} failed: {detail}.")
    run_ids = [r for r in (res.get("run_ids") or []) if r]
    ctx.emit(audit_part(run_ids[-1] if run_ids else ""))
    outcomes = (res.get("pack") or {}).get("outcomes") or []
    verdicts = [str(o.get("verdict") or "—") for o in outcomes]
    return _text(
        f"Ran a $0 REPLAY eval-pack {pack_id!r} over {len(agents)} agent(s): "
        f"verdicts={verdicts}. {len(run_ids)} run(s) persisted — they show in the run "
        f"history. (A live batch — one paid :8002 call per agent — is the human's "
        f"cost-confirmed action, never this tool.)"
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
    (
        get_agent_handler,
        "get_agent",
        "Read an assembled agent/domain ($0, no write): its judges, ontology, tools. Use "
        "FIRST to establish the domain before authoring flags or judges.",
        GET_AGENT_SCHEMA,
    ),
    (
        author_flag_handler,
        "author_flag",
        "EDIT AN EXISTING flag's tier/gradeable in the agent's ontology (audited config "
        "write). It does NOT create a flag or invent owners; an out-of-snapshot gradeable "
        "edit is rejected (422) — surface the error, do not retry blindly.",
        AUTHOR_FLAG_SCHEMA,
    ),
    (
        review_runs_handler,
        "review_runs",
        "Review the run history, the latest run's provenance, and the config-change audit "
        "trail ($0, no write). Use to show what was authored and what a run decided.",
        REVIEW_RUNS_SCHEMA,
    ),
    (
        run_eval_pack_handler,
        "run_eval_pack",
        "Run a $0 REPLAY eval-pack BATCH over one or more agents and render the run "
        "history. REPLAY ONLY — like run_eval it can never fire a paid (live) batch; one "
        "paid :8002 call per agent is the human's explicit cost-confirmed action.",
        RUN_EVAL_PACK_SCHEMA,
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
