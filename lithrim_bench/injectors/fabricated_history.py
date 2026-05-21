"""FABRICATED_HISTORY injector: adds an un-evidenced condition to the SOAP PMH section.

Tier 2 high-risk; routes to reject with 2+ judges, needs_review with 1.

Mutated projection: artifact_text. The injector inserts a plausible-but-
absent condition into the PMH bullet list. The condition is not present
in EncounterSpec.conditions and not mentioned in the transcript, so the
fabrication is unambiguous.

Selection of the fabricated condition is deterministic: the first item
in FABRICATIONS that is NOT already in the patient's actual condition
set. This keeps the labeled defect well-defined regardless of which
Synthea patient is chosen.
"""
from __future__ import annotations

from typing import Any

from ..encounter_spec import EncounterSpec
from ._soap import mutate_soap_body
from .base import DefectInjector, InjectionRecipe, InjectionResult

# Plausible conditions that are commonly fabricated by hallucinating scribes.
# Order matters: the first one not in the patient's actual condition set is used.
FABRICATIONS: list[tuple[str, str]] = [
    ("44054006", "Diabetes mellitus type 2 (disorder)"),
    ("38341003", "Hypertensive disorder, systemic arterial (disorder)"),
    ("55822004", "Hyperlipidemia (disorder)"),
    ("13644009", "Hypercholesterolemia (disorder)"),
    ("84114007", "Heart failure (disorder)"),
]


class FabricatedHistoryInjector(DefectInjector):
    defect_type = "inject_condition"
    safety_flag = "FABRICATED_HISTORY"
    mutates = "artifact_text"

    def _pick(self, spec: EncounterSpec) -> tuple[str, str] | None:
        actual = {c.snomed_code for c in spec.conditions}
        actual_descs = {c.description.lower() for c in spec.conditions}
        for code, desc in FABRICATIONS:
            if code in actual or desc.lower() in actual_descs:
                continue
            return code, desc
        return None

    def applies(self, spec: EncounterSpec) -> bool:
        return self._pick(spec) is not None

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifact: dict[str, Any],
    ) -> InjectionResult:
        pick = self._pick(spec)
        if pick is None:
            raise ValueError("no fabricatable condition available for this EncounterSpec")
        code, desc = pick
        fabricated_line = f"  - {desc}"

        def _insert(soap: str) -> str:
            if "PMH:" not in soap:
                raise ValueError("SOAP body has no PMH: anchor")
            anchor = "PMH:\n"
            head, sep, tail = soap.partition(anchor)
            if "No significant past medical history." in tail.split("\n", 2)[0]:
                head2, sep2, tail2 = tail.partition("No significant past medical history.")
                return head + sep + head2 + fabricated_line.strip() + "." + tail2
            return head + sep + fabricated_line + "\n" + tail

        new_artifact, _, _ = mutate_soap_body(artifact, _insert)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span="DocumentReference.content[0].attachment.data (PMH section)",
            pre_value="(no entry)",
            post_value=desc,
            params={"fabricated_snomed_code": code, "fabricated_description": desc},
        )
        return InjectionResult(transcript=transcript, artifact=new_artifact, recipe=recipe)
