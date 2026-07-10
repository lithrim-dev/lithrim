"""The sampling layer (`judge_call`) — the single primitive every live judge routes
through. All offline / $0: an injected fake ``predict`` + synthesized response payloads
(the dict shape ``extract_verdict_confidence`` accepts), so no network and no LM.

Covers: k=1 byte-equivalence to the pre-sampling ``Judge.forward`` path; k>1
mean/variance over multiple completions; the BYO-Claude (no native n) clamp + log; an
honest None confidence when the representative completion carries no logprobs; the k>1
cache bypass; the frozen seam staying frozen; and the distribution surfacing as
provenance telemetry through the authored evaluator.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

# judge_call lazily imports dspy + (via judges_dspy) compliance_council (openai/tenacity).
pytest.importorskip("dspy")
pytest.importorskip("openai")
pytest.importorskip("tenacity")

from lithrim_bench.runtime.council.compliance_council import KNOWN_TAXONOMY_CODES  # noqa: E402
from lithrim_bench.runtime.council.judges_dspy import Judge  # noqa: E402
from lithrim_bench.runtime.council.sampling import (  # noqa: E402
    JudgeResult,
    _is_single_completion_lm,
    judge_call,
)

_REPO = Path(__file__).resolve().parents[4]
# A code valid under WHATEVER pack is active, so _validate_findings keeps it (the
# council un-froze its taxonomy per-pack; hardcoding a healthcare code would drop on _core).
_VALID_CODE = sorted(KNOWN_TAXONOMY_CODES)[0]


def _raw_for_conf(conf):
    """A synthesized chat-completion carrying (or lacking) the verdict-token logprob —
    the same shape ``extract_verdict_confidence`` reads. ``None`` => no logprobs."""
    if conf is None:
        return {"choices": [{"logprobs": None}]}
    lp = math.log(conf) if 0 < conf <= 1 else 0.0
    return {"choices": [{"logprobs": {"content": [{"token": "reject", "logprob": lp}]}}]}


def _single_pred(decision, *, findings=None, reason="", conf=0.9):
    """A fake k=1 predict: returns one prediction with an attached _raw_response."""
    raw = _raw_for_conf(conf)

    def _predict(**_kw):
        return SimpleNamespace(
            decision=decision, findings=findings or [], reason=reason, _raw_response=raw
        )

    return _predict


def _multi_pred(decisions, *, findings_by_choice=None, reasons=None, record=None):
    """A fake k>1 predict: returns a prediction whose ``.completions`` is a list of
    per-choice predictions. ``record`` (a dict) captures the received ``config``."""

    def _predict(**kw):
        if record is not None:
            record["config"] = kw.get("config")
        comps = []
        for i, d in enumerate(decisions):
            comps.append(
                SimpleNamespace(
                    decision=d,
                    findings=(findings_by_choice or {}).get(i, []),
                    reason=(reasons or {}).get(i, ""),
                )
            )
        return SimpleNamespace(completions=comps)

    return _predict


def _lm_with_response(choices, *, model="azure/gpt-4.1"):
    """A fake bound LM exposing ``.history[-1]['response'].choices`` for the k>1 path."""
    resp = SimpleNamespace(choices=choices, model=model, usage=None)
    return SimpleNamespace(model=model, history=[{"response": resp}])


def _choice_with_logprob(conf):
    """A response choice carrying (or lacking) a verdict-token logprob."""
    if conf is None:
        return SimpleNamespace(logprobs=None)
    lp = math.log(conf)
    return SimpleNamespace(
        logprobs=SimpleNamespace(content=[SimpleNamespace(token="reject", logprob=lp)])
    )


# ── 1. k=1 byte-equivalence ────────────────────────────────────────────────
def test_k1_is_byte_equivalent_to_the_raw_predictor_path():
    """At k=1, routing through judge_call then Judge.forward yields the IDENTICAL seam
    dict as feeding the raw predictor straight to Judge.forward — and a degenerate
    distribution (one score, zero variance)."""
    findings = [{"taxonomy_code": _VALID_CODE, "evidence_spans": [{"quote": "q", "turn_ids": [1]}]}]

    jr = judge_call(
        "t", model=None, k=1, predict=_single_pred("reject", findings=findings, reason="r", conf=0.92)
    )
    assert jr.k == 1
    assert jr.scores_raw == [0.0]
    assert jr.score_mean == 0.0
    assert jr.score_variance == 0.0
    assert jr.decision == "reject"

    # The JudgeResult IS the predictor return for the frozen Judge.forward.
    seam_sampled = Judge("risk_judge", predictor=lambda **kw: jr).forward(transcript="t", artifact="a")
    # The raw path: the same underlying prediction fed straight to Judge.forward.
    seam_raw = Judge(
        "risk_judge", predictor=_single_pred("reject", findings=findings, reason="r", conf=0.92)
    ).forward(transcript="t", artifact="a")

    assert seam_sampled == seam_raw
    assert seam_sampled == {
        "model": "risk_judge",
        "decision": "reject",
        "confidence": 0.92,
        "findings": findings,
        "errors": [],
    }


# ── 2. k>1 mean / variance + modal representative ───────────────────────────
def test_k_gt_1_mean_variance_and_modal_representative():
    """Three completions [approve, approve, reject] → scores [1,1,0]; population
    mean 2/3, variance 2/9; modal=approve picks the first approve completion's
    findings/rationale; representative confidence read from that choice's logprobs."""
    rep_findings = [{"taxonomy_code": _VALID_CODE, "evidence_spans": [{"quote": "z", "turn_ids": [2]}]}]
    lm = _lm_with_response(
        [_choice_with_logprob(0.8), _choice_with_logprob(0.7), _choice_with_logprob(0.6)]
    )
    predict = _multi_pred(
        ["approve", "approve", "reject"],
        findings_by_choice={0: rep_findings},
        reasons={0: "because approve-0", 2: "because reject"},
    )

    jr = judge_call("t", model=lm, k=3, predict=predict)
    assert jr.k == 3
    assert jr.scores_raw == [1.0, 1.0, 0.0]
    assert jr.score_mean == pytest.approx(2 / 3)
    assert jr.score_variance == pytest.approx(2 / 9)
    assert jr.decision == "approve"
    assert jr.rationale == "because approve-0"
    assert jr.findings == rep_findings

    # The representative confidence flows through Judge.forward from choices[0] (0.8).
    seam = Judge("risk_judge", predictor=lambda **kw: jr).forward(transcript="t", artifact="a")
    assert seam["decision"] == "approve"
    assert seam["confidence"] == pytest.approx(0.8)


