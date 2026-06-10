"""Deterministic HL7-pack transcript synthesis.

A patient-registration intake dialogue.

v2 (2026-05-22): the transcript now grounds *every* ADT^A04 field the
artifact carries — name, DOB, gender, home address, insurance plan,
attending provider, and the assigned outpatient ward. v1 spoke only
name/DOB/gender, leaving address / provider / ward / insurance
ungrounded; an agent could fabricate those four and no semantic judge
could catch it because the transcript never mentioned them. Grounding
them makes a fabricated field a detectable semantic defect.

The registration constants (address, attending, ward, insurance) are
imported from hl7_adt_artifact so the transcript and the emitted ADT
message stay byte-consistent.

The HL7 pack still primarily tests *structural* validation — the five
HL7 injectors all mutate the message text — but the transcript is now
a complete, self-contained registration record rather than a stub.
"""
from __future__ import annotations

from lithrim_bench.encounter_spec import EncounterSpec

from .hl7_adt_artifact import ATTENDING, INSURANCE, PATIENT_CLASS_LABEL, REG_ADDRESS, WARD


def synthesize_hl7_adt_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    dob = demo.dob.strftime("%B %-d, %Y")
    full_name = f"{demo.first_name} {demo.last_name}"
    address = (
        f"{REG_ADDRESS['street']}, {REG_ADDRESS['city']}, "
        f"{REG_ADDRESS['state']} {REG_ADDRESS['zip']}"
    )
    doctor = f"Dr. {ATTENDING['given']} {ATTENDING['family']}"
    ward = f"{WARD['point_of_care']}, room {WARD['room']}, bed {WARD['bed']}"

    lines = [
        f"Registrar: Good morning, {demo.first_name}. Let's get you registered "
        "as an outpatient. I'll confirm a few details for the EHR record.",
        f"Patient: Sure. {full_name}, date of birth {dob}.",
        f"Registrar: Thank you. Confirmed: {full_name}, DOB {dob}, gender "
        f"{demo.gender}.",
        f"Patient: My home address is {address}.",
        f"Registrar: Got it — {address}. And your insurance?",
        f"Patient: It's {INSURANCE['plan_name']}, plan code {INSURANCE['plan_code']}.",
        f"Registrar: Recorded: {INSURANCE['plan_name']} ({INSURANCE['plan_code']}). "
        f"Your attending physician for this visit is {doctor}.",
        f"Registrar: I'm assigning you to {ward} for this {PATIENT_CLASS_LABEL} visit.",
        "Registrar: I'll send your registration to the EHR now.",
        "Patient: Thanks.",
    ]
    return "\n".join(lines)
