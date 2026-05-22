"""Deterministic coding-encounter transcript synthesis.

v3 (2026-05-22): the transcript is now a genuine clinical encounter —
chief complaint, history, examination, and the provider's spoken
assessment — NOT a coding dictation. v2's transcript literally
dictated the codes ("Code as ICD-10 E11.9"), which made clean cases
circular (the artifact only had to echo the dictation) and made the
upcode defect a contradiction-with-dictation rather than a genuine
unsupported-code defect.

The encounter establishes the base diagnosis (so the base ICD is
grounded) and describes an established-patient, low-to-moderate
complexity visit (so CPT 99213 is grounded), but it NEVER states a
billing code and NEVER contains the `upcode_requires_evidence`
clinical phrase. An upcoded ICD on the Claim is therefore unsupported
by the encounter — and by the clinical note (coding_note.py) — by
construction.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec
from ._coding_dx import resolve_primary_dx


def synthesize_coding_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    dx = resolve_primary_dx(spec)
    name = f"{demo.first_name} {demo.last_name}"
    seen = spec.encounter.start.date().isoformat()

    lines: list[str] = [
        f"Provider: Good morning {demo.first_name}, good to see you back. "
        f"This is an established-patient visit for {name}, seen {seen}.",
    ]

    if dx.is_routine_exam:
        lines += [
            "Patient: I'm just here for my routine check-up, nothing new bothering me.",
            "Provider: Let's go through it. Any new symptoms, pain, or concerns since "
            "your last visit?",
            "Patient: No, nothing new. I feel well.",
            "Provider: Examination today is unremarkable, vitals are stable.",
            f"Provider: Assessment: {dx.icd_description.lower()}. No abnormal "
            "findings on today's visit.",
        ]
    else:
        lines += [
            f"Patient: I'm here for my follow-up on the {dx.icd_description.lower()}.",
            "Provider: Let's review how you've been doing. Any new symptoms or "
            "changes since the last visit?",
            "Patient: No, it's been stable — nothing new, no flare-ups.",
            "Provider: Good. Examination is unremarkable and your vitals are stable. "
            "No complications or acute decompensation today.",
            f"Provider: Assessment: {dx.icd_description.lower()}, stable on current "
            "management.",
        ]

    lines += [
        "Provider: This was a standard established-patient office visit — history, "
        "examination, and a discussion of management, low-to-moderate complexity.",
        "Provider: Continue your current management and we'll do a routine "
        "follow-up in a month.",
        "Patient: Sounds good, thank you.",
    ]
    return "\n".join(lines)
