"""LocalPipelineBackend: the salvaged council, run IN-PROCESS (no HTTP, no Celery).

Mirrors ``LithrimPipelineBackend`` but instead of POSTing ``/v1/pipeline/evaluate``
it constructs the vendored ``PipelineOrchestrator`` (``lithrim_bench.runtime.pipeline``)
and runs it directly. For M1 only the SEMANTIC (council) stage runs:

  - structural stage -> injected skip (no etlp-mapper call)
  - artifact stage   -> ``_skipped_artifact_stage`` (no single-judge LLM call)
  - provenance       -> ``NoOpProvenanceStore`` (no Mongo)
  - retrieval        -> the M1 stub returns empty matches (no Pinecone; grounding
                        is empty, which the council tolerates -> still produces a verdict)

``eval_mode=True`` + ``conversation_id="run:local:case:<case_id>"`` makes the council
derive a deterministic per-(case, judge) seed, so re-runs are byte-reproducible. That
is what the paper determinism protocol and the calibration before/after diff need.

BYOK: the council's LLM provider is resolved by the vendored ``llm_provider`` from
``settings`` (``LITHRIM_LLM_PROVIDER`` = openai|azure, ``OPENAI_API_KEY`` / ``AZURE_*``).
Set ``COMPLIANCE_COUNCIL_VERSION=v1`` so all three judges run on one OpenAI model.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..runtime.pipeline.models import PipelineRequest, PipelineResult, StageResult
from ..runtime.pipeline.orchestrator import PipelineOrchestrator
from ..runtime.pipeline.provenance import NoOpProvenanceStore
from ..runtime.pipeline.stages import _skipped_artifact_stage
from .base import BackendClient, BackendPin, BackendVerdict, JudgeOutput
from .lithrim_pipeline import _GATE_TO_COMPLIANCE, _build_context

_VOTE_TO_COMPLIANCE = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}


async def _skip_structural(request: PipelineRequest) -> StageResult:
    """M1: no structural validator for the scribe pack (semantic-only by construction)."""
    return StageResult(status="not_applicable")


class LocalPipelineBackend(BackendClient):
    def __init__(self, *, org_id: str = "local", artifact_type_override: str | None = None):
        self.org_id = org_id
        self.artifact_type_override = artifact_type_override
        # Semantic(council)-only orchestrator: structural + artifact stages injected
        # as skips, provenance is a no-op. Stateless, so build once and reuse.
        self._orchestrator = PipelineOrchestrator(
            structural_stage=_skip_structural,
            artifact_stage=_skipped_artifact_stage,
            provenance_store=NoOpProvenanceStore(),
        )

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="LocalPipelineBackend",
            backend_version="0.1.0",
            judge_model="local-council",
            judge_model_version="in-process",
            extra={"org_id": self.org_id, "mode": "semantic_only", "grounding": "empty"},
        )

    def _build_request(self, case: dict[str, Any]) -> PipelineRequest | None:
        artifacts = case.get("artifacts") or []
        if not artifacts:
            return None
        artifact = artifacts[0]
        agent_type = case.get("agent_type")
        return PipelineRequest(
            artifact=artifact["content"],
            artifact_type=self.artifact_type_override or artifact.get("type") or "unknown",
            context_kind="transcript",
            context=_build_context(case, artifacts),
            org_id=self.org_id,
            # agent_metadata.category selects the council's scribe prompt branch
            # (build_prompt :597-655) — faithful to how the analyze flow judges a
            # scribe agent; suppresses false positives on legit scribe output.
            agent_metadata=(
                {"category": agent_type, "name": f"bench-{agent_type}"} if agent_type else None
            ),
            # Deterministic per-(case, judge) seed: eval_mode + the ":case:<id>" marker.
            conversation_id=f"run:local:case:{case['case_id']}",
            eval_mode=True,
            gate_mode=False,
        )

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        request = self._build_request(case)
        if request is None:
            return BackendVerdict(
                compliance_verdict="approve",
                artifact_verdict="PASS",
                flags=[],
                structural_verdict=None,
                structural_findings=[],
                raw={"skipped": "no artifacts"},
            )
        result: PipelineResult = asyncio.run(self._orchestrator.evaluate(request))
        return _map_result(result)


def _map_result(result: PipelineResult) -> BackendVerdict:
    """PipelineResult object -> BackendVerdict (mirrors lithrim_pipeline._parse)."""
    flags = sorted(
        {f.code or f.check_name or "" for f in result.findings if (f.code or f.check_name)} - {""}
    )

    per_judge: dict[str, JudgeOutput] | None = None
    votes = result.semantic.judge_votes if result.semantic else None
    if votes:
        per_judge = {
            jv.judge_role: JudgeOutput(
                judge_name=jv.judge_role,
                verdict=_VOTE_TO_COMPLIANCE.get(jv.vote, "approve"),
                flags=list(jv.findings or []),
                confidence=float(jv.confidence) if jv.confidence is not None else 0.0,
                reason=jv.reason or "",
            )
            for jv in votes
        }

    structural_verdict = (
        result.structural.status
        if result.structural and result.structural.status != "not_applicable"
        else None
    )

    return BackendVerdict(
        compliance_verdict=_GATE_TO_COMPLIANCE.get(result.gate_decision, "approve"),
        artifact_verdict=result.verdict,
        flags=flags,
        per_judge=per_judge,
        structural_verdict=structural_verdict,
        structural_findings=[],
        raw={
            "gate_decision": result.gate_decision,
            "duration_ms": result.duration_ms,
            "semantic_status": result.semantic.status if result.semantic else None,
            "council_error": result.provenance.council_error if result.provenance else None,
        },
        findings_rich=[f.model_dump() for f in result.findings],
    )
