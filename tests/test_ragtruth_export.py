"""EXPORT-1: the graded corpus as labeled rows with a split gate and label-basis tiers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "ragtruth_export", REPO / "scripts/ragtruth_export.py"
)
ex = importlib.util.module_from_spec(_spec)
sys.modules["ragtruth_export"] = ex
_spec.loader.exec_module(ex)

VOCAB = SimpleNamespace(
    id="ragtruth_vocabulary",
    terms_for=lambda c: {"SOURCE_CONTRADICTION": ["Evident Conflict"]}.get(c, []),
)
TEXT = "The venue offers valet parking and has a 4-star rating."


def _case(cid="c1", split="calibration"):
    return {
        "case_id": cid,
        "split": split,
        "source_kind": "record",
        "transcript": '{"business_stars": 3.5, "attributes": {"BusinessParking": {"valet": false}}}',
        "artifacts": [{"type": "generated_response", "content": TEXT}],
        "ragtruth": {"source_id": "s1", "task_type": "Data2txt", "model": "m", "labels": []},
    }


def _gold(agrees=False, missed=("SOURCE_CONTRADICTION",), split="calibration"):
    return {
        "schema_version": "gold-mismatch/1",
        "case_id": "c1",
        "split": split,
        "pipeline_run_id": "run-1",
        "ground_truth_basis": "human_annotated",
        "expected_codes": ["SOURCE_CONTRADICTION"],
        "raised_codes": [] if not agrees else ["SOURCE_CONTRADICTION"],
        "missed": list(missed) if not agrees else [],
        "spurious": [],
        "agrees_with_gold": agrees,
        "final_verdict": "BLOCK",
        "ts": "2026-09-09T00:00:00+00:00",
        "gold_spans": [
            {
                "start": TEXT.index("valet"),
                "end": TEXT.index("valet") + 13,
                "text": "valet parking",
                "label_type": "Evident Conflict",
                "code": "SOURCE_CONTRADICTION",
            }
        ],
        "rollout": [
            {
                "judge_role": "r",
                "reason": "x",
                "model": "azure/gpt-4.1",
                "served_model": "gpt-4.1-2025-04-14",
            }
        ],
        "ontology_version": "_core/1",
        "contract_versions": ["attribute-consistency/1"],
    }


def _blob(enforced=True):
    return {
        "pipeline_run_id": "run-1",
        "grounded": {
            "floor_blocks": [
                {
                    "contract": "attribute-consistency/1",
                    "contract_type": "attribute_consistency",
                    "flag": "SOURCE_CONTRADICTION",
                    "disposition": "VIOLATION" if enforced else "INCONCLUSIVE",
                    "injected": enforced,
                    "evidence": {"missing": ["valet=True vs record False"]},
                }
            ],
            "floor_passes": [],
        },
        "stage_results": {
            "semantic": {
                "judge_votes": [
                    {
                        "judge_role": "r",
                        "reason": "x",
                        "model": "azure/gpt-4.1",
                        "served_model": "gpt-4.1-2025-04-14",
                        "latency_ms": 900,
                        "confidence": None,
                    }
                ],
                "evidence": [
                    {
                        "judge": "r",
                        "violation_code": "SOURCE_CONTRADICTION",
                        "spans": [{"quote": "valet parking"}],
                    }
                ],
            }
        },
    }


def test_row_carries_identity_content_judge_floor_human_and_tier():
    row = ex.build_row(_case(), _gold(), _blob(), VOCAB)
    assert row["label_basis"] == "floor-proved" and row["floor"][0]["injected"] is True
    assert row["judge"]["spans"][0]["located"] and row["judge"]["spans"][0]["start"] == TEXT.index(
        "valet"
    )
    assert (
        row["judge"]["served_model"] == "gpt-4.1-2025-04-14" and row["judge"]["latency_ms"] == 900
    )
    assert row["human"]["codes"] == ["SOURCE_CONTRADICTION"] and row["source_id"] == "s1"
    assert row["judge"]["codes_dataset_terms"] == {}  # nothing raised on this row
    judge_only = ex.build_row(_case(), _gold(), _blob(enforced=False), VOCAB)
    assert judge_only["label_basis"] == "judge-only"


def test_filters_supervised_keeps_agreement_or_floor_proof_silver_needs_no_human():
    proved = ex.build_row(_case(), _gold(agrees=False), _blob(True), VOCAB)
    disagree = ex.build_row(_case(), _gold(agrees=False), _blob(False), VOCAB)
    agree = ex.build_row(_case(), _gold(agrees=True), _blob(False), VOCAB)
    assert ex.passes_filter(proved, "supervised") and ex.passes_filter(agree, "supervised")
    assert not ex.passes_filter(disagree, "supervised")
    assert ex.passes_filter(disagree, "silver") and ex.passes_filter(proved, "silver")


def test_training_labels_use_human_spans_when_supervised_and_judge_spans_when_silver():
    row = ex.build_row(_case(), _gold(), _blob(), VOCAB)
    sup = ex.training_labels(row, "supervised")
    assert sup == [
        {
            "start": TEXT.index("valet"),
            "end": TEXT.index("valet") + 13,
            "text": "valet parking",
            "label_type": "conflict",
        }
    ]
    silver = ex.training_labels(row, "silver")
    assert silver[0]["text"] == "valet parking" and silver[0]["label_type"] == "conflict"
    paper = ex.to_paper(row, "supervised")
    assert paper["reference"] == row["source"] and paper["labels"] == sup
    chat = ex.to_azure_chat(row, "supervised", lambda task, src, resp: f"{task}|{resp}")
    assert chat["messages"][1]["content"] == '{"hallucination list": ["valet parking"]}'
    assert chat["messages"][0]["content"].startswith("Data2txt|")


def test_the_slice_declares_the_split_over_a_gold_row_without_one():
    assert ex.build_row(_case(split="test"), _gold(split=None), None, VOCAB)["split"] == "test"
    assert (
        ex.build_row(_case(split=None), _gold(split="calibration"), None, VOCAB)["split"]
        == "calibration"
    )
