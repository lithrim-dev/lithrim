"""The parts-adapter (UAP-5b D4): a tool-result -> the gen-UI message-parts shape.

The shell's gen-UI registry (`apps/shell/src/genui/registry.js`) renders a typed
``{ type: "tool-<name>", state: "output-available", output: {...} }`` part via
``renderTool``. This module maps each CORE SDK-MCP tool's structured result into
that shape so the conversation renders the EXISTING cards inline — NO new card
types (the UAP-5b reuse guardrail). The ``output`` follows the S-BS-19 flat-spread
convention (the card destructures fields directly from ``part.output``).

Mapping (D-B/D-D, resolved at plan-review):
    author_judge -> tool-judge_editor   ({role, agent}; the card self-fetches the
                                          rendered prompt/questions via GET /v1/judges)
    get_judge    -> tool-judge_editor   ({role, agent}; a $0 preview mount)
    run_eval     -> tool-verdict_card   (flat {verdict, confidence, agreement, id, ...})

UAP-5c (the journey-completing tools — every target card pre-exists in KNOWN_TOOLS):
    get_agent    -> tool-agent_editor   ({agent}; the card self-fetches GET /v1/agent — Domain)
    author_flag  -> tool-flag_editor    ({agent}; the card self-fetches GET /v1/ontology — Flag)
    review_runs  -> tool-audit_log      ({runId}; AuditView shows the config-change audit stream +
                                          the latest run's provenance — Review; pure-read, no paid
                                          surface, so the Review leg adds no window.confirm gate)

UAP-5c-2 (the split tools — REUSE the same two cards, no new types [D-B]):
    run_eval_pack  -> tool-audit_log    (audit_part with the batch's newest run id; pure-read like
                                          review_runs — keeps the chat surface free of RunPanel's
                                          window.confirm paid gate, S-BS-80; the batch's runs
                                          round-trip to GET /v1/runs)
    assemble_agent -> tool-agent_editor (agent_part; the Domain-roster edit renders the same card
                                          as get_agent — it self-fetches the updated GET /v1/agent)

CHATBIND-2 (the pane-control channel — a DIRECTIVE, not a card):
    focus_artifact -> tool-open_artifact (open_artifact_part; the shell OPENS+FOCUSES the named
                                          ArtifactPane tab. NOT a gen-UI card — it is absent from
                                          KNOWN_TOOLS and is NEVER routed through renderTool.)
"""

from __future__ import annotations

from typing import Any


def _part(
    tool_name: str, output: dict[str, Any], *, show_intent: str = "auto"
) -> dict[str, Any]:
    """CONV-UX-1 (W3): every part carries a ``show_intent`` GATING tag — ``"auto"`` (a
    PRIMARY result the shell renders as a full card inline) or ``"ondemand"`` (a passive
    orientation read the shell collapses to a compact "Show … ▸" affordance, expanded only
    if asked). Additive + flat-spread-safe: the shell ignores unknown top-level keys, so an
    older shell renders every part as before. The DEFAULT is ``"auto"`` — only explicitly-
    passive reads tag ``"ondemand"``, keeping the gating conservative."""
    return {
        "type": f"tool-{tool_name}",
        "state": "output-available",
        "output": output,
        "show_intent": show_intent,
    }


def judge_part(role: str, agent: str, *, show_intent: str = "auto") -> dict[str, Any]:
    """author_judge / get_judge -> the JudgeEditor card (it self-fetches via GET /v1/judges).
    W3: author_judge is the PRIMARY result (``auto``); a bare get_judge PREVIEW is ``ondemand``
    (the handler passes the intent)."""
    return _part("judge_editor", {"role": role, "agent": agent}, show_intent=show_intent)


def agent_part(name: str, *, show_intent: str = "auto") -> dict[str, Any]:
    """get_agent (and UAP-5c-2 assemble_agent) -> the AgentEditor card (self-fetches
    GET /v1/agent for ``name``). The Domain leg. W3: an assemble_agent WRITE is ``auto``; a
    bare get_agent orientation READ is ``ondemand`` (the handler passes the intent)."""
    return _part("agent_editor", {"agent": name}, show_intent=show_intent)


