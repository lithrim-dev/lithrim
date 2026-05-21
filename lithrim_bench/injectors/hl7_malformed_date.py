"""STRUCTURAL_MALFORMED_DATE injector: corrupts PID-7 birthdate format.

HL7 v2 dates must be YYYYMMDD with no separators. A semantic judge
reading the message text will see a plausible-looking date string
(e.g. "1960-01-01") and is not wired to validate format. The Jute
validator (etlp-mapper mapping 25) deterministically rejects.

This is the paper's headline categorical-blindness defect.
"""
from __future__ import annotations

from typing import Any

from ..encounter_spec import EncounterSpec
from ._hl7 import find_segment, mutate_hl7
from .base import DefectInjector, InjectionRecipe, InjectionResult


class Hl7MalformedDateInjector(DefectInjector):
    defect_type = "hl7_malformed_date"
    safety_flag = "STRUCTURAL_MALFORMED_DATE"
    mutates = "artifact_text"

    def applies(self, spec: EncounterSpec) -> bool:
        return True

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        pre_value: str | None = None
        post_value: str | None = None

        def _swap(segments):
            nonlocal pre_value, post_value
            pid_idx = find_segment(segments, "PID")
            pid = segments[pid_idx]
            while len(pid) <= 7:
                pid.append("")
            original = pid[7]
            if not original:
                raise ValueError("PID-7 is empty; cannot inject malformed date")
            if len(original) >= 8 and original.isdigit():
                mutated_date = original[:4] + "-" + original[4:6] + "-" + original[6:8]
            else:
                mutated_date = "0000-00-00"
            pid[7] = mutated_date
            pre_value = original
            post_value = mutated_date
            return segments

        new_artifacts, _, _ = mutate_hl7(artifacts, _swap)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span="PID-7 (DOB)",
            pre_value=pre_value or "",
            post_value=post_value or "",
            params={
                "expected_format": "YYYYMMDD",
                "structural_defect_class": "malformed_date",
            },
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
