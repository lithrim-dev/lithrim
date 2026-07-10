"""Tests for WorstOfBackend composition rule.

Covers all 9 combinations of (semantic_artifact, structural_artifact) and
verifies the lifted compliance correctly escalates.
"""

import pytest

from lithrim_bench.backends.base import (
    BackendClient,
    BackendPin,
    BackendVerdict,
    JudgeOutput,
)
from lithrim_bench.backends.worst_of import WorstOfBackend


class _Fixed(BackendClient):
    def __init__(self, verdict: BackendVerdict, name: str = "fixed"):
        self._verdict = verdict
        self._name = name

    @property
    def pin(self) -> BackendPin:
        return BackendPin(backend=self._name, backend_version="test")

    def evaluate(self, case):
        return self._verdict


def _semantic(compliance: str, artifact: str, flags=()):
    return BackendVerdict(
        compliance_verdict=compliance,
        artifact_verdict=artifact,
        flags=list(flags),
        per_judge={"policy_judge": JudgeOutput("policy_judge", compliance)},
        structural_verdict=None,
        structural_findings=[],
    )


def _structural(artifact: str, findings=()):
    return BackendVerdict(
        compliance_verdict="approve",
        artifact_verdict=artifact,
        flags=[],
        structural_verdict=artifact,
        structural_findings=list(findings),
    )


@pytest.mark.parametrize(
    "sem_art,struct_art,want_artifact,want_compliance",
    [
        ("PASS", "PASS", "PASS", "approve"),
        ("PASS", "WARN", "WARN", "needs_review"),
        ("PASS", "BLOCK", "BLOCK", "reject"),
        ("WARN", "PASS", "WARN", "needs_review"),
        ("WARN", "WARN", "WARN", "needs_review"),
        ("WARN", "BLOCK", "BLOCK", "reject"),
        ("BLOCK", "PASS", "BLOCK", "reject"),
        ("BLOCK", "WARN", "BLOCK", "reject"),
        ("BLOCK", "BLOCK", "BLOCK", "reject"),
    ],
)
def test_worst_of_artifact_and_lifted_compliance(
    sem_art, struct_art, want_artifact, want_compliance
):
    semantic_compliance = {"PASS": "approve", "WARN": "needs_review", "BLOCK": "reject"}[sem_art]
    sem = _Fixed(_semantic(semantic_compliance, sem_art))
    struct = _Fixed(_structural(struct_art))
    v = WorstOfBackend(semantic=sem, structural=struct).evaluate({"case_id": "x"})
    assert v.artifact_verdict == want_artifact
    assert v.compliance_verdict == want_compliance


def test_flags_are_union_sorted_unique():
    sem = _Fixed(_semantic("reject", "BLOCK", flags=["WRONG_DOSAGE", "MISSING_ALLERGY"]))
    struct = _Fixed(_structural("BLOCK", findings=["STRUCTURAL_MALFORMED_DATE", "WRONG_DOSAGE"]))
    v = WorstOfBackend(semantic=sem, structural=struct).evaluate({"case_id": "x"})
    assert v.flags == ["MISSING_ALLERGY", "STRUCTURAL_MALFORMED_DATE", "WRONG_DOSAGE"]


def test_structural_verdict_passed_through_from_structural():
    sem = _Fixed(_semantic("approve", "PASS"))
    struct = _Fixed(_structural("BLOCK", findings=["STRUCTURAL_MALFORMED_DATE"]))
    v = WorstOfBackend(semantic=sem, structural=struct).evaluate({"case_id": "x"})
    assert v.structural_verdict == "BLOCK"
    assert v.structural_findings == ["STRUCTURAL_MALFORMED_DATE"]


def test_per_judge_passes_through_from_semantic():
    sem = _Fixed(_semantic("reject", "BLOCK"))
    struct = _Fixed(_structural("PASS"))
    v = WorstOfBackend(semantic=sem, structural=struct).evaluate({"case_id": "x"})
    assert v.per_judge is not None
    assert "policy_judge" in v.per_judge


def test_pin_records_both_sub_backends():
    sem = _Fixed(_semantic("approve", "PASS"), name="sem-x")
    struct = _Fixed(_structural("PASS"), name="struct-y")
    pin = WorstOfBackend(semantic=sem, structural=struct).pin
    assert pin.backend == "WorstOfBackend"
    assert pin.extra["semantic"]["backend"] == "sem-x"
    assert pin.extra["structural"]["backend"] == "struct-y"


def test_worst_of_rank_skips_structural_not_applicable_and_preserves_in_report():
    """BRS-0b: WorstOfBackend must treat a structural artifact_verdict of
    'not_applicable' as rank-0 (semantic dominates) AND surface
    structural_verdict='not_applicable' on the composed BackendVerdict.

    This locks the no-code-change invariant: `.get(..., default)` in
    `_worst` and `_LIFT_TO_COMPLIANCE` naturally rank-skip unknown
    statuses, while the structural_verdict pass-through (worst_of.py:89)
    preserves the reporting distinction. If a future refactor changes
    composition behavior on 'not_applicable', this test catches it.
    """
    sem = _Fixed(_semantic("reject", "BLOCK", flags=["WRONG_DOSAGE"]))
    struct = BackendVerdict(
        compliance_verdict="approve",
        artifact_verdict="not_applicable",
        flags=[],
        structural_verdict="not_applicable",
        structural_findings=[],
    )
    composed = WorstOfBackend(semantic=sem, structural=_Fixed(struct)).evaluate({"case_id": "x"})
    # semantic dominates because not_applicable is rank-skipped
    assert composed.artifact_verdict == "BLOCK"
    assert composed.compliance_verdict == "reject"
    # reporting preserves the distinct status (worst_of.py:89 passthrough)
    assert composed.structural_verdict == "not_applicable"
