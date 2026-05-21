"""Deterministic scheduling artifact synthesis.

Matches the artifact shape used by lithrim-backend's existing scheduling
eval cases (fhir_appointment + scheduling_confirmation).
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from ..encounter_spec import EncounterSpec


def _slot_window(spec: EncounterSpec) -> tuple[str, str]:
    start = spec.encounter.start
    end = start + timedelta(minutes=30)
    return start.isoformat(), end.isoformat()


def synthesize_scheduling_artifact(spec: EncounterSpec) -> list[dict[str, Any]]:
    demo = spec.demographics
    start_iso, end_iso = _slot_window(spec)
    appointment = {
        "resourceType": "Appointment",
        "status": "booked",
        "serviceType": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/service-type",
                        "code": "124",
                        "display": "general",
                    }
                ]
            }
        ],
        "start": start_iso,
        "end": end_iso,
        "participant": [
            {
                "actor": {
                    "reference": f"Patient/{demo.patient_id}",
                    "display": f"{demo.first_name} {demo.last_name}",
                },
                "required": "required",
                "status": "accepted",
            }
        ],
    }
    confirmation = {
        "patient_name": f"{demo.first_name} {demo.last_name}",
        "date": spec.encounter.start.date().isoformat(),
        "time": spec.encounter.start.strftime("%H:%M"),
        "provider": "Dr. Patel",
        "appointment_id": f"APT-{demo.patient_id[:8]}",
    }
    return [
        {
            "type": "fhir_appointment",
            "content": json.dumps(appointment),
            "target_system": "EHR",
        },
        {
            "type": "scheduling_confirmation",
            "content": json.dumps(confirmation),
            "target_system": "EHR",
        },
    ]