def flag_part(agent: str, *, show_intent: str = "auto") -> dict[str, Any]:
    """author_flag / create_flag / add_grounding_contract -> the FlagEditor card (self-fetches
    GET /v1/ontology for ``agent``). The Flag leg — a config WRITE, so ``auto`` by default."""
    return _part("flag_editor", {"agent": agent}, show_intent=show_intent)


def contract_builder_part(
    agent: str,
    flag_code: str = "",
    *,
    suggested_params: dict[str, Any] | None = None,
    question: str = "",
    contract_type: str = "",
    show_intent: str = "auto",
) -> dict[str, Any]:
    """FAUTH-1 (G1): author_contract -> the ContractBuilder INPUT widget, surfaced INLINE and
    SEEDED with the in-context ``flag_code`` + ``agent`` so the human authors a deterministic
    ``verification_contract`` by filling the card in the chat (not by the agent composing JSON,
    not in the side pane). The mirror is judge_part -> JudgeEditor (a $0 surface; the human's
    Save is the write). Unlike the read-or-self-fetch cards, this is an INPUT widget: its save
    rides the EXISTING audited ``putGroundingContract`` (the shell threads ``onResult`` to it) —
    this part adds NO new write path. ``auto`` by default (an authoring card the agent leads
    with is a PRIMARY result the shell renders inline).

    FAUTH-3 (G2, the ASSIST keystone): the OPTIONAL ``suggested_params`` (+ ``question``) pre-fill
    the card's EDITABLE params field (+ question) — the prose->params draft the agent proposes. They
    are DRAFT seeds only: the part is still emit-only, the human edits them, and the human's Save is
    the sole audited write (the assist never auto-writes the ontology / never enters ground()). Both
    are added to the output ONLY when present, so the un-suggested path is the byte-identical FAUTH-1
    shape ({agent, flag_code})."""
    out: dict[str, Any] = {"agent": agent, "flag_code": flag_code}
    if suggested_params:
        out["suggested_params"] = suggested_params
    if question:
        out["question"] = question
    # S-BS-143: the agent-chosen direction (value_presence FLOOR vs presence_check SUPPRESS) so the
    # card opens on the right contract_type. Added ONLY when set → the un-typed path is byte-identical.
    if contract_type:
        out["contract_type"] = contract_type
    return _part("contract_builder", out, show_intent=show_intent)


def criterion_jute_builder_part(
    agent: str,
    flag_code: str = "",
    tool: str = "",
    call: str = "",
    criterion: str = "",
    *,
    show_intent: str = "auto",
) -> dict[str, Any]:
    """CRITERION-JUTE-1d: author_contract, for a TOOL-GROUNDED (``mcp_call``) flag, ADDITIONALLY
    surfaces the CriterionJuteBuilder INPUT widget inline — the "pick a tool+call, seed generation
    with a plain-English criterion, gate over the corpus, pin on pass" move. The mirror is
    contract_builder_part: EMIT-ONLY (this part adds NO write path). The card's "Generate + gate" is
    a $0 PREVIEW and its "Pin" rides ``POST /v1/criterion-jute/generate`` (commit=true) — the
    human's Pin is the SOLE audited write, gated on the corpus gate passing; the agent never pins the
    contract itself. NOT a ``_TOOL_SPECS`` entry (a part-builder, not a chat tool) — the tool-count
    is unchanged. ``auto`` (an authoring card the agent leads with)."""
    return _part(
        "criterion_jute_builder",
        {"agent": agent, "flag_code": flag_code, "tool": tool, "call": call, "criterion": criterion},
        show_intent=show_intent,
    )


def tool_builder_part(
    agent: str, *, seed: dict[str, Any] | None = None, show_intent: str = "auto"
) -> dict[str, Any]:
    """TOOL-AUTHOR-1: author_tool -> the ToolBuilder INPUT widget, surfaced INLINE so the human
    DECLARES a ``kind: tool`` connector (an MCP server / API connector / KB / terminology service)
    by filling a card — the mirror of contract_builder_part. EMIT-ONLY: the card's Save rides the
    audited ``POST /v1/tools`` writer; the agent NEVER declares the tool itself (A-SAFE, no
    PAID_KEY). ``seed`` pre-fills the editable id/implements/transport fields when the agent has
    them; absent → an empty card (the card's own validation gates Save)."""
    out: dict[str, Any] = {"agent": agent}
    if seed:
        out["seed"] = seed
    return _part("tool_builder", out, show_intent=show_intent)


