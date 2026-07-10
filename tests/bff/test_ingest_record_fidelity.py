"""REPRO-1 / R1a — ingest fidelity: ``patient_profile`` survives INGEST end-to-end.

The gap: the non-native ingest envelope (``_to_envelope``, driven by the JUTE-template / LM
path) projects a fixed §4.1 shape and carries only the criteria-required ``*_path`` fields
through — a case's ``patient_profile`` (esp. ``patient_profile.conditions``, the record the
subsumption/upcode floor grounds against) is silently DROPPED. Without R1b's rendered SOURCE
RECORD having anything to render, the paper's centerpiece flip is not reproducible.

The fix lives in ``_ingest_cases`` (owned): after the envelope projection, the source record
``patient_profile`` is merged back onto each produced case by ``case_id`` — deterministic, no
LM, and OPTIONAL (absent record → cases unchanged, never a rejection), exactly like the BYO
label merge. So the record survives every ingest path, not only the native verbatim import.
Generic by construction: the key is a structural envelope field name, never a clinical string.

$0/offline. The native path already imports the record verbatim (test_native_corpus_ingest);
this pins the NON-native (enveloped) path too.
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


def test_record_passthrough_fields_name_patient_profile():
    """The record passthrough set names ``patient_profile`` — the structural record field the
    merge preserves regardless of any contract declaration."""
    assert "patient_profile" in bff._RECORD_PASSTHROUGH_FIELDS


def test_merge_source_record_copies_patient_profile_by_case_id():
    """The R1a merge: a source record's ``patient_profile`` lands on the produced (enveloped)
    case with the same ``case_id`` — the full nested record survives."""
    sample = [
        {
            "case_id": "cv_200",
            "patient_profile": {"conditions": ["Dementia", "Hypertensive disorder"]},
        },
        {"case_id": "cv_201"},  # no record — must be left untouched
    ]
    cases = [
        {"case_id": "cv_200", "artifacts": [{"type": "note", "content": "N"}], "context": "c"},
        {"case_id": "cv_201", "artifacts": [{"type": "note", "content": "N"}], "context": "c"},
    ]
    n = bff._merge_source_record(cases, sample)
    assert n == 1  # only the record-carrying case was enriched
    by_id = {c["case_id"]: c for c in cases}
    assert by_id["cv_200"]["patient_profile"] == {
        "conditions": ["Dementia", "Hypertensive disorder"]
    }
    assert by_id["cv_200"]["patient_profile"]["conditions"] == [
        "Dementia",
        "Hypertensive disorder",
    ]
    # a case whose source carried no record is unchanged (no rejection, no empty record)
    assert "patient_profile" not in by_id["cv_201"]


def test_merge_source_record_is_a_noop_when_no_source_carries_a_record():
    """The default-path parity guard: no source record → every case is byte-unchanged, 0 merged
    (never a spurious empty ``patient_profile``)."""
    sample = [{"case_id": "cv_300"}]
    cases = [{"case_id": "cv_300", "artifacts": [{"type": "n", "content": "N"}]}]
    before = [dict(c) for c in cases]
    assert bff._merge_source_record(cases, sample) == 0
    assert cases == before


def test_merge_source_record_scans_a_rows_wrapper():
    """A JSONL/native decode arrives wrapped (``{rows:[...]}`` / ``{runs:[...]}``); the record
    merge finds the source entries in any top-level list, like the BYO-label merge does."""
    sample = {"rows": [{"case_id": "cv_400", "patient_profile": {"conditions": ["Asthma"]}}]}
    cases = [{"case_id": "cv_400", "artifacts": [{"type": "n", "content": "N"}]}]
    assert bff._merge_source_record(cases, sample) == 1
    assert cases[0]["patient_profile"] == {"conditions": ["Asthma"]}
