"""VALUE_MISMATCH injector: drifts a numeric lab/vital value in OBJECTIVE.

Tier 1 never-event (per DoH Abu Dhabi Data Integrity Standard §3).
Production owner: behavior_judge.

Mutated projection: artifact_text. The OBJECTIVE section lists the lab
value (e.g., 'HbA1c: 9.2 %'); the injector mutates the numeric value
while leaving description, unit, and context unchanged. The transcript
references the original (correct) value, so the drift is grounded by
negative audit trail.

Defaults to first lab-of-interest observation. For HbA1c specifically
the default drift moves the value across the diabetes diagnostic
boundary (>=6.5%), making the defect clinically meaningful — the
canonical hba1c case in lithrim-backend.
"""
from __future__ import annotations

import re
from typing import Any

from lithrim_bench.encounter_spec import EncounterSpec, Observation
from lithrim_bench.injectors.base import DefectInjector, InjectionRecipe, InjectionResult

from ._soap import mutate_soap_body

_TARGET_LOINCS = {"4548-4", "2093-3", "2339-0", "2571-8", "2085-9", "13457-7"}


def _drift_value(value: float) -> float:
    """Default drift: shift toward the opposite side of a typical normal range.

    For HbA1c-like values (5..15), subtract ~2.0 — moves a diagnostic
    9.2 down to a non-diagnostic 7.2. For cholesterol-like values
    (>100), reduce by ~20%. Conservative on small values (no underflow).
    """
    if 5 <= value <= 20:
        return round(value - 2.0, 1)
    if value >= 100:
        return round(value * 0.8, 1)
    return round(value * 0.7, 1)


def _format(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


class ValueMismatchInjector(DefectInjector):
    defect_type = "lab_value_drift"
    safety_flag = "VALUE_MISMATCH"
    mutates = "artifact_text"

    def _pick(self, spec: EncounterSpec) -> Observation | None:
        for obs in spec.observations:
            if obs.loinc_code in _TARGET_LOINCS and isinstance(obs.value, (int, float)):
                return obs
        return None

    def applies(self, spec: EncounterSpec) -> bool:
        return self._pick(spec) is not None

    def inject(
        self,
        spec: EncounterSpec,
        transcript: str,
        artifacts: list[dict[str, Any]],
    ) -> InjectionResult:
        obs = self._pick(spec)
        if obs is None:
            raise ValueError("no targetable observation for VALUE_MISMATCH")
        original_val = float(obs.value)
        drifted_val = _drift_value(original_val)

        pre_str = _format(original_val)
        post_str = _format(drifted_val)
        unit_suffix = f" {obs.unit}" if obs.unit else ""
        pre_token = f"{obs.description}: {pre_str}{unit_suffix}"
        post_token = f"{obs.description}: {post_str}{unit_suffix}"

        def _swap(soap: str) -> str:
            return soap.replace(pre_token, post_token, 1)

        new_artifacts, _, _ = mutate_soap_body(artifacts, _swap)

        recipe = InjectionRecipe(
            defect_type=self.defect_type,
            safety_flag=self.safety_flag,
            mutated_projection=self.mutates,
            mutated_field_or_span=f"DocumentReference.content[0].attachment.data (OBJECTIVE: {obs.description})",
            pre_value=pre_token,
            post_value=post_token,
            params={
                "loinc_code": obs.loinc_code,
                "description": obs.description,
                "unit": obs.unit,
                "pre_value": original_val,
                "post_value": drifted_val,
            },
        )
        return InjectionResult(transcript=transcript, artifacts=new_artifacts, recipe=recipe)
