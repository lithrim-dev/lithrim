"""Offline tests for mutation coverage — deterministic proof that it catches the exact
oracle-coverage failure (the engagement-3 timestamp bug) that shipped "accepted".

The validator is a Python oracle (no JUTE, no network): a transaction checker whose
timestamp datatype check is either CORRECT (full charset) or BUGGY (first-char-only, the
anchored-regex bug). Mutation coverage must distinguish them via the legal-prefix-then-junk
mutant the original 10-case pack lacked.
"""

from __future__ import annotations

from lithrim_bench.verification import (
    field_mutants,
    generate_mutants,
    joint_coverage,
    mutants_to_cases,
    mutation_coverage,
    score_template,
    valid_variations,
)
from lithrim_bench.verification.tools import StructuralJuteTool

CLEAN_TXN = {
    "id": "txn_1",
    "amount": "120.50",
    "currency": "USD",
    "status": "settled",
    "timestamp": "2026-05-30T09:00:00Z",
    "account": {"reference": "acct_1"},
}
TRANSACTION_FIELDS = [
    {"field": "id", "kind": "presence", "required": True},
    {"field": "amount", "kind": "datatype", "datatype": "decimal", "required": True},
    {
        "field": "currency",
        "kind": "enum",
        "values": ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "INR"],
        "required": True,
    },
    {
        "field": "status",
        "kind": "enum",
        "values": ["pending", "settled", "failed", "refunded"],
        "required": True,
    },
    {"field": "timestamp", "kind": "datatype", "datatype": "datetime", "required": False},
    {"field": "account", "kind": "presence", "required": True},
]
_CURRENCIES = set(TRANSACTION_FIELDS[2]["values"])
_STATUSES = set(TRANSACTION_FIELDS[3]["values"])


def _decimal_ok(v) -> bool:
    return (
        isinstance(v, str)
        and len(v) > 0
        and v[0].isdigit()
        and all(c.isdigit() or c == "." for c in v)
    )


def _datetime_ok(v) -> bool:
    return (
        isinstance(v, str)
        and len(v) > 0
        and v[0].isdigit()
        and all(c.isdigit() or c in "-T:+.Z" for c in v)
    )


class _TxnValidatorFake:
    """A transaction validator as a Python oracle. `timestamp_mode` toggles the bug."""

    def __init__(self, timestamp_mode: str = "correct") -> None:
        self.timestamp_mode = timestamp_mode  # "correct" | "first_char_only"

    def _ts_ok(self, ts) -> bool:
        if ts is None:
            return True  # optional: absent is valid
        if self.timestamp_mode == "first_char_only":  # recall bug (anchored regex): misses junk
            return isinstance(ts, str) and len(ts) > 0 and ts[0].isdigit()
        if self.timestamp_mode == "over_tight":  # precision bug: only accepts the Z shape it saw
            return isinstance(ts, str) and ts.endswith("Z")
        return _datetime_ok(ts)

    def test_template(self, template: str, txn: dict) -> dict:
        def chk(name, ok):
            return {"name": name, "field": name, "status": "pass" if ok else "fail", "message": ""}

        checks = [
            chk("id", bool(txn.get("id"))),
            chk("amount", _decimal_ok(txn.get("amount"))),
            chk("currency", txn.get("currency") in _CURRENCIES),
            chk("status", txn.get("status") in _STATUSES),
            chk("timestamp", self._ts_ok(txn.get("timestamp"))),
            chk("account", bool(txn.get("account"))),
        ]
        return {"compiled": True, "output": {"request": {"checks": checks}}, "error": None}

    @staticmethod
    def find_checks(output):
        return StructuralJuteTool._find_checks(output)


# --------------------------------------------------------------------------- #
# the operator battery
# --------------------------------------------------------------------------- #
def test_battery_is_exhaustive_not_one_per_class():
    mutants = generate_mutants(CLEAN_TXN, TRANSACTION_FIELDS)
    # far more than the 10-case pack: presence x2, datatype x(2 reqd:5 + opt:4), enum x7 each
    assert len(mutants) >= 25
    labels = {m["label"] for m in mutants}
    # the adversarial one that the original pack lacked
    assert "timestamp:legal_prefix_then_junk" in labels
    assert "amount:legal_prefix_then_junk" in labels
    assert "currency:not_in_set" in labels


def test_optional_field_strip_is_a_pass_control():
    ts = [m for m in field_mutants(CLEAN_TXN, TRANSACTION_FIELDS[4]) if m["op"] == "strip"][0]
    assert ts["expected"] == "PASS"  # timestamp is optional
    id_strip = [m for m in field_mutants(CLEAN_TXN, TRANSACTION_FIELDS[0]) if m["op"] == "strip"][0]
    assert id_strip["expected"] == "BLOCK"  # id is required


