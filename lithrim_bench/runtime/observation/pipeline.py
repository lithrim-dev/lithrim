"""The recomposed observation / KPI pipeline (straight-line async).

Recomposed from ``lithrim-backend@mvp-ready`` ``observation_workflow.py`` — the
**KPI-half** of the LangGraph ``StateGraph`` (``_build_workflow:101``):

    process_input_item → get_transcription_data → analyze_audio
        → run_parallel_analyses (4-way asyncio.gather) → aggregate_kpis

The recompose (no Celery, no Mongo, no LangGraph runtime):

- the linear ``StateGraph`` + ``add_conditional_edges(should_continue, …)`` →
  plain ``await`` calls gated by ``if self._failed(state)``;
- the ``handle_error`` sink (``observation_workflow.py:282``) → ``_handle_error``
  (terminal passthrough, mirroring the backend node);
- the **4-way ``asyncio.gather`` fan-out** (``:570``, intent/sentiment/safety/
  technical) is **preserved as concurrency** — it is load-bearing, not flattened;
- the Mongo progress-stage writes (``_update_session_stage`` →
  ``conversation_session.update_one:30``) and the Mongo transcript read
  (``conversation_item.find_one:355``) are **dropped** — the transcript / audio
  is supplied in-memory (persistence is WS-6d, out of scope);
- agent instantiation is **hoisted** into ``ObservationAgents`` (the backend
  re-instantiated per node body).

THE RECOMPOSE BOUNDARY (the documented hand-off seam): the pipeline **STOPS at
aggregate_kpis**. The backend workflow continues into the compliance tail
(``check_hipaa_compliance → evaluate_artifacts → save_compliance_results``), and
``check_hipaa_compliance`` delegates to ``ComplianceWorkflow().process()``
(``observation_workflow.py:686-687``) — the compliance grade path **already
recomposed in-process** as ``runtime/pipeline/orchestrator.py`` (WS-6c-AGENTIC).
Re-porting it would duplicate that orchestrator, so the tail is a **seam**, not a
re-port: ``run()`` returns the in-memory ``ObservationState`` (with ``call_kpi``)
that would be handed off, and emits no ``ComplianceWorkflow`` / council call (A3).
"""

import asyncio
import logging
from typing import Any

from .agents.base import ObservationAgents
from .models import CallKPI
from .state import ObservationState

logger = logging.getLogger(__name__)

# File-extension inference (pure — replaces the backend's s3_service.is_*_file,
# observation_workflow.py:297-300, which only switched on the extension anyway).
_AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus")
_TEXT_EXTS = (".txt", ".json", ".jsonl", ".csv", ".md", ".vtt", ".srt")


def _infer_file_type(file_path: str) -> str:
    lowered = file_path.lower()
    if lowered.endswith(_AUDIO_EXTS):
        return "audio"
    if lowered.endswith(_TEXT_EXTS):
        return "text"
    return "unknown"


