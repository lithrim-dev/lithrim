"""LOGPROBS-MODEL-GRANULAR-1: the per-model logprobs capability check must match empirical +
registry reality.

Live-proven 2026-07-19 against the Azure AI Foundry resource:
  - azure/gpt-4.1        + logprobs -> 200, logprobs returned
  - azure/gpt-5.4        + logprobs -> 200, logprobs returned   (was WRONGLY excluded by "gpt-5")
  - azure/Mistral-Large-3 + logprobs -> 400 "Logprobs are not enabled for this model" (all routes)

The model registry catalog already marks gpt-5-x logprobs=True (tests/bff/test_model_registry_live.py),
so the runtime denylist excluding "gpt-5" was internally inconsistent AND cost gpt-5.4 its calibrated
confidence (faithfulness_judge ran confidence-dark). The reasoning o-series and the non-OpenAI
Azure-MaaS families (Mistral/Llama) are the genuine rejecters.
"""
from lithrim_bench.runtime.council import judges_dspy as J


def test_gpt5_chat_supports_logprobs():
    # the fix: gpt-5.x chat models return logprobs (proven live); must NOT be excluded
    assert J._model_supports_logprobs("azure", "gpt-5.4") is True
    assert J._model_supports_logprobs("azure", "gpt-4.1") is True


def test_azure_maas_families_are_confidence_dark():
    # Mistral/Llama on Azure reject the logprobs param (400); must be excluded so the request omits it
    assert J._model_supports_logprobs("azure", "Mistral-Large-3") is False
    assert J._model_supports_logprobs("azure", "mistral-large-latest") is False
    assert J._model_supports_logprobs("azure", "Llama-3.3-70B") is False


def test_openai_reasoning_families_still_excluded():
    # the o-series reasoning models reject logprobs (DRYRUN-2026-07-03) — unchanged
    assert J._model_supports_logprobs("openai", "o1-preview") is False
    assert J._model_supports_logprobs("openai", "o3-mini") is False


def test_confidence_dark_providers_unchanged():
    # anthropic/gemini/bedrock/openai_compatible stay dark at the provider level
    assert J._model_supports_logprobs("openai_compatible", "gpt-4.1") is False
    assert J._model_supports_logprobs("anthropic", "claude-opus-4-8") is False
