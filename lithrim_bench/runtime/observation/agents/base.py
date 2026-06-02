"""The 7-agent interface + the hoisted ``ObservationAgents`` container.

The recomposed pipeline calls agents through the structural ``Protocol``s below
(the agent *map*, A4) rather than concrete classes — so the audio-DSP agents can
be deferred behind the ``[observation]`` extra and tests can inject stubs. The
``ObservationAgents`` dataclass is the **instantiation-hoist**: the backend
re-instantiated each agent inside the per-node body
(``observation_workflow.py:333/391/447/481/503/537/613``); here they are built
**once** via ``ObservationAgents.build()`` and reused across the pipeline run.

Agent set (WS-6b Ratification Q4): transcription + 6 KPI. The dead
``evaluation_agent`` is not imported (dropped); the LiveKit ``simulation_agent``
is not imported (parked).
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .audio import AudioAnalysisAgent, TechnicalMetricsAgent, TranscriptionAgent
from .intent_quality import IntentQualityAgent
from .kpi_aggregation import KPIAggregationAgent
from .safety import SafetyAgent
from .sentiment import SentimentAgent


@runtime_checkable
class TranscriptionLike(Protocol):
    """Ingest: audio bytes → transcript dict."""

    async def transcribe_from_bytes(self, audio_bytes: bytes, file_name: str) -> dict[str, Any]: ...


@runtime_checkable
class AudioAnalysisLike(Protocol):
    """Audio DSP → core interaction metrics + turns/structure."""

    async def analyze_audio(
        self, audio_bytes: bytes, transcription_data: dict[str, Any], file_name: str
    ) -> dict[str, Any]: ...


@runtime_checkable
class IntentQualityLike(Protocol):
    """LLM: understanding-quality metrics."""

    async def analyze_intent_quality(
        self,
        transcription: str,
        agent_context: dict[str, Any] | None = ...,
        conversation_structure: str | None = ...,
        temporal_context: str | None = ...,
        speaker_context: str | None = ...,
        turns: list[dict[str, Any]] | None = ...,
    ) -> dict[str, Any]: ...


@runtime_checkable
class SentimentLike(Protocol):
    """LLM: sentiment metrics."""

    async def analyze_sentiment(
        self,
        include_turn_level: bool = ...,
        transcription_data: dict[str, Any] | None = ...,
        conversation_structure: str | None = ...,
        temporal_context: str | None = ...,
        speaker_context: str | None = ...,
        agent_context: dict[str, Any] | None = ...,
    ) -> dict[str, Any]: ...


@runtime_checkable
class SafetyLike(Protocol):
    """LLM + regex: safety/compliance metrics."""

    async def analyze_safety(
        self,
        agent_context: dict[str, Any] | None = ...,
        include_turn_level: bool = ...,
        transcription_data: dict[str, Any] | None = ...,
        conversation_structure: str | None = ...,
        temporal_context: str | None = ...,
        speaker_context: str | None = ...,
        turns: list[dict[str, Any]] | None = ...,
    ) -> dict[str, Any]: ...


@runtime_checkable
class TechnicalMetricsLike(Protocol):
    """Audio technical metrics (degrades gracefully without audio)."""

    async def extract_technical_metrics(
        self,
        audio_bytes: bytes | None,
        duration_ms: float | None = ...,
        tool_errors: list[dict[str, Any]] | None = ...,
        performance_metrics: dict[str, float] | None = ...,
        file_name: str | None = ...,
    ) -> dict[str, Any]: ...


@runtime_checkable
class KpiAggregationLike(Protocol):
    """Pure: combine metrics → aggregation dict + overall score."""

    def aggregate_kpis(
        self,
        core_metrics: Any,
        quality_metrics: Any,
        sentiment_metrics: Any,
        safety_metrics: Any,
        technical_metrics: Any,
    ) -> dict[str, Any]: ...


@dataclass
class ObservationAgents:
    """Hoisted bundle of the 7 recomposed agents (built once per pipeline run)."""

    transcription: TranscriptionLike
    audio_analysis: AudioAnalysisLike
    intent_quality: IntentQualityLike
    sentiment: SentimentLike
    safety: SafetyLike
    technical_metrics: TechnicalMetricsLike
    kpi_aggregation: KpiAggregationLike

    @classmethod
    def build(cls, *, llm_service: Any = None) -> "ObservationAgents":
        """Construct the default bundle once (instantiation hoist).

        ``llm_service`` is threaded into the 3 LLM agents (a stub in tests; ``None``
        → lazily built ``ObservationLLMService`` on first real call). No ``openai`` /
        whisper / librosa is imported here (A2).
        """
        return cls(
            transcription=TranscriptionAgent(),
            audio_analysis=AudioAnalysisAgent(),
            intent_quality=IntentQualityAgent(llm_service=llm_service),
            sentiment=SentimentAgent(llm_service=llm_service),
            safety=SafetyAgent(llm_service=llm_service),
            technical_metrics=TechnicalMetricsAgent(),
            kpi_aggregation=KPIAggregationAgent(),
        )
