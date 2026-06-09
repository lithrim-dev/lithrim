from lithrim_bench.harness import pack as _pack
from lithrim_bench.packager import package_case
from lithrim_bench.taxonomy import load_taxonomy

from ._factories import make_spec

# PACK-5a: the scribe injectors + synthesizers relocated into the active healthcare pack;
# reach them through the pack generator loader.
_GEN = _pack.load_pack_generators()
FabricatedHistoryInjector = _GEN.FabricatedHistoryInjector
MissingAllergyInjector = _GEN.MissingAllergyInjector
WrongDosageInjector = _GEN.WrongDosageInjector
synthesize_scribe_artifact = _GEN.synthesize_scribe_artifact
synthesize_scribe_transcript = _GEN.synthesize_scribe_transcript


def _setup():
    spec = make_spec()
    transcript = synthesize_scribe_transcript(spec)
    artifacts = [synthesize_scribe_artifact(spec)]
    taxonomy = load_taxonomy()
    return spec, transcript, artifacts, taxonomy


def test_clean_negative_pack():
    spec, transcript, artifacts, taxonomy = _setup()
    row = package_case(
        spec=spec, pack="scribe_v1", agent_type="scribe",
        transcript=transcript, artifacts=artifacts,
        recipes=[], taxonomy=taxonomy, pinned={},
    )
    assert row["clean_negative"] is True
    assert row["multi_defect"] is False
    assert row["expected_compliance_verdict"] == "approve"
    assert row["expected_artifact_verdict"] == "PASS"
    assert row["expected_safety_flags"] == []
    assert row["injection_recipes"] == []


def test_single_defect_pack():
    spec, transcript, artifacts, taxonomy = _setup()
    inj = WrongDosageInjector()
    result = inj.inject(spec, transcript, artifacts)
    row = package_case(
        spec=spec, pack="scribe_v1", agent_type="scribe",
        transcript=result.transcript, artifacts=result.artifacts,
        recipes=[result.recipe], taxonomy=taxonomy, pinned={},
    )
    assert row["clean_negative"] is False
    assert row["multi_defect"] is False
    assert row["expected_safety_flags"] == ["WRONG_DOSAGE"]
    assert row["expected_compliance_verdict"] == "reject"
    assert row["expected_artifact_verdict"] == "BLOCK"
    # v2-only (S-BS-30/S-BS-31): behavior_judge is dormant (not in the production
    # trio); risk_judge is WRONG_DOSAGE's emitting production owner under v2, so a
    # single risk_judge fire still one-strikes.
    assert {"risk_judge"} <= set(row["expected_owner_map"]["WRONG_DOSAGE"])


def test_multi_defect_worst_of_verdict():
    spec, transcript, artifacts, taxonomy = _setup()
    r1 = MissingAllergyInjector().inject(spec, transcript, artifacts)
    r2 = FabricatedHistoryInjector().inject(spec, r1.transcript, r1.artifacts)
    row = package_case(
        spec=spec, pack="scribe_v1", agent_type="scribe",
        transcript=r2.transcript, artifacts=r2.artifacts,
        recipes=[r1.recipe, r2.recipe], taxonomy=taxonomy, pinned={},
    )
    assert row["multi_defect"] is True
    assert set(row["expected_safety_flags"]) == {"MISSING_ALLERGY", "FABRICATED_HISTORY"}
    assert row["expected_compliance_verdict"] == "reject"
    assert row["expected_artifact_verdict"] == "BLOCK"
    assert len(row["injection_recipes"]) == 2


def test_unknown_code_raises():
    spec, transcript, artifacts, taxonomy = _setup()
    from lithrim_bench.injectors.base import InjectionRecipe

    bogus = InjectionRecipe(
        defect_type="bogus",
        safety_flag="NONEXISTENT_CODE",
        mutated_projection="artifact_text",
        mutated_field_or_span="x",
        pre_value="a",
        post_value="b",
    )
    try:
        package_case(
            spec=spec, pack="scribe_v1", agent_type="scribe",
            transcript=transcript, artifacts=artifacts,
            recipes=[bogus], taxonomy=taxonomy, pinned={},
        )
    except ValueError as e:
        assert "NONEXISTENT_CODE" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown safety_flag")
