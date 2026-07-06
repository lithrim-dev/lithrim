"""REPRO-1 / R1a — ingest fidelity: ``patient_profile`` survives INGEST end-to-end.

The gap: the non-native ingest envelope (``_to_envelope``, driven by the JUTE-template / LM
path) projects a fixed §4.1 shape and carries only the criteria-required ``*_path`` fields
through — a case's ``patient_profile`` (esp. ``patient_profile.conditions``, the record the
subsumption/upcode floor grounds against) is silently DROPPED. Without R1b's rendered SOURCE
RECORD having anything to render, the paper's centerpiece flip is not reproducible.

The fix lives in ``_ingest_cases`` (owned): the record ``patient_profile`` is ALWAYS a
structural passthrough field for the envelope, independent of any contract declaration — so it
survives every ingest path, not only the native verbatim import. Generic by construction: the
key is a structural envelope field name, never a clinical string.

$0/offline. The native path already imports the record verbatim (test_native_corpus_ingest);
this pins the NON-native envelope path too.
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


def test_record_passthrough_fields_always_include_patient_profile():
    """The passthrough set the envelope carries always names ``patient_profile`` — so the
    record survives regardless of whether an ontology/contract declared it."""
    fields = bff._record_passthrough_fields(())
    assert "patient_profile" in fields


def test_declared_criteria_fields_are_unioned_not_replaced():
    """A contract's declared ``*_path`` field (gap #4) is preserved AND the record is added —
    the record passthrough never drops a criteria-required field."""
    fields = bff._record_passthrough_fields(("record.entities",))
    assert "patient_profile" in fields
    assert "record.entities" in fields


def test_to_envelope_preserves_patient_profile_with_the_passthrough_set():
    """End-to-end at the envelope: given the R1a passthrough set, ``_to_envelope`` keeps the
    full record (this is the projection the ingest paths feed)."""
    from lithrim_bench.verification.jute_extractor import _to_envelope

    rec = {
        "case_id": "cv_200",
        "response": "THE NOTE",
        "transcript": "Doctor: hello",
        "patient_profile": {"conditions": ["Dementia", "Hypertensive disorder"]},
    }
    env = _to_envelope(rec, bff._record_passthrough_fields(()))
    assert env["patient_profile"] == {"conditions": ["Dementia", "Hypertensive disorder"]}
    assert env["patient_profile"]["conditions"] == ["Dementia", "Hypertensive disorder"]
