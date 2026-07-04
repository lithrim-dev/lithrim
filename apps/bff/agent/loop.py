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
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

from .adapter import propose_live_run_part, propose_run_all_part
from .tools import _TOOL_SPECS, ToolContext, build_sdk_tools

# CONV-RUNTIME-1: the verbatim one-step-per-turn pacing message. Hoisted to module scope so BOTH
# pacing enforcers — the SDK PreToolUse ``_pace_one_step`` hook AND the litellm-loop turn-local
# counter — feed back the IDENTICAL text (one-step parity across the two conversation engines).
_ONE_STEP_PACING_MESSAGE = (
    "One setup step per turn: you've already proposed a step this turn. "
    "Surface that one card, ask the human to review/save it and tell you to "
    "continue, then set up the next step on the following turn."
)

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
    "  - author_flag: EDIT an existing flag in the ontology (an audited config write): its "
    "tier/gradeable AND its criterion text (definition, when_to_use, when_NOT_to_use). "
    "when_to_use is the lens line the owning judge's prompt renders -- rewording it is the "
    "calibration move ('the judge over-fires on X' -> tighten when_to_use / add the exclusion "
    "to when_NOT_to_use, then re-run and compare). Omitted fields stay untouched; you cannot "
    "invent owners.\n"
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
    "the human DESCRIBES a criterion in PROSE, FIRST call kb_context to CITE the org policy (skip the "
    "citation if it reports no knowledge base is connected), THEN call "
    "author_contract(flag_code=…, contract_type=…) and the card opens PRE-FILLED with the CORRECT "
    "deterministic params for that type. PICK THE DIRECTION from what the criterion DOES: \n"
    "    • value_presence — a FLOOR that BLOCKS when a value the patient/source STATED is MISSING from "
    "the artifact (a completeness/omission/dissent-erasure criterion, e.g. 'the patient refused the "
    "vaccine but the SOAP note erased it', 'a stated symptom is dropped from the summary'). This is the "
    "direction that can FLIP an APPROVE to a BLOCK — use it whenever the harm is 'something said was "
    "left out'. Pass source_hint=<the path the value should appear in, e.g. transcript>. \n"
    "    • presence_check — SUPPRESSES a noisy false-positive finding (e.g. 'a medication named in the "
    "note the patient isn't actually on'); it removes findings, it does NOT block. Pass source_hint="
    "<the chart path to check the flagged term against, e.g. patient_profile.active_medications>. \n"
    "  Omitting contract_type defaults to presence_check. Do NOT hand-compose the params dict yourself "
    "(the system fills the correct keys for the chosen type — you'd get them wrong); pass "
    "suggested_params only if you already know the exact executor keys. ALWAYS say the pre-filled params "
    "are a DRAFT they edit + Save — you only PROPOSE; the human's Save is the only write and the "
    "suggestion never decides a verdict. (When YOU already know the contract_type + params, use "
    "add_grounding_contract — the agent-composes twin — instead.)\n"
    "  - author_criterion: SURFACE the criterion-authoring widget INLINE so the HUMAN mints a NEW "
    "GRADEABLE criterion -- a scoreable taxonomy code the council can RAISE -- by filling a card (the "
    "mirror of author_contract, for a gradeable code rather than a grounding contract). Use it when "
    "the human wants to CREATE / define a new gradeable criterion or scoreable flag: call "
    "author_criterion(code=…, tier=…, owner_role=…) to drop the card inline, seeded. The human reviews "
    "+ Saves; their Save is the SOLE audited write (POST /v1/criterion splices the active tier:core "
    "pack's taxonomy snapshot + ontology, gating owner ∈ production_judges + code shape + dup). You do "
    "NOT mint the code yourself; $0, never a paid run.\n"
    "  - create_judge: SURFACE the create-judge widget INLINE so the HUMAN mints a NEW judge ROLE -- a "
    "NEW voice on the council -- by filling a card (the mirror of author_criterion). Use it when the "
    "human wants to CREATE / add a NEW judge or a new council voice / reviewer role: call "
    "create_judge(role=…) to drop the card inline, seeded with the role id. The human fills the lens, "
    "owned codes, model + role prompt and Saves; their 'Create judge' Save is the SOLE audited write "
    "(POST /v1/judges mints the new role into the snapshot, owner↔emit + snapshot gated). You do NOT "
    "mint the judge yourself; $0, never a paid run. CONTRAST with author_judge: author_judge ASSIGNS a "
    "lens to an EXISTING role; create_judge CREATES a new role -- use create_judge for a brand-new "
    "judge, author_judge to re-lens one that already exists.\n"
    "  - kb_context: RETRIEVE + SHOW the connected knowledge base's relevant section(s) for a topic "
    "or finding ($0, read-only). It is a CONTEXT AID -- it grounds the discussion in the source policy "
    "but NEVER changes a verdict or clears a finding. Use it to show 'what the policy actually says', "
    "not to decide the outcome. When the human asks what the policy/regulation says, or to 'show the "
    "source', you MUST call kb_context and then QUOTE the returned section text VERBATIM in your reply "
    "-- do NOT answer from your own knowledge, and do NOT cite a section number you did not get back "
    "from the tool. The tool's returned text IS the source to display inline; do NOT call "
    "focus_artifact('corpus') for it (the corpus tab is the correction flywheel -- a different thing, "
    "not the knowledge base). Leave the namespace unset (the deployment's configured default applies); "
    "never pass an index name. If the tool reports no knowledge base is connected, SAY SO and answer "
    "from the conversation -- do NOT retry it.\n"
    "  - run_eval: GRADE the case FRESH -- THE way to run / grade / evaluate / run eval a case. It "
    "surfaces the cost-confirm modal so the human authorizes the fresh paid (live) grade; you only "
    "PROPOSE, you never spend. It does NOT replay a stored run (that stale-verdict replay was a bug). "
    "Pass case_id (from list_cases) for a SPECIFIC case; omit it for the case they're exploring. "
    "(propose_live_run opens the SAME cost-confirm -- both run_eval and propose_live_run are the "
    "fresh-grade path, so 'run eval' and 'run it' both land on a fresh cost-confirmed grade.) "
    "EXCEPTION (ZERO-DOLLAR-ROUTE): an explicit '$0' / 'replay' / 'stored result' / 'last result' / "
    "'for free / free of charge / at no cost' / 'don't spend / without spending / without paying' "
    "ask is NOT this tool -- serve it with review_runs (the $0 read of the stored result); never "
    "answer a $0 ask with the cost-confirm modal.\n"
    "  - run_eval_pack: run a $0 REPLAY eval-pack BATCH over one or more agents and show "
    "the run history -- a live batch (one paid call per agent) is the human's.\n"
    "  - propose_run_all: GRADE ALL ingested cases at once -- THE way to 'run all / grade all / run "
    "the whole suite / score every case'. Surfaces the cost-confirm for the whole cohort; the human's "
    "confirm grades them all and renders the consolidated scorecard inline (per-case vs gold + "
    "precision/recall). You only PROPOSE; the human's confirm spends. You can NEVER fire it.\n"
    "  - review_runs: review the run history, the latest run's STORED verdict/provenance, and the "
    "audit trail of everything you authored -- $0. Pass case_id when the human NAMES a case, so "
    "the history + latest verdict scope to THAT case. THE way to serve an explicit '$0 replay' / "
    "'show the stored result' / 'last result' / 'for free / free of charge / at no cost' / "
    "'don't spend / without spending / without paying' ask: show the stored result at $0 and NEVER "
    "surface the cost-confirm modal for it (a $0 ask must never escalate to a paid proposal unless "
    "the human then asks for a live/fresh grade). If the stored read refuses (e.g. the config "
    "changed since the last grade), surface its message VERBATIM and let the human decide -- never "
    "swallow it, never counter-propose a paid run unprompted.\n"
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
    "  - propose_live_run: the way to GRADE A CASE FRESH. This is your DEFAULT response when the "
    "human says 'run / grade / evaluate / run eval [this case|case X]' -- surface the cost-confirm "
    "modal so THEY authorize the fresh paid grade. A fresh grade makes real (paid) model calls, so "
    "the human's confirm runs it; you only PROPOSE, you never spend. (EXCEPTION: an explicit "
    "'$0' / 'replay' / 'stored/last result' / 'for free / free of charge / at no cost' / 'don't "
    "spend / without spending / without paying' ask is served by review_runs -- the $0 read -- "
    "NEVER by this modal; run_eval opens this SAME paid modal, so never use run_eval for a $0 ask "
    "either.)\n"
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
    "never something to round up to a pass.\n"
    "  - GROUND every claim about WHAT is wrong in the actual case. When you explain what's wrong, "
    "QUOTE the transcript / scribe note verbatim (it is injected as THE CASE ON SCREEN; else call "
    "show_case first). NEVER invent a hypothetical example (\"if the transcript says X…\") -- that is a "
    "story-shaped diagnosis, the exact thing this product exists to refuse. If you cannot quote evidence "
    "for a listed finding, say it is unsupported rather than inventing a scenario. When an ANSWER KEY "
    "(gold) is provided, a reviewer finding NOT in it is a likely OVER-FIRE -- name it as such, do not "
    "present it as a confirmed problem."
)


