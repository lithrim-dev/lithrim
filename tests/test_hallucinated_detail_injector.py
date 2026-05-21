import json

from lithrim_bench.injectors import HallucinatedDetailInjector
from lithrim_bench.synthesizers.scribe_artifact import synthesize_scribe_artifact
from lithrim_bench.synthesizers.transcript import synthesize_scribe_transcript

from ._factories import make_spec


def test_always_applies():
    assert HallucinatedDetailInjector().applies(make_spec())


def test_inject_appends_unsupported_detail_to_subjective():
    spec = make_spec()
    transcript = synthesize_scribe_transcript(spec)
    artifact = synthesize_scribe_artifact(spec)

    result = HallucinatedDetailInjector().inject(spec, transcript, artifact)

    assert result.recipe.safety_flag == "HALLUCINATED_DETAIL"
    soap = json.loads(result.artifact["content"])["content"][0]["attachment"]["data"]
    detail = result.recipe.params["detail"]
    assert detail in soap
    assert detail not in transcript
    subjective_line = soap.split("\n")[0]
    assert detail in subjective_line
