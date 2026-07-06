"""Pipeline stage executors — structural + semantic for Phase B/C.

Thin wrappers over existing services. Each stage takes a ``PipelineRequest``
and returns a ``StageResult`` populated per SPEC §3.3:

- Structural: delegates to ``validate_artifact_structural`` and maps the legacy
  ``structural_verdict`` + ``structural_findings`` shape to the pipeline's
  ``StageResult`` contract. Skip when no validator (no ``validator_id`` AND no
  default profile for ``artifact_type``).
- Semantic: dispatched via ``run_semantic(request)`` which routes on
  ``context_kind``:
    * ``transcript``      → ``run_semantic_transcript``     (Lane 1 voice-scribe)
    * ``source_message``  → ``run_semantic_source_message`` (Lane 2 HIE batch — Phase C)
    * ``none``            → orchestrator short-circuits before calling this module.

All stage functions are standalone so the orchestrator can dispatch them (and
tests can patch them) without instantiating stateful collaborators.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from ..council.compliance_council import (
    CONTEXT_KIND_SOURCE_MESSAGE,
    CONTEXT_KIND_TRANSCRIPT,
    ComplianceCouncil,
    CouncilModel,
)
from ..council.llm_provider import get_sync_openai_client
from ..services.artifact_evaluator import validate_artifact_structural
from .models import (
    _DECISION_TO_VOTE,
    Finding,
    JudgeVote,
    PipelineRequest,
    StageResult,
    Verdict,
)
from .retrieval import retrieve_for_request

logger = logging.getLogger(__name__)


# Type aliases for DI in tests.
StructuralValidator = Callable[..., Awaitable[dict[str, Any]]]
CouncilEvaluator = Callable[[dict[str, Any]], dict[str, Any]]


# ── Severity + verdict mapping helpers ────────────────────────────────────

_SEVERITY_MAP = {
    "critical": "HIGH",
    "high": "HIGH",
    "medium": "MEDIUM",
    "moderate": "MEDIUM",
    "low": "LOW",
}


def _normalize_severity(raw: Any) -> str:
    if not isinstance(raw, str):
        return "MEDIUM"
    return _SEVERITY_MAP.get(raw.lower(), "MEDIUM")


def _decision_to_status(decision: str | None) -> Verdict:
    """Map council decision → pipeline Verdict (PASS/WARN/BLOCK)."""
    if decision == "approve":
        return "PASS"
    if decision == "reject":
        return "BLOCK"
    # needs_review, uncertain, None → WARN (conservative default)
    return "WARN"


# ── Structural stage ──────────────────────────────────────────────────────


async def run_structural(
    request: PipelineRequest,
    *,
    validator: StructuralValidator | None = None,
) -> StageResult:
    """Run structural validation against a Jute template.

    Skips cleanly when neither ``validator_id`` nor a default profile is
    configured for ``artifact_type``. Returns ``StageResult(status=...)``.
    """
    call = validator or validate_artifact_structural
    try:
        result = await call(
            artifact=request.artifact,
            artifact_type=request.artifact_type,
            org_id=request.org_id,
            etlp_mapping_id=(
                int(request.validator_id) if request.validator_id and str(request.validator_id).isdigit() else None
            ),
        )
    except Exception as exc:
        # Never raise — treat as WARN with a single finding so the pipeline
        # continues and the caller sees a real verdict + context rather than a
        # 5xx.
        logger.warning(
            "pipeline_structural_stage_error",
            extra={
                "org_id": request.org_id,
                "artifact_type": request.artifact_type,
                "error": str(exc),
            },
        )
        return StageResult(
            status="WARN",
            findings=[
                Finding(
                    type="structural",
                    severity="MEDIUM",
                    detail=f"structural_validation_error: {exc}",
                )
            ],
        )

    verdict = result.get("structural_verdict")
    skipped_reason = result.get("skipped_reason")

    # skipped_reason OR verdict is None → stage not applicable (no profile, or
    # etlp-mapper unavailable). Treat as ``not_applicable``; the worst-of step
    # elevates this to PASS if semantic is also skipped.
    if verdict is None or skipped_reason:
        return StageResult(status="not_applicable", findings=[])

    raw_findings = result.get("structural_findings") or []
    findings = [
        Finding(
            type=f.get("type", "structural"),
            severity=_normalize_severity(f.get("severity")),
            detail=f.get("detail", "structural check failed"),
            field=f.get("field"),
            check_name=f.get("check_name"),
        )
        for f in raw_findings
    ]

    evidence: list[dict[str, Any]] = []
    for check in result.get("structural_checks") or []:
        evidence.append(
            {
                "name": check.get("name"),
                "status": check.get("status"),
                "field": check.get("field"),
                "message": check.get("message"),
            }
        )

    # BRS-1: surface validator template + per-check coverage on
    # StageResult.metadata so the orchestrator can hoist it onto
    # PipelineProvenance.structural_template_pin AND the audit-view
    # denormaliser can populate ArtifactProfileRef / StructuralCheck rows
    # without _resolve_profile_for_run's Mongo round-trip (B7-9 closure
    # side-benefit). Pre-BRS-1 docs still hit the resolved_profile fallback;
    # both paths now coexist.
    mapping_id_raw = result.get("etlp_mapping_id")
    mapping_id: int | None = (
        int(mapping_id_raw) if isinstance(mapping_id_raw, (int, float)) else None
    )
    version_raw = result.get("profile_version")
    profile_version: int | None = (
        int(version_raw) if isinstance(version_raw, (int, float)) else None
    )
    profile_name = result.get("profile_name")
    metadata: dict[str, Any] = {
        "profile_name": profile_name,
        "etlp_mapping_id": mapping_id,
        "profile_version": profile_version,
        "structural_checks": list(result.get("structural_checks") or []),
    }
    if mapping_id is not None and isinstance(profile_name, str) and profile_name:
        metadata["structural_template_pin"] = {
            "mapping_id": mapping_id,
            "validator_name": profile_name,
            "profile_version": profile_version,
            "check_ids_run": list(result.get("check_ids_run") or []),
            "check_ids_failed": list(result.get("check_ids_failed") or []),
        }

    return StageResult(
        status=verdict,
        findings=findings,
        evidence=evidence,
        metadata=metadata,
    )


# ── Semantic stage (transcript only for Phase B) ──────────────────────────


def _artifact_content_for_council(artifact: Any) -> str:
    """Normalize artifact → string representation council expects."""
    if isinstance(artifact, str):
        return artifact
    try:
        import json

        return json.dumps(artifact, default=str)
    except Exception:  # pragma: no cover — defensive
        return str(artifact)


def _context_as_transcript(context: Any) -> str:
    if context is None:
        return ""
    if isinstance(context, str):
        return context
    if isinstance(context, dict):
        # Common shape: {"transcript": "..."} or structured turns — stringify.
        if "transcript" in context:
            return str(context.get("transcript", ""))
        try:
            import json

            return json.dumps(context, default=str)
        except Exception:  # pragma: no cover
            return str(context)
    return str(context)


async def _build_transcript_payload(
    request: PipelineRequest,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build council context for ``context_kind=transcript``.

    Returns ``(payload, retrieval_meta)`` where ``retrieval_meta`` is the
    orchestrator-surfaced view of what was retrieved (for
    ``pipeline_runs.provenance.kb_retrievals`` + ``semantic_meta``).
    """
    transcript = _context_as_transcript(request.context)
    # S31 Phase 2: extract per-segment timestamps from the context dict if
    # present. Whisper emits segments as
    # ``[{id, start (s), end (s), text}, ...]`` on
    # ``conversation_item.transcription.segments``; the calling layer
    # (``artifact_evaluator.evaluate_artifacts`` -> observation_workflow)
    # threads them through ``request.context = {"transcript": str,
    # "segments": [...]}`` so the council post-judge linkback can resolve
    # judge-emitted ``turn_ids`` to millisecond boundaries. Absent on
    # transcript-string callers (legacy / eval harness); the linkback
    # noops in that case.
    transcript_segments: list[dict[str, Any]] | None = None
    if isinstance(request.context, dict):
        segs = request.context.get("segments")
        if isinstance(segs, list) and segs:
            transcript_segments = segs
    retrieval = await retrieve_for_request(request)

    # REPRO-1 R1b: carry the case's config-declared structured source record — a `record` dict
    # (field name → value) supplied on the dict context alongside the transcript — onto
    # call_context so the authored stage can fold it into the judge-visible context. Data-driven:
    # the field NAMES are whatever the caller declared (never hardcoded here). Absent (string
    # context / no record) → nothing added, the payload is byte-identical to before.
    record_context: dict[str, Any] = {}
    if isinstance(request.context, dict):
        _record = request.context.get("record")
        if isinstance(_record, dict) and _record:
            record_context["record"] = dict(_record)

    payload: dict[str, Any] = {
        "organization_id": request.org_id,
        "conversation_item_id": request.conversation_id or "pipeline_run",
        "query": "pipeline.evaluate(context_kind=transcript)",
        "call_context": {
            "transcript": transcript,
            "file_type": "text",
            **record_context,
        },
        "artifacts": [
            {
                "type": request.artifact_type,
                "content": _artifact_content_for_council(request.artifact),
                "target_system": request.artifact_type,
            }
        ],
        # Case-level Policy criterion (independent-axes model) — the authored stage layers it
        # onto policy_judge for this grade. Absent/None on the default path (no-op).
        "policy_criterion": request.policy_criterion,
    }

    if retrieval is not None:
        # Shape for transcript path = compliance_workflow._build_context_payload:
        # retrieval.matches (HIPAA) + top-level clinical_context / medication_context.
        payload["retrieval"] = {
            "matches": retrieval.get("matches") or [],
        }
        payload["clinical_context"] = retrieval.get("clinical_context") or []
        payload["medication_context"] = retrieval.get("medication_context") or []

    # S31 Phase 2: stash segments on payload so _run_council_and_map can
    # forward them into _findings_from_evidence_summary for post-judge
    # turn-timestamp linkback. Not consumed by the council itself (judges
    # see the transcript text only, not raw segment metadata).
    if transcript_segments:
        payload["transcript_segments"] = transcript_segments

    # Vendored addition (Bench salvage): forward agent-type context so the
    # council selects the category-specialised prompt branch (e.g. scribe).
    # Matches how the analyze flow judges a typed agent.
    if request.agent_metadata:
        payload["agent_metadata"] = request.agent_metadata

    return payload, retrieval


