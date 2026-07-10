"""Sentiment analysis agent for analyzing user sentiment.

Ported from ``lithrim-backend@mvp-ready`` ``app/agents/sentiment_agent/agent.py``.
Mechanical adaptations only: ``get_gemini_service`` → the injectable/lazy
``_LlmBackedAgent`` base; ``app.models.call_kpi`` → ``..models``; the module-level
singleton is dropped (instantiation hoisted). Prompt + JSON-repair faithful.
"""

import asyncio
import json
from typing import Any

from ..models import SentimentMetrics, TurnSentiment
from ._llm import _LlmBackedAgent


class SentimentAgent(_LlmBackedAgent):
    """Agent for analyzing sentiment in conversations."""

    async def analyze_sentiment(
        self,
        include_turn_level: bool = False,
        transcription_data: dict[str, Any] | None = None,
        conversation_structure: str | None = None,
        temporal_context: str | None = None,
        speaker_context: str | None = None,
        agent_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze sentiment in conversation."""
        try:
            transcription = transcription_data.get("transcription", "")
            prompt = self._build_sentiment_prompt(
                transcription=transcription,
                include_turn_level=include_turn_level,
                transcription_data=transcription_data,
                conversation_structure=conversation_structure,
                temporal_context=temporal_context,
                speaker_context=speaker_context,
                agent_context=agent_context,
            )

            formatted_prompt = self.gemini_service.create_prompt_template(prompt)
            response = await asyncio.to_thread(self.gemini_service.invoke_llm, formatted_prompt)

            sentiment_result = self._parse_response(response, include_turn_level)

            sentiment_metrics = SentimentMetrics(
                user_sentiment_final=sentiment_result.get("user_sentiment_final", ""),
                user_sentiment_confidence=float(
                    sentiment_result.get("user_sentiment_confidence", 0.0)
                ),
                user_sentiment_rationale=sentiment_result.get("user_sentiment_rationale", ""),
                agent_sentiment_final=sentiment_result.get("agent_sentiment_final", ""),
                agent_sentiment_confidence=sentiment_result.get("agent_sentiment_confidence", 0.0),
                agent_sentiment_rationale=sentiment_result.get("agent_sentiment_rationale", ""),
                alerts=sentiment_result.get("alerts", []),
                turn_level_sentiments=sentiment_result.get("turn_level_sentiments", []),
            )

            return {
                "success": True,
                "metrics": sentiment_metrics,
                "error": None,
            }

        except Exception as e:  # noqa: BLE001
            return {
                "success": False,
                "error": str(e),
                "metrics": None,
            }

    def _build_sentiment_prompt(
        self,
        transcription: str,
        include_turn_level: bool,
        transcription_data: dict[str, Any] | None,
        conversation_structure: str | None = None,
        temporal_context: str | None = None,
        speaker_context: str | None = None,
        agent_context: dict[str, Any] | None = None,
    ) -> str:
        """Build the sentiment analysis prompt using provided structured context."""
        conversation_block = (
            f"Conversation Structure:\n{conversation_structure}\n"
            if conversation_structure
            else f"Conversation (unstructured):\n{transcription}\n"
        )

        temporal_block = f"\nTemporal Context:\n{temporal_context}\n" if temporal_context else ""
        speaker_block = f"\nSpeaker Context:\n{speaker_context}\n" if speaker_context else ""

        agent_block = ""
        if agent_context:
            agent_block = "\nAgent Context:\n"
            system_prompt = agent_context.get("system_prompt")
            knowledge_base = agent_context.get("knowledge_base")
            if system_prompt:
                agent_block += f"- System Prompt: {system_prompt}\n"
            if knowledge_base:
                agent_block += f"- Knowledge Base: {json.dumps(knowledge_base, indent=2)}\n"

        segments = []
        if transcription_data:
            segments = transcription_data.get("segments", [])

        segments_block = ""
        if segments:
            segments_block = (
                "\nSegments (timestamped):\n"
                + "\n".join(
                    [
                        f"- t={seg.get('start_ms','?')} -> {seg.get('end_ms','?')} ms | "
                        f"{seg.get('speaker','unknown')}: {seg.get('text','')}"
                        for seg in segments
                    ]
                )
                + "\n"
            )

        turn_instruction = ""
        if include_turn_level:
            turn_instruction = """
            Also provide turn-level sentiment analysis using the structured turns (and timestamps if present):
            - For EACH turn (user and agent), classify sentiment (positive/neutral/negative)
            - Provide confidence score (0-1)
            - Include timestamp_ms if available
            - Add brief rationale and any alert flags (e.g., frustration, escalation_risk)
            """

        prompt = f"""
        You are a sentiment analysis expert. Use the provided structured context to evaluate the conversation.

        Goals:
        1. FINAL USER SENTIMENT:
        - Determine the user's overall sentiment at the end of the conversation (positive/neutral/negative)
        - Provide confidence score (0-1)
        - Provide a brief rationale referencing the turns/segments
        - Consider the entire conversation context, not just the last message

        2. FINAL AGENT SENTIMENT:
        - Determine the agent's overall sentiment (positive/neutral/negative)
        - Provide confidence score (0-1)
        - Provide a brief rationale referencing the turns/segments

        3. ALERTS:
        - Identify and list any alert flags (e.g., frustration, escalation_risk, confusion, dissatisfaction, praise)
        - Base alerts on evidence in the conversation; keep list empty if none

        {turn_instruction}

        INPUT DATA:
        {agent_block}
        {conversation_block}
        {segments_block}
        {temporal_block}
        {speaker_block}

        Respond with JSON in this exact format:
        {{
        "user_sentiment_final": "positive|neutral|negative",
        "user_sentiment_confidence": 0.0-1.0,
        "user_sentiment_rationale": "short explanation",
        "agent_sentiment_final": "positive|neutral|negative",
        "agent_sentiment_confidence": 0.0-1.0,
        "agent_sentiment_rationale": "short explanation",
        "alerts": ["frustration", "escalation_risk"],
        "turn_level_sentiments": [
            {{
            "turn_number": 1,
            "speaker": "user",
            "sentiment": "positive|neutral|negative",
            "confidence": 0.0-1.0,
            "timestamp_ms": 1000.0,
            "rationale": "brief reasoning",
            "alerts": ["frustration"]
            }}
        ]
        }}

        If turn-level analysis is not requested, return an empty array for turn_level_sentiments.
        """

        return prompt

    def _extract_json_content(self, response: str) -> str:
        """Extract first JSON object from response with string-aware brace counting."""
        content_str = response.strip()
        if "```json" in content_str:
            content_str = content_str.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in content_str:
            content_str = content_str.split("```", 1)[1].split("```", 1)[0].strip()

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

        return content_str.strip()

    def _parse_response(self, response: str, include_turn_level: bool) -> dict[str, Any]:
        """Parse LLM response into structured data."""
        content_str = self._extract_json_content(response)

        def _safe_float(val: Any, default: float = 0.0) -> float:
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        try:
            result = json.loads(content_str)
        except json.JSONDecodeError:
            try:
                start_idx = response.find("{")
                if start_idx != -1:
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    end_idx = -1
                    for i in range(start_idx, len(response)):
                        char = response[i]
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
                                    end_idx = i
                                    break
                    if end_idx != -1:
                        json_str = response[start_idx : end_idx + 1]
                        result = json.loads(json_str)
                    else:
                        raise ValueError("Could not find complete JSON object")
                else:
                    raise ValueError("No JSON object found in response")
            except Exception as parse_error:  # noqa: BLE001
                raise ValueError(f"Failed to parse JSON response: {parse_error}") from parse_error

        user_sentiment_final = result.get("user_sentiment_final", "neutral")
        user_sentiment_confidence = _safe_float(result.get("user_sentiment_confidence", 0.0))
        user_sentiment_rationale = result.get("user_sentiment_rationale")

        if isinstance(user_sentiment_final, dict):
            user_sentiment_rationale = user_sentiment_rationale or user_sentiment_final.get(
                "rationale"
            )
            user_sentiment_confidence = _safe_float(
                user_sentiment_final.get("confidence", user_sentiment_confidence)
            )
            user_sentiment_final = (
                user_sentiment_final.get("label")
                or user_sentiment_final.get("sentiment")
                or "neutral"
            )

        agent_sentiment_final = result.get("agent_sentiment_final")
        agent_sentiment_confidence = _safe_float(result.get("agent_sentiment_confidence"))
        agent_sentiment_rationale = result.get("agent_sentiment_rationale")

        alerts = result.get("alerts", [])
        if not isinstance(alerts, list):
            alerts = []

        turn_sentiments: list[TurnSentiment] = []
        if include_turn_level:
            for turn_data in result.get("turn_level_sentiments", []):
                if not isinstance(turn_data, dict):
                    continue
                alerts_list = turn_data.get("alerts", [])
                if not isinstance(alerts_list, list):
                    alerts_list = []
                turn_sentiments.append(
                    TurnSentiment(
                        turn_number=turn_data.get("turn_number", 0),
                        speaker=turn_data.get("speaker", "user"),
                        sentiment=turn_data.get("sentiment", "neutral"),
                        confidence=_safe_float(turn_data.get("confidence", 0.0)),
                        timestamp_ms=_safe_float(turn_data.get("timestamp_ms", 0.0)),
                        rationale=turn_data.get("rationale"),
                        alerts=alerts_list,
                    )
                )

        return {
            "user_sentiment_final": user_sentiment_final,
            "user_sentiment_confidence": user_sentiment_confidence,
            "user_sentiment_rationale": user_sentiment_rationale,
            "agent_sentiment_final": agent_sentiment_final,
            "agent_sentiment_confidence": agent_sentiment_confidence,
            "agent_sentiment_rationale": agent_sentiment_rationale,
            "alerts": alerts,
            "turn_level_sentiments": turn_sentiments,
        }

    def _aggregate_speaker_sentiment(
        self, turn_sentiments: list[TurnSentiment], speaker: str
    ) -> tuple[str | None, float, str | None]:
        """Aggregate turn-level sentiments into a single speaker sentiment.

        Returns (label, confidence, rationale).
        """
        speaker_turns = [t for t in turn_sentiments if t.speaker == speaker]
        if not speaker_turns:
            return None, 0.0, None

        score_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
        weighted_sum = 0.0
        weight_total = 0.0
        counts = {"positive": 0, "neutral": 0, "negative": 0}

        for t in speaker_turns:
            val = score_map.get(t.sentiment, 0.0)
            weighted_sum += val * t.confidence
            weight_total += t.confidence if t.confidence else 1.0
            if t.sentiment in counts:
                counts[t.sentiment] += 1

        avg_score = weighted_sum / weight_total if weight_total else 0.0
        if avg_score > 0.15:
            label = "positive"
        elif avg_score < -0.15:
            label = "negative"
        else:
            label = "neutral"

        confidence = min(1.0, abs(avg_score)) if weight_total else 0.0
        rationale = f"Derived from {len(speaker_turns)} {speaker} turn(s); distribution {counts}"
        return label, confidence, rationale