def _latest_run_context(ctx: ToolContext, *, _load_case=None) -> str:
    """EXPLAIN-RESULT-PARITY-1: the deterministic "latest run" context block injected into the
    system prompt BOTH chat engines build, so every provider can explain "this result" without a
    tool call. The verdict renders as an inline gen-UI card (not text) and the replayed history is
    text-only, so the result is otherwise NEVER in the model's text context — Claude proactively
    re-fetches it via review_runs; a temperature-0 / tool_choice-auto Azure model does not. This
    injects it for everyone.

    A-SAFE: a ``$0`` read + context injection ONLY. It calls ONLY ``ctx.review_runs`` (the existing
    $0 op) and NEVER any paid/run/grade op — the agent still cannot spend. PRESENT-ONLY: a fresh
    agent with NO runs ⇒ ``""`` ⇒ the prompt is byte-identical to today (the regression guard).
    DEFENSIVE / never-raises: a read failure returns ``""`` (it must never break chat). HONEST-Δ:
    it reports the REAL stored verdict/findings verbatim — never a cleaner result than the run gave.
    """
    # GROUNDED-EXPLAIN-1: the case-on-screen's artifact + gold is about the CASE, not the run — so
    # it is built up-front and returned even when there is NO run yet ("what's wrong with this
    # case?" must ground in the artifact regardless). Prefer the request-context loader the BFF
    # binds (``ctx.load_case_full``); ``_load_case`` (tests) wins over both. With no active case it
    # is "" → the no-run / no-case path stays byte-identical (the regression guard).
    loader = _load_case or getattr(ctx, "load_case_full", None)
    case_block = _case_artifact_block(getattr(ctx, "active_case", None), _load_case=loader)
    try:
        res = ctx.review_runs(limit=1)
    except Exception:
        return case_block  # a run-read failure NEVER breaks chat — still ground in the case
    runs = (res or {}).get("runs") or []
    if not runs:
        return case_block  # no run yet ⇒ no run block, but STILL ground in the case on screen
    audit = (res or {}).get("latest_audit") or {}
    run_id = (res or {}).get("latest_run_id") or runs[0].get("run_id") or ""
    verdict = audit.get("verdict") or runs[0].get("verdict") or "—"

    findings = audit.get("findings") or []
    finding_lines: list[str] = []
    for f in findings[:5]:
        if isinstance(f, dict):
            code = f.get("code") or f.get("flag_code") or f.get("flag") or "finding"
            reason = f.get("reason") or f.get("description") or f.get("detail") or ""
        else:
            code, reason = "finding", str(f)
        reason = (reason or "").strip().replace("\n", " ")
        if len(reason) > 140:
            reason = reason[:137] + "…"
        finding_lines.append(f"{code} — {reason}" if reason else str(code))
    findings_rendered = "; ".join(finding_lines) if finding_lines else "none — approved / nothing stands"

    judges = audit.get("judges") or []
    vote_lines: list[str] = []
    for j in judges:
        if not isinstance(j, dict):
            continue
        role = j.get("judge_role") or j.get("role") or "judge"
        vote = j.get("vote") or "—"
        conf = j.get("confidence")
        vote_lines.append(f"{role}={vote}({conf})" if conf is not None else f"{role}={vote}")
    votes_rendered = "; ".join(vote_lines) if vote_lines else "—"

    base = (
        "LATEST RUN CONTEXT (the result currently on screen — this IS \"this result\"/\"the "
        "verdict\"/\"this run\"):\n"
        f"  Run {run_id[:8] or '—'} on `{ctx.default_agent}`: verdict={verdict}.\n"
        f"  Findings still standing: {findings_rendered}\n"
        f"  Judge votes: {votes_rendered}\n"
        "When the human asks you to explain / interpret / break down this result, verdict, or run, "
        "ANSWER FROM THIS (call review_runs for full provenance). NEVER reply that you don't see a "
        "verdict or findings — you have them here."
    )
    return base + case_block


