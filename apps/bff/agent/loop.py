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
    {"event": "run_result",      "result": {...}}                 # CHATBIND-2 (D4): the chat's
        # $0 REPLAY record, lifted so the shell threads it into the shared runResult (the
        # run-bearing Report/Judge tabs render it). BYTE-SAME to the manual Run-eval result;
        # only run_eval (replay-only) emits it -> no paid run is ever lifted here.
    {"event": "error",           "detail": str}
    {"event": "done",            "cost_usd": float|None, "cost_label": str}
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from .tools import _TOOL_SPECS, ToolContext, build_sdk_tools

_SYSTEM_PROMPT = (
    "You are Lithrim's setup assistant inside an eval-config product. You drive the whole "
    "journey from a blank slate by calling the provided tools, in the natural order "
    "Domain -> Judge -> Flag -> Run -> Review:\n"
    "  - get_agent: read the agent/domain (its judges, ontology, tools) -- $0.\n"
    "  - assemble_agent: edit the agent's judges roster (add/remove ONE known judge; an "
    "audited config write) -- you cannot build an agent from scratch or invent a judge.\n"
    "  - get_judge / author_judge: read a judge, or author one by ASSIGNING ontology flag "
    "lenses to a role (an audited config write).\n"
    "  - delete_judge: REVERT a judge to its default lens (remove its authored config; an "
    "audited config write) -- reversible, re-author any time. You CANNOT delete an agent "
    "(human-only) or fire a paid run.\n"
    "  - author_flag: EDIT an existing flag's tier/gradeable in the ontology (an audited "
    "config write) -- you cannot invent owners.\n"
    "  - create_flag: CREATE a NEW reference (non-gradeable) flag in the ontology (an audited "
    "config write) -- reference flags are skip-logged, never scored; you CANNOT create a "
    "gradeable/scoreable flag (that needs a backend re-snapshot).\n"
    "  - delete_flag: DELETE a REFERENCE flag (an audited config write; reversible) -- only an "
    "unused reference flag; a gradeable/contract code, or one a judge or case uses, is refused.\n"
    "  - add_grounding_contract: ADD a grounding (verification) contract for a flag (an audited "
    "config write) -- the step-5 'add grounding contracts' move that binds a flag to a tool-grounded "
    "floor (e.g. snomed_subsumption, record_presence, presence_check); replaces an "
    "existing contract for that flag, else appends; $0, never a paid run.\n"
    "  - kb_context: RETRIEVE + SHOW the relevant HIPAA knowledge-base section(s) for a topic or "
    "finding ($0, read-only). It is a CONTEXT AID -- it grounds the discussion in the source policy "
    "but NEVER changes a verdict or clears a finding. Use it to show 'what the policy actually says', "
    "not to decide the outcome. Leave the namespace unset (it defaults to 'hipaa'); never pass the "
    "index name 'hipaa-compliancev2'.\n"
    "  - run_eval: run a $0 REPLAY evaluation and show the verdict.\n"
    "  - run_eval_pack: run a $0 REPLAY eval-pack BATCH over one or more agents and show "
    "the run history -- a live batch (one paid call per agent) is the human's.\n"
    "  - review_runs: review the run history, the latest run's provenance, and the audit "
    "trail of everything you authored -- $0.\n"
    "  - show_case: show the SOURCE case (transcript + artifact + the planted label) as an inline "
    "Case Summary card -- $0; use it to let the human SEE what they're about to evaluate.\n"
    "  - focus_artifact: open + focus the artifact side-panel on a tab (case | report | judges | "
    "config | corpus) to SHOW your work -- 'case' is the SOURCE INPUT (transcript + artifact + "
    "the planted label) the council grades; $0, a UI directive (never a paid run).\n"
    "  - propose_live_run: when the human wants the REAL/LIVE verdict (not a $0 replay) -- e.g. on "
    "an imported case with no replay baseline -- surface the cost-confirm modal so THEY can "
    "authorize the paid run. $0; you only PROPOSE, you never spend.\n"
    "You can NEVER fire a paid run; a live or in-process run -- single or batch -- is the "
    "human's explicit cost-confirmed action (offer propose_live_run; their modal-confirm spends). "
    "If a tool returns an error (an "
    "off-lens assignment, an unknown or out-of-snapshot flag, an unknown judge role), "
    "surface it plainly and propose a valid alternative -- never claim success you did not get.\n\n"
    "HONESTY IS THE PRODUCT (load-bearing -- never violate, this IS what Lithrim sells):\n"
    "  - The verdict a tool returns IS the verdict. If run_eval reports verdict=reject, the case "
    "was REJECTED -- never say it 'passed', is 'clean', or that 'nothing stands'. If verdict=approve, "
    "say approved. State the tool's verdict verbatim; never state a cleaner result than the tool gave.\n"
    "  - Findings a tool lists as STILL STANDING are real and DRIVE the verdict -- enumerate them. "
    "NEVER claim zero / no active findings when the tool listed any.\n"
    "  - A grounded suppression is a SPECIFIC corrected false-positive ('FINDING suppressed by TOOL "
    "because REASON'). It does NOT mean the other findings are false or that the note is clean. "
    "Correcting 2 of N false positives while M findings still stand is the HONEST story -- tell it "
    "exactly that way: the tools fixed these specific judge errors AND these real issues remain.\n"
    "  - A manufactured win is a product FAILURE. The entire value is verifiable truth, including the "
    "issues that remain -- so an honest reject (with the false positives corrected) is a WIN to narrate, "
    "never something to round up to a pass."
)


