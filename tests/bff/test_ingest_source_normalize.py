"""FLOOR-SOURCE-INGEST-1: normalize the source field at ingest so the council grades a
self-contained case.

An ingested agent-trace case stores its source under ``context``; the council grade path reads
the source from ``transcript`` ONLY (``ab_harness.py`` ``call_context.transcript``, the
``authored_stage`` ``case_view.transcript``, the per-judge ``SourceGrounding``). So a faithful
ingested case was graded against an EMPTY source → a judge spuriously raised
``UNSUPPORTED_ASSERTION``, the withstands gate's ``SourceGrounding`` returned ``disproved=False``
(its own answer tokens all ungrounded), and the council persisted a WRONG **BLOCK** — while the
report ``composite`` (which alone falls back ``transcript → context``) showed PASS, so the two
surfaces disagreed.

The fix normalizes ONCE at ingest (``_normalize_case_source`` copies ``context`` → ``transcript``
when ``transcript`` is empty) so the judges, the withstands gate, AND ``grounding.ground()`` read
the SAME populated source — retiring the per-consumer ``or context`` mapping (the FLOOR-SOURCE-1
anti-pattern). This test pins (a) the helper's copy/idempotence/back-compat behaviour, (b) the
``_AGENT_TRACE_TEMPLATE`` self-contained-output line, and (c) the ROOT contract flip at the
``SourceGrounding`` level: populating ``transcript`` flips a faithful case's ``source_grounding``
outcome the withstands gate reads from False → True.
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


# ── (1) _normalize_case_source: copy context → transcript when transcript is empty ──────────────
def test_normalize_copies_context_to_transcript_when_empty():
    cases = [{"case_id": "c", "context": "the source text", "response": "r"}]
    n = bff._normalize_case_source(cases)
    assert n == 1
    assert cases[0]["transcript"] == "the source text"


def test_normalize_idempotent_existing_transcript_unchanged():
    """A case that ALREADY has a non-empty transcript is left byte-unchanged (its transcript is
    NOT overwritten by context); contributes 0 to the count."""
    cases = [{"case_id": "c", "transcript": "real transcript", "context": "other", "response": "r"}]
    n = bff._normalize_case_source(cases)
    assert n == 0
    assert cases[0]["transcript"] == "real transcript"  # not overwritten by context


def test_normalize_no_context_leaves_case_unchanged():
    """A case with no/empty context is left unchanged — no transcript key added, no crash."""
    cases = [{"case_id": "c", "response": "r"}]
    n = bff._normalize_case_source(cases)
    assert n == 0
    assert "transcript" not in cases[0]

    cases_empty_ctx = [{"case_id": "c", "context": "", "response": "r"}]
    n2 = bff._normalize_case_source(cases_empty_ctx)
    assert n2 == 0
    assert "transcript" not in cases_empty_ctx[0]


def test_normalize_whitespace_only_transcript_is_empty():
    """A whitespace-only transcript is treated as empty (per _ctx_nonempty) and normalized."""
    cases = [{"case_id": "c", "transcript": "   \n  ", "context": "the source text", "response": "r"}]
    n = bff._normalize_case_source(cases)
    assert n == 1
    assert cases[0]["transcript"] == "the source text"


def test_normalize_idempotent_second_pass_no_change():
    """Running the normalization twice changes nothing on the second pass (idempotent)."""
    cases = [{"case_id": "c", "context": "the source text", "response": "r"}]
    bff._normalize_case_source(cases)
    snapshot = [dict(c) for c in cases]
    n2 = bff._normalize_case_source(cases)
    assert n2 == 0
    assert cases == snapshot


# ── (3) _AGENT_TRACE_TEMPLATE emits both a transcript: line and a context: line ────────────────
def test_agent_trace_template_emits_both_transcript_and_context():
    """The curated JUTE emits the canonical source under BOTH ``transcript`` (new, self-contained)
    and ``context`` (kept for back-compat/display), both using the same join expression.

    MUTATION the driver names: drop the new ``transcript:`` line from ``_AGENT_TRACE_TEMPLATE`` and
    this assertion goes RED."""
    tmpl = bff._AGENT_TRACE_TEMPLATE
    join_expr = 'joinStr("\\n\\n", e.messages.*.content)'
    assert f"transcript: $ {join_expr}" in tmpl
    assert f"context: $ {join_expr}" in tmpl


# ── The money test — the floor-source fix at the SourceGrounding contract level (offline) ──────
# Test-fidelity note: the driver's example answer "100 GB storage; email support included." does
# NOT fully ground against its source because SourceGrounding's light-stemmer maps "included" →
# "includ" while the source's "includes" → "include" (an ed-strip vs s-strip desync that is a real
# property of grounding.py, OUT of scope to change). We adjust the ANSWER wording to
# "100 GB storage and email support." so EVERY salient token (100, email, storage, support) is in
# the source — a genuinely faithful pair — exactly as the driver authorizes (tweak the TEST to the
# real SourceGrounding.check contract; never edit grounding.py).
def test_source_grounding_flips_when_transcript_populated():
    from lithrim_bench.harness.grounding import SourceGrounding
    from lithrim_bench.harness.ontology import VerificationContractDecl

    decl = VerificationContractDecl(
        flag_code="UNSUPPORTED_ASSERTION",
        contract_type="source_grounding",
        params={},
        version="",
        question="",
    )
    sg = SourceGrounding(decl)

    source = "The plan includes 100 GB of storage and email support."
    answer = "100 GB storage and email support."
    finding = {"code": "UNSUPPORTED_ASSERTION"}

    # BUG shape — the empty source the council actually saw (transcript empty, the ingested
    # source stranded on context): the faithful answer's salient tokens are ALL ungrounded → the
    # finding STANDS → the false BLOCK.
    bug = sg.check(finding, {"transcript": "", "artifacts": [{"content": answer}]})
    assert bug.disproved is False

    # FIXED shape — after _normalize_case_source populates transcript: every salient claim is in
    # the source → the floor disproves the finding → the false alarm clears.
    fixed = sg.check(finding, {"transcript": source, "artifacts": [{"content": answer}]})
    assert fixed.disproved is True
