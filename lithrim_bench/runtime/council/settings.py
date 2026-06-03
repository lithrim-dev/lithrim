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