def _system_prompt(active_agent: str) -> str:
    """CHATBIND-1 (S-BS-103): the active-agent-aware system prompt. ``_SYSTEM_PROMPT`` is
    the static base; this appends a stanza NAMING the rail-selected agent so the model
    targets it BY DEFAULT. The live bug was a static prompt with no active-agent context:
    the model emitted ``ws0_default`` for the agent-scoped tools (get_agent/run_eval), so
    chat reviewed the wrong case. The handlers already default an OMITTED arg to
    ``ctx.default_agent`` (tools.py) -- naming the agent here is what stops the model
    supplying a stale ``ws0_default`` in the first place. No A-SAFE surface changes: this
    is the system_prompt string only; the deny-hook + isolation in ``_build_options`` are
    byte-identical."""
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"The current evaluation in this workspace is the agent `{active_agent}`. Operate on "
        f"it BY DEFAULT: get_agent, run_eval, run_eval_pack, and review_runs target "
        f"`{active_agent}` unless the user EXPLICITLY names another agent. When the user says "
        f'"this case", "the current case", "this agent", or "the runs", they mean '
        f"`{active_agent}`.\n\n"
        "Drive the artifact side-panel as you work (CHATBIND-2/3): when the human wants to SEE or "
        "explore the case -- the transcript, the scribe artifact, or what defect is planted -- call "
        "show_case to drop an inline Case Summary card (its \"View case\" opens the full Case tab); this "
        "is the teaching move: look at the input, then run, then compare the verdict to the planted label. "
        "After you produce a verdict "
        'or review runs, call focus_artifact("judges") for the council votes or '
        'focus_artifact("report") for the composite; after you author or edit a judge or flag, '
        'call focus_artifact("config"); when you discuss the correction corpus or flywheel, '
        'call focus_artifact("corpus"). Pair the inline card with the pane focus so the human '
        "SEES the result -- it is $0 and can never fire a paid run. "
        "CALIBRATION (Act 3 -- make the judge right): when the human wants to optimize, tune, or "
        "calibrate a judge, call get_judge(role) to surface the JudgeEditor card; it carries the "
        "OPTIMIZE button -- a cost-confirmed paid DSPy tune the HUMAN authorizes (you propose by "
        "surfacing the card, the human spends; you can never optimize yourself). The card then shows "
        "the honest baseline->optimized held-out delta to compare."
    )


# The BYO-Claude cost figure the SDK reports is the subscription-EQUIVALENT estimate,
# not a per-loop charge (fold 4 — cost honesty, consistent with the honest-Δ discipline).
COST_LABEL = "subscription-equivalent estimate (BYO-Claude desktop — not a per-call charge)"


async def _deny_non_lithrim(input_data, tool_use_id, context):
    """The A-SAFE floor (S-BS-90): a deny-by-default PreToolUse gate. ``allowed_tools`` only
    governs prompting, and ``permission_mode="bypassPermissions"`` skips prompts, so the ONLY
    mechanism that gates EVERY tool call regardless of permission rules is a PreToolUse hook
    (claude-agent-sdk: ``can_use_tool`` is *not* invoked under bypass). This bounds the loop to
    the in-process ``mcp__lithrim__*`` tools — a built-in (Bash/Read/Write/...) is refused at the
    tool layer, not merely declined by persona (the live hole probe-1 found + the smoke proved).

    FAIL-CLOSED: this runs under bypass, where a raising hook could fail OPEN, so it never raises
    and default-DENIES anything not provably a lithrim tool (a missing/None tool_name -> deny)."""
    try:
        name = (input_data or {}).get("tool_name") or ""
    except Exception:
        name = ""
    if name.startswith("mcp__lithrim__"):
        return {}  # pass-through: allowed (no decision == allow under the existing allowlist)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{name or '<unknown>'} is not a Lithrim tool; this agent is bounded to "
                "mcp__lithrim__* (it can never fire a paid run or touch the host)."
            ),
        }
    }


