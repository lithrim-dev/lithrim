"""STRUCTURAL_MISSING_REQUIRED_SEGMENT injector: drops PV1 from ADT^A04.

ADT^A04 requires PV1 (patient visit) per HL7 v2.5. A semantic judge
reading the remaining segments will see a plausible patient
registration; the missing segment is a *specification* violation, not
a meaning violation. The Jute validator deterministically rejects.

PV1 is the default target because its absence has no observable
clinical effect in the text — the perfect categorical-blindness test.
"""
from __future__ import annotations

from typing import Any

from ..encounter_spec import EncounterSpec
from ._hl7 import find_segment, mutate_hl7
from .base import DefectInjector, InjectionRecipe, InjectionResult


class Hl7MissingSegmentInjector(DefectInjector):
    defect_type = "hl7_missing_segment"
    safety_flag = "STRUCTURAL_MISSING_REQUIRED_SEGMENT"
    mutates = "artifact_text"

    def __init__(self, segment: str = "PV1"):
        self.segment = segment

    def applies(self, spec: EncounterSpec) -> bool:
        return True

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        removed_segment_text: str | None = None

        def _drop(segments):
            nonlocal removed_segment_text
            idx = find_segment(segments, self.segment)
            removed_segment_text = "|".join(segments[idx])
            return segments[:idx] + segments[idx + 1:]

        new_artifacts, _, _ = mutate_hl7(artifacts, _drop)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span=f"{self.segment} (entire segment)",
            pre_value=removed_segment_text or "",
            post_value="(removed)",
            params={
                "missing_segment": self.segment,
                "structural_defect_class": "missing_required_segment",
            },
            expected_structural_verdict_when_caught="WARN",
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
