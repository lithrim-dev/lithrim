"""``ObservationState`` — the in-memory field contract the KPI pipeline threads.

Ported from ``lithrim-backend@mvp-ready`` ``observation_workflow.py:38`` (the
``ObservationState`` TypedDict). This is the **KPI-half subset**: the input,
processing, and KPI-extraction fields the recomposed pipeline
(``process_input_item … aggregate_kpis``) reads and writes.

The **compliance-tail fields are intentionally excluded** — they belong to the
documented hand-off seam to the already-recomposed compliance orchestrator
(``runtime/pipeline/orchestrator.py``, WS-6c-AGENTIC). See
``_SEAM_FIELDS`` below and ``pipeline.py`` for the seam. Recomposing them here
would duplicate that orchestrator (the WS-6c-AGENTIC "verify-and-document, don't
rebuild-nodes" pattern applied at the OBS boundary).

The upstream field sets are pinned as module constants so the A5 contract test
asserts the recompose preserved them without importing the backend.
"""

from typing import Any, Literal, TypedDict

from .models import CallKPI

# ── The upstream ObservationState field set (observation_workflow.py:38-92) ──
# Pinned here so the contract test can assert preservation offline. Split into
# the KPI-half (recomposed) and the compliance/artifact tail (hand-off seam).
_KPI_FIELDS = frozenset(
    {
        # Input
        "agent_id",
        "organization_id",
        "file_path",
        "file_name",
        "item_id",
        "session_id",
        "agent_context",
        # Processing state
        "status",
        "error_message",
        "file_type",
        "audio_bytes",
        # KPI extraction state
        "transcription_data",
        "normalized_transcript_stream",
        "call_kpi",
        "core_interaction_metrics",
        "agent_understanding_quality",
        "sentiment_metrics",
        "aggregated_kpis",
        "overall_score",
        "safety_compliance",
        "technical_metrics",
        "turns",
        "conversation_structure",
        "temporal_context",
        "speaker_context",
        "tool_errors",
        "performance_timings",
        "analysis_warnings",
    }
)

# The compliance/artifact tail — OUT of OBS scope; the documented hand-off seam.
_SEAM_FIELDS = frozenset(
    {
        "compliance_enabled",
        "compliance_report",
        "compliance_status",
        "compliance_report_id",
        "compliance_verdict",
        "compliance_confidence",
        "artifacts",
        "artifact_evaluation",
        "artifact_verdict",
    }
)


class ObservationState(TypedDict, total=False):
    """KPI-half state for the recomposed observation pipeline.

    ``total=False`` — the pipeline populates fields stage by stage, mirroring the
    LangGraph state-accumulation the recompose replaces.
    """

    # Input
    agent_id: str
    organization_id: str
    file_path: str
    file_name: str
    item_id: str
    session_id: str
    agent_context: dict[str, Any] | None
    # Processing state
    status: Literal[
        "pending",
        "initiated",
        "transcribing",
        "audio_analyzing",
        "llm_analyzing",
        "aggregating",
        "completed",
        "failed",
    ]
    error_message: str | None
    file_type: str | None
    audio_bytes: bytes | None
    # KPI extraction state
    transcription_data: dict[str, Any] | None
    normalized_transcript_stream: list[dict[str, Any]] | None
    call_kpi: CallKPI | None
    core_interaction_metrics: Any | None
    agent_understanding_quality: Any | None
    sentiment_metrics: Any | None
    aggregated_kpis: Any | None
    overall_score: float | None
    safety_compliance: Any | None
    technical_metrics: Any | None
    turns: list[dict[str, Any]] | None
    conversation_structure: str | None
    temporal_context: str | None
    speaker_context: str | None
    tool_errors: list[dict[str, Any]] | None
    performance_timings: dict[str, float] | None
    analysis_warnings: list[dict[str, Any]] | None
