"""REL-OPS-1 O1 — provider-drift canary, $0-testable on the seeded mock backend.

The mock's sha1(seed|case_id|run_index) determinism stands in for a provider:
the SAME noise_seed is a provider whose behavior is stable behind its pinned
model string; a DIFFERENT seed simulates the provider silently changing model
behavior (the pin's identity fields — backend/judge_model — are unchanged,
only the responses move). The canary must be quiet on the former and detect,
name, and exit non-zero on the latter.
"""
import json
from pathlib import Path

from lithrim_bench.backends import MockBackend
from lithrim_bench.canary import main as canary_main

FLIP = "0.5"


def _golden_cases() -> list[dict]:
    rows = [
        {
            "case_id": f"canary_{i:02d}",
            "pack": "canary_golden_v1",
            "agent_type": "scribe",
            "transcript": "...",
            "artifacts": [],
            "expected_compliance_verdict": "reject",
            "expected_safety_flags": ["WRONG_DOSAGE"],
        }
        for i in range(6)
    ]
    rows.append(
        {
            "case_id": "canary_clean",
            "pack": "canary_golden_v1",
            "agent_type": "scribe",
            "transcript": "...",
            "artifacts": [],
            "expected_compliance_verdict": "approve",
            "expected_safety_flags": [],
        }
    )
    return rows


def _golden_pack(tmp: Path) -> Path:
    path = tmp / "canary_golden.jsonl"
    with path.open("w") as f:
        for r in _golden_cases():
            f.write(json.dumps(r) + "\n")
    return path


def _mock_verdicts(seed: int, *, flip: float = 0.5, attach: float = 1.0) -> dict[str, str]:
    backend = MockBackend(decision_flip_rate=flip, flag_attachment_rate=attach, noise_seed=seed)
    return {c["case_id"]: backend.evaluate(c).compliance_verdict for c in _golden_cases()}


def _canary(pack: Path, baseline: Path, tmp: Path, *, record: bool, seed: int,
            flip: str = FLIP, attach: str = "1.0", tag: str = "run") -> int:
    argv = [
        "--pack-path", str(pack),
        "--baseline", str(baseline),
        "--backend", "mock",
        "--decision-flip-rate", flip,
        "--flag-attachment-rate", attach,
        "--noise-seed", str(seed),
        "--runs-out", str(tmp / f"{tag}.ndjson"),
    ]
    if record:
        argv.insert(0, "--record")
    return canary_main(argv)


def test_record_mints_baseline_with_pin_and_timestamp(tmp_path):
    pack = _golden_pack(tmp_path)
    baseline = tmp_path / "baseline.json"
    rc = _canary(pack, baseline, tmp_path, record=True, seed=0, tag="record")
    assert rc == 0
    doc = json.loads(baseline.read_text())
    assert doc["recorded_at"]
    assert doc["pin"]["backend"] == "MockBackend"
    assert doc["pin"]["judge_model"] == "mock"
    assert set(doc["cases"]) == {c["case_id"] for c in _golden_cases()}
    for entry in doc["cases"].values():
        assert entry["verdict"]
        assert isinstance(entry["flags"], list)


def test_same_seed_rerun_is_quiet(tmp_path, capsys):
    pack = _golden_pack(tmp_path)
    baseline = tmp_path / "baseline.json"
    assert _canary(pack, baseline, tmp_path, record=True, seed=0, tag="record") == 0
    capsys.readouterr()
    rc = _canary(pack, baseline, tmp_path, record=False, seed=0, tag="rerun")
    out = capsys.readouterr().out
    assert rc == 0
    assert "no drift" in out
    assert "DRIFT" not in out


def test_different_seed_detects_drift_and_names_flipped_cases(tmp_path, capsys):
    pack = _golden_pack(tmp_path)
    baseline = tmp_path / "baseline.json"
    v_base, v_new = _mock_verdicts(0), _mock_verdicts(1)
    flipped = sorted(c for c in v_base if v_base[c] != v_new[c])
    assert flipped, "precondition: the two seeds must genuinely disagree on this set"

    assert _canary(pack, baseline, tmp_path, record=True, seed=0, tag="record") == 0
    capsys.readouterr()
    rc = _canary(pack, baseline, tmp_path, record=False, seed=1, tag="rerun")
    out = capsys.readouterr().out
    assert rc != 0
    drift_lines = [line for line in out.splitlines() if "DRIFT" in line]
    assert sorted(
        c for c in v_base if any(c in line for line in drift_lines)
    ) == flipped
    for case_id in flipped:
        assert v_base[case_id] in out and v_new[case_id] in out


def test_flag_only_change_is_reported_but_not_a_verdict_flip(tmp_path, capsys):
    pack = _golden_pack(tmp_path)
    baseline = tmp_path / "baseline.json"
    assert _canary(
        pack, baseline, tmp_path, record=True, seed=0, flip="0.0", attach="0.5", tag="record"
    ) == 0
    capsys.readouterr()
    rc = _canary(
        pack, baseline, tmp_path, record=False, seed=1, flip="0.0", attach="0.5", tag="rerun"
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "no drift" in out
    assert "flags" in out
