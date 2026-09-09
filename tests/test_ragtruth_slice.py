"""``scripts/ragtruth_cases.py --slice N``: a deterministic, stratified per-task grading slice.

Unlike the five-rule tracked sample, the slice is experiment data under ``out/`` (a labeled
cohort to grade and score against RAGTruth's human spans). It must be reproducible from the
upstream files alone: lowest ids first, one response per source, half labeled / half clean."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ragtruth_cases", REPO / "scripts/ragtruth_cases.py")
rc = importlib.util.module_from_spec(_spec)
sys.modules["ragtruth_cases"] = rc
_spec.loader.exec_module(rc)


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
    picked = rc.select_slice(
        responses, sources, per_task=6
    )  # 3 labeled picks; the clean pool is empty
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
    # give the corpus a train split: mirror every test source as a distinct train source
    train_sources = {}
    extra = []
    rid = 1000
    for task in ("QA", "Summary", "Data2txt"):
        for i in range(4):
            sid = f"train-{task}-{i}"
            info = {"k": "v"} if task == "Data2txt" else f"train text {task} {i}"
            train_sources[sid] = {
                "source_id": sid,
                "task_type": task,
                "source_info": info,
                "prompt": "",
            }
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
    sources.update(train_sources)
    test_only = [
        r for r in responses if r["split"] == "test"
    ]  # drop the planted train copy of QA-0
    test_cases = [c for _, c in rc.select_slice(test_only, sources, per_task=4, natural=True)]
    rows = rc.build_calib_corpus(test_only + extra, sources, 4, test_cases)
    calib = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] == "test"]
    assert len(calib) == 12 and len(test) == 12
    assert {r["ragtruth"]["source_id"] for r in calib}.isdisjoint(
        {r["ragtruth"]["source_id"] for r in test}
    )
    assert all(r["ragtruth"]["source_id"].startswith("train-") for r in calib)
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
