"""Offline fixtures for the recomposed observation pipeline.

No network, no Celery/Mongo, no ``openai``/whisper: the 3 LLM agents are driven by
an injected ``StubLLM`` returning canned JSON; the input is a text case (the audio
path is not exercised — its DSP bodies are deferred behind ``[observation]``).
"""

import json
from typing import Any

import pytest

# One text case (no audio) — exercises the text branch + the 4-way fan-out.
TEXT_CASE: dict[str, Any] = {
    "session_id": "sess-obs-1",
    "agent_id": "agent-obs-1",
    "organization_id": "org-obs-1",
    "file_path": "calls/obs_case_1.txt",
    "item_id": "item-obs-1",
    "transcript": (
        "User: Hi, I need to refill my prescription.\n"
        "Agent: Of course — I've refilled your prescription, it's ready for pickup.\n"
        "User: Great, thank you so much!"
    ),
    "agent_context": {"system_prompt": "You are a helpful pharmacy support agent."},
}

# Canned per-agent JSON keyed on a distinctive prompt substring.
_CANNED = {
    "INTENT MATCH": {
        "intent_match": {
            "detected_intent": "prescription_refill",
            "expected_intent": "prescription_refill",
            "is_match": True,
            "confidence": 0.92,
            "evidence": "User: I need to refill my prescription.",
        },
        "hallucination": {
            "has_hallucination": False,
            "hallucination_segments": [],
            "confidence": 0.9,
            "explanation": None,
        },
        "workflow_deviation": {
            "has_deviation": False,
            "deviation_type": None,
            "expected_steps": [],
            "actual_steps": [],
            "deviation_segments": [],
        },
        "task_completion": True,
        "task_completion_confidence": 0.95,
        "task_completion_evidence": "Agent confirmed the refill.",
        "escalation_triggered": False,
        "escalation_type": None,
        "escalation_timestamp_ms": None,
    },
    "sentiment analysis expert": {
        "user_sentiment_final": "positive",
        "user_sentiment_confidence": 0.85,
        "user_sentiment_rationale": "User thanked the agent.",
        "agent_sentiment_final": "positive",
        "agent_sentiment_confidence": 0.8,
        "agent_sentiment_rationale": "Agent was helpful.",
        "alerts": [],
        "turn_level_sentiments": [],
    },
    "PII": {
        "has_pii_leakage": False,
        "pii_types": [],
        "leaked_segments": [],
        "severity": "low",
        "confidence": 0.1,
    },
    "unsafe": {
        "has_unsafe_response": False,
        "unsafe_types": [],
        "unsafe_segments": [],
        "severity": "low",
        "confidence": 0.1,
    },
    "compliance expert": {"violations": []},
}


class StubLLM:
    """Deterministic offline stand-in for ``ObservationLLMService`` (canned JSON)."""

    def __init__(self) -> None:
        self.calls = 0

    def create_prompt_template(self, prompt: str) -> str:
        return prompt

    def invoke_llm(self, prompt: str) -> str:
        self.calls += 1
        for needle, payload in _CANNED.items():
            if needle in prompt:
                return json.dumps(payload)
        # turn-level safety + any other branch → empty turn-level safety
        return json.dumps({"turn_level_safety": []})


@pytest.fixture
def text_case() -> dict[str, Any]:
    return dict(TEXT_CASE)


@pytest.fixture
def stub_llm() -> StubLLM:
    return StubLLM()
