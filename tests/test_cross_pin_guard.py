"""O5 cross-pin comparison refusal (eval spec §1.6, SPEC_RELIABILITY_PROGRAM O5).

Every run row records a pinned block; two runs are comparable only if the
pinned tuple matches. compare_runs refuses mismatched pins with a typed
error unless allow_cross_pin=True, and then labels the output cross_pin=True.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.analysis import CrossPinError, compare_runs, read_runs
from lithrim_bench.backends import MockBackend
from lithrim_bench.eval_runner import run_pack

REPO_ROOT = Path(__file__).resolve().parent.parent


def _toy_pack(tmp: Path, name: str = "toy_pack.jsonl") -> Path:
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
    path = tmp / name
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def _run(tmp: Path, out_name: str, backend: MockBackend, pack: Path | None = None) -> Path:
    pack = pack or _toy_pack(tmp)
    out = tmp / out_name
    run_pack(pack_path=pack, backend=backend, n=3, out_path=out)
    return out


def test_run_rows_record_pinned_block_with_dataset_sha256(tmp_path):
    pack = _toy_pack(tmp_path)
    out = _run(tmp_path, "runs.ndjson", MockBackend(), pack=pack)
    rows = read_runs(out)
    expected_sha = hashlib.sha256(pack.read_bytes()).hexdigest()
    assert rows
    for r in rows:
        assert r["pin"]["backend"] == "MockBackend"
        assert r["pin"]["judge_model"] == "mock"
        assert r["pin"]["dataset_sha256"] == expected_sha


def test_matching_pins_compare_fine(tmp_path):
    pack = _toy_pack(tmp_path)
    rows_a = read_runs(_run(tmp_path, "a.ndjson", MockBackend(), pack=pack))
    rows_b = read_runs(_run(tmp_path, "b.ndjson", MockBackend(), pack=pack))
    result = compare_runs({"a": rows_a, "b": rows_b})
    assert result["cross_pin"] is False
    assert len(result["pins"]) == 1
    assert set(result["runs"]) == {"a", "b"}
    assert result["runs"]["a"]["pack_summary"]["cases"] == 2
    assert result["runs"]["b"]["pack_summary"]["cases"] == 2


def test_mismatched_pins_refuse(tmp_path):
    pack = _toy_pack(tmp_path)
    rows_a = read_runs(_run(tmp_path, "a.ndjson", MockBackend(), pack=pack))
    rows_b = read_runs(
        _run(tmp_path, "b.ndjson", MockBackend(decision_flip_rate=0.5, noise_seed=7), pack=pack)
    )
    with pytest.raises(CrossPinError):
        compare_runs({"a": rows_a, "b": rows_b})


def test_different_dataset_is_a_pin_mismatch(tmp_path):
    pack_a = _toy_pack(tmp_path, "pack_a.jsonl")
    pack_b_path = tmp_path / "pack_b.jsonl"
    pack_b_path.write_text(pack_a.read_text() + "\n")
    rows_a = read_runs(_run(tmp_path, "a.ndjson", MockBackend(), pack=pack_a))
    rows_b = read_runs(_run(tmp_path, "b.ndjson", MockBackend(), pack=pack_b_path))
    with pytest.raises(CrossPinError):
        compare_runs({"a": rows_a, "b": rows_b})


def test_allow_cross_pin_permits_and_labels(tmp_path):
    pack = _toy_pack(tmp_path)
    rows_a = read_runs(_run(tmp_path, "a.ndjson", MockBackend(), pack=pack))
    rows_b = read_runs(
        _run(tmp_path, "b.ndjson", MockBackend(decision_flip_rate=0.5, noise_seed=7), pack=pack)
    )
    result = compare_runs({"a": rows_a, "b": rows_b}, allow_cross_pin=True)
    assert result["cross_pin"] is True
    assert len(result["pins"]) == 2
    assert result["runs"]["a"]["pack_summary"]["cases"] == 2


def test_mixed_pins_within_one_source_refuse(tmp_path):
    pack = _toy_pack(tmp_path)
    rows_a = read_runs(_run(tmp_path, "a.ndjson", MockBackend(), pack=pack))
    rows_b = read_runs(
        _run(tmp_path, "b.ndjson", MockBackend(decision_flip_rate=0.5, noise_seed=7), pack=pack)
    )
    with pytest.raises(CrossPinError):
        compare_runs({"concatenated": rows_a + rows_b})


def _cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "analyze_runs.py"), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_refuses_cross_pin_and_allow_flag_labels(tmp_path):
    pack = _toy_pack(tmp_path)
    out_a = _run(tmp_path, "a.ndjson", MockBackend(), pack=pack)
    out_b = _run(
        tmp_path, "b.ndjson", MockBackend(decision_flip_rate=0.5, noise_seed=7), pack=pack
    )

    refused = _cli(["--runs", str(out_a), str(out_b)])
    assert refused.returncode != 0
    assert "cross-pin" in (refused.stderr + refused.stdout).lower()

    out_json = tmp_path / "comparison.json"
    allowed = _cli(
        ["--runs", str(out_a), str(out_b), "--allow-cross-pin", "--out-json", str(out_json)]
    )
    assert allowed.returncode == 0, allowed.stderr
    payload = json.loads(out_json.read_text())
    assert payload["cross_pin"] is True
    assert len(payload["pins"]) == 2


def test_cli_matching_pins_compare_fine(tmp_path):
    pack = _toy_pack(tmp_path)
    out_a = _run(tmp_path, "a.ndjson", MockBackend(), pack=pack)
    out_b = _run(tmp_path, "b.ndjson", MockBackend(), pack=pack)
    out_json = tmp_path / "comparison.json"
    res = _cli(["--runs", str(out_a), str(out_b), "--out-json", str(out_json)])
    assert res.returncode == 0, res.stderr
    payload = json.loads(out_json.read_text())
    assert payload["cross_pin"] is False
    assert payload["runs"][str(out_a)]["pack_summary"]["cases"] == 2


def test_cli_single_file_still_works(tmp_path):
    pack = _toy_pack(tmp_path)
    out_a = _run(tmp_path, "a.ndjson", MockBackend(), pack=pack)
    res = _cli(["--runs", str(out_a), "--pack", str(pack)])
    assert res.returncode == 0, res.stderr
    payload = json.loads((tmp_path / "a.analysis.json").read_text())
    assert payload["pack_summary"]["cases"] == 2
    assert payload["cross_pin"] is False