def _build_options(ctx: ToolContext):
    """ClaudeAgentOptions for the BYO-Claude loop over the in-process tools (lazy SDK).

    A-SAFE floor (S-BS-90): the PreToolUse deny hook (``_deny_non_lithrim``) is the AUTHORITATIVE
    gate — ``allowed_tools`` is defense-in-depth (prompting only) and ``bypassPermissions`` skips
    prompts. SDK isolation: ``setting_sources=[]`` (do NOT inherit the user's ~/.claude settings /
    their MCP servers / auto-allow rules) + ``skills=[]`` (no skill listing; a context filter, not
    a sandbox -- the hook is the real gate). The in-process MCP server is passed in-options, so
    isolation does not touch it (the 8 tools still load -- A-WORKS, live-confirmed)."""
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, create_sdk_mcp_server

    tools = build_sdk_tools(ctx)
    server = create_sdk_mcp_server(name="lithrim", version="0.1.0", tools=tools)
    allowed = [f"mcp__lithrim__{name}" for _, name, *_ in _TOOL_SPECS]
    return ClaudeAgentOptions(
        mcp_servers={"lithrim": server},
        allowed_tools=allowed,  # defense-in-depth; the deny hook below is the real bound
        permission_mode="bypassPermissions",
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[_deny_non_lithrim])]},
        setting_sources=[],  # SDK isolation: no inherited ~/.claude settings / MCP servers
        skills=[],  # suppress skill listing (the hook denies Read/Bash regardless)
        system_prompt=_system_prompt(ctx.default_agent),  # CHATBIND-1: name the active agent
        max_turns=12,  # the 5-step Domain->Judge->Flag->Run->Review journey (was 8 for the spine)
    )


def _fold_history(message: str, history: list[dict] | None) -> str:
    """ONB-0 (S-BS-87): fold prior turns into a transcript PREAMBLE on the current query.

    The no-re-execution guarantee is BY CONSTRUCTION: the result is a plain ``str`` carrying
    no ``tool_use`` blocks and no assistant-role messages, so nothing in the replayed history
    can re-invoke a prior tool-call or re-spend — it is read by the model as context only.
    (The preamble's "do not re-run" line is belt-and-suspenders; the str-typing IS the proof.)
    We replay TEXT content only — the agent recovers config STATE from the live read tools
    (get_agent/get_judge) every turn, so history supplies only the conversational thread
    (the stated domain, what was taught, what was changed). Empty-content turns are dropped.
    The current ask is foregrounded LAST so the model answers this turn, not a stale one."""
    if not history:
        return message
    lines = [
        "Conversation so far (context only — do NOT re-run any tool you already called; "
        "re-read live config with the read tools if you need current state):",
    ]
    for turn in history:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        speaker = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"[{speaker}] {content}")
    lines.append("")
    lines.append(f"Now answer this current message:\n[User] {message}")
    return "\n".join(lines)


async def _real_source(
    message: str, ctx: ToolContext, history: list[dict] | None = None
) -> AsyncIterator[Any]:
    """The default source: the real ClaudeSDKClient on BYO-Claude (no API key). Prior turns
    are folded into the query string (``_fold_history``) — the SAME ``query(str)`` call shape
    as before, so replay provably cannot re-execute a tool (A4)."""
    from claude_agent_sdk import ClaudeSDKClient

    opts = _build_options(ctx)
    async with ClaudeSDKClient(options=opts) as client:
        await client.query(_fold_history(message, history))
        async for msg in client.receive_response():
            yield msg


async def run_chat(
    message: str,
    ctx: ToolContext,
    *,
    history: list[dict] | None = None,
    source: Callable[[str, ToolContext, list[dict] | None], AsyncIterator[Any]] | None = None,
) -> AsyncIterator[dict]:
    """Drive the loop and yield SSE event dicts. ``history`` is the client-replayed prior
    turns (text-only; default ``None`` -> no preamble -> back-compatible). ``source`` defaults
    to the real SDK; tests pass a stub async generator factory
    ``(message, ctx, history) -> AsyncIterator[msg]``."""
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )

    src = source or _real_source
    cost_usd: float | None = None
    try:
        async for msg in src(message, ctx, history):
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
            # CHATBIND-2 (D4): lift any $0 replay record run_eval stashed this turn into a
            # run_result event -> the shell threads it into the shared runResult so the focused
            # Report/Judge tab shows THIS run. Byte-same to the manual Run-eval result; only the
            # replay-only run_eval emits it, so no paid run ever streams here.
            while ctx.run_results:
                yield {"event": "run_result", "result": ctx.run_results.pop(0)}
    except Exception as exc:  # surface a loop/transport failure to the pane, don't 500
        yield {"event": "error", "detail": str(exc)}
        return
    yield {"event": "done", "cost_usd": cost_usd, "cost_label": COST_LABEL}


def sse_format(event: dict) -> str:
    """One SSE frame (``data: <json>\\n\\n``) for a run_chat event."""
    return f"data: {json.dumps(event, default=str)}\n\n"