def _findings_from_evidence_summary(
    evidence_summary: dict[str, Any],
    retrieval_matches: list[dict[str, Any]] | None = None,
    transcript_segments: list[dict[str, Any]] | None = None,
) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Collapse council tier-triggered violations into (findings, evidence_rows).

    S24 (Phase 5 Cycle 9): consensus aggregation in
    ``ComplianceCouncil._apply_consensus`` now carries the first-rank judge's
    ``evidence_spans`` on each tier entry. Findings emit as before (verdict
    logic untouched); parallel ``evidence_rows`` materialize the chunk-cited
    spans into ``StageResult.evidence`` so ``pipeline_runs.stage_results.semantic``
    surfaces the judge's citations.

    ``evidence_rows`` shape::

        [{"violation_code": str, "judge": Optional[str],
          "spans": List[Dict[str, Any]]}, ...]

    Only tier entries with non-empty spans contribute a row — keeps the audit
    trail free of ``{spans: []}`` placeholders when a judge flagged but didn't
    cite.

    S30 (Phase 5 Cycle 14): when ``retrieval_matches`` is passed, Tier A/B
    chunk-id injection runs inline (before Finding construction) so each
    emitted ``Finding.chunk_id`` captures the first span's chunk_id. Caller
    at :func:`_run_semantic_stage` delegates the linkback here instead of a
    separate post-hoc ``_inject_chunk_ids(evidence_rows, ...)`` call —
    guarantees Finding and evidence_row stay in lockstep. Judge-emitted
    chunk_ids (Tier 0, when the judge already encoded one) survive unchanged.
    """

    findings: list[Finding] = []
    evidence_rows: list[dict[str, Any]] = []

    def _mk(severity: str, tier_entries: list[dict[str, Any]]) -> None:
        for entry in tier_entries or []:
            violation = entry.get("violation") or "UNKNOWN_VIOLATION"
            judge_count = entry.get("judge_count")
            detail = f"{violation} (judges={judge_count})" if judge_count is not None else violation
            spans = entry.get("evidence_spans") or []
            if retrieval_matches and spans:
                _inject_chunk_ids_for_spans(spans, retrieval_matches)
            # Phase 2 (S31, 2026-04-29): post-judge audio-timestamp linkback.
            # Council judges emit spans with {quote, turn_ids} only; resolve
            # turn_ids → segment timestamps so the first-span pick below
            # propagates start_ms / end_ms / speaker onto the Finding.
            # Mirror of the chunk_id linkback right above.
            if transcript_segments and spans:
                _inject_turn_timestamps_for_spans(spans, transcript_segments)
            chunk_id: str | None = None
            start_ms: int | None = None
            end_ms: int | None = None
            speaker: str | None = None
            # Pick first span that carries each value. Mirrors the chunk_id
            # pattern: truthful absence is fine (None propagates). For
            # fabricated content, no transcript span will match the artifact
            # claim, so timestamps stay None — the finding still surfaces,
            # without an audio anchor (which is itself the audit signal).
            for span in spans:
                if not isinstance(span, dict):
                    continue
                if chunk_id is None:
                    cid = span.get("chunk_id")
                    if isinstance(cid, str) and cid:
                        chunk_id = cid
                if start_ms is None:
                    sm = span.get("start_ms")
                    if sm is not None:
                        start_ms = sm
                        end_ms = span.get("end_ms")
                        speaker = span.get("speaker")
                if chunk_id is not None and start_ms is not None:
                    break
            findings.append(
                Finding(
                    type="semantic",
                    severity=severity,
                    detail=detail,
                    code=violation,
                    chunk_id=chunk_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    speaker=speaker,
                )
            )
            if spans:
                evidence_rows.append(
                    {
                        "violation_code": violation,
                        "judge": entry.get("judge"),
                        "spans": spans,
                    }
                )

    _mk("HIGH", evidence_summary.get("tier1_triggered") or [])
    _mk("HIGH", evidence_summary.get("tier2_triggered") or [])
    _mk("MEDIUM", evidence_summary.get("tier2_flagged") or [])
    _mk("MEDIUM", evidence_summary.get("tier3_flagged") or [])
    return findings, evidence_rows


_MIN_CHUNK_ID_TOKEN_LEN = 3


def _inject_chunk_ids_for_spans(
    spans: list[dict[str, Any]],
    retrieval_matches: list[dict[str, Any]],
) -> None:
    """Mutate ``spans`` in-place — inject ``chunk_id`` on each span whose
    quote string-contains a retrieval match's ``metadata.code`` or
    ``metadata.section_label`` as a whole token.

    Deterministic, first-match-wins per span, no fallback slug. An absent
    ``chunk_id`` is truthful; a fabricated one would be misleading. Phase 5
    Cycle 10 backstop for judges that don't emit chunk_id despite Cycle 8's
    CITATION RULE. chunk_id format aligns with
    ``compliance_council._derive_chunk_id`` (``"<namespace>:<code|label>"``).

    Tier A (code) normalises both sides by stripping ``.`` so dotted judge
    quotes (``"E11.9"``) match KB's undotted form (``"E119"``); the emitted
    chunk_id preserves the KB's native form. Span-level variant of the
    original evidence-rows helper (S30, Cycle 14 split) so
    :func:`_findings_from_evidence_summary` can drive injection directly on
    tier-entry spans before Finding construction.
    """
    if not spans or not retrieval_matches:
        return
    for span in spans:
        if not isinstance(span, dict):
            continue
        if span.get("chunk_id"):
            continue
        quote = span.get("quote")
        if not isinstance(quote, str) or not quote:
            continue
        quote_norm = quote.replace(".", "")
        for match in retrieval_matches:
            metadata = match.get("metadata") or {}
            namespace = match.get("namespace")
            if not namespace:
                continue
            code = metadata.get("code")
            if (
                isinstance(code, str)
                and len(code) >= _MIN_CHUNK_ID_TOKEN_LEN
                and re.search(rf"\b{re.escape(code)}\b", quote_norm)
            ):
                span["chunk_id"] = f"{namespace}:{code}"
                break
            label = metadata.get("section_label")
            if (
                isinstance(label, str)
                and len(label) >= _MIN_CHUNK_ID_TOKEN_LEN
                and re.search(rf"\b{re.escape(label)}\b", quote)
            ):
                span["chunk_id"] = f"{namespace}:{label}"
                break


def _inject_chunk_ids(
    evidence_rows: list[dict[str, Any]],
    retrieval_matches: list[dict[str, Any]],
) -> None:
    """Evidence-row-level wrapper — preserved for existing call sites and
    tests. Delegates to :func:`_inject_chunk_ids_for_spans`. New call sites
    should prefer the span-level helper so Finding.chunk_id propagation stays
    in lockstep (S30, Cycle 14)."""
    if not evidence_rows or not retrieval_matches:
        return
    for row in evidence_rows:
        _inject_chunk_ids_for_spans(row.get("spans") or [], retrieval_matches)


def _inject_turn_timestamps_for_spans(
    spans: list[dict[str, Any]],
    transcript_segments: list[dict[str, Any]],
) -> None:
    """Mutate ``spans`` in-place — inject ``start_ms`` / ``end_ms`` /
    ``speaker`` on each span whose ``turn_ids`` reference a transcript segment.

    Phase 2 of the eight-link evidence chain (S31, 2026-04-29). Mirror of the
    chunk_id linkback pattern at :func:`_inject_chunk_ids_for_spans`. Council
    judges (gpt-4o) emit evidence spans with ``{quote, turn_ids}`` only — no
    raw timestamps because the LLM doesn't see segment millisecond boundaries.
    Whisper transcription produces segments with ``{id, start, end, text}``
    where ``start`` / ``end`` are seconds (float). This helper resolves the
    judge's ``turn_ids`` to the matching segment and injects millisecond
    timestamps onto the span so the Phase 1 first-span-pick in
    :func:`_findings_from_evidence_summary._mk` propagates timestamps onto
    the persisted ``Finding``.

    Deterministic, first-match-wins per span (mirrors chunk_id rule).
    Truthful absence preferred over fabrication: spans whose ``turn_ids``
    don't resolve to any segment keep ``start_ms=None``. Spans that already
    carry ``start_ms`` (e.g. HIPAA observation spans from
    :mod:`evidence_extraction`) are left untouched.

    ``transcript_segments`` shape (from Whisper / faster-whisper, persisted
    on ``conversation_item.transcription.segments``)::

        [{"id": int, "start": float (s), "end": float (s), "text": str}, ...]

    ``spans`` shape (judge-emitted, after council consensus)::

        [{"quote": str, "turn_ids": [int]}, ...]

    Speaker labels: optional. If a segment carries a ``speaker`` key it
    propagates onto the span; otherwise stays ``None``. Whisper's plain output
    doesn't include speaker diarization, so most demo runs leave speaker
    truthfully ``None`` (which is fine — UI renders this gracefully).
    """
    if not spans or not transcript_segments:
        return
    # Index segments by id (str + int variants) for fast lookup. Whisper
    # emits int ids; some upstream serializers may stringify them.
    seg_by_id: dict[Any, dict[str, Any]] = {}
    for seg in transcript_segments:
        if not isinstance(seg, dict):
            continue
        sid = seg.get("id")
        if sid is None:
            continue
        seg_by_id[sid] = seg
        # Also index stringified for resilience (judges sometimes return strings)
        with contextlib.suppress(Exception):
            seg_by_id[str(sid)] = seg

    for span in spans:
        if not isinstance(span, dict):
            continue
        if span.get("start_ms") is not None:
            # Already populated (e.g. HIPAA observation span). Don't overwrite.
            continue
        turn_ids = span.get("turn_ids") or []
        if not turn_ids:
            continue
        for tid in turn_ids:
            seg = seg_by_id.get(tid)
            if seg is None:
                # Try int → str / str → int coercion
                try:
                    seg = seg_by_id.get(int(tid)) if not isinstance(tid, int) else seg_by_id.get(str(tid))
                except (TypeError, ValueError):
                    seg = None
            if seg is None:
                continue
            start_s = seg.get("start")
            end_s = seg.get("end")
            if start_s is not None:
                # Whisper emits seconds (float); convert to ms (int) for
                # alignment with EvidenceSpan.start_ms / end_ms which the
                # transcription pipeline already uses for HIPAA observation
                # spans. Round to nearest ms.
                span["start_ms"] = int(round(float(start_s) * 1000))
            if end_s is not None:
                span["end_ms"] = int(round(float(end_s) * 1000))
            speaker = seg.get("speaker")
            if speaker:
                span["speaker"] = speaker
            break  # first-match-wins, like chunk_id pattern


def _synth_reason(decision: str, finding_codes: list[str]) -> str:
    """Synthesize a legible one-line justification when the per-judge seam carries
    no prose. The DSPy judge seam (``judges_dspy.Judge.forward``, FROZEN) emits
    ``{model, decision, confidence, findings, errors}`` — it has no ``summary`` /
    ``rationale``, so the authored in-process path would otherwise render an empty
    ``reason`` (S-BS-66). We reconstruct one from the data the seam DOES carry — the
    decision + the grounded finding codes — so ``/v1/runs/{id}/audit`` + the council
    view read legibly. A clean approve (no findings) keeps ``reason`` empty: there is
    nothing to justify."""
    if finding_codes:
        return f"{decision or 'flagged'} — {', '.join(finding_codes)}"
    return ""


def _judge_votes_from_models(
    models: list[dict[str, Any]],
    model_lookup: dict[str, str] | None = None,
) -> list[JudgeVote]:
    """Build structured per-judge votes from council model results.

    EVAL-CLARITY-B7-2: preserves the full attribution data (rationale,
    findings, LLM model id) that was previously discarded.

    ``model_lookup`` maps role name -> LLM model string (e.g.
    ``{"policy_judge": "gpt-4.1"}``). Built from ``council.models``
    in the caller closure. On the DI-injected (authored DSPy) path it is
    absent ({}); JudgeVote.model then falls back to the seam's own ``model``
    field (the role name) so the audit is never blank (S-BS-66).
    """
    if not model_lookup:
        model_lookup = {}
    votes: list[JudgeVote] = []
    for m in models or []:
        role = m.get("model") or "unknown"
        decision = m.get("decision") or ""
        vote = _DECISION_TO_VOTE.get(decision, "WARN")
        raw_findings = m.get("findings") or []
        finding_codes = [
            f.get("taxonomy_code")
            for f in raw_findings
            if isinstance(f, dict) and f.get("taxonomy_code")
        ]
        raw_conf = m.get("confidence")
        # Per-reviewer sampling distribution (judge_call): the independent variance + k for
        # THIS axis, surfaced so the UI shows each reviewer's own stability (never averaged).
        samp = m.get("sampling") or {}
        raw_var = samp.get("score_variance")
        raw_k = samp.get("k")
        raw_scores = samp.get("scores_raw")
        # R2c dual-confidence: the reviewer's OWN sampled decision aggregate (score_mean) —
        # a SECOND, independent channel from the logprob confidence below. Kept distinct so
        # the logprob never overwrites the self-report on the read surface.
        raw_self = samp.get("score_mean")
        votes.append(JudgeVote(
            judge_role=role,
            vote=vote,
            # Preserve None (e.g. Mistral has no logprobs under v2) rather than
            # coercing to 0.0, which would read as "0% confident". See
            # PIPELINE_GRADING_AUDIT_2026-05-28 §3.
            confidence=float(raw_conf) if isinstance(raw_conf, (int, float)) else None,
            # R2c: the self-report channel — None when unsampled (no score_mean), never coerced.
            confidence_self=float(raw_self) if isinstance(raw_self, (int, float)) else None,
            reason=m.get("summary") or m.get("rationale") or _synth_reason(decision, finding_codes),
            # The real deployment, in priority: the prompt-council's role→model lookup;
            # then the authored seam's own ``llm_model`` (VOTE-MODEL-1 — the LM the judge
            # graded on); then the role name (S-BS-66 back-compat — never blank).
            model=model_lookup.get(role) or m.get("llm_model") or m.get("model") or "",
            findings=finding_codes,
            variance=float(raw_var) if isinstance(raw_var, (int, float)) else None,
            k=int(raw_k) if isinstance(raw_k, (int, float)) else None,
            # R2c: the per-sample decision scores — the readable K-split. List-or-None,
            # never coerced (an absent distribution must not read as a unanimous one).
            scores_raw=(
                [float(s) for s in raw_scores]
                if isinstance(raw_scores, list) and raw_scores
                else None
            ),
        ))
    return votes


def _council_for_mode(gate_mode: bool) -> ComplianceCouncil:
    """Return council instance for the requested mode.

    gate_mode=True drops to 1 judge (policy_judge) — the Lane 1 fast path
    (SPEC §4.1 FR-5, NFR-1). Judge is reused across context_kind values; the
    source_message role prompt is selected at _invoke_openai time based on
    context_kind, not based on model.name.
    """
    if not gate_mode:
        return ComplianceCouncil()
    _, council_model = get_sync_openai_client(purpose="council")
    return ComplianceCouncil(
        models=[
            CouncilModel(
                name="policy_judge",
                provider="openai",
                model=council_model,
            )
        ]
    )


async def _build_source_message_payload(
    request: PipelineRequest,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Council payload for ``context_kind=source_message`` (SPEC §3.2).

    ``request.context`` is the raw or parsed source (FHIR bundle dict,
    HL7v2 pipe-delimited string, CSV row, etc.). No transcript semantics.

    Returns ``(payload, retrieval_meta)``. The authored judge does not yet
    consume ``retrieval``; we inject it so pipeline_runs provenance captures
    which schema / code KBs were queried. A future cycle extends the judge
    to consume.
    """
    # Source format hint — used by the judge prompt for parse-strategy hints.
    source_format = "unknown"
    src = request.context
    if isinstance(src, dict):
        if "resourceType" in src or "entry" in src or "bundle_type" in src:
            source_format = "fhir"
        elif "segments" in src or "msh" in src:
            source_format = "hl7v2"
        elif "columns" in src or "rows" in src:
            source_format = "csv"
    elif isinstance(src, str):
        stripped = src.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            source_format = "fhir"
        elif stripped.startswith("MSH|") or "\rMSH|" in src or "\nMSH|" in src:
            source_format = "hl7v2"
        elif "," in stripped.split("\n", 1)[0] and "\n" in src:
            source_format = "csv"

    retrieval = await retrieve_for_request(request)

    payload: dict[str, Any] = {
        "organization_id": request.org_id,
        "conversation_item_id": request.conversation_id or "pipeline_run",
        "query": "pipeline.evaluate(context_kind=source_message)",
        # target_profile hint: until ArtifactProfile lookup is wired (Phase D+),
        # use artifact_type as the declared target so the judge prompt's
        # "TARGET PROFILE (declared)" line isn't empty.
        "target_profile": request.artifact_type,
        "call_context": {
            "source_message": src,
            "source_format": source_format,
            "file_type": source_format,
        },
        "artifacts": [
            {
                "type": request.artifact_type,
                "content": _artifact_content_for_council(request.artifact),
                "target_system": request.artifact_type,
            }
        ],
        # Case-level Policy criterion (independent-axes model) — the authored stage layers it
        # onto policy_judge for this grade. Absent/None on the default path (no-op).
        "policy_criterion": request.policy_criterion,
    }

    if retrieval is not None:
        payload["retrieval"] = {
            "matches": retrieval.get("matches") or [],
        }

    return payload, retrieval


