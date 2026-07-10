"""Front-door decode shim (CE-INGEST-FRONTDOOR-1): JSON / JSONL / CSV → the ``sample`` the JUTE
ingest engine consumes.

Parse-in-Python, map-in-JUTE: decoding a *serialization* (splitting JSONL lines, reading CSV rows)
is plain, safe Python; the semantic field-mapping that follows stays JUTE (the model never emits
server-executed code). CSV/JSONL are generic serializations — not source-specific schemas — so this
honors "ingestion stays generic JUTE".

Pure + dependency-free (stdlib only): no fastapi, no dspy, no :3031.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

_JSON_EXTS = {".json"}
_JSONL_EXTS = {".jsonl", ".ndjson"}
_CSV_EXTS = {".csv"}


@dataclass
class DecodeResult:
    """The decoded ingest sample plus the hints the engine + front door need.

    - ``sample`` — the JSON object/list to hand the existing ``_ingest_cases`` engine.
    - ``expected_count`` — the row count when the shim knows it (JSONL/CSV/top-level array);
      ``None`` for a bare object (the engine infers via enhanced_scenes / an extraction hint).
    - ``iterated_collection`` — the collection name the engine should emit one case per (``rows``
      for the wrapped JSONL/CSV shapes); ``None`` when the engine's native inference applies.
    - ``columns`` — CSV header columns (for the "confirm which column → which field" front door),
      empty for JSON/JSONL.
    """

    fmt: str
    sample: object
    expected_count: int | None = None
    iterated_collection: str | None = None
    columns: list[str] = field(default_factory=list)


def _detect_fmt(raw: str, filename: str) -> str:
    ext = ""
    if filename and "." in filename:
        ext = filename[filename.rindex(".") :].lower()
    if ext in _JSONL_EXTS:
        return "jsonl"
    if ext in _CSV_EXTS:
        return "csv"
    if ext in _JSON_EXTS:
        return "json"
    # content sniff (no usable extension): multiple standalone JSON objects on their own lines
    # → JSONL; a single parseable JSON value → JSON; otherwise treat as CSV.
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 1 and all(_is_json_object_line(ln) for ln in lines):
        return "jsonl"
    try:
        json.loads(raw)
        return "json"
    except (json.JSONDecodeError, ValueError):
        return "csv"


def _is_json_object_line(line: str) -> bool:
    s = line.strip()
    if not (s.startswith("{") or s.startswith("[")):
        return False
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def decode_records(raw_text: str, *, fmt: str = "auto", filename: str = "") -> DecodeResult:
    """Decode an uploaded blob into a :class:`DecodeResult`. ``fmt`` is one of
    ``auto|json|jsonl|csv`` (``auto`` resolves by filename extension then content sniff)."""
    if not raw_text or not raw_text.strip():
        raise ValueError("the uploaded data is empty")
    if fmt == "auto":
        fmt = _detect_fmt(raw_text, filename)

    if fmt == "json":
        return _decode_json(raw_text)
    if fmt == "jsonl":
        return _decode_jsonl(raw_text)
    if fmt == "csv":
        return _decode_csv(raw_text)
    raise ValueError(f"unknown ingest format {fmt!r} (expected auto|json|jsonl|csv)")


def _dominant_record_collection(obj: dict) -> tuple[str | None, int | None]:
    """The iteration unit for an arbitrary JSON object: the top-level key whose value is the
    longest non-empty list-of-records (dicts). Generic (no schema knowledge) — it just answers
    "which array is one-case-per-entry". Returns (key, len) or (None, None) when there is no
    record array (then the engine's own inference / =1 gate applies). Scalar lists are ignored
    (tags/labels aren't a case collection); ties resolve to the first key (deterministic)."""
    best_key, best_len = None, 0
    for k, v in obj.items():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v) and len(v) > best_len:
            best_key, best_len = k, len(v)
    return (best_key, best_len) if best_key is not None else (None, None)


def _decode_json(raw: str) -> DecodeResult:
    try:
        sample = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"the uploaded JSON did not parse: {exc}") from exc
    if isinstance(sample, list):
        return DecodeResult(fmt="json", sample=sample, expected_count=len(sample))
    if isinstance(sample, dict):
        # arbitrary {key:[records]} → auto-detect the iteration unit so a custom trace doesn't hit
        # the engine's un-hinted =1 gate. The preview shows the result for approval, so never silent.
        key, n = _dominant_record_collection(sample)
        if key is not None:
            return DecodeResult(fmt="json", sample=sample, expected_count=n, iterated_collection=key)
    return DecodeResult(fmt="json", sample=sample, expected_count=None)


def _decode_jsonl(raw: str) -> DecodeResult:
    rows: list[object] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"JSONL line {i} did not parse: {exc}") from exc
    if not rows:
        raise ValueError("the uploaded JSONL had no non-blank lines")
    return DecodeResult(
        fmt="jsonl", sample={"rows": rows}, expected_count=len(rows), iterated_collection="rows"
    )


def _decode_csv(raw: str) -> DecodeResult:
    reader = csv.DictReader(io.StringIO(raw))
    columns = list(reader.fieldnames or [])
    if not columns:
        raise ValueError("the uploaded CSV had no header row")
    rows = [dict(r) for r in reader]
    if not rows:
        raise ValueError("the uploaded CSV had a header but no data rows")
    return DecodeResult(
        fmt="csv",
        sample={"rows": rows},
        expected_count=len(rows),
        iterated_collection="rows",
        columns=columns,
    )
