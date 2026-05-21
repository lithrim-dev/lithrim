"""Deterministic coding transcript synthesis.

Provider-to-coder dictation establishing the diagnosis and a level-3
visit. Crucially, the transcript NEVER mentions the upcode_requires_evidence
phrase for any condition — so any upcoded ICD code in the artifact is
unsupported by the transcript by construction.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec
from ._icd10_map import lookup


def synthesize_coding_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    primary_desc: str | None = None
    for cond in spec.conditions:
        mapping = lookup(cond.snomed_code)
        if mapping is not None:
            primary_desc = mapping.description
            break
    if primary_desc is None:
        primary_desc = "general health maintenance encounter"

    lines = [
        f"Provider: This is a coding dictation for {demo.first_name} {demo.last_name}, "
        f"{demo.age_at_encounter}{demo.gender}, seen on {spec.encounter.start.date().isoformat()}.",
        f"Provider: Primary diagnosis is {primary_desc.lower()}.",
        "Provider: Visit was a standard established-patient follow-up — history, "
        "examination, and discussion of management. Code as a level 3 office visit.",
        "Provider: No complications, no decompensation, no acute findings beyond "
        "what's already documented.",
        "Coder: Got it, primary diagnosis coded, level 3 visit billed.",
    ]
    return "\n".join(lines)