class ObservationPipeline:
    """In-process recompose of the observation KPI workflow (StateGraph-free)."""

    def __init__(self, agents: ObservationAgents | None = None, *, llm_service: Any = None) -> None:
        # Hoisted: agents are built ONCE here, not per node call.
        self.agents = agents or ObservationAgents.build(llm_service=llm_service)

    async def run(
        self,
        *,
        session_id: str,
        agent_id: str,
        organization_id: str | None = None,
        file_path: str,
        item_id: str,
        transcript: str | None = None,
        transcription_data: dict[str, Any] | None = None,
        turns: list[dict[str, Any]] | None = None,
        normalized_transcript_stream: list[dict[str, Any]] | None = None,
        audio_bytes: bytes | None = None,
        agent_context: dict[str, Any] | None = None,
        file_type: str | None = None,
    ) -> ObservationState:
        """Run the KPI pipeline end-to-end and return the in-memory ObservationState.

        Either ``transcript`` (raw text), ``transcription_data`` (pre-built), or
        ``audio_bytes`` (audio path, needs the ``[observation]`` extra) supplies the
        input. On any node failure the run short-circuits to ``_handle_error``
        (terminal), mirroring the backend ``should_continue`` → ``handle_error`` edge.
        """
        file_name = file_path.split("/")[-1]
        state: ObservationState = {
            "session_id": session_id,
            "agent_id": agent_id,
            "organization_id": organization_id,
            "file_path": file_path,
            "file_name": file_name,
            "item_id": item_id,
            "status": "initiated",
            "file_type": file_type,
            "agent_context": agent_context,
            "audio_bytes": audio_bytes,
            "transcription_data": transcription_data,
            "turns": turns,
            "normalized_transcript_stream": normalized_transcript_stream,
            "analysis_warnings": [],
        }

        state = await self._process_input_item(state)
        if self._failed(state):
            return self._handle_error(state)
        # `transcript` is the in-memory ingest (replaces the backend S3/Mongo read);
        # threaded as a node arg rather than stored in the typed ObservationState.
        state = await self._get_transcription_data(state, transcript)
        if self._failed(state):
            return self._handle_error(state)
        state = await self._analyze_audio(state)
        if self._failed(state):
            return self._handle_error(state)
        state = await self._run_parallel_analyses(state)
        if self._failed(state):
            return self._handle_error(state)
        state = await self._aggregate_kpis(state)
        if self._failed(state):
            return self._handle_error(state)

        # ── HAND-OFF SEAM (compliance tail — OUT of OBS scope) ──────────────
        # The backend workflow continues here into check_hipaa_compliance →
        # evaluate_artifacts → save_compliance_results, where
        # check_hipaa_compliance delegates to ComplianceWorkflow().process()
        # (observation_workflow.py:686-687) — the compliance grade path already
        # recomposed in-process as runtime/pipeline/orchestrator.py
        # (WS-6c-AGENTIC). The recompose STOPS at aggregate_kpis: `state` (the
        # in-memory ObservationState carrying call_kpi + transcription_data) is
        # what would be handed to that orchestrator's compliance entry. We emit
        # NO ComplianceWorkflow / council call here (A3 — verify-and-document,
        # don't rebuild-nodes).
        return state

    # ── routing helpers (the should_continue / handle_error edges) ──────────
    @staticmethod
    def _failed(state: ObservationState) -> bool:
        return state.get("status") == "failed"

    @staticmethod
    def _handle_error(state: ObservationState) -> ObservationState:
        """Terminal error sink (observation_workflow.py:282-285)."""
        logger.error("observation pipeline failed: %s", state.get("error_message"))
        return state

    # ── node 1: process_input_item (observation_workflow.py:287) ────────────
    async def _process_input_item(self, state: ObservationState) -> ObservationState:
        try:
            file_type = state.get("file_type")
            if not file_type or file_type == "unknown":
                file_type = _infer_file_type(state["file_path"])
                state["file_type"] = file_type

            # The backend reads audio bytes from S3 here; in-process they are
            # supplied via `audio_bytes`. A declared audio input without bytes is
            # a hard failure (mirrors the backend's "Failed to read audio file").
            if file_type == "audio" and not state.get("audio_bytes"):
                state["status"] = "failed"
                state["error_message"] = "audio file_type but no audio_bytes supplied"
            return state
        except Exception as e:  # noqa: BLE001
            logger.error("Error processing input item: %s", e, exc_info=True)
            state["status"] = "failed"
            state["error_message"] = str(e)
            return state

    # ── node 2: get_transcription_data (observation_workflow.py:325) ────────
    async def _get_transcription_data(
        self, state: ObservationState, raw_transcript: str | None = None
    ) -> ObservationState:
        file_type = state.get("file_type")
        if file_type == "audio":
            try:
                if not state.get("audio_bytes"):
                    raise ValueError("Audio bytes are not available")
                result = await self.agents.transcription.transcribe_from_bytes(
                    state["audio_bytes"], state["file_name"]
                )
                if result is None:
                    raise ValueError("Failed to transcribe audio file")
                state["transcription_data"] = result.get("transcription")
                state.pop("audio_bytes", None)  # free bytes post-transcription
                return state
            except Exception as e:
                logger.error("Error getting transcription data: %s", e, exc_info=True)
                state["status"] = "failed"
                state["error_message"] = str(e)
                return state

        # text (and unknown) path — transcript supplied in-memory (no Mongo/S3).
        # transcript_parser (chat-string → turns) is a backend ingest detail not
        # ported; callers supply `transcription_data` or a raw `transcript`.
        if not state.get("transcription_data"):
            if not raw_transcript:
                state["status"] = "failed"
                state["error_message"] = "no transcript or transcription_data supplied"
                return state
            state["transcription_data"] = {
                "transcription": raw_transcript,
                "duration_ms": None,
                "detected_language": "en",
                "segments": [],
            }
        return state

    # ── node 3: analyze_audio (observation_workflow.py:381) ─────────────────
    async def _analyze_audio(self, state: ObservationState) -> ObservationState:
        if state.get("file_type") == "text":
            # observation_workflow.py:384-387 — skip audio analysis for text.
            state["core_interaction_metrics"] = None
            return state
        try:
            if state.get("transcription_data") is None:
                raise ValueError("Transcription data is not available")
            result = await self.agents.audio_analysis.analyze_audio(
                state.get("audio_bytes"), state["transcription_data"], state["file_name"]
            )
            if result is None:
                raise ValueError("Failed to analyze audio")
            if not result.get("success"):
                state["error_message"] = result.get("error", "Unknown audio analysis error")
                state["core_interaction_metrics"] = None
                state["status"] = "failed"
            else:
                state["normalized_transcript_stream"] = result.get("normalized_transcript_stream")
                state["turns"] = result.get("turns")
                state["core_interaction_metrics"] = result.get("metrics")
                state["conversation_structure"] = result.get("conversation_structure")
                state["temporal_context"] = result.get("temporal_context")
                state["speaker_context"] = result.get("speaker_context")
            return state
        except Exception as e:
            logger.error("Error analyzing audio: %s", e, exc_info=True)
            state["status"] = "failed"
            state["error_message"] = str(e)
            return state

    # ── node 4: run_parallel_analyses — the 4-way gather (obs_workflow.py:423)
    async def _run_parallel_analyses(self, state: ObservationState) -> ObservationState:
        transcription_data = state.get("transcription_data")
        if not transcription_data:
            raise ValueError("No transcription available")
        transcription = transcription_data.get("transcription", "")
        if not transcription:
            raise ValueError("No transcription text available")

        agent_context = state.get("agent_context")
        turns = state.get("turns")
        conversation_structure = state.get("conversation_structure")
        temporal_context = state.get("temporal_context")
        speaker_context = state.get("speaker_context")

        async def run_intent_quality():
            try:
                result = await self.agents.intent_quality.analyze_intent_quality(
                    transcription,
                    agent_context,
                    conversation_structure,
                    temporal_context,
                    speaker_context,
                    turns,
                )
                if not result.get("success"):
                    logger.warning("Intent/quality analysis failed: %s", result.get("error"))
                    return ("intent_quality", None, None, _warns(result))
                return ("intent_quality", result.get("metrics"), None, _warns(result))
            except Exception as e:  # noqa: BLE001
                logger.error("Error in parallel intent quality analysis: %s", e)
                return ("intent_quality", None, str(e), [])

        async def run_sentiment():
            try:
                result = await self.agents.sentiment.analyze_sentiment(
                    include_turn_level=True,
                    transcription_data=transcription_data,
                    conversation_structure=conversation_structure,
                    temporal_context=temporal_context,
                    speaker_context=speaker_context,
                    agent_context=agent_context,
                )
                if not result.get("success"):
                    return ("sentiment", None, result.get("error", "Unknown sentiment error"), [])
                return ("sentiment", result.get("metrics"), None, [])
            except Exception as e:  # noqa: BLE001
                logger.error("Error in parallel sentiment analysis: %s", e)
                return ("sentiment", None, str(e), [])

        async def run_safety():
            try:
                result = await self.agents.safety.analyze_safety(
                    agent_context=agent_context,
                    include_turn_level=True,
                    transcription_data=transcription_data,
                    conversation_structure=conversation_structure,
                    temporal_context=temporal_context,
                    speaker_context=speaker_context,
                    turns=turns,
                )
                if not result.get("success"):
                    return ("safety", None, result.get("error", "Unknown safety error"), _warns(result))
                return ("safety", result.get("metrics"), None, _warns(result))
            except Exception as e:  # noqa: BLE001
                logger.error("Error in parallel safety analysis: %s", e)
                return ("safety", None, str(e), [])

        async def run_technical_metrics():
            try:
                result = await self.agents.technical_metrics.extract_technical_metrics(
                    state.get("audio_bytes"),
                    duration_ms=transcription_data.get("duration_ms"),
                    tool_errors=state.get("tool_errors"),
                    performance_metrics=state.get("performance_timings"),
                    file_name=state.get("file_name"),
                )
                if not result.get("success"):
                    logger.warning("Technical metrics extraction failed: %s", result.get("error"))
                    return ("technical_metrics", None, None, _warns(result))
                return ("technical_metrics", result.get("metrics"), None, _warns(result))
            except Exception as e:  # noqa: BLE001
                logger.error("Error in parallel technical metrics analysis: %s", e)
                return ("technical_metrics", None, str(e), [])

        try:
            results = await asyncio.gather(
                run_intent_quality(),
                run_sentiment(),
                run_safety(),
                run_technical_metrics(),
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    logger.error("Unexpected exception in parallel analysis: %s", result)
                    continue
                analysis_name, metrics, error, warnings = result
                if error:
                    logger.warning("%s analysis failed: %s", analysis_name, error)
                    continue
                if warnings:
                    state.setdefault("analysis_warnings", [])
                    state["analysis_warnings"].extend([w for w in warnings if isinstance(w, dict)])
                if analysis_name == "intent_quality":
                    state["agent_understanding_quality"] = metrics
                elif analysis_name == "sentiment":
                    state["sentiment_metrics"] = metrics
                elif analysis_name == "safety":
                    state["safety_compliance"] = metrics
                elif analysis_name == "technical_metrics":
                    state["technical_metrics"] = metrics
            return state
        except Exception as e:  # noqa: BLE001
            logger.error("Error in parallel analyses execution: %s", e)
            return state

    # ── node 5: aggregate_kpis (observation_workflow.py:607) ────────────────
    async def _aggregate_kpis(self, state: ObservationState) -> ObservationState:
        try:
            aggregated = self.agents.kpi_aggregation.aggregate_kpis(
                core_metrics=state.get("core_interaction_metrics"),
                quality_metrics=state.get("agent_understanding_quality"),
                sentiment_metrics=state.get("sentiment_metrics"),
                safety_metrics=state.get("safety_compliance"),
                technical_metrics=state.get("technical_metrics"),
            )
            state["aggregated_kpis"] = aggregated
            state["overall_score"] = aggregated.get("overall_score", 0.0)

            state["call_kpi"] = CallKPI(
                agent_id=state["agent_id"],
                organization_id=state.get("organization_id"),
                session_id=state["session_id"],
                item_id=state["item_id"],
                file_path=state["file_path"],
                core_interaction_metrics=aggregated.get("core_interaction_metrics"),
                agent_understanding_quality=aggregated.get("agent_understanding_quality"),
                sentiment_metrics=aggregated.get("sentiment_metrics"),
                safety_compliance=aggregated.get("safety_compliance"),
                technical_call_stats=aggregated.get("technical_call_stats"),
                normalized_transcript_stream=state.get("normalized_transcript_stream"),
                overall_score=aggregated.get("overall_score"),
                kpi_status="completed",
            )
            state["status"] = "completed"
            return state
        except Exception as e:  # noqa: BLE001
            logger.error("Error aggregating KPIs: %s", e)
            state["status"] = "failed"
            state["error_message"] = str(e)
            return state


def _warns(result: Any) -> list[dict[str, Any]]:
    """The backend's ``result.get("warnings", []) if isinstance(result, dict) else []``."""
    return result.get("warnings", []) if isinstance(result, dict) else []


async def run_observation_pipeline(
    *, agents: ObservationAgents | None = None, llm_service: Any = None, **kwargs: Any
) -> ObservationState:
    """Convenience: build an ``ObservationPipeline`` and run one case."""
    return await ObservationPipeline(agents, llm_service=llm_service).run(**kwargs)