def _default_load_case(case_id: str):
    from lithrim_bench.picklist import load_case

    return load_case(case_id)


def _case_artifact_block(case_id: str | None, *, _load_case=None) -> str:
    """GROUNDED-EXPLAIN-1: when a case is on screen, inject its transcript + note + gold answer key
    + grounding rules, so every provider explains WHAT is wrong FROM the artifact (quoting it),
    names non-gold findings as likely over-fires, and never invents hypothetical examples. The
    bug this fixes (live on clinverdict_case06): the model had only finding CODES, so it free-
    narrated "if the transcript says…" stories and amplified the over-fire as a real problem.

    DEFENSIVE / never-raises (a case-load failure must never break chat → ``""``). Each artifact
    is length-capped (clinical cases are short; keep the injected prompt bounded)."""
    if not case_id:
        return ""
    loader = _load_case or _default_load_case
    try:
        case = loader(case_id)
    except Exception:
        return ""  # a case-load failure (e.g. the corpus DB is down) NEVER breaks chat
    if not isinstance(case, dict):
        return ""
    transcript = str(case.get("transcript") or case.get("context") or "").strip()
    arts = case.get("artifacts") or []
    note = str(arts[0].get("content") or "").strip() if arts and isinstance(arts[0], dict) else ""
    gold = [str(g) for g in (case.get("expected_safety_flags") or []) if g]
    if not (transcript or note):
        return ""

    def _cap(s: str) -> str:
        return (s[:900] + "…") if len(s) > 900 else s

    lines = [
        f"\n\nTHE CASE ON SCREEN (`{case_id}`) — when asked what is WRONG with this case, GROUND "
        "every claim in THIS evidence and QUOTE the transcript / note verbatim. NEVER invent a "
        'hypothetical ("if the transcript says…") example — read the actual case below.'
    ]
    if transcript:
        lines.append(f"  TRANSCRIPT:\n{_cap(transcript)}")
    if note:
        lines.append(f"  SCRIBE NOTE / ARTIFACT:\n{_cap(note)}")
    if gold:
        lines.append(
            "  ANSWER KEY (the gold safety flags for this LABELED case): "
            + ", ".join(gold)
            + ". Reconcile the reviewers' findings against it: a finding IN the key is a CONFIRMED "
            "problem (explain it from the artifact); a reviewer finding NOT in the key is a likely "
            "OVER-FIRE — say so ('the reviewers also raised X, but it is not in the answer key — "
            "likely a false positive') and do NOT present it as a confirmed problem; a key flag the "
            "reviewers did NOT raise is a MISS — call it out."
        )
    else:
        lines.append(
            "  NO ANSWER KEY (this case is unlabeled): ground every claim in the artifact above; do "
            "NOT guess which findings are false positives — without ground truth you cannot. Report "
            "what the reviewers found and exactly what the artifact does or does not support."
        )
    return "\n".join(lines)


