"""``scripts/ragtruth_cycle.py``: the offline parts of the clean optimize path.

The measurement gate and the floor reading are what make a scorecard quotable; both must be
right without a stack up."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ragtruth_cycle", REPO / "scripts/ragtruth_cycle.py")
rc = importlib.util.module_from_spec(_spec)
sys.modules["ragtruth_cycle"] = rc
_spec.loader.exec_module(rc)


def test_measurement_gate_refuses_replays_and_reports_refusals():
    with pytest.raises(SystemExit, match="cache replays"):
        rc.check_measurement({"graded": 450, "cache_replays": 12, "judge_errors": 0})
    with pytest.raises(SystemExit, match="failed to grade"):
        rc.check_measurement({"graded": 449, "errors": 1, "cache_replays": 0})
    line = rc.check_measurement({"graded": 450, "cache_replays": 0, "judge_errors": 12})
    assert "450 graded" in line and "12 judge call(s) refused/failed" in line


def test_floor_reading_attributes_post_minus_no_floor_not_pre_minus_post():
    sc = {
        "floor": {
            "verdict_accuracy_pre_floor": 0.858,
            "verdict_accuracy_post_floor": 0.836,
            "verdict_accuracy_no_floor": 0.840,
            "enforced": 21,
            "cleared": 0,
            "inconclusive": 222,
            "gold_defect_clears": [],
        }
    }
    text = rc.floor_reading(sc)
    assert "floor effect: -0.4 pts" in text
    assert "genuine defects cleared by the floor: 0" in text
    assert "voting rule alone: 85.8" in text and "NOT a floor effect" in text
    assert "not attributable" in rc.floor_reading({"floor": {"verdict_accuracy_post_floor": 0.8}})


def test_dry_run_prints_the_step_plan_without_a_stack():
    out = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/ragtruth_cycle.py"),
            "--model",
            "azure/x-2025-01-01",
            "--from",
            "optimize",
            "--to",
            "after",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout
    assert "plan: optimize -> pin -> after" in out and "azure/x-2025-01-01" in out


def test_arm_attestation_accepts_a_dated_id_or_an_attested_deployment_only():
    assert (
        rc.arm_attestation("azure/gpt-4.1-2025-04-14", None, None)["pinned_by"] == "dated model id"
    )
    att = rc.arm_attestation("gpt-4.1", "2025-04-14", "NoAutoUpgrade")
    assert att["pinned_by"] == "operator attestation" and att["dated_model_id"] is False
    drift = rc.arm_attestation("gpt-4.1", "2025-04-14", "OnceNewDefaultVersionAvailable")
    assert "silent version drift" in drift["pinned_by"]
    pending = rc.arm_attestation("gpt-4.1", "unverified", "unverified")
    assert "PENDING" in pending["pinned_by"]
    with pytest.raises(SystemExit, match="floating alias"):
        rc.arm_attestation("gpt-4.1", None, None)
    with pytest.raises(SystemExit, match="floating alias"):
        rc.arm_attestation("gpt-4.1-latest", None, None)
