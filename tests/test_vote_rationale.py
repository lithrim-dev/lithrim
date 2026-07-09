"""F8-RATIONALE — a verdict-only reviewer's "why" reaches the vote's read surface.

The gap (live, 2026-07-04, the repro workspace's composo runs): a reward-model reviewer emits a
verdict + a prose explanation but NO coded findings, so ``_synth_reason`` (which reconstructs a
reason from finding codes) has nothing to build from and the stored ``JudgeVote.reason`` came out
EMPTY — the one reviewer whose only articulation is prose was the one rendered mute. The fix is
the same seam-enrichment shape as ``_fold_usage``/``sampling``: fold the captured
``JudgeResult.rationale`` onto the per-judge seam dict, ONLY for a findings-less judge — a coded
judge's synthesized reason stays byte-identical, and nothing is ever fabricated (no rationale →
the dict is untouched). ``stages._judge_votes_from_models`` already prefers ``rationale`` over the
synth, and the BFF council view + VerdictCard already project/render ``reason`` — so the fold is
the whole fix. $0/offline."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("openai")  # `stages` -> compliance_council imports openai at module load

from lithrim_bench.runtime.council.authored_stage import _fold_rationale  # noqa: E402
from lithrim_bench.runtime.council.sampling import JudgeResult  # noqa: E402
from lithrim_bench.runtime.pipeline.stages import _judge_votes_from_models  # noqa: E402


def _jr(rationale: str) -> JudgeResult:
    return JudgeResult(
        score_mean=0.4, score_variance=0.0, scores_raw=[0.4], k=1,
        rationale=rationale, decision="reject", findings=[],
    )


def test_fold_rationale_fills_a_findings_less_seam_dict():
    r = {"model": "reviewer_composo", "decision": "reject", "findings": []}
    _fold_rationale(r, _jr("the note omits the occupational history the patient stated"))
    assert r["rationale"] == "the note omits the occupational history the patient stated"


def test_fold_rationale_never_touches_a_coded_judge():
    # a judge WITH findings keeps its synthesized "decision — CODES" reason byte-identical
    r = {"model": "reviewer_gpt41", "decision": "reject",
         "findings": [{"taxonomy_code": "HISTORY_OMISSION"}]}
    _fold_rationale(r, _jr("some prose"))
    assert "rationale" not in r


def test_fold_rationale_never_fabricates_or_clobbers():
    r = {"model": "reviewer_composo", "decision": "reject", "findings": []}
    _fold_rationale(r, _jr(""))  # no rationale captured → untouched
    assert "rationale" not in r
    r2 = {"model": "reviewer_composo", "decision": "reject", "findings": [],
          "rationale": "already here"}
    _fold_rationale(r2, _jr("newer prose"))
    assert r2["rationale"] == "already here"
    r3 = {"model": "reviewer_composo", "decision": "reject", "findings": []}
    _fold_rationale(r3, None)  # no JudgeResult captured (offline predictor) → untouched
    assert "rationale" not in r3


def test_vote_reason_is_the_folded_rationale():
    votes = _judge_votes_from_models([
        {"model": "reviewer_composo", "decision": "reject", "findings": [],
         "rationale": "the dissent was erased", "llm_model": "composo-reward"},
        {"model": "reviewer_gpt41", "decision": "reject",
         "findings": [{"taxonomy_code": "DISSENT_ERASURE"}]},
    ])
    assert votes[0].reason == "the dissent was erased"
    assert votes[1].reason == "reject — DISSENT_ERASURE"  # the synth path, unchanged
