"""Data contracts for the unified pipeline primitive.

Mirrors SPEC_unified_pipeline_primitive.md §3. Kept in one module so the
orchestrator, route, SDK, and tests all share a single source of truth.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Severity = Literal["HIGH", "MEDIUM", "LOW"]
StageStatus = Literal["PASS", "WARN", "BLOCK", "not_applicable"]
Verdict = Literal["PASS", "WARN", "BLOCK"]

# Map council decision vocabulary to pipeline verdict vocabulary.
_DECISION_TO_VOTE: dict[str, Verdict] = {
    "approve": "PASS",
    "needs_review": "WARN",
    "reject": "BLOCK",
}
GateDecision = Literal["allow", "regenerate", "escalate"]
ContextKind = Literal["transcript", "source_message", "none"]


class JudgeVote(BaseModel):
    """Structured per-judge vote persisted on pipeline_run.stage_results.semantic.

    EVAL-CLARITY-B7-2: enriches the previously sparse dict (decision/confidence/
    errors only) with the fields needed for trust attribution on the eval surface.
    """

    judge_role: str  # "policy_judge" | "risk_judge" | "behavior_judge"
    vote: Verdict  # mapped from council decision via _DECISION_TO_VOTE
    # None = no calibrated confidence available (e.g. Mistral exposes no
    # logprobs under v2). Must NOT be coerced to 0.0 — that conflates "no
    # signal" with "0% confident". See PIPELINE_GRADING_AUDIT_2026-05-28 §3.
    confidence: float | None = None
    # REPRO-1 R2c (dual-confidence): the reviewer's OWN self-reported decision aggregate —
    # the sampled ``score_mean`` (0.0 reject … 1.0 approve over k completions). Kept DISTINCT
    # from the logprob-derived ``confidence`` above so the two channels are readable side by
    # side (the logprob no longer silently overwrites the self-report). None when unsampled;
    # never coerced (an absent self-report must not read as 0% self-confident).
    confidence_self: float | None = None
    reason: str = ""
    model: str = ""  # LLM model id, e.g. "gpt-4.1" (NOT the role name)
    findings: list[str] = Field(default_factory=list)  # taxonomy codes
    # Sampling layer (judge_call): THIS reviewer's own score variance + completion count k
    # over its native-n samples. Surfaced so each axis's stability shows independently (the
    # reviewers are never aggregated). None when sampling wasn't recorded (k=1 / legacy).
    variance: float | None = None
    k: int | None = None
    # REPRO-1 R2c: the raw per-sample decision scores (0.0 reject / 0.5 needs_review /
    # 1.0 approve, one per completion) — the within-call verdict split ("3 BLOCK / 2 PASS")
    # derives from this. None when sampling wasn't recorded; never fabricated.
    scores_raw: list[float] | None = None


def _coerce_legacy_judge_votes(
    raw: Any,
) -> list[JudgeVote] | None:
    """Convert legacy dict-keyed-by-role judge_votes to List[JudgeVote].

    Legacy shape (pre-B7-2):
        {"policy_judge": {"decision": "approve", "confidence": 1.0, "errors": []}, ...}
    New shape (B7-2+):
        [{"judge_role": "policy_judge", "vote": "PASS", "confidence": 1.0, ...}, ...]

    Returns None when raw is None/empty so StageResult.judge_votes stays Optional.
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw  # already new shape or List[JudgeVote]
    if isinstance(raw, dict):
        out: list[dict[str, Any]] = []
        for role, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            decision = entry.get("decision", "")
            vote = _DECISION_TO_VOTE.get(decision, "WARN")
            raw_conf = entry.get("confidence")
            out.append({
                "judge_role": role,
                "vote": vote,
                # Preserve None (no calibrated signal); only coerce real numerics.
                "confidence": float(raw_conf) if isinstance(raw_conf, (int, float)) else None,
                "reason": "",
                "model": "",
                "findings": [],
            })
        return out if out else None
    return None


