import json

from lithrim_bench.encounter_spec import Condition
from lithrim_bench.harness import pack as _pack

from ._factories import make_spec

# PACK-5a: the scribe injectors + synthesizers relocated into the active healthcare pack;
# reach them through the pack generator loader (FABRICATIONS via the relocated submodule).
_GEN = _pack.load_pack_generators()
FabricatedHistoryInjector = _GEN.FabricatedHistoryInjector
FABRICATIONS = _GEN.fabricated_history.FABRICATIONS
synthesize_scribe_artifact = _GEN.synthesize_scribe_artifact
synthesize_scribe_transcript = _GEN.synthesize_scribe_transcript


def test_applies_returns_true_when_a_fabrication_is_unused():
    assert FabricatedHistoryInjector().applies(make_spec())


def test_applies_returns_false_when_patient_already_has_all_fabrications():
    spec = make_spec()
    spec.conditions = [
        Condition(snomed_code=code, description=desc) for code, desc in FABRICATIONS
    ]
    assert not FabricatedHistoryInjector().applies(spec)


def test_inject_adds_unknown_condition_to_pmh():
    spec = make_spec()
    transcript = synthesize_scribe_transcript(spec)
    artifacts = [synthesize_scribe_artifact(spec)]

    result = FabricatedHistoryInjector().inject(spec, transcript, artifacts)

    assert result.recipe.safety_flag == "FABRICATED_HISTORY"
    fabricated = result.recipe.params["fabricated_description"]
    assert fabricated not in {c.description for c in spec.conditions}
    soap = json.loads(result.artifacts[0]["content"])["content"][0]["attachment"]["data"]
    assert fabricated in soap
    assert result.transcript == transcript


def test_inject_replaces_NSPMH_stub_when_no_conditions():
    spec = make_spec(with_conditions=False)
    artifacts = [synthesize_scribe_artifact(spec)]
    assert "No significant past medical history." in artifacts[0]["_soap_text"]

    result = FabricatedHistoryInjector().inject(spec, "tx", artifacts)
    soap = json.loads(result.artifacts[0]["content"])["content"][0]["attachment"]["data"]
    assert result.recipe.params["fabricated_description"] in soap