# --------------------------------------------------------------------------- #
# the headline: mutation coverage catches the timestamp bug the pack missed
# --------------------------------------------------------------------------- #
def test_buggy_validator_has_the_timestamp_survivor():
    cov = mutation_coverage(
        _TxnValidatorFake("first_char_only"), "tmpl", CLEAN_TXN, TRANSACTION_FIELDS
    )
    assert cov["score"] < 1.0
    survivor_labels = {s["label"] for s in cov["survivors"]}
    assert "timestamp:legal_prefix_then_junk" in survivor_labels  # the exact engagement-3 bug
    # and the survivor is actionable: it carries the value that slipped through
    survivor = next(s for s in cov["survivors"] if s["label"] == "timestamp:legal_prefix_then_junk")
    assert survivor["value"] == "2026!!junk" and survivor["verdict"] == "PASS"


def test_correct_validator_is_complete_against_the_battery():
    cov = mutation_coverage(_TxnValidatorFake("correct"), "tmpl", CLEAN_TXN, TRANSACTION_FIELDS)
    assert cov["score"] == 1.0 and cov["survivors"] == [] and cov["fp"] == []


def test_closing_the_loop_raises_the_score():
    buggy = mutation_coverage(
        _TxnValidatorFake("first_char_only"), "t", CLEAN_TXN, TRANSACTION_FIELDS
    )
    fixed = mutation_coverage(_TxnValidatorFake("correct"), "t", CLEAN_TXN, TRANSACTION_FIELDS)
    assert fixed["score"] > buggy["score"] and fixed["score"] == 1.0


# --------------------------------------------------------------------------- #
# the integration seam: mutants become pack cases the bench loop can gate on
# --------------------------------------------------------------------------- #
def test_mutants_to_cases_are_pack_shaped_and_gate_the_loop():
    cases = mutants_to_cases(CLEAN_TXN, TRANSACTION_FIELDS)
    # pack-shaped: score_template / bench_accept / build_generator consume them unchanged
    assert all(c["expected_structural_verdict"] in ("BLOCK", "PASS") for c in cases)
    assert all(c["artifacts"][0]["content"] for c in cases)
    # gating a CORRECT validator on the battery-as-cases -> accepted; a BUGGY one -> rejected
    assert score_template(_TxnValidatorFake("correct"), "t", cases)["accepted"] is True
    buggy = score_template(_TxnValidatorFake("first_char_only"), "t", cases)
    assert buggy["accepted"] is False
    # the rejection is specifically the timestamp mutant the pack-only oracle lacked
    missed = [r for r in buggy["rows"] if r["exp"] == "BLOCK" and r["verdict"] != "BLOCK"]
    assert any(
        "legal_prefix_then_junk" in r["case_id"] and "timestamp" in r["case_id"] for r in missed
    )


# --------------------------------------------------------------------------- #
# the JOINT gate: recall AND precision are complementary axes that trade off
# --------------------------------------------------------------------------- #
def test_valid_variations_are_all_pass_and_cover_other_valid_shapes():
    vv = valid_variations(CLEAN_TXN, TRANSACTION_FIELDS)
    assert vv and all(m["expected"] == "PASS" for m in vv)
    labels = {m["label"] for m in vv}
    assert "currency:valid:EUR" in labels  # other valid enum codes
    assert any(
        "timestamp:valid:" in label for label in labels
    )  # valid timestamp shapes the clean case lacks


def test_joint_coverage_correct_validator_is_recall_and_precision_complete():
    jc = joint_coverage(_TxnValidatorFake("correct"), "t", CLEAN_TXN, TRANSACTION_FIELDS)
    assert jc["recall"] == 1.0 and jc["precision"] == 1.0 and jc["complete"] is True


def test_joint_coverage_separates_recall_bug_from_precision_bug():
    # first_char_only = a RECALL bug: misses the junk defect, but precision stays clean
    recall_bug = joint_coverage(
        _TxnValidatorFake("first_char_only"), "t", CLEAN_TXN, TRANSACTION_FIELDS
    )
    assert recall_bug["recall"] < 1.0 and recall_bug["precision"] == 1.0
    assert any("legal_prefix_then_junk" in s["label"] for s in recall_bug["survivors"])

    # over_tight = a PRECISION bug: catches every defect but BLOCKS a valid timestamp shape
    prec_bug = joint_coverage(_TxnValidatorFake("over_tight"), "t", CLEAN_TXN, TRANSACTION_FIELDS)
    assert prec_bug["recall"] == 1.0 and prec_bug["precision"] < 1.0
    assert any("timestamp:valid:" in b["label"] for b in prec_bug["precision_breaks"])
    # exactly the failure mode the pack-only / recall-only oracle could not see
    assert prec_bug["complete"] is False