class Finding(BaseModel):
    """Single issue raised by a structural or semantic stage."""

    type: str  # "structural" | "semantic" | "transform"
    severity: Severity = "MEDIUM"
    detail: str
    field: str | None = None
    check_name: str | None = None
    code: str | None = None
    # Phase 5 Cycle 14 (S30): first evidence span's chunk_id, post Tier A/B
    # linkback (stages._inject_chunk_ids). Surfaces the KB citation the judge
    # leaned on — allows the audit view to render a traceable
    # quote → chunk pivot without denormalising ``evidence`` back from the
    # persisted stage_results. ``None`` when no span in the consensus
    # carried a chunk_id (truthful absence, not a fabricated slug).
    chunk_id: str | None = None
    # Audio-source linkback: first evidence span's audio segment timestamps
    # and speaker label, propagated from the transcript segment that fed the
    # span (``transcription_service.py``: ``word_timestamps=True``;
    # ``evidence_extraction.py:225``: ``EvidenceSpan(start_ms=..., end_ms=...)``).
    # Mirror the chunk_id pattern: pick from the first span that carries
    # values, ``None`` is truthful absence (e.g. fabricated content where no
    # source segment matches the artifact span). Closes the leak at
    # ``compliance.py:380`` where ``TranscriptSnippetResponse.timestamp_ms``
    # rendered ``None`` because the findings ETL had dropped it.
    start_ms: int | None = None
    end_ms: int | None = None
    speaker: str | None = None


class StageResult(BaseModel):
    """Uniform stage output for structural + semantic stages."""

    status: StageStatus
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    judge_votes: list[JudgeVote] | None = None  # semantic-stage only

    @model_validator(mode="before")
    @classmethod
    def _coerce_judge_votes(cls, values: Any) -> Any:
        if isinstance(values, dict) and "judge_votes" in values:
            values["judge_votes"] = _coerce_legacy_judge_votes(
                values["judge_votes"]
            )
        return values
    # Stage-level out-of-band metadata surfaced on the persisted pipeline_run
    # for the audit-view denormaliser. Documented keys:
    #   structural stage: profile_name, etlp_mapping_id, profile_version,
    #     structural_checks, structural_template_pin (BRS-1; see
    #     PipelineProvenance.structural_template_pin for the typed mirror)
    #   semantic stage: (none today)
    #   artifact stage: faithfulness_score, completeness_score, safety_flags
    # Optional + additive — callers that don't populate it stay backward-compat.
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransformResult(BaseModel):
    """Output of the optional transform stage."""

    applied: bool
    transformer_id: str | None = None
    output_summary: dict[str, Any] | None = None


class StructuralTemplatePin(BaseModel):
    """BRS-1: validator template the structural stage ran against.

    Records which mapping fired (mapping_id + validator_name + profile_version)
    and the per-check coverage the validator emitted (which checks ran, which
    failed). Sourced entirely from the existing
    ``/mappings/:id/apply`` response that ``_structural_validate`` already
    issues — no second etlp-mapper call.

    Persisted on ``PipelineProvenance.structural_template_pin``. Makes "did
    the validator cover the defect class" queryable in production logs,
    distinguishing "validator ran with coverage gap" from "validator ran
    with full coverage" — the load-bearing distinction the bench surfaced
    in ``lithrim-bench/docs/research/MEASUREMENT_AUDIT_2026-05-26.md`` §1.3
    (mapping 18 inspects 5 envelope fields, never the SOAP body).

    ``None`` on the parent provenance when stage status =
    ``not_applicable`` (no profile resolved, etlp-mapper unavailable, or
    context_kind=none).
    """

    mapping_id: int
    validator_name: str
    profile_version: int | None = None
    check_ids_run: list[str] = Field(default_factory=list)
    check_ids_failed: list[str] = Field(default_factory=list)


