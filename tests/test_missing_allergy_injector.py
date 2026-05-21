import json

from lithrim_bench.injectors import MissingAllergyInjector
from lithrim_bench.synthesizers.scribe_artifact import synthesize_scribe_artifact
from lithrim_bench.synthesizers.transcript import synthesize_scribe_transcript

from ._factories import make_spec


def test_applies_requires_at_least_one_allergy():
    inj = MissingAllergyInjector()
    assert inj.applies(make_spec())
    assert not inj.applies(make_spec(with_allergies=False))


def test_inject_drops_named_allergy_from_artifact_only():
    spec = make_spec()
    transcript = synthesize_scribe_transcript(spec)
    artifact = synthesize_scribe_artifact(spec)
    assert "Penicillin allergy" in artifact["_soap_text"]

    result = MissingAllergyInjector().inject(spec, transcript, artifact)

    assert result.recipe.safety_flag == "MISSING_ALLERGY"
    assert result.recipe.mutated_projection == "artifact_text"
    assert result.recipe.params["allergy_description"] == "Penicillin allergy"
    soap = json.loads(result.artifact["content"])["content"][0]["attachment"]["data"]
    assert "Penicillin allergy" not in soap
    assert "Latex allergy" in soap
    assert result.transcript == transcript
