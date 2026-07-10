"""PipelineOrchestrator — single entry point for artifact evaluation.

Phase C: dispatches structural + semantic stages for all three ``context_kind``
modes (``transcript``, ``source_message``, ``none``). Enforces worst-of verdict
semantics, derives ``gate_decision``, persists provenance per SPEC §3.3/§3.4,
and emits p50/p95 latency instrumentation tagged by context_kind + gate_mode.

Design notes:
- Stages live in ``app.services.pipeline.stages``. They are injected as callables
  so tests can patch them without monkeypatching module attributes.
- Provenance persistence is behind a ``ProvenanceStore`` interface. The default is
  ``NoOpProvenanceStore`` (hermetic — bare construction and unit tests persist
  nothing); the in-process grade path opts in to ``SqliteProvenanceStore`` (WS-6d).
  No Mongo on the product path.
- The orchestrator stays a single stateless object at module import; FastAPI DI
  switches in later phases when stages gain real per-request collaborators (KB
  clients, tool catalog, etc.).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from ..council._compat import emit_timing
from .models import (
    Finding,
    GateDecision,
    PipelineProvenance,
    PipelineRequest,
    PipelineResult,
    StageResult,
    StructuralTemplatePin,
    Verdict,
)
from .provenance import NoOpProvenanceStore, ProvenanceStore
from .stages import (
    run_artifact,
    run_semantic,
    run_structural,
)

logger = logging.getLogger(__name__)

# Stage-callable types (DI-friendly).
StructuralStage = Callable[[PipelineRequest], Awaitable[StageResult]]
SemanticStage = Callable[[PipelineRequest], Awaitable[tuple[StageResult, dict]]]
ArtifactStage = Callable[[PipelineRequest], Awaitable[tuple[StageResult, dict]]]


# ── Verdict + gate_decision helpers ───────────────────────────────────────

_VERDICT_RANK = {"PASS": 0, "WARN": 1, "BLOCK": 2}


def _worst_of(structural: StageResult, semantic: StageResult) -> Verdict:
    """Compute final verdict = max(structural, semantic).

    ``not_applicable`` contributes PASS (rank 0). If both stages are
    ``not_applicable`` the pipeline PASSes by definition (§3.3 rule).
    """
    stages = [s for s in (structural, semantic) if s.status != "not_applicable"]
    if not stages:
        return "PASS"
    worst = max(stages, key=lambda s: _VERDICT_RANK[s.status])
    return worst.status  # type: ignore[return-value]


def _worst_of_with_artifact(
    structural: StageResult,
    semantic: StageResult,
    artifact: StageResult,
) -> Verdict:
    """Worst-of across all three stages with the artifact-WARN-suppressed rule.

    Mirrors the live-workflow rule documented at
    ``observation_workflow.py:888-896``: the artifact_judge is a single
    LLM voice (gpt-4o-mini) that is documented false-positive prone on
    scribe artifacts that reference patient record data. Only its BLOCK
    contributes to the combined verdict; its WARN is informational.

    Concretely:
    - artifact PASS / WARN  → contributes "PASS" to the worst-of input set
    - artifact BLOCK        → contributes "BLOCK"
    - artifact not_applicable → contributes nothing (skipped or off-lane)
    """
    inputs = [s for s in (structural, semantic) if s.status != "not_applicable"]
    if artifact.status == "BLOCK":
        inputs.append(artifact)
    if not inputs:
        return "PASS"
    worst = max(inputs, key=lambda s: _VERDICT_RANK[s.status])
    return worst.status  # type: ignore[return-value]


def _verdict_flipped_by_stage(
    structural: StageResult,
    semantic: StageResult,
    artifact: StageResult,
    final_verdict: Verdict,
) -> str:
    """BRS-1: identify which stage contributed the max-severity input.

    Mirrors ``_worst_of_with_artifact``'s input-filtering rules (artifact
    only enters the candidate set on BLOCK; not_applicable stages are
    filtered out) and Python's ``max`` tie-break (first element wins on
    equal keys when iteration is ordered). The candidate list is built in
    ``(structural, semantic, artifact)`` order so tie-break per
    ``docs/research/AUDIT_bench_driven_reliability_2026-05-26.md`` (audit
    convention: structural > semantic > artifact, deterministic-stage-first)
    falls out naturally.

    Returns ``"none"`` when the final verdict is PASS — no stage worsened
    the baseline, so no attribution applies. Otherwise returns the name of
    the max-severity stage (``"structural"``, ``"semantic"``, or
    ``"artifact"``).
    """
    if final_verdict == "PASS":
        return "none"
    by_stage: list[tuple[str, StageResult]] = []
    if structural.status != "not_applicable":
        by_stage.append(("structural", structural))
    if semantic.status != "not_applicable":
        by_stage.append(("semantic", semantic))
    if artifact.status == "BLOCK":
        by_stage.append(("artifact", artifact))
    if not by_stage:
        return "none"
    name, _stage = max(by_stage, key=lambda kv: _VERDICT_RANK[kv[1].status])
    return name


def _has_high_severity(findings: list[Finding]) -> bool:
    return any(f.severity == "HIGH" for f in findings)


def _derive_gate_decision(verdict: Verdict, findings: list[Finding], gate_mode: bool) -> GateDecision:
    """SPEC §3.3 gate_decision derivation."""
    if verdict == "PASS":
        return "allow"
    if verdict == "WARN":
        if gate_mode:
            return "allow"
        return "regenerate"
    # verdict == BLOCK
    if _has_high_severity(findings):
        return "escalate"
    return "regenerate"


def _regenerate_hints(findings: list[Finding]) -> list[str] | None:
    """Return a prompt-oriented hint list when regeneration is actionable."""
    if not findings:
        return None
    hints: list[str] = []
    for f in findings:
        prefix = f.code or f.check_name or f.type
        hint = f"[{prefix}] {f.detail}"
        if f.field:
            hint += f" (field={f.field})"
        hints.append(hint)
    return hints


def _hash_request(request: PipelineRequest) -> str:
    """Deterministic request hash for dedup + idempotency (see §3.4)."""
    payload = {
        "artifact": request.artifact,
        "artifact_type": request.artifact_type,
        "context_kind": request.context_kind,
        "context": request.context,
        "org_id": request.org_id,
        "transformer_id": request.transformer_id,
        "validator_id": request.validator_id,
        "gate_mode": request.gate_mode,
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ── Orchestrator ──────────────────────────────────────────────────────────


class PipelineOrchestrator:
    """Composes transform → structural → semantic → verdict.

    Phase C wires structural + semantic for transcript AND source_message;
    transform is still skipped (Phase 2 / Task 46). context_kind=none
    short-circuits semantic with not_applicable.
    """

    def __init__(
        self,
        *,
        structural_stage: StructuralStage | None = None,
        semantic_stage: SemanticStage | None = None,
        artifact_stage: ArtifactStage | None = None,
        provenance_store: ProvenanceStore | None = None,
    ) -> None:
        self._structural_stage: StructuralStage = structural_stage or run_structural
        # Phase C: default semantic stage is the dispatcher that routes on
        # request.context_kind (transcript vs source_message).
        self._semantic_stage: SemanticStage = semantic_stage or run_semantic
        # EVAL-CLARITY-B6-1: default artifact stage runs single-judge
        # artifact_judge alongside the council so eval-pipeline runs surface
        # the four-pillar enrichment (faithfulness / completeness /
        # safety_flags) that live conversation runs already get via
        # ``observation_workflow.evaluate_artifacts``. The stage self-skips
        # when context_kind != "transcript", gate_mode=True, or context is
        # missing. Callers that already run the artifact_judge in their own
        # custom semantic stage (artifact_evaluator.evaluate_artifacts) opt
        # out by passing ``artifact_stage=_skipped_artifact_stage``.
        self._artifact_stage: ArtifactStage = artifact_stage or run_artifact
        self._provenance_store: ProvenanceStore = provenance_store or NoOpProvenanceStore()

    async def evaluate(self, request: PipelineRequest) -> PipelineResult:
        t0 = time.monotonic()

        logger.info(
            "pipeline_evaluate_start",
            extra={
                "org_id": request.org_id,
                "artifact_type": request.artifact_type,
                "context_kind": request.context_kind,
                "gate_mode": request.gate_mode,
                "agent_id": request.agent_id,
            },
        )

        # Stage 1 — STRUCTURAL
        structural = await self._structural_stage(request)

        # Stage 2 — SEMANTIC (Phase C: transcript + source_message route to the
        # council via the run_semantic dispatcher; context_kind=none skips).
        semantic_meta: dict = {"council_config": {"mode": "skipped"}}
        has_context = request.context is not None
        semantic_routable = request.context_kind in ("transcript", "source_message") and has_context
        if semantic_routable:
            semantic, semantic_meta = await self._semantic_stage(request)
        else:
            semantic = StageResult(status="not_applicable")

        # Stage 2.5 — ARTIFACT (EVAL-CLARITY-B6-1, transcript-only). Runs the
        # single-model artifact_judge so direct-orchestrator callers get the
        # four-pillar enrichment that the live observation_workflow already
        # surfaces via the separate evaluate_artifacts path. The stage's own
        # skip rules guard the actual LLM call (context_kind / gate_mode /
        # missing context); the orchestrator-side gate here is a fast-path
        # short-circuit so we don't even invoke the stage callable when we
        # already know it would skip.
        artifact_meta: dict[str, Any] = {}
        artifact_eligible = request.context_kind == "transcript" and has_context and not request.gate_mode
        if artifact_eligible:
            artifact, artifact_meta = await self._artifact_stage(request)
        else:
            artifact = StageResult(status="not_applicable")

        # Stage 3 — VERDICT (worst-of + gate_decision + findings union).
        # Findings union pulls structural + council semantic + artifact in
        # that order. The artifact-WARN-suppressed rule lives in
        # ``_worst_of_with_artifact``; findings still surface uniformly so
        # the audit-view three-column render carries every signal even when
        # an artifact WARN didn't move the final verdict.
        unioned_findings: list[Finding] = []
        unioned_findings.extend(structural.findings)
        unioned_findings.extend(semantic.findings)
        unioned_findings.extend(artifact.findings)

        verdict: Verdict = _worst_of_with_artifact(structural, semantic, artifact)
        # BRS-1: which stage flipped the verdict — sibling of worst-of with
        # the same input-filtering + artifact-WARN-suppression rules. Pure
        # observability; no impact on verdict or gate_decision.
        verdict_flipped_by_stage = _verdict_flipped_by_stage(
            structural, semantic, artifact, verdict
        )
        gate_decision: GateDecision = _derive_gate_decision(verdict, unioned_findings, request.gate_mode)
        regenerate_hints = (
            _regenerate_hints(unioned_findings)
            if gate_decision in ("regenerate", "escalate")
            and (semantic.status != "not_applicable" or artifact.status != "not_applicable")
            else None
        )

        stages_executed: list[str] = []
        stage_results: dict = {}
        if structural.status != "not_applicable":
            stages_executed.append("structural")
            stage_results["structural"] = structural
        if semantic.status != "not_applicable":
            stages_executed.append("semantic")
            stage_results["semantic"] = semantic
        if artifact.status != "not_applicable":
            stages_executed.append("artifact")
            stage_results["artifact"] = artifact
        stages_executed.append("verdict")

        duration_ms = int((time.monotonic() - t0) * 1000)

        # Cost tokens roll up across council semantic + artifact stages so
        # the persisted total reflects every LLM call attributed to this
        # request. Council retrieval / config / rationale stay
        # council-only at the top level (the artifact stage doesn't have
        # those concepts); artifact stage's own LLM-side metrics live on
        # ``stage_results["artifact"]`` and in artifact_meta cost_tokens.
        cost_tokens = dict(semantic_meta.get("cost_tokens") or {"prompt": 0, "completion": 0, "total": 0})
        artifact_cost = artifact_meta.get("cost_tokens") if isinstance(artifact_meta, dict) else None
        if isinstance(artifact_cost, dict):
            for key in ("prompt", "completion", "total"):
                cost_tokens[key] = int(cost_tokens.get(key, 0) or 0) + int(artifact_cost.get(key, 0) or 0)

        # BRS-1: hoist structural_template_pin from structural.metadata
        # (populated by run_structural when a profile resolved + validator
        # ran). None when stage status = not_applicable. The dict is built
        # in stages.py:run_structural from the single existing
        # /mappings/:id/apply response — no second etlp-mapper call here.
        structural_template_pin: StructuralTemplatePin | None = None
        if structural.status != "not_applicable":
            pin_data = structural.metadata.get("structural_template_pin")
            if isinstance(pin_data, dict):
                structural_template_pin = StructuralTemplatePin(**pin_data)

        # BRS council-reliability: surface whether the council semantic stage
        # errored (fallback WARN) so a WARN-on-error never counts as a graded
        # verdict. None when semantic didn't run (structural-only / none).
        council_error: bool | None = (
            bool(semantic_meta.get("council_error"))
            if semantic.status != "not_applicable"
            else None
        )

        # Plugin Phase-1 (D5): record the loaded-plugin set (active pack + tier + the gated
        # core∪pack contract/provider plugins) for this run. Default-safe — any failure degrades
        # to an empty snapshot rather than breaking the already-completed grade.
        try:
            from lithrim_bench.harness import plugins as _plugins

            _plugin_snapshot = _plugins.provenance_snapshot()
        except Exception:
            _plugin_snapshot = {"plugins": [], "active_pack": None, "pack_tier": None}

        provenance = PipelineProvenance(
            pipeline_run_id=str(uuid.uuid4()),
            org_id=request.org_id,
            timestamp=datetime.now(timezone.utc),
            request_hash=_hash_request(request),
            stages_executed=stages_executed,
            stage_results=stage_results,
            council_config=semantic_meta.get("council_config", {"mode": "skipped"}),
            judge_rationale=semantic_meta.get("judge_rationale"),
            sampling=semantic_meta.get("sampling"),
            case_outcome=semantic_meta.get("case_outcome"),
            kb_retrievals=semantic_meta.get("kb_retrievals", []),
            retrieval_stats=semantic_meta.get("retrieval_stats", {}),
            tool_calls=None,
            cost_tokens=cost_tokens,
            loaded_plugins=_plugin_snapshot["plugins"],
            active_pack=_plugin_snapshot["active_pack"],
            pack_tier=_plugin_snapshot["pack_tier"],
            # REL-OPS-1 O4: the bind-time dated-alias record (role → model + dated flag);
            # .get keeps the degraded-snapshot fallback above default-safe.
            model_bindings=_plugin_snapshot.get("model_bindings"),
            # Cycle 16: persist final orchestration summary so the audit-view
            # denormaliser doesn't have to re-derive verdict / findings from
            # stage_results. ``unioned_findings`` is the same list passed to
            # ``_derive_gate_decision`` above (structural+semantic union).
            artifact_type=request.artifact_type,
            verdict=verdict,
            gate_decision=gate_decision,
            findings=unioned_findings,
            structural_template_pin=structural_template_pin,
            verdict_flipped_by_stage=verdict_flipped_by_stage,  # type: ignore[arg-type]
            council_error=council_error,
        )

        # Fire-and-forget persistence — failures logged inside the store.
        await self._provenance_store.save(provenance, agent_id=request.agent_id)

        # Latency instrumentation (SPEC §4.2 NFR-1/NFR-2). Tags allow
        # downstream aggregation of p50/p95 per (context_kind × gate_mode).
        emit_timing(
            "pipeline.orchestrator.evaluate_ms",
            duration_ms,
            tags={
                "context_kind": request.context_kind,
                "gate_mode": str(request.gate_mode).lower(),
                "verdict": verdict,
            },
            org_id=request.org_id,
        )

        logger.info(
            "pipeline_evaluate_done",
            extra={
                "org_id": request.org_id,
                "pipeline_run_id": provenance.pipeline_run_id,
                "verdict": verdict,
                "gate_decision": gate_decision,
                "stages_executed": stages_executed,
                "duration_ms": duration_ms,
                "context_kind": request.context_kind,
                "gate_mode": request.gate_mode,
            },
        )

        return PipelineResult(
            verdict=verdict,
            gate_decision=gate_decision,
            findings=unioned_findings,
            duration_ms=duration_ms,
            structural=structural,
            semantic=semantic,
            artifact=artifact,
            transform=None,
            provenance=provenance,
            regenerate_hints=regenerate_hints,
            case_outcome=semantic_meta.get("case_outcome"),
        )
