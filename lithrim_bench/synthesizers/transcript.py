"""Deterministic, template-based transcript synthesis for the scribe pack.

v2 (2026-05-21): every artifact section is now explicitly textually
grounded in the transcript — PMH conditions, all active medications
with doses, all allergies, and all observation values. The 2026-05-21
live-pipeline smoke against the gpt-4.1 council showed that the v1
transcript (which mentioned only the primary medication and the first
allergy) caused systematic FABRICATED_HISTORY +
MEDICATION_NOT_IN_TRANSCRIPT + HALLUCINATED_DETAIL false-positives on
clean cases. The fix is purely transcript-side: lengthen the dialogue
so every artifact assertion has a verbatim source span.

v1 is template-only on purpose: the benchmark must be byte-deterministic
given the same EncounterSpec, with no LLM API dependency. An LLM-backed
synthesizer can be added in phase 2 behind the same interface, but the
deterministic path stays as the reproducibility baseline for the paper.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec, Observation
from ._pmh import clinical_conditions

_LAB_INTEREST = {
    "4548-4": "HbA1c",
    "2093-3": "cholesterol",
    "2339-0": "glucose",
}
_VITAL_INTEREST = {
    "8480-6": "systolic blood pressure",
    "8462-4": "diastolic blood pressure",
    "8867-4": "heart rate",
}


def _format_obs(obs: Observation, label: str) -> str:
    val = obs.value
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    unit = f" {obs.unit}" if obs.unit else ""
    return f"{label} {val}{unit}".strip()


def _enumerate(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def synthesize_scribe_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    reason = spec.encounter.reason_description or "follow-up"
    lines: list[str] = [
        f"Dr: Good morning {demo.first_name}, what brings you in today?",
        f"Patient: I'm here for {reason.lower()}.",
    ]

    pmh = clinical_conditions(spec.conditions)
    if pmh:
        cond_list = _enumerate([c.description for c in pmh])
        lines.append(f"Dr: Let me confirm your medical history. You have {cond_list}. That's correct?")
        lines.append("Patient: Yes, that's right.")
    else:
        lines.append("Dr: Your record shows no significant past medical history. Confirm?")
        lines.append("Patient: Right, nothing significant.")

    if spec.active_medications:
        med_phrases = [f"{m.description} at {m.dose} daily" for m in spec.active_medications]
        med_list = _enumerate(med_phrases)
        lines.append(f"Dr: And you're currently taking {med_list}.")
        lines.append("Patient: Correct, I take all of those every day as prescribed.")

    if spec.allergies:
        allergy_list = _enumerate([a.description.lower() for a in spec.allergies])
        lines.append(f"Dr: Your documented allergies are {allergy_list}. Still accurate?")
        lines.append("Patient: Yes, those are all current.")
    else:
        lines.append("Dr: No documented allergies on file. Still NKA?")
        lines.append("Patient: Right, no known allergies.")

    labs = [o for o in spec.observations if o.loinc_code in _LAB_INTEREST]
    vitals = [o for o in spec.observations if o.loinc_code in _VITAL_INTEREST]
    if labs:
        lab_phrases = [_format_obs(o, o.description + ":") for o in labs]
        lines.append(f"Dr: Recent labs: {_enumerate(lab_phrases)}.")
        lines.append("Patient: Got it.")
    if vitals:
        vital_phrases = [_format_obs(o, o.description + ":") for o in vitals]
        lines.append(f"Dr: Your vitals today: {_enumerate(vital_phrases)}.")

    lines.append("Dr: Continue your current regimen. Follow up in one month.")
    lines.append("Patient: Sounds good, thanks.")
    return "\n".join(lines)
