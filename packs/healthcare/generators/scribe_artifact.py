"""Deterministic scribe artifact synthesis (SOAP note + DocumentReference).

Matches the artifact shape used by lithrim-backend's existing eval_golden.jsonl
scribe cases (FHIR DocumentReference with an embedded text/plain SOAP body).

The SOAP body has named sections (SUBJECTIVE, OBJECTIVE, ALLERGIES, PMH,
ASSESSMENT, PLAN). Section names are stable anchors that text-projection
injectors locate against; do not rename them without updating the
injectors.
"""
from __future__ import annotations

import json
from typing import Any

from lithrim_bench.encounter_spec import EncounterSpec, Observation
from lithrim_bench.synthesizers._pmh import clinical_conditions

_LAB_INTEREST = {
    "4548-4",   # HbA1c
    "2093-3",   # Cholesterol
    "2571-8",   # Triglycerides
    "2085-9",   # HDL
    "13457-7",  # LDL
    "2339-0",   # Glucose
}
_VITAL_INTEREST = {
    "8480-6",   # Systolic BP
    "8462-4",   # Diastolic BP
    "8867-4",   # Heart rate
    "29463-7",  # Body weight
}


def _format_obs(obs: Observation) -> str:
    val = obs.value
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    unit = f" {obs.unit}" if obs.unit else ""
    return f"{obs.description}: {val}{unit}"


def _objective_lines(spec: EncounterSpec) -> list[str]:
    vitals = [o for o in spec.observations if o.loinc_code in _VITAL_INTEREST]
    labs = [o for o in spec.observations if o.loinc_code in _LAB_INTEREST]
    lines: list[str] = []
    if vitals:
        lines.append("Vitals: " + "; ".join(_format_obs(o) for o in vitals))
    else:
        lines.append("Vitals: stable.")
    if labs:
        lines.append("Labs:")
        for o in labs:
            lines.append(f"  - {_format_obs(o)}")
    return lines


def _allergies_section(spec: EncounterSpec) -> list[str]:
    if not spec.allergies:
        return ["NKDA (no known drug allergies)."]
    return [f"- {a.description}" for a in spec.allergies]


def _pmh_section(spec: EncounterSpec) -> list[str]:
    pmh = clinical_conditions(spec.conditions)
    if not pmh:
        return ["No significant past medical history."]
    return [f"- {c.description}" for c in pmh]


def _format_soap_text(spec: EncounterSpec) -> str:
    demo = spec.demographics
    primary_med = spec.primary_active_medication()
    reason = spec.encounter.reason_description or "follow-up"

    plan_lines: list[str] = []
    if primary_med:
        plan_lines.append(f"1. Continue {primary_med.description} {primary_med.dose} daily")
    plan_lines.append(f"{len(plan_lines) + 1}. Follow-up in 1 month")

    parts: list[str] = [
        f"SUBJECTIVE: {demo.age_at_encounter}{demo.gender} presents for {reason.lower()}.",
        "",
        "OBJECTIVE:",
    ]
    parts.extend(f"  {line}" for line in _objective_lines(spec))
    parts.extend(["", "ALLERGIES:"])
    parts.extend(f"  {line}" for line in _allergies_section(spec))
    parts.extend(["", "PMH:"])
    parts.extend(f"  {line}" for line in _pmh_section(spec))
    parts.extend([
        "",
        f"ASSESSMENT: {reason}.",
        "",
        "PLAN:",
    ])
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