def _system_prompt(
    active_agent: str, active_case: str | None = None, latest_run: str | None = None
) -> str:
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
    a spend -- the A-SAFE surface is unchanged.

    EXPLAIN-RESULT-PARITY-1: ``latest_run`` is the optional ``_latest_run_context(ctx)`` block. When
    it is a non-empty string it is appended as a TRAILING stanza (after ``_SHEPHERD_STANZA``), so the
    verdict + findings of the run on screen are IN context and every provider can explain "this
    result" without a tool call. ``None``/``""`` ⇒ the return is BYTE-IDENTICAL to today (the no-run
    path + the regression guard). It is a context read, never a spend — the A-SAFE surface is
    unchanged."""
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
        + "\n\n"
        + _REGISTER_STANZA
        # EXPLAIN-RESULT-PARITY-1: append the latest-run context ONLY when a run exists. A no-run
        # turn passes None/"" → this concatenation is byte-identical to the pre-PARITY return.
        + (f"\n\n{latest_run}" if latest_run else "")
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
    "    - Run: at least one run exists for this agent (a fresh cost-confirmed grade — run_eval or "
    "propose_live_run surfaces the cost-confirm, the human's confirm runs it).\n"
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
    "done), guide the human to RUN their eval. To GRADE the case, propose a FRESH grade -- run_eval "
    "OR propose_live_run both surface the cost-confirm, and the human's confirm runs the fresh paid "
    "grade; you can never spend. 'run / grade / evaluate / run eval [this case|case X]' ALWAYS means "
    "this fresh cost-confirmed grade -- never a stale stored replay. EXCEPTION (ZERO-DOLLAR-ROUTE, "
    "credit-safety): when the human EXPLICITLY says '$0' / 'replay' / 'stored result' / 'last "
    "result' / 'for free / free of charge / at no cost' / 'don't spend / without spending / "
    "without paying', that is a review_runs ask -- show the stored result at $0 and do NOT surface "
    "the cost-confirm for it (a $0 ask never escalates to a paid proposal unless they then ask for "
    "a live/fresh grade). A run for this agent ticks Run; reviewing its verdict ticks Review.\n"
    "  If setup is already COMPLETE (every required step done), do NOT lead -- drop back to the "
    "reactive operator posture and simply answer what the human asks."
)


# UX-COPY-REGISTER-1: the "speak to a person" register rule. This governs ONLY what the model
# SAYS to the human — it never changes how the model CALLS the tools (it still invokes them by
# their exact documented names internally). It is appended LAST among the standing stanzas so it
# qualifies everything above it: the tool descriptions, the honesty contract, and the shepherd
# guidance all describe behavior in insider terms; this stanza tells the model to TRANSLATE those
# terms before they reach the user. Additive — no existing instruction is rewritten.
_REGISTER_STANZA = (
    "HOW TO SPEAK TO THE USER (a register rule -- governs ONLY what you SAY, never how you CALL "
    "tools): you are talking to a person setting up evaluations, not an engineer reading the "
    "internals. Keep your replies in plain product language and NEVER let the machinery leak "
    "through.\n"
    "  - NEVER print a tool/function name (focus_artifact, run_eval, propose_live_run, author_judge, "
    "add_grounding_contract, etc.), an HTTP path or verb (POST /v1/...), a port number (:8002, "
    ":3031), an internal property/field name (role_key_questions, kb_bindings, expected_safety_flags), "
    "or a run-id hex. Describe the ACTION instead: say \"open the report\", \"run the evaluation\", or "
    "\"grade this case\" -- never the function you call to do it.\n"
    "  - TRANSLATE the insider terms in EVERY reply: the council / the roster -> \"the reviewers\"; a "
    "judge -> \"a reviewer\" (e.g. the faithfulness_judge -> \"the Faithfulness reviewer\"); a "
    "verdict -> \"the result\"; BLOCK / reject -> \"flagged\"; PASS / approve -> \"passed\"; WARN -> "
    "\"needs a look\"; a lens -> \"what a reviewer checks for\"; an ontology -> \"your checks\" / "
    "\"your checklist\"; a verification contract / floor / oracle / grounding contract -> \"a "
    "fact-check\"; the corpus -> \"your saved cases\".\n"
    "  - Refer to a run as \"your latest run\" or \"this run\", NEVER by its hex id. When you name a "
    "raw flag/issue code, say it in plain words (MEDICATION_NOT_IN_TRANSCRIPT -> \"medication not in "
    "the transcript\").\n"
    "  - This is a translation layer only: it does NOT relax the HONESTY contract above. State the "
    "real result and the findings that still stand, just in human words -- a flagged result is still "
    "\"flagged\", never softened to \"passed\"."
)


# The BYO-Claude cost figure the SDK reports is the subscription-EQUIVALENT estimate,
# not a per-loop charge (fold 4 — cost honesty, consistent with the honest-Δ discipline).
COST_LABEL = "subscription-equivalent estimate (BYO-Claude desktop — not a per-call charge)"

# SHEPHERD-1b (W2b, S-BS-150): the STEP-PROPOSING write tools — each surfaces a config editor
# card == one journey step (Domain/Judges/Ground-truth/etc.; one step == one write, confirmed at
# plan-review). The turn-scoped pacing hook (_pace_one_step) caps these to 1/turn so the shepherd
# proposes exactly one step and waits. NOT counted (free): reads (get_agent/get_judge/review_runs),
# run_eval (RUN-EVAL-FRESH-1: now a cost-confirm DIRECTIVE — a fresh-grade proposal, not a spend)
# and the run_eval_pack $0 replay batch (the natural payoff after an edit, not a second step), and
# the look/teach directives (show_case/focus_artifact/kb_context/propose_live_run). This is a SET
# of tool NAMES; tools.py is byte-stable.
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


def _provider_config_root():
    """The repo-root directory the chat-provider env-file fallback reads the DEV-AUTHOR files
    (``.env`` / ``.live_env``) from. Factored out so tests can point it at a tmp dir (no real .env
    leaks in). NOTE: ``.provider_env`` is NOT read from here — it is relocatable (CONFIG-PERSIST-1);
    see ``_relocatable_provider_env_dir``."""
    from pathlib import Path

    return Path(__file__).resolve().parents[3]  # apps/bff/agent/loop.py → repo root


def _relocatable_provider_env_dir():
    """CONFIG-PERSIST-1: the dir the in-app ``.provider_env`` (provider keys + ``LITHRIM_CHAT_*``)
    lives in — ``LITHRIM_PROVIDER_ENV_DIR`` if set (docker-compose defaults it to ``/app/out`` = the
    named volume, so a restarted/``down``-``up``ed BFF still finds the persisted chat binding), else
    the repo root (dev back-compat). loop.py cannot import app.py — it reads the env var directly,
    mirroring ``app._provider_env_dir``."""
    import os
    from pathlib import Path

    override = os.environ.get("LITHRIM_PROVIDER_ENV_DIR")
    return Path(override) if override else _provider_config_root()


def _read_chat_env(name: str) -> str | None:
    """Read ``name`` from os.environ, else the gitignored ``.env`` / ``.live_env`` (dev-author files,
    repo-root) / ``.provider_env`` (the relocatable in-app sidecar, CONFIG-PERSIST-1), at TURN time —
    so flipping a chat-provider var needs no BFF restart. The chat api_key
    (``LITHRIM_CHAT_API_KEY``) is written to ``.provider_env`` by the provider endpoint; we read it
    here. NEVER logs the value."""
    import os

    v = os.environ.get(name)
    if v:
        return v
    root = _provider_config_root()
    candidates = [root / ".env", root / ".live_env", _relocatable_provider_env_dir() / ".provider_env"]
    for f in candidates:
        if not f.exists() or not f.is_file():
            continue
        for raw in f.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, val = line.split("=", 1)
            if k.strip() == name:
                return val.strip().strip("'\"")
    return None


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

    NOTE: Anthropic only — this seam binds the Agent SDK to Claude. A non-anthropic conversational
    agent (Azure GPT / Mistral / Llama / Gemini / ...) is driven by the litellm OpenAI-tools loop
    (``_litellm_loop``), selected via ``_chat_provider_config`` (CONV-RUNTIME-1).
    """
    if (_read_chat_env("LITHRIM_CHAT_PROVIDER") or "").strip().lower() not in (
        "anthropic", "anthropic-api", "api",
    ):
        return None, None  # credit-safe default: $0 BYO-Claude (desktop auth), key on disk ignored
    return (_read_chat_env("ANTHROPIC_API_KEY") or None), (_read_chat_env("LITHRIM_CHAT_MODEL") or "sonnet")


def _chat_provider_config() -> dict | None:
    """CONV-RUNTIME-1 — which conversation ENGINE drives the chat, selected by the configured
    chat provider. Read at TURN time from os.environ else the repo-root ``.env`` / ``.live_env`` /
    ``.provider_env`` (no BFF restart needed).

    **Credit-safe default.** No ``LITHRIM_CHAT_PROVIDER`` set, OR set to ``anthropic`` →
    returns ``None`` → the EXISTING Anthropic Agent-SDK / BYO-Claude path is taken UNCHANGED (a key
    on disk NEVER silently picks a billing engine; ``_chat_provider_env`` independently governs
    whether the SDK path uses the paid Anthropic API or desktop auth).

    For any OTHER provider (openai / azure / gemini / bedrock / openai_compatible) → returns
    ``{provider, model, api_key, api_base}`` read from ``LITHRIM_CHAT_{PROVIDER,MODEL,API_KEY,API_BASE}``
    → the litellm OpenAI-tools loop drives the chat. NEVER logs the key."""
    provider = (_read_chat_env("LITHRIM_CHAT_PROVIDER") or "").strip().lower()
    if provider in ("", "anthropic", "anthropic-api", "api"):
        return None  # credit-safe default → the SDK / BYO-Claude path, unchanged
    return {
        "provider": provider,
        "model": _read_chat_env("LITHRIM_CHAT_MODEL"),
        "api_key": _read_chat_env("LITHRIM_CHAT_API_KEY"),
        "api_base": _read_chat_env("LITHRIM_CHAT_API_BASE"),
        # CONNECT-AI-AZURE-1: an azure chat needs an api_version (litellm wall); empty for non-azure.
        "api_version": _read_chat_env("LITHRIM_CHAT_API_VERSION"),
    }


