"""``lithrim`` (lithrim_bench.cli): the offline parts of the product loop.

The measurement gate, the pin gate, and the floor reading are what make a scorecard quotable;
all must be right without a stack up. Nothing in the CLI names a dataset: the adapter slices
it and the judge file defines the reviewer."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.cli import adapters
from lithrim_bench.cli import loop as rc

REPO = Path(__file__).resolve().parents[1]
JUDGE = REPO / "examples/ragtruth/judge.ragtruth_detector.json"


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lithrim_bench.cli", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


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
    out = _cli(
        "run",
        "--model",
        "azure/x-2025-01-01",
        "--judge",
        str(JUDGE),
        "--from",
        "optimize",
        "--to",
        "after",
        "--dry-run",
    )
    assert out.returncode == 0, out.stderr
    assert "plan: optimize -> pin -> after" in out.stdout and "azure/x-2025-01-01" in out.stdout


def test_product_verbs_alias_the_steps_and_load_needs_no_model():
    out = _cli(
        "run",
        "--model",
        "azure/x-2025-01-01",
        "--judge",
        str(JUDGE),
        "--from",
        "grade",
        "--to",
        "calibrate",
        "--dry-run",
    )
    assert out.returncode == 0 and "plan: before -> optimize -> pin" in out.stdout
    assert rc.plan("load", "load") == ("download",)
    assert rc.plan("load", "regrade") == rc.STEPS[: rc.STEPS.index("after") + 1]
    load = _cli("load", "--adapter", "examples/ragtruth/adapter.py", "--dry-run")
    assert load.returncode == 0 and "plan: download -> slice -> ingest" in load.stdout


def test_a_paid_verb_refuses_without_confirm_cost_and_a_judge():
    paid = _cli("grade", "--model", "azure/x-2025-01-01", "--judge", str(JUDGE))
    assert paid.returncode != 0 and "REFUSING a paid step (before)" in paid.stderr
    nojudge = _cli("configure", "--model", "azure/x-2025-01-01")
    assert nojudge.returncode != 0 and "needs --judge" in nojudge.stderr


def test_judge_file_is_a_contract(tmp_path):
    j = rc.load_judge(JUDGE)
    assert j["role"] == "ragtruth_detector" and len(j["lens_codes"]) == 2 and j["owned_codes"] == []
    bad = tmp_path / "j.json"
    bad.write_text(json.dumps({"role": "x"}))
    with pytest.raises(SystemExit, match="lacks"):
        rc.load_judge(bad)


def test_adapter_loader_fails_closed_on_a_module_without_the_contract(tmp_path):
    good = adapters.load_adapter("examples/ragtruth/adapter.py")
    assert callable(good.slice_cases) and callable(good.calibration_corpus)
    bad = tmp_path / "bad.py"
    bad.write_text("def slice_cases(*a, **k):\n    return []\n")
    with pytest.raises(TypeError, match="calibration_corpus"):
        adapters.load_adapter(str(bad))
    with pytest.raises(FileNotFoundError):
        adapters.load_adapter("no/such/adapter.py")


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
    role = "some_judge"
    (tmp_path / f"result_dspy3b_{role}.json").write_text(
        json.dumps(
            {
                "n_heldout": 150,
                "compile_config": {"n_demos_bootstrapped": 4, "n_positive_demos": 4},
                "manifest": {
                    "demo_source_ids": ["case_1"],
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
    line = rc.summarize_optimize(tmp_path, role)
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
        },
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
        },
        {"schema_version": "ws3-floor-correction/1", "case_id": "c4"},
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "c1",
            "agrees_with_gold": True,
            "missed": [],
        },
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


def test_pin_gate_refuses_a_regressing_demo_set_unless_forced():
    assert rc.pin_gate(0.76, None).startswith("pinned")
    assert rc.pin_gate(0.76, 0.52).startswith("pinned")
    assert rc.pin_gate(0.69, 0.69).startswith("pinned")
    with pytest.raises(SystemExit, match="REFUSING to pin"):
        rc.pin_gate(0.69, 0.76)
    assert "force-pin OVER" in rc.pin_gate(0.69, 0.76, force=True)


def test_contrastive_ids_interleave_missed_and_spurious_cases_in_equal_number():
    gold = [
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "m1",
            "agrees_with_gold": False,
            "missed": ["A"],
            "spurious": [],
        },
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "m2",
            "agrees_with_gold": False,
            "missed": ["A"],
            "spurious": ["B"],
        },
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "s1",
            "agrees_with_gold": False,
            "missed": [],
            "spurious": ["B"],
        },
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "ok",
            "agrees_with_gold": True,
            "missed": [],
            "spurious": [],
        },
        {
            "schema_version": "gold-mismatch/1",
            "case_id": "t1",
            "agrees_with_gold": False,
            "missed": [],
            "spurious": ["B"],
        },
    ]
    out = rc.contrastive_calibration_ids(gold, {"m1", "m2", "s1", "ok"})
    assert out == ["m1", "s1"]  # one pair: the first miss with the first spurious-only case


def test_the_cli_package_names_no_dataset():
    import re

    src = "".join(p.read_text().lower() for p in (REPO / "lithrim_bench/cli").glob("*.py"))
    src = re.sub(r"examples/ragtruth/\S*", "", src)  # usage lines may point at the example
    assert "ragtruth" not in src, "the CLI must not name a dataset outside an example path"
