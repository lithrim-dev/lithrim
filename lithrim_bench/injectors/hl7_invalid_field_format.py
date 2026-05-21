"""STRUCTURAL_INVALID_FIELD_FORMAT injector: corrupts PID-8 gender.

HL7 v2 PID-8 (Administrative Sex) allows {M,F,O,U,A,N} per HL7 table
0001. Setting it to something like "MALE" or "1" is structurally
invalid even though a human reader would understand it. Semantic judge
sees plausible English; Jute validator deterministically rejects.
"""
from __future__ import annotations

from typing import Any

from ..encounter_spec import EncounterSpec
from ._hl7 import find_segment, mutate_hl7
from .base import DefectInjector, InjectionRecipe, InjectionResult


class Hl7InvalidFieldFormatInjector(DefectInjector):
    defect_type = "hl7_invalid_field_format"
    safety_flag = "STRUCTURAL_INVALID_FIELD_FORMAT"
    mutates = "artifact_text"

    def __init__(self, replacement: str = "MALE"):
        self.replacement = replacement

    def applies(self, spec: EncounterSpec) -> bool:
        return True

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        pre_value: str | None = None

        def _swap(segments):
            nonlocal pre_value
            idx = find_segment(segments, "PID")
            pid = segments[idx]
            while len(pid) <= 8:
                pid.append("")
            pre_value = pid[8]
            pid[8] = self.replacement
            return segments

        new_artifacts, _, _ = mutate_hl7(artifacts, _swap)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span="PID-8 (Administrative Sex)",
            pre_value=pre_value or "",
            post_value=self.replacement,
            params={
                "allowed_values": ["M", "F", "O", "U", "A", "N"],
                "structural_defect_class": "invalid_field_format",
            },
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
