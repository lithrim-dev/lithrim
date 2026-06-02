"""LLM service shim for the recomposed KPI agents.

The 3 LLM-backed KPI agents (``intent_quality`` / ``sentiment`` / ``safety``)
call exactly two methods of the backend ``app/services/gemini_service.py``
(``GeminiService``): ``create_prompt_template`` (passthrough) and ``invoke_llm``.
This shim reproduces just those two, **reusing the vendored council infra**
(``runtime/council/llm_provider`` + ``phi_redaction``) — the same Azure/OpenAI
client factory the council already ships. ("Gemini" is a legacy class name; the
backend service is an OpenAI/Azure client, ``gemini_service.py:8,68``.)

A2 (default install unchanged): ``openai`` (the ``[council]`` extra) and the
council settings (``pydantic_settings``) are **lazy-imported inside the methods**,
never at module-top, so importing this module — and constructing the agents —
pulls no heavy deps. A real call needs the ``[council]`` extra; tests inject a
stub service via ``_LlmBackedAgent(llm_service=...)`` and never touch ``openai``.
"""

from typing import Any


class ObservationLLMService:
    """Minimal OpenAI/Azure client shim — ``create_prompt_template`` + ``invoke_llm``.

    Mirrors ``gemini_service.GeminiService`` for the two methods the KPI agents
    use; reuses the council ``llm_provider`` (``purpose="mini"`` → the mini
    deployment) and ``phi_redaction``.
    """

    def __init__(self) -> None:
        from ...council.llm_provider import get_sync_openai_client  # lazy: pulls openai

        self._client, self._model = get_sync_openai_client(purpose="mini")
        self._temperature = 0.1
        self._timeout = 30

    def create_prompt_template(self, prompt: str) -> str:
        """Passthrough (the backend kept this as a no-op hook)."""
        return prompt

    def invoke_llm(self, prompt: Any) -> str:
        """Invoke the LLM (sync) and return the message content; PHI-redacted."""
        from ...council.phi_redaction import sanitize_prompt  # lazy

        if isinstance(prompt, list):
            prompt_text = " ".join(
                msg.content if hasattr(msg, "content") else str(msg) for msg in prompt
            )
        else:
            prompt_text = prompt

        sanitized = sanitize_prompt(prompt_text, provider="openai")

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": sanitized}],
            temperature=self._temperature,
            timeout=self._timeout,
        )
        return response.choices[0].message.content.strip() if response.choices[0].message.content else ""


class _LlmBackedAgent:
    """Shared base for the LLM KPI agents — injectable + lazy LLM service.

    The backend agents called ``get_gemini_service()`` eagerly in ``__init__``
    (building an OpenAI client at construction) and exposed a module-level
    singleton (instantiated at import). Both are dropped here: the service is
    **injectable** (a stub in tests) and otherwise built **lazily on first use**,
    so constructing the agent — and the hoisted ``ObservationAgents`` bundle —
    pulls no ``openai`` (A2). Instantiation is hoisted by ``ObservationAgents``.
    """

    def __init__(self, llm_service: Any = None) -> None:
        self._llm_service = llm_service

    @property
    def gemini_service(self) -> Any:
        if self._llm_service is None:
            self._llm_service = ObservationLLMService()
        return self._llm_service