# ── 3. BYO-Claude (no native n) clamps to k=1 + logs the downgrade ──────────
def test_byo_claude_clamps_to_k1_and_logs(caplog):
    assert _is_single_completion_lm(SimpleNamespace(model="byo-claude")) is True
    assert _is_single_completion_lm(SimpleNamespace(model="claude-cli")) is True
    assert _is_single_completion_lm(SimpleNamespace(model="azure/gpt-4.1")) is False
    assert _is_single_completion_lm(SimpleNamespace(supports_n=False)) is True

    lm = SimpleNamespace(model="byo-claude")
    with caplog.at_level(logging.INFO, logger="lithrim_bench.runtime.council.sampling"):
        jr = judge_call("t", model=lm, k=4, predict=_single_pred("approve", conf=None))
    assert jr.k == 1
    assert jr.scores_raw == [1.0]
    assert any("clamping k=4 -> 1" in r.getMessage() for r in caplog.records)


# ── 4. representative completion with no logprobs → honest None confidence ───
def test_representative_without_logprobs_yields_none_confidence():
    lm = _lm_with_response([_choice_with_logprob(None), _choice_with_logprob(None)])
    jr = judge_call("t", model=lm, k=2, predict=_multi_pred(["approve", "reject"]))
    assert jr.k == 2
    seam = Judge("risk_judge", predictor=lambda **kw: jr).forward(transcript="t", artifact="a")
    assert seam["confidence"] is None  # never coerced


# ── 5. the frozen seam stays frozen after the refactor ──────────────────────
def test_frozen_seam_still_green():
    import tests._seam_freeze as sf

    sf.assert_judges_dspy_consensus_seam_frozen(_REPO)
    sf.assert_compliance_council_carveouts_only(_REPO)


# ── 6. k>1 bypasses the dspy cache (the live-grade cache trap) + sampling temperature ──
def test_k_gt_1_passes_cache_false_and_default_temperature():
    from lithrim_bench.runtime.council.sampling import DEFAULT_SAMPLE_TEMPERATURE

    record: dict = {}
    lm = _lm_with_response([_choice_with_logprob(0.9), _choice_with_logprob(0.9)])
    judge_call("t", model=lm, k=2, predict=_multi_pred(["approve", "approve"], record=record))
    assert record["config"]["n"] == 2
    assert record["config"]["cache"] is False
    # explicit sampling temperature (the 1.0 default) — never DSPy's hidden bump, never silently 0.
    assert record["config"]["temperature"] == DEFAULT_SAMPLE_TEMPERATURE == 1.0


