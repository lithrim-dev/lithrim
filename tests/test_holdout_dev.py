"""HOLDOUT-DEV-1: the pin gate never reads the test cut.

Found 2026-09-10: both the CLI (the RAGTruth adapter's calibration corpus) and the shell's
split calibrate held out on the graded TEST cut, and the after round then graded that same
cut, so a gate decision (accept or refuse a demo set) was taken on test labels. The optimizer
corpus is now the calibration split alone: a deterministic, source-disjoint DEV slice (30% of
each task's sources) is carved from it for the gate to score on, the rest trains the demos,
and the test cut stays out of the corpus until the after round grades it.
"""

from __future__ import annotations

import pytest

from lithrim_bench.harness.calib_corpus import DEV_FRACTION, carve_dev


def _rows(n_per_task=10, tasks=("QA", "Summary", "Data2txt"), dup_source=None):
    rows = []
    for t in tasks:
        for i in range(n_per_task):
            rows.append(
                {"case_id": f"{t}-{i}", "split": "calibration", "task": t, "source": f"{t}-src-{i}"}
            )
    if dup_source:
        rows.append({"case_id": "dup", "split": "calibration", "task": "QA", "source": dup_source})
    return rows


def _carve(rows, **kw):
    return carve_dev(rows, source_of=lambda r: r["source"], group_of=lambda r: r["task"], **kw)


def test_the_fraction_is_thirty_percent_of_each_tasks_sources():
    assert DEV_FRACTION == 0.3
    out = _carve(_rows())
    for t in ("QA", "Summary", "Data2txt"):
        dev = [r for r in out if r["task"] == t and r["split"] == "dev"]
        train = [r for r in out if r["task"] == t and r["split"] == "calibration"]
        assert (len(dev), len(train)) == (3, 7)


def test_it_is_deterministic_and_independent_of_input_order():
    a = {r["case_id"] for r in _carve(_rows()) if r["split"] == "dev"}
    b = {r["case_id"] for r in _carve(list(reversed(_rows()))) if r["split"] == "dev"}
    assert a == b


def test_rows_sharing_a_source_land_on_the_same_side():
    out = _carve(_rows(dup_source="QA-src-0"))
    sides = {r["split"] for r in out if r["source"] == "QA-src-0"}
    assert len(sides) == 1
    train_sources = {r["source"] for r in out if r["split"] == "calibration"}
    dev_sources = {r["source"] for r in out if r["split"] == "dev"}
    assert train_sources.isdisjoint(dev_sources)


def test_it_only_relabels_and_leaves_other_rows_alone():
    rows = _rows(n_per_task=4) + [{"case_id": "t1", "split": "test", "task": "QA", "source": "x"}]
    out = _carve(rows)
    assert [r["case_id"] for r in out] == [r["case_id"] for r in rows], "order kept"
    assert next(r for r in out if r["case_id"] == "t1")["split"] == "test"
    assert rows[0]["split"] == "calibration", "inputs are not mutated"


def test_a_task_with_one_source_keeps_it_for_training_and_bad_fractions_are_refused():
    out = _carve(_rows(n_per_task=1))
    assert all(r["split"] == "calibration" for r in out)
    with pytest.raises(ValueError):
        _carve(_rows(), fraction=0)
    with pytest.raises(ValueError):
        _carve(_rows(), fraction=1)


# ── the RAGTruth adapter's corpus (CLI) ───────────────────────────────────────
def test_the_adapter_corpus_is_calibration_plus_dev_and_never_the_test_cut():
    from lithrim_bench.cli.adapters import load_adapter
    from tests.examples.test_ragtruth_adapter import _corpus, _train_rows

    rc = load_adapter("examples/ragtruth/adapter.py")
    responses, sources = _corpus()
    extra = _train_rows(sources, 10)
    test_only = [r for r in responses if r["split"] == "test"]
    test_cases = [c for _, c in rc.select_slice(test_only, sources, per_task=4, natural=True)]
    rows = rc.build_calib_corpus(test_only + extra, sources, 10, test_cases)
    assert {r["split"] for r in rows} == {"calibration", "dev"}
    assert not {r["case_id"] for r in rows} & {c["case_id"] for c in test_cases}
    for t in ("QA", "Summary", "Data2txt"):
        assert sum(1 for r in rows if r["ragtruth"]["task_type"] == t and r["split"] == "dev") == 3
    train = {r["ragtruth"]["source_id"] for r in rows if r["split"] == "calibration"}
    dev = {r["ragtruth"]["source_id"] for r in rows if r["split"] == "dev"}
    assert train.isdisjoint(dev) and all(s.startswith("train-") for s in train | dev)
    again = rc.build_calib_corpus(test_only + extra, sources, 10, test_cases)
    assert [(r["case_id"], r["split"]) for r in again] == [(r["case_id"], r["split"]) for r in rows]


# ── the optimizer and the CLI loop ───────────────────────────────────────────
def test_the_optimizer_never_holds_out_on_its_trainset(tmp_path):
    from lithrim_bench.runtime.council.judge_optimize import run_optimize

    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        '{"case_id": "a", "split": "calibration"}\n{"case_id": "b", "split": "dev"}\n'
    )
    with pytest.raises(ValueError, match="held-out split"):
        run_optimize(
            "risk_judge",
            corpus_path=corpus,
            confirm_cost=True,
            out_dir=tmp_path,
            heldout_split="calibration",
        )


def test_the_cli_holds_out_on_dev_when_the_corpus_has_it_and_keeps_it_in_an_enriched_round():
    from lithrim_bench.cli import loop as rc

    assert rc.heldout_split_for([{"split": "calibration"}, {"split": "dev"}]) == "dev"
    assert rc.heldout_split_for([{"split": "calibration"}, {"split": "test"}]) == "test"
    rows = [
        {"case_id": "c5", "split": "calibration"},
        {"case_id": "c1", "split": "calibration"},
        {"case_id": "d1", "split": "dev"},
    ]
    assert rc.build_enriched_corpus(rows, {"c5"}) == [rows[0], rows[2]]
