from lithrim_bench.injectors import (
    Hl7InvalidFieldFormatInjector,
    Hl7MalformedDateInjector,
    Hl7MissingSegmentInjector,
)
from lithrim_bench.injectors._hl7 import find_segment, parse_segments
from lithrim_bench.packager import package_case
from lithrim_bench.packs import HL7_ADT_PACK
from lithrim_bench.synthesizers.hl7_adt_artifact import synthesize_hl7_adt_artifact
from lithrim_bench.synthesizers.hl7_adt_transcript import synthesize_hl7_adt_transcript
from lithrim_bench.taxonomy import load_taxonomy

from ._factories import make_spec


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
