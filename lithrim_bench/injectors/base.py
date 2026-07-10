"""Defect injector interface.

A DefectInjector takes a clean (transcript, artifact) pair plus the
EncounterSpec, mutates one of them in a typed way, and returns the
mutated pair together with an InjectionRecipe describing exactly what
changed. The recipe IS the label justification: a case with no recipe
is a clean negative.

Modality-aware by design: WRONG_DOSAGE in the transcript is a different
test than WRONG_DOSAGE in the artifact. The recipe records which
projection was mutated.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from ..encounter_spec import EncounterSpec

Projection = Literal["transcript", "artifact_text", "artifact_structured", "hl7_segment"]


@dataclass(frozen=True)
class InjectionRecipe:
    defect_type: str
    safety_flag: str
    mutated_projection: Projection
    mutated_field_or_span: str
    pre_value: str
    post_value: str
    params: dict[str, Any] = field(default_factory=dict)
    expected_structural_verdict_when_caught: str = "BLOCK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect_type": self.defect_type,
            "safety_flag": self.safety_flag,
            "mutated_projection": self.mutated_projection,
            "mutated_field_or_span": self.mutated_field_or_span,
            "pre_value": self.pre_value,
            "post_value": self.post_value,
            "params": self.params,
            "expected_structural_verdict_when_caught": self.expected_structural_verdict_when_caught,
        }


@dataclass
class InjectionResult:
    transcript: str
    artifacts: list[dict[str, Any]]
    recipe: InjectionRecipe


class DefectInjector(ABC):
    """Base class for typed defect injectors.

    Each subclass declares the safety_flag it produces and the projection
    it mutates. The packager uses these to populate expected_safety_flags
    and to verify the recipe is consistent with the snapshotted taxonomy.
    """

    defect_type: str = ""
    safety_flag: str = ""
    mutates: Projection = "artifact_text"

    @abstractmethod
    def applies(self, spec: EncounterSpec) -> bool:
        """Return True if the injector can apply to this EncounterSpec.

        WRONG_DOSAGE needs at least one med; MISSING_ALLERGY needs at
        least one allergy; etc.
        """

    @abstractmethod
    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        """Apply the defect. The clean inputs are not mutated in place."""