def test_k_gt_1_explicit_temperature_is_passed_through():
    record: dict = {}
    lm = _lm_with_response([_choice_with_logprob(0.9), _choice_with_logprob(0.9)])
    judge_call("t", model=lm, k=2, temperature=0.7, predict=_multi_pred(["approve", "approve"], record=record))
    assert record["config"]["temperature"] == 0.7


def test_k1_passes_no_config():
    """k=1 passes NO config (so temperature/cache stay the LM's defaults — the
    byte-equivalence guarantee)."""
    seen = {}

    def _predict(**kw):
        seen["config_present"] = "config" in kw
        return SimpleNamespace(decision="approve", findings=[], reason="", _raw_response=_raw_for_conf(0.9))

    judge_call("t", model=None, k=1, predict=_predict)
    assert seen["config_present"] is False


# ── 7. the distribution surfaces as authored-evaluator telemetry ────────────
def test_authored_evaluator_carries_sampling_telemetry():
    from lithrim_bench.harness.pack import pack_production_judges
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator

    roles = list(pack_production_judges())
    block = JudgeResult(
        score_mean=0.5, score_variance=0.25, scores_raw=[0.0, 1.0], k=2,
        rationale="r", decision="needs_review", findings=[], _raw_response=None,
    )
    predictors = {r: (lambda **kw: block) for r in roles}

    evaluator = build_authored_evaluator(
        ontology=None, assignments=None, predictors=predictors, apply_gate=False
    )
    out = evaluator({"call_context": {"transcript": "t"}, "artifacts": [{"content": "a"}]})

    models = out["models"]
    assert models, "expected at least one per-judge seam dict"
    for m in models:
        assert m["sampling"] == {
            "score_mean": 0.5,
            "score_variance": 0.25,
            "scores_raw": [0.0, 1.0],
            "k": 2,
        }


# ── 8. the distribution reaches the persisted PipelineProvenance (product path) ──
def test_sampling_reaches_pipeline_provenance():
    """The orchestrator must forward semantic_meta['sampling'] into PipelineProvenance —
    the hop that surfaces the distribution in the persisted blob the BFF/run_eval write.
    Drives grade_inprocess end-to-end ($0, fake semantic stage) so the orchestrator runs
    for real. Regression guard for the orchestrator passthrough."""
    from lithrim_bench.harness.grade import grade_inprocess
    from lithrim_bench.runtime.pipeline.models import JudgeVote, StageResult

    sampling = {
        "risk_judge": {"score_mean": 0.75, "score_variance": 0.0625, "scores_raw": [1.0, 0.5], "k": 2},
    }

    async def _stage(_request):
        sr = StageResult(
            status="PASS",
            findings=[],
            judge_votes=[
                JudgeVote(
                    judge_role="risk_judge", vote="PASS", confidence=0.9,
                    model="openai/gpt-4o", findings=[],
                )
            ],
        )
        return sr, {"council_config": {"mode": "full"}, "sampling": sampling}

    case = {"case_id": "samp1", "transcript": "t", "artifacts": [{"content": "a", "type": "note"}]}
    result = grade_inprocess(case, semantic_stage=_stage)
    assert result["provenance"]["sampling"] == sampling


