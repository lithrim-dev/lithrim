"""Configuration settings for the application."""

from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application settings
    APP_NAME: str = "Velto Backend"
    DEBUG: bool = False

    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "velto"

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    # AWS S3 settings
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    S3_ENDPOINT_URL: str = ""  # For MinIO or S3-compatible services (e.g., http://localhost:9000)
    S3_PRESIGNED_URL_EXPIRATION: int = 3600  # Default 1 hour

    # JWT settings
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # OAuth Providers
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # OAuth Redirect URIs
    OAUTH_REDIRECT_URI: str = "http://localhost:8002/auth/callback"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8002"

    # PDF / clinical-report audit-link surfaces.
    # AUDIT_BASE_URL: the live UI host used in the per-case provenance footer
    # of the clinical-report PDF. Defaults to FRONTEND_URL when unset.
    # PUBLIC_AUDIT_BASE_URL: B7-8. When set, the PDF provenance footer renders
    # this URL (suitable for LinkedIn-share). When None, the footer renders
    # "Live audit available on request" plus the pipeline_run_id, so leaking
    # a localhost:3000 link into a shared artifact is impossible by default.
    AUDIT_BASE_URL: str = ""
    PUBLIC_AUDIT_BASE_URL: str = ""

    # CORS Settings
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Email Service
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "noreply@velto.ai"
    EMAIL_FROM_NAME: str = "Velto"

    # Magic Link Settings
    MAGIC_LINK_EXPIRATION_MINUTES: int = 15
    MAGIC_LINK_RATE_LIMIT_PER_EMAIL: int = 3
    MAGIC_LINK_RATE_LIMIT_WINDOW_MINUTES: int = 15

    # Google Gemini settings
    GOOGLE_API_KEY: str = ""

    # OpenAI settings
    OPENAI_API_KEY: str = ""

    # LLM provider selector (C15-B). "openai" = direct OpenAI API.
    # "azure" = Azure OpenAI via AZURE_OPENAI_* settings below; the factory
    # in app/services/llm_provider.py resolves the deployment per purpose.
    LITHRIM_LLM_PROVIDER: str = "openai"
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    AZURE_OPENAI_DEPLOYMENT_COUNCIL: str = "gpt-4.1"
    AZURE_OPENAI_DEPLOYMENT_MINI: str = "gpt-4.1-mini"

    # Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_TASK_TIME_LIMIT: int = 3600  # 1 hour max per task
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300  # 55 minutes soft limit

    AGENTOPS_API_KEY: str | None = None

    # HuggingFace settings (optional, for pyannote.audio private models)
    HUGGINGFACE_TOKEN: str | None = None

    # Vapi webhook settings
    VAPI_WEBHOOK_SECRET: str = ""

    # LiveKit settings
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    LIVEKIT_URL: str = "wss://your-project.livekit.cloud"

    # TTS settings (using OpenAI TTS)
    # Note: ElevenLabs settings kept for potential future use
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # Default voice (Rachel)

    # Recording settings
    RECORDING_STORAGE_PATH: str = "/tmp/velto-recordings"  # Local temp storage
    RECORDING_S3_BUCKET: str = ""  # S3 bucket for recordings (defaults to S3_BUCKET_NAME if empty)
    PERSONA_BOT_TIMEOUT_SECONDS: int = 300  # 5 minutes default timeout

    # Pinecone settings
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = ""
    PINECONE_INDEX_HOST: str = ""
    PINECONE_NAMESPACE: str = ""
    PINECONE_BATCH_SIZE: int = 100

    # HIPAA embedding settings
    HIPAA_DENSE_MODEL_PATH: str = ""
    HIPAA_SPARSE_MODEL_PATH: str = ""
    HIPAA_EMBEDDING_MAX_LENGTH: int = 512

    # SDK compatibility (lithrim_search_sdk uses these names)
    DENSE_MODEL_PATH: str = ""  # Alias for HIPAA_DENSE_MODEL_PATH
    SPARSE_MODEL_PATH: str = ""  # Alias for HIPAA_SPARSE_MODEL_PATH
    HYBRID_QUERY_THRESHOLD: float = 0.9  # Used by SDK for hybrid search weighting

    # HIPAA ingestion settings
    HIPAA_SOURCE_URLS: list[str] = [
        "https://www.ecfr.gov/api/renderer/v1/content/enhanced/2026-01-20/title-45?subtitle=A&subchapter=C&part=160",
        "https://www.ecfr.gov/api/renderer/v1/content/enhanced/2026-01-20/title-45?subtitle=A&subchapter=C&part=164&subpart=C",
        "https://www.ecfr.gov/api/renderer/v1/content/enhanced/2026-01-20/title-45?subtitle=A&subchapter=C&part=164&subpart=E",
        # "https://www.govinfo.gov/content/pkg/PLAW-104publ191/html/PLAW-104publ191.htm",
        # "https://www.govinfo.gov/content/pkg/CFR-2023-title45-vol1/xml/CFR-2023-title45-vol1-part160.xml",
    ]
    HIPAA_VERSION_TAG: str = "2023"
    HIPAA_CORPUS_VERSION: str = "2023"
    HIPAA_REQUEST_TIMEOUT_SECONDS: int = 30
    HIPAA_USER_AGENT: str = "Lithrim HIPAA Ingest/1.0"
    HIPAA_REQUIRE_ELIGIBLE_LLM_PROVIDER: bool = False
    HIPAA_REQUIRE_PHI_REDACTION: bool = True
    HIPAA_REDACT_LOGS: bool = True
    HIPAA_ELIGIBLE_LLM_PROVIDERS: list[str] = []
    HIPAA_ALLOW_NON_STANDARD_REGULATION: bool = False
    HIPAA_ALLOW_NON_US_JURISDICTION: bool = False

    # PHI Redaction Mode: off | basic | strict
    PHI_REDACTION_MODE: str = "basic"

    # HIPAA Audit Workflow Settings
    ENABLE_HIPAA_AUDIT_ALL_FILES: bool = True  # Enable compliance check for all files by default
    HIPAA_QUERY_AUDIO: str = "Evaluate this healthcare call for HIPAA Privacy and Security Rule violations"
    HIPAA_QUERY_TEXT: str = """Evaluate this healthcare chat transcript for HIPAA compliance violations:
- Unauthorized PHI disclosure
- Missing patient consent verification
- Improper handling of protected health information
- Security safeguards violations
- Policy and procedure non-compliance"""

    # Compliance council settings
    COMPLIANCE_COUNCIL_MAX_MODELS: int = 3
    COMPLIANCE_COUNCIL_MODEL_TIMEOUT_SECONDS: int = 120  # F30-ext-2 fix: bumped from 30 (config) and 12 (.env override) to handle Azure gpt-4.1 cross-language reasoning latency. Arabic case 03 needed >60s per judge.
    COMPLIANCE_COUNCIL_TOTAL_BUDGET_SECONDS: int = 400  # 3 judges sequentially at 120s = 360s + 40s buffer

    # Phase B.5 supplement: Ralph Loop critique-pass on artifact_judge.
    # When True, ``_run_artifact_judge`` runs an extra LLM critique step
    # (one call per artifact) that drops safety_flags + findings whose
    # taxonomy_code is not supported by a transcript span. Negation-aware.
    # See ``app/services/artifact_evaluator.py::_critique_artifact_judge_output``
    # and ``docs/research/PHASE_B_DEEP_DIVE_2026-04-29.md`` § Implementation
    # pattern: Ralph Loop, Integration A. Layered with the post-processing
    # filter ``filter_uncorroborated_escalation_flags`` as defense in depth.
    # Production default ``True`` as of DP-SPRINT-B5-SUPPLEMENT-GLOBAL-FLIP
    # cycle, anchored to E2E validation in commit 870c5c4: Stage 1 case-12
    # single-encounter PASS via live Celery analyze_audio (V1 to V5 verbatim
    # in reports/b5_e2e_validation_stage1_case12_2026-05-03.md); Stage 2
    # scribe_v1 12-case pack PARTIAL with verdict_match drift (10/12)
    # CONFIRMED upstream-LLM-variance per the architectural drop-only
    # contract at artifact_evaluator.py:436-453 (the critique mechanically
    # cannot ADD flags or shift faithfulness scores). Phase B.5 supplement
    # itself shipped in commit 49ceb64.
    ARTIFACT_JUDGE_CRITIQUE_PASS_ENABLED: bool = True
    # Phase B.5 supplement (Ralph Loop critique-pass on artifact_judge).
    # Resolves model via get_sync_openai_client(purpose=...). Smoke ablation
    # on case 12 (reports/critique_pass_smoke_ablation_2026-05-03.md) found
    # purpose="mini" (gpt-4.1-mini) conflates hallucination-support with
    # escalation-support; purpose="council" (gpt-4.1) correctly distinguishes
    # them. Council is the empirical default; mini deferred until model-tier
    # reasoning improves OR a tighter anti-conflation prompt is validated.
    ARTIFACT_JUDGE_CRITIQUE_PASS_PURPOSE: Literal["council", "mini"] = "council"

    # BRS-3 Council-v2: cross-provider trio feature flag.
    # When "v1" (default), runs the existing 3x gpt-4.1 monoculture council
    # with tier-evidence consensus + worst-of final verdict aggregation.
    # When "v2", swaps to the cross-provider trio (gpt-4.1 / Mistral-Large-3
    # / Llama-4-Maverick) with capability-flag-aware request building and
    # llama-veto-approve composition over tier-modulated per-judge verdicts.
    # Two-step rollout per spec lithrim-bench docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md
    # section 3.6: deploy with v1 default, user flips to v2 for validation,
    # default flips to v2 in a follow-on commit after A1-A7 acceptance pass.
    COMPLIANCE_COUNCIL_VERSION: Literal["v1", "v2"] = "v1"
    # Per-provider Azure deployment names for the v2 trio. Values match the
    # bench v3 pilot at lithrim-bench commit ffdd3f2 (Azure AI Foundry
    # surfaces both behind the same chat.completions interface as gpt-4.1).
    # Default None so v1 deployments without these env vars set still boot.
    AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK: Optional[str] = None

    # Confidence gate settings
    CONFIDENCE_GATE_THRESHOLD: float = 0.85
    # INERT as of C15-B — factory resolves model per purpose; see llm_provider.py
    CONFIDENCE_GATE_MODEL: str = "gpt-4o-mini"

    # Simulation settings
    SIMULATION_TIMEOUT_SECONDS: int = 300  # 5-minute timeout for scenario polling

    # HIPAA Findings Retrieval Settings
    HIPAA_FINDINGS_QUERY_MODE: str = "facet_v1"  # "facet_v1" or "legacy"
    HIPAA_FINDINGS_ENABLE_DEBUG_LOGS: bool = False

    # etlp-mapper integration settings (structural artifact validation)
    ETLP_MAPPER_URL: str = "http://192.168.1.21:3031"
    # B7-9: share-quality URL for validator-template deep links surfaced
    # on audit-view StructuralFinding rows and in the clinical-report PDF.
    # When set, the audit-view denormaliser and PDF renderer emit
    # ``{ETLP_MAPPER_PUBLIC_URL}/mappings/{etlp_mapping_id}`` per finding.
    # When unset, ``etlp_mapping_url`` stays ``None`` so the internal
    # ETLP_MAPPER_URL (192.168.1.21:3031 by default) never leaks into a
    # LinkedIn-shared PDF. Mirrors the PUBLIC_AUDIT_BASE_URL pattern above.
    ETLP_MAPPER_PUBLIC_URL: str = ""
    ETLP_MAPPER_TIMEOUT_SECONDS: int = 10
    ETLP_MAPPER_ENABLED: bool = False  # Enable when etlp-mapper is running with OIDC_ENABLED=false
    # INERT as of C15-B — factory resolves model per purpose; see llm_provider.py
    ARTIFACT_EVAL_MODEL: str = "gpt-4o-mini"

    # Eval runner tuning (also read via os.environ in eval_runner_tasks.py)
    EVAL_MAX_PARALLEL_CASES: int = 5
    EVAL_BATCH_SIZE: int = 3

    # Pipeline retrieval warmup (Phase 5 Cycle 6, S16)
    # Pre-warm ONNX embedding service + Pinecone client + KB singletons at
    # FastAPI lifespan startup so the first pipeline_run does not pay the
    # cold-start cost inside the 2s per-namespace asyncio.wait_for budget.
    # Opt out in tests / short-lived processes where boot time matters more
    # than first-call latency.
    RETRIEVAL_WARMUP_ON_STARTUP: bool = True

    # KB ops (Phase 2 block 2.6 — Task 53)
    # Role name that gates /v1/admin/kb/* routes. Checked against the JWT
    # user's users.role field by require_role([settings.KB_ADMIN_ROLE]).
    KB_ADMIN_ROLE: str = "admin"

    # HL7v2 Schema KB (Phase 2 block 2.2 — Task 38a)
    # Directory containing segments.yaml, types.yaml, messages.yaml from the
    # etlp-hl7v2 sibling repo. Override via env when the repo layout differs.
    ETLP_HL7V2_RESOURCES_PATH: str = "../etlp-hl7v2/resources"

    # FHIR Schema KB (Phase 2 block 2.2 — Task 38b)
    # Directory containing downloaded FHIR spec zips. Fail-loud if missing —
    # operator runs the curl command surfaced in the error message (no
    # network fetch at reindex time, keeps the path deterministic).
    FHIR_SCHEMA_SOURCES_PATH: str = "data/schema_sources"

    # Code-system KBs (Phase 2 block 2.1 — Task 37)
    # Per-system directories live under here (icd10cm/, loinc/, rxnorm/).
    # Each system's loader resolves its own file via its reindexer config.
    CODE_SYSTEM_SOURCES_PATH: str = "data/code_systems"

    # Template Pattern KB (Phase 2 block 2.3 — Task 36, per-tenant)
    # Read-only connection string to etlp-mapper's Postgres. Ops prerequisite:
    # create a read-only role (e.g. etlp_mapper_ro) with SELECT on mappings
    # and override this env var. Dev default matches etlp-mapper's JDBC_URL.
    ETLP_MAPPER_DB_URL: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    # Shared secret gating POST /v1/admin/kb/hooks/mapping-changed. The Clojure
    # side of etlp-mapper fires the hook as a service; no human-operator JWT
    # is involved. Empty → hook returns 503 (not configured) rather than 403.
    ETLP_MAPPER_HOOK_SECRET: str = ""

    # Playground Phase 4 closing-loop endpoint settings (CYCLE-16-D-v2).
    # Public-tier shared API key. Empty disables the public-tier path,
    # leaving anonymous-with-IP-rate-limit as the only unauthenticated route.
    # Per-org keys (existing api_keys collection) continue to work
    # independently regardless of this value.
    LITHRIM_PLAYGROUND_PUBLIC_API_KEY: str = ""
    # slowapi rate-limit string applied to POST /v1/playground/phase4-loop/*.
    # Per driver §1, default is the cold-prospect-friendly 10 req/min per IP.
    LITHRIM_PLAYGROUND_RATE_LIMIT: str = "10/minute"
    # Mongo collection holding cached Copilot results keyed on
    # (case_id, copilot_input_hash). Created on first cache write; index
    # ensured by the orchestrator at first use.
    LITHRIM_PLAYGROUND_CACHE_COLLECTION: str = "playground_phase4_cache"
    # CYCLE-16-D-v2 Sub-G-2: feature flag for Validation Council insertion at
    # Sub-A stage 2.5. Default False preserves existing 10 Sub-A test
    # baseline; set True in dev .env to enable Council reasoning + suggester
    # consumes Council verdict + Copilot prompt enriched with
    # copilot_feedback. Once Sub-G-3 eval suite confirms Council quality,
    # flip default True at Sub-E close-out + delete the regex fallback path
    # in _stage_suggester_decide.
    LITHRIM_PLAYGROUND_USE_COUNCIL: bool = False
    # CYCLE-16-D-v2 Sub-G-2 Risk-A track: gates whether stage 4 Copilot
    # generate prompt is enriched with Council copilot_feedback in the
    # description field. Default False because the in-line description
    # block caused the Copilot to copy expected_output verbatim instead
    # of generating a $switch (smoking-gun mapping 49+51 vs canonical
    # mapping 50; see scripts/phase4_pilot/c16d_council_smoke_2026-04-28
    # /SUB_G_2_KNOWN_REGRESSION.md). Sub-G-3 prompt eval suite tunes the
    # enrichment shape; flip this flag True once eval cases regression-
    # check clean.
    LITHRIM_PLAYGROUND_COUNCIL_ENRICH_COPILOT: bool = False
    # Mongo collection holding cached ValidationCouncilOutput per
    # (findings_hash, destination_id). Independent of the Sub-A copilot
    # cache; both layers cache independently.
    LITHRIM_PLAYGROUND_VALIDATION_COUNCIL_CACHE_COLLECTION: str = "validation_council_cache"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
