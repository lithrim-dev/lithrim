"""Shared primary-diagnosis resolution for the coding pack.

transcript, clinical note, and FHIR Claim must all describe the same
primary diagnosis. Resolving it in one place keeps the three
projections consistent and fixes the age-blind ICD fallback: a
routine-exam encounter on a minor must not be coded Z00.00 (adult
exam).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..encounter_spec import EncounterSpec
from ._icd10_map import IcdMapping, lookup

_ADULT_EXAM = (
    "Z00.00",
    "Encounter for general adult medical examination without abnormal findings",
)
_CHILD_EXAM = (
    "Z00.129",
    "Encounter for routine child health examination without abnormal findings",
)


@dataclass(frozen=True)
class CodingDx:
    icd_code: str
    icd_description: str
    mapping: IcdMapping | None  # None == routine-exam fallback
    is_routine_exam: bool


def resolve_primary_dx(spec: EncounterSpec) -> CodingDx:
    """Pick the first condition with an ICD-10 mapping; else an
    age-appropriate routine-exam code."""
    for cond in spec.conditions:
        mapping = lookup(cond.snomed_code)
        if mapping is not None:
            return CodingDx(
                icd_code=mapping.icd10_base,
                icd_description=mapping.description,
                mapping=mapping,
                is_routine_exam=False,
            )
    code, desc = (
        _CHILD_EXAM if spec.demographics.age_at_encounter < 18 else _ADULT_EXAM
    )
    return CodingDx(icd_code=code, icd_description=desc, mapping=None, is_routine_exam=True)
