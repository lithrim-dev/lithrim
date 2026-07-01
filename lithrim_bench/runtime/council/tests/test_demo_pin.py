"""DEMO-PIN-1 (S-BS-48) — pin an optimized judge's compiled demos into the live grade.

The DSPy optimizer writes ``compiled_demos_<tag>_<role>.json`` and measures the held-out Δ,
but nothing bound the demos back into grading (the ``bind_compiled_demos`` docstring flagged
this as the deferred production-behavior cycle). These pin tests wire it: a workspace that has
a compiled-demos file for a roster role grades with those demos in the judge's ``dspy.Predict``.

The demos ride the LIVE sampling path (``judge_call`` builds the ``dspy.Predict`` lazily), NOT
``judge.predict`` (a closure under the sampling layer), so the wire is:
  load_compiled_demos → build_trio(demos=) → live-predictor closure → judge_call(demos=) → predict.demos
"""

from __future__ import annotations

import json
import types

import pytest


# ── the load layer (deserialize + discover) ──────────────────────────────────────────────
def test_deserialize_demos_roundtrip(tmp_path):
    dspy = pytest.importorskip("dspy")
    from lithrim_bench.runtime.council.judge_optimize import deserialize_demos

    rows = [
        {
            "augmented": True,
            "transcript": "Doctor: ...",
            "artifact": "S: ...\nPMH:\n  - X",
            "role_key_questions": "raise Y when...",
            "taxonomy_context": "codes: ...",
            "decision": "reject",
            "findings": [{"taxonomy_code": "FABRICATED_CLAIM"}],
            "reason": "because",
        }
    ]
    demos = deserialize_demos(rows)
    assert len(demos) == 1
    ex = demos[0]
    assert isinstance(ex, dspy.Example)
    assert ex.transcript == "Doctor: ..."
    assert ex.decision == "reject"
    # the judge signature's INPUT fields are marked as inputs (so few-shot formats correctly)
    assert set(ex.inputs().keys()) == {
        "transcript",
        "artifact",
        "role_key_questions",
        "taxonomy_context",
    }


def test_load_compiled_demos_discovers_latest(tmp_path):
    pytest.importorskip("dspy")
    from lithrim_bench.runtime.council.judge_optimize import load_compiled_demos

    # absent → None (a workspace with no optimized judge grades byte-identically to before)
    assert load_compiled_demos(tmp_path, "faithfulness_judge") is None

    row = {
        "transcript": "t", "artifact": "a", "role_key_questions": "q",
        "taxonomy_context": "c", "decision": "approve", "findings": [], "reason": "",
    }
    (tmp_path / "compiled_demos_dspy3b_faithfulness_judge.json").write_text(json.dumps([row]))
    demos = load_compiled_demos(tmp_path, "faithfulness_judge")
    assert demos is not None and len(demos) == 1
    # a DIFFERENT role is unaffected (no cross-role leak)
    assert load_compiled_demos(tmp_path, "policy_judge") is None


# ── the application point: judge_call binds demos onto the predict it uses ─────────────────
def test_judge_call_binds_demos_onto_predict():
    from lithrim_bench.runtime.council.sampling import judge_call

    class StubPredict:
        def __init__(self):
            self.demos = None
            self.lm = None

        def __call__(self, **kw):
            return types.SimpleNamespace(decision="reject", findings=[], reason="ok")

    stub = StubPredict()
    sentinel = ["DEMO_A", "DEMO_B"]
    res = judge_call("transcript", model=None, k=1, predict=stub, demos=sentinel)
    assert stub.demos == sentinel  # the compiled demos are now on the judge's predictor
    assert res.decision == "reject"  # and the call still returns a normal JudgeResult


def test_judge_call_no_demos_is_backcompat():
    from lithrim_bench.runtime.council.sampling import judge_call

    class StubPredict:
        def __init__(self):
            self.demos = "UNTOUCHED"
            self.lm = None

        def __call__(self, **kw):
            return types.SimpleNamespace(decision="approve", findings=[], reason="")

    stub = StubPredict()
    judge_call("t", model=None, k=1, predict=stub)  # no demos kwarg
    assert stub.demos == "UNTOUCHED"  # absent demos never touches the predictor


# ── the threading: build_trio passes per-role demos to the live predictor ──────────────────
def test_build_trio_threads_demos_to_judge_call(monkeypatch):
    import lithrim_bench.runtime.council.judges_dspy as jd
    from lithrim_bench.runtime.council.sampling import JudgeResult

    monkeypatch.setattr(jd, "build_judge_lm", lambda role, **kw: types.SimpleNamespace(model="fake"))

    captured: dict = {}

    def fake_judge_call(prompt, **kw):
        captured.update(kw)
        return JudgeResult(
            score_mean=0.0, score_variance=0.0, scores_raw=[0.0], k=1,
            rationale="", decision="approve", findings=[], _raw_response=None,
        )

    # build_trio does `from .sampling import judge_call` at call time → patch the source symbol.
    monkeypatch.setattr("lithrim_bench.runtime.council.sampling.judge_call", fake_judge_call)

    sentinel = ["EX1"]
    trio = jd.build_trio(roles=["faithfulness_judge"], demos={"faithfulness_judge": sentinel})
    trio[0].forward(transcript="t", artifact="a")
    assert captured.get("demos") == sentinel


def test_build_trio_demos_backcompat_no_kwarg(monkeypatch):
    """A trio built with no demos passes demos=None — byte-compatible with pre-pin grading."""
    import lithrim_bench.runtime.council.judges_dspy as jd
    from lithrim_bench.runtime.council.sampling import JudgeResult

    monkeypatch.setattr(jd, "build_judge_lm", lambda role, **kw: types.SimpleNamespace(model="fake"))
    captured: dict = {}

    def fake_judge_call(prompt, **kw):
        captured.update(kw)
        return JudgeResult(
            score_mean=0.0, score_variance=0.0, scores_raw=[0.0], k=1,
            rationale="", decision="approve", findings=[], _raw_response=None,
        )

    monkeypatch.setattr("lithrim_bench.runtime.council.sampling.judge_call", fake_judge_call)
    trio = jd.build_trio(roles=["faithfulness_judge"])
    trio[0].forward(transcript="t", artifact="a")
    assert captured.get("demos") is None
