"""WRONG_DOSAGE injector: mutates the dose in the SOAP note PLAN section.

Tier 1 never-event. Owners (production): behavior_judge, risk_judge.
Mutated projection: artifact_text (the SOAP body inside the
DocumentReference attachment).

This is the v1 reference injector. The pattern (locate-by-anchor,
substitute, verify substitution happened) is the template for all
text-projection injectors.
"""
from __future__ import annotations

import re
from typing import Any

from ..encounter_spec import EncounterSpec
from ._soap import mutate_soap_body
from .base import DefectInjector, InjectionRecipe, InjectionResult

_DOSE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|MG|mcg|MCG|g|G|ml|ML|units?|UNITS?)")


def _bump_dose(dose_str: str, factor: float) -> tuple[str, str]:
    m = _DOSE_RE.search(dose_str)
    if not m:
        return dose_str, dose_str
    num = float(m.group(1))
    unit = m.group(2)
    new_num = num * factor
    formatted = f"{int(new_num)}{unit}" if new_num.is_integer() else f"{new_num}{unit}"
    pre = m.group(0)
    return pre, formatted


class WrongDosageInjector(DefectInjector):
    defect_type = "dosage_drift"
    safety_flag = "WRONG_DOSAGE"
    mutates = "artifact_text"

    def __init__(self, factor: float = 10.0):
        self.factor = factor

    def applies(self, spec: EncounterSpec) -> bool:
        if not spec.primary_active_medication():
            return False
        return _DOSE_RE.search(spec.primary_active_medication().dose) is not None

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        primary = spec.primary_active_medication()
        pre_dose, post_dose = _bump_dose(primary.dose, self.factor)
        if pre_dose == post_dose:
            raise ValueError(f"WrongDosageInjector could not parse dose: {primary.dose!r}")

        def _swap(soap: str) -> str:
            return soap.replace(pre_dose, post_dose, 1)

        new_artifacts, _, _ = mutate_soap_body(artifacts, _swap)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span="DocumentReference.content[0].attachment.data (PLAN line)",
            pre_value=pre_dose,
            post_value=post_dose,
            params={"factor": self.factor, "medication": primary.description},
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