def _run_council_and_map(
    *,
    request: PipelineRequest,
    payload: dict[str, Any],
    context_kind: str,
    council_evaluate: CouncilEvaluator | None,
    retrieval: dict[str, Any] | None = None,
) -> Callable[[], Awaitable[tuple[StageResult, dict[str, Any]]]]:
    """Shared machinery: invoke council, map result → (StageResult, meta).

    ``retrieval`` is the per-request retrieval payload produced by the
    pipeline retrieval orchestrator. Its ``matches`` land on
    ``provenance.kb_retrievals``; its ``stats`` land under
    ``semantic_meta.retrieval_stats`` for observability.
    """

    if council_evaluate is None:
        council = _council_for_mode(request.gate_mode)

        # B7-5 sub (c): when eval_mode is set the council derives a per-
        # (case, judge) seed so re-runs of the same eval case produce
        # byte-identical reason paragraphs + votes. The eval-external path
        # populates ``conversation_id`` as ``run:{run_id}:case:{case_id}``
        # — strip the run prefix so the seed is stable across runs. Live
        # paths build their own ComplianceCouncil and never reach this seam.
        eval_case_id: str | None = None
        if request.eval_mode and request.conversation_id:
            cid = request.conversation_id
            marker = ":case:"
            idx = cid.find(marker)
            eval_case_id = cid[idx + len(marker):] if idx >= 0 else cid

        def _call(p: dict[str, Any]) -> dict[str, Any]:
            return council.evaluate(
                p,
                context_kind=context_kind,
                gate_mode=request.gate_mode,
                case_id=eval_case_id,
            )

        evaluator: CouncilEvaluator = _call
        council_config = {
            "mode": "gate" if request.gate_mode else "full",
            "context_kind": context_kind,
            "judges": [m.name for m in council.models],
        }
        # B7-2: map role name -> LLM model string for JudgeVote.model
        _model_lookup: dict[str, str] = {m.name: m.model for m in council.models}
    else:
        evaluator = council_evaluate
        council_config = {
            "mode": "gate" if request.gate_mode else "full",
            "context_kind": context_kind,
            "judges": ["injected"],
        }
        _model_lookup = {}

    # Flatten retrieval for provenance. kb_retrievals records (namespace,
    # score, source, chunk_id-ish) tuples — enough for the acceptance Mongo
    # query to confirm retrieval fired without round-tripping chunk text.
    kb_retrievals: list[dict[str, Any]] = []
    retrieval_stats: dict[str, Any] = {}
    if retrieval:
        retrieval_stats = retrieval.get("stats") or {}
        for m in retrieval.get("matches") or []:
            kb_retrievals.append(
                {
                    "namespace": m.get("namespace") or "hipaa",
                    "score": m.get("score"),
                    "source": m.get("source"),
                    "id": m.get("vector_id") or m.get("chunk_id") or m.get("id"),
                }
            )
        for r in retrieval.get("clinical_context") or []:
            kb_retrievals.append(
                {
                    "namespace": "clinical-escalation",
                    "score": r.get("score"),
                    "source": r.get("domain"),
                    "id": r.get("heading"),
                }
            )
        for r in retrieval.get("medication_context") or []:
            kb_retrievals.append(
                {
                    "namespace": "medication-safety",
                    "score": r.get("score"),
                    "source": r.get("medication"),
                    "id": r.get("heading"),
                }
            )

    async def _runner() -> tuple[StageResult, dict[str, Any]]:
        try:
            council_result: dict[str, Any] = await asyncio.to_thread(evaluator, payload)
        except Exception as exc:
            logger.warning(
                "pipeline_semantic_stage_error",
                extra={
                    "org_id": request.org_id,
                    "artifact_type": request.artifact_type,
                    "context_kind": context_kind,
                    "error": str(exc),
                },
            )
            return (
                StageResult(
                    status="WARN",
                    findings=[
                        Finding(
                            type="semantic",
                            severity="MEDIUM",
                            detail=f"semantic_evaluation_error: {exc}",
                        )
                    ],
                ),
                {
                    "council_config": council_config,
                    "kb_retrievals": kb_retrievals,
                    "retrieval_stats": retrieval_stats,
                    # The council raised (429/timeout/etc.) — this WARN is a
                    # fallback, NOT a graded verdict. Surface it so a
                    # WARN-on-error never silently counts as evaluated.
                    "council_error": True,
                    "council_error_detail": str(exc),
                },
            )

        consensus = council_result.get("consensus") or {}
        decision = consensus.get("decision")
        # Independent-axes outcome (the authored rule table): when present it IS the case
        # verdict — the three reviewers are not aggregated into a consensus decision. Falls
        # back to the consensus decision when absent (non-authored / legacy paths).
        case_outcome = council_result.get("case_outcome")
        if case_outcome:
            from lithrim_bench.runtime.council.outcomes import case_outcome_to_verdict

            status = case_outcome_to_verdict(case_outcome)
        else:
            status = _decision_to_status(decision)

        evidence_summary = council_result.get("evidence_summary") or {}
        retrieval_matches = retrieval.get("matches") or [] if retrieval else []
        # S31 Phase 2: pass transcript segments (when present) so judge-emitted
        # spans get audio timestamps injected before the first-span pick.
        # `_build_transcript_payload` extracts segments from the request
        # context dict; for non-transcript paths (source_message) the field
        # is absent and the linkback noops.
        transcript_segments = payload.get("transcript_segments") or None
        findings, evidence_rows = _findings_from_evidence_summary(
            evidence_summary,
            retrieval_matches=retrieval_matches,
            transcript_segments=transcript_segments,
        )
        judge_votes = _judge_votes_from_models(
            council_result.get("models") or [],
            model_lookup=_model_lookup,
        )

        # S-BS-66: on the injected (authored DSPy) path the roster is built before
        # the trio is known, so it lands as the placeholder ["injected"]. Now that
        # the result is in, project the REAL role names off the per-judge seam (each
        # seam dict's ``model`` field is its role) so the council view's "configured"
        # roster reads legibly instead of "injected".
        if council_config.get("judges") == ["injected"]:
            roster = [m.get("model") for m in (council_result.get("models") or []) if m.get("model")]
            if roster:
                council_config["judges"] = roster

        prompt_tokens = 0
        completion_tokens = 0
        for m in council_result.get("models") or []:
            usage = m.get("usage") or {}
            prompt_tokens += int(usage.get("input_tokens", 0) or 0)
            completion_tokens += int(usage.get("output_tokens", 0) or 0)

        semantic_meta = {
            "council_config": council_config,
            "judge_rationale": {
                "decision": decision,
                "confidence": consensus.get("confidence"),
                "consensus": consensus.get("consensus"),
                "uncertainty": consensus.get("uncertainty"),
            },
            "cost_tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
            "kb_retrievals": kb_retrievals,
            "retrieval_stats": retrieval_stats,
            # True when every judge errored (consensus fell back to
            # needs_review with reason=insufficient_valid_models) — the
            # council ran but produced no usable verdict. False on a normally
            # graded result. Mirrors the except-branch council_error above.
            "council_error": consensus.get("reason") == "insufficient_valid_models",
        }

        # Sampling-layer telemetry (judge_call): each judge's per-grade score
        # distribution, when the authored stage attached it to the seam dict. Keyed by
        # role → {score_mean, score_variance, scores_raw, k}. Purely additive (absent on
        # the default k=1 non-authored paths); never feeds verdict derivation.
        sampling = {
            m.get("model"): m["sampling"]
            for m in (council_result.get("models") or [])
            if isinstance(m, dict) and m.get("sampling")
        }
        if sampling:
            semantic_meta["sampling"] = sampling

        # The named case outcome (independent-axes rule table), surfaced for provenance + UI.
        if case_outcome:
            semantic_meta["case_outcome"] = case_outcome

        return (
            StageResult(
                status=status,
                findings=findings,
                evidence=evidence_rows,
                judge_votes=judge_votes,
            ),
            semantic_meta,
        )

    return _runner


