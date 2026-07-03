"""FIRST-CONTACT-1: the DOCUMENTED first ingest must be $0 and provider-free.

samples/README.md walks a stranger through attaching ``samples/quickstart/notes.jsonl`` /
``notes.csv`` — flat ``{id, note, transcript}`` records — but that shape had no curated
template, so the documented first touch of BYO data silently required a connected LM (and
422'd without one). This registers the flat-notes shape as a KNOWN shape (deterministic,
hand-authored, still live-gated) beside the agent-trace shape.

$0/offline; the live :3031 gate is exercised by the existing known-shape on-mapper test.
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

from lithrim_bench.verification.ingest_decode import decode_records  # noqa: E402

_QS = REPO_ROOT / "samples" / "quickstart"

_FLAT_SAMPLE = {
    "rows": [
        {"id": "n1", "note": "the generated note", "transcript": "the source dialogue"},
        {"id": "n2", "note": "another note", "transcript": "another dialogue"},
    ]
}


def test_flat_notes_shape_resolves_to_the_curated_template():
    tpl = bff._known_shape_template(_FLAT_SAMPLE)
    assert isinstance(tpl, str) and tpl == bff._FLAT_NOTES_TEMPLATE


def test_template_maps_note_to_response_and_dual_emits_the_source():
    tpl = bff._FLAT_NOTES_TEMPLATE
    assert "case_id: $ e.id" in tpl
    assert "response: $ e.note" in tpl
    # FLOOR-SOURCE-1 dual-emit: the council + withstands gate read `transcript`; `context` is
    # kept for back-compat/display — both must carry the source.
    assert "transcript: $ e.transcript" in tpl
    assert "context: $ e.transcript" in tpl


@pytest.mark.parametrize("fname,fmt", [("notes.jsonl", "jsonl"), ("notes.csv", "csv")])
def test_the_shipped_quickstart_samples_match_the_known_shape(fname, fmt):
    """The load-bearing claim: the files samples/README.md tells a stranger to attach FIRST
    resolve deterministically — no LM, no provider, no 422."""
    decoded = decode_records((_QS / fname).read_text(), fmt=fmt, filename=fname)
    tpl = bff._known_shape_template(decoded.sample)
    assert tpl == bff._FLAT_NOTES_TEMPLATE, f"{fname} fell through to the LM-gen path"


@pytest.mark.parametrize(
    "sample",
    [
        pytest.param({"rows": []}, id="empty-rows"),
        pytest.param({"rows": [{"id": "n1", "note": "x"}]}, id="missing-transcript"),
        pytest.param({"rows": [{"id": "n1", "transcript": "x"}]}, id="missing-note"),
        pytest.param({"rows": [{"note": "x", "transcript": "y"}]}, id="missing-id"),
        pytest.param({"rows": [{"id": "n1", "note": {"deep": 1}, "transcript": "y"}]}, id="non-scalar-note"),
    ],
)
def test_near_miss_rows_fall_through_to_the_existing_paths(sample):
    assert bff._known_shape_template(sample) is None


def test_agent_trace_shape_still_wins_its_own_template():
    sample = {"runs": [{"id": "r1", "messages": [{"content": "a"}], "final": {"content": "b"}}]}
    assert bff._known_shape_template(sample) == bff._AGENT_TRACE_TEMPLATE