class PipelineProvenance(BaseModel):
    """Audit record persisted per pipeline run. See §3.4."""

    pipeline_run_id: str
    # RUNTRAIL-1 (SPEC_RUN_AUDIT_TRAIL.md §3 Lineage): the run_id a replay was derived
    # from — a replay is a NEW record that POINTS AT its baseline; it never overwrites it.
    # None for a fresh in_process/live (authoritative) grade. Additive + optional so every
    # existing persisted blob still parses (the Cycle-16 additive-field precedent).
    replay_of: str | None = None
    # RUNTRAIL-7 (SPEC_RUN_AUDIT_TRAIL.md §3 Identity): HOW this verdict was produced —
    # ``replay`` | ``in_process`` | ``live``. Computed in ``run_eval.run`` and stamped onto
    # the persisted blob at persist time (was previously written only to the API-response
    # dict, never the trail — seam S-RUNTRAIL-6-1). Additive + optional so every existing
    # persisted blob still parses (the RUNTRAIL-1 ``replay_of`` precedent).
    grade_path: str | None = None
    org_id: str
    timestamp: datetime
    request_hash: str
    stages_executed: list[str]
    # stage_results persists the per-stage verdict/findings/evidence so
    # downstream audit, eval harness §5.1 demo rendering, and compliance
    # reporting don't have to replay the pipeline to inspect stage-level
    # outcomes. Keyed by stage name ("structural" | "semantic"); stages
    # with status="not_applicable" are omitted to keep docs compact.
    # Added in Phase 5 Cycle 7 (seam S21).
    stage_results: dict[str, StageResult] = Field(default_factory=dict)
    council_config: dict[str, Any] = Field(default_factory=dict)
    judge_rationale: dict[str, Any] | None = None
    # Sampling-layer (judge_call) telemetry: per-role score distribution from the
    # native-n sampling — {role: {score_mean, score_variance, scores_raw, k}}. None on
    # the default k=1 non-authored paths; never feeds verdict derivation (additive).
    sampling: dict[str, Any] | None = None
    # The named case outcome (independent-axes rule table) — CRITICAL / POLICY_VIOLATION /
    # RISK_FLAG / FINDING / NEEDS_REVIEW / CLEAR. None on non-authored / legacy paths.
    case_outcome: str | None = None
    kb_retrievals: list[dict[str, Any]] = Field(default_factory=list)
    # Retrieval orchestrator stats surfaced for empirical observability of
    # the S20 retry-on-empty path. Populated by
    # ``app/services/pipeline/stages.py::_run_council_and_map``; keys come
    # from ``retrieve_for_request``'s ``payload["stats"]`` (queried /
    # failed namespaces, total_matches, duration_ms, and from Cycle 10
    # ``retry_attempted`` / ``retry_recovered`` when the retry path fires).
    # Added in Phase 5 Cycle 10 (seam S20).
    retrieval_stats: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] | None = None
    cost_tokens: dict[str, int] = Field(default_factory=dict)
    # Phase 5 Cycle 16: top-level summary fields persisted alongside
    # stage_results so the audit-view denormaliser (and external eval
    # surfaces) can read final orchestration outcomes without re-deriving
    # them from stage_results. These are populated from the in-memory
    # ``PipelineResult`` at orchestrator save time. Optional for back-compat
    # with older docs persisted before Cycle 16. The artifact_evaluator
    # concepts ``faithfulness_score`` / ``completeness_score`` are NOT
    # added here because the council semantic path does not compute them;
    # surfacing them as ``None`` on every council-path doc would be a
    # lying-by-default field. Those scores belong in a separate stage when
    # artifact_evaluator co-runs alongside the council.
    artifact_type: str | None = None
    verdict: str | None = None
    gate_decision: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    # BRS-1 (post-audit reframe, 2026-05-27): observability surfaces for
    # validator coverage + per-stage verdict attribution. Both default to
    # None so older persisted docs read cleanly through Pydantic v2 (mirrors
    # the Cycle-16 additive-field precedent for ``artifact_type`` etc.).
    # ``silent_confident_certification`` is intentionally NOT persisted — it
    # is a derived query pattern over (verdict_flipped_by_stage,
    # stage_results.structural.status, stage_results.semantic.status). See
    # ``docs/research/AUDIT_bench_driven_reliability_2026-05-26.md`` §5.1.
    structural_template_pin: StructuralTemplatePin | None = None
    verdict_flipped_by_stage: Literal["structural", "semantic", "artifact", "none"] | None = None
    # True when the council semantic stage errored (429/timeout) or every judge
    # errored (insufficient_valid_models) — the surfaced WARN is a fallback, not
    # a graded verdict. None when the semantic stage didn't run (structural-only
    # / context_kind=none) or on pre-existing docs. Lets downstream eval rollups
    # compute council_error_rate and exclude WARN-on-error from accuracy.
    council_error: bool | None = None
    # Plugin Phase-1 (D5): the loaded-plugin set + active pack/tier, recorded per run so an
    # audit can answer "which Core/Pro plugins were active for this eval" (SPEC §Data Contracts:
    # the load-time gate records the loaded set in the provenance blob). Default-safe:
    # loaded_plugins defaults to [] and active_pack/pack_tier to None, so older docs AND the
    # replay/live blobs (persisted as raw dicts, never re-parsed through this model) read cleanly
    # through Pydantic v2 — the Cycle-16 additive-field precedent (artifact_type etc.).
    loaded_plugins: list[dict[str, Any]] = Field(default_factory=list)
    active_pack: str | None = None
    pack_tier: str | None = None
    # REL-OPS-1 O4: the bind-time model-binding record — each role's resolved model id +
    # ``dated: true/false`` (``None`` when that judge bound no LM, e.g. offline predictors).
    # ``None`` on older docs / runs where no council was constructed. Additive + default-
    # safe (the Cycle-16/D5 precedent); observation-only, never feeds verdict derivation.
    model_bindings: list[dict[str, Any]] | None = None


