import json
from pathlib import Path

from lithrim_bench.analysis import analyze_pack, analyze_per_case
from lithrim_bench.backends import MockBackend
from lithrim_bench.backends.etlp_structural import _failed_checks
from lithrim_bench.eval_runner import run_pack
from lithrim_bench.packager import package_case
from lithrim_bench.packs import HL7_ADT_PACK
from lithrim_bench.synthesizers.hl7_adt_artifact import synthesize_hl7_adt_artifact
from lithrim_bench.synthesizers.hl7_adt_transcript import synthesize_hl7_adt_transcript
from lithrim_bench.taxonomy import load_taxonomy

from ._factories import make_spec


def test_failed_checks_dict_layout():
    checks = {
        "msh2_separators": {"pass": True, "message": "ok"},
        "pid7_date_format": {"pass": False, "message": "1973-09-11 not YYYYMMDD"},
        "pv1_present": {"pass": True, "message": "ok"},
    }
    failed = _failed_checks(checks)
    assert failed == ["pid7_date_format"]


def test_failed_checks_list_layout():
    checks = [
        {"name": "msh2_separators", "pass": True},
        {"name": "pid7_date_format", "pass": False},
    ]
    assert _failed_checks(checks) == ["pid7_date_format"]


def test_mock_backend_emits_structural_verdict_for_hl7_cases(tmp_path: Path):
    spec = make_spec()
    transcript = synthesize_hl7_adt_transcript(spec)
    artifacts = synthesize_hl7_adt_artifact(spec)
    taxonomy = load_taxonomy()

    from lithrim_bench.injectors import Hl7MalformedDateInjector

    inj = Hl7MalformedDateInjector()
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
    from lithrim_bench.injectors import Hl7MissingSegmentInjector

    result = Hl7MissingSegmentInjector().inject(spec, transcript, artifacts)
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
