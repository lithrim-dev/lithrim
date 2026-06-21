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
    {"event": "assistant_delta", "text": str}   # CONV-UX-1 (W2): now token-granular when the
        # SDK streams partials (include_partial_messages); whole-block fallback otherwise.
    {"event": "thinking",        "text": str}   # CONV-UX-1 (W1): a reasoning ThinkingBlock /
        # thinking_delta, surfaced as a collapsible muted section (only when the SDK emits it).
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
    "config write) -- reference flags are skip-logged, never scored. For a GRADEABLE/scoreable "
    "criterion, use author_criterion instead (the sanctioned self-serve writer, tier:core packs).\n"
    "  - delete_flag: DELETE a REFERENCE flag (an audited config write; reversible) -- only an "
    "unused reference flag; a gradeable/contract code, or one a judge or case uses, is refused.\n"
    "  - add_grounding_contract: ADD a grounding (verification) contract for a flag (an audited "
    "config write) -- the step-5 'add grounding contracts' move that binds a flag to a tool-grounded "
    "floor (e.g. snomed_subsumption, record_presence, presence_check); replaces an "
    "existing contract for that flag, else appends; $0, never a paid run.\n"
    "  - author_contract: SURFACE the contract-authoring widget INLINE so the HUMAN authors a "
    "grounding contract by FILLING A CARD in the chat (the conversational-first move; the mirror of "
    "get_judge surfacing the JudgeEditor). Use it when the human wants to AUTHOR / define / set up a "
    "grounding contract or criterion THEMSELVES: call author_contract(flag_code=…) to drop the card "
    "inline, seeded with the flag — do NOT compose the contract silently and do NOT send them to the "
    "side pane. The human's Save IS the audited write; $0, you only surface. ASSIST (FAUTH-3): when "
    "the human DESCRIBES a presence-style criterion in PROSE (e.g. 'flag a medication named in the "
    "note the patient isn't actually on'), FIRST call kb_context to CITE the org policy, THEN call "
    "author_contract(flag_code=…) — for a NAMED flag it AUTOMATICALLY opens the card PRE-FILLED with "
    "the CORRECT deterministic presence_check params (med_source / dosage_regex / token_min_len / "
    "noise_tokens). Pass source_hint=<the chart path to check the flagged term against, e.g. "
    "transcript.text or patient_profile.active_medications> to set med_source. Do NOT hand-compose "
    "the params dict yourself (the system fills the correct keys — you'd get them wrong; presence_check "
    "needs med_source + dosage_regex, NOT needle/haystack); pass suggested_params only if you already "
    "know the exact executor keys. ALWAYS say the pre-filled params are a DRAFT they edit + Save — you "
    "only PROPOSE; the human's Save is the only write and the suggestion never decides a verdict. "
    "(When YOU already know the contract_type + params, use add_grounding_contract — the agent-composes "
    "twin — instead.)\n"
    "  - author_criterion: SURFACE the criterion-authoring widget INLINE so the HUMAN mints a NEW "
    "GRADEABLE criterion -- a scoreable taxonomy code the council can RAISE -- by filling a card (the "
    "mirror of author_contract, for a gradeable code rather than a grounding contract). Use it when "
    "the human wants to CREATE / define a new gradeable criterion or scoreable flag: call "
    "author_criterion(code=…, tier=…, owner_role=…) to drop the card inline, seeded. The human reviews "
    "+ Saves; their Save is the SOLE audited write (POST /v1/criterion splices the active tier:core "
    "pack's taxonomy snapshot + ontology, gating owner ∈ production_judges + code shape + dup). You do "
    "NOT mint the code yourself; $0, never a paid run.\n"
    "  - kb_context: RETRIEVE + SHOW the relevant HIPAA knowledge-base section(s) for a topic or "
    "finding ($0, read-only). It is a CONTEXT AID -- it grounds the discussion in the source policy "
    "but NEVER changes a verdict or clears a finding. Use it to show 'what the policy actually says', "
    "not to decide the outcome. When the human asks what HIPAA/the policy says, or to 'show the "
    "source', you MUST call kb_context and then QUOTE the returned section text VERBATIM in your reply "
    "-- do NOT answer from your own knowledge, and do NOT cite a section number you did not get back "
    "from the tool. The tool's returned text IS the source to display inline; do NOT call "
    "focus_artifact('corpus') for it (the corpus tab is the correction flywheel -- a different thing, "
    "not the knowledge base). Leave the namespace unset (it defaults to 'hipaa'); never pass the "
    "index name 'hipaa-compliancev2'.\n"
    "  - run_eval: run a $0 REPLAY evaluation and show the verdict.\n"
    "  - run_eval_pack: run a $0 REPLAY eval-pack BATCH over one or more agents and show "
    "the run history -- a live batch (one paid call per agent) is the human's.\n"
    "  - review_runs: review the run history, the latest run's provenance, and the audit "
    "trail of everything you authored -- $0.\n"
    "  - ingest_cases: INGEST an arbitrary JSON dump of AI-system output into eval cases (the "
    "'eval anything' tool; an audited $0 write, never a paid run). ARGS: `json` = the JSON dump "
    "(paste it verbatim); `extraction_rules` = a plain-language description that says what ONE case "
    "is and NAMES the source collection to iterate, in backticks (e.g. \"one case per `comments`; "
    "response = the comment body; join the issue title by issue_number\"); `agent` = the target "
    "agent. It generates a JUTE transform (or REUSES the one already pinned for that agent -> "
    "instant), live-gates it on :3031, pins it, applies it, and upserts the workspace corpus. A "
    "mis-join is rejected with NOTHING pinned -- surface that plainly; never claim a partial ingest.\n"
    "  - list_cases: LIST the cases the human can evaluate -- the workspace's INGESTED corpus "
    "(every case_id), NOT the agent's single seed case -- $0; opens the Cases tab. Call it whenever "
    "they ask 'what cases are there', 'show me the cases I can evaluate', or 'load all cases'.\n"
    "  - show_case: show a SPECIFIC source case (transcript + artifact + any label) as an inline "
    "Case Summary card -- $0. Pass case_id (from list_cases) to open THAT case; omit it for the case "
    "they're exploring. NEVER claim you opened a case_id you did not pass, and describe a clean/"
    "unlabeled case as clean, never as a planted defect.\n"
    "  - focus_artifact: open + focus the artifact side-panel on a tab (case | report | judges | "
    "config | corpus) to SHOW your work -- 'case' is the SOURCE INPUT (transcript + artifact + "
    "the planted label) the council grades; $0, a UI directive (never a paid run).\n"
    "  - propose_live_run: when the human wants the REAL/LIVE verdict (not a $0 replay) -- e.g. on "
    "an imported case with no replay baseline -- surface the cost-confirm modal so THEY can "
    "authorize the paid run. $0; you only PROPOSE, you never spend.\n"
    "ALL of the tools above are ALREADY loaded and directly callable by their exact names with "
    "the documented arguments -- there is no tool-discovery or loader step in this environment, so "
    "always call the tool you need directly. If you are unsure of an argument, use the names "
    "documented above (never guess a different arg name, and never look one up).\n"
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


