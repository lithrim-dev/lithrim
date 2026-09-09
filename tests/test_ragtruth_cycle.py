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


def test_summarize_optimize_reads_the_three_files(tmp_path):
    import json

    role = rc.ROLE
    (tmp_path / f"result_dspy3b_{role}.json").write_text(
        json.dumps(
            {
                "n_heldout": 150,
                "compile_config": {"n_demos_bootstrapped": 4, "n_positive_demos": 4},
                "manifest": {
                    "demo_source_ids": ["ragtruth_1"],
                    "demos_out_of_sample": True,
                    "model": "azure/x",
                },
            }
        )
    )
    for k, g, p, r, e in (("baseline", 0.52, 0.30, 0.56, 5), ("optimized", 0.76, 0.53, 0.65, 4)):
        (tmp_path / f"score_{k}_dspy3b_{role}.json").write_text(
            json.dumps({"graded": g, "precision": p, "recall": r, "errors": e})
        )
    line = rc.summarize_optimize(tmp_path)
    assert "4 demos (4 positive)" in line and "out_of_sample=True" in line
    assert "graded 0.52 -> 0.76" in line and "refused 5 -> 4" in line and "azure/x" in line


def test_observed_served_counts_versions_across_the_cohort():
    matrix = [
        {"votes": [{"served_model": "gpt-4.1-2025-04-14"}]},
        {"votes": [{"served_model": "gpt-4.1-2025-04-14"}, {"served_model": None}]},
        {"votes": []},
    ]
    assert rc.observed_served(matrix) == {"gpt-4.1-2025-04-14": 2, "None": 1}


def test_cohort_summary_reports_states_purity_and_floor_from_one_grade():
    grade = {
        "matrix": [
            {"case_id": "a", "review": {"state": "CLEARED"}},
            {"case_id": "b", "review": {"state": "CLEARED"}},
            {"case_id": "c", "review": {"state": "FLAGGED"}},
            {"case_id": "d", "review": {"state": "ESCALATED"}},
        ],
        "scorecard": {
            "flag": {"precision": 0.53, "recall": 0.62},
            "verdict_accuracy": "3/4",
            "floor": {"enforced": 1, "cleared": 0, "inconclusive": 2, "gold_defect_clears": ["b"]},
        },
        "summary": {"judge_errors": 1, "cache_replays": 0},
    }
    rows = [
        {"case_id": "a", "expected_safety_flags": []},
        {"case_id": "b", "expected_safety_flags": ["X"]},  # a defect the floor cleared: impurity
        {"case_id": "c", "expected_safety_flags": ["X"]},
        {"case_id": "d", "expected_safety_flags": []},
    ]
    out = rc.cohort_summary(grade, rows)
    assert out["states"] == {"CLEARED": 2, "FLAGGED": 1, "ESCALATED": 1}
    assert out["auto_clear_purity"] == "1/2" and out["gold_defect_clears"] == 1
    assert out["flag_precision"] == 0.53 and out["verdict_accuracy"] == "3/4"
    assert out["floor"] == {"enforced": 1, "cleared": 0, "inconclusive": 2}
    assert out["judge_errors"] == 1 and out["cache_replays"] == 0


def test_enriched_ids_are_calibration_mismatches_with_a_missed_code_newest_row_wins():
    gold = [
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "c1",
            "agrees_with_gold": False,
            "missed": ["A"],
        },
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "c2",
            "agrees_with_gold": False,
            "missed": [],
        },  # spurious only
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "c3",
            "agrees_with_gold": True,
            "missed": [],
        },
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "t1",
            "agrees_with_gold": False,
            "missed": ["A"],
        },  # test side
        {"schema_version": "ws3-floor-correction/1", "case_id": "c4"},
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "c1",
            "agrees_with_gold": True,
            "missed": [],
        },  # newer: fixed
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "c5",
            "agrees_with_gold": False,
            "missed": ["B"],
        },
    ]
    chosen = rc.enriched_calibration_ids(gold, {"c1", "c2", "c3", "c4", "c5"})
    assert chosen == ["c5"]
    rows = [
        {"case_id": "c5", "split": "calibration"},
        {"case_id": "c1", "split": "calibration"},
        {"case_id": "t1", "split": "test"},
    ]
    assert rc.build_enriched_corpus(rows, set(chosen)) == [rows[0], rows[2]]
