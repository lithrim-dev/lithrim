"""REPRO-1 / R1b — the RECORD reaches the judge (authored-stage rendering).

The paper-blocking gap: the authored semantic stage forwards ``transcript`` + ``artifact``
to each judge ONLY — a case's structured source record (the problem list / account state the
grounding floor reasons over) never reached the judge prompt, so the record-vs-artifact
fidelity check graded incomplete input.

This closes it AT THE AUTHORED STAGE (``runtime/council/authored_stage.py``): the agent declares
the record field name(s) in its ontology ``grading_context_fields`` (DATA), and the authored
evaluator folds those case fields into the ``transcript`` the judges vote on as delimited SOURCE
RECORD sections. Fully data-driven + generic by construction: core hardcodes NO field name — it
renders whatever fields the config declares. The test below uses an arbitrary non-standard field
name (``account_profile``) to prove core is field-agnostic; the healthcare pack declares its own.

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

# The record field the agent declares (DATA) — a deliberately NON-standard, non-clinical name to
# prove the fold is driven by config, not a core-hardcoded field. The healthcare pack declares
# its own field name; core carries none.
_RECORD_FIELD = "account_profile"


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
        "transcript": "Agent: how can I help?\n\nUser: my subscription renewed unexpectedly.",
        _RECORD_FIELD: {
            "entitlements": ["Pro tier", "Priority support"],
        },
        "artifacts": [{"type": "note", "content": "Summary: billing dispute."}],
    }


def _case_without_record():
    return {
        "case_id": "cv_101_norecord",
        "transcript": "Agent: hello.\n\nUser: hi.",
        "artifacts": [{"type": "note", "content": "Summary: greeting."}],
    }


def test_declared_record_is_rendered_into_the_judge_transcript():
    """The centerpiece: a case whose agent declares a ``grading_context_fields`` record renders
    that record into the transcript EVERY judge votes on — the record reaches the judge. Config
    declares the field NAME (here ``account_profile``); core folds whatever is declared."""
    ont = load_ontology(_FIXTURE_ONTOLOGY_PATH)
    cap: dict = {}
    stage = build_authored_semantic_stage(
        ontology=ont,
        assignments=None,
        predictors=_transcript_recording_predictors(cap),
    )
    grade_inprocess(
        _case_with_record(), semantic_stage=stage, context_fields=(_RECORD_FIELD,)
    )

    # the record reaches EVERY judge, not just one
    assert set(cap) == set(V2_ROLES)
    for role, seen in cap.items():
        assert "Pro tier" in seen, f"{role} never saw the record's contents"
        assert "Priority support" in seen, f"{role} saw an incomplete record"
        # a labeled SOURCE RECORD section, not the bare values smuggled in
        assert f"SOURCE RECORD: {_RECORD_FIELD}" in seen
        # the original transcript is preserved alongside the record
        assert "my subscription renewed unexpectedly" in seen


def test_record_is_not_double_rendered_when_already_folded():
    """Idempotency: if the declared grading_context_fields fold already put the record's SOURCE
    RECORD section in the transcript string, the authored render does NOT append a second copy."""
    from lithrim_bench.runtime.council.authored_stage import _fold_record_into_transcript

    already = (
        f"Agent: hi\n\n--- SOURCE RECORD: {_RECORD_FIELD} ---\n"
        '{\n "entitlements": [\n  "Pro tier"\n ]\n}'
    )
    call_context = {
        "transcript": already,
        "record": {_RECORD_FIELD: {"entitlements": ["Pro tier"]}},
    }
    out = _fold_record_into_transcript(already, call_context)
    assert out == already  # not appended a second time
    assert out.count(f"SOURCE RECORD: {_RECORD_FIELD}") == 1


def test_no_declared_record_leaves_the_transcript_byte_identical():
    """A case with no declared record is byte-unchanged: the judge sees exactly its transcript,
    no empty SOURCE RECORD section (the default-path parity guard). Even a case that HAS a record
    object grades unchanged when the agent declared NO grading_context_fields — the fold is
    strictly config-gated."""
    ont = load_ontology(_FIXTURE_ONTOLOGY_PATH)
    cap: dict = {}
    stage = build_authored_semantic_stage(
        ontology=ont,
        assignments=None,
        predictors=_transcript_recording_predictors(cap),
    )
    case = _case_without_record()
    grade_inprocess(case, semantic_stage=stage)  # no context_fields declared
    for seen in cap.values():
        assert seen == case["transcript"]
        assert "SOURCE RECORD" not in seen

    # a case carrying a record object but with NO declaration is still byte-unchanged
    cap2: dict = {}
    stage2 = build_authored_semantic_stage(
        ontology=ont,
        assignments=None,
        predictors=_transcript_recording_predictors(cap2),
    )
    with_record = _case_with_record()
    grade_inprocess(with_record, semantic_stage=stage2)  # still no context_fields
    for seen in cap2.values():
        assert seen == with_record["transcript"]
        assert "SOURCE RECORD" not in seen
