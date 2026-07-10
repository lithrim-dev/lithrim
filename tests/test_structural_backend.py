import json
from pathlib import Path

from lithrim_bench.analysis import analyze_pack, analyze_per_case
from lithrim_bench.backends import MockBackend
from lithrim_bench.backends.etlp_structural import _extract_checks, _failed_checks
from lithrim_bench.eval_runner import run_pack
from lithrim_bench.harness import pack as _pack
from lithrim_bench.packager import package_case
from lithrim_bench.packs import active_packs
from lithrim_bench.taxonomy import load_taxonomy

from ._factories import make_spec

# PACK-5b: HL7 generation relocated into the active healthcare pack; reach it via the loader.
_GEN = _pack.load_pack_generators()
synthesize_hl7_adt_artifact = _GEN.synthesize_hl7_adt_artifact
synthesize_hl7_adt_transcript = _GEN.synthesize_hl7_adt_transcript
HL7_ADT_PACK = active_packs()["hl7_adt_v1"]


def test_failed_checks_real_shape():
    # The /apply checks carry {name, field, status: "pass"|"fail", message}.
    checks = [
        {"name": "dob-format-valid", "field": "PID.7", "status": "fail", "message": "not YYYYMMDD"},
        {"name": "gender-value-valid", "field": "PID.8", "status": "pass", "message": "ok"},
    ]
    assert _failed_checks(checks) == ["dob-format-valid"]


def test_extract_checks_nested_under_result_request():
    # HL7 mapping 93 shape: result.request.checks
    body = {
        "result": {
            "request": {
                "valid": False,
                "totalChecks": 2,
                "checks": [
                    {"name": "dob-format-valid", "status": "fail"},
                    {"name": "msg-type-valid", "status": "pass"},
                ],
            }
        },
        "org/id": "x",
    }
    assert _failed_checks(_extract_checks(body)) == ["dob-format-valid"]


def test_extract_checks_directly_under_result():
    # FHIR validator shape: result.checks
    body = {
        "result": {
            "resourceType": "Patient",
            "checks": [
                {"name": "name-present", "status": "pass"},
                {"name": "birthdate-present", "status": "fail"},
            ],
        }
    }
    assert _failed_checks(_extract_checks(body)) == ["birthdate-present"]


def test_extract_checks_absent_returns_empty():
    assert _extract_checks({"result": {"error": "no mapping"}}) == []


def test_mock_backend_emits_structural_verdict_for_hl7_cases(tmp_path: Path):
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    taxonomy = load_taxonomy()

    inj = _GEN.Hl7MalformedDateInjector()
    result = inj.inject(spec, transcript, artifacts)
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

    pack_path = tmp_path / "pack.jsonl"
    pack_path.write_text(json.dumps(row) + "\n")
    out = tmp_path / "runs.ndjson"

    run_pack(pack_path=pack_path, backend=MockBackend(), n=5, out_path=out)
    rows = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert all(r["structural_verdict"] == "BLOCK" for r in rows)
    assert all("STRUCTURAL_MALFORMED_DATE" in r["structural_findings"] for r in rows)

    per_case = analyze_per_case(rows)
    assert per_case[0]["structural"]["expected"] == "BLOCK"
    assert per_case[0]["structural"]["match_rate"] == 1.0

    pack_summary = analyze_pack(per_case)
    assert pack_summary["structural_cases"] == 1
    assert pack_summary["mean_structural_match_rate"] == 1.0


def test_structural_drift_rate_breaks_recall(tmp_path: Path):
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    taxonomy = load_taxonomy()
    result = _GEN.Hl7MissingSegmentInjector().inject(spec, transcript, artifacts)
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
    pack_path = tmp_path / "pack.jsonl"
    pack_path.write_text(json.dumps(row) + "\n")
    out = tmp_path / "runs.ndjson"

    backend = MockBackend(structural_drift_rate=1.0, noise_seed=42)
    run_pack(pack_path=pack_path, backend=backend, n=10, out_path=out)
    per_case = analyze_per_case([json.loads(line) for line in out.read_text().splitlines() if line.strip()])
    # drift_rate=1.0 -> validator always emits opposite verdict -> match_rate = 0
    assert per_case[0]["structural"]["match_rate"] == 0.0