def criterion_builder_part(
    agent: str,
    code: str = "",
    tier: str = "",
    owner_role: str = "",
    definition: str = "",
    when_to_use: str = "",
    when_NOT_to_use: str = "",
    *,
    show_intent: str = "auto",
) -> dict[str, Any]:
    """NARR-5-CRIT-b: author_criterion -> the CriterionBuilder INPUT widget, surfaced INLINE and
    SEEDED with the in-context ``code``/``tier``/``owner_role`` + ``agent`` so the human MINTS a new
    gradeable criterion by filling the card in the chat. The mirror is contract_builder_part. The
    SPINE/CONTAINMENT invariant: this is emit-only — the card's Save rides ``POST /v1/criterion``
    (the sanctioned snapshot writer), the human's Save is the SOLE write of the contract-of-record;
    the agent never mints a code itself. ``auto`` (an authoring card the agent leads with)."""
    return _part(
        "criterion_builder",
        {
            "agent": agent, "code": code, "tier": tier, "owner_role": owner_role,
            # CRITERION-TEXT-1: the agent's DRAFT of the criterion text, editable in the card.
            "definition": definition,
            "when_to_use": when_to_use,
            "when_NOT_to_use": when_NOT_to_use,
        },
        show_intent=show_intent,
    )


def judge_builder_part(
    agent: str, role: str = "", *, show_intent: str = "auto"
) -> dict[str, Any]:
    """PHASE2-WIRE: create_judge -> the JudgeBuilder INPUT widget, surfaced INLINE and SEEDED with
    the in-context ``role`` id + ``agent`` so the human MINTS a NEW judge role (a new council voice)
    over the active pack's taxonomy snapshot by filling the card in the chat. The mirror is
    criterion_builder_part. The SPINE/CONTAINMENT invariant: this is emit-only — the card's "Create
    judge" Save rides ``POST /v1/judges`` (the sanctioned snapshot writer), the human's Save is the
    SOLE write of the new judge; the agent never mints the judge itself. Distinct from judge_part
    (author_judge → tool-judge_editor, which ASSIGNS a lens to an EXISTING role). ``auto`` (an
    authoring card the agent leads with)."""
    return _part("judge_builder", {"agent": agent, "role": role}, show_intent=show_intent)


def audit_part(
    run_id: str = "", *, case_id: str | None = None, show_intent: str = "ondemand"
) -> dict[str, Any]:
    """review_runs (and UAP-5c-2 run_eval_pack — the batch's newest run) -> the AuditView
    card. AuditView defaults to the config-change audit stream (GET /v1/audit — every
    authored judge/flag write) and, given ``runId``, loads that run's provenance
    (GET /v1/runs/{id}/audit). The Review/batch leg — pure-read. W3: a PASSIVE orientation
    read, so ``ondemand`` by default (the off-context Audit-trail-next-to-404 the live drive
    hit was exactly this card firing on the agent's incidental review_runs).
    RUN-TRAIL-CASE-SCOPE: ``caseId`` (present-only, additive) is the case the review was
    scoped to — AuditView then requests the CASE-scoped run trail (full trail one click
    away) instead of leading with whichever case anyone graded most recently."""
    output: dict[str, Any] = {"runId": run_id}
    if case_id:
        output["caseId"] = case_id
    return _part("audit_log", output, show_intent=show_intent)


