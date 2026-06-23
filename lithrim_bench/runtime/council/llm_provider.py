"""LLM provider factory — OpenAI direct vs Azure OpenAI behind a single flag.

Exposes ``get_sync_openai_client`` and ``get_async_openai_client`` keyed on a
``purpose`` literal (``"council"`` → full model, ``"mini"`` → mini model).
When ``settings.LITHRIM_LLM_PROVIDER == "azure"`` the returned client is
``AzureOpenAI`` / ``AsyncAzureOpenAI`` and the model string is the Azure
deployment name (``AZURE_OPENAI_DEPLOYMENT_COUNCIL`` / ``_MINI``). Default
provider is ``"openai"``; returned model strings are ``"gpt-4o"`` / ``"gpt-4o-mini"``.

Clients are cached at module scope by (kind, provider, purpose) so repeated
construction does not re-open connection pools — replacing the previous
``_shared_openai_client`` singleton inside ``compliance_council.py``.

Callers receive a tuple ``(client, model_or_deployment)``; the model string
is passed explicitly to ``client.chat.completions.create(model=..., ...)``.
"""

from __future__ import annotations

from typing import Any, Literal

from openai import AsyncAzureOpenAI, AsyncOpenAI, AzureOpenAI, OpenAI

from .settings import settings

Purpose = Literal["council", "mini", "validation_council", "mistral_judge", "meta_judge"]

SyncClient = OpenAI | AzureOpenAI
AsyncClient = AsyncOpenAI | AsyncAzureOpenAI

_PROVIDER_OPENAI = "openai"
_PROVIDER_AZURE = "azure"

# (kind, provider, purpose) → client instance
_client_cache: dict[tuple[str, str, str], Any] = {}


def _resolve_model(provider: str, purpose: Purpose) -> str:
    if provider == _PROVIDER_AZURE:
        if purpose in ("council", "validation_council"):
            return settings.AZURE_OPENAI_DEPLOYMENT_COUNCIL
        if purpose == "mistral_judge":
            # BRS-3 council-v2 policy_judge target. AzureOpenAI SDK reaches
            # Mistral-Large-3 via deployment-id substitution (SDK compat
            # confirmed by smoke 2026-05-27, 200 OK on chat.completions).
            dep = settings.AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3
            if not dep:
                raise ValueError(
                    "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3 is required when "
                    "purpose='mistral_judge' (COMPLIANCE_COUNCIL_VERSION=v2)"
                )
            return dep
        if purpose == "meta_judge":
            # BRS-3 council-v2 faithfulness_judge target. Same SDK path as
            # Mistral; logprobs supported (SDK exposes logprobs.content with
            # ChatCompletionTokenLogprob entries per call 2 smoke).
            dep = settings.AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK
            if not dep:
                raise ValueError(
                    "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK is required when "
                    "purpose='meta_judge' (COMPLIANCE_COUNCIL_VERSION=v2)"
                )
            return dep
        return settings.AZURE_OPENAI_DEPLOYMENT_MINI
    # openai path — hardcoded; CONFIDENCE_GATE_MODEL / ARTIFACT_EVAL_MODEL
    # settings are inert as of C15-B (factory owns model resolution).
    # validation_council purpose (Sub-G-1) targets gpt-4.1 on Azure;
    # openai-direct fallback uses gpt-4o (closest available capability).
    if purpose in ("council", "validation_council"):
        return "gpt-4o"
    if purpose in ("mistral_judge", "meta_judge"):
        # BRS-3 council-v2: Mistral-Large-3 and Llama-4-Maverick have no
        # openai.com analog; v2 requires LITHRIM_LLM_PROVIDER=azure. v1
        # default behavior is unaffected (these purposes are only requested
        # under COMPLIANCE_COUNCIL_VERSION=v2).
        raise ValueError(
            f"purpose={purpose!r} requires LITHRIM_LLM_PROVIDER=azure; "
            f"openai-direct has no equivalent deployment"
        )
    return "gpt-4o-mini"


def _validate_azure() -> None:
    if not settings.AZURE_OPENAI_ENDPOINT:
        raise ValueError("AZURE_OPENAI_ENDPOINT is required when LITHRIM_LLM_PROVIDER=azure")
    if not settings.AZURE_OPENAI_API_KEY:
        raise ValueError("AZURE_OPENAI_API_KEY is required when LITHRIM_LLM_PROVIDER=azure")


def _current_provider() -> str:
    provider = settings.LITHRIM_LLM_PROVIDER
    if provider not in (_PROVIDER_OPENAI, _PROVIDER_AZURE):
        raise ValueError(f"LITHRIM_LLM_PROVIDER must be 'openai' or 'azure', got {provider!r}")
    return provider


def get_sync_openai_client(purpose: Purpose) -> tuple[SyncClient, str]:
    """Return a sync OpenAI/AzureOpenAI client + model string for the purpose."""
    provider = _current_provider()
    cache_key = ("sync", provider, purpose)
    model = _resolve_model(provider, purpose)

    cached = _client_cache.get(cache_key)
    if cached is not None:
        return cached, model

    if provider == _PROVIDER_AZURE:
        _validate_azure()
        client: SyncClient = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    else:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

    _client_cache[cache_key] = client
    return client, model


def get_async_openai_client(purpose: Purpose) -> tuple[AsyncClient, str]:
    """Return an async OpenAI/AzureOpenAI client + model string for the purpose."""
    provider = _current_provider()
    cache_key = ("async", provider, purpose)
    model = _resolve_model(provider, purpose)

    cached = _client_cache.get(cache_key)
    if cached is not None:
        return cached, model

    if provider == _PROVIDER_AZURE:
        _validate_azure()
        client: AsyncClient = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    else:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    _client_cache[cache_key] = client
    return client, model


def reset_clients() -> None:
    """Drop cached clients. Test fixtures call this between provider flips."""
    _client_cache.clear()
