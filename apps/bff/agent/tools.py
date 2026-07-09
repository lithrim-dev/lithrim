"""The CORE SDK-MCP tools (UAP-5b D3): the 2-3 tool spine the conversation drives.

Each tool is a THIN wrapper over an EXISTING BFF op (FROZEN — wrapped, never
modified). The wrappers run inside the BFF process, so every config write goes
through the same audited path the click-driven UI uses (R0 — the conversation IS
the audit log). The CORE set (D-A, resolved at plan-review):

    author_judge -> the audited PUT /v1/judges/{role} logic (owner<->emit + snapshot
                    + validator-ref gates INTACT — a bad assignment 422s and the
                    agent SURFACES it, never bypasses).
    get_judge    -> the $0 GET /v1/judges/{role} preview (read-only).
    run_eval     -> GRADE A CASE FRESH (RUN-EVAL-FRESH-1). The A-SAFE crux: this tool's
                    input schema has NO confirm/in_process/live field and the handler
                    SURFACES THE COST-CONFIRM directive (it fires no op at all), so the
                    AGENT HAS NO PATH TO A PAID RUN. A paid run is 100% the human's in-DOM
                    modal-confirm calling the existing confirm-gated endpoint. The agent
                    proposes; only the human spends. (It no longer routes to the stale $0
                    replay — that resolved a fixed pre-calibration stored run.)

The handler bodies + schemas here are SDK-FREE (no claude_agent_sdk import) so the
A-SAFE / audited-write tests exercise them without the SDK. ``build_sdk_tools``
lazy-wraps them with the SDK ``@tool`` decorator (import-isolation, A5).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .adapter import (
    agent_part,
    audit_part,
    case_summary_part,
    contract_builder_part,
    criterion_builder_part,
    criterion_jute_builder_part,
    flag_part,
    judge_builder_part,
    judge_part,
    open_artifact_part,
    propose_live_run_part,
    propose_run_all_part,
    tool_builder_part,
)
from .assist import suggest_contract_params

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
    # CRITERION-TEXT-1: the criterion TEXT is authorable — when_to_use is the field the
    # judge-prompt bridge renders (the AUTHORED REFINEMENT lens line), so rewording it IS
    # the calibration move. Omitted → untouched (never clobbered); still no paid knob.
    "definition": str,
    "when_to_use": str,
    "when_NOT_to_use": str,
    "rationale": str,
}
# RUN-TRAIL-CASE-SCOPE: case_id is a SELECTOR (the RUN_EVAL_SCHEMA precedent), never a
# paid knob — it scopes the $0 read to the case the human named (exact id).
REVIEW_RUNS_SCHEMA: dict[str, Any] = {"limit": int, "case_id": str}
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
# RUN-ALL-1: propose_run_all takes NO params — it asks the shell to open the cohort cost-confirm.
# The agent PROPOSES; the human's modal-confirm grades all cases. No paid knob, nothing to smuggle.
PROPOSE_RUN_ALL_SCHEMA: dict[str, Any] = {}
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
# FAUTH-1 (G1) — SURFACE the ContractBuilder INPUT widget inline (the conversational-first
# "author a grounding contract by filling a card in the chat" move). It is a $0 SURFACE tool —
# the mirror of get_judge (which surfaces JudgeEditor): it emits the builder seeded with the
# in-context flag_code, and the HUMAN's Save (the widget's existing putGroundingContract) is the
# only write. It performs NO write itself — NO PAID_KEY (the A-SAFE test asserts this generically).
# FAUTH-3 (G2, the ASSIST keystone): OPTIONAL prose->params seeds — suggested_params (a deterministic
# draft the agent proposes) + source_hint (the chart path the agent lifts from the prose; the handler
# builds the matching skeleton from it via assist.suggest_contract_params when suggested_params is
# omitted) + question. S-BS-143: contract_type is the agent-chosen DIRECTION — value_presence (FLOOR,
# injects a BLOCK on an absent required value; flips APPROVE→BLOCK) vs presence_check (SUPPRESS, default).
# All DRAFT seeds for the EDITABLE card; the handler stays emit-only and the human's Save remains the
# sole audited write (still NO PAID_KEY, still no write op).
AUTHOR_CONTRACT_SCHEMA: dict[str, Any] = {
    "flag_code": str,
    "contract_type": str,
    "suggested_params": dict,
    "source_hint": str,
    "question": str,
}
# TOOL-AUTHOR-1 — SURFACE the ToolBuilder inline so the HUMAN declares a kind:tool connector (an
# MCP server / API connector / KB / terminology service) by filling a card. EMIT-ONLY: the card's
# Save rides POST /v1/tools (the audited writer); the agent NEVER declares the tool itself (no
# PAID_KEY — the A-SAFE sweep asserts this). All fields optional DRAFT seeds for the editable card.
AUTHOR_TOOL_SCHEMA: dict[str, Any] = {
    "id": str,
    "implements": str,
    "transport": str,
}
# NARR-5-CRIT-b — SURFACE the CriterionBuilder inline so the HUMAN mints a new GRADEABLE criterion
# (code + tier + owner) by filling a card. EMIT-ONLY: the card's Save rides POST /v1/criterion (the
# sanctioned snapshot writer); the agent never mints a code itself (the containment the holistic
# critic praised). NO PAID_KEY. All fields optional (defaulted/empty seed; the card's own validation
# + the server-side gate enforce shape/owner/tier at Save).
AUTHOR_CRITERION_SCHEMA: dict[str, Any] = {
    "code": str,
    "tier": str,
    "owner_role": str,
    "definition": str,
    # CRITERION-TEXT-1: the agent may DRAFT the criterion text into the card seed; the
    # human's Save on the card remains the SOLE write (the SPINE/CONTAINMENT invariant).
    "when_to_use": str,
    "when_NOT_to_use": str,
}
# PHASE2-WIRE — SURFACE the JudgeBuilder inline so the HUMAN mints a NEW judge ROLE (a new council
# voice) over the active pack's taxonomy snapshot by filling a card (role id + lens + owned + model
# + role prompt). The SEED is the role id ONLY — the agent never composes the snapshot write; the
# card's own "Create judge" Save rides POST /v1/judges (the sanctioned snapshot writer). EMIT-ONLY,
# NO PAID_KEY (the A-SAFE sweep asserts this). Distinct from AUTHOR_JUDGE_SCHEMA (assign a lens to an
# EXISTING role); this CREATES a new role via the card.
CREATE_JUDGE_SCHEMA: dict[str, Any] = {"role": str}
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
# META-VERDICT-1 — RECORD a clinician's INDEPENDENT verdict + judge meta-audit on a run
# (Clinical Scribe Review Layer-3, the HITL clinical validator). An audited $0 WRITE: the human's pass/fail,
# whether they AGREE with the council, and — on dissent — the judge's named fallacy (a CLOSED enum:
# Hallucination Blindness | Reference Bias | Metric Conflation | Risk-Severity Blindness | Boundary
# Violation; an out-of-enum code is rejected). NO PAID_KEY — recording an attestation is not a grade.
RECORD_META_VERDICT_SCHEMA: dict[str, Any] = {
    "run_id": str,
    "human_verdict": str,
    "agrees_with_council": bool,
    "judge_fallacy_code": str,
    "rationale": str,
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
    - ``author_flag(flag_code, tier, gradeable, definition, when_to_use, when_NOT_to_use,
      rationale) -> dict``  (UAP-5c Flag + CRITERION-TEXT-1; an audited ontology edit of an
      EXISTING flag incl. its criterion text; raises on 404/422 — the handler surfaces it)
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
    - ``record_meta_verdict(run_id, human_verdict, agrees_with_council, judge_fallacy_code,
      rationale) -> dict``  (META-VERDICT-1: the clinician's INDEPENDENT verdict + judge meta-audit
      — Clinical Scribe Review Layer-3. An audited $0 WRITE of one immutable AuditRecord (action=meta_verdict,
      target=verdict/run_id). An out-of-enum judge_fallacy_code raises (surfaced). Never a paid run.)
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
    record_meta_verdict: Callable[..., dict]
    default_agent: str = "ws0_default"
    active_case: str | None = None
    # GROUNDED-EXPLAIN-1: a request-context case loader (case_id -> raw case dict with
    # transcript/context + artifacts + expected_safety_flags), bound by the BFF so the chat's
    # "what's wrong with this case" answer grounds in the real artifact + gold. Optional — a ctx
    # built without it (or a test stub) degrades to no artifact injection.
    load_case_full: Callable[..., dict] | None = None
    # CHAT-CASE-TOKEN-RESOLVE: the agent's known case ids (the SAME source that backs
    # GET /v1/cases/browser — pinned source ⊕ pack fixtures ⊕ ingested corpus), so the chat/tool
    # layer can map a SHORT/PREFIX token a user typed ("cv_mts_002") to the UNIQUE full case_id
    # BEFORE the exact-match GET /v1/runs query. Optional — a ctx built without it (or a test stub)
    # degrades to today's exact-match pass-through (the shared endpoint query is never loosened).
    known_case_ids: Callable[..., list[str]] | None = None
    # CE-INGEST-FRONTDOOR-1: the first-class data front door — decode (JSON/JSONL/CSV) then the
    # human-in-the-loop PREVIEW (select/gen a template + apply, pin + write NOTHING) -> COMMIT (pin
    # the approved template + upsert). Optional — a ctx built without them (or a test stub) simply
    # has no front door; the chat ``ingest_cases`` path is unaffected.
    ingest_preview: Callable[..., dict] | None = None
    ingest_commit: Callable[..., dict] | None = None
    parts: list[dict] = field(default_factory=list)
    run_results: list[dict] = field(default_factory=list)

    def emit(self, part: dict) -> None:
        self.parts.append(part)

    def emit_run(self, record: dict) -> None:
        """CHATBIND-2 (D4): stash a $0 REPLAY record so the loop LIFTS it into the shell's shared
        ``runResult`` (the run-bearing Report/Judge tabs render it). The record is byte-same to the
        manual Run-eval result. RUN-EVAL-FRESH-1 retired the "run eval" -> $0 replay route, so no
        live handler calls this today; the lift channel is retained for a future EXPLICIT replay
        tool. It only ever carries a $0 replay record, so no paid path is ever lifted."""
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
    # RUN-EVAL-FRESH-1: "run / grade / evaluate / run eval [a case]" must produce a FRESH grade, not
    # a stale $0 replay. The prompt-only routing (CHAT-FRESH-GRADE-1) failed — the model grabs run_eval
    # for the words "run eval." So make it deterministic AT THE HANDLER: run_eval now SURFACES the
    # cost-confirm (the propose_live_run directive) for a FRESH live grade of the named/active case —
    # whichever tool the model picks (run_eval OR propose_live_run), the result is one fresh, cost-
    # confirmed grade, never the stale stored replay (which had been resolving a fixed pre-calibration
    # run, e.g. 6649be3a -> a frozen wrong REJECT while "run live" graded fresh -> PASS).
    #
    # A-SAFE: the agent STILL cannot spend. This emits the DIRECTIVE only — NO op runs here; the
    # human's in-DOM cost-confirm (confirmPaidRun -> runEval(in_process,confirm)) is the SOLE spend.
    # The schema stays paid-knob-free; any injected confirm/in_process/live is simply ignored (no op
    # is reached). ``ctx.run_eval_replay`` (the bound $0 op) is intentionally NOT called from this
    # route — it is retained for a future explicit replay tool, just no longer how "run eval" routes.
    case_id = args.get("case_id")
    if case_id:
        # Mirror show_case_handler: an EXPLICIT case_id updates the shared active case so the FRESH
        # grade the human confirms (confirmPaidRun runs runEval(case_id=activeCase)) targets it.
        ctx.active_case = str(case_id)
    target = ctx.active_case or "the current evaluation's case"
    # CHAT-CASE-TARGET-1: carry the targeted case on the directive so the shell grades the case the
    # chat NAMED (confirmPaidRun targets it), not the stale client top-bar selection. A SELECTOR,
    # not a spend — the human's in-DOM confirm is still the SOLE paid path.
    ctx.emit(propose_live_run_part(ctx.active_case))  # surface the cost-confirm (the propose_live_run door)
    return _text(
        f"Surfaced the cost-confirm for a FRESH live grade of {target!r} — confirm in the modal to "
        f"run it (a $0 replay of a stored run is no longer the default; the verdict you see must be "
        f"fresh). I can't fire a paid run myself; your confirm authorizes it."
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
    # The Flag leg (audited WRITE): edit an EXISTING flag's tier/gradeable/criterion-text
    # (CRITERION-TEXT-1). Never creates a flag or invents owner_roles; an out-of-snapshot
    # gradeable edit 422s and is surfaced. Omitted fields stay untouched (None ≠ clear).
    flag_code = str(args.get("flag_code") or "")
    tier = args.get("tier")
    gradeable = args.get("gradeable")
    rationale = str(args.get("rationale") or "edited via the conversational shell")
    try:
        res = ctx.author_flag(
            flag_code=flag_code, tier=tier, gradeable=gradeable, rationale=rationale,
            definition=args.get("definition"),
            when_to_use=args.get("when_to_use"),
            when_NOT_to_use=args.get("when_NOT_to_use"),
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


def _verdict_narration(
    verdict: Any, grounded_verdict: Any, floor_suppressed: Any
) -> str:
    """RUN-TRAIL-CASE-SCOPE: narrate BOTH verdict layers whenever they differ — never
    quote the pre-floor council verdict alone (the 2026-07-04 live defect narrated
    "verdict=BLOCK" on a floor-cleared clean case whose grounded_verdict was PASS).
    Agreeing (or single-known-layer / legacy) rows narrate one verdict, grounded
    preferred."""
    v = str(verdict or "").strip()
    g = str(grounded_verdict or "").strip()
    if not v or not g or v.upper() == g.upper():
        return f"verdict={g or v or '—'}."
    n = int(floor_suppressed or 0)
    council = (
        f"council flagged ({v})"
        if v.upper() in ("BLOCK", "WARN", "REJECT")
        else f"council said {v}"
    )
    floor = (
        f"the grounding floor cleared {n} false alarm{'' if n == 1 else 's'}"
        if n
        else "the grounding floor overrode it"
    )
    return f"{council}; {floor}; final: {g}."


def _resolve_case_token(
    token: str | None, known_ids: list[str]
) -> tuple[str | None, str | None]:
    """CHAT-CASE-TOKEN-RESOLVE — map a SHORT/PREFIX case token a user typed to the UNIQUE full
    case_id, in the CHAT/TOOL layer (NEVER by loosening the exact-match GET /v1/runs query the
    replay-baseline resolver depends on). Returns ``(resolved_id, ambiguity_note)``:

    * exact known id → ``(token, None)`` (wins outright);
    * unique PREFIX of exactly ONE known id → ``(full_id, None)``;
    * matches MULTIPLE known ids → ``(None, "<honest note listing the matches>")`` — do NOT
      guess a scope; stay UNSCOPED and let the caller narrate the ambiguity;
    * matches ZERO → ``(token, None)`` — today's honest-empty behavior (the exact-match query
      returns 0 runs, unchanged);
    * no token / empty known list → the token passes through unchanged.

    A PREFIX (not an arbitrary substring): case ids are hierarchical (``cv_mts_002_…``), so a
    typed prefix is the natural short form; an arbitrary-substring match would silently over-hit
    and pick a wrong scope. Pure — no I/O, never raises."""
    tok = (token or "").strip() or None
    if tok is None or not known_ids:
        return tok, None
    if tok in known_ids:
        return tok, None
    prefix_hits = [cid for cid in known_ids if cid.startswith(tok)]
    if len(prefix_hits) == 1:
        return prefix_hits[0], None
    if len(prefix_hits) > 1:
        note = (
            f"{tok!r} matches {len(prefix_hits)} cases: "
            + ", ".join(sorted(prefix_hits))
            + " — which one?"
        )
        return None, note
    return tok, None


async def review_runs_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # The Review leg ($0 read): run history + the latest run's provenance + the config
    # audit trail (rendered by AuditView). No paid surface. case_id (RUN-TRAIL-CASE-SCOPE)
    # scopes the read to the case the human named — latest = that case's latest run.
    limit = args.get("limit")
    case_id = str(args.get("case_id") or "").strip() or None
    # CHAT-CASE-TOKEN-RESOLVE — resolve the case to scope to, in the TOOL layer, BEFORE the
    # exact-match GET /v1/runs query (the shared endpoint semantics stay EXACT — the replay
    # baseline resolver depends on it). Precedence: an ARMED case (ctx.active_case, a known full
    # id) WINS over a typed short token; else map a short/prefix token to the UNIQUE full id.
    ambiguity_note: str | None = None
    known_ids = []
    if ctx.known_case_ids is not None:
        try:
            known_ids = [c for c in (ctx.known_case_ids() or []) if c]
        except Exception:  # noqa: BLE001 — a known-case read must never break the $0 read
            known_ids = []
    armed = (ctx.active_case or "").strip() or None
    if armed and armed in known_ids:
        case_id = armed  # armed beats typed
    elif case_id and known_ids:
        case_id, ambiguity_note = _resolve_case_token(case_id, known_ids)
    try:
        kwargs: dict[str, Any] = {"limit": int(limit) if limit else 5}
        if case_id:
            kwargs["case_id"] = case_id
        res = ctx.review_runs(**kwargs)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Could not read run history: {detail}.")
    runs = res.get("runs") or []
    latest = res.get("latest_run_id") or ""
    scoped_case = res.get("case_id") or case_id
    ctx.emit(audit_part(latest, case_id=scoped_case))
    latest_audit = res.get("latest_audit") or {}
    head = runs[0] if runs else {}
    verdict_line = _verdict_narration(
        latest_audit.get("verdict") or head.get("verdict"),
        latest_audit.get("grounded_verdict") or head.get("grounded_verdict"),
        head.get("floor_suppressed"),
    )
    scope = f" for case {scoped_case!r}" if scoped_case else ""
    ask = f" {ambiguity_note}" if ambiguity_note else ""
    return _text(
        f"{len(runs)} run(s) on record{scope}. Latest {latest[:8] or '—'}: {verdict_line} "
        f"The config-change audit trail (your flag + judge edits) and this run's "
        f"provenance are shown.{ask}"
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


async def author_contract_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # FAUTH-1 (G1): SURFACE the ContractBuilder INPUT widget inline, seeded with the in-context
    # flag_code + agent — the conversational-first "author a grounding contract by filling a card
    # in the chat" move. The mirror is get_judge_handler: it READS nothing and WRITES nothing — it
    # only ctx.emit(...) the input card + returns guidance text. The widget's own
    # putGroundingContract (the human's Save) is the SOLE audited write (add_grounding_contract is
    # the agent-composes twin; this is the human-authors surface alongside it). $0, no PAID_KEY,
    # surfaces-not-spends. ``flag`` is accepted as an alias for ``flag_code`` (the model often
    # reaches for the shorter name); an omitted/blank flag opens an empty card (the widget's own
    # validation gates Save, R5).
    flag_code = str(args.get("flag_code") or args.get("flag") or "")
    # FAUTH-3 (G2, the ASSIST keystone) + FAUTH-3a (the reliability fix): prose->params seeds. An
    # explicit suggested_params (the agent's composed draft) wins; otherwise, for a NAMED flag, the
    # handler DEFAULT-fills the DETERMINISTIC skeleton (correct KEYS by construction, not LLM-
    # hallucinated) via the pure helper — so the pre-fill does NOT depend on the live agent remembering
    # to pass source_hint (A-LIVE showed it doesn't). source_hint, when given, sets the skeleton's
    # source path. No flag yet (the "name the flag first" empty card) → no pre-fill. All are DRAFT
    # seeds for the EDITABLE card; this handler stays EMIT-ONLY (it calls NO bound write op); the
    # human's Save (putGroundingContract) remains the sole audited write, so the assist never
    # auto-writes the ontology and never enters ground() (the spine invariant).
    # S-BS-143: contract_type is the agent-chosen DIRECTION — value_presence (FLOOR, can flip
    # APPROVE→BLOCK) vs presence_check (SUPPRESS, the historical default). suggest_contract_params
    # routes to the matching skeleton; an empty/unknown type falls back to presence_check (byte-
    # identical to the prior behavior). The chosen type rides into the part so the card opens on it.
    # NB: the SDK-MCP layer passes an EMPTY dict {} for an omitted dict-typed param (not None), so
    # `{}` must be treated as "no suggestion" — else a real named-flag call (suggested_params={})
    # would skip the default-fill and the card would show the inert default (the A-LIVE bug).
    contract_type = str(args.get("contract_type") or "").strip()
    _raw = args.get("suggested_params")
    suggested = _raw if (isinstance(_raw, dict) and _raw) else None
    source_hint = str(args.get("source_hint") or "").strip() or None
    if suggested is None and flag_code:
        suggested = suggest_contract_params(contract_type, flag_code, source_hint=source_hint)
    question = str(args.get("question") or "")
    ctx.emit(
        contract_builder_part(
            ctx.default_agent,
            flag_code,
            suggested_params=suggested,
            question=question,
            contract_type=contract_type,
        )
    )
    # CRITERION-JUTE-1d: for a TOOL-GROUNDED (mcp_call) flag, ADDITIONALLY surface the
    # CriterionJuteBuilder inline — the "pick a tool+call, seed generation with a plain-English
    # criterion, gate over the corpus, pin on pass" surface. EMIT-ONLY (like the contract card): the
    # human's "Pin" is the sole audited write, gated on the corpus gate passing. The tool prose from
    # suggested_params (tool/call) seeds the picker when present. This is a part-builder, NOT a new
    # _TOOL_SPECS entry — the tool-count is unchanged.
    if contract_type == "mcp_call":
        _sp = suggested or {}
        ctx.emit(
            criterion_jute_builder_part(
                ctx.default_agent,
                flag_code=flag_code,
                tool=str(_sp.get("tool") or ""),
                call=str(_sp.get("call") or ""),
                criterion=question or str(_sp.get("criterion") or ""),
            )
        )
    seeded = " (pre-filled with a suggested draft you can edit)" if suggested else ""
    return _text(
        f"Surfaced the contract builder inline, pre-bound to flag "
        f"{flag_code or '(none yet — name the flag in the card)'} on agent "
        f"{ctx.default_agent!r}{seeded}. Fill in / adjust the deterministic verification contract "
        f"(claim → tool-query → verdict) and Save — the Save IS the audited write (the floor then "
        f"runs at grade time over this flag). I only surface the card and propose a draft; I do not "
        f"author the contract for you, and this is $0 (never a paid run)."
    )


async def author_tool_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # TOOL-AUTHOR-1: SURFACE the ToolBuilder INPUT widget inline, seeded with any in-context
    # id/implements/transport — the conversational "declare an MCP/API tool by filling a card" move
    # (the mirror of author_contract). EMIT-ONLY by design (SPINE/CONTAINMENT): this calls NO bound
    # write op; the card's Save rides POST /v1/tools (the audited writer). The agent declares a
    # CONNECTOR, never uploads code — custom execution stays behind the user's own transport
    # boundary (SPEC_TOOL_AUTHORING §1). NO PAID_KEY, $0, surfaces-not-spends.
    seed = {k: str(args.get(k)) for k in ("id", "implements", "transport") if args.get(k)}
    ctx.emit(tool_builder_part(ctx.default_agent, seed=seed or None))
    return _text(
        "Surfaced the tool builder inline. Declare a kind:tool connector (an MCP server, API "
        "connector, KB, or terminology service) + optionally bind it to a flag, then Save — the "
        "Save IS the audited write (POST /v1/tools), and the tool then resolves at grade time for "
        "this workspace. I only surface the card; I never declare the tool or run it. This is $0."
    )


async def author_criterion_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # NARR-5-CRIT-b: SURFACE the CriterionBuilder INPUT widget inline, seeded with the in-context
    # code/tier/owner_role + agent — the conversational "mint a new gradeable criterion by filling a
    # card" move (the mirror of author_contract). EMIT-ONLY by design (the SPINE/CONTAINMENT
    # invariant the holistic critic praised): this calls NO bound write op; the card's Save rides the
    # sanctioned snapshot writer POST /v1/criterion (which gates tier:core + owner ∈ production_judges
    # + code shape + dup, and audits) — the HUMAN's Save is the SOLE write of the contract-of-record.
    # The agent never mints a code itself. $0, no PAID_KEY. All seeds are optional DRAFTs for the
    # editable card; an empty seed opens an empty card (the card's own validation gates Save).
    code = str(args.get("code") or "")
    tier = str(args.get("tier") or "")
    owner_role = str(args.get("owner_role") or "")
    ctx.emit(
        criterion_builder_part(
            ctx.default_agent, code=code, tier=tier, owner_role=owner_role,
            definition=str(args.get("definition") or ""),
            when_to_use=str(args.get("when_to_use") or ""),
            when_NOT_to_use=str(args.get("when_NOT_to_use") or ""),
        )
    )
    return _text(
        f"Surfaced the criterion builder inline on agent {ctx.default_agent!r}"
        f"{f' (seeded {code}/{tier}/{owner_role})' if code else ''}. Choose the code, tier, and "
        f"owning judge, then Save — your Save is the SOLE write (POST /v1/criterion mints the "
        f"gradeable criterion into the pack's taxonomy snapshot + ontology, audited). I only surface "
        f"the card; I do not mint the criterion for you, and this is $0 (never a paid run)."
    )


async def create_judge_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # PHASE2-WIRE: SURFACE the JudgeBuilder INPUT widget inline, seeded with the in-context role id +
    # agent — the conversational "create a NEW judge role by filling a card" move (the mirror of
    # author_criterion). EMIT-ONLY by design (the SPINE/CONTAINMENT invariant): this calls NO bound
    # write op; the card's "Create judge" Save rides the sanctioned snapshot writer POST /v1/judges
    # (which gates role shape + owner↔emit + code∈taxonomy + role collision + tier:core pack, and
    # audits) — the HUMAN's Save is the SOLE write of the new council voice. The agent never mints the
    # judge itself. $0, no PAID_KEY. The role seed is optional; an omitted role opens an empty card
    # (the card's own validation gates Save). Distinct from author_judge (which ASSIGNS a lens to an
    # EXISTING role); this CREATES a new role over the snapshot.
    role = str(args.get("role") or "")
    ctx.emit(judge_builder_part(ctx.default_agent, role=role))
    return _text(
        f"Surfaced the create-judge card inline on agent {ctx.default_agent!r}"
        f"{f' (seeded role {role})' if role else ''}. Fill in the lens (the codes this judge may "
        f"raise), any owned codes (⊆ lens), the model, and an optional role prompt, then click "
        f"Create judge — your Save is the SOLE write (POST /v1/judges mints the NEW judge role into "
        f"the active pack's taxonomy snapshot, owner↔emit + snapshot gated, audited). I only surface "
        f"the card; I do NOT mint the judge for you, and this is $0 (never a paid run). To ASSIGN a "
        f"lens to an EXISTING role instead, use author_judge."
    )


async def record_meta_verdict_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # META-VERDICT-1 (audited WRITE): record the clinician's INDEPENDENT verdict + judge meta-audit
    # on a run — Clinical Scribe Review Layer-3 (the HITL clinical validator). $0, no PAID_KEY. The bound
    # ctx.record_meta_verdict validates at the model boundary (an out-of-enum judge_fallacy_code or
    # human_verdict raises) and writes one immutable AuditRecord; a failure is SURFACED exactly as
    # add_grounding_contract surfaces 404/422 — never bypassed, never a paid run.
    run_id = str(args.get("run_id") or "")
    human_verdict = str(args.get("human_verdict") or "")
    raw_agree = args.get("agrees_with_council")
    agrees = (
        raw_agree
        if isinstance(raw_agree, bool)
        else str(raw_agree).strip().lower() in ("true", "1", "yes")
    )
    # an empty/blank fallacy code -> None (the agreeing path carries no fallacy).
    fallacy = (str(args.get("judge_fallacy_code") or "").strip()) or None
    rationale = str(args.get("rationale") or "")
    try:
        ctx.record_meta_verdict(
            run_id=run_id,
            human_verdict=human_verdict,
            agrees_with_council=agrees,
            judge_fallacy_code=fallacy,
            rationale=rationale,
        )
    except Exception as exc:  # ValidationError (out-of-enum) / HTTPException / anything raised
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not record the clinician meta-verdict for run {run_id!r}: {detail}. Nothing was "
            f"recorded. human_verdict must be 'pass'/'fail'; judge_fallacy_code (only on dissent) "
            f"must be one of the five named fallacies — surface the error, do not retry blindly."
        )
    # CONV-FIRST (SPEC_CONVERSATIONAL_FIRST §2): recording the dissent is complete IN THE
    # CONVERSATION — the clinician-verdict form lives inline on the verdict card, and this
    # closes with a narrated confirmation. Do NOT open the pane (the reversed anti-pattern):
    # the human opens the full report only on an explicit "show me the full report".
    return _text(
        f"Recorded the clinician meta-verdict for run {run_id!r}: human_verdict={human_verdict}, "
        f"agrees_with_council={agrees}, judge_fallacy={fallacy or 'none'}. The attestation is "
        f"immutable + audited (action=meta_verdict) — it adds to the record, it does not change the "
        f"verdict."
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
    except TimeoutError as exc:  # CE-INGEST-FASTFAIL: the bounded extractor did not converge in time
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(
            f"Could not ingest cases: {detail}. NOTHING was pinned or upserted. The extractor "
            f"couldn't converge to a valid case structure within the bound — simplify the "
            f"extraction rules, reduce the JSON dump, or name the join key explicitly (the "
            f"timeout is configurable via LITHRIM_INGEST_TIMEOUT), then retry."
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
    labeled = res.get("labeled") or 0
    mapping_id = res.get("mapping_id")
    ctx.emit(open_artifact_part("corpus"))
    # INGEST-LABELS-1 (honest report): state the ACTUAL labeled count — never claim a ground-truth
    # label landed when the source carried none / it was not mapped.
    label_note = (
        f" {labeled} of them carry your ground-truth labels (expected verdict / safety flags), so "
        f"accuracy + calibration can be scored."
        if labeled
        else " NONE carry ground-truth labels — the source had no expected_* fields for these case "
        "ids (or they weren't mapped), so they are UNLABELED (accuracy can't be scored; add "
        "expected_compliance_verdict / expected_safety_flags per source entry and re-ingest)."
    )
    return _text(
        f"Ingested {count} case(s) from the JSON dump for agent {agent!r} via pinned mapping "
        f"{mapping_id} — extracted, live-gated on :3031, PINNED, and upserted to the workspace "
        f"corpus (one audit record written; $0, no paid run).{label_note} Open the corpus tab to "
        f"review them, then author criteria + grade."
    )


async def kb_context_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # KB-CONTEXT-1 ($0/read-only): retrieve the relevant KB section(s) for a topic/finding and SHOW
    # them — the honest CONTEXT AID. It NEVER changes a verdict (retrieval-only; kb_grounding-as-
    # suppress over-clears on these flags, proven, so we surface context instead of clearing). No
    # PAID_KEY; a transport/auth failure is surfaced, never fabricated context.
    query = str(args.get("query") or "")
    # The default catalog namespace is deployment CONFIG (LITHRIM_KB_NAMESPACE), not a product
    # hardwire; "hipaa" stays the unset fallback for byte-compat with the reference deployment.
    default_ns = os.environ.get("LITHRIM_KB_NAMESPACE") or "hipaa"
    namespace = str(args.get("namespace") or default_ns)
    # The backing INDEX name is deployment config too (LITHRIM_KB_INDEX; generic default —
    # REL-5f: never a product hardwire). The model sometimes passes it (or "DEFAULT") instead
    # of a catalog namespace — both 400. Normalize to the configured namespace so the aid
    # doesn't fail on name confusion.
    kb_index = os.environ.get("LITHRIM_KB_INDEX") or "kb-index"
    if namespace.lower() in {kb_index.lower(), "default", ""}:
        namespace = default_ns
    top_k = int(args.get("top_k") or 3)
    if not query:
        return _error("kb_context needs a `query` (the topic or finding to ground in the KB).")
    try:
        chunks = ctx.kb_context(query=query, namespace=namespace, top_k=top_k)
    except (ConnectionError, OSError) as exc:
        # No KB service is connected (CE ships none) — say exactly that, so the agent reports
        # honestly instead of retry-looping (S-BS-91 family) or blaming credentials.
        return _error(
            "no knowledge base is connected (the KB service is unreachable). Connect one by "
            "setting LITHRIM_KB_BASE_URL to a KB search service, or answer from the conversation "
            f"and SAY the KB is not connected — do not retry. ({exc})"
        )
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
        f"The case {target!r} for {ctx.default_agent!r} is shown INLINE above — the visit transcript "
        f"and the scribe note are both in the card (compare what was said vs what was documented), plus "
        f"any by-construction label. Read it in the conversation; point out anything the note left out. "
        f"(If a case has no planted label it is an ingested or clean case — say so honestly; do not call "
        f"a clean/unlabeled case a planted defect.) Offer the raw/editable transcript only if asked."
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
    # CHAT-CASE-TARGET-1: carry the request's active case so a directly-proposed run targets the
    # case the human is on (the shell syncs + grades it), not a dropped/empty selector. SELECTOR,
    # not a spend — the schema stays param-free; only the human's confirm spends.
    ctx.emit(propose_live_run_part(ctx.active_case))
    return _text(
        "I've surfaced the cost-confirm. A live in-process council run makes real (paid) model "
        "calls, so it's your authorization — confirm it in the modal to run. I cannot fire a paid "
        "run myself; a $0 replay is the most I can do directly."
    )


async def propose_run_all_handler(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # RUN-ALL-1: emit a $0 DIRECTIVE that opens the in-DOM CostModal for the WHOLE ingested cohort.
    # The agent NEVER fires the batch — propose_run_all_part carries no paid knob and the shell only
    # OPENS the modal; the human's confirm (which calls POST /v1/cases/grade) is the SOLE paid path.
    # A-SAFE-preserving hand-off, identical posture to propose_live_run.
    ctx.emit(propose_run_all_part())
    return _text(
        "I've surfaced the cost-confirm for grading ALL ingested cases. A cohort run makes real "
        "(paid) model calls across every case, so it's your authorization — confirm it in the modal "
        "and I'll render the consolidated scorecard inline. I cannot fire the paid batch myself."
    )


# (handler, name, description, schema) — the spine. run_eval's description states the
# replay-only contract so the model does not try to request a paid run through it.
_TOOL_SPECS: list[tuple[Callable, str, str, dict]] = [
    (
        author_judge_handler,
        "author_judge",
        "ASSIGN a lens (ontology flag codes the judge may raise) to an EXISTING judge role — an "
        "audited config write. Use it to bind/adjust the lens of a role that already exists; it does "
        "NOT create a new role (for a NEW council voice use create_judge). Rejects (422) an off-lens "
        "/ off-snapshot assignment — surface the error, do not retry blindly.",
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
        "GRADE a case FRESH — this is THE way to run / grade / evaluate / run eval a case. It "
        "surfaces the cost-confirm modal for a real (paid) live council run on the case; the human's "
        "confirm spends. It does NOT replay a stored run (that stale-verdict replay was the bug). "
        "Pass case_id for a SPECIFIC ingested case (from list_cases) — it becomes the active case the "
        "fresh grade targets; omit it for the case the human is exploring. No paid knob — you only "
        "PROPOSE (surface the modal); the human authorizes the spend. (propose_live_run opens the "
        "same modal — both are the fresh-grade path.) NOT for an explicit '$0 replay / stored (last) "
        "result / for free / at no cost / don't spend / without spending or paying' ask — serve "
        "that with review_runs, the $0 read.",
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
        "EDIT AN EXISTING flag in the agent's ontology (audited config write): its tier/"
        "gradeable AND its criterion text (definition, when_to_use, when_NOT_to_use — "
        "when_to_use is the lens line the judge's prompt renders, so rewording it is the "
        "calibration move). Omitted fields stay untouched. It does NOT create a flag or "
        "invent owners; an out-of-snapshot gradeable edit is rejected (422) — surface the "
        "error, do not retry blindly.",
        AUTHOR_FLAG_SCHEMA,
    ),
    (
        review_runs_handler,
        "review_runs",
        "Review the run history, the latest run's STORED verdict/provenance, and the config-change "
        "audit trail ($0, no write) — THE way to serve an explicit '$0 replay', 'show the stored "
        "result', 'last result', 'for free / free of charge / at no cost', 'don't spend', 'without "
        "spending', or 'without paying' ask (never the cost-confirm modal; a $0 ask must never "
        "escalate to a paid proposal). Pass case_id whenever the human NAMES a case (exact id) — "
        "the history and the latest stored verdict then scope to THAT case, not whichever case was "
        "graded most recently. Use to show what was authored and what a run decided. If the "
        "read refuses (e.g. the config changed since the last grade), surface its message verbatim "
        "— never swallow it, never counter-propose a paid run unprompted.",
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
        "Show a SPECIFIC source case as an inline Case Summary card ($0, read-only) — the card "
        "renders the visit transcript AND the scribe note INLINE in the conversation (so the human "
        "compares what was said vs what was documented), plus any by-construction label. Pass case_id "
        "to show THAT case (get the id from list_cases); omit it to show the case the human is "
        "currently exploring. Use it when they want to SEE or explore a case BEFORE running, then read "
        "it together in the chat and point out anything the note omits. The case IS the inline card — "
        "do NOT direct the human elsewhere to read it (offer the raw/editable transcript on request "
        "only). NEVER claim you opened a case_id you did not pass; describe a clean/unlabeled case as "
        "clean, not as a planted defect.",
        SHOW_CASE_SCHEMA,
    ),
    (
        propose_live_run_handler,
        "propose_live_run",
        "The way to GRADE A CASE FRESH — the DEFAULT for 'run / grade / evaluate / run eval [this "
        "case|case X]'. It surfaces the cost-confirm modal; the human's confirm runs the fresh paid "
        "(live, in-process) grade. A fresh grade makes real (paid) model calls, so you only PROPOSE: "
        "this opens the modal, the human's confirm is the only thing that spends. You can NEVER fire "
        "a paid run yourself. (For an explicit '$0 replay / stored (last) result / for free / at no "
        "cost / don't spend / without spending or paying' ask, use review_runs — the $0 read — "
        "instead; never open this modal for a $0 ask.) No params.",
        PROPOSE_LIVE_RUN_SCHEMA,
    ),
    (
        propose_run_all_handler,
        "propose_run_all",
        "Grade ALL ingested cases at once — the DEFAULT for 'run all / grade all / run the whole "
        "suite / run every case / score the cohort'. It surfaces the cost-confirm modal; the human's "
        "confirm grades the full cohort and renders the consolidated scorecard (per-case caught/"
        "missed/spurious vs gold + precision/recall) INLINE in the chat. A cohort grade makes real "
        "(paid) model calls across every case, so you only PROPOSE: the human's confirm is the only "
        "thing that spends. You can NEVER fire it yourself. No params.",
        PROPOSE_RUN_ALL_SCHEMA,
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
        author_contract_handler,
        "author_contract",
        "SURFACE the interactive contract-authoring widget INLINE so the HUMAN authors a "
        "deterministic grounding (verification) contract by FILLING A CARD in the chat — the "
        "conversational-first authoring move ($0, read-only; the mirror of get_judge surfacing the "
        "JudgeEditor). Use it when the human wants to AUTHOR / define / set up a grounding contract "
        "or criterion themselves. Shape: {flag_code} — the flag to pre-bind the card to (from "
        "create_flag or named by the human). The human fills the contract_type/question/params and "
        "their Save is the audited write (you do NOT compose the contract). For the agent-composes "
        "path (you already know the contract_type + params), use add_grounding_contract instead. "
        "Never a paid run.",
        AUTHOR_CONTRACT_SCHEMA,
    ),
    (
        author_tool_handler,
        "author_tool",
        "SURFACE the interactive tool-builder widget INLINE so the HUMAN declares a kind:tool "
        "connector — an MCP server, an API connector, a KB query, or a terminology service — by "
        "FILLING A CARD in the chat ($0, read-only; the mirror of author_contract). Use it when the "
        "human wants to CONNECT / configure / add a tool (e.g. a SNOMED/Hermes MCP server, a "
        "web-scraper MCP, an API endpoint) that a judge's flag can then ground against. Shape: "
        "{id, implements, transport} — optional DRAFT seeds (implements is tool.mcp_server | "
        "tool.terminology | tool.kb_query | tool.api_connector). The human fills the connector "
        "config + optional flag bind and their Save is the audited write (POST /v1/tools); you DECLARE "
        "a connector, never upload code, and never run it. Bind a tool to a flag via author_contract "
        "(contract_type mcp_call, or snomed_subsumption for the SNOMED instance). Never a paid run.",
        AUTHOR_TOOL_SCHEMA,
    ),
    (
        author_criterion_handler,
        "author_criterion",
        "SURFACE the interactive criterion-authoring widget INLINE so the HUMAN mints a new GRADEABLE "
        "criterion (a scoreable taxonomy code) by FILLING A CARD in the chat ($0, read-only; the "
        "mirror of author_contract). Use it when the human wants to CREATE / define a new gradeable "
        "criterion or scoreable flag the council should be able to RAISE. Shape: {code, tier, "
        "owner_role} — the new SCREAMING_SNAKE code, its tier (TIER_1|TIER_2|TIER_3), and the owning "
        "production judge. The human reviews and their Save is the audited write (POST /v1/criterion "
        "splices the active tier:core pack's taxonomy snapshot + ontology); you do NOT mint the code. "
        "For a NON-gradeable reference flag use create_flag; for a grounding contract use "
        "author_contract. Never a paid run.",
        AUTHOR_CRITERION_SCHEMA,
    ),
    (
        create_judge_handler,
        "create_judge",
        "SURFACE the interactive create-judge widget INLINE so the HUMAN mints a NEW judge ROLE — a "
        "new voice on the council — over the active pack's taxonomy snapshot by FILLING A CARD in the "
        "chat ($0, read-only; the mirror of author_criterion). Use it when the human wants to CREATE / "
        "add a NEW judge / a new council voice / a new reviewer role. Shape: {role} — the new "
        "lower_snake role id to seed the card with (e.g. escalation_judge); the human fills the lens "
        "(codes the judge may raise), any owned codes (⊆ lens), the model, and an optional role "
        "prompt. Their 'Create judge' Save is the SOLE audited write (POST /v1/judges mints the new "
        "role into the snapshot, owner↔emit + snapshot gated); you do NOT mint the judge yourself. "
        "Contrast with author_judge, which ASSIGNS a lens to an EXISTING role — use create_judge to "
        "CREATE a new role, author_judge to RE-LENS an existing one. Never a paid run.",
        CREATE_JUDGE_SCHEMA,
    ),
    (
        kb_context_handler,
        "kb_context",
        "Retrieve the relevant HIPAA knowledge-base section(s) for a topic or a finding and SHOW "
        "them as CONTEXT — the honest 'what does the policy actually say' aid. Args: {query, "
        "[namespace], [top_k=3]}. LEAVE namespace unset (defaults to 'hipaa'); the only valid "
        "namespaces are 'hipaa' (default), 'medication-safety', 'clinical-escalation' — do NOT pass "
        "the backing index name (deployment config, LITHRIM_KB_INDEX). $0, READ-ONLY — it retrieves "
        "and displays; it NEVER changes a verdict or clears a finding. Use it to ground a "
        "discussion in the source policy.",
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
    (
        record_meta_verdict_handler,
        "record_meta_verdict",
        "RECORD the clinician's INDEPENDENT verdict + judge meta-audit on a run (the physician "
        "Layer-3 review): their own pass/fail, whether they AGREE with the council, and — only when "
        "they DISSENT — the judge's named fallacy. Shape: {run_id, human_verdict('pass'|'fail'), "
        "agrees_with_council(bool), [judge_fallacy_code], [rationale]}. judge_fallacy_code is a CLOSED "
        "enum (Hallucination Blindness | Reference Bias | Metric Conflation | Risk-Severity Blindness | "
        "Boundary Violation); omit it when agreeing. Get run_id from the run/report on screen. An "
        "audited $0 WRITE — it adds an immutable attestation, it NEVER changes the verdict or fires a "
        "paid run. An out-of-enum code is rejected (surface it, do not retry blindly).",
        RECORD_META_VERDICT_SCHEMA,
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
