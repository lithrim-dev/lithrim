import json
from pathlib import Path

from lithrim_bench.analysis import analyze_pack, analyze_per_case
from lithrim_bench.backends import MockBackend
from lithrim_bench.eval_runner import run_pack


def _toy_pack(tmp: Path) -> Path:
    rows = [
        {
            "case_id": "case_clean",
            "pack": "scribe_v1",
            "agent_type": "scribe",
            "transcript": "...",
            "artifacts": [],
            "expected_compliance_verdict": "approve",
            "expected_safety_flags": [],
            "clean_negative": True,
        },
        {
            "case_id": "case_t1",
            "pack": "scribe_v1",
            "agent_type": "scribe",
            "transcript": "...",
            "artifacts": [],
            "expected_compliance_verdict": "reject",
            "expected_safety_flags": ["WRONG_DOSAGE"],
            "clean_negative": False,
        },
    ]
    path = tmp / "toy_pack.jsonl"
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def test_ideal_mock_backend_yields_zero_instability(tmp_path):
    pack = _toy_pack(tmp_path)
    out = tmp_path / "runs.ndjson"
    run_pack(pack_path=pack, backend=MockBackend(), n=5, out_path=out)

    rows = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(rows) == 10  # 2 cases x 5 runs

    per_case = analyze_per_case(rows)
    by_id = {c["case_id"]: c for c in per_case}
    assert by_id["case_clean"]["verdict_instability"] == 0.0
    assert by_id["case_clean"]["verdict_match_rate"] == 1.0
    assert by_id["case_t1"]["verdict_instability"] == 0.0
    assert by_id["case_t1"]["verdict_match_rate"] == 1.0
    assert by_id["case_t1"]["flag_attachment_rate"]["WRONG_DOSAGE"] == 1.0


def test_flag_attachment_noise_shows_up_at_layer_two(tmp_path):
    pack = _toy_pack(tmp_path)
    out = tmp_path / "runs.ndjson"
    backend = MockBackend(flag_attachment_rate=0.5, noise_seed=42)
    run_pack(pack_path=pack, backend=backend, n=20, out_path=out)

    rows = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    per_case = analyze_per_case(rows)
    by_id = {c["case_id"]: c for c in per_case}

    # Decision layer should still be perfectly stable (verdict was never flipped).
    assert by_id["case_t1"]["verdict_instability"] == 0.0
    # Layer 2 attachment rate should land near the noise level (0.5 +/- sampling).
    attach = by_id["case_t1"]["flag_attachment_rate"]["WRONG_DOSAGE"]
    assert 0.2 <= attach <= 0.8


def test_decision_flip_rate_drives_verdict_instability(tmp_path):
    pack = _toy_pack(tmp_path)
    out = tmp_path / "runs.ndjson"
    backend = MockBackend(decision_flip_rate=0.5, noise_seed=7)
    run_pack(pack_path=pack, backend=backend, n=20, out_path=out)
    per_case = analyze_per_case([json.loads(line) for line in out.read_text().splitlines() if line.strip()])
    by_id = {c["case_id"]: c for c in per_case}
    # reject -> needs_review drift on the T1 case should produce > 0 instability
    assert by_id["case_t1"]["verdict_instability"] > 0.0


def test_pack_summary_reports_false_block_rate(tmp_path):
    pack = _toy_pack(tmp_path)
    out = tmp_path / "runs.ndjson"
    run_pack(pack_path=pack, backend=MockBackend(), n=5, out_path=out)
    per_case = analyze_per_case([json.loads(line) for line in out.read_text().splitlines() if line.strip()])
    pack_rows = [json.loads(line) for line in pack.read_text().splitlines() if line.strip()]
    summary = analyze_pack(per_case, pack_rows=pack_rows)
    assert summary["false_block_rate"] == 0.0
    assert summary["mean_verdict_match_rate"] == 1.0
    assert summary["instability_rate"] == 0.0


def test_fleiss_kappa_perfect_agreement_is_one(tmp_path):
    pack = _toy_pack(tmp_path)
    out = tmp_path / "runs.ndjson"
    run_pack(pack_path=pack, backend=MockBackend(), n=5, out_path=out)
    per_case = analyze_per_case([json.loads(line) for line in out.read_text().splitlines() if line.strip()])
    # Ideal backend -> all 3 judges agree on every run -> kappa = 1.0
    kappas = [c["decision_layer_kappa"] for c in per_case if c["decision_layer_kappa"] is not None]
    assert kappas
    assert all(abs(k - 1.0) < 1e-9 for k in kappas)
