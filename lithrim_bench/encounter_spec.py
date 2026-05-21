"""EncounterSpec: the single source of truth for a synthetic clinical case.

Every projection (transcript, SOAP note, FHIR resource, HL7 message,
agent-specific artifact) is derived from one of these. A defect is a
typed mutation against a named projection; pre_value / post_value are
recorded so the label is true by construction.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Gender = Literal["M", "F", "O", "U"]


class Demographics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    first_name: str
    last_name: str
    dob: date
    gender: Gender
    age_at_encounter: int


class Medication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rxnorm_code: str
    description: str
    dose: str
    route: str | None = None
    frequency: str | None = None
    indication: str | None = None
    indication_code: str | None = None


class Allergy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snomed_code: str
    description: str
    severity: Literal["MILD", "MODERATE", "SEVERE"] | None = None
    reaction: str | None = None


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snomed_code: str
    description: str
    onset: date | None = None


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loinc_code: str
    description: str
    value: float | str
    unit: str | None = None


class Encounter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encounter_id: str
    start: datetime
    stop: datetime | None = None
    encounter_class: str
    reason_code: str | None = None
    reason_description: str | None = None


class SyntheaProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cohort_path: str
    cohort_sha256: str
    synthea_version: str | None = None


class EncounterSpec(BaseModel):
    """The canonical clinical encounter from which all modalities are derived."""

    model_config = ConfigDict(extra="forbid")

    demographics: Demographics
    encounter: Encounter
    conditions: list[Condition] = Field(default_factory=list)
    active_medications: list[Medication] = Field(default_factory=list)
    encounter_medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    provenance: SyntheaProvenance

    def primary_active_medication(self) -> Medication | None:
        return self.active_medications[0] if self.active_medications else None
