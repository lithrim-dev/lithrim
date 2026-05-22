"""UPCODING_RISK injector: swaps a base ICD-10 code for an upcoded sibling.

Tier 2 high-risk. Routes to reject with 2+ judges, needs_review with 1.

Mutated projection: artifact_structured. Locates the FHIR Claim among
the case artifacts (by type, not index — a coding case also carries a
fhir_document_reference clinical note) and swaps the diagnosis code
for its upcoded sibling. The sibling code requires clinical evidence
(e.g., 'heart failure', 'hyperglycemia') that neither the
coding_transcript nor the coding_note synthesizer ever produces — so
the upcoded code is unsupported by the documentation by construction.
"""
from __future__ import annotations

import json
from typing import Any

from ..encounter_spec import EncounterSpec
from ..synthesizers._icd10_map import lookup
from .base import DefectInjector, InjectionRecipe, InjectionResult


class UpcodingRiskInjector(DefectInjector):
    defect_type = "upcode"
    safety_flag = "UPCODING_RISK"
    mutates = "artifact_structured"

    def _primary_mapping(self, spec: EncounterSpec):
        for cond in spec.conditions:
            mapping = lookup(cond.snomed_code)
            if mapping is not None:
                return mapping
        return None

    def applies(self, spec: EncounterSpec) -> bool:
        return self._primary_mapping(spec) is not None

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        mapping = self._primary_mapping(spec)
        if mapping is None:
            raise ValueError("no upcodable diagnosis available for this EncounterSpec")
        new_artifacts = json.loads(json.dumps(artifacts))
        claim_idx = next(
            (i for i, a in enumerate(new_artifacts) if a.get("type") == "fhir_claim"),
            None,
        )
        if claim_idx is None:
            raise ValueError("coding case has no fhir_claim artifact to mutate")
        claim = json.loads(new_artifacts[claim_idx]["content"])
        diag_codings = claim["diagnosis"][0]["diagnosisCodeableConcept"]["coding"]
        target = next((c for c in diag_codings if c["code"] == mapping.icd10_base), None)
        if target is None:
            raise ValueError(
                f"Claim diagnosis does not contain expected base code {mapping.icd10_base!r}"
            )
        target["code"] = mapping.icd10_upcoded
        target["display"] = mapping.upcoded_description
        new_artifacts[claim_idx]["content"] = json.dumps(claim)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span=f"Claim.diagnosis[0].diagnosisCodeableConcept.coding[code]",
            pre_value=mapping.icd10_base,
            post_value=mapping.icd10_upcoded,
            params={
                "base_description": mapping.description,
                "upcoded_description": mapping.upcoded_description,
                "upcode_requires_evidence": mapping.upcode_requires_evidence,
            },
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
