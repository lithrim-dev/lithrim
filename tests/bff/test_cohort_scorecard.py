"""RUN-ALL-1 — the consolidated cohort scorecard.

``POST /v1/cases/grade`` returns a case-attributed matrix; ``_cohort_scorecard`` turns that matrix +
the per-case gold (``expected_safety_flags``) into the consolidated report the chat renders: per-case
caught / missed / spurious flags + an aggregate flag precision/recall + verdict accuracy + a per-flag
over/under-fire breakdown. Only LABELED cases feed the accuracy metrics (honest-unlabeled — no
fabricated numbers on unlabeled data). Pure function over the matrix → unit-tested directly, $0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

# a small cohort: a perfect match, an over+under-fire, a clean negative, an unlabeled case
_MATRIX = [
    {"case_id": "c1", "verdict": "BLOCK", "findings": ["INTENT_ERASURE", "HISTORY_OMISSION"]},
    {"case_id": "c2", "verdict": "BLOCK", "findings": ["HALLUCINATED_DETAIL", "INTERNAL_INCONSISTENCY"]},
    {"case_id": "c3", "verdict": "PASS", "findings": []},
    {"case_id": "c4", "verdict": "WARN", "findings": ["HALLUCINATED_DETAIL"]},  # unlabeled — no gold
]
_GOLDS = {
    "c1": {"INTENT_ERASURE", "HISTORY_OMISSION"},   # perfect
    "c2": {"HALLUCINATED_DETAIL", "VALUE_MISMATCH"},  # caught HALL, spurious INT_INC, missed VALUE_MISMATCH
    "c3": set(),                                     # clean negative
}
_LABELED = {"c1", "c2", "c3"}  # c4 is unlabeled


def _card():
    return bff._cohort_scorecard(_MATRIX, _GOLDS, _LABELED)


def test_per_case_caught_missed_spurious():
    cases = {c["case_id"]: c for c in _card()["cases"]}
    assert cases["c1"]["caught"] == ["HISTORY_OMISSION", "INTENT_ERASURE"]
    assert cases["c1"]["missed"] == [] and cases["c1"]["spurious"] == []
    assert cases["c2"]["caught"] == ["HALLUCINATED_DETAIL"]
    assert cases["c2"]["spurious"] == ["INTERNAL_INCONSISTENCY"]
    assert cases["c2"]["missed"] == ["VALUE_MISMATCH"]
    assert cases["c3"]["caught"] == [] and cases["c3"]["spurious"] == []  # clean stays clean


def test_verdict_match_uses_gold_presence():
    cases = {c["case_id"]: c for c in _card()["cases"]}
    assert cases["c1"]["verdict_match"] is True   # gold present + BLOCK
    assert cases["c3"]["verdict_match"] is True   # gold empty + PASS
    assert cases["c2"]["verdict_match"] is True   # gold present + BLOCK


def test_aggregate_precision_recall_over_labeled_only():
    card = _card()
    # TP = c1(2) + c2(1) = 3 ; FP = c2(1) ; FN = c2(1)
    assert card["flag"] == {"tp": 3, "fp": 1, "fn": 1, "precision": 0.75, "recall": 0.75}
    assert card["verdict_accuracy"] == "3/3"
    assert card["n_cases"] == 4 and card["n_labeled"] == 3


def test_unlabeled_case_excluded_from_accuracy():
    c4 = {c["case_id"]: c for c in _card()["cases"]}["c4"]
    assert c4["labeled"] is False
    assert "gold" not in c4 and "verdict_match" not in c4  # no fabricated comparison
    assert c4["raised"] == ["HALLUCINATED_DETAIL"]  # the raw result still shown


def test_by_flag_over_and_under_fire_breakdown():
    by = _card()["by_flag"]
    assert by["INTERNAL_INCONSISTENCY"] == {"tp": 0, "fp": 1, "fn": 0}  # pure over-fire
    assert by["VALUE_MISMATCH"] == {"tp": 0, "fp": 0, "fn": 1}          # pure miss
    assert by["HALLUCINATED_DETAIL"]["tp"] == 1


# --- regression: the labeled-set + golds DERIVATION from the REAL ingested envelope ---
# The stored case envelope carries NO `labeled` key — that field is *derived* by /v1/cases.
# The cohort scorecard must derive it the SAME way (from the gold), or a fully-labeled corpus
# reports "0 labeled" and the scorecard refuses to score anything (the live bug on the
# Clinical Scribe Review suite: 10 labeled cases shown as unlabeled, precision/recall n/a).


def test_case_has_gold_derives_from_gold_not_a_labeled_key():
    assert bff._case_has_gold({"expected_safety_flags": ["HALLUCINATED_DETAIL"]}) is True
    assert bff._case_has_gold({"expected_compliance_verdict": "approve", "expected_safety_flags": []}) is True
    assert bff._case_has_gold({"expected_safety_flags": []}) is False   # unlabeled placeholder ([] is not gold)
    assert bff._case_has_gold({"labeled": True}) is False               # a stray `labeled` key is NOT gold


def test_corpus_golds_labeled_over_real_envelope_shape():
    # the real cases_store payload: NO `labeled` key; gold lives in flags/verdict
    rows = [
        {"case_id": "k1", "expected_safety_flags": ["HALLUCINATED_DETAIL", "HISTORY_OMISSION"],
         "expected_compliance_verdict": "reject"},
        {"case_id": "k2", "expected_safety_flags": [], "expected_compliance_verdict": "approve"},  # labeled clean-negative
        {"case_id": "k3", "expected_safety_flags": []},  # unlabeled (no verdict)
        {"case_id": None},  # malformed — dropped
    ]
    golds, labeled = bff._corpus_golds_labeled(rows)
    assert labeled == {"k1", "k2"}  # the bug read a missing `labeled` key → empty set → "0 labeled"
    assert golds["k1"] == {"HALLUCINATED_DETAIL", "HISTORY_OMISSION"}
    assert golds["k2"] == set()  # clean-negative gold is the empty set, still labeled
    assert "k3" in golds and golds["k3"] == set()
