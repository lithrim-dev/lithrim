"""Intent and Quality analysis agent for evaluating agent understanding.

Ported from ``lithrim-backend@mvp-ready``
``app/agents/intent_quality_agent/agent.py``. Mechanical adaptations only:
``app.services.gemini_service.get_gemini_service`` → the injectable/lazy
``_LlmBackedAgent`` base (``self.gemini_service``); ``app.models.call_kpi`` →
``..models``; the unused ``app.utils.agents`` context imports are dropped (dead
in the backend too — ruff-clean); the module-level singleton is dropped
(instantiation hoisted). The prompt text + JSON-repair are reproduced faithfully.
"""

import asyncio
import json
import logging
import re
from typing import Any

from ..models import (
    AgentUnderstandingQuality,
    HallucinationDetection,
    IntentMatch,
    WorkflowDeviation,
)
from ._llm import _LlmBackedAgent

logger = logging.getLogger(__name__)


class IntentQualityAgent(_LlmBackedAgent):
    """Agent for analyzing intent, quality, and workflow adherence."""

    async def analyze_intent_quality(
        self,
        transcription: str,
        agent_context: dict[str, Any] | None = None,
        conversation_structure: str | None = None,
        temporal_context: str | None = None,
        speaker_context: str | None = None,
        turns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Analyze intent, quality, and workflow adherence with rich context."""
        try:
            prompt = self._build_enhanced_analysis_prompt(
                transcription,
                conversation_structure,
                temporal_context,
                speaker_context,
                agent_context,
                turns,
            )

            formatted_prompt = self.gemini_service.create_prompt_template(prompt)
            response = await asyncio.to_thread(self.gemini_service.invoke_llm, formatted_prompt)

            analysis_result = self._parse_response(response)
            parse_warnings = analysis_result.pop("_warnings", [])

            quality_metrics = AgentUnderstandingQuality(
                intent_match=analysis_result.get("intent_match"),
                hallucination=analysis_result.get("hallucination"),
                workflow_deviation=analysis_result.get("workflow_deviation"),
                task_completion=analysis_result.get("task_completion", False),
                task_completion_confidence=analysis_result.get("task_completion_confidence", 0.0),
                task_completion_evidence=analysis_result.get("task_completion_evidence"),
                escalation_triggered=analysis_result.get("escalation_triggered", False),
                escalation_type=analysis_result.get("escalation_type"),
                escalation_timestamp_ms=analysis_result.get("escalation_timestamp_ms"),
            )

            return {
                "success": True,
                "metrics": quality_metrics,
                "error": None,
                "warnings": parse_warnings,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "metrics": None,
            }

    def _build_enhanced_analysis_prompt(
        self,
        transcription: str,
        conversation_structure: str,
        temporal_context: str,
        speaker_context: str,
        agent_context: dict[str, Any] | None,
        turns: list[dict[str, Any]] | None,
    ) -> str:
        """Build enhanced analysis prompt with rich context."""
        context_str = ""
        if agent_context:
            knowledge_base_str = ""
            if agent_context.get("knowledge_base"):
                kb = agent_context.get("knowledge_base", {})
                if isinstance(kb, dict):
                    knowledge_base_str = f"\n- Knowledge Base: {json.dumps(kb, indent=2)}"
                else:
                    knowledge_base_str = f"\n- Knowledge Base: {kb}"

            context_str = f"""
            Agent Context:
            - System Prompt: {agent_context.get('system_prompt', 'N/A')}
            - Knowledge Base: {knowledge_base_str}
            """

        enhanced_instructions = ""
        if turns:
            enhanced_instructions = """
            IMPORTANT: You have access to structured conversation data with speaker labels and timestamps.
            Use this information for more accurate analysis:
            - Analyze each turn separately, understanding who said what
            - Track workflow progression temporally using timestamps
            - Identify exact moments when deviations or issues occurred
            - Match agent responses to specific user intents
            - Use speaker labels to distinguish user vs agent statements
            """

        prompt = f"""
        You are an expert QA analyst evaluating a customer service call with full context. Analyze the following conversation and extract:

        1. INTENT MATCH/MISMATCH:
        - Detect the user's primary intent (analyze each user turn if turn data available)
        - Compare with expected intent based on agent context
        - Track intent evolution throughout conversation if multiple user turns
        - Match agent responses to user intents
        - Provide confidence score (0-1)
        - Include evidence snippet with turn/timestamp if available

        2. HALLUCINATION DETECTION:
        - Identify if agent made unsupported claims or fabricated information
        - Compare agent statements against agent's knowledge base and system prompt
        - Only flag as hallucination if claim is NOT in knowledge base or system prompt
        - List specific segments with potential hallucinations (include turn/timestamp)
        - Provide confidence score (0-1)
        - Explain why it's a hallucination

        3. WORKFLOW/SCRIPT DEVIATION:
        - Track workflow progression temporally using timestamps
        - Compare actual conversation flow with expected workflow step-by-step
        - Identify skipped steps, wrong order, or deviations with exact timestamps
        - List expected vs actual steps with timing information
        - Provide deviation segments with turn information

        4. TASK COMPLETION:
        - Verify each expected task with turn-level evidence
        - Track task completion signals across conversation turns
        - Determine if user's goal/task was successfully completed
        - Provide confidence score (0-1)
        - Include evidence with specific turn/timestamp

        5. ESCALATION:
        - Detect if escalation was triggered
        - Identify exact timestamp and triggering turn if available
        - Identify escalation type (technical, supervisor, etc.)
        - Note what user said that triggered escalation

        {enhanced_instructions}

        {conversation_structure}

        {temporal_context}

        {speaker_context}

        {context_str}

        CONVERSATION (Full Text):
        {transcription}

        Respond with JSON in this exact format:
        {{
        "intent_match": {{
            "detected_intent": "string",
            "expected_intent": "string or null",
            "is_match": true/false,
            "confidence": 0.0-1.0,
            "evidence": "string or null"
        }},
        "hallucination": {{
            "has_hallucination": true/false,
            "hallucination_segments": ["string"],
            "confidence": 0.0-1.0,
            "explanation": "string or null"
        }},
        "workflow_deviation": {{
            "has_deviation": true/false,
            "deviation_type": "string or null",
            "expected_steps": ["string"],
            "actual_steps": ["string"],
            "deviation_segments": ["string"]
        }},
        "task_completion": true/false,
        "task_completion_confidence": 0.0-1.0,
        "task_completion_evidence": "string or null",
        "escalation_triggered": true/false,
        "escalation_type": "string or null",
        "escalation_timestamp_ms": number or null
        }}
        """

        return prompt

    def _sanitize_malformed_json(self, text: str) -> str:
        """Best-effort cleanup for common malformed JSON patterns from LLMs."""
        sanitized = text.strip()

        sanitized = re.sub(r"^```json\s*", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"^```\s*", "", sanitized)
        sanitized = re.sub(r"\s*```$", "", sanitized)

        sanitized = re.sub(r",\s*([}\]])", r"\1", sanitized)

        sanitized = re.sub(
            r'("(?:[^"\\]|\\.)*"\s*:\s*(?:"(?:[^"\\]|\\.)*"|\{[^{}]*\}|\[[^\]]*\]|true|false|null|-?\d+(?:\.\d+)?))\s*("(?:[^"\\]|\\.)*"\s*:)',
            r"\1, \2",
            sanitized,
            flags=re.DOTALL,
        )

        return sanitized.strip()

    def _default_intent_payload(self) -> dict[str, Any]:
        """Safe default payload when LLM JSON cannot be parsed."""
        return {
            "intent_match": None,
            "hallucination": None,
            "workflow_deviation": None,
            "task_completion": False,
            "task_completion_confidence": 0.0,
            "task_completion_evidence": None,
            "escalation_triggered": False,
            "escalation_type": None,
            "escalation_timestamp_ms": None,
        }

    def _extract_json_from_response(self, response: str) -> str:
        """Extract and clean JSON from an LLM response (fences, preamble, trailing commas)."""
        content_str = response.strip()

        content_str = re.sub(r"^```(?:json)?\s*\n?", "", content_str, flags=re.IGNORECASE)
        content_str = re.sub(r"\n?\s*```\s*$", "", content_str)
        content_str = content_str.strip()

        if not content_str.startswith("{") and not content_str.startswith("["):
            first_brace = content_str.find("{")
            first_bracket = content_str.find("[")
            if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
                content_str = content_str[first_brace:]
            elif first_bracket != -1:
                content_str = content_str[first_bracket:]

        if content_str.startswith("{"):
            brace_count = 0
            in_string = False
            escape_next = False
            json_end_idx = -1

            for i, char in enumerate(content_str):
                if escape_next:
                    escape_next = False
                    continue
                if char == "\\":
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end_idx = i
                            break

            if json_end_idx != -1:
                content_str = content_str[: json_end_idx + 1]

        content_str = re.sub(r",\s*([}\]])", r"\1", content_str)

        return content_str

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response into structured data."""
        content_str = self._extract_json_from_response(response)

        try:
            result = json.loads(content_str)
            converted = self._convert_to_models(result)
            converted["_warnings"] = []
            return converted
        except json.JSONDecodeError as e:
            logger.warning("JSON parse attempt 1 failed: %s", e)
            try:
                sanitized = self._sanitize_malformed_json(content_str or response)
                result = json.loads(sanitized)
                converted = self._convert_to_models(result)
                converted["_warnings"] = [
                    {
                        "code": "INTENT_JSON_PARSE_FAILED_DEFAULTED",
                        "message": "Intent JSON required sanitization before parsing.",
                        "component": "intent_quality",
                    }
                ]
                return converted
            except Exception as parse_error:
                logger.error(
                    "Fallback parsing also failed: %s — response: %.500s", parse_error, response
                )
                default_payload = self._default_intent_payload()
                default_payload["_warnings"] = [
                    {
                        "code": "INTENT_JSON_PARSE_FAILED_DEFAULTED",
                        "message": "Intent JSON parse failed; default intent payload applied.",
                        "component": "intent_quality",
                    }
                ]
                return default_payload

    def _normalize_segments(self, segments: list[Any]) -> list[str]:
        """Normalize segments from LLM response — handle string arrays and object arrays."""
        normalized = []
        for segment in segments:
            if isinstance(segment, str):
                normalized.append(segment)
            elif isinstance(segment, dict):
                segment_text = (
                    segment.get("segment")
                    or segment.get("text")
                    or segment.get("content")
                    or segment.get("snippet")
                )
                if segment_text and isinstance(segment_text, str):
                    normalized.append(segment_text)
        return normalized

    def _convert_to_models(self, result: dict[str, Any]) -> dict[str, Any]:
        """Convert parsed JSON result to model objects."""
        intent_match_data = result.get("intent_match", {})
        intent_match = (
            IntentMatch(
                detected_intent=intent_match_data.get("detected_intent", ""),
                expected_intent=intent_match_data.get("expected_intent"),
                is_match=intent_match_data.get("is_match", False),
                confidence=float(intent_match_data.get("confidence", 0.0)),
                evidence=intent_match_data.get("evidence"),
            )
            if intent_match_data
            else None
        )

        hallucination_data = result.get("hallucination", {})
        hallucination = (
            HallucinationDetection(
                has_hallucination=hallucination_data.get("has_hallucination", False),
                hallucination_segments=self._normalize_segments(
                    hallucination_data.get("hallucination_segments", [])
                ),
                confidence=float(hallucination_data.get("confidence", 0.0)),
                explanation=hallucination_data.get("explanation"),
            )
            if hallucination_data
            else None
        )

        workflow_data = result.get("workflow_deviation", {})
        workflow_deviation = (
            WorkflowDeviation(
                has_deviation=workflow_data.get("has_deviation", False),
                deviation_type=workflow_data.get("deviation_type"),
                expected_steps=workflow_data.get("expected_steps", []),
                actual_steps=workflow_data.get("actual_steps", []),
                deviation_segments=self._normalize_segments(
                    workflow_data.get("deviation_segments", [])
                ),
            )
            if workflow_data
            else None
        )

        return {
            "intent_match": intent_match,
            "hallucination": hallucination,
            "workflow_deviation": workflow_deviation,
            "task_completion": result.get("task_completion", False),
            "task_completion_confidence": float(result.get("task_completion_confidence", 0.0)),
            "task_completion_evidence": result.get("task_completion_evidence"),
            "escalation_triggered": result.get("escalation_triggered", False),
            "escalation_type": result.get("escalation_type"),
            "escalation_timestamp_ms": result.get("escalation_timestamp_ms"),
        }
