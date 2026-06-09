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
# CHATBIND-3: show_case takes NO params — it summarizes the ACTIVE agent's source case as an
# inline card (the card self-fetches GET /v1/case). $0/read, no paid knob, nothing to smuggle.
SHOW_CASE_SCHEMA: dict[str, Any] = {}
# CHATBIND-4: propose_live_run takes NO params — it asks the shell to OPEN the cost-confirm modal.
# The agent PROPOSES; the human's modal-confirm is the only paid path. No paid knob, nothing to smuggle.
PROPOSE_LIVE_RUN_SCHEMA: dict[str, Any] = {}
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
    - ``default_agent``: the agent the tools default to.
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
    default_agent: str = "ws0_default"
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
    try:
        record = ctx.run_eval_replay(agent=agent)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(f"Replay run failed for {agent!r}: {detail}.")
    ctx.emit(verdict_part(record))
    ctx.emit_run(record)  # CHATBIND-2 (D4): lift this $0 replay into the shell's runResult
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
    # CHATBIND-3: emit an inline Case Summary card for the ACTIVE agent's source case. $0/read —
    # NO bound op (the card self-fetches GET /v1/case), NO paid knob, no params. Pairs with
    # focus_artifact: the card summarizes inline; its "View case" opens the full Case tab.
    ctx.emit(case_summary_part(ctx.default_agent))
    return _text(
        f"Showing the source case for {ctx.default_agent!r} as a card — the transcript, the scribe "
        f"artifact, and the planted (by-construction) label. Open it to read the full case ($0)."
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
        show_case_handler,
        "show_case",
        "Show the SOURCE case the council grades as an inline Case Summary card ($0, read-only) — "
        "the transcript, the scribe artifact, and the by-construction planted label. Use it when "
        "the human wants to SEE or explore the case BEFORE running. The card's 'View case' opens "
        "the full Case tab. No params — it summarizes the current evaluation's case.",
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
