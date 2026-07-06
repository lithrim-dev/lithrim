"""REPRO-1 / R1b — the RECORD reaches the judge (authored-stage rendering).

The paper-blocking gap: the authored semantic stage forwards ``transcript`` + ``artifact``
to each judge ONLY — a case's structured record (``patient_profile`` in the research corpus)
never reaches the judge prompt, so the subsumption/upcode check grades incomplete input.

This closes it AT THE AUTHORED STAGE (``runtime/council/authored_stage.py``): whenever the
graded case carries a ``patient_profile`` (a generic record the case supplies, no ontology
declaration required), the authored evaluator renders it as a delimited SOURCE RECORD section
folded into the ``transcript`` the judges vote on. Data-driven + generic by construction: the
record VALUES are whatever the case carries; core renders the section, never clinical strings.

$0/offline: injected per-role predictors capture the exact ``transcript`` each judge was fed;
no dspy compile, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

from lithrim_bench.harness.grade import grade_inprocess  # noqa: E402
from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.runtime.council.authored_stage import (  # noqa: E402
    build_authored_semantic_stage,
)
from lithrim_bench.runtime.council.judges_dspy import V2_ROLES  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE_ONTOLOGY_PATH = _REPO / "packs" / "support_ticket_qa" / "ontology.json"


def _transcript_recording_predictors(captured: dict):
    """Per-role predictors that record the exact ``transcript`` they were fed and always
    approve. Pure dict-returning callables; no dspy / no network."""

    def make(role):
        def _p(*, transcript: str = "", **_kw):
            captured[role] = transcript
            return {"decision": "approve", "findings": []}

        return _p

    return {role: make(role) for role in V2_ROLES}


def _case_with_record():
    return {
        "case_id": "cv_100_record",
        "transcript": "Doctor: what brings you in?\n\nPatient: my memory has been slipping.",
        "patient_profile": {
            "conditions": ["Dementia", "Hypertensive disorder"],
        },
        "artifacts": [{"type": "note", "content": "Assessment: cognitive decline."}],
    }


def _case_without_record():
    return {
        "case_id": "cv_101_norecord",
        "transcript": "Doctor: hello.\n\nPatient: hi.",
        "artifacts": [{"type": "note", "content": "Assessment: well."}],
    }


def test_patient_profile_is_rendered_into_the_judge_transcript():
    """The centerpiece: a case carrying ``patient_profile`` renders its record into the
    transcript EVERY judge votes on — no ontology declaration required."""
    ont = load_ontology(_FIXTURE_ONTOLOGY_PATH)
    cap: dict = {}
    stage = build_authored_semantic_stage(
        ontology=ont,
        assignments=None,
        predictors=_transcript_recording_predictors(cap),
    )
    grade_inprocess(_case_with_record(), semantic_stage=stage)

    # the record reaches EVERY judge, not just one
    assert set(cap) == set(V2_ROLES)
    for role, seen in cap.items():
        assert "Dementia" in seen, f"{role} never saw the record's conditions"
        assert "Hypertensive disorder" in seen, f"{role} saw an incomplete record"
        # a labeled SOURCE RECORD section, not the bare conditions smuggled in
        assert "SOURCE RECORD" in seen
        # the original transcript is preserved alongside the record
        assert "my memory has been slipping" in seen


def test_record_is_not_double_rendered_when_already_folded():
    """Idempotency: if the declared grading_context_fields fold already put the record's SOURCE
    RECORD section in the transcript, the authored render does NOT append a second copy."""
    from lithrim_bench.runtime.council.authored_stage import _fold_record_into_transcript

    already = (
        "Doctor: hi\n\n--- SOURCE RECORD: patient_profile ---\n"
        '{\n "conditions": [\n  "Dementia"\n ]\n}'
    )
    call_context = {
        "transcript": already,
        "patient_profile": {"conditions": ["Dementia"]},
    }
    out = _fold_record_into_transcript(already, call_context)
    assert out == already  # not appended a second time
    assert out.count("SOURCE RECORD: patient_profile") == 1


def test_no_record_leaves_the_transcript_byte_identical():
    """A case with no record is byte-unchanged: the judge sees exactly its transcript, no
    empty SOURCE RECORD section (the default-path parity guard)."""
    ont = load_ontology(_FIXTURE_ONTOLOGY_PATH)
    cap: dict = {}
    stage = build_authored_semantic_stage(
        ontology=ont,
        assignments=None,
        predictors=_transcript_recording_predictors(cap),
    )
    case = _case_without_record()
    grade_inprocess(case, semantic_stage=stage)

    for seen in cap.values():
        assert seen == case["transcript"]
        assert "SOURCE RECORD" not in seen