def _system_prompt(active_agent: str, active_case: str | None = None) -> str:
    """CHATBIND-1 (S-BS-103): the active-agent-aware system prompt. ``_SYSTEM_PROMPT`` is
    the static base; this appends a stanza NAMING the rail-selected agent so the model
    targets it BY DEFAULT. The live bug was a static prompt with no active-agent context:
    the model emitted ``ws0_default`` for the agent-scoped tools (get_agent/run_eval), so
    chat reviewed the wrong case. The handlers already default an OMITTED arg to
    ``ctx.default_agent`` (tools.py) -- naming the agent here is what stops the model
    supplying a stale ``ws0_default`` in the first place. No A-SAFE surface changes: this
    is the system_prompt string only; the deny-hook + isolation in ``_build_options`` are
    byte-identical.

    NARR-CHAT-LOOP: ``active_case`` is the case the human is exploring in the UI (the shared
    "active case"). Naming it here makes run_eval/show_case default to THAT case (the chat↔UI
    decoupling fix) -- without it the chat graded the agent's seed regardless of what was on
    screen. ``None`` (no case selected yet) appends a list_cases nudge instead. A selector, never
    a spend -- the A-SAFE surface is unchanged."""
    case_stanza = (
        f"The case the human is currently exploring is `{active_case}`. show_case and run_eval "
        f"operate on `{active_case}` BY DEFAULT (you may omit case_id) unless the user names another "
        f"case. When the user says \"this case\", \"the case\", or \"run it\", they mean "
        f"`{active_case}`. To see the other cases, call list_cases; to switch, call "
        f"show_case(case_id=…) / run_eval(case_id=…). Never claim to have opened or graded a case "
        f"you did not pass to a tool.\n\n"
        if active_case
        else (
            "No specific case is selected yet. When the human asks about cases, or to explore or "
            "run one, call list_cases first to see the ingested corpus, then show_case(case_id=…) / "
            "run_eval(case_id=…). Do not invent a case_id or operate on the seed as if it were the "
            "corpus.\n\n"
        )
    )
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"The current evaluation in this workspace is the agent `{active_agent}`. Operate on "
        f"it BY DEFAULT: get_agent, run_eval, run_eval_pack, and review_runs target "
        f"`{active_agent}` unless the user EXPLICITLY names another agent. When the user says "
        f'"this case", "the current case", "this agent", or "the runs", they mean '
        f"`{active_agent}`.\n\n"
        f"{case_stanza}"
        "CONVERSATIONAL-FIRST (SPEC_CONVERSATIONAL_FIRST -- load-bearing, never violate): the "
        "conversation IS the product. You answer with INLINE gen-UI cards in the chat -- you NEVER "
        "send the human to the side panel to see your result. show_case drops an inline Case Summary "
        "card (transcript + artifact + label); run_eval renders the inline verdict card; the clinician "
        "verdict is recorded inline. The artifact side-panel is AUXILIARY and stays CLOSED: do NOT call "
        "focus_artifact after producing a verdict, running, reviewing runs, or authoring a judge/flag -- "
        "the inline card IS the result the human reads, and opening the pane unprompted is the exact "
        "anti-pattern this product forbids. Call focus_artifact(<tab>) ONLY when the human EXPLICITLY "
        "asks to OPEN or see the FULL/RAW detail that cannot live inline: the full transcript ('open the "
        "full transcript' / 'show me the source' -> focus_artifact('case')), the full report table -> "
        "'report', the complete council/audit detail -> 'judges', the ontology config -> 'config', the "
        "correction corpus/flywheel -> 'corpus'. That explicit drill-down is the ONLY time the pane "
        "opens; otherwise keep the work in the conversation. It is $0 and can never fire a paid run. "
        "CALIBRATION (Act 3 -- make the judge right): when the human wants to optimize, tune, or "
        "calibrate a judge, call get_judge(role) to surface the JudgeEditor card; it carries the "
        "OPTIMIZE button -- a cost-confirmed paid DSPy tune the HUMAN authorizes (you propose by "
        "surfacing the card, the human spends; you can never optimize yourself). The card then shows "
        "the honest baseline->optimized held-out delta to compare.\n\n"
        + _SHEPHERD_STANZA
    )


