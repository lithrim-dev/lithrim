"""Deterministic HL7-pack transcript synthesis.

A patient-registration intake dialogue. The transcript is short and
intentionally clinically uninteresting — the HL7 pack tests structural
validation, not semantic content. A semantic judge reading this
transcript and the message will see nothing wrong even when the HL7
message is structurally malformed; that is exactly the categorical
blindness the paper claims about.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec


def synthesize_hl7_adt_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    dob = demo.dob.strftime("%B %-d, %Y")
    lines = [
        f"Registrar: Good morning, {demo.first_name}. Let's get you registered.",
        f"Patient: {demo.first_name} {demo.last_name}, date of birth {dob}.",
        f"Registrar: Confirmed: {demo.first_name} {demo.last_name}, DOB {dob}, "
        f"gender {demo.gender}.",
        "Registrar: I'll send your registration to the EHR now.",
        "Patient: Thanks.",
    ]
    return "\n".join(lines)
