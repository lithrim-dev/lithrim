"""Offline tests for the DSPy judge-optimizer loop (WS-6c-DSPy-3b).

All $0 and deterministic. The projection / eval-Δ / demo-binding / corpus-filter
tests run on the DEFAULT pydantic+pandas core (no ``dspy``, no ``openai``, no
network): ``judge_optimize`` is import-safe there (every council/dspy symbol is
lazy), and these tests exercise only the pure seams (a fake predictor stands in for
the live ``dspy.Predict``). The one live test is env-gated and skips $0 by default.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from lithrim_bench.runtime.council.judge_metric import LENS_BY_ROLE
from lithrim_bench.runtime.council.judge_optimize import (
    _demo_raises,
    _example_fields,
    _example_raises_in_lens,
    bind_compiled_demos,
    evaluate_program,
    load_corpus,
    order_positive_first,
    role_relevant,
    run_optimize,
)

CORPUS = Path(__file__).resolve().parents[4] / "examples" / "judge_calib_v1.jsonl"


# --------------------------------------------------------------------------- #
# offline projection ($0, no dspy)
# --------------------------------------------------------------------------- #
def test_example_fields_projects_row_to_signature_inputs():
    row = {
        "transcript": "T",
        "artifacts": [{"content": "A1"}, {"content": "A2"}],
        "expected_safety_flags": ["WRONG_DOSAGE"],
    }
    fields = _example_fields(row, role_prompt="RP", taxonomy_context="TC")
    assert fields["transcript"] == "T"
    assert fields["artifact"] == "A1\n\nA2"  # _artifact_text join
    assert fields["role_key_questions"] == "RP"
    assert fields["taxonomy_context"] == "TC"
    assert fields["expected_safety_flags"] == ["WRONG_DOSAGE"]


@pytest.mark.skipif(
    not CORPUS.exists(),
    reason="PACK-DIST-1: judge_calib corpus relocated to the external lithrim-pack-healthcare repo",
)
def test_load_corpus_and_lens_filter_match_widened_split():
    # UAP-4/S-BS-49: the corpus widened 47→83 (+36 positives, all pinned to the
    # calibration/trainset split). The `test` held-out split is FROZEN at the v1 30
    # cases (driver "go" #2) so both optimize arms measure on the IDENTICAL test set.
    rows = load_corpus(CORPUS)
    cal = load_corpus(CORPUS, split="calibration")
    test = load_corpus(CORPUS, split="test")
    assert len(rows) == 83
    assert len(cal) == 53
    assert len(test) == 30  # FROZEN — widening never touches the held-out split

    lens = LENS_BY_ROLE["risk_judge"]
    train = [r for r in cal if role_relevant(r, lens)]
    heldout = [r for r in test if role_relevant(r, lens)]
    # the D4 lens-filter: in-lens label OR clean negative; other-lens-only dropped.
    # train grew (12→24) with the widened positives; heldout is UNCHANGED (10) — the
    # proof the held-out measurement can't be a test-set artifact.
    assert len(train) == 24
    assert len(heldout) == 10


def test_role_relevant_drops_other_lens_only_keeps_clean():
    lens = LENS_BY_ROLE["risk_judge"]
    assert role_relevant({"expected_safety_flags": ["WRONG_DOSAGE"]}, lens) is True
    assert role_relevant({"expected_safety_flags": []}, lens) is True  # clean negative
    # FABRICATED_CONSENT is policy's; not in risk lens, not clean -> dropped
    assert role_relevant({"expected_safety_flags": ["FABRICATED_CONSENT"]}, lens) is False


# --------------------------------------------------------------------------- #
# coverage-aware demo selection ($0, pure) — S-BS-49 (judge_metric FROZEN)
# --------------------------------------------------------------------------- #
def test_example_raises_in_lens_distinguishes_positive_from_clean_and_other_lens():
    lens = LENS_BY_ROLE["risk_judge"]
    assert _example_raises_in_lens({"expected_safety_flags": ["WRONG_DOSAGE"]}, lens) is True
    assert _example_raises_in_lens({"expected_safety_flags": []}, lens) is False  # clean
    # policy's code is out of risk's lens -> not a risk positive exemplar
    assert _example_raises_in_lens({"expected_safety_flags": ["FABRICATED_CONSENT"]}, lens) is False


def test_order_positive_first_surfaces_positives_preserving_order():
    lens = LENS_BY_ROLE["risk_judge"]
    clean_a = {"case_id": "ca", "expected_safety_flags": []}
    clean_b = {"case_id": "cb", "expected_safety_flags": []}
    pos_1 = {"case_id": "p1", "expected_safety_flags": ["WRONG_DOSAGE"]}
    pos_2 = {"case_id": "p2", "expected_safety_flags": ["MISSED_ESCALATION"]}
    # positives interspersed AFTER cleans — the S-BS-49 pathology (silent cases fill
    # the demo slots first). order_positive_first puts every in-lens positive first.
    ordered = order_positive_first([clean_a, pos_1, clean_b, pos_2], lens=lens)
    assert [r["case_id"] for r in ordered] == ["p1", "p2", "ca", "cb"]
    # relative order WITHIN each group is preserved (deterministic, stable)
    assert [r["case_id"] for r in order_positive_first([pos_2, pos_1], lens=lens)] == ["p2", "p1"]


@pytest.mark.skipif(
    not CORPUS.exists(),
    reason="PACK-DIST-1: judge_calib corpus relocated to the external lithrim-pack-healthcare repo",
)
def test_order_positive_first_on_the_corpus_has_positives_to_surface():
    # the widened calibration split actually carries in-lens positives for the
    # default optimize role, so coverage-aware selection has something to surface.
    lens = LENS_BY_ROLE["risk_judge"]
    cal = [r for r in load_corpus(CORPUS, split="calibration") if role_relevant(r, lens)]
    ordered = order_positive_first(cal, lens=lens)
    n_pos = sum(1 for r in cal if _example_raises_in_lens(r, lens))
    assert n_pos >= 1
    # the first n_pos rows are exactly the in-lens positives
    assert all(_example_raises_in_lens(r, lens) for r in ordered[:n_pos])
    assert not any(_example_raises_in_lens(r, lens) for r in ordered[n_pos:])


def test_demo_raises_detects_non_silent_exemplar():
    assert _demo_raises({"findings": [{"taxonomy_code": "WRONG_DOSAGE"}]}) is True
    assert _demo_raises({"findings": []}) is False
    assert _demo_raises(SimpleNamespace(findings=[{"taxonomy_code": "X"}])) is True
    assert _demo_raises(SimpleNamespace(findings=[])) is False


# --------------------------------------------------------------------------- #
# offline eval-Δ ($0, fake predictors) — the Δ-measurement logic is correct
# --------------------------------------------------------------------------- #
class _FakeProgram:
    """Stands in for a JudgeProgram: maps a case transcript to the codes it raises,
    returning the ``findings``-bearing prediction ``score_judge`` reads."""

    def __init__(self, by_transcript: dict[str, list[str]]) -> None:
        self.by_transcript = by_transcript

    def forward(self, transcript, artifact, role_key_questions, taxonomy_context):
        codes = self.by_transcript.get(transcript, [])
        findings = [{"taxonomy_code": c, "evidence_spans": [{"quote": "q"}]} for c in codes]
        return SimpleNamespace(findings=findings)

    # evaluate_program calls program(...) (so a dspy.Module resolves its ambient LM);
    # a fake stands in as a plain callable.
    __call__ = forward


def test_evaluate_program_measures_compiled_better_than_baseline():
    pos = {
        "case_id": "pos",
        "transcript": "pos-tx",
        "artifacts": [{"content": "a"}],
        "expected_safety_flags": ["WRONG_DOSAGE"],
    }
    clean = {
        "case_id": "clean",
        "transcript": "clean-tx",
        "artifacts": [{"content": "b"}],
        "expected_safety_flags": [],
    }
    cases = [pos, clean]

    # baseline over-fires an in-lens code (SEVERITY_ESCALATION) on the positive case;
    # compiled raises exactly the in-lens label and stays silent on the clean.
    baseline = _FakeProgram({"pos-tx": ["WRONG_DOSAGE", "SEVERITY_ESCALATION"], "clean-tx": []})
    compiled = _FakeProgram({"pos-tx": ["WRONG_DOSAGE"], "clean-tx": []})

    base_score = evaluate_program(
        baseline, cases, role="risk_judge", role_prompt="rp", taxonomy_context="tc"
    )
    opt_score = evaluate_program(
        compiled, cases, role="risk_judge", role_prompt="rp", taxonomy_context="tc"
    )

    assert base_score["precision"] < opt_score["precision"]
    assert base_score["graded"] < opt_score["graded"]
    assert opt_score["accepted"] is True
    assert base_score["accepted"] is False
    # an in-lens over-fire is a genuine FP — co_raise_aware does not rescue it
    assert base_score["fp"] == 1 and opt_score["fp"] == 0


# --------------------------------------------------------------------------- #
# offline demo-binding ($0, stubs) — the loop's closing move
# --------------------------------------------------------------------------- #
def test_bind_compiled_demos_copies_onto_judge():
    program = SimpleNamespace(predict=SimpleNamespace(demos=["d1", "d2"]))
    judge = SimpleNamespace(predict=SimpleNamespace(demos=[]))

    out = bind_compiled_demos(judge, program)

    assert out is judge
    assert judge.predict.demos == ["d1", "d2"]
    # an independent copy: mutating the program's demos later must not leak in
    program.predict.demos.append("d3")
    assert judge.predict.demos == ["d1", "d2"]


# --------------------------------------------------------------------------- #
# cost gate ($0) — refuses paid work without confirm_cost
# --------------------------------------------------------------------------- #
def test_run_optimize_refuses_without_confirm_cost(tmp_path):
    with pytest.raises(RuntimeError):
        run_optimize("risk_judge", corpus_path=CORPUS, out_dir=tmp_path)


# --------------------------------------------------------------------------- #
# holdout hygiene ($0, REL-OPS-1 O6 / docs/POLICY_HOLDOUT_HYGIENE.md) — the
# optimization entry point refuses a CERTIFY-ONLY corpus (no `calibration` rows):
# the held-out `test` split may certify a judge, never tune it. The refusal must
# fire BEFORE any paid work (no dspy import, no LM construction).
# --------------------------------------------------------------------------- #
def test_run_optimize_refuses_certify_only_corpus(tmp_path):
    corpus = tmp_path / "certify_only.jsonl"
    rows = [
        {
            "case_id": f"held_out_{i}",
            "split": "test",
            "transcript": "T",
            "artifacts": [{"content": "A"}],
            "expected_safety_flags": ["WRONG_DOSAGE"],
        }
        for i in range(3)
    ]
    corpus.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="certify-only"):
        run_optimize("risk_judge", corpus_path=corpus, confirm_cost=True, out_dir=tmp_path)


# --------------------------------------------------------------------------- #
# live compile/eval — env-gated, skips $0 by default (same gate as test_live_smoke)
# --------------------------------------------------------------------------- #
_REQUIRED = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT_COUNCIL")
_AZURE_READY = os.environ.get("LITHRIM_LLM_PROVIDER") == "azure" and all(
    os.environ.get(k) for k in _REQUIRED
)


@pytest.mark.skipif(
    not _AZURE_READY,
    reason="live optimizer: set LITHRIM_LLM_PROVIDER=azure + AZURE_OPENAI_* (separate cost-go)",
)
def test_live_compile_and_eval_shape(tmp_path):
    pytest.importorskip("dspy")
    pytest.importorskip("openai")
    result = run_optimize(
        "risk_judge", corpus_path=CORPUS, confirm_cost=True, out_dir=tmp_path, limit=2
    )
    assert {"role", "n_train", "n_heldout", "baseline", "optimized", "delta"} <= set(result)
    for arm in ("baseline", "optimized"):
        for key in ("accepted", "graded", "precision", "recall", "tp", "fp", "fn", "n"):
            assert key in result[arm]
    assert result["compile_config"]["co_raise_aware"] is True
    assert result["compile_config"]["max_labeled_demos"] == 0