def _default_authored_evaluator() -> CouncilEvaluator:
    """The default council evaluator (both ``context_kind`` values) — the AUTHORED DSPy
    trio over the ACTIVE PACK, each production judge at its FULL pack lens.

    CE-PACK-6b-CLEAN D1 / CE-PACK-6c: when no evaluator is injected (the orchestrator
    default / ``LocalPipelineBackend`` / ``run_local_scribe``), the default transcript
    AND source_message grades run the authored path — the single live prompt source
    (OQ-1) — so neither the legacy ``ComplianceCouncil.build_prompt`` default council nor
    ``build_source_message_prompt`` is reached. Mirrors the
    6b-ROUTE pattern in ``scripts/run_eval.py`` (no-assignment → ``pack_lenses()[role]``
    over ``pack_production_judges()``). Heavy deps (``dspy`` via ``build_trio``, the
    pack ontology) are imported lazily here so the default-deps core stays import-clean.
    """
    from lithrim_bench.harness.ontology import load_ontology
    from lithrim_bench.harness.pack import (
        pack_lenses,
        pack_ontology_path,
        pack_production_judges,
    )
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator

    ontology = load_ontology(pack_ontology_path())
    lenses = pack_lenses()
    assignments = {
        role: sorted(lenses[role]) for role in pack_production_judges() if role in lenses
    }
    return build_authored_evaluator(ontology=ontology, assignments=assignments)


