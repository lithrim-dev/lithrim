"""EXPORT-1 (``lithrim export``): the graded corpus as labeled rows with a split gate and
label-basis tiers; the training class names come from the importer manifest."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lithrim_bench.cli import export as ex

VOCAB = SimpleNamespace(
    id="ragtruth_vocabulary",
    terms_for=lambda c: {"SOURCE_CONTRADICTION": ["Evident Conflict"]}.get(c, []),
    training_class_for=lambda c: {"SOURCE_CONTRADICTION": "conflict"}.get(c, c.lower()),
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
    row = ex.build_row(_case(), _gold(), _blob(), VOCAB, pack="_core")
    assert row["label_basis"] == "floor-proved" and row["floor"][0]["injected"] is True
    assert row["judge"]["spans"][0]["located"] and row["judge"]["spans"][0]["start"] == TEXT.index(
        "valet"
    )
    assert (
        row["judge"]["served_model"] == "gpt-4.1-2025-04-14" and row["judge"]["latency_ms"] == 900
    )
    assert row["human"]["codes"] == ["SOURCE_CONTRADICTION"] and row["source_id"] == "s1"
    assert row["task_type"] == "Data2txt" and row["generator_model"] == "m"
    assert row["judge"]["codes_dataset_terms"] == {}  # nothing raised on this row
    judge_only = ex.build_row(_case(), _gold(), _blob(enforced=False), VOCAB, pack="_core")
    assert judge_only["label_basis"] == "judge-only"


def test_a_bare_case_exports_through_the_top_level_fields():
    case = _case()
    del case["ragtruth"]
    case.update({"source_id": "n1", "task": "Data2txt", "model": "gen", "gold_spans": []})
    row = ex.build_row(case, _gold(), None, VOCAB, pack="_core")
    assert (row["source_id"], row["task_type"], row["generator_model"]) == ("n1", "Data2txt", "gen")


def test_filters_supervised_keeps_agreement_or_floor_proof_silver_needs_no_human():
    proved = ex.build_row(_case(), _gold(agrees=False), _blob(True), VOCAB, pack="_core")
    disagree = ex.build_row(_case(), _gold(agrees=False), _blob(False), VOCAB, pack="_core")
    agree = ex.build_row(_case(), _gold(agrees=True), _blob(False), VOCAB, pack="_core")
    assert ex.passes_filter(proved, "supervised") and ex.passes_filter(agree, "supervised")
    assert not ex.passes_filter(disagree, "supervised")
    assert ex.passes_filter(disagree, "silver") and ex.passes_filter(proved, "silver")


def test_training_labels_use_human_spans_when_supervised_and_judge_spans_when_silver():
    row = ex.build_row(_case(), _gold(), _blob(), VOCAB, pack="_core")
    sup = ex.training_labels(row, "supervised", VOCAB)
    assert sup == [
        {
            "start": TEXT.index("valet"),
            "end": TEXT.index("valet") + 13,
            "text": "valet parking",
            "label_type": "conflict",
        }
    ]
    silver = ex.training_labels(row, "silver", VOCAB)
    assert silver[0]["text"] == "valet parking" and silver[0]["label_type"] == "conflict"
    paper = ex.to_paper(row, "supervised", VOCAB)
    assert paper["reference"] == row["source"] and paper["labels"] == sup
    chat = ex.to_chat(row, "supervised", lambda task, src, resp: f"{task}|{resp}", VOCAB)
    assert chat["messages"][1]["content"] == '{"hallucination list": ["valet parking"]}'
    assert chat["messages"][0]["content"].startswith("Data2txt|")


def test_the_slice_declares_the_split_over_a_gold_row_without_one():
    assert (
        ex.build_row(_case(split="test"), _gold(split=None), None, VOCAB, pack="_core")["split"]
        == "test"
    )
    assert (
        ex.build_row(_case(split=None), _gold(split="calibration"), None, VOCAB, pack="_core")[
            "split"
        ]
        == "calibration"
    )


def test_training_classes_come_from_the_manifest_with_a_term_fallback():
    from lithrim_bench.harness.plugins import ImporterManifest, importer_vocabulary

    v = importer_vocabulary("ragtruth", pack="_core")
    assert v.training_class_for("SOURCE_CONTRADICTION") == "conflict"
    assert v.training_class_for("UNSUPPORTED_ASSERTION") == "baseless info"
    m = ImporterManifest.model_validate(
        {"id": "x", "dataset": "d", "label_types": {"Made Up": "UNSUPPORTED_ASSERTION"}}
    )
    assert m.training_class_for("UNSUPPORTED_ASSERTION") == "made up"
    assert m.training_class_for("NOPE") == "nope"


def test_gold_from_blob_matches_the_log_row_the_pipeline_writes():
    """UI-JOURNEY-1 (B8): a service export rebuilds the gold-mismatch row from the run blob
    with the same builder the pipeline uses for the corrections log."""
    from lithrim_bench.cli.export import export_manifest, export_rows, gold_from_blob
    from lithrim_bench.harness.plugins import importer_vocabulary

    case = {
        "case_id": "c1",
        "split": "test",
        "transcript": "src",
        "artifacts": [{"type": "generated_response", "content": "the sky is green"}],
        "expected_safety_flags": ["SOURCE_CONTRADICTION"],
        "expected_artifact_verdict": "BLOCK",
        "ground_truth_basis": "human_annotated",
        "ragtruth": {
            "source_id": "s1",
            "task_type": "QA",
            "model": "m",
            "labels": [
                {
                    "start": 11,
                    "end": 16,
                    "text": "green",
                    "label_type": "Evident Conflict",
                    "code": "SOURCE_CONTRADICTION",
                }
            ],
        },
    }
    blob = {
        "pipeline_run_id": "run-c1",
        "agent_id": "a",
        "timestamp": "2026-09-10T00:00:00+00:00",
        "verdict": "BLOCK",
        "grounded": {"verdict": "BLOCK", "floor_blocks": [], "floor_passes": []},
        "findings": ["SOURCE_CONTRADICTION"],
        "stage_results": {
            "semantic": {
                "judge_votes": [
                    {
                        "judge_role": "r",
                        "vote": "BLOCK",
                        "findings": ["SOURCE_CONTRADICTION"],
                        "served_model": "gpt-4.1-2025-04-14",
                    }
                ],
                "evidence": [
                    {
                        "judge": "r",
                        "violation_code": "SOURCE_CONTRADICTION",
                        "spans": [{"quote": "green"}],
                    }
                ],
            }
        },
    }
    vocab = importer_vocabulary("ragtruth", pack="_core")
    gold = gold_from_blob(case, blob, pack="_core")
    assert gold["schema_version"] == "gold-mismatch/1"
    assert (
        gold["agrees_with_gold"] is True
        and gold["split"] == "test"
        and gold["pipeline_run_id"] == "run-c1"
    )
    assert gold["gold_spans"][0]["text"] == "green" and gold["ts"] == blob["timestamp"]
    rows, out = export_rows(
        {"c1": case}, {"c1": gold}, {"run-c1": blob}, vocab, split="test", pack="_core"
    )
    assert len(rows) == 1 and rows[0]["label_basis"] == "judge-only"
    assert (
        rows[0]["judge"]["spans"][0]["located"] is True
        and rows[0]["judge"]["served_model"] == "gpt-4.1-2025-04-14"
    )
    assert out == rows
    m = export_manifest(
        rows, split="test", filter_mode="supervised", fmt="generic", vocab=vocab, graded_from="x"
    )
    assert (
        m["rows"] == 1
        and m["tiers"] == {"judge-only": 1}
        and m["served_models"] == ["gpt-4.1-2025-04-14"]
    )
    with pytest.raises(ValueError):
        export_rows({"c1": case}, {"c1": gold}, {}, vocab, split="test", fmt="paper", pack="_core")
    assert (
        gold_from_blob({"case_id": "u", "artifacts": []}, blob, pack="_core") is None
    )  # unlabeled: no row


def test_chat_export_hands_a_json_object_source_to_the_prompt_as_an_object():
    """A RAGTruth QA source is a {question, passages} object stored as JSON text on a prose
    case; the chat format crashed on every QA row (the prompt indexes the object)."""
    from lithrim_bench.cli.export import to_chat
    from lithrim_bench.harness.plugins import importer_vocabulary

    seen = {}

    def fill(task, src, response):
        seen[task] = src
        return f"{task}: {response}"

    vocab = importer_vocabulary("ragtruth", pack="_core")
    base = {
        "response": "r",
        "human": {"spans": [{"text": "r", "code": "SOURCE_CONTRADICTION"}]},
        "judge": {"spans": []},
    }
    to_chat(
        {
            **base,
            "task_type": "QA",
            "source_kind": "prose",
            "source": json.dumps({"question": "q", "passages": "p"}),
        },
        "supervised",
        fill,
        vocab,
    )
    to_chat(
        {
            **base,
            "task_type": "Summary",
            "source_kind": "prose",
            "source": "an article about {braces}",
        },
        "supervised",
        fill,
        vocab,
    )
    to_chat(
        {
            **base,
            "task_type": "Data2txt",
            "source_kind": "record",
            "source": json.dumps({"name": "x"}),
        },
        "supervised",
        fill,
        vocab,
    )
    assert seen["QA"] == {"question": "q", "passages": "p"}
    assert seen["Summary"] == "an article about {braces}"
    assert seen["Data2txt"] == {"name": "x"}


def test_a_row_the_training_prompt_cannot_fill_is_refused_by_name():
    from lithrim_bench.cli.export import export_rows
    from lithrim_bench.harness.plugins import importer_vocabulary

    vocab = importer_vocabulary("ragtruth", pack="_core")
    case = {
        "case_id": "q1",
        "split": "calibration",
        "transcript": "plain text",
        "source_kind": "prose",
        "artifacts": [{"content": "an answer"}],
        "ragtruth": {"task_type": "QA", "source_id": "s"},
    }
    gold = {
        "q1": {
            "schema_version": "gold-mismatch/1",
            "case_id": "q1",
            "split": "calibration",
            "agrees_with_gold": True,
            "raised_codes": [],
            "expected_codes": [],
            "gold_spans": [],
        }
    }

    def fill(task, src, response):
        return src["question"]

    with pytest.raises(ValueError, match="q1.*QA"):
        export_rows(
            {"q1": case},
            gold,
            {},
            vocab,
            split="calibration",
            filter_mode="all",
            fmt="chat",
            fill_prompt=fill,
            pack="_core",
        )
