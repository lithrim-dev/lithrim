"""Front-door decode shim (CE-INGEST-FRONTDOOR-1, Stage 1a): turn an uploaded JSON / JSONL / CSV
blob into the ``sample`` the existing JUTE ingest engine consumes — parse-in-Python, map-in-JUTE.

The thesis line (harness-jute-is-the-safe-transform-dsl): the model never emits server-executed
parsing; *decoding* a serialization (splitting JSONL lines, reading CSV rows) is plain Python, and
the semantic field-mapping stays JUTE. CSV/JSONL are generic serializations, NOT source-specific
schemas, so this stays inside "ingestion stays generic JUTE".

The shim is pure + dependency-free (no fastapi, no dspy, no :3031) → runs in any interpreter.
"""

from __future__ import annotations

import pytest

from lithrim_bench.verification.ingest_decode import DecodeResult, decode_records


# ── JSON ──────────────────────────────────────────────────────────────────────
def test_json_object_passes_through_unwrapped():
    r = decode_records('{"resource": {"id": "s"}}', fmt="json")
    assert isinstance(r, DecodeResult)
    assert r.fmt == "json"
    assert r.sample == {"resource": {"id": "s"}}
    assert r.expected_count is None  # a dict: let the engine infer (enhanced_scenes / hint)
    assert r.iterated_collection is None


def test_json_top_level_array_sets_expected_count():
    r = decode_records('[{"id": "a"}, {"id": "b"}, {"id": "c"}]', fmt="json")
    assert r.sample == [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert r.expected_count == 3
    assert r.iterated_collection is None  # top-level list is handled natively by the engine


def test_json_object_with_nested_array_autodetects_the_collection():
    """An arbitrary {key:[records]} object → detect the dominant nested list-of-records as the
    iteration unit (count + hint), so the engine doesn't fall back to its un-hinted =1 gate.
    The preview is the validation gate, so an auto-guess is shown for approval, never silent."""
    blob = '{"trace": "x", "episodes": [{"eid": "e1"}, {"eid": "e2"}, {"eid": "e3"}]}'
    r = decode_records(blob, fmt="json")
    assert r.expected_count == 3
    assert r.iterated_collection == "episodes"


def test_json_object_picks_the_dominant_list_of_records():
    """Multiple nested arrays → the longest list-of-records wins (the {issues,comments} shape)."""
    blob = '{"issues": [{"n": 1}, {"n": 2}], "comments": [{"c": 1}, {"c": 2}, {"c": 3}]}'
    r = decode_records(blob, fmt="json")
    assert r.expected_count == 3
    assert r.iterated_collection == "comments"


def test_json_object_ignores_scalar_lists():
    """A list of scalars (e.g. tags) is not a case collection — only list-of-records counts."""
    blob = '{"tags": ["a", "b", "c", "d"], "rows": [{"id": "r1"}, {"id": "r2"}]}'
    r = decode_records(blob, fmt="json")
    assert r.expected_count == 2
    assert r.iterated_collection == "rows"


def test_json_object_no_record_array_defers_to_engine():
    """No nested list-of-records → expected_count stays None (the engine's inference / =1 gate)."""
    r = decode_records('{"resource": {"metadata": {"enhanced_scenes": {"a": {}}}}}', fmt="json")
    assert r.expected_count is None
    assert r.iterated_collection is None


# ── JSONL ─────────────────────────────────────────────────────────────────────
def test_jsonl_splits_lines_and_wraps_in_rows():
    blob = '{"id": "a", "note": "x"}\n{"id": "b", "note": "y"}\n'
    r = decode_records(blob, fmt="jsonl")
    assert r.fmt == "jsonl"
    assert r.sample == {"rows": [{"id": "a", "note": "x"}, {"id": "b", "note": "y"}]}
    assert r.expected_count == 2
    assert r.iterated_collection == "rows"  # the engine hint: one case per `rows` entry


def test_jsonl_ignores_blank_lines():
    blob = '{"id": "a"}\n\n   \n{"id": "b"}\n'
    r = decode_records(blob, fmt="jsonl")
    assert r.expected_count == 2
    assert [row["id"] for row in r.sample["rows"]] == ["a", "b"]


# ── CSV ───────────────────────────────────────────────────────────────────────
def test_csv_reads_rows_as_dicts():
    blob = "id,note,dialogue\nr1,a note,a dialogue\nr2,another,more\n"
    r = decode_records(blob, fmt="csv")
    assert r.fmt == "csv"
    assert r.sample == {
        "rows": [
            {"id": "r1", "note": "a note", "dialogue": "a dialogue"},
            {"id": "r2", "note": "another", "dialogue": "more"},
        ]
    }
    assert r.expected_count == 2
    assert r.iterated_collection == "rows"


def test_csv_columns_surface_for_field_mapping():
    """The CSV header columns are surfaced so the front door can offer a field-mapping confirm
    (which column → case_id / response / context) — the "ask the user the fields" path."""
    r = decode_records("ident,output,input\nr1,o,i\n", fmt="csv")
    assert r.columns == ["ident", "output", "input"]


# ── auto-detect by filename / content ─────────────────────────────────────────
@pytest.mark.parametrize(
    "filename,blob,expected_fmt",
    [
        ("data.json", '{"a": 1}', "json"),
        ("data.jsonl", '{"a": 1}\n{"a": 2}', "jsonl"),
        ("data.ndjson", '{"a": 1}\n{"a": 2}', "jsonl"),
        ("data.csv", "a,b\n1,2", "csv"),
    ],
)
def test_auto_detect_by_extension(filename, blob, expected_fmt):
    r = decode_records(blob, fmt="auto", filename=filename)
    assert r.fmt == expected_fmt


def test_auto_detect_jsonl_by_content_when_no_filename():
    """Two+ standalone JSON objects on separate lines → JSONL (not a single JSON parse)."""
    r = decode_records('{"a": 1}\n{"a": 2}\n{"a": 3}', fmt="auto")
    assert r.fmt == "jsonl"
    assert r.expected_count == 3


# ── errors are actionable, never bare ─────────────────────────────────────────
def test_bad_json_raises_actionable():
    with pytest.raises(ValueError, match="did not parse"):
        decode_records("{not json", fmt="json")


def test_empty_blob_raises():
    with pytest.raises(ValueError, match="empty"):
        decode_records("   ", fmt="auto")