class PipelineRequest(BaseModel):
    """Input to PipelineOrchestrator.evaluate. See §3.1."""

    artifact: dict[str, Any] | str
    artifact_type: str
    context_kind: ContextKind = "transcript"
    context: dict[str, Any] | str | None = None
    org_id: str
    agent_id: str | None = None
    transformer_id: str | None = None
    validator_id: str | None = None
    gate_mode: bool = False
    conversation_id: str | None = None
    idempotency_key: str | None = None
    # B7-5 sub (c): when True the council derives a per-(case, judge) seed
    # from ``conversation_id`` so re-running the same case produces byte-
    # identical reason paragraphs + votes. Live-conversation paths construct
    # their own ComplianceCouncil and never set this flag, so they keep the
    # default ``seed=42`` behavior.
    eval_mode: bool = False
    # The CASE-level Policy criterion (independent-axes model): the one criterion sentence
    # the policy reviewer applies to THIS case (Policy criteria are case-level, not global).
    # Threaded into the council payload; the authored stage layers it onto policy_judge's prompt
    # for this grade only. None → policy uses its global JudgeConfig.criterion (if any).
    policy_criterion: str | None = None
    # Vendored addition (Bench salvage): agent-type context. It historically selected
    # build_prompt's category-specialised prompt branch (e.g. the scribe branch), but
    # build_prompt was deleted in CE-PACK-6b-CLEAN and the authored path does not branch on
    # category — retained for provenance; the analyze flow (ObservationWorkflow) still
    # passes it via agent_metadata.
    agent_metadata: dict[str, Any] | None = None


class PipelineResult(BaseModel):
    """Output of PipelineOrchestrator.evaluate. See §3.3."""

    verdict: Verdict
    gate_decision: GateDecision
    findings: list[Finding] = Field(default_factory=list)
    duration_ms: int
    structural: StageResult
    semantic: StageResult
    # EVAL-CLARITY-B6-1: artifact stage runs the single-model artifact_judge
    # alongside the council so direct-orchestrator runs surface
    # faithfulness / completeness / safety_flags. Defaults to
    # ``not_applicable`` for backward compat with callers / tests that
    # constructed a ``PipelineResult`` without an artifact field.
    artifact: StageResult = Field(default_factory=lambda: StageResult(status="not_applicable"))
    transform: TransformResult | None = None
    provenance: PipelineProvenance
    regenerate_hints: list[str] | None = None
    # The named case outcome (independent-axes rule table): CRITICAL / POLICY_VIOLATION /
    # RISK_FLAG / FINDING / NEEDS_REVIEW / CLEAR. PRIMARY result; ``verdict`` (PASS/WARN/BLOCK)
    # is the mapped gate value underneath. None on non-authored / legacy paths.
    case_outcome: str | None = None


