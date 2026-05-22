"""Deterministic coding artifact synthesis (FHIR Claim + clinical note).

A coding case carries two artifacts:
  [0] fhir_claim             — the coding agent's output, the thing under test
  [1] fhir_document_reference — the clinical note, the documentation of record

v2 shipped only the Claim, with a "coding dictation" transcript that
pre-stated the codes. That made clean cases circular and the upcode
defect a contradiction-with-dictation. v3 adds the clinical note
(coding_note.py) and a genuine clinical-encounter transcript
(coding_transcript.py); the Claim's codes are now verified against
real documentation.

CPT defaults to 99213 (established-patient office visit, level 3) —
the visit-level upcoding target sits one tier higher at 99215.

The Claim carries `provider.reference` and `insurance[0].coverage.reference`
to satisfy the CARIN Claim Validator (etlp mapping 15) checks
`has_provider` and `has_insurance`.

Primary diagnosis is resolved by `_coding_dx.resolve_primary_dx`,
which fixes the age-blind ICD fallback: a routine exam on a minor is
coded Z00.129 (child health exam), not Z00.00 (adult exam).
"""
from __future__ import annotations

import json
from typing import Any

from ..encounter_spec import EncounterSpec
from ._coding_dx import resolve_primary_dx
from .coding_note import synthesize_coding_note

PROVIDER_ID = "lithrim-clinic-001"
PROVIDER_NPI = "1234567890"
COVERAGE_ID = "medicare-part-b-coverage"
PAYER_DISPLAY = "Medicare Part B"
VISIT_CHARGE_USD = 148.00


def _synthesize_claim(spec: EncounterSpec) -> dict[str, Any]:
    demo = spec.demographics
    dx = resolve_primary_dx(spec)
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
                            "code": dx.icd_code,
                            "display": dx.icd_description,
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
    return {
        "type": "fhir_claim",
        "content": json.dumps(claim),
        "target_system": "EHR",
    }


def synthesize_coding_artifact(spec: EncounterSpec) -> list[dict[str, Any]]:
    """Return [claim, clinical_note].

    The Claim is artifact[0] (the agent output under test); the
    DocumentReference note is artifact[1] (documentation of record).
    """
    return [
        _synthesize_claim(spec),
        synthesize_coding_note(spec),
    ]
