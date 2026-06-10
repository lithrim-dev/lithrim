from lithrim_bench.harness import pack as _pack
from lithrim_bench.packager import package_case
from lithrim_bench.packs import active_packs
from lithrim_bench.taxonomy import load_taxonomy

from ._factories import make_spec

# PACK-5b: the HL7 injectors + synthesizers + the hl7_adt_v1 recipe relocated into the
# active healthcare pack; reach them through the pack generator loader.
_GEN = _pack.load_pack_generators()
Hl7InvalidFieldFormatInjector = _GEN.Hl7InvalidFieldFormatInjector
Hl7MalformedDateInjector = _GEN.Hl7MalformedDateInjector
Hl7MissingSegmentInjector = _GEN.Hl7MissingSegmentInjector
Hl7TriggerEventMismatchInjector = _GEN.Hl7TriggerEventMismatchInjector
find_segment = _GEN.find_segment
parse_segments = _GEN.parse_segments
synthesize_hl7_adt_artifact = _GEN.synthesize_hl7_adt_artifact
synthesize_hl7_adt_transcript = _GEN.synthesize_hl7_adt_transcript
HL7_ADT_PACK = active_packs()["hl7_adt_v1"]


def test_synthesized_message_has_required_segments_and_msh2():
    spec = make_spec()
    artifacts = synthesize_hl7_adt_artifact(spec)
    body = artifacts[0]["content"]
    segments = parse_segments(body)
    names = [s[0] for s in segments]
    assert names[0] == "MSH"
    assert "EVN" in names
    assert "PID" in names
    assert "PV1" in names
    assert segments[0][1] == "^~\\&"
    pid_idx = find_segment(segments, "PID")
    assert segments[pid_idx][7] == spec.demographics.dob.strftime("%Y%m%d")


def test_malformed_date_injector_breaks_pid7_only():
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    result = Hl7MalformedDateInjector().inject(spec, transcript, artifacts)
    assert result.recipe.safety_flag == "STRUCTURAL_MALFORMED_DATE"
    assert "-" in result.recipe.post_value
    segments = parse_segments(result.artifacts[0]["content"])
    pid_idx = find_segment(segments, "PID")
    assert "-" in segments[pid_idx][7]
    assert result.transcript == transcript


def test_missing_segment_injector_drops_pv1():
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    result = Hl7MissingSegmentInjector().inject(spec, transcript, artifacts)
    assert result.recipe.safety_flag == "STRUCTURAL_MISSING_REQUIRED_SEGMENT"
    segments = parse_segments(result.artifacts[0]["content"])
    assert "PV1" not in [s[0] for s in segments]


def test_invalid_field_format_injector_corrupts_pid8():
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    result = Hl7InvalidFieldFormatInjector(replacement="MALE").inject(spec, transcript, artifacts)
    assert result.recipe.safety_flag == "STRUCTURAL_INVALID_FIELD_FORMAT"
    segments = parse_segments(result.artifacts[0]["content"])
    pid_idx = find_segment(segments, "PID")
    assert segments[pid_idx][8] == "MALE"


def test_trigger_event_mismatch_injector_corrupts_msh9_not_msh10():
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    result = Hl7TriggerEventMismatchInjector().inject(spec, transcript, artifacts)
    assert result.recipe.safety_flag == "STRUCTURAL_TRIGGER_EVENT_MISMATCH"
    segments = parse_segments(result.artifacts[0]["content"])
    msh = segments[find_segment(segments, "MSH")]
    evn = segments[find_segment(segments, "EVN")]
    # MSH-9 (message type / trigger) is at split-index 8 — that's what
    # must carry the corrupted trigger, NOT MSH-10 (control id, index 9).
    assert msh[8] == "ADT^A99"
    assert msh[9] != "ADT^A99"  # control id untouched
    # the EVN-1 trigger stays A04 — that is the actual mismatch
    assert evn[1] == "A04"


def test_structural_case_packages_with_block_and_empty_owner_map():
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    result = Hl7MalformedDateInjector().inject(spec, transcript, artifacts)
    taxonomy = load_taxonomy()
    row = package_case(
        spec=spec,
        pack=HL7_ADT_PACK.name,
        agent_type=HL7_ADT_PACK.agent_type,
        transcript=result.transcript,
        artifacts=result.artifacts,
        recipes=[result.recipe],
        taxonomy=taxonomy,
        pinned={},
    )
    assert row["expected_compliance_verdict"] == "reject"
    assert row["expected_artifact_verdict"] == "BLOCK"
    assert row["expected_structural_verdict"] == "BLOCK"
    assert row["expected_safety_flags"] == ["STRUCTURAL_MALFORMED_DATE"]
    assert row["expected_owner_map"] == {}


def test_clean_hl7_case_has_pass_structural_verdict():
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    taxonomy = load_taxonomy()
    row = package_case(
        spec=spec,
        pack=HL7_ADT_PACK.name,
        agent_type=HL7_ADT_PACK.agent_type,
        transcript=transcript,
        artifacts=artifacts,
        recipes=[],
        taxonomy=taxonomy,
        pinned={},
    )
    assert row["expected_structural_verdict"] == "PASS"
    assert row["expected_compliance_verdict"] == "approve"