# ── 9. per-reviewer k / temperature / criterion threading through build_trio ──
def test_build_trio_threads_per_role_k_temp_criterion(monkeypatch):
    import lithrim_bench.runtime.council.judges_dspy as jd
    import lithrim_bench.runtime.council.sampling as sampling_mod

    seen_temp: dict = {}

    def fake_build_judge_lm(role, **ov):
        seen_temp[role] = ov.get("temperature")
        return SimpleNamespace(model=f"fake/{role}")

    monkeypatch.setattr(jd, "build_judge_lm", fake_build_judge_lm)

    seen_k: dict = {}

    def spy_judge_call(prompt, *, model, k=1, **kw):
        seen_k[getattr(model, "model", model)] = k
        return sampling_mod.JudgeResult(
            score_mean=0.0, score_variance=0.0, scores_raw=[0.0], k=k,
            rationale="", decision="approve", findings=[], _raw_response=None,
        )

    monkeypatch.setattr(sampling_mod, "judge_call", spy_judge_call)

    trio = jd.build_trio(
        samples={"risk_judge": 4},                       # explicit override beats the default
        temperatures={"policy_judge": 0.7},
        criteria={"faithfulness_judge": "Check the allergy list."},
    )
    faith = next(j for j in trio if j.role == "faithfulness_judge")
    assert faith.role_prompt.rstrip().endswith("Evaluation criterion: Check the allergy list.")
    assert seen_temp["policy_judge"] == 0.7
    assert seen_temp["risk_judge"] is None  # unset → default (no override threaded)

    for j in trio:
        j.forward(transcript="t", artifact="a")
    assert seen_k["fake/risk_judge"] == 4          # explicit samples=
    assert seen_k["fake/policy_judge"] == 1        # DEFAULT_JUDGE_SAMPLES
    assert seen_k["fake/faithfulness_judge"] == 3  # DEFAULT_JUDGE_SAMPLES


# ── 10. the authored evaluator computes case_outcome from the independent axes ──
def test_authored_evaluator_computes_case_outcome():
    from lithrim_bench.harness.pack import pack_production_judges
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator

    roster = list(pack_production_judges())  # risk / policy / faithfulness

    def mk(decision, variance=0.0):
        return lambda **kw: JudgeResult(
            score_mean=0.0, score_variance=variance, scores_raw=[0.0], k=1,
            rationale="", decision=decision, findings=[], _raw_response=None,
        )

    def outcome(decisions, variances=None):
        variances = variances or {}
        predictors = {r: mk(decisions[r], variances.get(r, 0.0)) for r in roster}
        ev = build_authored_evaluator(
            ontology=None, assignments=None, predictors=predictors, apply_gate=False
        )
        return ev({"call_context": {"transcript": "t"}, "artifacts": [{"content": "a"}]})["case_outcome"]

    assert outcome({"risk_judge": "reject", "policy_judge": "approve", "faithfulness_judge": "approve"}) == "CRITICAL"
    assert outcome({"risk_judge": "approve", "policy_judge": "approve", "faithfulness_judge": "approve"}) == "CLEAR"
    # high variance on ANY axis gates to NEEDS_REVIEW even when the modal verdict would CLEAR.
    assert outcome(
        {"risk_judge": "approve", "policy_judge": "approve", "faithfulness_judge": "approve"},
        variances={"policy_judge": 0.25},
    ) == "NEEDS_REVIEW"


# ── 11. case_outcome reaches the persisted provenance + result (orchestrator hop) ──
def test_case_outcome_reaches_pipeline_provenance():
    from lithrim_bench.harness.grade import grade_inprocess
    from lithrim_bench.runtime.pipeline.models import JudgeVote, StageResult

    async def _stage(_request):
        sr = StageResult(
            status="BLOCK", findings=[],
            judge_votes=[JudgeVote(judge_role="risk_judge", vote="BLOCK", confidence=0.9,
                                   model="openai/gpt-4o", findings=[], variance=0.0625, k=5)],
        )
        return sr, {"council_config": {"mode": "full"}, "case_outcome": "CRITICAL"}

    case = {"case_id": "co1", "transcript": "t", "artifacts": [{"content": "a", "type": "note"}]}
    result = grade_inprocess(case, semantic_stage=_stage)
    assert result["case_outcome"] == "CRITICAL"
    assert result["provenance"]["case_outcome"] == "CRITICAL"
    # the per-reviewer variance/k survive onto the persisted vote.
    vote = result["semantic"]["judge_votes"][0]
    assert vote["variance"] == 0.0625
    assert vote["k"] == 5


# ── 12. _judge_votes_from_models lifts variance/k off each seam dict's sampling ──
def test_judge_votes_carry_per_reviewer_variance_and_k():
    from lithrim_bench.runtime.pipeline.stages import _judge_votes_from_models

    votes = _judge_votes_from_models([
        {"model": "risk_judge", "decision": "approve", "confidence": 0.9, "findings": [],
         "sampling": {"score_variance": 0.0625, "k": 5}},
        {"model": "policy_judge", "decision": "approve", "confidence": 0.8, "findings": []},  # no sampling
    ])
    assert votes[0].variance == 0.0625 and votes[0].k == 5
    assert votes[1].variance is None and votes[1].k is None  # absent → None, not coerced