# ── Audit-view response models (Phase 5 Cycle 14 / S31) ─────────────────────
#
# Denormalised read of a persisted ``pipeline_run`` for the UI's three-column
# finding detail panel. Rows = findings; columns are bucketed by span
# provenance:
# - ``transcript`` — span carries ``turn_ids`` (judge quoted the transcript)
# - ``artifact`` — span carries a ``path`` (judge quoted the artifact / map)
# - ``source`` — span carries ``chunk_id`` (judge cited a KB chunk)
#
# Spans may fit multiple buckets; the column is a best-fit label — a span
# with both ``turn_ids`` and ``chunk_id`` falls to ``source`` since KB
# citations are the scarcer signal. Rendered as clickable rows in the UI,
# with ``source`` spans fetching detail via ``GET /v1/kb/chunks/{chunk_id}``.
AuditColumn = Literal["transcript", "artifact", "source"]


class AuditSpan(BaseModel):
    """One evidence span surfaced in the audit view."""

    column: AuditColumn
    quote: str
    chunk_id: str | None = None
    turn_ids: list[str] = Field(default_factory=list)
    path: str | None = None
    source_label: str | None = None
    # Phase 2 audio-linkback fields. Populated by
    # ``_inject_turn_timestamps_for_spans`` (council path) or by
    # ``artifact_evaluator._semantic_stage`` (legacy path) when a
    # transcript segment matches the span. ``None`` is truthful absence:
    # the span has no source segment, which is itself the negative-audit
    # signal for fabricated content. Mirror of the chunk_id pattern.
    start_ms: int | None = None
    end_ms: int | None = None
    speaker: str | None = None


class AuditFinding(BaseModel):
    """One finding row in the audit view."""

    failure_type: str
    severity: Severity
    judge: str | None = None
    chunk_id: str | None = None
    spans: list[AuditSpan] = Field(default_factory=list)
    # Phase 2 audio-linkback fields, hoisted to finding level. Picked from
    # the first span that carries a timestamp (mirrors the chunk_id hoist
    # in ``_findings_from_evidence_summary._mk``). Lets the eight-link UI
    # surface a single "audio segment" anchor per finding without making
    # the renderer scan the spans array.
    start_ms: int | None = None
    end_ms: int | None = None
    speaker: str | None = None


class ArtifactProfileRef(BaseModel):
    """Validator profile the structural stage ran against.

    Populated when the structural stage's captured metadata carries a
    recognised artifact profile (org-scoped or default). Null when the run
    skipped structural (no profile, etlp-mapper unavailable, or
    context_kind=none).

    B7-9d: ``etlp_mapping_url`` mirrors the field on StructuralFinding
    so UI consumers can render the "Validated against" badge as a
    clickable link even when there are no per-field findings to link
    from. Composed via ``_build_etlp_mapping_url``: PUBLIC_URL-only,
    stays ``None`` when ``ETLP_MAPPER_PUBLIC_URL`` is unset.
    """

    artifact_type: str | None = None
    profile_name: str | None = None
    etlp_mapping_id: int | None = None
    etlp_mapping_url: str | None = None
    profile_version: int | None = None


class StructuralCheck(BaseModel):
    """One check row from the structural validator's /mappings/:id/apply output."""

    name: str
    passed: bool
    severity: str | None = None
    extracted_value: Any | None = None
    detail: str | None = None


