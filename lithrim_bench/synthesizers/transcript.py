"""Deterministic, template-based transcript synthesis.

v1 is template-only on purpose: the benchmark must be byte-deterministic
given the same EncounterSpec, with no LLM API dependency. An LLM-backed
synthesizer can be added in phase 2 behind the same interface, but the
deterministic path stays as the reproducibility baseline for the paper.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec


def synthesize_scribe_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    primary_med = spec.primary_active_medication()
    reason = spec.encounter.reason_description or "follow-up"

    lines: list[str] = []
    lines.append(
        f"Dr: Hello {demo.first_name}, what brings you in today?"
    )
    lines.append(
        f"Patient: I'm here for {reason.lower()}."
    )
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
