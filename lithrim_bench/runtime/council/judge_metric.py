"""Bench-accept metric for DSPy-rebuilt council judges — the judge analogue of
``verification/jute_dspy.py``'s ``score_template`` / ``make_bench_metric``.

WS-6c-DSPy (bench-salvage). The jute generator made the by-construction pack the
acceptance oracle for *tool authoring*; this does the same for *judge-prompt
authoring*. A judge's findings are scored against a case's ``expected_safety_flags``
(recipe = label, the CLAUDE.md core invariant), giving precision / recall and a
hard-accept gate: a candidate judge is trusted ONLY if it raises every in-lens
label and zero false positives (the judge analogue of jute's 0 FP / 0 ERR). This
is the WS-3a discipline — ship the accept GATE, the optimizer climbs the gradient
later; nothing here runs an optimizer.

Pure offline scorer: no ``dspy`` / ``openai`` / council import, so it stays
importable on the default pydantic+pandas core and can score fixtured judge
outputs (or persisted corpus rows) without the live stack. A single rebuilt judge
covers only its role's LENS of codes, so scoring is restricted to ``lens_codes``
(an out-of-lens raise counts as a false positive — the judge over-stepped its
scope).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

# risk_judge's code lens — the "CODES YOU MAY RAISE" in
# runtime/council/council_roles/risk_judge.txt (clinical-safety scope). NB:
# FABRICATED_HISTORY / HALLUCINATED_DETAIL are explicitly the BEHAVIOR JUDGE's
# domain (risk_judge.txt "CODES YOU MAY NOT RAISE"), so a risk_judge that stays
# SILENT on those cases is correct — they are not in this lens.
RISK_JUDGE_LENS = frozenset(
    {
        "MISSED_ESCALATION",
        "SEVERITY_ESCALATION",
        "WRONG_DOSAGE",
        "MEDICATION_NOT_IN_TRANSCRIPT",
        "FABRICATED_ALLERGY",
    }
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def expected_codes(case: Any) -> set[str]:
    """The recipe=label positives for a case (its ``expected_safety_flags``)."""
    return {c for c in (_get(case, "expected_safety_flags", []) or []) if c}


def raised_codes(judge_output: Any) -> set[str]:
    """The taxonomy codes a judge flagged — from a seam dict's ``findings`` or a
    dspy prediction's ``findings`` (each finding a dict or a model)."""
    out: set[str] = set()
    for f in (_get(judge_output, "findings", []) or []):
        code = _get(f, "taxonomy_code", "") or ""
        if code:
            out.add(code)
    return out


def _score_one(expected: set[str], raised: set[str], lens: set[str] | None) -> dict[str, Any]:
    """Per-case confusion counts for one judge, restricted to its lens.

    in-lens ground truth = expected ∩ lens; a judge should raise exactly those.
    A false positive is anything raised that is NOT an in-lens positive — this
    folds in clean-negative over-firing AND out-of-lens raises (scope overreach).
    """
    truth = (expected & lens) if lens is not None else expected
    tp = raised & truth
    fp = raised - truth
    fn = truth - raised
    return {
        "tp": sorted(tp),
        "fp": sorted(fp),
        "fn": sorted(fn),
        "exact": not fp and not fn,
    }


def _f_partial(tp: int, fp: int, fn: int) -> float:
    """Graded [0,1) partial credit (F1) for an inexact case — the optimizer's
    gradient. Exact cases are scored 1.0 by the caller; a case with no signal
    either way (no truth, no raise) is exact and never reaches here."""
    denom = 2 * tp + fp + fn
    return (2 * tp / denom) if denom else 0.0


def score_judge(
    run_judge: Callable[[Any], Any],
    cases: Iterable[Any],
    *,
    lens_codes: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Score a judge against a by-construction pack (recipe = label).

    ``run_judge(case)`` returns that case's judge output (a seam dict, or anything
    with ``findings``); pass a fixtured callable offline, or a thunk that runs a
    live ``Judge`` per case. ``accepted`` is the hard gate: 0 false positives AND
    0 false negatives across the pack (every in-lens label caught, nothing
    over-fired) — the judge analogue of jute's 0 FP / 0 ERR. ``graded`` is the
    fraction of per-case correctness, the gradient an optimizer would climb.
    """
    lens = set(lens_codes) if lens_codes is not None else None
    rows: list[dict[str, Any]] = []
    fp_total = fn_total = tp_total = 0
    graded_sum = 0.0
    n = 0
    for case in cases:
        n += 1
        expected = expected_codes(case)
        raised = raised_codes(run_judge(case))
        one = _score_one(expected, raised, lens)
        tp, fp, fn = len(one["tp"]), len(one["fp"]), len(one["fn"])
        tp_total += tp
        fp_total += fp
        fn_total += fn
        graded_sum += 1.0 if one["exact"] else _f_partial(tp, fp, fn)
        rows.append(
            {
                "case_id": _get(case, "case_id", "") or "",
                "expected": sorted(expected),
                "raised": sorted(raised),
                **one,
            }
        )
    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 1.0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 1.0
    return {
        "accepted": fp_total == 0 and fn_total == 0,
        "graded": graded_sum / n if n else 0.0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "tp": tp_total,
        "fp": fp_total,
        "fn": fn_total,
        "n": n,
        "rows": rows,
    }


def make_judge_metric(*, lens_codes: Iterable[str] | None = None):
    """Build a DSPy-style ``metric(example, pred, trace=None) -> float|bool`` that
    scores ONE judge output against ONE case's recipe label.

    With ``trace`` set (the optimizer's bootstrap gate) it returns the hard-accept
    bool — only a per-case-perfect judgement becomes a few-shot demo. Otherwise it
    returns the graded [0,1] score so the optimizer has a gradient. Mirrors
    ``jute_dspy.make_bench_metric``.
    """
    lens = set(lens_codes) if lens_codes is not None else None

    def metric(example: Any, pred: Any, trace: Any = None) -> Any:
        one = _score_one(expected_codes(example), raised_codes(pred), lens)
        if trace is not None:
            return bool(one["exact"])
        if one["exact"]:
            return 1.0
        return _f_partial(len(one["tp"]), len(one["fp"]), len(one["fn"]))

    return metric