# CONV-RUNTIME-1: map a plain-dict tool schema's python type → its JSON-schema type string.
_JSON_SCHEMA_TYPES = {str: "string", int: "integer", bool: "boolean", list: "array", dict: "object"}


def _openai_tool_schemas() -> list[dict]:
    """CONV-RUNTIME-1 — build the OpenAI / litellm function-tool list from ``_TOOL_SPECS``. Each
    ``(handler, name, desc, {param: pytype})`` → ``{"type":"function","function":{name, description,
    parameters: <JSON-schema object>}}``. ALL params are OPTIONAL (no ``required``): the handlers
    default every omitted arg, mirroring the SDK plain-dict schema semantics. Covers all 22 tools."""
    schemas: list[dict] = []
    for _handler, name, desc, schema in _TOOL_SPECS:
        properties = {
            param: {"type": _JSON_SCHEMA_TYPES.get(pytype, "string")}
            for param, pytype in schema.items()
        }
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": {"type": "object", "properties": properties, "required": []},
                },
            }
        )
    return schemas


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
                    "permissionDecisionReason": _ONE_STEP_PACING_MESSAGE,
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
        # CHATBIND-1 + NARR-CHAT-LOOP: name the active agent + case. EXPLAIN-RESULT-PARITY-1:
        # inject the latest-run context ($0 review_runs read) so Claude explains "this result"
        # from context too — present-only (no-run ⇒ byte-identical to the pre-PARITY prompt).
        system_prompt=_system_prompt(
            ctx.default_agent, ctx.active_case, latest_run=_latest_run_context(ctx)
        ),
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


async def _run_sdk_chat(
    message: str,
    ctx: ToolContext,
    *,
    history: list[dict] | None = None,
    source: Callable[[str, ToolContext, list[dict] | None], AsyncIterator[Any]] | None = None,
) -> AsyncIterator[dict]:
    """The Anthropic Agent-SDK / BYO-Claude consumer: normalize a ClaudeSDKClient message stream
    into SSE event dicts. ``history`` is the client-replayed prior turns (text-only; default
    ``None`` -> no preamble -> back-compatible). ``source`` defaults to the real SDK; tests pass a
    stub async generator factory ``(message, ctx, history) -> AsyncIterator[msg]``.

    CONV-RUNTIME-1: this is the regression-guard path — BYTE-IDENTICAL to the pre-CONV-RUNTIME-1
    ``run_chat`` for the anthropic/unset case (``run_chat`` now dispatches here vs ``_litellm_loop``)."""
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


# CONV-RUNTIME-1 — the bare tool names the whitelist admits (the A-SAFE floor of the litellm
# engine: ONLY a name in this set is ever dispatched; a Bash / unknown call is fed back as an error
# and NEVER executed). Resolves a bare OR ``mcp__lithrim__``-prefixed name to its bare form.
_LITHRIM_TOOL_NAMES = frozenset(name for _h, name, *_ in _TOOL_SPECS)
_LITHRIM_HANDLERS = {name: handler for handler, name, *_ in _TOOL_SPECS}
_LITELLM_MAX_TURNS = 12  # parity with _build_options.max_turns (the Domain→Judge→Flag→Run→Review journey)

# CONV-RUNTIME-1: the honest BYO-key chat cost label (the user's own provider key pays for the chat).
_LITELLM_COST_LABEL = "your-BYO-key conversation cost"

# CONV-RUNTIME-1: the litellm provider/model prefix (mirrors judges_dspy._LITELLM_PREFIX — inlined so
# the agent package stays import-isolated: no dspy/openai pulled at import). ``openai_compatible``
# rides the ``openai`` prefix + an ``api_base``; an unknown provider falls back to its own id.
_LITELLM_PREFIX = {
    "openai": "openai",
    "azure": "azure",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "bedrock": "bedrock",
    "openai_compatible": "openai",
}


def _litellm_prefix(provider: str) -> str:
    p = (provider or "").strip().lower()
    return _LITELLM_PREFIX.get(p, p)


def _resolve_lithrim_tool(name: str) -> str | None:
    """Resolve a tool-call name to a whitelisted bare lithrim tool name, else None (NOT a Lithrim
    tool → never dispatched). Strips the ``mcp__lithrim__`` prefix the SDK naming would carry."""
    bare = name[len("mcp__lithrim__") :] if name.startswith("mcp__lithrim__") else name
    return bare if bare in _LITHRIM_TOOL_NAMES else None


# CONFIRM-MODAL-FALLBACK-1: a question/explain opener that means "tell me ABOUT the run", never
# "run it" — so the deterministic cost-confirm fallback stays off when the human is asking, not
# requesting. Conservative on purpose (the fallback only OPENS a modal the human confirms, but a
# false-open is still noise).
_RUN_REQUEST_QUESTION_OPENERS = (
    "how", "what", "why", "when", "where", "who", "which", "can", "could", "would",
    "should", "do", "does", "is", "are", "explain", "tell", "show me",
)
# the imperative grade verb + a run/case object cue (both must be present): an unambiguous
# "grade THIS" request, not a stray "run" inside prose.
_RUN_REQUEST_VERB = re.compile(r"\b(run|re-?run|grade|evaluate|score)\b")
_RUN_REQUEST_OBJECT = re.compile(r"\b(eval|evaluation|case|live|grade|run|it|this)\b")
# ZERO-DOLLAR-ROUTE: an EXPLICIT "$0 / replay / stored (last) result / for free / at no cost /
# don't spend / without spending|paying" ask is NEVER a run-request — "run a $0 replay of case X"
# contains "run", so without this guard the deterministic fallback below opened the PAID
# cost-confirm on a $0 ask (the live 2026-07-04 defect; the "for free" family was a
# critic-verified residual red). The credit-safety invariant: a $0 path never escalates to a
# paid proposal on its own; the chat serves it with review_runs (the $0 read) instead. The
# free-alternates are PHRASE-bounded ("for free" / "free of charge"), so a "freeform"/
# "free-text" token never over-excludes a legitimate paid proposal.
_ZERO_DOLLAR_RE = re.compile(
    r"\$\s*0\b|\bzero[- ]dollar\b|\breplay\b|\bstored\b|\blast result\b"
    r"|\bdon'?t spend\b|\bdo not spend\b|\bwithout spending\b|\bno spend\b"
    r"|\bfor free\b|\bfree of charge\b|\bno cost\b|\bwithout paying\b"
)


