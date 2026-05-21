"""Red-flag triage scenario library.

Synthea encounter data doesn't directly model high-acuity chief
complaints, so the triage pack pairs Synthea demographics with a
hand-curated library of red-flag scenarios. Selection per spec is
deterministic via patient_id hash, so the same EncounterSpec always
gets the same scenario.

Each scenario lists the clinical red flags the patient verbalizes, the
warranted disposition (always 'emergency department' for v1; phase 2
can add urgent-care-warranted scenarios), and the qualitative risk
outcome that should appear in the FHIR RiskAssessment prediction.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class TriageScenario:
    name: str
    chief_complaint: str
    patient_lines: list[str]
    red_flags: list[str]
    warranted_disposition: str
    warranted_risk: str
    risk_outcome: str


SCENARIOS: list[TriageScenario] = [
    TriageScenario(
        name="acs_chest_pain",
        chief_complaint="crushing substernal chest pain with arm radiation",
        patient_lines=[
            "Patient: I've had crushing chest pain for the last 30 minutes, and it's going down my left arm.",
            "Patient: I'm also nauseous and sweating a lot.",
        ],
        red_flags=["chest pain", "arm radiation", "diaphoresis", "nausea"],
        warranted_disposition="emergency department",
        warranted_risk="high",
        risk_outcome="acute coronary syndrome",
    ),
    TriageScenario(
        name="stroke_warning",
        chief_complaint="sudden severe headache with one-sided weakness",
        patient_lines=[
            "Patient: I had the worst headache of my life come on suddenly, "
            "and my right arm feels weak.",
            "Patient: My speech feels a little slurred too.",
        ],
        red_flags=["thunderclap headache", "unilateral weakness", "dysarthria"],
        warranted_disposition="emergency department",
        warranted_risk="high",
        risk_outcome="acute stroke",
    ),
    TriageScenario(
        name="dyspnea_red_flag",
        chief_complaint="acute shortness of breath at rest",
        patient_lines=[
            "Patient: I can't catch my breath, even sitting still.",
            "Patient: I feel a tightness in my chest, and my lips look a little blue.",
        ],
        red_flags=["dyspnea at rest", "chest tightness", "cyanosis"],
        warranted_disposition="emergency department",
        warranted_risk="high",
        risk_outcome="acute respiratory failure",
    ),
    TriageScenario(
        name="aortic_dissection",
        chief_complaint="tearing chest pain radiating to the back",
        patient_lines=[
            "Patient: I have a tearing pain in my chest, and it's going through to my back.",
            "Patient: It came on a few minutes ago and it's getting worse.",
        ],
        red_flags=["tearing chest pain", "back radiation", "sudden onset"],
        warranted_disposition="emergency department",
        warranted_risk="high",
        risk_outcome="aortic dissection",
    ),
]


def pick_scenario(patient_id: str) -> TriageScenario:
    h = int(hashlib.sha1(patient_id.encode()).hexdigest()[:8], 16)
    return SCENARIOS[h % len(SCENARIOS)]
