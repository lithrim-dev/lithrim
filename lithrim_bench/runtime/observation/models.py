"""Observation KPI domain models — the in-memory state contract.

Ported from ``lithrim-backend@mvp-ready`` ``app/models/call_kpi.py`` (WS-6c-OBS,
bench-salvage). The field set is reproduced faithfully — it is the ``CallKPI``
contract the recomposed observation pipeline emits and the source of the
``ObservationState`` KPI-half fields (see ``state.py``). Mechanical adaptations
only:

- the Mongo ``bson``/``PyObjectId`` coupling is dropped — ``CallKPI.id`` is a
  plain ``Optional[str]`` (no ``_id`` alias, no ``ObjectId`` json-encoder), since
  the recomposed pipeline is in-memory (no persistence — WS-6d owns that);
- ``from_mongo`` is dropped (Mongo-document constructor); ``to_dict`` keeps its
  signature minus the bson branch.

Pure pydantic v2 — imports nothing heavy, ships on the default install (A2).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TurnLatency(BaseModel):
    """Turn-level latency metrics."""

    turn_number: int = Field(..., description="Turn number in conversation")
    latency_ms: float = Field(..., description="Latency in milliseconds (gap duration)")
    last_end_time_ms: float = Field(
        ...,
        description="Timestamp when user last ended speaking (in ms)",
    )
    first_start_time_ms: float = Field(
        ...,
        description="Timestamp when agent first started speaking (in ms)",
    )
    speaker: str | None = Field(None, description="Speaker this latency is for (agent/user)")


class InterruptionEvent(BaseModel):
    """Interruption event details."""

    timestamp_ms: float = Field(..., description="Timestamp when interruption occurred")
    interrupted_speaker: str = Field(..., description="Who was interrupted (user/agent)")
    interrupting_speaker: str = Field(..., description="Who interrupted (user/agent)")
    duration_ms: float = Field(..., description="Duration of overlap in milliseconds")


class SilenceGap(BaseModel):
    """Silence gap details."""

    start_time_ms: float = Field(..., description="Start time of silence gap")
    end_time_ms: float = Field(..., description="End time of silence gap")
    duration_ms: float = Field(..., description="Duration of silence gap in milliseconds")
    is_too_long: bool = Field(..., description="Whether silence gap exceeds threshold")


class CoreInteractionMetrics(BaseModel):
    """Core interaction metrics from audio analysis."""

    turn_latencies: list[TurnLatency] = Field(
        default_factory=list, description="Latency for each turn"
    )
    avg_turn_latency_ms: float | None = Field(
        None, description="Average turn latency in milliseconds"
    )
    response_latencies: list[float] = Field(
        default_factory=list,
        description="Response latency for each agent response (ms)",
    )
    avg_response_latency_ms: float | None = Field(
        None, description="Average response latency in milliseconds"
    )
    interruption_events: list[InterruptionEvent] = Field(
        default_factory=list, description="List of interruption events"
    )
    interruption_count: int = Field(default=0, description="Total number of interruptions")
    repetition_count: int = Field(default=0, description="Number of times agent repeated itself")
    silence_gaps: list[SilenceGap] = Field(
        default_factory=list, description="List of silence gaps detected"
    )
    total_silence_duration_ms: float = Field(
        default=0.0, description="Total duration of silence gaps in milliseconds"
    )
    long_silence_gaps_count: int = Field(
        default=0, description="Number of silence gaps exceeding threshold"
    )


class IntentMatch(BaseModel):
    """Intent match/mismatch details."""

    detected_intent: str = Field(..., description="Detected user intent")
    expected_intent: str | None = Field(None, description="Expected intent based on context")
    is_match: bool = Field(..., description="Whether intent matches expected")
    confidence: float = Field(..., description="Confidence score (0-1)")
    evidence: str | None = Field(None, description="Evidence snippet")


class HallucinationDetection(BaseModel):
    """Hallucination detection details."""

    has_hallucination: bool = Field(..., description="Whether hallucination detected")
    hallucination_segments: list[str] = Field(
        default_factory=list, description="Segments with potential hallucinations"
    )
    confidence: float = Field(..., description="Confidence score (0-1)")
    explanation: str | None = Field(None, description="Explanation of detection")


class WorkflowDeviation(BaseModel):
    """Workflow/script deviation details."""

    has_deviation: bool = Field(..., description="Whether workflow deviation detected")
    deviation_type: str | None = Field(
        None, description="Type of deviation (e.g., 'skipped_step', 'wrong_order')"
    )
    expected_steps: list[str] = Field(default_factory=list, description="Expected workflow steps")
    actual_steps: list[str] = Field(default_factory=list, description="Actual steps taken")
    deviation_segments: list[str] = Field(
        default_factory=list, description="Conversation segments with deviations"
    )


class AgentUnderstandingQuality(BaseModel):
    """Agent understanding and quality metrics."""

    intent_match: IntentMatch | None = Field(None, description="Intent match/mismatch analysis")
    hallucination: HallucinationDetection | None = Field(
        None, description="Hallucination detection results"
    )
    workflow_deviation: WorkflowDeviation | None = Field(
        None, description="Workflow/script deviation analysis"
    )
    task_completion: bool = Field(..., description="Whether task was completed")
    task_completion_confidence: float = Field(
        ..., description="Confidence in task completion (0-1)"
    )
    task_completion_evidence: str | None = Field(
        None, description="Evidence for task completion"
    )
    escalation_triggered: bool = Field(..., description="Whether escalation was triggered")
    escalation_type: str | None = Field(None, description="Type of escalation if triggered")
    escalation_timestamp_ms: float | None = Field(
        None, description="Timestamp when escalation was triggered"
    )


class TurnSentiment(BaseModel):
    """Turn-level sentiment analysis."""

    turn_number: int = Field(..., description="Turn number")
    speaker: str = Field(..., description="Speaker (user/agent)")
    sentiment: str = Field(..., description="Sentiment (positive/neutral/negative)")
    confidence: float = Field(..., description="Confidence score (0-1)")
    timestamp_ms: float = Field(..., description="Timestamp of turn")
    rationale: str | None = Field(None, description="Short reasoning for the sentiment call")
    alerts: list[str] = Field(
        default_factory=list,
        description="Alert flags for this turn (e.g., frustration)",
    )


class SentimentMetrics(BaseModel):
    """Sentiment analysis metrics."""

    user_sentiment_final: str = Field(
        ..., description="Final user sentiment (positive/neutral/negative)"
    )
    user_sentiment_confidence: float = Field(
        ..., description="Confidence in final sentiment (0-1)"
    )
    user_sentiment_rationale: str | None = Field(
        None, description="Reasoning behind the final user sentiment judgment"
    )
    agent_sentiment_final: str | None = Field(
        None, description="Final agent sentiment (positive/neutral/negative)"
    )
    agent_sentiment_confidence: float | None = Field(
        None, description="Confidence in final agent sentiment (0-1)"
    )
    agent_sentiment_rationale: str | None = Field(
        None, description="Reasoning behind the final agent sentiment judgment"
    )
    turn_level_sentiments: list[TurnSentiment] = Field(
        default_factory=list, description="Turn-level sentiment analysis (optional)"
    )
    alerts: list[str] = Field(
        default_factory=list,
        description="Conversation-level alert flags (e.g., frustration, escalation_risk)",
    )


class PIILeakage(BaseModel):
    """PII leakage detection details."""

    has_pii_leakage: bool = Field(..., description="Whether PII leakage detected")
    pii_types: list[str] = Field(
        default_factory=list,
        description="Types of PII detected (e.g., 'phone', 'email', 'ssn')",
    )
    leaked_segments: list[str] = Field(
        default_factory=list, description="Conversation segments with PII"
    )
    severity: str = Field(..., description="Severity level (high/medium/low)")
    confidence: float = Field(
        default=0.0, description="Confidence score for PII detection (0-1)"
    )


class UnsafeResponse(BaseModel):
    """Unsafe response detection details."""

    has_unsafe_response: bool = Field(..., description="Whether unsafe response detected")
    unsafe_types: list[str] = Field(
        default_factory=list,
        description="Types of unsafe content (e.g., 'inappropriate', 'risky_advice')",
    )
    unsafe_segments: list[str] = Field(
        default_factory=list, description="Conversation segments with unsafe content"
    )
    severity: str = Field(..., description="Severity level (high/medium/low)")
    confidence: float = Field(
        default=0.0, description="Confidence score for unsafe response detection (0-1)"
    )


class ComplianceViolation(BaseModel):
    """Compliance violation detection details."""

    violation_type: str = Field(
        ...,
        description="Type of violation (e.g., 'HIPAA', 'PCI-DSS', 'GDPR', 'data_retention', 'consent')",
    )
    has_violation: bool = Field(..., description="Whether violation detected")
    violation_segments: list[str] = Field(
        default_factory=list, description="Conversation segments with violations"
    )
    severity: str = Field(..., description="Severity level (high/medium/low)")
    confidence: float = Field(
        default=0.0, description="Confidence score for violation detection (0-1)"
    )
    explanation: str | None = Field(None, description="Explanation of the violation")


class TurnSafety(BaseModel):
    """Turn-level safety analysis."""

    turn_number: int = Field(..., description="Turn number in conversation")
    speaker: str = Field(..., description="Speaker (user/agent)")
    timestamp_ms: float = Field(..., description="Timestamp of turn in milliseconds")
    pii_detected: bool = Field(default=False, description="Whether PII was detected in this turn")
    pii_types: list[str] = Field(
        default_factory=list, description="Types of PII detected in this turn"
    )
    unsafe_content_detected: bool = Field(
        default=False, description="Whether unsafe content was detected in this turn"
    )
    unsafe_types: list[str] = Field(
        default_factory=list, description="Types of unsafe content detected"
    )
    compliance_violations: list[str] = Field(
        default_factory=list,
        description="Compliance violations detected (e.g., 'HIPAA', 'GDPR', 'PCI-DSS')",
    )
    severity: str = Field(
        default="low", description="Severity level for this turn (high/medium/low)"
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence score for this turn's safety analysis (0-1)",
    )
    rationale: str | None = Field(
        None, description="Brief explanation of safety issues in this turn"
    )
    alerts: list[str] = Field(
        default_factory=list,
        description="Alert flags for this turn (e.g., 'pii_leakage', 'policy_violation')",
    )


class SafetyCompliance(BaseModel):
    """Safety and compliance metrics."""

    pii_leakage: PIILeakage | None = Field(None, description="PII leakage detection results")
    unsafe_response: UnsafeResponse | None = Field(
        None, description="Unsafe response detection results"
    )
    compliance_violations: list[ComplianceViolation] = Field(
        default_factory=list, description="Compliance violation detection results"
    )
    turn_level_safety: list[TurnSafety] = Field(
        default_factory=list, description="Turn-level safety analysis (optional)"
    )
    overall_risk_score: float = Field(
        default=0.0,
        description="Overall risk score for the conversation (0-1, where 1 is highest risk)",
    )
    overall_confidence: float = Field(
        default=0.0, description="Overall confidence in safety analysis (0-1)"
    )
    alerts: list[str] = Field(
        default_factory=list,
        description="Aggregated alert flags (e.g., 'high_risk_pii', 'compliance_violation')",
    )


class ToolError(BaseModel):
    """Tool/API error details."""

    error_type: str = Field(
        ...,
        description="Type of error (e.g., 'api_error', 'agent_failure', 'processing_error', 'service_error')",
    )
    source: str = Field(
        ...,
        description="Source of error (e.g., 'transcription', 'llm', 'audio_analysis', 'safety_agent')",
    )
    error_message: str = Field(..., description="Error message")
    timestamp_ms: float | None = Field(
        None, description="Timestamp when error occurred (in milliseconds)"
    )
    severity: str = Field(
        ...,
        description="Error severity level (e.g., 'critical', 'high', 'medium', 'low')",
    )
    context: dict[str, Any] | None = Field(
        None, description="Additional context about the error"
    )


class AudioQualityMetrics(BaseModel):
    """Audio quality analysis metrics."""

    snr_db: float | None = Field(None, description="Signal-to-noise ratio in decibels")
    noise_level: float | None = Field(
        None, description="Background noise level (0-1, where 1 is highest noise)"
    )
    distortion_detected: bool = Field(
        default=False, description="Whether audio distortion/clipping was detected"
    )
    distortion_segments: list[float] = Field(
        default_factory=list,
        description="Timestamps (in ms) where distortion occurs",
    )
    avg_volume_db: float | None = Field(None, description="Average volume level in decibels")
    peak_volume_db: float | None = Field(None, description="Peak volume level in decibels")
    frequency_range_ok: bool = Field(
        default=True,
        description="Whether full frequency range is present in audio",
    )
    audio_quality_score: float = Field(
        default=0.0,
        description="Composite audio quality score (0-1, where 1 is best quality)",
    )


class NetworkMetrics(BaseModel):
    """Network and connection quality metrics.

    NOTE: These metrics are inferred from audio analysis and are not reliable indicators
    of actual network conditions. They should be used for informational purposes only
    and not included in call quality scoring. For accurate network metrics, actual
    network-layer measurements are required.
    """

    connection_stable: bool = Field(
        default=True,
        description="Whether connection was stable throughout call (inferred from audio)",
    )
    connection_drops: int = Field(
        default=0,
        description="Number of connection drops detected (inferred from audio gaps)",
    )
    avg_latency_ms: float | None = Field(
        None,
        description="Average network latency in milliseconds (inferred, not reliable)",
    )
    packet_loss_indicators: int = Field(
        default=0,
        description="Number of missing audio segments (may indicate packet loss, but not reliable)",
    )
    jitter_ms: float | None = Field(
        None,
        description="Timing irregularity (jitter) in milliseconds (inferred, not reliable)",
    )
    network_quality_score: float = Field(
        default=0.0,
        description="Composite network quality score (0-1, inferred from audio, not reliable)",
    )


class PerformanceMetrics(BaseModel):
    """Processing performance metrics."""

    transcription_time_ms: float | None = Field(
        None, description="Time taken for transcription in milliseconds"
    )
    audio_analysis_time_ms: float | None = Field(
        None, description="Time taken for audio analysis in milliseconds"
    )
    intent_quality_time_ms: float | None = Field(
        None, description="Time taken for intent quality analysis in milliseconds"
    )
    sentiment_analysis_time_ms: float | None = Field(
        None, description="Time taken for sentiment analysis in milliseconds"
    )
    safety_analysis_time_ms: float | None = Field(
        None, description="Time taken for safety analysis in milliseconds"
    )
    technical_metrics_time_ms: float | None = Field(
        None, description="Time taken for technical metrics extraction in milliseconds"
    )
    total_processing_time_ms: float | None = Field(
        None, description="Total end-to-end processing time in milliseconds"
    )
    bottleneck_step: str | None = Field(
        None, description="Which processing step took the longest"
    )
    api_response_times: dict[str, float] = Field(
        default_factory=dict,
        description="Per-API response times in milliseconds",
    )


class CallQualityScore(BaseModel):
    """Call quality scoring using MOS (Mean Opinion Score).

    NOTE: Network metrics are not included in the overall MOS calculation as they
    cannot be reliably measured from audio bytes alone. Only audio quality metrics
    are used for scoring.
    """

    audio_mos: float = Field(
        ...,
        description="Mean Opinion Score for audio quality (1-5 scale, where 5 is best)",
    )
    network_mos: float | None = Field(
        None,
        description="Mean Opinion Score for network quality (1-5 scale, inferred, not reliable)",
    )
    overall_mos: float = Field(
        ...,
        description="Overall Mean Opinion Score based on audio quality only (1-5 scale)",
    )
    quality_category: str = Field(
        ...,
        description="Quality category (e.g., 'excellent', 'good', 'fair', 'poor', 'bad')",
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence in the quality scoring (0-1, where 1 is most confident)",
    )


class CallDropDetails(BaseModel):
    """Enhanced call drop detection details.

    NOTE: Call drop detection is inferred from audio characteristics and is not fully
    reliable. An "abrupt ending" detected in audio could indicate an actual
    network/connection drop, a natural abrupt hangup, a recording cutoff, or a natural
    conversation fade-out. For accurate call drop detection, network-level telemetry is
    required.
    """

    detected: bool = Field(
        ...,
        description="Whether abrupt ending was detected (inferred from audio)",
    )
    confidence: float = Field(
        ...,
        description="Confidence in abrupt ending detection (0-1, where 1 is most confident)",
    )
    drop_timestamp_ms: float | None = Field(
        None,
        description="Timestamp when abrupt ending was detected (in milliseconds, inferred)",
    )
    drop_reason: str | None = Field(
        None,
        description="Reason for abrupt ending classification (e.g., 'abrupt_cutoff', 'silence')",
    )
    detection_methods: list[str] = Field(
        default_factory=list,
        description="Methods that detected the abrupt ending (e.g., 'energy_based')",
    )


class TechnicalCallStats(BaseModel):
    """Technical call statistics."""

    call_duration_ms: float = Field(..., description="Total call duration in milliseconds")
    call_drop_flag: bool = Field(
        ...,
        description="Whether abrupt ending was detected (inferred from audio)",
    )
    call_drop_details: CallDropDetails | None = Field(
        None,
        description="Enhanced abrupt ending detection details (inferred from audio)",
    )
    call_availability: bool = Field(..., description="Whether agent was available for the call")
    tool_errors: list[ToolError] = Field(
        default_factory=list,
        description="List of tool/API errors encountered during call",
    )
    tool_error_count: int = Field(default=0, description="Total number of tool errors")
    audio_quality: AudioQualityMetrics | None = Field(
        None, description="Audio quality analysis metrics"
    )
    network_metrics: NetworkMetrics | None = Field(
        None, description="Network and connection quality metrics"
    )
    performance_metrics: PerformanceMetrics | None = Field(
        None, description="Processing performance metrics"
    )
    call_quality_score: CallQualityScore | None = Field(
        None, description="Call quality scoring using MOS"
    )


class CallKPI(BaseModel):
    """Comprehensive Call KPI model — the in-memory aggregation the pipeline emits.

    Field-faithful to ``lithrim-backend`` ``call_kpi.CallKPI`` minus the Mongo
    coupling: ``id`` is a plain ``Optional[str]`` (no ``_id`` alias / ``bson``).
    """

    id: str | None = Field(default=None, description="In-memory id (was Mongo _id)")
    agent_id: str = Field(..., description="Agent ID")
    organization_id: str | None = Field(None, description="Organization ID")
    session_id: str = Field(..., description="Audit session ID")
    item_id: str = Field(..., description="Audit item ID (call recording)")
    file_path: str = Field(..., description="File path of the call recording")

    core_interaction_metrics: CoreInteractionMetrics | None = Field(
        None, description="Core interaction metrics"
    )
    agent_understanding_quality: AgentUnderstandingQuality | None = Field(
        None, description="Agent understanding and quality metrics"
    )
    sentiment_metrics: SentimentMetrics | None = Field(
        None, description="Sentiment analysis metrics"
    )
    safety_compliance: SafetyCompliance | None = Field(
        None, description="Safety and compliance metrics"
    )
    technical_call_stats: TechnicalCallStats | None = Field(
        None, description="Technical call statistics"
    )
    normalized_transcript_stream: list[dict[str, Any]] | None = Field(
        None,
        description="Normalized transcript stream with speaker labels and timestamps",
    )
    overall_score: float | None = Field(None, description="Overall KPI score (0-100)")
    kpi_status: str = Field(
        default="pending",
        description="KPI extraction status (pending/processing/completed/failed)",
    )
    error_message: str | None = Field(None, description="Error message if extraction failed")
    compliance_report_id: str | None = Field(
        None, description="Reference to compliance report ID"
    )
    hipaa_compliance_status: str | None = Field(
        None,
        description="HIPAA compliance verdict (compliant/non_compliant/needs_review)",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    model_config = ConfigDict(populate_by_name=True)

    def to_dict(self, exclude_id: bool = False) -> dict[str, Any]:
        """Convert model to a plain dictionary."""
        data = self.model_dump(exclude_none=True)
        if exclude_id:
            data.pop("id", None)
        return data
