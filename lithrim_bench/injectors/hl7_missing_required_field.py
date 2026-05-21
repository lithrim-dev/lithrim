"""STRUCTURAL_MISSING_REQUIRED_FIELD: blanks a required field inside a segment.

Calibrated against etlp-mapper mapping 26 (hl7-adt-a04-validator) — the
field-presence checks the live validator actually runs:

  PV1.2 patient-class    (required, in {I,O,E})
  PV1.7 attending-doctor (required for order routing)
  PID.3 patient-id
  PID.5.1/.5.2 names
  PID.7 dob; PID.8 gender; PID.11.4 state; PID.11.5 zip
  MSH.10 msg-control-id; MSH.12 hl7-version
  EVN.1 event-type

This is the "real" structural defect class the deterministic validator
catches in practice. A semantic judge reading the message will see a
plausible patient registration with one field blank; the validator
deterministically rejects.
"""
from __future__ import annotations

from typing import Any

from ..encounter_spec import EncounterSpec
from ._hl7 import find_segment, mutate_hl7
from .base import DefectInjector, InjectionRecipe, InjectionResult


class Hl7MissingRequiredFieldInjector(DefectInjector):
    defect_type = "hl7_missing_required_field"
    safety_flag = "STRUCTURAL_MISSING_REQUIRED_FIELD"
    mutates = "artifact_text"

    def __init__(self, segment: str = "PV1", field_index: int = 7, field_label: str = "PV1.7 attending-doctor"):
        self.segment = segment
        self.field_index = field_index
        self.field_label = field_label

    def applies(self, spec: EncounterSpec) -> bool:
        return True

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        pre_value: str | None = None

        def _blank(segments):
            nonlocal pre_value
            idx = find_segment(segments, self.segment)
            seg = segments[idx]
            while len(seg) <= self.field_index:
                seg.append("")
            pre_value = seg[self.field_index]
            seg[self.field_index] = ""
            return segments

        new_artifacts, _, _ = mutate_hl7(artifacts, _blank)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span=self.field_label,
            pre_value=pre_value or "",
            post_value="",
            params={
                "segment": self.segment,
                "field_index": self.field_index,
                "structural_defect_class": "missing_required_field",
            },
            expected_structural_verdict_when_caught="WARN",
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
