import json

from lithrim_bench.harness import pack as _pack

from ._factories import make_spec

# PACK-5a: the scribe injectors + synthesizers relocated into the active healthcare pack;
# reach them through the pack generator loader.
_GEN = _pack.load_pack_generators()
HallucinatedDetailInjector = _GEN.HallucinatedDetailInjector
synthesize_scribe_artifact = _GEN.synthesize_scribe_artifact
synthesize_scribe_transcript = _GEN.synthesize_scribe_transcript


def test_always_applies():
    assert HallucinatedDetailInjector().applies(make_spec())


def test_inject_appends_unsupported_detail_to_subjective():
    spec = make_spec()
    transcript = synthesize_scribe_transcript(spec)
    artifacts = [synthesize_scribe_artifact(spec)]

    result = HallucinatedDetailInjector().inject(spec, transcript, artifacts)

    assert result.recipe.safety_flag == "HALLUCINATED_DETAIL"
    soap = json.loads(result.artifacts[0]["content"])["content"][0]["attachment"]["data"]
    detail = result.recipe.params["detail"]
    assert detail in soap
    assert detail not in transcript
    subjective_line = soap.split("\n")[0]
    assert detail in subjective_line
