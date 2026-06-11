"""Load a Synthea CSV cohort into EncounterSpec objects.

Deterministic by construction: selection is by sorted patient_id, then
sorted encounter_id. No random state inside the loader.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .encounter_spec import (
    Allergy,
    Condition,
    Demographics,
    Encounter,
    EncounterSpec,
    Medication,
    Observation,
    SyntheaProvenance,
    _repo_relative,
)

_NAME_SUFFIX = re.compile(r"\d+$")


def _strip_synthea_suffix(name: str) -> str:
    return _NAME_SUFFIX.sub("", name)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dose_from_description(description: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?\s*(?:MG|mg|ML|ml|MCG|mcg|G|g|UNIT|UNITS))", description)
    return m.group(1) if m else "as directed"


class SyntheaCohort:
    """Lazily-loaded handle over the Synthea CSV directory."""

    def __init__(self, cohort_dir: Path):
        self.cohort_dir = cohort_dir
        if not (cohort_dir / "patients.csv").exists():
            raise FileNotFoundError(f"patients.csv missing under {cohort_dir}")
        self._patients = pd.read_csv(cohort_dir / "patients.csv", dtype=str, keep_default_na=False)
        self._encounters = pd.read_csv(cohort_dir / "encounters.csv", dtype=str, keep_default_na=False)
        self._medications = pd.read_csv(cohort_dir / "medications.csv", dtype=str, keep_default_na=False)
        self._conditions = pd.read_csv(cohort_dir / "conditions.csv", dtype=str, keep_default_na=False)
        self._allergies = pd.read_csv(cohort_dir / "allergies.csv", dtype=str, keep_default_na=False)
        try:
            self._observations = pd.read_csv(
                cohort_dir / "observations.csv", dtype=str, keep_default_na=False
            )
        except FileNotFoundError:
            self._observations = pd.DataFrame()

        self._patients = self._patients.sort_values("Id").reset_index(drop=True)
        self._encounters = self._encounters.sort_values(["PATIENT", "START"]).reset_index(drop=True)

        self.provenance = SyntheaProvenance(
            cohort_path=_repo_relative(cohort_dir),
            cohort_sha256=_file_sha256(cohort_dir / "patients.csv"),
        )

    def patient_ids(self) -> list[str]:
        return self._patients["Id"].tolist()

    def first_encounter_with_active_medication(self, patient_id: str) -> EncounterSpec | None:
        """Return the patient's earliest encounter that has at least one medication.

        Used by the v1 proof: WRONG_DOSAGE requires at least one med to mutate.
        """
        encs = self._encounters[self._encounters["PATIENT"] == patient_id]
        for _, enc in encs.iterrows():
            spec = self._build_spec(patient_id, enc["Id"])
            if spec is not None and spec.encounter_medications:
                return spec
        return None

    def first_encounter(self, patient_id: str) -> EncounterSpec | None:
        """Return the patient's earliest encounter with no precondition filter."""
        encs = self._encounters[self._encounters["PATIENT"] == patient_id]
        for _, enc in encs.iterrows():
            spec = self._build_spec(patient_id, enc["Id"])
            if spec is not None:
                return spec
        return None

    def _build_spec(self, patient_id: str, encounter_id: str) -> EncounterSpec | None:
        prow = self._patients.loc[self._patients["Id"] == patient_id]
        if prow.empty:
            return None
        p = prow.iloc[0]
        erow = self._encounters.loc[self._encounters["Id"] == encounter_id]
        if erow.empty:
            return None
        e = erow.iloc[0]

        dob = date.fromisoformat(p["BIRTHDATE"])
        enc_start = datetime.fromisoformat(e["START"].replace("Z", "+00:00"))
        enc_stop = (
            datetime.fromisoformat(e["STOP"].replace("Z", "+00:00")) if e.get("STOP") else None
        )
        age = enc_start.date().year - dob.year - (
            (enc_start.date().month, enc_start.date().day) < (dob.month, dob.day)
        )

        demographics = Demographics(
            patient_id=patient_id,
            first_name=_strip_synthea_suffix(p["FIRST"]),
            last_name=_strip_synthea_suffix(p["LAST"]),
            dob=dob,
            gender="M" if p["GENDER"] == "M" else "F" if p["GENDER"] == "F" else "U",
            age_at_encounter=age,
        )
        encounter = Encounter(
            encounter_id=encounter_id,
            start=enc_start,
            stop=enc_stop,
            encounter_class=e["ENCOUNTERCLASS"],
            reason_code=e.get("REASONCODE") or None,
            reason_description=e.get("REASONDESCRIPTION") or None,
        )

        enc_meds = self._medications[self._medications["ENCOUNTER"] == encounter_id]
        active_meds = self._medications[
            (self._medications["PATIENT"] == patient_id) & (self._medications["STOP"] == "")
        ]

        def med_from_row(r: pd.Series) -> Medication:
            return Medication(
                rxnorm_code=r["CODE"],
                description=r["DESCRIPTION"],
                dose=_dose_from_description(r["DESCRIPTION"]),
                indication=r.get("REASONDESCRIPTION") or None,
                indication_code=r.get("REASONCODE") or None,
            )

        conditions = [
            Condition(snomed_code=r["CODE"], description=r["DESCRIPTION"])
            for _, r in self._conditions[self._conditions["PATIENT"] == patient_id].iterrows()
        ]
        allergies = [
            Allergy(snomed_code=r["CODE"], description=r["DESCRIPTION"])
            for _, r in self._allergies[self._allergies["PATIENT"] == patient_id].iterrows()
        ]

        observations: list[Observation] = []
        if not self._observations.empty:
            obs_rows = self._observations[self._observations["ENCOUNTER"] == encounter_id]
            for _, r in obs_rows.iterrows():
                if r.get("TYPE") != "numeric":
                    continue
                try:
                    value = float(r["VALUE"])
                except (ValueError, TypeError):
                    continue
                observations.append(
                    Observation(
                        loinc_code=r["CODE"],
                        description=r["DESCRIPTION"],
                        value=value,
                        unit=r.get("UNITS") or None,
                    )
                )

        return EncounterSpec(
            demographics=demographics,
            encounter=encounter,
            conditions=conditions,
            active_medications=[med_from_row(r) for _, r in active_meds.iterrows()],
            encounter_medications=[med_from_row(r) for _, r in enc_meds.iterrows()],
            allergies=allergies,
            observations=observations,
            provenance=self.provenance,
        )