# SHEPHERD-1 (W2): the proactive, plan-aware ONBOARDING stanza. Appended to the active-agent
# prompt as a SUPERSET — the base persona, the HONESTY contract, and the active-agent naming
# above are all intact, so a non-onboarding chat is behavior-unchanged (the back-compat test).
# It is NOT a mode flag (the Phase-1 ChatRequest/ToolContext stay un-widened): the agent reads
# the live state with the tools it already has (get_agent / review_runs) to find the current
# incomplete step, and the LAST clause degrades it to the reactive operator posture once setup
# is complete -- so a fully-configured agent's chat is answered, not led.
_SHEPHERD_STANZA = (
    "SHEPHERD THE ONBOARDING (lead, do not just react):\n"
    "  ONE STEP PER TURN, THEN STOP (non-negotiable): propose EXACTLY ONE setup step per turn -- "
    "one config PROPOSAL (one editor card) -- then STOP and end the turn. Do NOT chain multiple "
    "authoring proposals in a single turn, and do NOT propose the next step until the human has "
    "acted on the one you surfaced. Reading the live state is FREE: at the start of a turn you may "
    "freely read (get_agent / get_judge / review_runs) and show/teach -- the one-step cap is on "
    "config PROPOSALS, not on reads or on a $0 run.\n"
    "  The setup journey has a fixed order: Domain -> Judges -> Ground truth -> Knowledge base "
    "(optional) -> Run -> Review. A step is complete when:\n"
    "    - Domain: the agent has an ontology (an ontology_ref / a bound domain).\n"
    "    - Judges: the agent's judge roster is non-empty (author one by ASSIGNING an ontology "
    "lens to a role).\n"
    "    - Ground truth: at least one grounding/verification contract is attached "
    "(add_grounding_contract binds a flag to a tool-grounded floor).\n"
    "    - Knowledge base (OPTIONAL -- never block on it): a KB binding exists.\n"
    "    - Run: at least one run exists for this agent (run_eval, a $0 replay).\n"
    "    - Review: the human has seen a verdict/report.\n"
    "  At the START of a turn, READ the live state first (get_agent for the roster/ontology, "
    "review_runs for the run history) to find the FIRST incomplete REQUIRED step (skip the "
    "optional KB when choosing what to lead).\n"
    "  When the agent is a fresh/empty eval (no judges, no runs), OPEN with brief guidance and "
    "LEAD the next step -- e.g. 'Let's set up your first evaluation. What kind of AI output do "
    "you want to grade?' -- rather than waiting to be asked.\n"
    "  After the human acts on the one step you surfaced, acknowledge it on the NEXT turn and "
    "propose the next incomplete step (again, just the one).\n"
    "  PROPOSE, never auto-commit: surface the editor card for the human to Save (the Save IS "
    "the approval gate). Never claim a step is done that the live read does not show as done, "
    "and never claim a capability you do not have.\n"
    "  JUDGES -> GROUND TRUTH (EVAL-FLOW): once the judge roster is non-empty (Judges done) and "
    "NO verification contract is attached yet, the FIRST incomplete required step is Ground "
    "truth -- propose EXACTLY the grounding-contract step (and nothing else this turn): add ONE "
    "verification contract that binds a flag to a tool-grounded floor (add_grounding_contract), "
    "so the judge's verdict has an oracle to withstand. A saved contract ticks Ground truth.\n"
    "  GROUND TRUTH -> RUN (EVAL-FLOW): once a verification contract is attached (Ground truth "
    "done), guide the human to RUN their eval. A $0 replay (run_eval) is the natural payoff and "
    "is FREE for you to fire; a live/in-process PAID run is the human's own cost-confirmed action "
    "(you can never spend) -- surface the run, then let them authorize it. A run for this agent "
    "ticks Run; reviewing its verdict ticks Review.\n"
    "  If setup is already COMPLETE (every required step done), do NOT lead -- drop back to the "
    "reactive operator posture and simply answer what the human asks."
)


