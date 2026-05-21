import json

from lithrim_bench.injectors import ValueMismatchInjector
from lithrim_bench.synthesizers.scribe_artifact import synthesize_scribe_artifact

from ._factories import make_spec


def test_applies_requires_a_lab_of_interest():
    assert ValueMismatchInjector().applies(make_spec())
    assert not ValueMismatchInjector().applies(make_spec(with_observations=False))


def test_inject_drifts_hba1c_into_non_diagnostic_range():
    spec = make_spec()
    artifacts = [synthesize_scribe_artifact(spec)]
    assert "Hemoglobin A1c: 9.2 %" in artifacts[0]["_soap_text"]

    result = ValueMismatchInjector().inject(spec, "tx", artifacts)

    assert result.recipe.safety_flag == "VALUE_MISMATCH"
    assert result.recipe.params["loinc_code"] == "4548-4"
    assert result.recipe.params["pre_value"] == 9.2
    assert result.recipe.params["post_value"] == 7.2

    soap = json.loads(result.artifacts[0]["content"])["content"][0]["attachment"]["data"]
    assert "Hemoglobin A1c: 7.2 %" in soap
    assert "Hemoglobin A1c: 9.2 %" not in soap
