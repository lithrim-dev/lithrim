"""Deterministic triage artifact synthesis (FHIR RiskAssessment).

Matches the artifact shape used by lithrim-backend's existing triage
eval cases: a RiskAssessment with `prediction[]` (outcome +
qualitativeRisk) and a `mitigation` field carrying the agent's
disposition recommendation.
"""
from __future__ import annotations

import json
from typing import Any

from ..encounter_spec import EncounterSpec
from ._triage_scenarios import pick_scenario


def synthesize_triage_artifact(spec: EncounterSpec) -> list[dict[str, Any]]:
    demo = spec.demographics
    scenario = pick_scenario(demo.patient_id)
    risk_assessment = {
        "resourceType": "RiskAssessment",
        "status": "final",
        "subject": {"reference": f"Patient/{demo.patient_id}"},
        "occurrenceDateTime": spec.encounter.start.isoformat(),
        "prediction": [
            {
                "outcome": {"text": scenario.risk_outcome},
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
