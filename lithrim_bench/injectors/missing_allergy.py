"""MISSING_ALLERGY injector: drops a documented allergy from the SOAP ALLERGIES section.

Tier 1 never-event. Production owners: behavior_judge.

Mutated projection: artifact_text (the SOAP ALLERGIES list inside the
DocumentReference attachment). The transcript still references the
allergy, so the omission is unambiguously evidenced by negative audit
trail (transcript span vs absent artifact section).
"""
from __future__ import annotations

from typing import Any

from ..encounter_spec import EncounterSpec
from ._soap import mutate_soap_body
from .base import DefectInjector, InjectionRecipe, InjectionResult


class MissingAllergyInjector(DefectInjector):
    defect_type = "drop_allergy"
    safety_flag = "MISSING_ALLERGY"
    mutates = "artifact_text"

    def applies(self, spec: EncounterSpec) -> bool:
        return bool(spec.allergies)

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        target = spec.allergies[0]
        target_line = f"  - {target.description}"

        def _drop(soap: str) -> str:
            return soap.replace(target_line + "\n", "", 1).replace("\n" + target_line, "", 1)

        new_artifacts, _, _ = mutate_soap_body(artifacts, _drop)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span="DocumentReference.content[0].attachment.data (ALLERGIES list line)",
            pre_value=target_line.strip(),
            post_value="(removed)",
            params={
                "allergy_snomed_code": target.snomed_code,
                "allergy_description": target.description,
            },
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
