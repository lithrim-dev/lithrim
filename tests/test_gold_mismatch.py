"""GOLD-MISMATCH-1 + CORRECTIONS-SCOPE-1: every graded labeled case leaves a gold row in the
WORKSPACE's corrections log, and the run carries the comparison.

Observed 2026-09-09 (RAGTruth): the cohort scorecard computed caught/missed/spurious per case
only in the grade response; the run record and the corrections log carried no gold fields, so
"which cases did the judge disagree with the label on" was a script over grade JSONs, not a
query. And the log was one repo-level file for every workspace."""

from __future__ import annotations

import json
from pathlib import Path

from lithrim_bench.harness.correction import (
    DEFAULT_CORRECTIONS_PATH,
    GOLD_SCHEMA_VERSION,
    build_gold_mismatch,
    corrections_path,
)
from lithrim_bench.harness.ontology import load_ontology
from tests.test_persist2a import (
    HOUSE_BASELINE_PATH,
    HOUSE_CASE_ID,
    HOUSE_CASE_PATH,
    HOUSE_ONTOLOGY_PATH,
    PIPELINE_RUNS,
    _agent_no_baseline,
    _ontology_dict,
    grade_signature,
    load_case,
    run_eval,
)


def _result(codes, vote="BLOCK"):
    return {
        "semantic": {
            "judge_votes": [
                {
                    "judge_role": "risk_judge",
                    "vote": vote,
                    "findings": list(codes),
                    "confidence": 0.9,
                    "model": "m",
                    "reason": "r",
                    "served_model": "m-2025",
                }
            ]
        }
    }


def test_builder_strict_agreement_miss_and_spurious():
    ont = load_ontology(HOUSE_ONTOLOGY_PATH)
    case = {
        "case_id": "c1",
        "expected_safety_flags": ["A", "B"],
        "ground_truth_basis": "human_annotated",
        "split": "test",
        "gold_spans": [{"start": 0, "end": 3, "text": "abc"}],
    }
    row = build_gold_mismatch(
        case=case,
        result=_result(["A", "C"]),
        final_verdict="BLOCK",
        active_codes=["A", "C"],
        ontology=ont,
        contract_versions=["value-grounding/3"],
        case_id="c1",
        agent_id="ag",
        pipeline_run_id="run",
    )
    assert row["schema_version"] == GOLD_SCHEMA_VERSION
    assert row["missed"] == ["B"] and row["spurious"] == ["C"] and row["verdict_match"] is True
    assert row["agrees_with_gold"] is False and row["gold_spans"][0]["text"] == "abc"
    assert row["split"] == "test" and row["ground_truth_basis"] == "human_annotated"
    assert row["rollout"][0]["served_model"] == "m-2025" and row["contract_versions"] == [
        "value-grounding/3"
    ]
    assert (row["case_id"], row["agent_id"], row["pipeline_run_id"]) == ("c1", "ag", "run")
    clean = build_gold_mismatch(
        case={"expected_safety_flags": []},
        result=_result([], "PASS"),
        final_verdict="PASS",
        active_codes=[],
        ontology=ont,
    )
    assert clean["agrees_with_gold"] is True and clean["gold_verdict"] == "PASS"
    assert (
        build_gold_mismatch(
            case={"case_id": "unlabeled"},
            result=_result([]),
            final_verdict="PASS",
            active_codes=[],
            ontology=ont,
        )
        is None
    )


def test_gold_spans_resolve_through_the_importer_manifest(tmp_path):
    """ENGINE-CLEAN-1: a dataset-shaped case (spans where its importer manifest says) yields the
    same gold row as a case carrying the neutral top-level ``gold_spans``; correction.py names
    no dataset."""
    import lithrim_bench.harness.correction as corr

    ont = load_ontology(HOUSE_ONTOLOGY_PATH)
    case = {
        "case_id": "c2",
        "expected_safety_flags": ["A"],
        "ragtruth": {"source_id": "s1", "labels": [{"start": 4, "end": 9, "text": "quote"}]},
    }
    row = build_gold_mismatch(
        case=case,
        result=_result(["A"]),
        final_verdict="BLOCK",
        active_codes=["A"],
        ontology=ont,
        pack="_core",
    )
    assert row["gold_spans"] == [{"start": 4, "end": 9, "text": "quote"}]
    src = Path(corr.__file__).read_text().lower().replace("ragtruth_5827", "")
    assert "ragtruth" not in src, "the engine must not name a dataset"


def test_corrections_path_is_workspace_scoped_with_a_legacy_default(tmp_path):
    assert corrections_path(tmp_path) == tmp_path / "corrections.ndjson"
    assert corrections_path(None) == DEFAULT_CORRECTIONS_PATH


def test_a_graded_labeled_case_writes_a_gold_row_and_stamps_the_run(tmp_path):
    db = tmp_path / "collections.sqlite"
    agent = _agent_no_baseline()
    baseline = json.loads(HOUSE_BASELINE_PATH.read_text())
    blob = dict(baseline["provenance"])
    blob["agent_id"] = agent.name
    blob["case_id"] = agent.dataset.case_id
    blob["grade_signature"] = grade_signature(
        _ontology_dict(),
        assignments=None,
        models=None,
        council_config=agent.eval_profile.council_config,
    )
    PIPELINE_RUNS.insert(blob, db_path=db)
    out = tmp_path / "out"

    record = run_eval.run(agent, collections_db=db, out_dir=out)

    log = out / "corrections.ndjson"
    assert log.exists(), "the corrections log must live in the workspace out dir"
    rows = [json.loads(line) for line in log.open() if line.strip()]
    gold = [r for r in rows if r.get("schema_version") == GOLD_SCHEMA_VERSION]
    assert len(gold) == 1
    g = gold[0]
    case = load_case(HOUSE_CASE_ID, source=str(HOUSE_CASE_PATH))
    assert g["case_id"] == agent.dataset.case_id and g["agent_id"] == agent.name
    assert g["expected_codes"] == sorted(case.get("expected_safety_flags") or [])
    assert g["pipeline_run_id"] == record["result"]["provenance"]["pipeline_run_id"]
    assert record["gold"]["agrees_with_gold"] == g["agrees_with_gold"]
    head = PIPELINE_RUNS.get(g["pipeline_run_id"], db_path=db)
    assert head["gold"]["missed"] == g["missed"] and head["gold"]["spurious"] == g["spurious"]