def verdict_part(record: dict[str, Any]) -> dict[str, Any]:
    """run_eval -> the VerdictCard (flat-spread). Projects the REAL council output off the
    run-eval record — the verdict, the active findings it flagged (the "why"), the realized
    judge agreement + confidence, and the faithfulness-judge status. NO demo fill: the card
    shows what the council actually returned ([[no-static-components-in-live-eval-ui]])."""
    composite = record.get("composite") or {}
    council = record.get("council") or {}
    votes = council.get("votes") or []
    verdict = str(composite.get("verdict") or composite.get("stage_verdict") or "—")
    findings = [str(f) for f in (composite.get("active_findings") or [])]
    n = len(votes)
    agree = (
        sum(
            1
            for v in votes
            if (v.get("vote") or "").lower() == (votes[0].get("vote") or "").lower()
        )
        if n
        else 0
    )
    confs = [v.get("confidence") for v in votes if isinstance(v.get("confidence"), (int, float))]
    conf = f"{(sum(confs) / len(confs)):.2f}" if confs else "—"
    # the real "why" — the findings the council flagged (or a clean pass), not a demo Q/A.
    answer = (
        f"{len(findings)} finding(s): " + ", ".join(findings[:6])
        if findings
        else "No findings — passes the quality gate."
    )
    out: dict[str, Any] = {
        "id": record.get("pipeline_run_id") or record.get("case_id") or "run",
        "verdict": verdict.upper(),
        "confidence": conf,
        "agreement": f"{agree} / {n}" if n else "—",
        "answer": answer,
        # CONV-FIRST §3: the inline card is the WHOLE result — carry the realized per-judge
        # votes (role/vote/confidence) so the conversation shows how each judge voted, and the
        # pipeline_run_id the inline clinician-dissent form (META-VERDICT-1) binds to.
        "runId": record.get("pipeline_run_id") or "",
        "votes": [
            {
                "role": str(v.get("judge_role") or v.get("role") or "judge"),
                "vote": str(v.get("vote") or ""),
                **(
                    {"confidence": v.get("confidence")}
                    if isinstance(v.get("confidence"), (int, float))
                    else {}
                ),
                # INLINE-IMPACT-1: carry each judge's REASON so the approve reads as a reasoned
                # verdict inline (not a bare scorecard) — added only when present (byte-identical else).
                **({"reason": str(v.get("reason"))} if v.get("reason") else {}),
                # Per-reviewer sampling distribution (independent-axes model): THIS axis's own
                # variance + k, shown inline so each reviewer's stability reads separately.
                **({"variance": v.get("variance")} if isinstance(v.get("variance"), (int, float)) else {}),
                **({"k": v.get("k")} if isinstance(v.get("k"), int) else {}),
                # R2c: the raw per-sample scores — the inline "3B/2P" split derives from this.
                **(
                    {"scores_raw": v.get("scores_raw")}
                    if isinstance(v.get("scores_raw"), list) and v.get("scores_raw")
                    else {}
                ),
            }
            for v in votes
        ],
    }
    # The named case outcome (independent-axes rule table) — the PRIMARY headline the card shows
    # (the reviewers are not aggregated into a single score). Added only when present.
    case_outcome = council.get("case_outcome") or composite.get("case_outcome")
    if case_outcome:
        out["caseOutcome"] = str(case_outcome)
    # INLINE-IMPACT-1 (the demo's thesis, inline): the structural-floor INJECTIONS — a deterministic
    # contract that BLOCKED what the council missed. Projected from composite.floor_adjustments
    # (action == floor_block only; inconclusive floors did not flip the verdict). The card renders a
    # "Caught by floor rule" attribution (code + contract + one-line disposition) so the flip shows
    # WHO caught it — the rule the human authored — not just "BLOCK". Added only when non-empty.
    floor_blocks = [
        {
            "flag": fa.get("flag"),
            "contract_type": fa.get("contract_type"),
            "contract": fa.get("contract"),
            "disposition": fa.get("disposition"),
        }
        for fa in (composite.get("floor_adjustments") or [])
        if fa.get("action") == "floor_block"
    ]
    if floor_blocks:
        out["floorBlocks"] = floor_blocks
    # FLOOR-CLEAR-1 (the SNOMED-flip thesis, inline): the symmetric attribution — a deterministic
    # fact-check DISPROVED a finding a judge raised (a false positive), so a flagged case still PASSES.
    # Projected from record.grounded.suppressed (code + reason + evidence). The card renders a "Cleared
    # by a fact-check" attribution so the suppression flip reads on-card, not only in the full report.
    # Added only when non-empty (a real clean pass shows nothing — never a fabricated 'cleared').
    # REL-OPS-1 O2: `terminology_edition` rides along when the suppression carries it —
    # absent (not null) otherwise, so pre-O2 entries project shape-identical.
    floor_clears = [
        {
            "flag": s.get("code"),
            "reason": s.get("reason"),
            "evidence": s.get("evidence"),
            **(
                {"terminology_edition": s["terminology_edition"]}
                if s.get("terminology_edition") is not None
                else {}
            ),
        }
        for s in ((record.get("grounded") or {}).get("suppressed") or [])
        if s.get("code")
    ]
    if floor_clears:
        out["floorClears"] = floor_clears
    # the faithfulness pillar reflects the faithfulness judge's actual vote (clear vs flagged).
    faith = next((v for v in votes if "faith" in str(v.get("judge_role") or "").lower()), None)
    if faith:
        out["pillar"] = "Faithfulness"
        out["pillarStatus"] = (
            "clear ✓" if str(faith.get("vote") or "").upper() in ("PASS", "APPROVE") else "flagged"
        )
    return _part("verdict_card", out)


