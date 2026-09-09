"""The alignment experiment keeps benchmark targets outside its feedback path."""

import copy
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from repro.archehr.run import export_submission, make_feedback, prepare, review, validate_inputs


@pytest.fixture
def inputs():
    return {
        "schema_version": "archehr-alignment-input/1",
        "dataset": {"name": "neutral-fixture", "split": "smoke", "release": "1"},
        "cases": [
            {
                "case_id": "1",
                "patient_question": "When will it arrive?",
                "clinician_question": "What is the delivery window?",
                "note_sentences": [
                    {"id": "1", "text": "Delivery takes 12 days."},
                    {"id": "2", "text": "The box contains 12 items."},
                ],
                "answer_sentences": [
                    {"id": "1", "text": "Delivery takes 12 days."},
                    {"id": "2", "text": "No extra information is available."},
                ],
            }
        ],
    }


@pytest.fixture
def prediction():
    return [
        {
            "case_id": "1",
            "prediction": [
                {"answer_id": "1", "evidence_id": ["2"]},
                {"answer_id": "2", "evidence_id": []},
            ],
        }
    ]


@pytest.mark.parametrize(
    "location,key",
    [
        ("root", "gold"),
        ("case", "expected_safety_flags"),
        ("answer", "citations"),
        ("note", "relevance"),
    ],
)
def test_input_allowlist_rejects_target_fields(inputs, location, key):
    node = {
        "root": inputs,
        "case": inputs["cases"][0],
        "answer": inputs["cases"][0]["answer_sentences"][0],
        "note": inputs["cases"][0]["note_sentences"][0],
    }[location]
    node[key] = ["SECRET_TARGET"]
    with pytest.raises(ValueError, match="fields"):
        validate_inputs(inputs)


def test_duplicate_source_identifiers_refused(inputs):
    inputs["cases"][0]["note_sentences"][1]["id"] = "1"
    with pytest.raises(ValueError, match="duplicate"):
        validate_inputs(inputs)


def test_prepare_is_gold_free_preserves_answers_and_refuses_overwrite(inputs, tmp_path):
    original = copy.deepcopy(inputs)
    target = tmp_path / "prepared"
    manifest = prepare(inputs, target)
    assert inputs == original
    assert manifest["dataset"]["split"] == "smoke"
    assert manifest["model_calls"] == 0
    packet = json.loads((target / "prompts.jsonl").read_text().splitlines()[0])
    assert packet["input"] == inputs["cases"][0]
    assert packet["system"].find("Do not rewrite") >= 0
    with pytest.raises(FileExistsError):
        prepare(inputs, target)


def test_wrong_relation_is_never_deterministically_cleared(inputs, prediction):
    report = make_feedback(inputs, prediction)
    assert report["submission_valid"] is True
    link = report["cases"][0]["answers"][0]
    assert link["native_lithrim"]["value_membership"]["conforms"] is True
    assert link["semantic_support"] is None
    assert report["benchmark_score"] is None
    assert report["council_executed"] is False
    assert report["inputs_sha256"]


@pytest.mark.parametrize(
    "mutation,issue",
    [
        ("missing_case", "case_coverage"),
        ("extra_case", "case_coverage"),
        ("missing_answer", "answer_coverage"),
        ("invalid_source", "unknown_evidence_id"),
        ("duplicate_link", "duplicate_evidence_id"),
        ("duplicate_case", "duplicate_case_id"),
        ("duplicate_answer", "duplicate_answer_id"),
    ],
)
def test_bad_predictions_report_errors_and_cannot_export(
    inputs, prediction, mutation, issue, tmp_path
):
    if mutation == "missing_case":
        prediction.clear()
    elif mutation == "extra_case":
        prediction.append({"case_id": "9", "prediction": []})
    elif mutation == "missing_answer":
        prediction[0]["prediction"].pop()
    elif mutation == "invalid_source":
        prediction[0]["prediction"][0]["evidence_id"] = ["999"]
    elif mutation == "duplicate_link":
        prediction[0]["prediction"][0]["evidence_id"] = ["2", "2"]
    elif mutation == "duplicate_case":
        prediction.append(copy.deepcopy(prediction[0]))
    elif mutation == "duplicate_answer":
        prediction[0]["prediction"].append(copy.deepcopy(prediction[0]["prediction"][0]))
    feedback = make_feedback(inputs, prediction)
    assert not feedback["submission_valid"]
    assert issue in {e["code"] for e in feedback["issues"]}
    with pytest.raises(ValueError, match="invalid submission"):
        export_submission(inputs, prediction, tmp_path / "submission")
    assert not (tmp_path / "submission").exists()


def test_full_abstention_is_valid_but_has_no_truth_claim(inputs, prediction):
    for answer in prediction[0]["prediction"]:
        answer["evidence_id"] = []
    feedback = make_feedback(inputs, prediction)
    assert feedback["submission_valid"]
    assert all(a["semantic_support"] is None for a in feedback["cases"][0]["answers"])
    assert feedback["empty_alignment_count"] == 2


def test_export_is_official_shape_without_feedback(inputs, prediction, tmp_path):
    out = tmp_path / "submission"
    export_submission(inputs, prediction, out)
    with zipfile.ZipFile(out / "submission.zip") as archive:
        assert archive.namelist() == ["submission.json"]
        assert json.loads(archive.read("submission.json")) == prediction


def test_smoke_cli_never_claims_benchmark_or_model_improvement(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "repro.archehr.run",
            "smoke",
            "--out",
            str(tmp_path / "smoke"),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "smoke" / "manifest.json").read_text())
    assert manifest["model_calls"] == 0
    assert manifest["benchmark_score"] is None
    assert manifest["experiment_kind"] == "synthetic_plumbing_only"


def test_malformed_submission_does_not_echo_extra_fields_into_revision(inputs, tmp_path):
    submission = [{"case_id": "1", "prediction": [], "citations": "SECRET_TARGET"}]
    out = tmp_path / "review"
    report = review(inputs, submission, out)
    assert not report["submission_valid"]
    assert "SECRET_TARGET" not in (out / "revision_prompts.jsonl").read_text()