async def run_semantic_transcript(
    request: PipelineRequest,
    *,
    council_evaluate: CouncilEvaluator | None = None,
) -> tuple[StageResult, dict[str, Any]]:
    """Run the compliance council for ``context_kind=transcript``.

    When no evaluator is injected, the council grades via the AUTHORED stage — each
    production judge at its full pack lens (:func:`_default_authored_evaluator`) — so
    the legacy ``ComplianceCouncil.build_prompt`` default council is never reached
    (CE-PACK-6b-CLEAN D1). The ``context_kind=source_message`` path
    (:func:`run_semantic_source_message`) reroutes the same way (CE-PACK-6c) — the
    authored stage is the single live prompt source for both context kinds.
    """
    if council_evaluate is None:
        council_evaluate = _default_authored_evaluator()
    payload, retrieval = await _build_transcript_payload(request)
    runner = _run_council_and_map(
        request=request,
        payload=payload,
        context_kind=CONTEXT_KIND_TRANSCRIPT,
        council_evaluate=council_evaluate,
        retrieval=retrieval,
    )
    return await runner()


async def run_semantic_source_message(
    request: PipelineRequest,
    *,
    council_evaluate: CouncilEvaluator | None = None,
) -> tuple[StageResult, dict[str, Any]]:
    """Run the compliance council for ``context_kind=source_message`` (Lane 2).

    When no evaluator is injected, the council grades via the AUTHORED stage — each
    production judge at its full pack lens (:func:`_default_authored_evaluator`) — so
    the legacy ``ComplianceCouncil.build_source_message_prompt`` clinical prompt is
    never reached (CE-PACK-6c, mirroring the 6b-CLEAN transcript reroute). The authored
    stage is the single live prompt source for both context kinds. Evaluates the
    artifact for fidelity to the source payload; no transcript semantics.
    """
    if council_evaluate is None:
        council_evaluate = _default_authored_evaluator()
    payload, retrieval = await _build_source_message_payload(request)
    runner = _run_council_and_map(
        request=request,
        payload=payload,
        context_kind=CONTEXT_KIND_SOURCE_MESSAGE,
        council_evaluate=council_evaluate,
        retrieval=retrieval,
    )
    return await runner()


