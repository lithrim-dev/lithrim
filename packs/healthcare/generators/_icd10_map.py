"""SNOMED -> ICD-10 mapping for the coding pack.

Coverage is intentionally narrow: the top-frequency Synthea clinical
disorders that have well-known upcoding patterns. Adding a row requires
a base code, a description, and an upcoded sibling — the upcode is what
makes the row useful as a defect target.

Each entry: snomed_code -> (icd10_base, description, icd10_upcoded_sibling,
upcode_description, upcode_requires_evidence).

upcode_requires_evidence is a clinical phrase that should appear in the
transcript to justify the upcoded code. Because the transcript synthesizer
never produces that phrase, the upcoded artifact is always evidentially
unsupported by construction.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IcdMapping:
    icd10_base: str
    description: str
    icd10_upcoded: str
    upcoded_description: str
    upcode_requires_evidence: str


SNOMED_TO_ICD10: dict[str, IcdMapping] = {
    "59621000": IcdMapping(
        icd10_base="I10",
        description="Essential (primary) hypertension",
        icd10_upcoded="I11.0",
        upcoded_description="Hypertensive heart disease with heart failure",
        upcode_requires_evidence="heart failure",
    ),
    "44054006": IcdMapping(
        icd10_base="E11.9",
        description="Type 2 diabetes mellitus without complications",
        icd10_upcoded="E11.65",
        upcoded_description="Type 2 diabetes mellitus with hyperglycemia",
        upcode_requires_evidence="hyperglycemia",
    ),
    "55822004": IcdMapping(
        icd10_base="E78.5",
        description="Hyperlipidemia, unspecified",
        icd10_upcoded="E78.2",
        upcoded_description="Mixed hyperlipidemia",
        upcode_requires_evidence="elevated triglycerides",
    ),
    "271737000": IcdMapping(
        icd10_base="D64.9",
        description="Anemia, unspecified",
        icd10_upcoded="D50.0",
        upcoded_description="Iron deficiency anemia secondary to blood loss (chronic)",
        upcode_requires_evidence="chronic blood loss",
    ),
    "10509002": IcdMapping(
        icd10_base="J20.9",
        description="Acute bronchitis, unspecified",
        icd10_upcoded="J20.0",
        upcoded_description="Acute bronchitis due to Mycoplasma pneumoniae",
        upcode_requires_evidence="Mycoplasma pneumoniae",
    ),
    "414545008": IcdMapping(
        icd10_base="I25.10",
        description="Atherosclerotic heart disease of native coronary artery without angina pectoris",
        icd10_upcoded="I25.110",
        upcoded_description="Atherosclerotic heart disease with unstable angina pectoris",
        upcode_requires_evidence="unstable angina",
    ),
}


def lookup(snomed_code: str) -> IcdMapping | None:
    return SNOMED_TO_ICD10.get(snomed_code)
