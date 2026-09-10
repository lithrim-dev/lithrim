"""``examples/ragtruth/adapter.py``: a deterministic, stratified per-task grading slice.

Unlike the five-rule tracked sample, the slice is experiment data under ``out/`` (a labeled
cohort to grade and score against RAGTruth's human spans). It must be reproducible from the
upstream files alone: lowest ids first, one response per source, half labeled / half clean.
The adapter also satisfies the ``lithrim load`` contract."""

from __future__ import annotations

import json
from pathlib import Path

from lithrim_bench.cli.adapters import load_adapter

REPO = Path(__file__).resolve().parents[2]
rc = load_adapter(str(REPO / "examples/ragtruth/adapter.py"))


def _corpus():
    """Per task, six sources; each source has a CLEAN first response (model a, lowest id) and a
    LABELED second one (model b) — the shape that starved the labeled pool under a naive
    one-per-source rule. Plus a train-split row that must never be picked."""
    sources, responses = {}, []
    rid = 0
    for task in ("QA", "Summary", "Data2txt"):
        for i in range(6):
            sid = f"{task}-{i}"
            info = {"k": "v"} if task == "Data2txt" else f"source text {task} {i}"
            sources[sid] = {"source_id": sid, "task_type": task, "source_info": info, "prompt": ""}
            for model, labeled in (("model-a", False), ("model-b", True)):
                rid += 1
                responses.append(
                    {
                        "id": str(rid),
                        "source_id": sid,
                        "model": model,
                        "split": "test",
                        "quality": "good",
                        "response": f"resp {rid}",
                        "labels": [
                            {"start": 0, "end": 4, "text": "resp", "label_type": "Evident Conflict"}
                        ]
                        if labeled
                        else [],
                    }
                )
    responses.append({**responses[0], "id": "999", "split": "train"})
    return responses, sources


def _train_rows(sources, per_task, start=1000):
    extra = []
    rid = start
    for task in ("QA", "Summary", "Data2txt"):
        for i in range(per_task):
            sid = f"train-{task}-{i}"
            info = {"k": "v"} if task == "Data2txt" else f"train text {task} {i}"
            sources[sid] = {"source_id": sid, "task_type": task, "source_info": info, "prompt": ""}
            rid += 1
            extra.append(
                {
                    "id": str(rid),
                    "source_id": sid,
                    "model": "model-a",
                    "split": "train",
                    "quality": "good",
                    "response": f"train resp {rid}",
                    "labels": [],
                }
            )
    return extra


def test_slice_is_stratified_one_per_source_and_lowest_ids():
    responses, sources = _corpus()
    picked = rc.select_slice(responses, sources, per_task=4)
    assert len(picked) == 12
    for task in ("QA", "Summary", "Data2txt"):
        rows = [c for rule, c in picked if rule == f"slice:{task}"]
        assert len(rows) == 4
        assert sum(1 for c in rows if c["expected_safety_flags"]) == 2, "labeled half first"
        assert len({c["ragtruth"]["source_id"] for c in rows}) == 4, "one response per source"
    assert "999" not in {c["ragtruth"]["id"] for _, c in picked}
    assert rc.select_slice(responses, sources, per_task=4) == picked, "deterministic"
    assert all(c["ground_truth_basis"] == "human_annotated" for _, c in picked)


def test_slice_balances_generating_models_within_a_pool():
    responses, sources = _corpus()
    for r in responses:  # make every response labeled and alternate three models by id
        r["labels"] = [{"start": 0, "end": 4, "text": "resp", "label_type": "Evident Conflict"}]
        r["model"] = ("m1", "m2", "m3")[int(r["id"]) % 3]
    picked = rc.select_slice(responses, sources, per_task=6)  # 3 labeled picks; clean pool empty
    qa = [c["ragtruth"]["model"] for rule, c in picked if rule == "slice:QA"]
    assert len(qa) == 3 and sorted(qa.count(m) for m in ("m1", "m2", "m3")) == [1, 1, 1]


def test_natural_slice_keeps_the_corpus_rate_and_one_per_source():
    responses, sources = _corpus()
    picked = rc.select_slice(responses, sources, per_task=6, natural=True)
    assert len(picked) == 18  # every source once, no stratification
    for task in ("QA", "Summary", "Data2txt"):
        rows = [c for rule, c in picked if rule == f"slice:{task}"]
        assert len({c["ragtruth"]["source_id"] for c in rows}) == 6
        models = [c["ragtruth"]["model"] for c in rows]
        assert sorted(models.count(m) for m in ("model-a", "model-b")) == [3, 3], "model-balanced"


