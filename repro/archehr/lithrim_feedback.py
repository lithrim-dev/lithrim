"""Bounded, offline reuse of the shipped tool; not an evidence-alignment oracle."""

from dataclasses import asdict

from lithrim_bench.verification.spec import Claim, VerificationSpec
from lithrim_bench.verification.tools import ValueGroundingTool

LIMIT = (
    "Numeric membership only: matching values do not establish entity, time, negation, "
    "causality or semantic support. Missing prose values are review leads, not violations."
)


def review_values(answer_text: str, cited_source_text: str) -> dict:
    claim = Claim(
        claim_type="reference_conformance",
        flag_code=None,
        subject=answer_text,
        locus="supplied_answer_sentence",
        source={"transcript": cited_source_text, "source_kind": "prose"},
    )
    spec = VerificationSpec(
        tool="value_grounding",
        applies_to_flags=(),
        locus=claim.locus,
        reference={"source_path": "transcript", "on_missing": "lead", "min_digits": 1},
        version="archehr-value-diagnostic/1",
    )
    return {
        "value_membership": asdict(ValueGroundingTool().verify(claim, spec)),
        "semantic_support": None,
        "limitation": LIMIT,
    }


def build_review_case(
    case_id: str,
    answer_id: str,
    answer_text: str,
    cited_source_text: str,
) -> dict:
    return {
        "case_id": f"archehr-{case_id}-answer-{answer_id}",
        "source_kind": "prose",
        "transcript": cited_source_text,
        "context": {"task": "Assess support using ONLY the proposed cited source text."},
        "artifacts": [{"kind": "generated_response", "content": answer_text}],
        "provenance": {
            "benchmark_case_id": case_id,
            "answer_id": answer_id,
            "label_status": "unlabeled_external_prediction",
        },
    }
