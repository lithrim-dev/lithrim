"""The sampling layer — ONE core primitive every reviewer's model call goes through.

The grading engine used to scatter its model call: each ``Judge`` made its own
``dspy.Predict`` invocation and read a single completion. There was no way to ask
for ``k`` samples and estimate how stable a judge's verdict is — the distributional
reporting ``docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`` Part 2 ("stop reporting
single-run verdicts; measure distributions") and the "self-consistency / sampling-
based confidence proxy" in the landscape report both call for.

:func:`judge_call` is that single primitive: it makes ONE API call using the native
``n`` parameter to request ``k`` completions simultaneously, and returns a
:class:`JudgeResult` carrying ``score_mean`` / ``score_variance`` / ``scores_raw`` /
``k`` / ``rationale``. Every LIVE judge (single, Faithfulness, Policy, Risk, any
future role) routes through it via the authorized ``judges_dspy.build_trio`` seam —
no reviewer makes a raw model call. ``k=1`` is the default and needs no special
handling: it is byte-equivalent to the pre-sampling ``Judge.forward`` path.

The frozen seam is untouched. ``JudgeResult`` ALSO carries the representative
completion's ``decision`` / ``findings`` / ``_raw_response`` so it can be returned
DIRECTLY as the predictor object the byte-frozen ``Judge.forward`` already consumes
(``Judge.forward`` reads ``.decision`` / ``.findings`` and the logprob confidence off
``_raw_response`` — exactly the ``SimpleNamespace`` shape the offline test predictors
already use). So:

  * verdict derivation is unchanged — confidence is still the representative
    completion's logprob ``exp(logprob)`` via the FROZEN ``extract_verdict_confidence``
    (computed in ``Judge.forward`` from ``_raw_response``), NOT a self-report and NOT
    the sampled mean;
  * the score distribution (``score_mean`` / ``score_variance``) is ADDITIVE
    telemetry, surfaced into provenance by the editable ``authored_stage`` /
    ``stages`` layers — it never feeds ``_apply_consensus``.

The per-completion SCALAR score is DERIVED from the existing ``decision`` output
(reject=0.0, needs_review=0.5, approve=1.0); no numeric-score output field is added to
the signature (that would change reviewer configuration, not the sampling layer). So
``score_*`` measures decision stability (the spec's ``verdict_instability``) and works
for every provider, including the logprob-dark ones (Anthropic / Gemini / Mistral).

Heavy deps (``dspy``) import lazily inside the function that needs them, mirroring
``judges_dspy`` / ``byo_claude_lm``, so importing this module is cheap and safe on the
default pydantic+pandas core.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .byo_claude_lm import BYO_CLAUDE_MODEL_VALUES

logger = logging.getLogger(__name__)

# The default sampling temperature for k>1 (the ensembling regime). Set EXPLICITLY rather than
# relying on DSPy's hidden "bump temp to 0.7 when <=0.15 and n>1" rule — so the value is
# predictable and matches the UI. Per the criteria-injection/ensembling paper, ensembling gains
# grow with temperature; 1.0 maximizes the benefit of k-sampling (averaging out per-call noise).
# A per-reviewer ``temperature`` overrides it; k=1 always runs deterministically (temp 0).
DEFAULT_SAMPLE_TEMPERATURE = 1.0

# decision → scalar score. The score is DERIVED from the decision the signature
# already emits; nothing new is asked of the model. reject is the worst (0.0),
# approve the best (1.0), needs_review the midpoint — so a clean approve→reject
# split over k samples produces a 0.5 mean and the maximum variance, the exact
# "this judge is unstable on this case" signal.
_SCORE_BY_DECISION = {"reject": 0.0, "needs_review": 0.5, "approve": 1.0}


def _score_of(decision: str) -> float:
    return _SCORE_BY_DECISION.get(decision, 0.5)


@dataclass(frozen=True)
class JudgeResult:
    """The return of :func:`judge_call` — a sampled judgement over k completions.

    The first five fields are the sampling-layer contract (the distribution). The
    last three (``decision`` / ``findings`` / ``_raw_response``) are the
    representative completion, present so a ``JudgeResult`` can be returned straight
    to the byte-frozen ``Judge.forward`` (which reads ``.decision`` / ``.findings``
    and the logprob confidence off ``_raw_response``). ``reason`` aliases
    ``rationale`` so the object also duck-types the dspy ``Prediction`` shape.

    A frozen dataclass (not a pydantic model) on purpose: ``_raw_response`` is a
    leading-underscore name, which pydantic v2 treats as a private attribute, not a
    field — a dataclass carries it as a plain attribute that ``getattr`` reads, which
    is exactly what ``judges_dspy._raw_response_for`` does.
    """

    score_mean: float
    score_variance: float
    scores_raw: list[float] = field(default_factory=list)
    k: int = 0
    rationale: str = ""
    decision: str = "needs_review"
    findings: list[dict[str, Any]] = field(default_factory=list)
    _raw_response: Any = None
    # LAYER0-READ-1: real token spend of THIS call ({input_tokens, output_tokens} — the
    # exact keys the frozen stages.py cost_tokens sum reads), None when the LM exposes
    # no usage. Captured here (the unfrozen sampling layer), NOT in the byte-frozen
    # Judge.forward — the authored stage folds it onto the per-judge seam dict.
    usage: dict[str, int] | None = None

    @property
    def reason(self) -> str:
        return self.rationale


def _usage_delta(lm: Any, history_before: int | None) -> dict[str, int] | None:
    """LAYER0-READ-1: sum token usage from the LM-history entries THIS call appended.
    LiteLLM entries carry ``usage.prompt_tokens/completion_tokens`` (``input_/output_``
    tolerated); emitted as ``{input_tokens, output_tokens}`` — the exact keys the frozen
    stages.py cost_tokens sum reads. No lm / no history / zero-sum → None, so offline
    fake-predictor paths stay byte-identical (no key ever fabricated)."""
    if lm is None or history_before is None:
        return None
    entries = list(getattr(lm, "history", []) or [])[history_before:]
    prompt = completion = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        usage = entry.get("usage") or {}
        prompt += int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion += int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    if not (prompt or completion):
        return None
    return {"input_tokens": prompt, "output_tokens": completion}


def _is_single_completion_lm(lm: Any) -> bool:
    """True iff ``lm`` cannot honor a native ``n`` (so k>1 must clamp to k=1).

    Gates on BYO-Claude membership (the one provider in this codebase whose
    ``claude -p`` CLI returns exactly one completion per call) plus an explicit
    ``supports_n=False`` escape hatch for a future single-completion LM. Deliberately
    NOT keyed on logprob support — Gemini/Anthropic-API support ``n`` while exposing no
    logprobs, and clamping them would needlessly kill sampling.
    """
    if getattr(lm, "supports_n", True) is False:
        return True
    model_id = str(getattr(lm, "model", lm) or "").strip().lower()
    return model_id in BYO_CLAUDE_MODEL_VALUES


def _single_choice_response(resp: Any, index: int) -> Any:
    """A single-choice response holding ``resp.choices[index]`` at ``choices[0]``.

    ``extract_verdict_confidence`` only ever reads ``choices[0]`` and accepts a dict
    payload (the shape its own docstring documents for synthesized inputs), so wrapping
    the representative choice in ``{"choices": [choice]}`` is sufficient and keeps this
    module free of any litellm import. The wrapped ``choice`` keeps its native type
    (a litellm ``Choices`` live, whatever a test injects offline)."""
    choices = getattr(resp, "choices", None)
    if choices is None and isinstance(resp, dict):
        choices = resp.get("choices")
    if not choices or index >= len(choices):
        return None
    return {"choices": [choices[index]]}


def _reward_judge_result(
    model: Any, prompt: str, *, artifact: str, role_key_questions: str, k: int
) -> JudgeResult:
    """F8-PROVIDER: score→verdict for a reward-model LM (``is_reward_lm``) — deterministic
    threshold logic in the unfrozen sampling layer, no dspy anywhere.

    ``k`` independent evaluations (the reward API has no native ``n``; the research measured
    n=3 byte-identical — repeats are the determinism CHECK, not noise smoothing). Per sample:
    verdict = ``reject`` iff ``score < model.threshold`` (0.5, the research's cut). The RAW
    scores land in ``scores_raw`` — the same low=block / high=pass direction as the decision
    scalars, so the K-split chip renders the graded score honestly. Honesty invariants:
    ``findings=[]`` (a reward model types no defect codes), ``usage=None`` (no token report),
    ``_raw_response=None`` (no logprobs → confidence ``None``), and a failed/short evaluation
    set DECLINES to ``needs_review`` — never a manufactured verdict. The criterion sent is the
    LM's explicit ``criterion`` when authored, else the composed role prompt (which carries the
    reviewer's CRITERION-TEXT sentence)."""
    criterion = str(getattr(model, "criterion", "") or "") or role_key_questions
    threshold = float(getattr(model, "threshold", 0.5))
    # REWARD-SEMANTICS-1 (measured — the case09 six-call table): a reward model scores "did the
    # assistant serve the request", so the user message must BE a request. A bare source dump
    # collapsed the faithfulness pressure (0.44 → 0.6 on identical text); the source is framed
    # with a task line — the LM's SME-authored ``task_instruction`` when set, else the generic
    # default below.
    task = str(getattr(model, "task_instruction", "") or "") or (
        "Generate a faithful artifact from this source material."
    )
    user = f"Source material:\n{prompt}\n\n{task}"
    scores: list[float] = []
    explanations: list[str] = []
    errors: list[str] = []
    for _ in range(max(1, int(k))):
        try:
            out = model.evaluate(user, artifact, criterion)
        except Exception as exc:  # noqa: BLE001 — a transport failure is a declined sample
            errors.append(str(exc))
            continue
        scores.append(float(out["score"]))
        if out.get("explanation"):
            explanations.append(str(out["explanation"]))
    if errors:
        logger.info("judge_call[reward]: %d/%d evaluation(s) failed: %s", len(errors), k, errors[-1])

    verdicts = ["reject" if s < threshold else "approve" for s in scores]
    n_reject, n_approve = verdicts.count("reject"), verdicts.count("approve")
    if not scores or n_reject == n_approve:
        decision = "needs_review"  # no samples, or an exact split → decline, never a guess
    else:
        decision = "reject" if n_reject > n_approve else "approve"

    mean = sum(scores) / len(scores) if scores else 0.0
    variance = sum((s - mean) ** 2 for s in scores) / len(scores) if scores else 0.0
    rationale = explanations[0] if explanations else (f"evaluation failed: {errors[0]}" if errors else "")
    return JudgeResult(
        score_mean=mean,
        score_variance=variance,
        scores_raw=scores,
        k=len(scores),
        rationale=rationale,
        decision=decision,
        findings=[],
        _raw_response=None,
        usage=None,
    )


def judge_call(
    prompt: str,
    *,
    model: Any,
    k: int = 1,
    temperature: float | None = None,
    artifact: str = "",
    role_key_questions: str = "",
    taxonomy_context: str | None = None,
    predict: Any = None,
    demos: Any = None,
) -> JudgeResult:
    """The single sampling primitive: one API call, k completions, one JudgeResult.

    ``prompt`` is the source conversation (the ``transcript`` input of the frozen
    judge signature — named ``prompt`` to match the primitive's contract
    ``judge_call(prompt, model, k, temperature)``). ``model`` is the role's bound
    ``dspy.LM`` (what ``dspy.Predict.set_lm`` takes), not a string. ``predict`` is an
    injectable ``dspy.Predict`` for $0 offline tests; when omitted it is built lazily
    from the FROZEN ``_build_signature`` and bound to ``model`` — so parsing is
    identical to ``Judge.forward`` and k=1 stays byte-equivalent.

    k=1 (the default) makes a single call with NO sampling config — temperature stays
    the LM's (0), cache stays on, one completion — and returns a JudgeResult whose
    representative IS that completion. k>1 makes ONE call with ``config={"n": k,
    "cache": False}`` (cache off so a re-grade actually re-samples instead of replaying
    the cached k completions — the "DSPy live-grade cache trap"); DSPy then forces
    temperature 0.7 (its own n>1 rule). The k completions are scored
    (decision→scalar), the MODAL decision picks the representative completion (its
    findings/rationale/logprobs feed the seam dict), and the population
    mean/variance over the scored scalars become ``score_mean`` / ``score_variance``.

    ``temperature`` is the SAMPLING temperature for k>1: the per-reviewer value when set, else
    :data:`DEFAULT_SAMPLE_TEMPERATURE` (1.0, the paper's max-ensembling setting). It is passed
    EXPLICITLY in the k>1 config (so it's predictable, not DSPy's hidden ≤0.15→0.7 bump). k=1
    ignores it and runs deterministically (no config — byte-identical to the pre-sampling path).

    A provider that cannot honor a native ``n`` (BYO-Claude) clamps to k=1 and logs a
    one-line downgrade.

    F8-PROVIDER: a reward-model LM (``is_reward_lm``, e.g. ``provider: composo``) branches to
    :func:`_reward_judge_result` BEFORE any dspy construction — the reward API answers
    ``(messages, criteria) -> score``, not a signature prompt, so the verdict is deterministic
    threshold logic here in the (unfrozen) sampling layer, never a parsed completion.
    """
    if getattr(model, "is_reward_lm", False):
        return _reward_judge_result(
            model, prompt, artifact=artifact, role_key_questions=role_key_questions, k=k
        )

    from .judges_dspy import (
        _norm_decision,
        _raw_response_for,
        _validate_findings,
        default_taxonomy_context,
    )

    if k > 1 and _is_single_completion_lm(model):
        logger.info(
            "judge_call: model %r cannot honor native n; clamping k=%d -> 1",
            getattr(model, "model", model),
            k,
        )
        k = 1

    if predict is None:
        import dspy

        from .judges_dspy import _build_signature

        predict = dspy.Predict(_build_signature())
        if model is not None and hasattr(predict, "set_lm"):
            predict.set_lm(model)

    # DEMO-PIN-1 (S-BS-48): an optimized judge's compiled few-shot demos bind onto the predict
    # here (the single live construction point), so the grade actually USES the demos the DSPy
    # optimizer harvested. None (the default) leaves the predict demo-less — byte-identical to
    # the pre-pin path. Applied to an injected ``predict`` too (offline determinism).
    if demos is not None:
        predict.demos = list(demos)

    inputs = dict(
        transcript=prompt,
        artifact=artifact,
        role_key_questions=role_key_questions,
        taxonomy_context=taxonomy_context or default_taxonomy_context(),
    )

    # LAYER0-READ-1: snapshot the LM history length so the usage of exactly THIS call
    # (either branch — one API call each) can be summed after it returns.
    _usage_lm = getattr(predict, "lm", None) or model
    _hist_before = (
        len(getattr(_usage_lm, "history", []) or []) if _usage_lm is not None else None
    )

    # ---- k == 1: byte-equivalent to the pre-sampling Judge.forward path ----
    # No config is passed, so temperature/cache are the LM's defaults and the call is
    # identical to today; confidence comes from the SAME _raw_response_for read.
    if k == 1:
        pred = predict(**inputs)
        decision = _norm_decision(_get(pred, "decision"))
        findings = _validate_findings(_get(pred, "findings", []))
        raw = _raw_response_for(pred, predict)
        score = _score_of(decision)
        return JudgeResult(
            score_mean=score,
            score_variance=0.0,
            scores_raw=[score],
            k=1,
            rationale=str(_get(pred, "reason", "") or ""),
            decision=decision,
            findings=findings,
            _raw_response=raw,
            usage=_usage_delta(_usage_lm, _hist_before),
        )

    # ---- k > 1: ONE call, native n, cache off (avoid the n>k cache replay) ----
    # Explicit sampling temperature (per-reviewer override, else the 1.0 default) so ensembling
    # actually samples — never silently deterministic and never DSPy's hidden 0.7 bump.
    samp_temp = temperature if temperature is not None else DEFAULT_SAMPLE_TEMPERATURE
    pred = predict(**inputs, config={"n": k, "cache": False, "temperature": samp_temp})
    completions = getattr(pred, "completions", None)
    n = len(completions) if completions is not None else 1
    resp = _lm_last_response(model)

    scored: list[tuple[int, str, float]] = []  # (choice_index, decision, score)
    for i in range(n):
        comp = completions[i] if completions is not None else pred
        raw_decision = _get(comp, "decision")
        if raw_decision is None or str(raw_decision).strip() == "":
            continue  # a failed/empty completion is excluded, never scored needs_review
        decision_i = _norm_decision(raw_decision)
        scored.append((i, decision_i, _score_of(decision_i)))

    if not scored:
        # Every completion failed to produce a decision — degenerate, mirrors the
        # consensus ``insufficient_valid_models`` fallback. Judge.forward still wraps
        # any hard raise into errors; this is the soft all-empty case.
        return JudgeResult(
            score_mean=0.0,
            score_variance=0.0,
            scores_raw=[],
            k=0,
            rationale="",
            decision="needs_review",
            findings=[],
            _raw_response=None,
            usage=_usage_delta(_usage_lm, _hist_before),  # the failed call still spent
        )

    scores = [s for _, _, s in scored]
    decisions = [d for _, d, _ in scored]
    modal = _modal_decision(decisions)
    rep_i = next(ci for ci, d, _ in scored if d == modal)
    rep_comp = completions[rep_i] if completions is not None else pred

    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    rep_raw = _single_choice_response(resp, rep_i) if resp is not None else None

    return JudgeResult(
        score_mean=mean,
        score_variance=variance,
        scores_raw=scores,
        k=len(scores),
        rationale=str(_get(rep_comp, "reason", "") or ""),
        decision=modal,
        findings=_validate_findings(_get(rep_comp, "findings", [])),
        _raw_response=rep_raw,
        usage=_usage_delta(_usage_lm, _hist_before),
    )


def _modal_decision(decisions: list[str]) -> str:
    """The most common decision, ties broken by first occurrence (deterministic)."""
    counts = Counter(decisions)
    top = max(counts.values())
    for d in decisions:  # iteration order = choice order → first-occurrence tie-break
        if counts[d] == top:
            return d
    return decisions[0]


def _lm_last_response(model: Any) -> Any:
    """The full (multi-choice) ModelResponse of the LM's last call, or None."""
    history = getattr(model, "history", None)
    if not history:
        return None
    last = history[-1]
    return last.get("response") if isinstance(last, dict) else getattr(last, "response", None)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` off a dict / pydantic model / dspy Prediction / namespace."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
