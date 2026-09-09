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