class StructuralFinding(BaseModel):
    """B7-6 typed structural failure with field attribution.

    Lifted from the persisted ``stage_results.structural.findings[*]`` shape
    by the audit-view denormaliser so consumers can render per-field detail
    (e.g., "subject.reference missing") without walking the generic
    AuditFinding span synthesis. Complements the existing untyped
    ``findings: List[AuditFinding]`` surface; never replaces it.

    Open seam (S7-6-1): ``expected`` and ``actual`` are nullable placeholders.
    Current Jute templates emit ``{name, status, field, message}`` without
    separating expected vs actual; richer templates that emit them will
    populate these fields without a schema change.

    B7-9: ``etlp_mapping_id`` + ``etlp_mapping_url`` carry the validator
    template the finding originated from so audit consumers can deep-link
    to the etlp-mapper resource that produced it. Both stay ``None`` when
    the structural stage didn't resolve a profile (no profile registered,
    pre-B7-9 persisted docs) or when ``ETLP_MAPPER_PUBLIC_URL`` is unset
    (mapping_id populated, url null; internal IP never leaks).
    """

    field_path: str | None = None
    validator_name: str | None = None
    severity: str
    message: str | None = None
    expected: str | None = None
    actual: str | None = None
    etlp_mapping_id: int | None = None
    etlp_mapping_url: str | None = None


class PillarsSummary(BaseModel):
    """Four-pillar + citations scorecard surfaced alongside the three-column
    findings panel. Each field defaults to ``None`` / empty so the UI can
    render a graceful "Not applicable" state on runs missing a stage."""

    faithfulness_score: float | None = None
    completeness_score: float | None = None
    safety_flags_count: int = 0
    safety_flags: list[str] = Field(default_factory=list)
    structural_passed: int | None = None
    structural_total: int | None = None
    grounded_citations_count: int = 0
    combined_verdict: str | None = None


class AuditView(BaseModel):
    """Full response shape for GET /v1/pipeline/runs/{run_id}/audit-view."""

    run_id: str
    org_id: str
    agent_id: str | None = None
    timestamp: datetime | None = None
    verdicts: dict[str, str | None] = Field(default_factory=dict)
    aggregates: dict[str, int] = Field(default_factory=dict)
    findings: list[AuditFinding] = Field(default_factory=list)
    # EVAL-CLARITY-B7-2: structured per-judge votes from the semantic stage.
    # Surfaces judge attribution (role, vote, confidence, rationale, findings)
    # so the UI's CouncilSummaryRow can render per-judge breakdown without
    # cross-referencing the compliance_report. None on pre-B7-2 docs and on
    # runs where the semantic stage was skipped.
    judge_votes: list[JudgeVote] | None = None
    # Cycle 14 fast-follow scope extension: 5-pillar summary + profile ref
    # so the Playground + ConversationDetail can render the full evaluation
    # scorecard without refetching the compliance_report. All three are
    # Optional / empty-default for backward-compat with pre-extension runs
    # and with test fixtures built before this change (HALT (f)).
    artifact_profile: ArtifactProfileRef | None = None
    pillars: PillarsSummary | None = None
    structural_checks: list[StructuralCheck] = Field(default_factory=list)
    # B7-6: typed structural failures with field attribution. Backward-compat:
    # default empty list so pre-B7-6 docs and runs without a structural stage
    # render cleanly. Coexists with the untyped ``findings`` surface above.
    structural_findings: list[StructuralFinding] = Field(default_factory=list)
    # BRS-5: hoist BRS-1's per-stage observability fields onto the audit-view
    # response. ``structural_template_pin`` + ``verdict_flipped_by_stage`` are
    # read verbatim from the persisted PipelineProvenance doc; on pre-BRS-1
    # docs they stay None.  ``silent_confident_certification`` is derived
    # on-read in ``_denormalise_audit_view`` (NOT persisted) per
    # ``docs/research/AUDIT_bench_driven_reliability_2026-05-26.md`` §5.1 —
    # True when ``verdict_flipped_by_stage="artifact"`` AND structural=PASS
    # AND semantic in {PASS, WARN}; None when ``verdict_flipped_by_stage``
    # is absent (pre-BRS-1 doc).
    structural_template_pin: StructuralTemplatePin | None = None
    verdict_flipped_by_stage: Literal["structural", "semantic", "artifact", "none"] | None = None
    silent_confident_certification: bool | None = None
    # True when the council semantic stage errored / all judges errored — the
    # verdict is a fallback WARN, not a graded result. None on pre-existing docs
    # and structural-only runs. Read verbatim from the persisted provenance.
    council_error: bool | None = None
