"""WS-6c-DSPy A2: the bench-accept judge metric scores a judge's findings against
a by-construction case's ``expected_safety_flags`` (recipe = label).

Hermetic + pure: ``judge_metric`` has no dspy/openai/council import, so this runs
on the default pydantic+pandas core (no importorskip). Fixtured judge outputs +
fixtured recipe-labelled cases, no network — the metric IS the acceptance oracle
for judge-prompt authoring, mirroring ``jute_dspy``'s bench-accept gate.
"""
from __future__ import annotations

from lithrim_bench.runtime.council.judge_metric import (
    FAITHFULNESS_JUDGE_LENS,
    RISK_JUDGE_LENS,
    make_judge_metric,
    raised_codes,
    score_judge,
)

# By-construction cases (recipe = label). One in-lens Tier-1 positive
# (WRONG_DOSAGE), one clean negative, one OUT-OF-lens defect (FABRICATED_HISTORY
# is behavior_judge's domain — risk_judge must stay silent on it).
CASES = [
    {"case_id": "wrong_dosage_viol", "expected_safety_flags": ["WRONG_DOSAGE"]},
    {"case_id": "clean_negative", "expected_safety_flags": []},
    {"case_id": "fabricated_history_viol", "expected_safety_flags": ["FABRICATED_HISTORY"]},
]


def _finding(code):
    return {"taxonomy_code": code, "evidence_spans": [{"quote": f"q::{code}", "turn_ids": [1]}]}


def _judge_only_wrong_dosage(case):
    """A correct risk_judge: raises WRONG_DOSAGE when present, silent otherwise
    (incl. silent on the out-of-lens FABRICATED_HISTORY case)."""
    flags = set(case.get("expected_safety_flags") or [])
    findings = [_finding("WRONG_DOSAGE")] if "WRONG_DOSAGE" in flags else []
    return {"model": "risk_judge", "decision": "reject" if findings else "approve", "findings": findings}


def test_perfect_in_lens_judge_is_accepted():
    s = score_judge(_judge_only_wrong_dosage, CASES, lens_codes=RISK_JUDGE_LENS)
    assert s["accepted"] is True
    assert s["precision"] == 1.0 and s["recall"] == 1.0
    assert (s["tp"], s["fp"], s["fn"]) == (1, 0, 0)
    assert s["graded"] == 1.0


def test_false_positive_on_clean_negative_fails_the_gate():
    s = score_judge(lambda case: {"findings": [_finding("WRONG_DOSAGE")]}, CASES, lens_codes=RISK_JUDGE_LENS)
    assert s["accepted"] is False
    assert s["fp"] == 2  # over-fired on the clean negative + the out-of-lens case
    assert s["recall"] == 1.0  # still caught the one real WRONG_DOSAGE


def test_out_of_lens_raise_counts_as_false_positive():
    """risk_judge raising FABRICATED_HISTORY (behavior's domain) is scope overreach."""

    def overreach(case):
        flags = set(case.get("expected_safety_flags") or [])
        f = []
        if "WRONG_DOSAGE" in flags:  # in-lens, correctly caught (isolates the FP below)
            f.append(_finding("WRONG_DOSAGE"))
        if "FABRICATED_HISTORY" in flags:  # out-of-lens — scope overreach
            f.append(_finding("FABRICATED_HISTORY"))
        return {"findings": f}

    s = score_judge(overreach, CASES, lens_codes=RISK_JUDGE_LENS)
    assert s["accepted"] is False
    assert s["fp"] == 1 and s["fn"] == 0  # the FABRICATED_HISTORY raise is the only error


def test_missed_in_lens_label_fails_the_gate():
    s = score_judge(lambda case: {"findings": []}, CASES, lens_codes=RISK_JUDGE_LENS)
    assert s["accepted"] is False
    assert s["fn"] == 1  # missed the one WRONG_DOSAGE
    assert s["fp"] == 0


def test_dspy_metric_hard_accept_under_trace_else_graded():
    metric = make_judge_metric(lens_codes=RISK_JUDGE_LENS)
    wd = CASES[0]
    hit = {"findings": [_finding("WRONG_DOSAGE")]}
    miss = {"findings": []}
    assert metric(wd, hit, trace=object()) is True  # bootstrap gate: only perfect becomes a demo
    assert metric(wd, hit) == 1.0
    assert metric(wd, miss) == 0.0


