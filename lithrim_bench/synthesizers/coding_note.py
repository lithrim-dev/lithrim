"""Deterministic coding-encounter clinical note (FHIR DocumentReference).

The coder codes *from* a clinical note. v2 of the coding pack shipped
only the FHIR Claim with no documentation of record, which made clean
cases circular (the old "dictation" transcript pre-stated the codes)
and made the upcode defect a contradiction-with-dictation rather than
a genuine unsupported-code defect.

v3: every coding case carries this SOAP note as the documentation of
record. The note's ASSESSMENT names the base diagnosis only; it never
contains the `upcode_requires_evidence` clinical phrase, so an upcoded
ICD on the Claim is unsupported by the documentation by construction.
The PLAN/visit-complexity wording grounds CPT 99213 (established
patient, low-to-moderate complexity) without dictating the code.

SOAP section names (SUBJECTIVE / OBJECTIVE / ASSESSMENT / PLAN) are
stable anchors; do not rename without updating any text-projection
injector that targets them.
"""
from __future__ import annotations

import json
from typing import Any

from ..encounter_spec import EncounterSpec
from ._coding_dx import resolve_primary_dx


def _soap_text(spec: EncounterSpec) -> str:
    demo = spec.demographics
    dx = resolve_primary_dx(spec)

    if dx.is_routine_exam:
        subjective = (
            f"{demo.age_at_encounter}{demo.gender} presents for a routine "
            "established-patient health examination. No new complaints."
        )
        assessment = f"{dx.icd_description}. No abnormal findings on today's visit."
    else:
        subjective = (
            f"{demo.age_at_encounter}{demo.gender} presents for established-patient "
            f"follow-up of {dx.icd_description.lower()}."
        )
        assessment = (
            f"{dx.icd_description}. Stable on current management; "
            "no complications or acute decompensation documented this visit."
        )

    parts = [
        f"SUBJECTIVE: {subjective}",
        "",
        "OBJECTIVE:",
        "  Vitals: stable. Examination unremarkable for an interval follow-up.",
        "",
        f"ASSESSMENT: {assessment}",
        "",
        "PLAN:",
        "1. Established-patient office visit, low-to-moderate complexity "
        "(history, examination, and discussion of management).",
        "2. Continue current management; routine follow-up in 1 month.",
    ]
    return "\n".join(parts)


def synthesize_coding_note(spec: EncounterSpec) -> dict[str, Any]:
    """FHIR DocumentReference carrying the coding-encounter SOAP note."""
    demo = spec.demographics
    soap_text = _soap_text(spec)
    doc_ref = {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note",
                }
            ]
        },
        "subject": {"reference": f"patient/{demo.patient_id}"},
        "date": spec.encounter.start.isoformat(),
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": soap_text,
                    "title": "Progress Note",
                }
            }
        ],
    }
    return {
        "type": "fhir_document_reference",
        "content": json.dumps(doc_ref),
        "target_system": "EHR",
        "_soap_text": soap_text,
    }
