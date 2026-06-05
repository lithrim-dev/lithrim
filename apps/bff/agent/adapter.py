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
"""

from __future__ import annotations

from typing import Any


def _part(tool_name: str, output: dict[str, Any]) -> dict[str, Any]:
    return {"type": f"tool-{tool_name}", "state": "output-available", "output": output}


def judge_part(role: str, agent: str) -> dict[str, Any]:
    """author_judge / get_judge -> the JudgeEditor card (it self-fetches via GET /v1/judges)."""
    return _part("judge_editor", {"role": role, "agent": agent})


def agent_part(name: str) -> dict[str, Any]:
    """get_agent (and UAP-5c-2 assemble_agent) -> the AgentEditor card (self-fetches
    GET /v1/agent for ``name``). The Domain leg."""
    return _part("agent_editor", {"agent": name})


def flag_part(agent: str) -> dict[str, Any]:
    """author_flag -> the FlagEditor card (self-fetches GET /v1/ontology for ``agent``).
    The Flag leg."""
    return _part("flag_editor", {"agent": agent})


def audit_part(run_id: str = "") -> dict[str, Any]:
    """review_runs -> the AuditView card. AuditView defaults to the config-change audit
    stream (GET /v1/audit — every authored judge/flag write) and, given ``runId``, loads
    that run's provenance (GET /v1/runs/{id}/audit). The Review leg — pure-read."""
    return _part("audit_log", {"runId": run_id})


def verdict_part(record: dict[str, Any]) -> dict[str, Any]:
    """run_eval -> the VerdictCard (flat-spread). Projects the composite verdict + the
    realized council agreement off the run-eval record; defaults fill the rest of the
    demo-shaped card."""
    composite = record.get("composite") or {}
    council = record.get("council") or {}
    votes = council.get("votes") or []
    verdict = str(composite.get("verdict") or composite.get("stage_verdict") or "—")
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
    return _part(
        "verdict_card",
        {
            "id": record.get("pipeline_run_id") or record.get("case_id") or "run",
            "verdict": verdict.upper(),
            "confidence": conf,
            "agreement": f"{agree} / {n}" if n else "—",
        },
    )
