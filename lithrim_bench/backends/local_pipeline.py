"""LocalPipelineBackend: the salvaged council, run IN-PROCESS (no HTTP, no Celery).

Mirrors ``LithrimPipelineBackend`` but instead of POSTing ``/v1/pipeline/evaluate``
it constructs the vendored ``PipelineOrchestrator`` (``lithrim_bench.runtime.pipeline``)
and runs it directly. For the WS-6c-AGENTIC grade-wire milestone only the SEMANTIC
(council) stage runs:

  - structural stage -> injected skip (no etlp-mapper call)
  - artifact stage   -> ``_skipped_artifact_stage`` (no single-judge LLM call)
  - provenance       -> injectable; defaults to ``NoOpProvenanceStore`` (hermetic).
                        The WS-6d in-process grade path injects ``SqliteProvenanceStore``
                        so the product path persists provenance (no Mongo).
  - retrieval        -> the M1 stub returns empty matches (no Pinecone; grounding
                        is empty, which the council tolerates -> still produces a verdict)

``eval_mode=True`` + ``conversation_id="run:local:case:<case_id>"`` makes the council
derive a deterministic per-(case, judge) seed, so re-runs are byte-reproducible. That
is what the paper determinism protocol and the calibration before/after diff need.

BYOK: the council's LLM provider is resolved by the vendored ``llm_provider`` from
``settings`` (``LITHRIM_LLM_PROVIDER`` = openai|azure, ``OPENAI_API_KEY`` / ``AZURE_*``).
WS-6c-AGENTIC: the council runs the **v2 cross-provider trio** by default
(``COMPLIANCE_COUNCIL_VERSION`` defaults to ``v2`` in ``runtime/council/settings.py``;
the trio reaches Mistral-Large-3 + Llama-4-Maverick via the Azure deployment ids
``AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3`` / ``_LLAMA_4_MAVERICK``, so a live run
HARD-requires ``LITHRIM_LLM_PROVIDER=azure`` + those two deployments). Offline tests
inject the semantic stage, so they never touch Azure. Semantic-only remains the
milestone scope: structural + artifact stay injected-skip and the structural FLOOR
lives in the harness ``ground()`` layer, not this stage.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..runtime.council.settings import settings
from ..runtime.pipeline.models import PipelineRequest, PipelineResult, StageResult
from ..runtime.pipeline.orchestrator import PipelineOrchestrator
from ..runtime.pipeline.provenance import NoOpProvenanceStore, ProvenanceStore
from ..runtime.pipeline.stages import _skipped_artifact_stage
from .base import BackendClient, BackendPin, BackendVerdict, JudgeOutput
from .lithrim_pipeline import _GATE_TO_COMPLIANCE, _build_context

_VOTE_TO_COMPLIANCE = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}


async def _skip_structural(request: PipelineRequest) -> StageResult:
    """M1: no structural validator for the scribe pack (semantic-only by construction)."""
    return StageResult(status="not_applicable")


class LocalPipelineBackend(BackendClient):
    def __init__(
        self,
        *,
        org_id: str = "local",
        artifact_type_override: str | None = None,
        semantic_stage: Any = None,
        provenance_store: ProvenanceStore | None = None,
        context_fields: tuple[str, ...] = (),
    ):
        self.org_id = org_id
        self.artifact_type_override = artifact_type_override
        # REPRO-1 R1b: ontology-declared case fields folded into the grading context as
        # SOURCE RECORD sections (see _build_context). Default () = byte-identical.
        self.context_fields = tuple(context_fields or ())
        # Semantic(council)-only orchestrator: structural + artifact stages injected
        # as skips. Stateless, so build once and reuse.
        # ``semantic_stage`` is injectable so the grade seam can run a deterministic
        # offline stage (A1) without an Azure call; None -> the orchestrator's
        # default run_semantic (the live v2 trio).
        # ``provenance_store`` is injectable (WS-6d): None -> NoOp (hermetic; the
        # default for direct/test construction); the grade runner passes a
        # ``SqliteProvenanceStore`` so the product path persists. Either way the
        # store is a fire-and-forget sink behind ``save`` — the returned
        # ``PipelineResult`` is byte-identical regardless (the frozen-contract A3).
        self._orchestrator = PipelineOrchestrator(
            structural_stage=_skip_structural,
            semantic_stage=semantic_stage,
            artifact_stage=_skipped_artifact_stage,
            provenance_store=provenance_store or NoOpProvenanceStore(),
        )

    @property
    def pin(self) -> BackendPin:
        return BackendPin(
            backend="LocalPipelineBackend",
            backend_version="0.1.0",
            judge_model="local-council",
            judge_model_version=f"in-process-{settings.COMPLIANCE_COUNCIL_VERSION}",
            extra={
                "org_id": self.org_id,
                "mode": "semantic_only",
                "grounding": "empty",
                "council_version": settings.COMPLIANCE_COUNCIL_VERSION,
            },
        )

    def _build_request(self, case: dict[str, Any]) -> PipelineRequest | None:
        artifacts = case.get("artifacts") or []
        if not artifacts:
            return None
        artifact = artifacts[0]
        agent_type = case.get("agent_type")
        # REPRO-1 R1b: when the agent declared structured source-record fields (its ontology's
        # `grading_context_fields`, DATA), carry those case fields on a dict context under `record`
        # so the authored stage folds them into the judge-visible context — the record reaches the
        # judge. Data-driven: the field NAMES come from config, never hardcoded here. No declared
        # record (or none present on the case) → a plain transcript string (byte-identical to
        # before). `_context_as_transcript` unwraps the dict's transcript for every string caller.
        transcript = _build_context(case, artifacts, context_fields=self.context_fields)
        record = {
            name: case[name]
            for name in self.context_fields
            if case.get(name) not in (None, "", [], {})
        }
        context: dict[str, Any] | str = (
            {"transcript": transcript, "record": record} if record else transcript
        )
        return PipelineRequest(
            artifact=artifact["content"],
            artifact_type=self.artifact_type_override or artifact.get("type") or "unknown",
            context_kind="transcript",
            context=context,
            org_id=self.org_id,
            # agent_metadata.category historically selected build_prompt's scribe prompt
            # branch (deleted in CE-PACK-6b-CLEAN; the authored default path ignores
            # category). Retained for provenance / parity with how the analyze flow tags a
            # scribe agent.
            agent_metadata=(
                {"category": agent_type, "name": f"bench-{agent_type}"} if agent_type else None
            ),
            # Deterministic per-(case, judge) seed: eval_mode + the ":case:<id>" marker.
            conversation_id=f"run:local:case:{case['case_id']}",
            eval_mode=True,
            gate_mode=False,
            # Case-level Policy criterion (independent-axes model) — carried from the case
            # record to the council payload so the authored stage applies it to policy_judge.
            policy_criterion=case.get("policy_criterion"),
        )

    def evaluate_pipeline(self, case: dict[str, Any]) -> PipelineResult | None:
        """Run the in-process orchestrator; return the raw PipelineResult (None when
        the case has no artifacts). The grade seam (``grade_inprocess``) model_dumps
        this to the ``/v1/pipeline/evaluate`` dict shape so ``ground``/``composite``
        stay path-agnostic; ``evaluate`` maps it to a BackendVerdict for the
        backends API.
        """
        request = self._build_request(case)
        if request is None:
            return None
        return asyncio.run(self._orchestrator.evaluate(request))

    def evaluate(self, case: dict[str, Any]) -> BackendVerdict:
        result = self.evaluate_pipeline(case)
        if result is None:
            return BackendVerdict(
                compliance_verdict="approve",
                artifact_verdict="PASS",
                flags=[],
                structural_verdict=None,
                structural_findings=[],
                raw={"skipped": "no artifacts"},
            )
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
