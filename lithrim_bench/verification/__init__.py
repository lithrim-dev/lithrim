"""WS-3 verification toolbox: uniform tool-grounded contracts behind one interface.

    tool.verify(claim, spec) -> VerificationResult(conforms, evidence, manifest)

with per-claim routing + verdict composition (the false-negative guardrail) in
`router`. Promoted into `main` from the `spike/verification-toolbox` prototype
(WS-3a); the KB/RAG/ONNX stack (`kb_rag`, `embeddings`) is deferred to WS-3b.
See `.devloop/state/STREAM_bench-salvage.md` (WS-3 row).
"""

from .argshape_gate import (
    FindingResult,
    GateFailure,
    GateReport,
    assert_gate_passes,
    gate_contract_over_corpus,
)
from .etlp_client import EtlpJuteClient
from .extraction_floors import FactPreservationTool, SpeakerAttributionTool
from .jute_argshape import (
    argshape_feedback_from,
    best_of_n_argshape,
    build_argshape_generator,
    make_argshape_metric,
    required_keys_of,
    score_argshape,
)
from .jute_dspy import (
    GOLDEN_US_CORE_PATIENT_VALIDATOR,
    US_CORE_PATIENT_RULES,
    best_of_n,
    build_generator,
    feedback_from,
    make_bench_metric,
    render_dsl_excerpt,
    score_template,
    strip_fences,
    verdict_for,
)
from .jute_extractor import (
    best_of_n_extractor,
    build_extractor_generator,
    extraction_feedback_from,
    make_extraction_metric,
    required_case_fields,
    score_extraction,
)
from .jute_gen import JuteGenValidatorTool
from .mcp_client import McpError, McpStdioClient
from .mutation import (
    field_mutants,
    generate_mutants,
    joint_coverage,
    mutants_to_cases,
    mutation_coverage,
    survivor_cases,
    valid_variation_cases,
    valid_variations,
)
from .router import CLEARED, CONFIRMED, UNRESOLVED, Router, compose_verdict
from .snomed_floor import SnomedSubsumptionFloorTool
from .spec import (
    RECORD_PRESENCE,
    REFERENCE_CONFORMANCE,
    STRUCTURAL_CONFORMANCE,
    TOOL_DOSAGE_GROUNDING,
    TOOL_IN_ROW,
    TOOL_JUTE_GEN,
    TOOL_KB_RAG,
    TOOL_RECORD_RAG,
    TOOL_STRUCTURAL_JUTE,
    TOOL_WEB_SEARCH,
    Claim,
    VerificationResult,
    VerificationSpec,
)
from .storyworld_client import StoryWorldAdminClient
from .tools import (
    FakeRecordRagTool,
    KbRagTool,
    RecordRagTool,
    StructuralJuteTool,
    ValuePresenceTool,
    VerificationTool,
    WebSearchTool,
)

# NOTE: the CLINICAL executors (the record-presence + dose-grounding tools) relocated into
# the active pack (packs/healthcare/floors.py, PACK-3); the core exports only generic tools.

__all__ = [
    "Claim",
    "VerificationResult",
    "VerificationSpec",
    "STRUCTURAL_CONFORMANCE",
    "RECORD_PRESENCE",
    "REFERENCE_CONFORMANCE",
    "TOOL_IN_ROW",
    "TOOL_STRUCTURAL_JUTE",
    "TOOL_RECORD_RAG",
    "TOOL_KB_RAG",
    "TOOL_JUTE_GEN",
    "TOOL_DOSAGE_GROUNDING",
    "TOOL_WEB_SEARCH",
    "VerificationTool",
    "StructuralJuteTool",
    "ValuePresenceTool",
    "FactPreservationTool",
    "SpeakerAttributionTool",
    "SnomedSubsumptionFloorTool",
    "KbRagTool",
    "WebSearchTool",
    "RecordRagTool",
    "FakeRecordRagTool",
    "JuteGenValidatorTool",
    "EtlpJuteClient",
    "StoryWorldAdminClient",
    "McpStdioClient",
    "McpError",
    "GOLDEN_US_CORE_PATIENT_VALIDATOR",
    "US_CORE_PATIENT_RULES",
    "score_template",
    "verdict_for",
    "make_bench_metric",
    "feedback_from",
    "render_dsl_excerpt",
    "strip_fences",
    "build_generator",
    "best_of_n",
    "score_extraction",
    "extraction_feedback_from",
    "make_extraction_metric",
    "build_extractor_generator",
    "best_of_n_extractor",
    "required_case_fields",
    "score_argshape",
    "argshape_feedback_from",
    "make_argshape_metric",
    "build_argshape_generator",
    "best_of_n_argshape",
    "required_keys_of",
    "mutation_coverage",
    "joint_coverage",
    "mutants_to_cases",
    "survivor_cases",
    "valid_variations",
    "valid_variation_cases",
    "generate_mutants",
    "field_mutants",
    "Router",
    "compose_verdict",
    "CLEARED",
    "CONFIRMED",
    "UNRESOLVED",
    "GateReport",
    "FindingResult",
    "GateFailure",
    "gate_contract_over_corpus",
    "assert_gate_passes",
]