def _is_run_request(message: str) -> bool:
    """CONFIRM-MODAL-FALLBACK-1 — a CONSERVATIVE run-intent matcher for the litellm-path cost-confirm
    fallback. True only for an unambiguous imperative "grade the case" request; questions and
    explain/show asks are excluded (they mean "tell me about the run", not "run it"). Empty → False.

    A run-request iff: the message is NOT a question (no ``?``, not opened by a question/explain word)
    AND it is NOT an explicit $0/replay/stored-result ask (``_ZERO_DOLLAR_RE`` — ZERO-DOLLAR-ROUTE:
    the fallback must never open the PAID modal on a $0 ask) AND it contains an imperative grade
    verb (run/re-run/grade/evaluate/score) AND a run/case object cue
    (eval/evaluation/case/live/grade/run/it/this). Pure (no I/O); the fallback in ``_litellm_loop``
    calls it post-loop to decide whether to deterministically surface the cost-confirm directive."""
    text = (message or "").strip().lower()
    if not text:
        return False
    if "?" in text:
        return False
    if any(
        text == opener or text.startswith(opener + " ") for opener in _RUN_REQUEST_QUESTION_OPENERS
    ):
        return False
    if _ZERO_DOLLAR_RE.search(text):
        return False
    return bool(_RUN_REQUEST_VERB.search(text)) and bool(_RUN_REQUEST_OBJECT.search(text))


# RUN-ALL-ROUTE — the COHORT-intent matcher (sibling of _is_run_request). True for an unambiguous
# "grade the whole corpus" imperative: a grade verb + an all/every/whole quantifier, or a bare
# "all cases"/"every case"/"whole suite"/"all of them". Checked BEFORE _is_run_request so
# "run all cases" routes to the cohort directive, not a single-case run (which 500s on a corpus
# agent with no bound case). Questions excluded (a question ABOUT grading is not a request to grade).
_GRADE_ALL_RE = re.compile(
    r"\b(?:run|re-?run|grade|evaluat\w*|scor\w*)\s+(?:all|every|everything|the\s+(?:whole|entire|full|cohort|suite|corpus|batch))\b"
    r"|\b(?:all|every)\s+(?:the\s+)?(?:ingested\s+)?cases?\b"
    r"|\b(?:whole|entire|full)\s+(?:suite|corpus|cohort|set|batch)\b"
    r"|\ball\s+of\s+them\b"
)


def _is_grade_all_request(message: str) -> bool:
    """RUN-ALL-ROUTE — conservative cohort-intent matcher (see ``_GRADE_ALL_RE``). Pure; the
    ``_litellm_loop`` route calls it to (a) UPGRADE a mis-picked single directive to the cohort
    one and (b) emit the cohort directive in the no-directive fallback. Empty/question → False.
    ZERO-DOLLAR-ROUTE: an explicit $0/replay ask is excluded here too — the cohort modal is as
    paid as the single one, and a $0 ask must never escalate to either."""
    text = (message or "").strip().lower()
    if not text or "?" in text:
        return False
    if _ZERO_DOLLAR_RE.search(text):
        return False
    return bool(_GRADE_ALL_RE.search(text))


# RUN-TRAIL-CASE-SCOPE — a case-id-shaped token: starts with a letter and carries at least
# one underscore (every corpus/ingested case id does — cv_mts_*, snomed_inj_*, case_10).
# Deliberately conservative: prose words don't carry underscores, so a miss means an
# UNSCOPED $0 read (today's behavior), never a wrong scope.
_CASE_TOKEN_RE = re.compile(r"\b[A-Za-z][\w.-]*_[\w.-]*[A-Za-z0-9]\b")


def _zero_dollar_case_token(message: str) -> str | None:
    """The case the user NAMED in a $0 ask ("run a $0 replay of cv_mts_002_… and show the
    report") — the first case-id-shaped token that is not a Lithrim tool name (a user
    echoing 'review_runs' must not scope the read to a bogus case). None when no such
    token exists (the read stays unscoped). Pure."""
    for tok in _CASE_TOKEN_RE.findall(message or ""):
        if tok not in _LITHRIM_HANDLERS:
            return tok
    return None


def _is_zero_dollar_replay_request(message: str) -> bool:
    """ZERO-DOLLAR-ROUTE, the SERVING half: True for an unambiguous "$0 replay / stored
    result" request the deterministic fallback should serve with review_runs (the $0 read)
    when the model narrated without calling it. The same trigger family the paid-fallback
    GUARD excludes (``_ZERO_DOLLAR_RE``), plus a run/replay/show cue so a stray mention of
    'replay' inside a question or bare prose doesn't auto-fire a card. Pure."""
    text = (message or "").strip().lower()
    if not text or "?" in text:
        return False
    if not _ZERO_DOLLAR_RE.search(text):
        return False
    return bool(
        _RUN_REQUEST_VERB.search(text)
        or re.search(r"\b(replay|show|report|result)\b", text)
    )


