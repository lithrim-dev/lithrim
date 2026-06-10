"""Shared helpers for HL7-projection injectors.

Each HL7 injector targets the first artifact in the list (the message
text), locates a segment by name, mutates a field by 1-based index,
and returns the new artifacts list.
"""
from __future__ import annotations

import json
from typing import Any, Callable

_FIELD = "|"
_SEG_DELIM = "\r"


def parse_segments(hl7_text: str) -> list[list[str]]:
    """Split into segments and segments into fields.

    Returns one list per segment (e.g. ["PID", "1", "", "...", ...]).
    Empty trailing segments from the trailing \\r are dropped.
    """
    segs = [s for s in hl7_text.replace("\n", "\r").split(_SEG_DELIM) if s]
    return [s.split(_FIELD) for s in segs]


def serialize_segments(segments: list[list[str]]) -> str:
    return _SEG_DELIM.join(_FIELD.join(seg) for seg in segments) + _SEG_DELIM


def mutate_hl7(
    artifacts: list[dict[str, Any]],
    mutator: Callable[[list[list[str]]], list[list[str]]],
) -> tuple[list[dict[str, Any]], str, str]:
    """Apply mutator to the parsed segments of artifacts[0]."""
    if not artifacts:
        raise ValueError("no artifacts to mutate")
    new_artifacts = json.loads(json.dumps(artifacts))
    original = new_artifacts[0]["content"]
    segments = parse_segments(original)
    mutated_segments = mutator(segments)
    mutated = serialize_segments(mutated_segments)
    if mutated == original:
        raise ValueError("HL7 mutator was a no-op")
    new_artifacts[0]["content"] = mutated
    return new_artifacts, original, mutated


def find_segment(segments: list[list[str]], name: str) -> int:
    for i, seg in enumerate(segments):
        if seg and seg[0] == name:
            return i
    raise ValueError(f"segment {name} not found")