async def run_semantic(
    request: PipelineRequest,
    *,
    council_evaluate: CouncilEvaluator | None = None,
) -> tuple[StageResult, dict[str, Any]]:
    """Dispatch semantic stage based on ``request.context_kind``.

    ``none`` never reaches this function — the orchestrator short-circuits
    and returns ``StageResult(status="not_applicable")`` before calling.
    """
    if request.context_kind == CONTEXT_KIND_SOURCE_MESSAGE:
        return await run_semantic_source_message(request, council_evaluate=council_evaluate)
    # Default: transcript. ``context_kind="none"`` should have been handled
    # upstream; if it leaks through we treat it as transcript for safety.
    return await run_semantic_transcript(request, council_evaluate=council_evaluate)


# ── Artifact stage (transcript-only, eval-pipeline parity) ────────────────
#
# Phase 5 EVAL-CLARITY-B6-1 — runs the single-model artifact_judge
# (gpt-4o-mini) alongside the 3-judge council semantic stage so direct-
# orchestrator callers (eval_runner via /eval-runs/{id}) get the same
# faithfulness / completeness / safety_flags / findings enrichment that
# the live observation_workflow already gets via evaluate_artifacts.
#
# Skip rules (orchestrator-side, replicated here for safety):
#   - context_kind != "transcript"  (Lane 2 source_message keeps single-stage)
#   - gate_mode == True             (Lane 1 SLA preservation)
#   - request.context is None       (no transcript to compare against)
# Skipping returns ``StageResult(status="not_applicable")`` so the worst-of
# treatment matches the existing structural-skip path.
#
# Combined-verdict rule lives in the orchestrator: artifact stage's WARN
# is informational (does not move the council baseline). Only artifact
# BLOCK escalates the final verdict. Mirrors the live rule documented at
# ``observation_workflow.py:888-896``.

