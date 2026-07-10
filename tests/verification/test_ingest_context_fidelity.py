"""Ingest fidelity: the grading CONTEXT (e.g. a clinical transcript) must survive ingestion,
and a transform that DROPS it must be REJECTED — not silently pinned.

Diagnosis (live dogfood 2026-06-17, Clinical Scribe Review scribe push): `_to_envelope` assembled
`context` from NARRATIVE-only keys, so a clinical record carrying `transcript` produced
`context="{}"` — the SOAP survived but the thing it is graded AGAINST was lost. And
`_REQUIRED_KEYS=("case_id","response")` did not require `context`, so `score_extraction`
ACCEPTED the lossy transform → pinned + reused. This is the exact silent-degradation the
suite exists to catch, occurring inside our own ingest.

Contract (Phase 1): the envelope is DOMAIN-AGNOSTIC — an explicit `context`/`transcript`
on the record is carried verbatim; the narrative `ctx_bits` assembly remains the fallback
(StoryWorld unchanged). The structural invariant additionally requires every enveloped case
to have a NON-EMPTY `context` and graded content; a dropped context fails the gate.

Offline: no `:3031`, no LLM (a tiny fake client returns a fixed apply array).
"""

from __future__ import annotations

import pytest

from lithrim_bench.verification.jute_extractor import _to_envelope, score_extraction

# a clinical scribe record (the shape a scribe→lithrim-sdk push normalizes to): the SOAP is
# `response`; the transcript it is graded against rides `context`.
CLINICAL = {
    "case_id": "clinical_scribe_01",
    "response": "S (Subjective): cramps in feet and hands ...",
    "context": "Doctor: Tell me what brings you here?\nPatient: I'm having these cramps ...",
}
# the BUG shape: the transform dropped the transcript — case_id+response present, no context.
CLINICAL_NO_CONTEXT = {
    "case_id": "clinical_scribe_01",
    "response": "S (Subjective): cramps in feet and hands ...",
}
# a narrative record (StoryWorld §4.2 per-scene shape) — context is assembled from these keys.
NARRATIVE = {
    "case_id": "story-jinn-n1",
    "response": "The lantern flickered as Layla stepped into the souk ...",
    "story_id": "jinn", "mode": "adult", "language": "en", "node": "n1",
    "scene_title": "The Souk", "source": "enhanced",
}


class _FakeClient:
    """Returns a fixed apply array; the template string is ignored (the array IS the oracle)."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def test_template(self, template, sample_input):
        return {"compiled": True, "output": self.rows, "error": None}


# --------------------------------------------------------------------------- #
# _to_envelope is domain-agnostic
# --------------------------------------------------------------------------- #
def test_to_envelope_carries_clinical_transcript():
    """A record's explicit `context` (the clinical transcript) survives into the envelope —
    it is NOT overwritten by the empty narrative ctx_bits assembly (today: context='{}')."""
    env = _to_envelope(CLINICAL)
    assert "Doctor:" in env["context"], f"transcript dropped: context={env['context']!r}"
    assert env["artifacts"] and env["artifacts"][0]["content"]  # SOAP survives


def test_to_envelope_accepts_transcript_alias():
    """`transcript` is honored as an alias for `context` (scribe pushes name it that)."""
    env = _to_envelope({"case_id": "c1", "response": "soap", "transcript": "Doctor: hi"})
    assert "Doctor:" in env["context"]


def test_to_envelope_narrative_backcompat():
    """StoryWorld unchanged: with no explicit context, the narrative ctx_bits assembly still
    produces a non-empty context carrying the scene keys."""
    env = _to_envelope(NARRATIVE)
    assert env["context"] and env["context"] != "{}"
    assert '"node"' in env["context"] and '"story_id"' in env["context"]


# --------------------------------------------------------------------------- #
# the structural invariant requires the grading context to survive
# --------------------------------------------------------------------------- #
def test_invariant_rejects_dropped_context():
    """case_id + response present but NO context → the SOAP would be graded against nothing →
    the transform MUST be rejected (today it is wrongly ACCEPTED)."""
    s = score_extraction(_FakeClient([CLINICAL_NO_CONTEXT]), "tmpl", {}, expected_count=1)
    assert s["accepted"] is False, "a context-dropping transform must NOT be accepted"
    assert "context" in (s["null_keys"] or []), s["null_keys"]
    assert s["cases"] == []  # nothing to pin


def test_invariant_accepts_context_carrying_transform():
    """The corrected clinical transform (context carried) is accepted and the enveloped case
    holds the transcript."""
    s = score_extraction(_FakeClient([CLINICAL]), "tmpl", {}, expected_count=1)
    assert s["accepted"] is True, s
    assert "Doctor:" in s["cases"][0]["context"]


def test_invariant_accepts_narrative_unchanged():
    """Regression guard: the narrative path (context assembled from scene keys) still accepts."""
    rows = [dict(NARRATIVE, case_id=f"story-jinn-n{i}", node=f"n{i}") for i in range(1, 6)]
    s = score_extraction(_FakeClient(rows), "tmpl", {}, expected_count=5)
    assert s["accepted"] is True and len(s["cases"]) == 5


@pytest.mark.parametrize("ctx", ["", "   ", "null", "None", {}, [], "{}", "[]"])
def test_invariant_rejects_every_empty_context_form(ctx):
    """The contract enumerates ``""``/``{}``/``[]``/``null`` as empty — a transform producing
    ANY of them (whether the value is a literal empty string/dict/list or the JSON-serialized
    ``"{}"``/``"[]"``/``"null"``) must be rejected, not just the missing-key form."""
    rec = {"case_id": "c1", "response": "S (Subjective): ...", "context": ctx}
    s = score_extraction(_FakeClient([rec]), "tmpl", {}, expected_count=1)
    assert s["accepted"] is False, f"empty context {ctx!r} must be rejected"
    assert "context" in s["null_keys"]
    assert s["cases"] == []
