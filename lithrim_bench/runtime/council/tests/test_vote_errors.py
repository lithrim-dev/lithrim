"""VOTE-ERRORS — a failed judge call persists as a failed vote, never a considered one.

``Judge.forward`` (frozen) already emits ``errors: [...]`` on a predictor/model failure, but
the persisted vote record (``_judge_votes_from_models`` → ``JudgeVote`` →
``stage_results.semantic.judge_votes`` → the BFF council.votes / run-audit projections)
DROPPED it — a judge failing 100% of calls rendered as a considered WARN under the
configured model's name. These pin: (a) the error string rides the persisted vote and the
errored vote is never identical to a considered one; (b) a clean vote carries an empty
``errors``; (c) ``JudgeVote.model`` reflects the LM actually bound (the seam's
``llm_model``, stamped from the constructed LM in ``build_trio``) over roster/config
metadata. The frozen seam is untouched: only the projection above it changes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

pytest.importorskip("dspy", reason="the judge seam lives with the [council]/[verification] extras")

from lithrim_bench.runtime.council.judges_dspy import Judge  # noqa: E402
from lithrim_bench.runtime.pipeline.stages import _judge_votes_from_models  # noqa: E402


def _boom(**kw):
    raise RuntimeError("boom")


def _considered(**kw):
    return SimpleNamespace(decision="needs_review", findings=[])


def test_erroring_judge_persists_the_error_and_never_reads_as_considered():
    errored = Judge("risk_judge", predictor=_boom, taxonomy_context="ctx").forward(
        transcript="t", artifact="a"
    )
    considered = Judge("risk_judge", predictor=_considered, taxonomy_context="ctx").forward(
        transcript="t", artifact="a"
    )
    assert errored["errors"] == ["RuntimeError: boom"]  # the frozen seam already carries it
    votes = _judge_votes_from_models([errored, considered], model_lookup={})
    assert votes[0].errors == ["RuntimeError: boom"]
    assert votes[1].errors == []
    assert votes[0].model_dump() != votes[1].model_dump()


def test_clean_vote_serializes_with_empty_errors():
    seam = [{"model": "policy_judge", "decision": "approve", "confidence": 0.9, "findings": []}]
    vote = _judge_votes_from_models(seam, model_lookup={})[0]
    assert vote.errors == []
    assert vote.model_dump()["errors"] == []


def test_vote_model_reflects_the_bound_lm_over_config_metadata():
    seam = [{"model": "risk_judge", "llm_model": "azure/gpt-4.1-ACTUAL",
             "decision": "approve", "confidence": 0.9, "findings": [], "errors": []}]
    votes = _judge_votes_from_models(seam, model_lookup={"risk_judge": "config/METADATA"})
    assert votes[0].model == "azure/gpt-4.1-ACTUAL"
