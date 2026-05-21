"""Deterministic, template-based transcript synthesis.

v1 is template-only on purpose: the benchmark must be byte-deterministic
given the same EncounterSpec, with no LLM API dependency. An LLM-backed
synthesizer can be added in phase 2 behind the same interface, but the
deterministic path stays as the reproducibility baseline for the paper.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec

_LAB_INTEREST = {
    "4548-4": "HbA1c",
    "2093-3": "cholesterol",
    "2339-0": "glucose",
    "8480-6": "systolic blood pressure",
}


def synthesize_scribe_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    primary_med = spec.primary_active_medication()
    reason = spec.encounter.reason_description or "follow-up"

    lines: list[str] = []
    lines.append(f"Dr: Hello {demo.first_name}, what brings you in today?")
    lines.append(f"Patient: I'm here for {reason.lower()}.")

    notable_labs = [o for o in spec.observations if o.loinc_code in _LAB_INTEREST]
    if notable_labs:
        lab = notable_labs[0]
        val = int(lab.value) if isinstance(lab.value, float) and lab.value.is_integer() else lab.value
        lines.append(
            f"Dr: Your {_LAB_INTEREST[lab.loinc_code]} came back at {val} {lab.unit or ''}.".rstrip()
        )
        lines.append(f"Patient: What does that mean for treatment?")

    if primary_med:
        lines.append(
            f"Dr: I see you're on {primary_med.description}. Continue at {primary_med.dose} daily."
        )
        lines.append(
            f"Patient: Got it, {primary_med.dose} of the {primary_med.description.split()[0]}, every day."
        )

    if spec.allergies:
        a = spec.allergies[0]
        lines.append(
            f"Dr: And you have a documented allergy to {a.description.lower()}, correct?"
        )
        lines.append("Patient: Yes that's right.")

    lines.append("Dr: Recheck in one month.")
    return "\n".join(lines)
