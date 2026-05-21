"""Deterministic scribe artifact synthesis (SOAP note + DocumentReference).

Matches the artifact shape used by lithrim-backend's existing eval_golden.jsonl
scribe cases (FHIR DocumentReference with an embedded text/plain SOAP body).
"""
from __future__ import annotations

import json
from typing import Any

from ..encounter_spec import EncounterSpec


def _format_soap_text(spec: EncounterSpec) -> str:
    demo = spec.demographics
    primary_med = spec.primary_active_medication()
    reason = spec.encounter.reason_description or "follow-up"

    plan_lines: list[str] = []
    if primary_med:
        plan_lines.append(f"1. Continue {primary_med.description} {primary_med.dose} daily")
    plan_lines.append(f"{len(plan_lines) + 1}. Follow-up in 1 month")

    parts = [
        f"SUBJECTIVE: {demo.age_at_encounter}{demo.gender} presents for {reason.lower()}.",
        "",
        "OBJECTIVE: Vital signs stable.",
        "",
        f"ASSESSMENT: {reason}.",
        "",
        "PLAN:",
    ]
    parts.extend(plan_lines)
    return "\n".join(parts)


def synthesize_scribe_artifact(spec: EncounterSpec) -> dict[str, Any]:
    """Return a FHIR DocumentReference artifact, matching backend eval_golden shape."""
    demo = spec.demographics
    soap_text = _format_soap_text(spec)
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
