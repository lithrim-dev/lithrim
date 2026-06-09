import json

from lithrim_bench.harness import pack as _pack

from ._factories import make_spec

# PACK-5a: the scribe injectors + synthesizers relocated into the active healthcare pack;
# reach them through the pack generator loader.
_GEN = _pack.load_pack_generators()
MissingAllergyInjector = _GEN.MissingAllergyInjector
synthesize_scribe_artifact = _GEN.synthesize_scribe_artifact
synthesize_scribe_transcript = _GEN.synthesize_scribe_transcript


def test_applies_requires_at_least_one_allergy():
    inj = MissingAllergyInjector()
    assert inj.applies(make_spec())
    assert not inj.applies(make_spec(with_allergies=False))


def test_inject_drops_named_allergy_from_artifact_only():
    spec = make_spec()
    transcript = synthesize_scribe_transcript(spec)
    artifacts = [synthesize_scribe_artifact(spec)]
    assert "Penicillin allergy" in artifacts[0]["_soap_text"]

    result = MissingAllergyInjector().inject(spec, transcript, artifacts)

    assert result.recipe.safety_flag == "MISSING_ALLERGY"
    assert result.recipe.mutated_projection == "artifact_text"
    assert result.recipe.params["allergy_description"] == "Penicillin allergy"
    soap = json.loads(result.artifacts[0]["content"])["content"][0]["attachment"]["data"]
    assert "Penicillin allergy" not in soap
    assert "Latex allergy" in soap
    assert result.transcript == transcript
