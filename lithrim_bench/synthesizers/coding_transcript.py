"""Deterministic coding transcript synthesis.

v2 (2026-05-21): the dictation now explicitly grounds the ICD-10 code
the artifact carries (e.g., "Code as E11.9, type 2 diabetes without
complications, level 3 visit billed as CPT 99213"). v1 referred to
"the diagnosis" abstractly, which caused the live council to flag
clean cases as needs_review (no code grounding in transcript).

Contract preserved: the transcript NEVER mentions the
`upcode_requires_evidence` clinical phrase for any condition, so any
upcoded ICD in the artifact remains unsupported by construction.
"""
from __future__ import annotations

from ..encounter_spec import EncounterSpec
from ._icd10_map import lookup


def synthesize_coding_transcript(spec: EncounterSpec) -> str:
    demo = spec.demographics
    primary_icd: str | None = None
    primary_desc: str | None = None
    for cond in spec.conditions:
        mapping = lookup(cond.snomed_code)
        if mapping is not None:
            primary_icd = mapping.icd10_base
            primary_desc = mapping.description
            break
    if primary_icd is None:
        primary_icd = "Z00.00"
        primary_desc = "Encounter for general adult medical examination without abnormal findings"

    lines = [
        f"Provider: This is a coding dictation for {demo.first_name} {demo.last_name}, "
        f"{demo.age_at_encounter}{demo.gender}, seen on {spec.encounter.start.date().isoformat()}.",
        f"Provider: Primary diagnosis: {primary_desc}. Code as ICD-10 {primary_icd}.",
        "Provider: Visit was a standard established-patient follow-up — history, "
        "examination, and discussion of management. Code as a level 3 office visit, "
        "CPT 99213.",
        "Provider: No complications, no decompensation, no acute findings beyond "
        "what's already documented.",
        f"Coder: Confirmed: ICD-10 {primary_icd} ({primary_desc}), CPT 99213 level 3. Submitting the claim.",
    ]
    return "\n".join(lines)
