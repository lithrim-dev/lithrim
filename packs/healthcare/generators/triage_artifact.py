"""Deterministic triage artifact synthesis (FHIR RiskAssessment).

Matches the artifact shape used by lithrim-backend's existing triage
eval cases: a RiskAssessment with `prediction[]` (outcome +
qualitativeRisk) and a `mitigation` field carrying the agent's
disposition recommendation.

v3 (2026-05-21): emits `code.coding[0]` (SNOMED-CT system) and
`prediction[0].probabilityDecimal`. v2 omitted both, which caused the
FHIR R4 RiskAssessment Validator (etlp mapping 19) checks
`has-condition-code` and `valid-probability` to fail-closed on every
clean case; the structural stage returned WARN and worst-of
composition flipped all 4/4 cleans to needs_review.
HIGH_RISK_PROBABILITY mirrors the "85%" anchor the transcript now
carries, giving the council a textual ground-truth to validate
against the artifact's numeric value.
"""
from __future__ import annotations

import json
from typing import Any

from lithrim_bench.encounter_spec import EncounterSpec

from ._triage_scenarios import pick_scenario

ASSESSMENT_SNOMED_CODE = "709510001"
ASSESSMENT_SNOMED_DISPLAY = "Assessment of risk factors"
HIGH_RISK_PROBABILITY = 0.85


def synthesize_triage_artifact(spec: EncounterSpec) -> list[dict[str, Any]]:
    demo = spec.demographics
    scenario = pick_scenario(demo.patient_id)
    risk_assessment = {
        "resourceType": "RiskAssessment",
        "status": "final",
        "subject": {"reference": f"Patient/{demo.patient_id}"},
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": ASSESSMENT_SNOMED_CODE,
                    "display": ASSESSMENT_SNOMED_DISPLAY,
                }
            ]
        },
        "occurrenceDateTime": spec.encounter.start.isoformat(),
        "prediction": [
            {
                "outcome": {"text": scenario.risk_outcome},
                "probabilityDecimal": HIGH_RISK_PROBABILITY,
                "qualitativeRisk": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/risk-probability",
                            "code": scenario.warranted_risk,
                            "display": scenario.warranted_risk.capitalize() + " risk",
                        }
                    ]
                },
            }
        ],
        "mitigation": (
            f"Refer to {scenario.warranted_disposition} immediately. "
            f"Red flags present: {', '.join(scenario.red_flags)}. "
            "Do not attempt self-care or routine scheduling."
        ),
    }
    return [
        {
            "type": "fhir_risk_assessment",
            "content": json.dumps(risk_assessment),
            "target_system": "EHR",
        }
    ]
