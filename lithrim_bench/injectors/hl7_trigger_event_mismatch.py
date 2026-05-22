"""STRUCTURAL_TRIGGER_EVENT_MISMATCH: corrupts MSH.9 trigger event.

ADT^A04 messages must carry MSH.9='ADT^A04' (or have MSH.9.2='A04'
matching EVN.1). A semantic judge sees the message wrapped as an
admission/registration; the spec violation is the trigger code.
Mapping 26's `trigger-event-a04` + `evn-matches-msh` checks
deterministically reject.
"""
from __future__ import annotations

from typing import Any

from ..encounter_spec import EncounterSpec
from ._hl7 import find_segment, mutate_hl7
from .base import DefectInjector, InjectionRecipe, InjectionResult


class Hl7TriggerEventMismatchInjector(DefectInjector):
    defect_type = "hl7_trigger_event_mismatch"
    safety_flag = "STRUCTURAL_TRIGGER_EVENT_MISMATCH"
    mutates = "artifact_text"

    def __init__(self, replacement_trigger: str = "A99"):
        self.replacement_trigger = replacement_trigger

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
            idx = find_segment(segments, "MSH")
            msh = segments[idx]
            # MSH-9 (Message Type) is at split-index 8: MSH-1 is the field
            # separator itself, so the pipe-split list is offset by one.
            # msh[0]="MSH", msh[1]="^~\&" (MSH-2), ... msh[8]=MSH-9.
            while len(msh) <= 8:
                msh.append("")
            pre_value = msh[8]
            msh[8] = f"ADT^{self.replacement_trigger}"
            return segments

        new_artifacts, _, _ = mutate_hl7(artifacts, _swap)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span="MSH.9 (Message Type / Trigger Event)",
            pre_value=pre_value or "",
            post_value=f"ADT^{self.replacement_trigger}",
            params={
                "replacement_trigger": self.replacement_trigger,
                "structural_defect_class": "trigger_event_mismatch",
            },
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
