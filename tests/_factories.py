"""Shared fixtures: build a self-contained EncounterSpec without Synthea CSV."""
from __future__ import annotations

from datetime import date, datetime, timezone

from lithrim_bench.encounter_spec import (
    Allergy,
    Condition,
    Demographics,
    Encounter,
    EncounterSpec,
    Medication,
    Observation,
    SyntheaProvenance,
)


def make_spec(
    *,
    with_meds: bool = True,
    with_allergies: bool = True,
    with_observations: bool = True,
    with_conditions: bool = True,
) -> EncounterSpec:
    meds = (
        [Medication(rxnorm_code="123", description="metoprolol 50 MG Oral Tablet", dose="50mg")]
        if with_meds
        else []
    )
    allergies = (
        [
            Allergy(snomed_code="91936005", description="Penicillin allergy"),
            Allergy(snomed_code="300916003", description="Latex allergy"),
        ]
        if with_allergies
        else []
    )
    observations = (
        [
            Observation(loinc_code="4548-4", description="Hemoglobin A1c", value=9.2, unit="%"),
            Observation(loinc_code="8480-6", description="Systolic Blood Pressure", value=138.0, unit="mm[Hg]"),
        ]
        if with_observations
        else []
    )
    conditions = (
        [Condition(snomed_code="38341003", description="Hypertensive disorder")]
        if with_conditions
        else []
    )
    return EncounterSpec(
        demographics=Demographics(
            patient_id="p1",
            first_name="Jane",
            last_name="Doe",
            dob=date(1960, 1, 1),
            gender="F",
            age_at_encounter=65,
        ),
        encounter=Encounter(
            encounter_id="e1",
            start=datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc),
            encounter_class="ambulatory",
            reason_description="Hypertension follow-up",
        ),
        conditions=conditions,
        active_medications=meds,
        allergies=allergies,
        observations=observations,
        provenance=SyntheaProvenance(cohort_path="test", cohort_sha256="0" * 64),
    )