# The BYO-Claude cost figure the SDK reports is the subscription-EQUIVALENT estimate,
# not a per-loop charge (fold 4 — cost honesty, consistent with the honest-Δ discipline).
COST_LABEL = "subscription-equivalent estimate (BYO-Claude desktop — not a per-call charge)"

# SHEPHERD-1b (W2b, S-BS-150): the STEP-PROPOSING write tools — each surfaces a config editor
# card == one journey step (Domain/Judges/Ground-truth/etc.; one step == one write, confirmed at
# plan-review). The turn-scoped pacing hook (_pace_one_step) caps these to 1/turn so the shepherd
# proposes exactly one step and waits. NOT counted (free): reads (get_agent/get_judge/review_runs),
# the $0 replays (run_eval/run_eval_pack — a $0 run after an edit is the natural payoff, not a
# second proposal), and the look/teach directives (show_case/focus_artifact/kb_context/
# propose_live_run). This is a SET of tool NAMES; tools.py is byte-stable.
_STEP_PROPOSING_WRITES = frozenset(
    {
        "author_judge",
        "author_flag",
        "create_flag",
        "delete_flag",
        "assemble_agent",
        "delete_judge",
        "add_grounding_contract",
    }
)


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
    # TARGETED REDIRECT: a tool-discovery / loader call (ToolSearch and friends) should never happen
    # now that `tools=[]` un-offers the built-ins, but if one slips through, redirect rather than just
    # refuse — so the model's retry is instant and it calls the loaded tool directly instead of probing.
    _disc = name.lower().replace("-", "_")
    _is_discovery = (
        "toolsearch" in _disc
        or "tool_search" in _disc
        or _disc.endswith("_search")
        or "loadtool" in _disc
        or "load_tool" in _disc
        or _disc in {"tool_loader", "list_tools", "describe_tool"}
    )
    reason = (
        (
            f"{name}: all tools are already loaded — there is no tool-discovery or loader step here. "
            "Call the tool you need directly by its exact mcp__lithrim__* name (e.g. list_cases, "
            "show_case, run_eval, get_agent) with the documented arguments."
        )
        if _is_discovery
        else (
            f"{name or '<unknown>'} is not a Lithrim tool; this agent is bounded to "
            "mcp__lithrim__* (it can never fire a paid run or touch the host)."
        )
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _chat_provider_env() -> tuple[str | None, str | None]:
    """CONV-PROVIDER-1 — OPT-IN hot-switch of the conversational layer to the Anthropic API.

    **Credit-safe by default.** The PAID Anthropic API powers the chat agent ONLY when explicitly
    enabled via ``LITHRIM_CHAT_PROVIDER=anthropic`` (read from os.environ, else the gitignored
    repo-root ``.env`` / ``.live_env``, at TURN time — so flipping the flag needs no BFF restart).
    The DEFAULT — *even with ``ANTHROPIC_API_KEY`` sitting in ``.env``* — returns ``(None, None)`` →
    the $0 BYO-Claude path (the local ``claude`` CLI on desktop auth). A key on disk NEVER silently
    bills.

    When opted in: the key is handed ONLY to the conversation SDK subprocess
    (``ClaudeAgentOptions.env``, which the SDK MERGES over the inherited env — subprocess_cli.py:431),
    NEVER written to the BFF ``os.environ`` — so the BYO-Claude JUDGE plane stays on desktop auth.
    ``LITHRIM_CHAT_MODEL`` pins the model (alias "sonnet"/"opus" or a full id; default "sonnet").
    Returns (api_key, model). NEVER logs the key.

    NOTE: Anthropic only. The Agent SDK drives Claude; an Azure GPT/Mistral/Llama conversational
    agent would need a different (OpenAI-tools) loop engine, not this seam.
    """
    import os
    from pathlib import Path

    def _read(name: str) -> str | None:
        v = os.environ.get(name)
        if v:
            return v
        root = Path(__file__).resolve().parents[3]  # apps/bff/agent/loop.py → repo root
        for fname in (".env", ".live_env"):
            f = root / fname
            if not f.exists():
                continue
            for raw in f.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, val = line.split("=", 1)
                if k.strip() == name:
                    return val.strip().strip("'\"")
        return None

    if (_read("LITHRIM_CHAT_PROVIDER") or "").strip().lower() not in ("anthropic", "anthropic-api", "api"):
        return None, None  # credit-safe default: $0 BYO-Claude (desktop auth), key on disk ignored
    return (_read("ANTHROPIC_API_KEY") or None), (_read("LITHRIM_CHAT_MODEL") or "sonnet")


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

    # SHEPHERD-1b (W2b, S-BS-150): one-step-and-wait, mechanically enforced. _build_options is
    # rebuilt PER TURN (_real_source: opts = _build_options(ctx)), so this turn-local counter
    # resets by construction every turn. The hook ADDS a second PreToolUse matcher alongside the
    # A-SAFE _deny_non_lithrim (which stays byte-unchanged and FIRST -- the SDK runs all matchers,
    # and a PreToolUse deny prevents the audited write, so no second card is fabricated). It is
    # fail-OPEN for ITSELF (any error -> {} == allow): safe because it can only ever ADD a deny,
    # never remove one -- _deny_non_lithrim still independently governs the security bound.
    pacing = {"writes": 0}

    async def _pace_one_step(input_data, tool_use_id, context):
        try:
            name = (input_data or {}).get("tool_name") or ""
            if name.startswith("mcp__lithrim__"):
                name = name[len("mcp__lithrim__") :]
            if name not in _STEP_PROPOSING_WRITES:
                return {}  # reads, $0 runs, look/teach directives are free -- never counted
            pacing["writes"] += 1
            if pacing["writes"] <= 1:
                return {}  # the FIRST step this turn -- allow it
            # a 2nd+ config proposal this turn: pace it (graceful, not an error to the human)
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "One setup step per turn: you've already proposed a step this turn. "
                        "Surface that one card, ask the human to review/save it and tell you to "
                        "continue, then set up the next step on the following turn."
                    ),
                }
            }
        except Exception:
            return {}  # fail-open for the pacing hook only; the deny hook is the real bound

    api_key, chat_model = _chat_provider_env()
    return ClaudeAgentOptions(
        model=chat_model,  # CONV-PROVIDER-1: a pinned Claude via the Anthropic API when set; None → CLI default
        env=({"ANTHROPIC_API_KEY": api_key} if api_key else {}),  # SCOPED to this subprocess (judges unaffected)
        mcp_servers={"lithrim": server},
        # A-SAFE ROOT CONTROL (S-BS-90 follow-up): `tools=[]` disables ALL built-ins (Bash/Read/
        # ToolSearch/...) so they are NEVER OFFERED to the model — unlike `allowed_tools`, which under
        # bypassPermissions only governs prompting (claude-agent-sdk types.py: `tools=[]` → `--tools ""`,
        # built-ins off; the MCP server rides the SEPARATE `--mcp-config` path, so the 18 mcp__lithrim__*
        # tools are untouched). This stops the model reaching for ToolSearch out of Claude-Code habit at
        # the SOURCE (the live "ToolSearch misfire") and demotes _deny_non_lithrim to pure
        # defense-in-depth (the probe-1 built-in is now un-offered, not merely refused). `disallowed_tools`
        # names ToolSearch explicitly as a belt-and-suspenders backstop (removed from the model's context).
        tools=[],
        disallowed_tools=["ToolSearch"],
        allowed_tools=allowed,  # defense-in-depth; the deny hook below is the real bound
        permission_mode="bypassPermissions",
        hooks={
            "PreToolUse": [HookMatcher(matcher=None, hooks=[_deny_non_lithrim, _pace_one_step])]
        },
        setting_sources=[],  # SDK isolation: no inherited ~/.claude settings / MCP servers
        skills=[],  # suppress skill listing (the hook denies Read/Bash regardless)
        system_prompt=_system_prompt(ctx.default_agent, ctx.active_case),  # CHATBIND-1 + NARR-CHAT-LOOP: name the active agent + case
        max_turns=12,  # the 5-step Domain->Judge->Flag->Run->Review journey (was 8 for the spine)
        # CONV-UX-1 (W2): fine-grained streaming. The SDK (>=0.2.90) interleaves StreamEvent
        # objects whose `event` dict carries the Anthropic content_block_delta/text_delta chunks,
        # so the shell can accrete text token-by-token instead of whole-block pops. The HONEST
        # spike verdict: feasible on this path (see docs/research/PROOF_*). run_chat de-dups the
        # trailing full AssistantMessage so a streamed block is not emitted twice.
        include_partial_messages=True,
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

    # CONV-UX-1 (W1/W2): StreamEvent + ThinkingBlock are present from SDK 0.2.90; under an older
    # SDK (or the test stub, which yields only Assistant/Result) they are simply never matched —
    # the whole-block path still runs, so the loop degrades cleanly to block-granular streaming.
    try:
        from claude_agent_sdk import StreamEvent, ThinkingBlock
    except ImportError:  # pragma: no cover — defensive for an older SDK
        StreamEvent = ThinkingBlock = ()  # type: ignore[assignment]

    src = source or _real_source
    cost_usd: float | None = None
    # CONV-UX-1 (W2): when partials stream a content block, the SDK still yields the assembled
    # AssistantMessage afterward carrying the SAME full text/thinking — track what already
    # streamed so the trailing full block is NOT emitted twice (de-dup, not double-render).
    streamed_text = False
    streamed_thinking = False
    try:
        async for msg in src(message, ctx, history):
            if StreamEvent and isinstance(msg, StreamEvent):
                # The Anthropic raw streaming event dict: a content_block_delta carries either a
                # text_delta (assistant prose) or a thinking_delta (reasoning) — emit token-granular.
                delta = (msg.event or {}).get("delta") or {}
                dtype = delta.get("type")
                if dtype == "text_delta" and delta.get("text"):
                    streamed_text = True
                    yield {"event": "assistant_delta", "text": delta["text"]}
                elif dtype == "thinking_delta" and delta.get("thinking"):
                    streamed_thinking = True
                    yield {"event": "thinking", "text": delta["thinking"]}
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if ThinkingBlock and isinstance(block, ThinkingBlock):
                        if not streamed_thinking and (block.thinking or "").strip():
                            yield {"event": "thinking", "text": block.thinking}
                    elif isinstance(block, TextBlock):
                        if not streamed_text and block.text.strip():
                            yield {"event": "assistant_delta", "text": block.text}
                    # Only stream the activity step for an in-process lithrim tool. A non-
                    # mcp__lithrim__ block (e.g. a ToolSearch the model tried out of habit) is
                    # GUARANTEED to be denied by _deny_non_lithrim, so it never yields a tool_result
                    # — emitting it would render a doomed "ToolSearch…" chip in the chat. Drop it on
                    # the wire (the security policy stays in one place — the deny hook).
                    elif isinstance(block, ToolUseBlock) and block.name.startswith("mcp__lithrim__"):
                        yield {"event": "tool_call", "name": block.name, "input": block.input}
                # The assembled message closes a streamed turn; reset for the next AssistantMessage
                # (a multi-turn loop streams, assembles, then streams the next turn's partials).
                streamed_text = False
                streamed_thinking = False
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
