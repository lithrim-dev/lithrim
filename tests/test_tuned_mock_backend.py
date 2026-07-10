"""Tests for TunedMockBackend.

Covers: the categorical-blindness invariant (structural_verdict is
always None regardless of input), the ensemble majority-vote lift over
single-member accuracy, deterministic seeding, and the per_judge
emission contract.
"""
from lithrim_bench.backends import TunedMockBackend


def _case_with_flags(flags: list[str], expected: str = "reject") -> dict:
    return {
        "case_id": "demo_case",
        "pack": "scribe_v1",
        "agent_type": "scribe",
        "transcript": "...",
        "artifacts": [],
        "expected_compliance_verdict": expected,
        "expected_safety_flags": flags,
    }


def test_categorical_blindness_invariant_for_structural_only_case():
    case = _case_with_flags(["STRUCTURAL_MALFORMED_DATE"], expected="reject")
    case["expected_structural_verdict"] = "BLOCK"
    backend = TunedMockBackend(ensemble_size=5, noise_seed=42)
    for _ in range(20):
        v = backend.evaluate(case)
        assert v.structural_verdict is None
        assert v.structural_findings == []


def test_purely_semantic_case_gets_majority_reject_at_default_accuracy():
    case = _case_with_flags(["WRONG_DOSAGE"], expected="reject")
    backend = TunedMockBackend(
        ensemble_size=3, per_member_semantic_accuracy=0.85, noise_seed=7
    )
    correct = 0
    n = 200
    for i in range(n):
        case["case_id"] = f"sem_{i}"
        v = backend.evaluate(case)
        if v.compliance_verdict == "reject":
            correct += 1
    rate = correct / n
    assert rate > 0.85


def test_K_eq_1_collapses_to_single_member_accuracy():
    case = _case_with_flags(["WRONG_DOSAGE"], expected="reject")
    backend = TunedMockBackend(
        ensemble_size=1, per_member_semantic_accuracy=0.6, noise_seed=11
    )
    correct = 0
    n = 500
    for i in range(n):
        case["case_id"] = f"single_{i}"
        v = backend.evaluate(case)
        if v.compliance_verdict == "reject":
            correct += 1
    rate = correct / n
    assert 0.55 <= rate <= 0.65


def test_per_judge_emits_ensemble_members():
    case = _case_with_flags(["WRONG_DOSAGE"])
    backend = TunedMockBackend(ensemble_size=3, noise_seed=1)
    v = backend.evaluate(case)
    assert v.per_judge is not None
    assert set(v.per_judge.keys()) == {"tuned_member_0", "tuned_member_1", "tuned_member_2"}


def test_deterministic_same_seed_same_output():
    case = _case_with_flags(["WRONG_DOSAGE"])
    a = TunedMockBackend(ensemble_size=3, noise_seed=99).evaluate(case)
    b = TunedMockBackend(ensemble_size=3, noise_seed=99).evaluate(case)
    assert a.compliance_verdict == b.compliance_verdict
    assert a.flags == b.flags


def test_clean_case_with_low_fp_rate_mostly_approves():
    case = _case_with_flags([], expected="approve")
    backend = TunedMockBackend(
        ensemble_size=3, false_positive_rate=0.02, noise_seed=3
    )
    approves = 0
    n = 200
    for i in range(n):
        case["case_id"] = f"clean_{i}"
        v = backend.evaluate(case)
        if v.compliance_verdict == "approve":
            approves += 1
    assert approves / n > 0.95


def test_pin_records_lit_anchor_and_blindness_contract():
    backend = TunedMockBackend(ensemble_size=3)
    pin = backend.pin
    assert pin.extra["structural_blind_by_contract"] is True
    assert "Lail" in pin.extra["lit_anchor"]
