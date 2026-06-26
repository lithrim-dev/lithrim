"""INGEST-LABELS-1: the ingest carries BYO ground-truth labels through to the case envelope.

The JUTE transform extracts only grading fields (context, response, the ontology's
required_case_fields), so author-supplied ``expected_compliance_verdict`` /
``expected_safety_flags`` were dropped — the case came back UNLABELED while the agent claimed
otherwise (an over-claim). ``_source_labels_by_id`` + ``_merge_byo_labels`` carry them through
DETERMINISTICALLY (no LM) so the handler can report the HONEST labeled count.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")

import app as bff  # noqa: E402

# The exact payload the user supplies (the {runs:[…]} shape, id == case_id).
_SAMPLE = {
    "runs": [
        {"id": "run_001_fabricates", "expected_compliance_verdict": "reject",
         "expected_safety_flags": ["UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION"]},
        {"id": "run_002_faithful", "expected_compliance_verdict": "approve",
         "expected_safety_flags": []},  # [] IS a label — a declared clean-negative
    ]
}


def test_source_labels_by_id_indexes_byo_labels():
    by_id = bff._source_labels_by_id(_SAMPLE)
    assert by_id["run_001_fabricates"] == {
        "expected_compliance_verdict": "reject",
        "expected_safety_flags": ["UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION"],
    }
    # the empty-list clean-negative IS captured (not skipped) — it's a declared label
    assert by_id["run_002_faithful"] == {
        "expected_compliance_verdict": "approve",
        "expected_safety_flags": [],
    }


def test_source_labels_by_id_top_level_list_and_case_id_key():
    by_id = bff._source_labels_by_id([{"case_id": "c1", "expected_safety_flags": []}])
    assert by_id == {"c1": {"expected_safety_flags": []}}


def test_source_labels_by_id_no_labels_is_empty():
    assert bff._source_labels_by_id({"runs": [{"id": "r1"}]}) == {}
    assert bff._source_labels_by_id({"no": "entries"}) == {}


def test_merge_byo_labels_carries_them_onto_cases_by_case_id():
    """THE FIX: a produced case (grading fields only) gets its BYO labels merged by case_id, and the
    count of labeled cases is returned (the honest number the handler reports)."""
    cases = [
        {"case_id": "run_001_fabricates", "context": "…", "response": "…unlimited storage…"},
        {"case_id": "run_002_faithful", "context": "…", "response": "…100 GB…"},
    ]
    n = bff._merge_byo_labels(cases, _SAMPLE)
    assert n == 2
    assert cases[0]["expected_compliance_verdict"] == "reject"
    assert cases[0]["expected_safety_flags"] == ["UNSUPPORTED_ASSERTION", "SOURCE_CONTRADICTION"]
    assert cases[1]["expected_compliance_verdict"] == "approve"
    assert cases[1]["expected_safety_flags"] == []  # the clean-negative landed


def test_merge_byo_labels_unmatched_case_unchanged():
    cases = [{"case_id": "not_in_source", "context": "…", "response": "…"}]
    n = bff._merge_byo_labels(cases, _SAMPLE)
    assert n == 0
    assert "expected_safety_flags" not in cases[0]  # untouched


def test_merge_byo_labels_no_labels_returns_zero_byte_identical():
    """Back-compat: a source with no expected_* fields leaves every case unchanged (returns 0) —
    so an unlabeled BYO dump behaves exactly as before."""
    cases = [{"case_id": "c1", "context": "x", "response": "y"}]
    before = [dict(c) for c in cases]
    n = bff._merge_byo_labels(cases, {"runs": [{"id": "c1"}]})
    assert n == 0
    assert cases == before
