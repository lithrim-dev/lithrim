"""Deterministic coding artifact synthesis.

Matches the artifact shape used by lithrim-backend's existing coding
eval cases (fhir_claim with embedded ICD-10 diagnosis and CPT procedure
codes).

CPT defaults to 99213 (established-patient office visit, level 3) —
the visit-level upcoding target sits one tier higher at 99215.

v3 (2026-05-21): emits `provider.reference` and `insurance[0].coverage.reference`
to satisfy the CARIN Claim Validator (etlp mapping 15) checks
`has_provider` and `has_insurance`. v2 omitted both, which caused the
live structural stage to return WARN on every clean case and the
worst-of composition rule (semantic=approve ∧ structural=WARN →
needs_review) flipped all 4/4 cleans away from approve. `total` and
`provider.identifier` (NPI) are included as transcript anchors; they
are not enforced by mapping 15 but produce a coherent billing
narrative the council can ground against.
"""
from __future__ import annotations

import json
from typing import Any

from ..encounter_spec import EncounterSpec
from ._icd10_map import lookup

PROVIDER_ID = "lithrim-clinic-001"
PROVIDER_NPI = "1234567890"
COVERAGE_ID = "medicare-part-b-coverage"
PAYER_DISPLAY = "Medicare Part B"
VISIT_CHARGE_USD = 148.00


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
        "provider": {
            "reference": f"Organization/{PROVIDER_ID}",
            "identifier": {
                "system": "http://hl7.org/fhir/sid/us-npi",
                "value": PROVIDER_NPI,
            },
        },
        "insurance": [
            {
                "sequence": 1,
                "focal": True,
                "coverage": {
                    "reference": f"Coverage/{COVERAGE_ID}",
                    "display": PAYER_DISPLAY,
                },
            }
        ],
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
                "unitPrice": {"value": VISIT_CHARGE_USD, "currency": "USD"},
                "net": {"value": VISIT_CHARGE_USD, "currency": "USD"},
            }
        ],
        "total": {"value": VISIT_CHARGE_USD, "currency": "USD"},
    }
    return [
        {
            "type": "fhir_claim",
            "content": json.dumps(claim),
            "target_system": "EHR",
        }
    ]
