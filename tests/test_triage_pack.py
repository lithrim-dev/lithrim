import json

from lithrim_bench.harness import pack as _pack
from lithrim_bench.packager import package_case
from lithrim_bench.packs import active_packs
from lithrim_bench.taxonomy import load_taxonomy

from ._factories import make_spec

# PACK-5b: the triage injector + synthesizers + scenarios + the triage_v1 recipe relocated
# into the active healthcare pack; reach them through the pack generator loader.
_GEN = _pack.load_pack_generators()
MissedEscalationInjector = _GEN.MissedEscalationInjector
SCENARIOS = _GEN.SCENARIOS
pick_scenario = _GEN.pick_scenario
synthesize_triage_artifact = _GEN.synthesize_triage_artifact
synthesize_triage_transcript = _GEN.synthesize_triage_transcript
TRIAGE_PACK = active_packs()["triage_v1"]


def test_pick_scenario_is_deterministic_per_patient_id():
    spec = make_spec()
    a = pick_scenario(spec.demographics.patient_id)
    b = pick_scenario(spec.demographics.patient_id)
    assert a is b


def test_pick_scenario_returns_from_library():
    spec = make_spec()
    assert pick_scenario(spec.demographics.patient_id) in SCENARIOS


def test_artifact_carries_high_risk_and_ed_disposition():
    spec = make_spec()
    artifacts = synthesize_triage_artifact(spec)
    ra = json.loads(artifacts[0]["content"])
    assert ra["resourceType"] == "RiskAssessment"
    assert ra["prediction"][0]["qualitativeRisk"]["coding"][0]["code"] == "high"
    assert "emergency department" in ra["mitigation"]


def test_transcript_contains_red_flags_and_escalation():
    spec = make_spec()
    transcript = synthesize_triage_transcript(spec)
    scenario = pick_scenario(spec.demographics.patient_id)
    for flag in scenario.red_flags:
        assert flag in transcript
    assert "emergency department" in transcript


def test_missed_escalation_injector_downgrades_disposition_and_risk():
    spec = make_spec()
    transcript = synthesize_triage_transcript(spec)
    artifacts = synthesize_triage_artifact(spec)

    result = MissedEscalationInjector().inject(spec, transcript, artifacts)

    assert result.recipe.safety_flag == "MISSED_ESCALATION"
    ra = json.loads(result.artifacts[0]["content"])
    assert ra["prediction"][0]["qualitativeRisk"]["coding"][0]["code"] == "low"
    assert "self-care" in ra["mitigation"].lower()
    assert "emergency" not in ra["mitigation"].lower()
    assert result.transcript == transcript


def test_missed_escalation_case_packages_as_tier1_reject():
    spec = make_spec()
    transcript = synthesize_triage_transcript(spec)
    artifacts = synthesize_triage_artifact(spec)
    result = MissedEscalationInjector().inject(spec, transcript, artifacts)
    taxonomy = load_taxonomy()
    row = package_case(
        spec=spec,
        pack=TRIAGE_PACK.name,
        agent_type=TRIAGE_PACK.agent_type,
        transcript=result.transcript,
        artifacts=result.artifacts,
        recipes=[result.recipe],
        taxonomy=taxonomy,
        pinned={},
    )
    assert row["expected_safety_flags"] == ["MISSED_ESCALATION"]
    assert row["expected_compliance_verdict"] == "reject"
    assert row["expected_artifact_verdict"] == "BLOCK"
    # v2-only (S-BS-30/S-BS-31): behavior_judge is dormant (not in the production
    # trio); risk_judge is MISSED_ESCALATION's emitting production owner under v2,
    # so a single risk_judge fire still one-strikes.
    assert {"risk_judge"} <= set(row["expected_owner_map"]["MISSED_ESCALATION"])
