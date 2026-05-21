"""Deterministic coding artifact synthesis.

Matches the artifact shape used by lithrim-backend's existing coding
eval cases (fhir_claim with embedded ICD-10 diagnosis and CPT procedure
codes).

CPT defaults to 99213 (established-patient office visit, level 3) —
the visit-level upcoding target sits one tier higher at 99215.
"""
from __future__ import annotations

import json
from typing import Any

from ..encounter_spec import EncounterSpec
from ._icd10_map import lookup


def synthesize_coding_artifact(spec: EncounterSpec) -> list[dict[str, Any]]:
    demo = spec.demographics
    primary_icd: str | None = None
    primary_desc: str | None = None
    for cond in spec.conditions:
        mapping = lookup(cond.snomed_code)
        if mapping is not None:
            primary_icd = mapping.icd10_base
            primary_desc = mapping.description
            break
    if primary_icd is None:
        primary_icd = "Z00.00"
        primary_desc = "Encounter for general adult medical examination without abnormal findings"

    claim = {
        "resourceType": "Claim",
        "status": "active",
        "type": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type",
                        "code": "professional"}]
        },
        "use": "claim",
        "patient": {"reference": f"Patient/{demo.patient_id}"},
        "billablePeriod": {
            "start": spec.encounter.start.date().isoformat(),
            "end": spec.encounter.start.date().isoformat(),
        },
        "diagnosis": [
            {
                "sequence": 1,
                "diagnosisCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/sid/icd-10-cm",
                            "code": primary_icd,
                            "display": primary_desc,
                        }
                    ]
                },
            }
        ],
        "item": [
            {
                "sequence": 1,
                "productOrService": {
                    "coding": [
                        {
                            "system": "http://www.ama-assn.org/go/cpt",
                            "code": "99213",
                            "display": "Office or other outpatient visit, established patient, level 3",
                        }
                    ]
                },
                "servicedDate": spec.encounter.start.date().isoformat(),
            }
        ],
    }
    return [
        {
            "type": "fhir_claim",
            "content": json.dumps(claim),
            "target_system": "EHR",
        }
    ]