def test_calib_corpus_is_source_disjoint_and_task_interleaved():
    responses, sources = _corpus()
    extra = _train_rows(sources, 4)
    test_only = [r for r in responses if r["split"] == "test"]  # drop the planted train copy
    test_cases = [c for _, c in rc.select_slice(test_only, sources, per_task=4, natural=True)]
    rows = rc.build_calib_corpus(test_only + extra, sources, 4, test_cases)
    calib = [r for r in rows if r["split"] == "calibration"]
    dev = [r for r in rows if r["split"] == "dev"]
    # HOLDOUT-DEV-1: 4 train sources per task -> 1 dev (30%, rounded) + 3 calibration; the
    # graded test cut is not in the corpus at all
    assert len(calib) == 9 and len(dev) == 3 and not [r for r in rows if r["split"] == "test"]
    assert {r["ragtruth"]["source_id"] for r in calib + dev}.isdisjoint(
        {c["ragtruth"]["source_id"] for c in test_cases}
    )
    assert {r["ragtruth"]["source_id"] for r in calib}.isdisjoint(
        {r["ragtruth"]["source_id"] for r in dev}
    )
    assert all(r["ragtruth"]["source_id"].startswith("train-") for r in calib + dev)
    assert [r["ragtruth"]["task_type"] for r in rows[:3]] == ["Data2txt", "QA", "Summary"], (
        "interleaved"
    )
    assert all(
        "source_id" in r["ragtruth"] and r["ground_truth_basis"] == "human_annotated" for r in rows
    )


def test_calib_corpus_refuses_a_source_on_both_sides():
    import pytest

    responses, sources = _corpus()  # row 999 is a TRAIN copy of test source QA-0
    test_cases = [c for _, c in rc.select_slice(responses, sources, per_task=4, natural=True)]
    with pytest.raises(SystemExit, match="share 1 source"):
        rc.build_calib_corpus(responses, sources, 4, test_cases)


def test_train_split_slice_carries_the_calibration_marker_and_matches_the_calib_corpus():
    responses, sources = _corpus()
    extra = _train_rows(sources, 3, start=2000)
    test_only = [r for r in responses if r["split"] == "test"]
    train_cases = [
        c for _, c in rc.select_slice(test_only + extra, sources, 3, natural=True, split="train")
    ]
    assert len(train_cases) == 9 and all(c["split"] == "calibration" for c in train_cases)
    assert all(c["ragtruth"]["source_id"].startswith("train-") for c in train_cases)
    test_cases = [c for _, c in rc.select_slice(test_only, sources, 3, natural=True)]
    assert all(c["split"] == "test" for c in test_cases)
    calib_rows = rc.build_calib_corpus(test_only + extra, sources, 3, test_cases)
    # the corpus is the train-split slice exactly, carved into calibration + dev
    assert {r["case_id"] for r in calib_rows} == {c["case_id"] for c in train_cases}
    assert {r["split"] for r in calib_rows} == {"calibration", "dev"}


def test_the_adapter_contract_reads_the_two_upstream_files(tmp_path):
    """What ``lithrim load`` calls: slice_cases and calibration_corpus over a data dir."""
    responses, sources = _corpus()
    extra = _train_rows(sources, 2, start=3000)
    test_only = [r for r in responses if r["split"] == "test"]
    (tmp_path / "response.jsonl").write_text(
        "\n".join(json.dumps(r) for r in test_only + extra) + "\n"
    )
    (tmp_path / "source_info.jsonl").write_text(
        "\n".join(json.dumps(s) for s in sources.values()) + "\n"
    )
    cases = rc.slice_cases(tmp_path, per_task=2, split="test", natural=True)
    assert len(cases) == 6 and all(c["split"] == "test" for c in cases)
    assert all(c["ragtruth"]["selection_rule"].startswith("slice:") for c in cases)
    rows = rc.calibration_corpus(tmp_path, per_task=2, test_cases=cases)
    # 2 train sources per task -> 1 dev + 1 calibration each (a task keeps one source to train on)
    assert sum(1 for r in rows if r["split"] == "calibration") == 3
    assert sum(1 for r in rows if r["split"] == "dev") == 3
    train = rc.slice_cases(tmp_path, per_task=2, split="train", natural=True)
    assert len(train) == 6 and all(c["split"] == "calibration" for c in train)