# ── S-BS-43: the co-raise-aware lens ─────────────────────────────────────────
# A cross-owner multi-defect case (the judge_calib_v1 fixture): WRONG_DOSAGE is
# risk's Tier-1 code, MISSING_ALLERGY is faithfulness's. A faithfulness judge
# that catches its own MISSING_ALLERGY AND corroborates the expected (risk-owned)
# WRONG_DOSAGE is doing the right thing — under the co-raise-aware lens that
# corroboration is neutral, not an FP.
_CO_RAISE_CASES = [
    {"case_id": "multi_dosage_allergy", "expected_safety_flags": ["MISSING_ALLERGY", "WRONG_DOSAGE"]},
    {"case_id": "clean_negative", "expected_safety_flags": []},
]


def _faithfulness_corroborates(case):
    """Raises its own in-lens MISSING_ALLERGY plus a corroborating WRONG_DOSAGE
    (risk-owned, but expected in the multi-defect case)."""
    flags = set(case.get("expected_safety_flags") or [])
    findings = []
    if "MISSING_ALLERGY" in flags:
        findings.append(_finding("MISSING_ALLERGY"))
    if "WRONG_DOSAGE" in flags:  # corroboration of risk's expected code
        findings.append(_finding("WRONG_DOSAGE"))
    return {"findings": findings}


def test_co_raise_of_expected_code_is_fp_by_default():
    """Default (owner-consistent) lens: the corroborating WRONG_DOSAGE raise is an
    out-of-lens FP — the documented lower bound."""
    s = score_judge(_faithfulness_corroborates, _CO_RAISE_CASES, lens_codes=FAITHFULNESS_JUDGE_LENS)
    assert s["accepted"] is False
    assert s["fp"] == 1 and s["fn"] == 0  # the WRONG_DOSAGE corroboration is the only "error"
    assert s["tp"] == 1  # MISSING_ALLERGY caught


def test_co_raise_of_expected_code_is_neutral_when_aware():
    """co_raise_aware: the corroboration of the expected, risk-owned WRONG_DOSAGE
    is neutral — not an FP — so the faithfulness judge is accepted."""
    s = score_judge(
        _faithfulness_corroborates,
        _CO_RAISE_CASES,
        lens_codes=FAITHFULNESS_JUDGE_LENS,
        co_raise_aware=True,
    )
    assert s["accepted"] is True
    assert s["fp"] == 0 and s["fn"] == 0
    assert s["tp"] == 1 and s["neutral"] == 1  # WRONG_DOSAGE corroboration scored neutral


def test_co_raise_aware_still_flags_genuine_overfire():
    """A raise of a NOT-expected code is still an FP under co_raise_aware — the
    neutral carve-out is only for codes in the case's expected set."""

    def overfire(case):
        flags = set(case.get("expected_safety_flags") or [])
        findings = [_finding("MISSING_ALLERGY")] if "MISSING_ALLERGY" in flags else []
        findings.append(_finding("HALLUCINATED_DETAIL"))  # not expected in either case
        return {"findings": findings}

    s = score_judge(
        overfire, _CO_RAISE_CASES, lens_codes=FAITHFULNESS_JUDGE_LENS, co_raise_aware=True
    )
    assert s["accepted"] is False
    assert s["fp"] == 2  # HALLUCINATED_DETAIL over-fired on both cases (not expected)


def test_co_raise_aware_metric_hard_accept():
    """make_judge_metric(co_raise_aware=True): the multi-defect case with a
    corroborating raise passes the bootstrap gate (was rejected by default)."""
    case = _CO_RAISE_CASES[0]
    pred = {"findings": [_finding("MISSING_ALLERGY"), _finding("WRONG_DOSAGE")]}
    default_metric = make_judge_metric(lens_codes=FAITHFULNESS_JUDGE_LENS)
    aware_metric = make_judge_metric(lens_codes=FAITHFULNESS_JUDGE_LENS, co_raise_aware=True)
    assert default_metric(case, pred, trace=object()) is False  # corroboration breaks the gate
    assert aware_metric(case, pred, trace=object()) is True  # neutral → gate passes
    assert aware_metric(case, pred) == 1.0


def test_raised_codes_reads_findings():
    assert raised_codes({"findings": [_finding("WRONG_DOSAGE"), _finding("MISSED_ESCALATION")]}) == {
        "WRONG_DOSAGE",
        "MISSED_ESCALATION",
    }
    assert raised_codes({"findings": []}) == set()
