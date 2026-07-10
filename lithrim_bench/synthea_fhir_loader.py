"""Load a Synthea FHIR R4 cohort directory into Patient resources.

Sibling to ``lithrim_bench.synthea_loader`` for the CSV cohort. Synthea
v4.0.0 emits one Bundle JSON per patient under ``fhir/``, with the
Patient resource as one entry alongside Encounter / Observation /
Condition / MedicationRequest / etc.

For paper-1-copilot P1-FHIR-CONFORMANCE-MINI scope this loader returns
raw FHIR Patient resource dicts — what
``etlp-mapper/mappings/41/apply`` consumes wrapped as
``{"data": {"resource": <patient>}}``. Demographics projection to
``EncounterSpec.Demographics`` is provided as a convenience for
transcript synthesis.

Deterministic by construction: bundle paths sorted by patient_id;
Synthea v4.0.0 at the same seed produces byte-identical Patient
resources (Encounter/Claim time components drift by seconds — see
``data/synthea_2026-05-28/MANIFEST.txt`` for the falsifier check).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from .encounter_spec import Demographics, SyntheaProvenance, _repo_relative

# Non-patient bundles that share fhir/ with patient bundles.
_AUX_BUNDLE_PREFIXES = ("hospitalInformation", "practitionerInformation")


def _is_patient_bundle(path: Path) -> bool:
    return path.suffix == ".json" and not path.name.startswith(_AUX_BUNDLE_PREFIXES)


def _patient_id_from_bundle(bundle: dict) -> str:
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            return resource["id"]
    raise ValueError("bundle has no Patient resource")


class SyntheaFhirCohort:
    """Lazily-loaded handle over a Synthea FHIR-export directory."""

    def __init__(self, fhir_dir: Path):
        self.fhir_dir = Path(fhir_dir)
        if not self.fhir_dir.is_dir():
            raise FileNotFoundError(f"FHIR cohort dir not found: {fhir_dir}")

        self._bundle_paths_by_pid: dict[str, Path] = {}
        for path in self.fhir_dir.iterdir():
            if not _is_patient_bundle(path):
                continue
            with path.open() as f:
                bundle = json.load(f)
            try:
                pid = _patient_id_from_bundle(bundle)
            except ValueError:
                continue
            self._bundle_paths_by_pid[pid] = path

        # Deterministic ordering — patient_id sort, not filename sort.
        # Synthea filenames embed display-names which can drift if name
        # generation changes, but patient_id is the stable key.
        self._sorted_pids = sorted(self._bundle_paths_by_pid.keys())

        self.provenance = SyntheaProvenance(
            cohort_path=_repo_relative(self.fhir_dir),
            cohort_sha256=self._cohort_id_hash(),
            synthea_version="v4.0.0",
        )

    def _cohort_id_hash(self) -> str:
        """SHA256 of the sorted patient_id list.

        Stable across runs at the same seed even though individual
        bundle bytes drift on timestamps. Matches the reproducibility
        guarantee documented in MANIFEST.txt.
        """
        h = hashlib.sha256()
        for pid in self._sorted_pids:
            h.update(pid.encode())
            h.update(b"\n")
        return h.hexdigest()

    def patient_ids(self) -> list[str]:
        return list(self._sorted_pids)

    def __len__(self) -> int:
        return len(self._sorted_pids)

    def load_patient(self, patient_id: str) -> dict:
        """Return the raw FHIR Patient resource dict for the given id."""
        path = self._bundle_paths_by_pid.get(patient_id)
        if path is None:
            raise KeyError(f"patient_id {patient_id!r} not in cohort {self.fhir_dir}")
        with path.open() as f:
            bundle = json.load(f)
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Patient":
                return resource
        raise ValueError(f"bundle at {path} has no Patient resource")

    def first_n_patients(self, n: int) -> list[dict]:
        """Return the first n Patient resources in patient_id sort order."""
        return [self.load_patient(pid) for pid in self._sorted_pids[:n]]


def fhir_patient_to_demographics(patient: dict) -> Demographics:
    """Project a FHIR Patient resource to EncounterSpec Demographics.

    Used by transcript synthesizers that share a Demographics signature
    with the CSV-cohort path. Drops Patient fields the EncounterSpec
    doesn't model (identifier, address, extensions); preserves the
    name/dob/gender used by the transcript template.

    Synthea name strings carry numeric suffixes (e.g. ``Abdul218``) to
    avoid collisions with real-world names; we keep them as-is here so
    the projection is lossless. Strip via
    ``lithrim_bench.synthea_loader._strip_synthea_suffix`` if the
    transcript needs cleaner output.
    """
    gender_map = {"male": "M", "female": "F", "other": "O", "unknown": "U"}
    name = (patient.get("name") or [{}])[0]
    given = (name.get("given") or [""])[0]
    family = name.get("family") or ""

    dob_str = patient.get("birthDate")
    dob = date.fromisoformat(dob_str) if dob_str else date(1900, 1, 1)

    return Demographics(
        patient_id=patient["id"],
        first_name=given,
        last_name=family,
        dob=dob,
        gender=gender_map.get(patient.get("gender", "unknown"), "U"),
        age_at_encounter=0,
    )