async def _litellm_loop(
    message: str,
    ctx: ToolContext,
    history: list[dict] | None = None,
    *,
    provider: str,
    model: str,
    api_key: str | None,
    api_base: str | None,
    api_version: str | None = None,
    _completion: Callable[..., Any] | None = None,
) -> AsyncIterator[dict]:
    """CONV-RUNTIME-1 — the provider-agnostic conversation loop on litellm (OpenAI tools). Drives
    the SAME ``_TOOL_SPECS`` handlers and yields the SAME SSE event contract as ``_run_sdk_chat``
    (assistant_delta / tool_call / tool_result / run_result / error / done), so OpenAI / Gemini /
    Bedrock / Azure / openai_compatible can drive the chat for a non-anthropic configured provider.

    A-SAFE FLOOR (this engine's whole security bound — there are no built-ins on this path; litellm
    only ever sees the tools we pass): (a) WHITELIST dispatch — only a name resolving into
    ``_TOOL_SPECS`` runs; a Bash / unknown call is fed back as a "not a Lithrim tool" tool-result and
    NEVER executed; (b) one-step pacing parity with ``_pace_one_step`` — the 2nd+ step-proposing
    write in a turn is paced (fed back the verbatim ``_ONE_STEP_PACING_MESSAGE``, not executed);
    (c) ``run_eval`` stays REPLAY-ONLY — the handler drops every paid knob, so no ``confirm`` /
    ``in_process`` / ``live`` ever reaches a bound op. ``_completion`` is injected by tests
    (a mocked ``litellm.completion``) so the loop runs $0 / offline.
    """
    completion = _completion
    if completion is None:  # pragma: no cover — the live path; tests inject a mocked completion
        import litellm

        completion = litellm.completion

    tools = _openai_tool_schemas()
    # EXPLAIN-RESULT-PARITY-1: inject the latest-run context ($0 review_runs read) so the
    # litellm provider (azure/openai/gemini/bedrock) explains "this result" from context too —
    # the PARITY with the SDK path. Present-only (no-run ⇒ byte-identical to the pre-PARITY prompt).
    messages: list[dict] = [
        {
            "role": "system",
            "content": _system_prompt(
                ctx.default_agent, ctx.active_case, latest_run=_latest_run_context(ctx)
            ),
        }
    ]
    for turn in history or []:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        role = "user" if turn.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    model_id = f"{_litellm_prefix(provider)}/{model}"
    completion_kwargs: dict[str, Any] = {
        "model": model_id,
        "tools": tools,
        "tool_choice": "auto",
        "stream": True,
        "temperature": 0,
        "max_tokens": 4096,
    }
    if api_key:
        completion_kwargs["api_key"] = api_key
    if api_base:  # azure / openai_compatible
        completion_kwargs["api_base"] = api_base
    if api_version:  # CONNECT-AI-AZURE-1: azure needs an api_version (empty/None for non-azure)
        completion_kwargs["api_version"] = api_version

    cost_usd: float | None = None
    # CONFIRM-MODAL-FALLBACK-1: track whether a cost-confirm directive (tool-propose_live_run) was
    # emitted this turn — by run_eval OR propose_live_run. If the model narrates "I'll surface the
    # modal" but calls NO tool (the live gpt-4.1 failure), no directive reaches the shell and no modal
    # opens; the post-loop fallback below deterministically emits one IFF the user asked to run AND
    # none was emitted. Self-limiting: when the model DID call the tool, the handler already set this
    # True → no double-open. A-SAFE: the fallback emits ONLY the directive (opens the modal); it
    # never fires a paid op — the human's modal-confirm stays the sole spend.
    directive_emitted = False
    # RUN-TRAIL-CASE-SCOPE: whether the model called review_runs itself this turn — the
    # zero-dollar fallback below is skipped when it did (self-limiting, like the above).
    review_runs_called = False
    # RUN-ALL-ROUTE: an unambiguous "grade all cases" message routes to the COHORT directive — both
    # by UPGRADING a mis-picked single directive (below) and in the no-directive fallback — so it
    # never lands on a single-case run that 500s on a corpus agent with no bound case.
    grade_all_intent = _is_grade_all_request(message)
    try:
        for _turn in range(_LITELLM_MAX_TURNS):
            resp = completion(messages=list(messages), **completion_kwargs)
            text_parts: list[str] = []
            # accumulate tool_calls by index (name + the chunked `arguments` JSON string)
            tool_calls: dict[int, dict] = {}
            for chunk in resp:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None)
                if content:
                    text_parts.append(content)
                    yield {"event": "assistant_delta", "text": content}
                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = getattr(tc, "index", 0) or 0
                    slot = tool_calls.setdefault(idx, {"id": None, "name": None, "arguments": ""})
                    if getattr(tc, "id", None):
                        slot["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            slot["arguments"] += fn.arguments

            if not tool_calls:
                break  # a plain assistant turn with no tool call ends the loop

            # append the assistant tool_calls message (so the model sees what it asked for)
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts) or None}
            ordered = [tool_calls[i] for i in sorted(tool_calls)]
            assistant_msg["tool_calls"] = [
                {
                    "id": c["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": c["name"] or "", "arguments": c["arguments"] or "{}"},
                }
                for i, c in enumerate(ordered)
            ]
            messages.append(assistant_msg)

            writes_this_turn = 0  # one-step pacing: turn-local counter (parity with _pace_one_step)
            for i, call in enumerate(ordered):
                call_id = call["id"] or f"call_{i}"
                raw_name = call["name"] or ""
                bare = _resolve_lithrim_tool(raw_name)
                # (a) WHITELIST: a non-lithrim / unknown name is NEVER executed — fed back as error.
                if bare is None:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": (
                                f"{raw_name or '<unknown>'} is not a Lithrim tool; this agent is "
                                "bounded to the loaded tools (it can never fire a paid run or touch "
                                "the host). Call a loaded tool by its exact name instead."
                            ),
                        }
                    )
                    continue
                # parse arguments (a malformed JSON string → feed an error tool-result, never crash)
                try:
                    args = json.loads(call["arguments"] or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("tool arguments must be a JSON object")
                except (ValueError, TypeError) as exc:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": f"Could not parse the arguments for {bare}: {exc}. Resend valid JSON.",
                        }
                    )
                    continue
                # (b) ONE-STEP PACING: the 2nd+ step-proposing write this turn is paced, not run.
                if bare in _STEP_PROPOSING_WRITES:
                    writes_this_turn += 1
                    if writes_this_turn > 1:
                        messages.append(
                            {"role": "tool", "tool_call_id": call_id, "content": _ONE_STEP_PACING_MESSAGE}
                        )
                        continue
                # dispatch the whitelisted handler (it drops paid knobs by construction; run_eval is replay)
                yield {"event": "tool_call", "name": bare, "input": args}
                if bare == "review_runs":
                    # RUN-TRAIL-CASE-SCOPE: the model served the $0 read itself — the
                    # post-loop zero-dollar fallback is SKIPPED (no double-serve).
                    review_runs_called = True
                handler = _LITHRIM_HANDLERS[bare]
                result = await handler(ctx, args)
                # drain the gen-UI parts + any $0 replay record this handler emitted
                while ctx.parts:
                    part = ctx.parts.pop(0)
                    # RUN-ALL-ROUTE: for an unambiguous "grade all" message, UPGRADE a mis-picked
                    # single-run directive (the model's frequent wrong choice) to the cohort one, so
                    # the Grade-all modal opens instead of a single-case run. $0/A-SAFE (both only
                    # open a modal); the single directive never reaches the shell.
                    if grade_all_intent and part.get("type") == "tool-propose_live_run":
                        part = propose_run_all_part()
                    # CONFIRM-MODAL-FALLBACK-1: a cost-confirm directive from run_eval/propose_live_run
                    # — record it so the post-loop fallback is SKIPPED (no double-open).
                    if part.get("type") in ("tool-propose_live_run", "tool-propose_run_all"):
                        directive_emitted = True
                    yield {"event": "tool_result", "part": part}
                while ctx.run_results:
                    yield {"event": "run_result", "result": ctx.run_results.pop(0)}
                # feed the handler's text summary back to the model as the tool-result
                summary = ""
                for block in (result or {}).get("content", []):
                    if block.get("type") == "text":
                        summary += block.get("text", "")
                messages.append(
                    {"role": "tool", "tool_call_id": call_id, "content": summary or "(done)"}
                )
        # CONFIRM-MODAL-FALLBACK-1 — the self-limiting cost-confirm fallback. Azure gpt-4.1 narrates
        # "I will surface the cost-confirm modal" ~40-60% of run-requests WITHOUT calling any tool
        # (8 live trials), so no directive reaches the shell and no modal opens. If the user clearly
        # asked to run AND no directive was emitted this turn, the BFF deterministically emits one —
        # making the agent's narrated intent TRUE (honest-Δ). SELF-LIMITING: when the model DID call
        # run_eval/propose_live_run, ``directive_emitted`` is already True → this is skipped (no
        # double-open). A-SAFE: ``propose_live_run_part()`` only OPENS the in-DOM CostModal — it fires
        # NO paid op; the human's modal-confirm remains the sole spend.
        if not directive_emitted and grade_all_intent:
            # RUN-ALL-ROUTE: a "grade all" message with no directive → emit the COHORT directive (the
            # cohort modal), not the single one. Checked before the single-run fallback so "run all
            # cases" never falls through to a single-case run.
            yield {"event": "tool_result", "part": propose_run_all_part()}
        elif not directive_emitted and _is_run_request(message):
            # CHAT-CASE-RESOLVE-1 follow-on: carry the resolved/named active case so the fallback
            # directive targets the SAME case the handler directives do (a present-only selector,
            # not a paid field) — else confirmPaidRun grades the stale client selection.
            yield {"event": "tool_result", "part": propose_live_run_part(ctx.active_case)}
        elif (
            not directive_emitted
            and not review_runs_called
            and _is_zero_dollar_replay_request(message)
        ):
            # RUN-TRAIL-CASE-SCOPE — the ZERO-DOLLAR-ROUTE fallback's SERVING half. The guard
            # above keeps a "$0 replay of case X" ask off the paid modal, but a narrate-only
            # model then served NOTHING (and the case the user NAMED was dropped before any
            # tool ran — the 2026-07-04 trace). Deterministically serve the $0 read WITH the
            # named case token, mirroring CONFIRM-MODAL-FALLBACK-1 (self-limiting via
            # ``review_runs_called``). A-SAFE: review_runs is a pure read — no paid surface.
            zd_args: dict[str, Any] = {}
            token = _zero_dollar_case_token(message)
            if token:
                zd_args["case_id"] = token
            yield {"event": "tool_call", "name": "review_runs", "input": zd_args}
            zd_result = await _LITHRIM_HANDLERS["review_runs"](ctx, zd_args)
            while ctx.parts:
                yield {"event": "tool_result", "part": ctx.parts.pop(0)}
            zd_text = "".join(
                b.get("text", "")
                for b in (zd_result or {}).get("content", [])
                if b.get("type") == "text"
            )
            if zd_text:
                # relay the read's narration (incl. a refusal's verbatim guard message) —
                # the fallback makes the model's narrated intent TRUE, honestly labeled.
                yield {"event": "assistant_delta", "text": "\n" + zd_text}
    except Exception as exc:  # surface a loop/transport failure to the pane, don't 500
        yield {"event": "error", "detail": str(exc)}
        return
    yield {"event": "done", "cost_usd": cost_usd, "cost_label": _LITELLM_COST_LABEL}


