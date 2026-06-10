import json

from lithrim_bench.harness import pack as _pack
from lithrim_bench.packager import package_case
from lithrim_bench.packs import active_packs
from lithrim_bench.taxonomy import load_taxonomy

from ._factories import make_spec

# PACK-5b: the scheduling injectors + synthesizers + the scheduling_v1 recipe relocated into
# the active healthcare pack; reach them through the pack generator loader.
_GEN = _pack.load_pack_generators()
PhiDisclosurePreVerificationInjector = _GEN.PhiDisclosurePreVerificationInjector
synthesize_scheduling_artifact = _GEN.synthesize_scheduling_artifact
synthesize_scheduling_transcript = _GEN.synthesize_scheduling_transcript
VERIFICATION_END = _GEN.VERIFICATION_END
VERIFICATION_START = _GEN.VERIFICATION_START
SCHEDULING_PACK = active_packs()["scheduling_v1"]


def test_scheduling_transcript_has_verification_block():
    spec = make_spec()
    t = synthesize_scheduling_transcript(spec)
    assert VERIFICATION_START in t
    assert VERIFICATION_END in t
    assert "verify_identity" in t
    assert "book_appointment" in t


def test_scheduling_artifact_shape():
    spec = make_spec()
    artifacts = synthesize_scheduling_artifact(spec)
    assert len(artifacts) == 2
    appt = json.loads(artifacts[0]["content"])
    assert appt["resourceType"] == "Appointment"
    assert appt["status"] == "booked"
    conf = json.loads(artifacts[1]["content"])
    assert conf["provider"] == "Dr. Patel"


def test_phi_injector_drops_verification_turns():
    spec = make_spec()
    transcript = synthesize_scheduling_transcript(spec)
    artifacts = synthesize_scheduling_artifact(spec)
    inj = PhiDisclosurePreVerificationInjector()
    result = inj.inject(spec, transcript, artifacts)

    assert result.recipe.safety_flag == "PHI_DISCLOSURE_PRE_VERIFICATION"
    assert result.recipe.mutated_projection == "transcript"
    assert "verify_identity" not in result.transcript
    assert "book_appointment" in result.transcript
    assert result.artifacts == artifacts


def test_phi_case_packages_cleanly_and_strips_markers():
    spec = make_spec()
    transcript = synthesize_scheduling_transcript(spec)
    artifacts = synthesize_scheduling_artifact(spec)
    inj = PhiDisclosurePreVerificationInjector()
    result = inj.inject(spec, transcript, artifacts)
    taxonomy = load_taxonomy()
    row = package_case(
        spec=spec,
        pack=SCHEDULING_PACK.name,
        agent_type=SCHEDULING_PACK.agent_type,
        transcript=result.transcript,
        artifacts=artifacts,
        recipes=[result.recipe],
        taxonomy=taxonomy,
        pinned={},
    )
    assert row["expected_compliance_verdict"] == "reject"
    assert row["expected_artifact_verdict"] == "BLOCK"
    assert row["expected_safety_flags"] == ["PHI_DISCLOSURE_PRE_VERIFICATION"]
    assert row["expected_owner_map"]["PHI_DISCLOSURE_PRE_VERIFICATION"] == ["policy_judge"]
    assert VERIFICATION_START not in row["transcript"]
    assert VERIFICATION_END not in row["transcript"]


def test_clean_scheduling_case_strips_markers_too():
    spec = make_spec()
    transcript = synthesize_scheduling_transcript(spec)
    artifacts = synthesize_scheduling_artifact(spec)
    taxonomy = load_taxonomy()
    row = package_case(
        spec=spec,
        pack=SCHEDULING_PACK.name,
        agent_type=SCHEDULING_PACK.agent_type,
        transcript=transcript,
        artifacts=artifacts,
        recipes=[],
        taxonomy=taxonomy,
        pinned={},
    )
    assert row["expected_compliance_verdict"] == "approve"
    assert VERIFICATION_START not in row["transcript"]
    assert "verify_identity" in row["transcript"]