ArtifactJudgeRunner = Callable[..., dict[str, Any]]


def _artifact_evaluator_for_request() -> tuple[Any, ComplianceCouncil]:
    """Build a single-judge council instance for the artifact stage.

    Lazy-imports ``_run_artifact_judge`` to avoid a circular import: the
    artifact_evaluator module itself wraps :class:`PipelineOrchestrator`
    with custom DI'd stages and pulls from this module at call time.
    """
    from ..services.artifact_evaluator import _run_artifact_judge as _judge_runner

    _, artifact_model = get_sync_openai_client(purpose="mini")
    council = ComplianceCouncil(
        models=[
            CouncilModel(
                name="artifact_judge",
                provider="openai",
                model=artifact_model,
            )
        ]
    )
    return _judge_runner, council


def _findings_from_artifact_judge(
    legacy_findings: list[dict[str, Any]],
    transcript_segments: list[dict[str, Any]] | None = None,
) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Map artifact_judge findings to (Finding[], evidence_rows[]).

    Mirrors the shape produced by :func:`_findings_from_evidence_summary` so
    audit-view denormalisation stays uniform across council + artifact
    stages. Also resolves transcript_span quotes to Whisper segments for
    audio-anchor timestamps when ``transcript_segments`` is provided. The
    matcher is deterministic substring (same pattern as the artifact_
    evaluator's custom semantic stage in ``artifact_evaluator.py``).
    """
    findings: list[Finding] = []
    evidence_rows: list[dict[str, Any]] = []

    def _match_quote_to_segment(quote: str) -> dict[str, Any] | None:
        if not quote or not transcript_segments:
            return None
        quote_norm = quote.strip().lower()
        if not quote_norm:
            return None
        for seg in transcript_segments:
            if not isinstance(seg, dict):
                continue
            seg_text = (seg.get("text") or "").strip().lower()
            if seg_text and quote_norm in seg_text:
                return seg
        for seg in transcript_segments:
            if not isinstance(seg, dict):
                continue
            seg_text = (seg.get("text") or "").strip().lower()
            if seg_text and len(seg_text) >= 8 and seg_text in quote_norm:
                return seg
        return None

    for f in legacy_findings:
        if not isinstance(f, dict):
            continue
        finding_kwargs: dict[str, Any] = {
            "type": f.get("type", "semantic"),
            "severity": _normalize_severity(f.get("severity")),
            "detail": f.get("detail", "artifact check"),
            "field": f.get("field"),
            "check_name": f.get("check_name"),
            "code": f.get("code"),
        }
        chunk_id = f.get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id:
            finding_kwargs["chunk_id"] = chunk_id

        seg_match = _match_quote_to_segment(f.get("transcript_span") or "")
        if seg_match:
            start_s = seg_match.get("start")
            end_s = seg_match.get("end")
            if start_s is not None:
                finding_kwargs["start_ms"] = int(round(float(start_s) * 1000))
            if end_s is not None:
                finding_kwargs["end_ms"] = int(round(float(end_s) * 1000))
            speaker = seg_match.get("speaker")
            if speaker:
                finding_kwargs["speaker"] = speaker

        findings.append(Finding(**finding_kwargs))

        vcode = f.get("code") or f.get("check_name") or f.get("type")
        if not vcode:
            continue
        spans: list[dict[str, Any]] = []
        t_span = f.get("transcript_span")
        a_span = f.get("artifact_span")
        if isinstance(t_span, str) and t_span.strip():
            transcript_span_dict: dict[str, Any] = {"quote": t_span, "turn_ids": []}
            seg = _match_quote_to_segment(t_span)
            if seg:
                if seg.get("id") is not None:
                    transcript_span_dict["turn_ids"] = [seg.get("id")]
                if seg.get("start") is not None:
                    transcript_span_dict["start_ms"] = int(round(float(seg["start"]) * 1000))
                if seg.get("end") is not None:
                    transcript_span_dict["end_ms"] = int(round(float(seg["end"]) * 1000))
                if seg.get("speaker"):
                    transcript_span_dict["speaker"] = seg["speaker"]
            spans.append(transcript_span_dict)
        if isinstance(a_span, str) and a_span.strip():
            spans.append({"quote": a_span, "path": f.get("field") or "artifact"})
        if isinstance(chunk_id, str) and chunk_id and spans:
            target_span = next((s for s in spans if "path" in s), spans[0])
            target_span["chunk_id"] = chunk_id
        if spans:
            evidence_rows.append({"violation_code": str(vcode), "spans": spans})

    return findings, evidence_rows


async def run_artifact(
    request: PipelineRequest,
    *,
    artifact_judge_runner: ArtifactJudgeRunner | None = None,
) -> tuple[StageResult, dict[str, Any]]:
    """Run the single-model artifact_judge for ``context_kind=transcript``.

    Skips when the request is not eligible (source_message lane, gate-mode
    fast path, missing context). Eligible requests run gpt-4o-mini against
    the transcript+artifact pair and surface
    ``faithfulness_score`` / ``completeness_score`` / ``safety_flags`` on
    ``StageResult.metadata``. The audit-view denormaliser reads this
    metadata to populate the four-pillar summary alongside the council's
    semantic findings.
    """
    if request.context_kind != CONTEXT_KIND_TRANSCRIPT:
        return StageResult(status="not_applicable"), {}
    if request.gate_mode:
        return StageResult(status="not_applicable"), {}
    if request.context is None:
        return StageResult(status="not_applicable"), {}

    transcript = _context_as_transcript(request.context)
    transcript_segments: list[dict[str, Any]] | None = None
    if isinstance(request.context, dict):
        segs = request.context.get("segments")
        if isinstance(segs, list) and segs:
            transcript_segments = segs

    if not transcript:
        return StageResult(status="not_applicable"), {}

    artifact_payload: dict[str, Any] = {
        "type": request.artifact_type,
        "content": request.artifact,
        "target_system": request.artifact_type,
    }

    if artifact_judge_runner is None:
        runner, council = _artifact_evaluator_for_request()

        def _call(t: str, a: dict[str, Any], idx: int) -> dict[str, Any]:
            return runner(council, t, a, idx)

        invoke = _call
    else:
        invoke = artifact_judge_runner

    try:
        legacy = await asyncio.to_thread(invoke, transcript, artifact_payload, 0)
    except Exception as exc:
        logger.warning(
            "pipeline_artifact_stage_error",
            extra={
                "org_id": request.org_id,
                "artifact_type": request.artifact_type,
                "error": str(exc),
            },
        )
        return (
            StageResult(
                status="WARN",
                findings=[
                    Finding(
                        type="semantic",
                        severity="MEDIUM",
                        detail=f"artifact_evaluation_error: {exc}",
                    )
                ],
                metadata={
                    "faithfulness_score": None,
                    "completeness_score": None,
                    "safety_flags": [],
                },
            ),
            {"cost_tokens": {"prompt": 0, "completion": 0, "total": 0}},
        )

    verdict = legacy.get("verdict", "WARN")
    legacy_findings = [f for f in legacy.get("findings", []) if isinstance(f, dict)]
    findings, evidence_rows = _findings_from_artifact_judge(legacy_findings, transcript_segments)

    metadata: dict[str, Any] = {
        "faithfulness_score": legacy.get("faithfulness_score"),
        "completeness_score": legacy.get("completeness_score"),
        "safety_flags": list(legacy.get("safety_flags") or []),
    }

    stage_result = StageResult(
        status=verdict,
        findings=findings,
        evidence=evidence_rows,
        judge_votes=None,
        metadata=metadata,
    )

    meta: dict[str, Any] = {
        "cost_tokens": {"prompt": 0, "completion": 0, "total": 0},
    }
    return stage_result, meta


async def _skipped_artifact_stage(
    _request: PipelineRequest,
) -> tuple[StageResult, dict[str, Any]]:
    """Opt-out callable for callers that don't want the artifact stage to run.

    Used by ``artifact_evaluator.evaluate_artifacts`` (which already runs the
    artifact_judge as its custom semantic stage) and by tests that assert the
    legacy two-stage shape (``{"structural", "semantic"}``).
    """
    return StageResult(status="not_applicable"), {}
