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

from .adapter import (
    agent_part,
    audit_part,
    case_summary_part,
    flag_part,
    judge_part,
    open_artifact_part,
    propose_live_run_part,
    verdict_part,
)

# Plain-dict input schemas (SDK-free; the A-SAFE test asserts the paid keys are
# ABSENT from RUN_EVAL_SCHEMA — the agent literally cannot request a paid run).
AUTHOR_JUDGE_SCHEMA: dict[str, Any] = {
    "role": str,
    "assigned_flags": list,
    "rationale": str,
    # BYOC-1: the provider selector — "" (default Azure LM) | "byo-claude" (the tool-less
    # BYO-Claude judge). Not a paid knob (an audited config write via put_judge).
    "model": str,
}
GET_JUDGE_SCHEMA: dict[str, Any] = {"role": str}
# NARR-CHAT-LOOP: ``case_id`` selects WHICH ingested-corpus case to grade (the "run case X"
# leg). It is a SELECTOR, not a paid knob — the A-SAFE test asserts no PAID_KEY is here, and
# the handler defaults an omitted case_id to the shared active case (never a paid path).
RUN_EVAL_SCHEMA: dict[str, Any] = {"agent": str, "case_id": str}
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
# UAP-5c-2 — the first agent-reachable Agent WRITE, scoped to EDIT-ONE-FACET (the judges
# roster): add or remove ONE known v2 judge. The agent supplies a DELTA, never a full Agent
# dict (which it cannot build conversationally). Mirrors author_flag's edit-only discipline.
ASSEMBLE_AGENT_SCHEMA: dict[str, Any] = {
    "name": str,
    "add_judge": str,
    "remove_judge": str,
    "rationale": str,
}
# CRUD-1 (D3) — the FIRST agent-reachable DELETE, scoped to REVERT-TO-DEFAULT: remove a
# judge's authored JudgeConfig so the role falls back to its default lens. Reversible +
# bounded (no PAID_KEY); the role never disappears (LENS_BY_ROLE), no flag is orphaned —
# which is why judge-delete is agent-exposable. Agent-DELETE is NOT a tool (human-only,
# too destructive — mirrors flag-create's human-act posture).
DELETE_JUDGE_SCHEMA: dict[str, Any] = {"role": str, "rationale": str}
# FLAG-1 (D2) — CREATE a NEW *reference* flag. The DEFINITIONAL fields only; there is NO
# `gradeable` field AT ALL — the agent has no knob to make a flag scoreable, and the bound
# _create_flag hardcodes gradeable=False/tier=None/owner_roles=[]. A gradeable flag is a
# lithrim-backend re-snapshot (labels are true by construction); it cannot be created from
# clean. The A-SAFE test asserts "gradeable" not in this schema (non-vacuous).
CREATE_FLAG_SCHEMA: dict[str, Any] = {
    "flag_code": str,
    "category": str,
    "definition": str,
    "when_to_use": str,
    "when_NOT_to_use": str,
    "rationale": str,
}
# FLAG-1 (D3) — DELETE a REFERENCE flag (reversible — re-create any time). {flag_code, rationale}
# only: no gradeable knob, no paid knob. The reference-only + orphan guards (gradeable/in-snapshot,
# judge-assigned, case-emitted) live in the ENDPOINT (delete_flag_endpoint), NOT here, so they hold
# for EVERY caller; this tool reaches only an UNUSED reference flag.
DELETE_FLAG_SCHEMA: dict[str, Any] = {"flag_code": str, "rationale": str}
# CHATBIND-2 — the pane-control DIRECTIVE tool ($0, read-only). It emits a UI directive so the
# conversation can OPEN + FOCUS the artifact pane; it wraps NO op and carries NO paid knob. The
# schema is {tab} ONLY — `ref` was dropped (no consumer under the run_result lift; re-add with one
# later, per the CHATBIND-1 drop-unreachable discipline). The 5 tabs are the contract.
FOCUS_ARTIFACT_SCHEMA: dict[str, Any] = {"tab": str}
# "case" (CHATBIND-3) is the SOURCE INPUT view (transcript + artifact + the planted label) — the
# "show me the case before we run it" leg. Still $0/read: the tab self-fetches GET /v1/case.
_ARTIFACT_TABS = ("case", "report", "judges", "config", "corpus")
# CHATBIND-3 / NARR-CHAT-LOOP: show_case takes an OPTIONAL ``case_id`` — it summarizes a
# SPECIFIC ingested-corpus case as an inline card (the card self-fetches GET /v1/case?case_id=X).
# Omitted → the shared active case. $0/read, no paid knob (a selector, not a spend). The live bug
# this fixes: with no case_id the tool always showed the agent's seed, so "open case X" claimed X
# but showed the seed (confident-but-wrong).
SHOW_CASE_SCHEMA: dict[str, Any] = {"case_id": str}
# NARR-CHAT-LOOP: list_cases takes NO params — it enumerates the active workspace's INGESTED
# corpus (GET /v1/cases) so "show me the cases I can evaluate" surfaces the real corpus, not the
# agent's single seed case. $0/read, no paid knob, nothing to smuggle.
LIST_CASES_SCHEMA: dict[str, Any] = {}
# CHATBIND-4: propose_live_run takes NO params — it asks the shell to OPEN the cost-confirm modal.
# The agent PROPOSES; the human's modal-confirm is the only paid path. No paid knob, nothing to smuggle.
PROPOSE_LIVE_RUN_SCHEMA: dict[str, Any] = {}
# GROUND-CHAT-1 — ADD a grounding (verification) contract to the active agent's DRAFT ontology
# (an audited config WRITE; makes "step 5: add grounding contracts" conversational). Entry shape
# mirrors ContractBuilder.jsx + ontology.VerificationContractDecl: {contract_type, flag_code,
# question, params, version}. $0 — NO PAID_KEY (the A-SAFE test asserts this generically over
# _TOOL_SPECS). question/version/agent are optional (defaulted in the handler, exactly as
# ContractBuilder defaults version to f"{flag_code}/v1").
ADD_GROUNDING_CONTRACT_SCHEMA: dict[str, Any] = {
    "flag_code": str,
    "contract_type": str,
    "params": dict,
    "agent": str,
    "question": str,
    "version": str,
}
# KB-CONTEXT-1 — the honest CONTEXT AID ($0/read-only): retrieve the relevant HIPAA-KB section(s)
# for a topic/finding and SHOW them, WITHOUT touching the verdict (kb_grounding-as-suppress over-
# clears on these flags, so this is retrieval-only — informative, never a clear). No PAID_KEY.
KB_CONTEXT_SCHEMA: dict[str, Any] = {"query": str, "namespace": str, "top_k": int}
# NARR-2 — INGEST cases: drop a JSON dump → generate a JUTE jute_transform → live-gate on :3031 →
# apply → PIN (persist_or_update) → upsert the workspace corpus + write ONE AuditRecord. The
# "eval anything" ingestion half. The bound _ingest_cases owns generate/gate/pin/upsert/audit; the
# handler surfaces a structured error (invariant failed / :3031 down / nothing pinned) exactly as
# add_grounding_contract surfaces 404/422 — never bypassed, NEVER a paid run. NO PAID_KEY: ingestion
# is the author-side JUTE transform ($0/BYO-key), not a council grade. `json` is the dump (string);
# `extraction_rules`/`agent` are optional. The extractor is INGESTION-ONLY — it never reaches the
# grade-time floor (trust-model separation; SPEC_NARRATIVE_EVAL A4).
INGEST_CASES_SCHEMA: dict[str, Any] = {
    "json": str,
    "extraction_rules": str,
    "agent": str,
}
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
    - ``assemble_agent(name, add_judge, remove_judge, rationale) -> dict``  (UAP-5c-2 Domain
      WRITE, EDIT-ONE-FACET: load→edit the judges roster→put; audited; raises on an unknown
      role/agent — the handler surfaces it, never a full-dict from the model)
    - ``delete_judge(role, rationale) -> dict``  (CRUD-1 D3: REVERT a judge to its default
      lens — remove its authored config; audited; reversible. Raises on an unknown role —
      the handler surfaces it. It CANNOT delete an agent or fire a paid run.)
    - ``create_flag(flag_code, category, definition, when_to_use, when_NOT_to_use, rationale)
      -> dict``  (FLAG-1 D1: CREATE a new REFERENCE flag — gradeable=False/tier=None/
      owner_roles=[] hardcoded; raises 409 if it exists. It CANNOT create a gradeable flag.)
    - ``delete_flag(flag_code, rationale) -> dict``  (FLAG-1 D3: DELETE a REFERENCE flag;
      reversible. The reference-only + orphan guards live in the endpoint, so this reaches only
      an UNUSED reference flag; a contract/judge-assigned/case-emitted flag raises and is surfaced.)
    - ``put_grounding_contract(flag_code, contract_type, params, question, version, agent) -> dict``
      (GROUND-CHAT-1: splice/replace the verification_contracts entry for flag_code in the DRAFT
      ontology, then PUT via the FROZEN audited op; 404 unknown flag / 422 malformed — surfaced.
      An audited $0 config write — the conversational "add grounding contracts" move.)
    - ``kb_context(query, namespace, top_k) -> dict``  (KB-CONTEXT-1: read-only KB RETRIEVAL — the
      honest "show the relevant HIPAA section" context aid; returns chunks, NEVER changes a verdict.)
    - ``ingest_cases(json_dump, extraction_rules, agent) -> dict``  (NARR-2: the "eval anything"
      ingestion half — generate a JUTE jute_transform, live-gate on :3031, apply, PIN
      (persist_or_update), upsert the workspace corpus + write ONE AuditRecord. Returns
      {cases, mapping_id, count}. Raises on an invariant failure / :3031 down — the handler
      surfaces it and NOTHING is pinned. INGESTION-ONLY: the extractor never reaches the
      grade-time floor (trust-model separation). $0/BYO-key — never a paid run.)
    - ``list_cases() -> dict``  (NARR-CHAT-LOOP: enumerate the active workspace's INGESTED corpus
      — the gradeable cases a user dropped via ingest — so "show me the cases" surfaces the real
      corpus, not the agent's single seed. Returns {cases, count}. $0/read.)
    - ``default_agent``: the agent the tools default to.
    - ``active_case``: NARR-CHAT-LOOP — the case the human is exploring in the UI (the shared
      "active case" the shell sends per turn). run_eval/show_case DEFAULT their ``case_id`` to it
      when omitted, so a conversational run grades the case on screen — never the agent's seed.
      ``None`` keeps the agent's own ``dataset.case_id`` (back-compat). A selector, never a spend.
    """

    author_judge: Callable[..., dict]
    get_judge: Callable[..., dict]
    run_eval_replay: Callable[..., dict]
    get_agent: Callable[..., dict]
    author_flag: Callable[..., dict]
    review_runs: Callable[..., dict]
    run_eval_pack: Callable[..., dict]
    assemble_agent: Callable[..., dict]
    delete_judge: Callable[..., dict]
    create_flag: Callable[..., dict]
    delete_flag: Callable[..., dict]
    put_grounding_contract: Callable[..., dict]
    kb_context: Callable[..., dict]
    ingest_cases: Callable[..., dict]
    list_cases: Callable[..., dict]
    default_agent: str = "ws0_default"
    active_case: str | None = None
    parts: list[dict] = field(default_factory=list)
    run_results: list[dict] = field(default_factory=list)

    def emit(self, part: dict) -> None:
        self.parts.append(part)

    def emit_run(self, record: dict) -> None:
        """CHATBIND-2 (D4): stash the chat's $0 REPLAY record so the loop LIFTS it into the
        shell's shared ``runResult`` (the run-bearing Report/Judge tabs render it). The record
        is byte-same to the manual Run-eval result; ONLY run_eval (replay-only) ever calls this,
        so no paid path is ever lifted."""
        self.run_results.append(record)


def _text(summary: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": summary}]}


def _error(summary: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": summary}], "is_error": True}


async def author_judge_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    role = str(args.get("role") or "")
    assigned = list(args.get("assigned_flags") or [])
    rationale = str(args.get("rationale") or "authored via the conversational shell")
    model = str(args.get("model") or "")  # BYOC-1 provider selector ("" | "byo-claude")
    try:
        res = ctx.author_judge(role=role, assigned_flags=assigned, rationale=rationale, model=model)
    except Exception as exc:  # HTTPException (422/404) or anything the op raises
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not author judge {role!r}: {detail}. The assignment was NOT persisted "
            f"(the owner<->emit / snapshot gate held). Propose a valid lens and retry."
        )
    ctx.emit(judge_part(role, ctx.default_agent))
    return _text(
        f"Authored judge {role!r} with assigned flags {res.get('assigned_flags', assigned)} "
        f"on model {model or '(default Azure)'} "
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
    # NARR-CHAT-LOOP: grade the case the human is exploring (an explicit case_id, else the shared
    # active case), not the agent's seed. ``case_id`` is a SELECTOR (the spy test proves no PAID_KEY
    # reaches the op alongside it); ``None`` keeps the agent's own dataset.case_id (back-compat).
    case_id = args.get("case_id") or ctx.active_case
    try:
        record = ctx.run_eval_replay(agent=agent, case_id=case_id)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Replay run failed for {agent!r}: {detail}.")
    ctx.emit(verdict_part(record))
    ctx.emit_run(record)  # CHATBIND-2 (D4): lift this $0 replay into the shell's runResult
    composite = record.get("composite") or {}
    # Surface the grounding corrections so the agent can REASON about them (and narrate
    # which tool suppressed which false positive) — not just the top-line verdict. The
    # grounded_adjustments are tool-verified suppressions (a confident council finding
    # disproved by a deterministic floor, e.g. SNOMED subsumption over Hermes).
    adj = composite.get("grounded_adjustments") or []
    sup = (
        "; ".join(
            f"{a.get('flag')} suppressed by {a.get('contract')} — {(a.get('reason') or '').strip()[:120]}"
            for a in adj
        )
        or "none"
    )
    # active_findings entries are flag-code STRINGS (or finding dicts) — normalize either shape.
    # (The prior dict-only filter silently dropped string findings, telling the agent "none stand"
    # on a reject verdict — a manufactured-win data bug the agent then faithfully relayed.)
    active = [
        (f.get("flag_code") or f.get("code")) if isinstance(f, dict) else f
        for f in (composite.get("active_findings") or [])
    ]
    active = [a for a in active if a]
    verdict = composite.get("verdict", "—")
    meaning = {
        "reject": "the case was REJECTED",
        "approve": "the case was APPROVED",
        "needs_review": "the case NEEDS REVIEW",
    }.get(str(verdict), str(verdict))
    return _text(
        f"Ran a $0 REPLAY eval for {agent!r}. VERDICT = {str(verdict).upper()} ({meaning}). "
        f"{len(active)} finding(s) STILL STAND and drive this verdict — do NOT call the case clean or "
        f"say 'nothing stands' when this list is non-empty: {active or 'none'}. "
        f"{len(adj)} false-positive(s) were tool-corrected (this corrects ONLY these; it does NOT "
        f"clear the standing findings above): {sup}. "
        f"Narrate the verdict + the standing findings honestly. "
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


async def assemble_agent_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # The Domain WRITE (audited), EDIT-ONE-FACET: add/remove ONE known v2 judge in the
    # agent's roster. Never accepts a full agent dict; an unknown role/agent (or no delta)
    # raises (404/422/400) and is surfaced, never bypassed (mirrors author_flag's discipline).
    name = str(args.get("name") or ctx.default_agent)
    add_judge = args.get("add_judge")
    remove_judge = args.get("remove_judge")
    rationale = str(args.get("rationale") or "assembled via the conversational shell")
    try:
        res = ctx.assemble_agent(
            name=name, add_judge=add_judge, remove_judge=remove_judge, rationale=rationale
        )
    except Exception as exc:  # HTTPException (404 unknown role/agent, 422 malformed, 400 no-op)
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not edit agent {name!r}: {detail}. The agent was NOT changed (the "
            f"validation gate held). Add or remove a KNOWN judge role; do not invent a "
            f"judge or supply a whole agent."
        )
    ctx.emit(agent_part(name))
    return _text(
        f"Edited agent {name!r}: judges={res.get('judges')} (added {add_judge or '—'}, "
        f"removed {remove_judge or '—'}). The Agent write is audited."
    )


async def delete_judge_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # CRUD-1 (D3): REVERT a judge to its default lens (remove its authored JudgeConfig).
    # Reversible + bounded — the agent-exposable half of CRUD. A-SAFE: no PAID_KEY in the
    # schema, and the bound op is delete_judge_endpoint (revert-only) — this tool can NEITHER
    # delete an agent (human-only) NOR fire a paid run. An unknown role (404) is surfaced.
    role = str(args.get("role") or "")
    rationale = str(args.get("rationale") or "reverted to default via the conversational shell")
    try:
        res = ctx.delete_judge(role=role, rationale=rationale)
    except Exception as exc:  # HTTPException (404 unknown role) or anything the op raises
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not revert judge {role!r}: {detail}. Nothing was changed. Revert a KNOWN "
            f"judge role (risk_judge / policy_judge / faithfulness_judge)."
        )
    ctx.emit(judge_part(role, ctx.default_agent))
    state = (
        "removed its authored config — it now uses its DEFAULT lens"
        if res.get("removed")
        else "was already at its default lens (no change)"
    )
    return _text(
        f"Reverted judge {role!r}: {state} (actor {res.get('actor', {}).get('id', '?')}). "
        f"The revert is audited; re-author it any time to re-bind a lens."
    )


async def create_flag_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # FLAG-1 (audited WRITE): CREATE a NEW reference flag. gradeable=False BY CONSTRUCTION —
    # this schema has NO gradeable field and the bound _create_flag hardcodes gradeable=False/
    # tier=None/owner_roles=[]. The agent CANNOT create a scoreable flag; a gradeable flag is a
    # lithrim-backend re-snapshot. 409 if the code already exists (edit it via author_flag).
    flag_code = str(args.get("flag_code") or "")
    category = str(args.get("category") or "")
    definition = str(args.get("definition") or "")
    when_to_use = str(args.get("when_to_use") or "")
    when_not = str(args.get("when_NOT_to_use") or "")
    rationale = str(args.get("rationale") or "created via the conversational shell")
    try:
        ctx.create_flag(
            flag_code=flag_code,
            category=category,
            definition=definition,
            when_to_use=when_to_use,
            when_NOT_to_use=when_not,
            rationale=rationale,
        )
    except Exception as exc:  # HTTPException (409 exists / 422 malformed) or anything the op raises
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not create flag {flag_code!r}: {detail}. Nothing was persisted. Create a NEW "
            f"reference flag (non-gradeable by construction); to re-grade a flag you need a backend "
            f"re-snapshot, and to edit an existing flag use author_flag."
        )
    ctx.emit(flag_part(ctx.default_agent))
    return _text(
        f"Created reference flag {flag_code!r} (gradeable=False, tier=None, owner_roles=[]) for "
        f"agent {ctx.default_agent!r}. It is grounding-skip-logged, never scored. The ontology "
        f"working copy is audited."
    )


async def delete_flag_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # FLAG-1 (audited WRITE): DELETE a REFERENCE flag. The reference-only + orphan guards
    # (gradeable/in-snapshot, judge-assigned, case-emitted) live in delete_flag_endpoint, so
    # this reaches only an UNUSED reference flag; a contract code (or a judge-assigned / case-
    # emitted flag) raises 422 and is surfaced. Reversible — re-create any time.
    flag_code = str(args.get("flag_code") or "")
    rationale = str(args.get("rationale") or "deleted via the conversational shell")
    try:
        res = ctx.delete_flag(flag_code=flag_code, rationale=rationale)
    except Exception as exc:  # HTTPException (404 unknown / 422 guard) or anything the op raises
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not delete flag {flag_code!r}: {detail}. Nothing was changed. Delete an UNUSED "
            f"reference flag only — a gradeable/in-snapshot contract code, or one a judge assigns or "
            f"a case emits, is refused."
        )
    ctx.emit(flag_part(ctx.default_agent))
    return _text(
        f"Deleted reference flag {flag_code!r} for agent {ctx.default_agent!r} "
        f"(actor {res.get('actor', {}).get('id', '?')}). The removal is audited (action=delete)."
    )


async def add_grounding_contract_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # GROUND-CHAT-1 (audited WRITE): add/replace ONE verification_contract for flag_code in the
    # active agent's DRAFT ontology — the conversational "step 5: add grounding contracts" move.
    # $0, no PAID_KEY. The splice (replace-by-flag-code else append) + the FROZEN audited PUT live in
    # the bound ctx.put_grounding_contract; a 404 (unknown flag) / 422 (malformed) is surfaced, never
    # bypassed. question/version default exactly as ContractBuilder.jsx does. ``flag`` is accepted as
    # an alias for ``flag_code`` (the model often reaches for the shorter name — don't make it fumble).
    flag_code = str(args.get("flag_code") or args.get("flag") or "")
    contract_type = str(args.get("contract_type") or "")
    params = args.get("params") if isinstance(args.get("params"), dict) else {}
    question = str(args.get("question") or f"Does the grounding floor verify {flag_code}?")
    version = str(args.get("version") or f"{flag_code or 'contract'}/v1")
    agent = str(args.get("agent") or ctx.default_agent)
    try:
        res = ctx.put_grounding_contract(
            flag_code=flag_code, contract_type=contract_type, params=params,
            question=question, version=version, agent=agent,
        )
    except Exception as exc:  # HTTPException (404 unknown flag / 422 malformed) or anything raised
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not add a grounding contract for {flag_code!r}: {detail}. Nothing was persisted "
            f"(the structural/snapshot gate held). Use a known contract_type and a flag that exists "
            f"in the ontology."
        )
    ctx.emit(flag_part(agent))
    return _text(
        f"Added grounding contract {res.get('version', version)!r} ({contract_type}) for flag "
        f"{flag_code!r} on agent {agent!r} ({'replaced the existing' if res.get('replaced') else 'new'} "
        f"contract). The ontology working copy is audited; the floor runs at grade time over this flag."
    )


async def ingest_cases_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # NARR-2 (audited INGESTION): drop a JSON dump → the bound ctx.ingest_cases generates a JUTE
    # jute_transform, live-gates it on :3031, applies it, PINs the mapping, upserts the workspace
    # corpus, and writes ONE AuditRecord. The handler holds NO generate/pin logic of its own — it
    # forwards + SURFACES a structured error (the structural invariant failed / :3031 down /
    # nothing pinned) exactly as add_grounding_contract surfaces 404/422 — never bypassed, NEVER a
    # paid run (ingestion is the author-side $0/BYO-key JUTE transform, not a council grade). On
    # success it emits a `corpus` focus part (open the corpus tab to see the ingested cases).
    json_dump = str(args.get("json") or "")
    extraction_rules = str(args.get("extraction_rules") or "")
    agent = str(args.get("agent") or ctx.default_agent)
    if not json_dump.strip():
        return _error(
            "ingest_cases needs a `json` dump (the AI-system output to extract eval cases from). "
            "Nothing was ingested or pinned."
        )
    try:
        res = ctx.ingest_cases(
            json_dump=json_dump, extraction_rules=extraction_rules, agent=agent
        )
    except Exception as exc:  # invariant failure / :3031 down / persist error — surface, never pin
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not ingest cases: {detail}. NOTHING was pinned or upserted (the structural "
            f"output-invariant — a JSON array of N records, zero-null on the required keys — held; "
            f"a mis-join returns null, so it is rejected, not silently shipped). Refine the "
            f"extraction rules or check the :3031 mapper is up, then retry."
        )
    count = res.get("count") or len(res.get("cases") or [])
    mapping_id = res.get("mapping_id")
    ctx.emit(open_artifact_part("corpus"))
    return _text(
        f"Ingested {count} case(s) from the JSON dump for agent {agent!r} via pinned mapping "
        f"{mapping_id} — extracted, live-gated on :3031, PINNED, and upserted to the workspace "
        f"corpus (one audit record written; $0, no paid run). Open the corpus tab to review them, "
        f"then author criteria + grade."
    )


async def kb_context_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # KB-CONTEXT-1 ($0/read-only): retrieve the relevant KB section(s) for a topic/finding and SHOW
    # them — the honest CONTEXT AID. It NEVER changes a verdict (retrieval-only; kb_grounding-as-
    # suppress over-clears on these flags, proven, so we surface context instead of clearing). No
    # PAID_KEY; a transport/auth failure is surfaced, never fabricated context.
    query = str(args.get("query") or "")
    namespace = str(args.get("namespace") or "hipaa")
    # The KB catalog namespace is "hipaa" (also "medication-safety" / "clinical-escalation"). The
    # model sometimes passes the Pinecone INDEX name ("hipaa-compliancev2") or "DEFAULT" — both 400.
    # Normalize those to the working "hipaa" so the context aid doesn't fail on a name confusion.
    if namespace.lower() in {"hipaa-compliancev2", "default", ""}:
        namespace = "hipaa"
    top_k = int(args.get("top_k") or 3)
    if not query:
        return _error("kb_context needs a `query` (the topic or finding to ground in the KB).")
    try:
        chunks = ctx.kb_context(query=query, namespace=namespace, top_k=top_k)
    except Exception as exc:  # noqa: BLE001 - transport/auth -> surface, never fabricate context
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"KB context retrieval failed for namespace {namespace!r}: {detail}. (The KB needs a "
            f"kb:read credential in the BFF env; this is read-only and never affects a verdict.)"
        )
    if not chunks:
        return _text(f"No KB context found in namespace {namespace!r} for {query!r}.")
    lines = []
    for i, ch in enumerate(chunks[:top_k], 1):
        text = (ch.get("text") or ch.get("chunk") or "").strip().replace("\n", " ")
        lines.append(f"[{i}] (score {ch.get('score')}) {text[:400]}")
    return _text(
        f"KB context from namespace {namespace!r} for {query!r} ({len(chunks)} hit(s)) — RETRIEVAL "
        f"ONLY, this does NOT change any verdict:\n" + "\n".join(lines)
    )


async def focus_artifact_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # CHATBIND-2: emit a pane-control DIRECTIVE so the conversation can OPEN + FOCUS the artifact
    # pane. $0/read-only — NO bound op, NO paid knob. An unknown tab (outside the 4-tab contract)
    # is REJECTED and surfaced, never emitted; the directive never carries a run or fires one.
    tab = str(args.get("tab") or "")
    if tab not in _ARTIFACT_TABS:
        return _error(
            f"Cannot focus the artifact pane on {tab!r}: the tab must be one of "
            f"{', '.join(_ARTIFACT_TABS)}. No pane directive was emitted."
        )
    ctx.emit(open_artifact_part(tab))
    return _text(
        f"Opened the artifact pane and focused the {tab!r} tab. The run-bearing tabs show the "
        f"latest $0 replay; a paid run stays the human's cost-confirmed action."
    )


async def show_case_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # CHATBIND-3 / NARR-CHAT-LOOP: emit an inline Case Summary card for a SPECIFIC case. $0/read —
    # NO bound op (the card self-fetches GET /v1/case?case_id=X), NO paid knob. ``case_id`` selects
    # the case (else the shared active case); the card carries it so it fetches X, not the agent's
    # seed (the confident-but-wrong live bug). An EXPLICIT case_id also updates ctx.active_case so a
    # same-turn run_eval defaults to the just-shown case (the chat↔UI active-case stays one thing).
    case_id = args.get("case_id") or ctx.active_case
    if args.get("case_id"):
        ctx.active_case = str(args["case_id"])
    ctx.emit(case_summary_part(ctx.default_agent, case_id))
    target = case_id or "the current evaluation's case"
    return _text(
        f"Showing case {target!r} for {ctx.default_agent!r} as a card — the transcript, the scribe "
        f"artifact, and any by-construction label. (If a case has no planted label it is an ingested "
        f"or clean case — say so honestly; do not call a clean/unlabeled case a planted defect.) "
        f"Open it to read the full case ($0)."
    )


async def list_cases_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # NARR-CHAT-LOOP: enumerate the active workspace's INGESTED corpus (the gradeable cases a user
    # dropped via ingest) so "show me the cases I can evaluate" surfaces the REAL corpus, not the
    # agent's single seed (the live decoupling bug). $0/read — the bound ctx.list_cases wraps GET
    # /v1/cases. Opens the Cases tab so the human SEES the corpus (a directive, not a card).
    try:
        res = ctx.list_cases()
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Could not list the cases: {detail}.")
    cases = res.get("cases") or []
    count = res.get("count") if res.get("count") is not None else len(cases)
    ctx.emit(open_artifact_part("corpus"))
    if not count:
        return _text(
            "0 ingested cases in this workspace yet — there's nothing to evaluate until you ingest "
            "some. Drop a JSON dump (ingest_cases) or pull a connector batch first, then ask again."
        )
    ids = ", ".join(str(c.get("case_id")) for c in cases if c.get("case_id"))
    no_ctx = [c.get("case_id") for c in cases if not c.get("has_context")]
    fidelity = (
        f" ({len(no_ctx)} have an EMPTY grading context and would grade blind — re-ingest them)"
        if no_ctx
        else ""
    )
    return _text(
        f"{count} ingested case(s) you can evaluate{fidelity}: {ids}. They're unlabeled by "
        f"construction (the dump is the system's output, not gold). I opened the Cases tab — say "
        f"\"open case <id>\" to explore one, or \"run case <id>\" for a $0 replay verdict."
    )


async def propose_live_run_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # CHATBIND-4: emit a $0 DIRECTIVE that opens the in-DOM CostModal so the HUMAN can authorize a
    # live/in-process run. The agent NEVER fires the run — propose_live_run_part carries no paid
    # knob and the shell only OPENS the modal; confirmPaidRun (the human's confirm click) is the
    # SOLE paid path. This is the A-SAFE-preserving hand-off, not a paid tool.
    ctx.emit(propose_live_run_part())
    return _text(
        "I've surfaced the cost-confirm. A live in-process council run makes real (paid) model "
        "calls, so it's your authorization — confirm it in the modal to run. I cannot fire a paid "
        "run myself; a $0 replay is the most I can do directly."
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
        "Read a judge's config + derived questions AND surface the JudgeEditor card ($0, no "
        "write). The card carries the OPTIMIZE button — the calibration trainer (a cost-confirmed "
        "paid DSPy tune the HUMAN authorizes; you can't optimize, you surface the card + its honest "
        "held-out Δ). Use it to show a judge, set up its lens, or hand off calibration (Act 3).",
        GET_JUDGE_SCHEMA,
    ),
    (
        run_eval_handler,
        "run_eval",
        "Run a $0 REPLAY evaluation and render the verdict card. Pass case_id to grade a SPECIFIC "
        "ingested case (from list_cases); omit it to grade the case the human is exploring. REPLAY "
        "ONLY — this tool can never fire a paid (live/in-process) run; a paid run is the human's "
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
    (
        assemble_agent_handler,
        "assemble_agent",
        "Edit an agent's JUDGES ROSTER (audited config write): add_judge or remove_judge "
        "ONE known judge role. It does NOT build an agent from scratch or accept a full "
        "agent dict; an unknown role is rejected — surface the error, do not retry blindly.",
        ASSEMBLE_AGENT_SCHEMA,
    ),
    (
        delete_judge_handler,
        "delete_judge",
        "REVERT a judge to its DEFAULT lens (remove its authored config; an audited config "
        "write). Reversible — re-author any time. It reverts a KNOWN judge role only; it "
        "CANNOT delete an agent (human-only) or fire a paid run. An unknown role is rejected "
        "— surface the error, do not retry blindly.",
        DELETE_JUDGE_SCHEMA,
    ),
    (
        create_flag_handler,
        "create_flag",
        "CREATE a NEW reference (non-gradeable) flag in the agent's ontology (an audited config "
        "write). Reference flags are grounding-skip-logged, never scored. It CANNOT create a "
        "gradeable/scoreable flag — that requires a lithrim-backend re-snapshot. 409 if the code "
        "already exists (edit it via author_flag) — surface the error, do not retry blindly.",
        CREATE_FLAG_SCHEMA,
    ),
    (
        delete_flag_handler,
        "delete_flag",
        "DELETE a REFERENCE (non-gradeable) flag from the agent's ontology (an audited config "
        "write; reversible — re-create any time). It deletes only an UNUSED reference flag; a "
        "gradeable/in-snapshot contract code, or one a judge assigns or a case emits, is refused "
        "(422) — surface the error, do not retry blindly.",
        DELETE_FLAG_SCHEMA,
    ),
    (
        focus_artifact_handler,
        "focus_artifact",
        "Open + focus the artifact side-panel on a tab (case | report | judges | config | corpus) "
        "to SHOW your work ($0, read-only — emits a UI directive, never a paid run). Pair it with "
        "the relevant card: 'case' shows the source input; after a verdict/run-review focus judges "
        "or report; after a config/judge/flag change focus config; for the corpus/flywheel focus "
        "corpus. An unknown tab is rejected — surface it, do not retry blindly.",
        FOCUS_ARTIFACT_SCHEMA,
    ),
    (
        list_cases_handler,
        "list_cases",
        "LIST the cases the human can evaluate — the active workspace's INGESTED corpus ($0, "
        "read-only; opens the Cases tab). Use it whenever they ask 'what cases are there', 'show "
        "me the cases I can evaluate', or 'load all cases'. It enumerates the REAL corpus (every "
        "case_id), NOT the agent's single seed case. The cases are unlabeled by construction. No "
        "params. Then use show_case(case_id=…) to open one or run_eval(case_id=…) to grade it.",
        LIST_CASES_SCHEMA,
    ),
    (
        show_case_handler,
        "show_case",
        "Show a SPECIFIC source case as an inline Case Summary card ($0, read-only) — the "
        "transcript, the artifact, and any by-construction label. Pass case_id to open THAT case "
        "(get the id from list_cases); omit it to show the case the human is currently exploring. "
        "Use it when they want to SEE or explore a case BEFORE running. The card's 'View case' "
        "opens the full Case tab. NEVER claim you opened a case_id you did not pass; describe a "
        "clean/unlabeled case as clean, not as a planted defect.",
        SHOW_CASE_SCHEMA,
    ),
    (
        propose_live_run_handler,
        "propose_live_run",
        "Surface the cost-confirm modal so the HUMAN can authorize a LIVE (paid, in-process) "
        "council run — use it when they want the real verdict (not a $0 replay), e.g. on a case "
        "with no replay baseline. You only PROPOSE: this opens the modal; the human's confirm is "
        "the only thing that spends. You can NEVER fire a paid run yourself. No params.",
        PROPOSE_LIVE_RUN_SCHEMA,
    ),
    (
        add_grounding_contract_handler,
        "add_grounding_contract",
        "ADD a grounding (verification) contract to the agent's ontology for a flag (an audited "
        "config write; the step-5 'add grounding contracts' move). Shape: {flag_code, contract_type, "
        "params, [question], [version]}. Replaces an existing contract for the same flag, else appends. "
        "Canonical contract_types: snomed_subsumption (SNOMED code subsumption via Hermes), "
        "record_presence, presence_check. (For HIPAA-KB grounding, prefer the read-only kb_context "
        "aid — KB-as-suppress over-clears these flags.) $0 — never a paid run. A malformed contract or "
        "unknown flag is rejected (422/404) — surface it, do not retry blindly.",
        ADD_GROUNDING_CONTRACT_SCHEMA,
    ),
    (
        kb_context_handler,
        "kb_context",
        "Retrieve the relevant HIPAA knowledge-base section(s) for a topic or a finding and SHOW "
        "them as CONTEXT — the honest 'what does the policy actually say' aid. Args: {query, "
        "[namespace], [top_k=3]}. LEAVE namespace unset (defaults to 'hipaa'); the only valid "
        "namespaces are 'hipaa' (default), 'medication-safety', 'clinical-escalation' — do NOT pass "
        "the index name 'hipaa-compliancev2'. $0, READ-ONLY — it retrieves and displays; it NEVER "
        "changes a verdict or clears a finding. Use it to ground a discussion in the source policy.",
        KB_CONTEXT_SCHEMA,
    ),
    (
        ingest_cases_handler,
        "ingest_cases",
        "INGEST eval cases from a JSON dump of an AI system's output (the 'eval anything' move): "
        "generate a JUTE transform behind the scenes, live-gate it on the :3031 mapper, apply it, "
        "PIN the mapping, and upsert the extracted cases into the workspace corpus (one audit "
        "record). Shape: {json, [extraction_rules], [agent]}. The extracted cases are UNLABELED by "
        "construction (the dump is the SUT input, not gold). $0/BYO-key — never a paid run; the "
        "extractor is ingestion-only and never touches the grade-time floor. A structural-invariant "
        "failure (a mis-join → null → rejected) or a :3031-down path surfaces an error and pins "
        "NOTHING — surface it, refine the rules, do not retry blindly.",
        INGEST_CASES_SCHEMA,
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
