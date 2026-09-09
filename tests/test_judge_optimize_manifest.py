"""PROVENANCE-1: an optimize result carries what a reader needs to prove it was clean.

Observed 2026-09-09: a peer reviewer had to reconstruct, by matching demo text against corpus
files, whether the four compiled demos came from the train split. The result file must say."""

from __future__ import annotations

import json

from lithrim_bench.runtime.council import judge_optimize as jo


def _row(cid: str, source: str, artifact: str) -> dict:
    return {
        "case_id": cid,
        "transcript": "src",
        "artifacts": [{"type": "generated_response", "content": artifact}],
        "expected_safety_flags": [],
        "ragtruth": {"source_id": source, "task_type": "QA"},
    }


def test_manifest_records_splits_hashes_and_demo_provenance(tmp_path):
    train = [_row("t1", "s1", "alpha"), _row("t2", "s2", "beta")]
    heldout = [_row("h1", "s9", "gamma")]
    corpus = tmp_path / "calib.jsonl"
    corpus.write_text("\n".join(json.dumps(r) for r in train + heldout) + "\n")
    demos = [{"artifact": "beta", "findings": [{"taxonomy_code": "X"}]}]
    m = jo.build_manifest(
        role="ragtruth_detector",
        corpus_path=corpus,
        train_rows=train,
        heldout_rows=heldout,
        role_prompt="the prompt",
        model="azure/gpt-4.1-2025-04-14",
        demos=demos,
    )
    assert m["train_case_ids"] == ["t1", "t2"] and m["heldout_case_ids"] == ["h1"]
    assert m["train_source_ids"] == ["s1", "s2"] and m["heldout_source_ids"] == ["s9"]
    assert m["corpus_sha256"] == jo._sha256_file(corpus) and len(m["corpus_sha256"]) == 64
    assert m["role_prompt_sha256"] == jo._sha256_text("the prompt")
    assert m["model"] == "azure/gpt-4.1-2025-04-14"
    assert m["demo_source_ids"] == ["t2"] and m["demos_out_of_sample"] is True


def test_a_demo_from_outside_the_trainset_is_reported_not_guessed(tmp_path):
    train = [_row("t1", "s1", "alpha")]
    corpus = tmp_path / "calib.jsonl"
    corpus.write_text(json.dumps(train[0]) + "\n")
    demos = [{"artifact": "gamma (held-out text)", "findings": []}]
    m = jo.build_manifest(
        role="r",
        corpus_path=corpus,
        train_rows=train,
        heldout_rows=[],
        role_prompt="p",
        model=None,
        demos=demos,
    )
    assert m["demo_source_ids"] == [None] and m["demos_out_of_sample"] is False
