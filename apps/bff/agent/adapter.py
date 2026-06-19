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
    agent: str, flag_code: str = "", *, show_intent: str = "auto"
) -> dict[str, Any]:
    """FAUTH-1 (G1): author_contract -> the ContractBuilder INPUT widget, surfaced INLINE and
    SEEDED with the in-context ``flag_code`` + ``agent`` so the human authors a deterministic
    ``verification_contract`` by filling the card in the chat (not by the agent composing JSON,
    not in the side pane). The mirror is judge_part -> JudgeEditor (a $0 surface; the human's
    Save is the write). Unlike the read-or-self-fetch cards, this is an INPUT widget: its save
    rides the EXISTING audited ``putGroundingContract`` (the shell threads ``onResult`` to it) —
    this part adds NO new write path. ``auto`` by default (an authoring card the agent leads
    with is a PRIMARY result the shell renders inline)."""
    return _part(
        "contract_builder",
        {"agent": agent, "flag_code": flag_code},
        show_intent=show_intent,
    )


def audit_part(run_id: str = "", *, show_intent: str = "ondemand") -> dict[str, Any]:
    """review_runs (and UAP-5c-2 run_eval_pack — the batch's newest run) -> the AuditView
    card. AuditView defaults to the config-change audit stream (GET /v1/audit — every
    authored judge/flag write) and, given ``runId``, loads that run's provenance
    (GET /v1/runs/{id}/audit). The Review/batch leg — pure-read. W3: a PASSIVE orientation
    read, so ``ondemand`` by default (the off-context Audit-trail-next-to-404 the live drive
    hit was exactly this card firing on the agent's incidental review_runs)."""
    return _part("audit_log", {"runId": run_id}, show_intent=show_intent)


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
            }
            for v in votes
        ],
    }
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
    the reference-carrying pattern, like agent_part/judge_part). An inline summary of the
    SOURCE case the council grades, with a "View case ->" that opens the full Case tab. $0.

    NARR-CHAT-LOOP: ``case_id`` selects a SPECIFIC ingested-corpus case (the "open case X"
    leg). It rides the output so the card self-fetches GET /v1/case?case_id=X — without it the
    card showed the agent's seed regardless of the case asked for (the confident-but-wrong live
    bug). ``None`` keeps the agent's own ``dataset.case_id`` (back-compat)."""
    return _part("case_summary", {"agent": agent, "case_id": case_id})


def propose_live_run_part() -> dict[str, Any]:
    """CHATBIND-4: propose_live_run -> a $0 DIRECTIVE (not a card; like open_artifact) that asks
    the shell to OPEN the in-DOM CostModal. The AGENT only PROPOSES — it never fires the run; the
    human's explicit modal-confirm (confirmPaidRun) is the ONLY paid path. Absent from KNOWN_TOOLS,
    never routed through renderTool, carries no agent/run/paid field — emitting it cannot spend.

    W3: a DIRECTIVE carries NO ``show_intent`` tag (like open_artifact) — it is not a card and
    never goes through the shell's dedup/intent gating."""
    return {"type": "tool-propose_live_run", "state": "output-available", "output": {}}
