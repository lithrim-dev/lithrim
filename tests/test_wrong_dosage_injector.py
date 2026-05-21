import json
from datetime import date, datetime, timezone

from lithrim_bench.encounter_spec import (
    Demographics,
    Encounter,
    EncounterSpec,
    Medication,
    SyntheaProvenance,
)
from lithrim_bench.injectors import WrongDosageInjector
from lithrim_bench.synthesizers.scribe_artifact import synthesize_scribe_artifact
from lithrim_bench.synthesizers.transcript import synthesize_scribe_transcript


def _spec() -> EncounterSpec:
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
        active_medications=[
            Medication(rxnorm_code="123", description="metoprolol 50 MG Oral Tablet", dose="50mg")
        ],
        provenance=SyntheaProvenance(cohort_path="test", cohort_sha256="0" * 64),
    )


def test_applies_requires_parseable_dose():
    inj = WrongDosageInjector()
    assert inj.applies(_spec())


def test_inject_mutates_artifact_only():
    spec = _spec()
    transcript = synthesize_scribe_transcript(spec)
    artifacts = [synthesize_scribe_artifact(spec)]
    inj = WrongDosageInjector(factor=10.0)
    result = inj.inject(spec, transcript, artifacts)

    assert result.transcript == transcript
    assert result.artifacts[0] != artifacts[0]
    assert result.recipe.safety_flag == "WRONG_DOSAGE"
    assert result.recipe.mutated_projection == "artifact_text"
    assert result.recipe.pre_value == "50mg"
    assert result.recipe.post_value == "500mg"

    doc = json.loads(result.artifacts[0]["content"])
    soap = doc["content"][0]["attachment"]["data"]
    assert "500mg" in soap
    assert "50mg" not in soap.replace("500mg", "")