async def run_chat(
    message: str,
    ctx: ToolContext,
    *,
    history: list[dict] | None = None,
    source: Callable[[str, ToolContext, list[dict] | None], AsyncIterator[Any]] | None = None,
) -> AsyncIterator[dict]:
    """CONV-RUNTIME-1 — the conversation-engine DISPATCHER (the public entry; ``chat_endpoint``
    stays a thin caller). When ``_chat_provider_config()`` is ``None`` (anthropic / BYO-Claude /
    unset) → the EXISTING Anthropic Agent-SDK consumer (``_run_sdk_chat``), byte-identical (the
    ``source`` stub still threads through it). Otherwise → the provider-agnostic ``_litellm_loop``.
    BOTH yield the identical SSE event contract, so ``sse_format`` / ``chat_endpoint`` are unchanged."""
    cfg = _chat_provider_config()
    if cfg is None:
        try:
            async for event in _run_sdk_chat(message, ctx, history=history, source=source):
                yield event
        except ModuleNotFoundError as exc:
            if exc.name != "claude_agent_sdk":
                raise
            # FIRST-CONTACT-1: the [agent] extra (and the claude CLI) don't ship in the Docker
            # image — the SDK path CANNOT run there. Without this, the ImportError fires after
            # the SSE headers are sent, the stream dies, and the shell renders the false
            # "Couldn't reach the server". Say what to do instead. (Short, slash-free detail so
            # the shell's friendlyError keeps it verbatim.)
            yield {
                "event": "error",
                "detail": (
                    "The assistant needs a model. In Connect AI (⋯ menu, bottom left) "
                    "assign it one from OpenAI, Azure, Gemini, or OpenAI-compatible."
                ),
            }
        return
    async for event in _litellm_loop(
        message, ctx, history,
        provider=cfg["provider"], model=cfg.get("model") or "",
        api_key=cfg.get("api_key"), api_base=cfg.get("api_base"),
        api_version=cfg.get("api_version"),
    ):
        yield event


def sse_format(event: dict) -> str:
    """One SSE frame (``data: <json>\\n\\n``) for a run_chat event."""
    return f"data: {json.dumps(event, default=str)}\n\n"
