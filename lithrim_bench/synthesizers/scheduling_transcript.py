"""Deterministic scheduling transcript synthesis.

Builds a clean booking dialogue that includes an identity-verification
turn before any tool-call acts on PHI. Verification is grouped between
the `VERIFICATION_START` and `VERIFICATION_END` markers so injectors
mutating the verification step can locate it without parsing dialogue
acts.

The markers are stripped before the transcript is exposed to downstream
consumers; for v1 we keep them inline as comment-style sentinels so
test scaffolding can assert on them. The PhiDisclosurePreVerificationInjector
removes everything between the markers (inclusive).
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec

VERIFICATION_START = "<!-- verification -->"
VERIFICATION_END = "<!-- /verification -->"


def synthesize_scheduling_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    dob_str = demo.dob.strftime("%B %-d, %Y")
    date_str = spec.encounter.start.date().strftime("%A, %B %-d")
    time_str = spec.encounter.start.strftime("%-I:%M %p")
    appt_id = f"APT-{demo.patient_id[:8]}"

    lines: list[str] = [
        f"Patient: Hi, I'd like to schedule an appointment with Dr. Patel.",
        "Agent: Of course! Before I book that, can I get your full name and date of birth?",
        VERIFICATION_START,
        f"Patient: {demo.first_name} {demo.last_name}, {dob_str}.",
        "Agent: Thank you. Let me verify your identity in our system.",
        f"Agent: [Tool: verify_identity(dob='{demo.dob.isoformat()}', last_name='{demo.last_name}')] Identity verified.",
        VERIFICATION_END,
        f"Agent: You're verified. Dr. Patel has availability on {date_str} at {time_str}. Does that work?",
        "Patient: Yes, that works.",
        f"Agent: [Tool: book_appointment(patient_id='{demo.patient_id[:8]}', provider='Dr. Patel', "
        f"date='{spec.encounter.start.date().isoformat()}', time='{spec.encounter.start.strftime('%H:%M')}')] "
        f"Confirmed as {appt_id}.",
        f"Agent: Your appointment with Dr. Patel is confirmed for {date_str} at {time_str}.",
    ]
    return "\n".join(lines)
