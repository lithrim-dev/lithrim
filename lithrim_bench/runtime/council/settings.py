"""Council-runtime configuration — the SUBSET of lithrim-backend Settings that
the vendored compliance council actually reads.

WS-6c (bench-salvage): the parked package previously vendored the *entire*
backend ``Settings`` (Mongo / S3 / JWT / Celery / Pinecone / LiveKit / …). This
subset keeps ONLY the 16 fields read by ``compliance_council.py``,
``llm_provider.py`` and ``phi_redaction.py`` (grep-verified read-set), so the
council config surface is legible and carries none of the retired-stack
baggage. Field types and defaults are ported verbatim from
``lithrim-backend@493b533 app/config.py`` with ONE deliberate change, flagged
inline: ``COMPLIANCE_COUNCIL_VERSION`` defaults to ``"v2"`` here (the backend
default is ``"v1"``).

Env / ``.env`` override is preserved (``case_sensitive=True``) so the live Azure
smoke can inject the endpoint + key + the three v2 deployment names at runtime.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The council-runtime config subset (the 16 fields the council reads)."""

    # ── LLM provider selector ────────────────────────────────────────────
    # "openai" = direct OpenAI API; "azure" = Azure OpenAI via the AZURE_*
    # fields below (``llm_provider._resolve_model`` picks the deployment per
    # purpose). v2 HARD-requires "azure" for the Mistral/Llama judges.
    LITHRIM_LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    # BYOK single-provider council (Cycle 1): when LITHRIM_LLM_PROVIDER=openai and OPENAI_API_KEY
    # is set, each judge role binds to its model below on the user's ONE key (no Azure trio).
    # Default gpt-4o for all three (reliable; supports logprobs+json so the calibrated-confidence
    # path still works); override per role for intra-provider model diversity (KEEP THE MULTI-COUNCIL).
    OPENAI_MODEL_RISK: str = "gpt-4o"
    OPENAI_MODEL_POLICY: str = "gpt-4o"
    OPENAI_MODEL_FAITHFULNESS: str = "gpt-4o"

    # ── Per-role provider override (PROVIDER-CENTER-A, S-BS-MR1a-CROSSPROVIDER) ──────────
    # The cross-provider-per-role UNLOCK: each judge role may run on ANY configured provider
    # (risk→OpenAI, policy→Gemini, faithfulness→Anthropic). A GENERIC per-role binding the registry
    # bind writes (LITHRIM_LLM_{PROVIDER,MODEL,API_KEY,API_BASE}_<ROLE>). Defaults "" so when NONE is
    # set ``build_judge_lm`` falls through to the byte-identical global path (the regression guard).
    # PROVIDER values: openai | azure | anthropic | gemini | bedrock | openai_compatible (the litellm
    # path speaks them all). The per-role MAP keyed by role lives in ``judges_dspy._ROLE_PROVIDER_KEYS``
    # (a module constant, OUTSIDE the frozen consensus seam).
    LITHRIM_LLM_PROVIDER_RISK: str = ""
    LITHRIM_LLM_MODEL_RISK: str = ""
    LITHRIM_LLM_API_KEY_RISK: str = ""
    LITHRIM_LLM_API_BASE_RISK: str = ""
    LITHRIM_LLM_PROVIDER_POLICY: str = ""
    LITHRIM_LLM_MODEL_POLICY: str = ""
    LITHRIM_LLM_API_KEY_POLICY: str = ""
    LITHRIM_LLM_API_BASE_POLICY: str = ""
    LITHRIM_LLM_PROVIDER_FAITHFULNESS: str = ""
    LITHRIM_LLM_MODEL_FAITHFULNESS: str = ""
    LITHRIM_LLM_API_KEY_FAITHFULNESS: str = ""
    LITHRIM_LLM_API_BASE_FAITHFULNESS: str = ""

    # CONNECT-AI-AZURE-1: the per-role Azure ``api_version`` for a per-role azure provider override.
    # The GLOBAL azure trio threads ``AZURE_OPENAI_API_VERSION``; a UI-bound per-role azure judge (the
    # cross-provider unlock) needs its OWN version or litellm hits the api-version / DeploymentNotFound
    # wall. Default "" → ``build_judge_lm``'s per-role azure branch falls back to
    # ``AZURE_OPENAI_API_VERSION`` (the council default). Only the per-role azure path reads these.
    LITHRIM_LLM_API_VERSION_RISK: str = ""
    LITHRIM_LLM_API_VERSION_POLICY: str = ""
    LITHRIM_LLM_API_VERSION_FAITHFULNESS: str = ""

    # Gemini (litellm reads GEMINI_API_KEY from env when a per-role api_key is not threaded in).
    GEMINI_API_KEY: str = ""

    # ── Azure OpenAI ─────────────────────────────────────────────────────
    # The v2 cross-provider trio reaches Mistral-Large-3 + Llama-4-Maverick by
    # deployment-id substitution on the AzureOpenAI SDK (smoke-verified, Q2).
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    AZURE_OPENAI_DEPLOYMENT_COUNCIL: str = "gpt-4.1"
    AZURE_OPENAI_DEPLOYMENT_MINI: str = "gpt-4.1-mini"
    # Default None so an openai-direct host without these env vars still boots.
    AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3: str | None = None
    AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK: str | None = None

    # ── Compliance council ───────────────────────────────────────────────
    # WS-6c DELIBERATE CHANGE vs backend (which defaults "v1"): the bench
    # ports the validated cross-provider trio and defaults to v2 per the WS-6b
    # ratification (v2-only). The v1 branch is ported verbatim but unused by
    # default. Override to "v1" via env only for differential testing.
    COMPLIANCE_COUNCIL_VERSION: Literal["v1", "v2"] = "v2"
    COMPLIANCE_COUNCIL_MAX_MODELS: int = 3
    COMPLIANCE_COUNCIL_MODEL_TIMEOUT_SECONDS: int = 120
    COMPLIANCE_COUNCIL_TOTAL_BUDGET_SECONDS: int = 400
    # Sampling layer (judge_call): how many completions each judge requests per
    # grade via the native ``n`` parameter (k). Default 1 ⇒ a single completion,
    # byte-equivalent to the pre-sampling council. k>1 makes ONE API call returning
    # k completions to estimate per-judge decision stability (score_mean/variance);
    # DSPy forces temperature 0.7 when n>1, so k>1 is non-deterministic by design.
    # This is a SAMPLING-layer knob, not reviewer config — it never touches the
    # per-role judge bindings, ontology, or prompts.
    COUNCIL_JUDGE_SAMPLES: int = 1

    # ── PHI redaction / HIPAA provider policy (read by phi_redaction.py) ──
    HIPAA_REQUIRE_PHI_REDACTION: bool = True
    HIPAA_REQUIRE_ELIGIBLE_LLM_PROVIDER: bool = False
    HIPAA_ELIGIBLE_LLM_PROVIDERS: list[str] = []

    # extra="ignore": the .env on the read path is the shared lithrim-backend env,
    # which carries many backend-only vars (persona-bot / elevenlabs / recording /
    # etlp-mapper / eval / playground …) this 16-field SUBSET deliberately doesn't
    # declare. Tolerate them — undeclared backend vars must not crash the council
    # (pydantic-settings defaults extra="forbid", which made the in-process council
    # die the moment the backend .env grew).
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