def open_artifact_part(tab: str) -> dict[str, Any]:
    """CHATBIND-2: focus_artifact -> a pane-control DIRECTIVE (not a gen-UI card). The shell
    honors it by OPENING + FOCUSING the named ArtifactPane tab; it is absent from KNOWN_TOOLS
    and is NEVER routed through ``renderTool``. ``tab`` is one of case|report|judges|config|corpus
    (the caller validates it). $0 — emitting a directive can never fire a paid run.

    W3: a DIRECTIVE carries NO ``show_intent`` tag — it is not a gen-UI card and never goes
    through the shell's dedup/intent gating (the shell special-cases it out of renderTool), so
    it keeps its bare {type,state,output} shape."""
    return {"type": "tool-open_artifact", "state": "output-available", "output": {"tab": tab}}


def case_summary_part(agent: str, case_id: str | None = None) -> dict[str, Any]:
    """CHATBIND-3: show_case -> the CaseCard (it self-fetches GET /v1/case for ``agent`` —
    the reference-carrying pattern, like agent_part/judge_part). It renders the SOURCE case the
    council grades — the visit transcript AND the scribe note, INLINE in the conversation, so the
    human compares what was said vs what was documented; an optional "Open transcript editor ->" is a
    secondary drill-down, NOT the way to read the case (INLINE-IMPACT-1). $0.

    NARR-CHAT-LOOP: ``case_id`` selects a SPECIFIC ingested-corpus case (the "open case X"
    leg). It rides the output so the card self-fetches GET /v1/case?case_id=X — without it the
    card showed the agent's seed regardless of the case asked for (the confident-but-wrong live
    bug). ``None`` keeps the agent's own ``dataset.case_id`` (back-compat)."""
    return _part("case_summary", {"agent": agent, "case_id": case_id})


def propose_live_run_part(case_id: str | None = None) -> dict[str, Any]:
    """CHATBIND-4: propose_live_run -> a $0 DIRECTIVE (not a card; like open_artifact) that asks
    the shell to OPEN the in-DOM CostModal. The AGENT only PROPOSES — it never fires the run; the
    human's explicit modal-confirm (confirmPaidRun) is the ONLY paid path. Absent from KNOWN_TOOLS,
    never routed through renderTool, carries no agent/run/paid field — emitting it cannot spend.

    CHAT-CASE-TARGET-1: ``case_id`` is the targeted case the directive carries so the shell grades
    the case the chat NAMED (it syncs its active case to it, then confirmPaidRun targets it) — the
    fix for the dropped-case bug where the human's spend hit the stale top-bar selection. A case
    SELECTOR is NOT a paid field: emitting the directive still cannot spend (no agent/run/paid/
    confirm field). Back-compat: ``None`` -> ``output: {}`` (byte-identical for any non-case caller
    — the TopBar path, the _litellm_loop fallback, propose_live_run with no active case).

    W3: a DIRECTIVE carries NO ``show_intent`` tag (like open_artifact) — it is not a card and
    never goes through the shell's dedup/intent gating."""
    output = {"case_id": case_id} if case_id else {}
    return {"type": "tool-propose_live_run", "state": "output-available", "output": output}


def propose_run_all_part() -> dict[str, Any]:
    """RUN-ALL-1: propose_run_all -> a $0 DIRECTIVE (like propose_live_run) that asks the shell to
    open the in-DOM CostModal for the WHOLE ingested cohort. The AGENT only PROPOSES — it never
    fires the batch; the human's modal-confirm is the ONLY paid path. On confirm the shell calls
    ``POST /v1/cases/grade`` and renders the inline ScorecardCard (tool-scorecard). Absent from
    KNOWN_TOOLS, never routed through renderTool, carries NO agent/run/paid/confirm field — emitting
    it cannot spend (the A-SAFE property, identical to propose_live_run). NO ``show_intent`` tag."""
    return {"type": "tool-propose_run_all", "state": "output-available", "output": {}}
