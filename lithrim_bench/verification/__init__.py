"""WS-3 verification toolbox: uniform tool-grounded contracts behind one interface.

    tool.verify(claim, spec) -> VerificationResult(conforms, evidence, manifest)

with per-claim routing + verdict composition (the false-negative guardrail) in
`router`. Promoted into `main` from the `spike/verification-toolbox` prototype
(WS-3a); the KB/RAG/ONNX stack (`kb_rag`, `embeddings`) is deferred to WS-3b.
See `.devloop/state/STREAM_bench-salvage.md` (WS-3 row).
"""

from .etlp_client import EtlpJuteClient
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
from .jute_gen import JuteGenValidatorTool
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
    Claim,
    VerificationResult,
    VerificationSpec,
)
from .tools import (
    DosageGroundingTool,
    FakeRecordRagTool,
    InRowTool,
    RecordRagTool,
    StructuralJuteTool,
    VerificationTool,
)

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
    "VerificationTool",
    "InRowTool",
    "StructuralJuteTool",
    "DosageGroundingTool",
    "RecordRagTool",
    "FakeRecordRagTool",
    "JuteGenValidatorTool",
    "EtlpJuteClient",
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
]
