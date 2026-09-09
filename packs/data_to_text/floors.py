"""data_to_text pack floors: the ``null_negation`` SUPPRESS contract (zero engine edits; registered
through the same PACK-3 ``SUPPRESS_EXECUTORS`` interface as the fixture and domain packs).

A ``NULL_AS_NEGATION`` finding claims the response says an attribute is absent where the record
holds ``null``. That claim is decidable: parse the record's attributes, find the ones that are
null, and look for a negation of one of their surface terms in the response. No such negation
means the finding is not grounded and is DISPROVED; a negation means it STANDS, span attached.
The attribute vocabulary and negation patterns are contract ``params`` (domain data), not code."""

from __future__ import annotations

import json
import re
from typing import Any

DEFAULT_NEGATION = (
    r"\b(no|not|without|lacks?|lacking|doesn'?t|does not|don'?t|do not|isn'?t|is not|aren'?t|are not|"
    r"unavailable|not available|not offered|no longer)\b"
)


def _record(case: dict[str, Any], params: dict[str, Any]) -> dict | None:
    raw = case.get(params.get("record_path") or "transcript")
    try:
        rec = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def null_negations(record: Any, text: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Every (null attribute, negated surface term, span) the text asserts. Pure and deterministic."""
    rec = record
    if isinstance(rec, str):
        try:
            rec = json.loads(rec)
        except ValueError:
            return []
    attrs = (
        (rec or {}).get(params.get("attributes_path") or "attributes")
        if isinstance(rec, dict)
        else None
    )
    if not isinstance(attrs, dict):
        return []
    window = int(params.get("negation_window") or 60)
    neg = re.compile(params.get("negation_pattern") or DEFAULT_NEGATION, re.I)
    terms: dict[str, list[str]] = params.get("attribute_terms") or {}
    low = text.lower()
    # Flatten one level: a null member of a nested attribute dict is addressed as "Attr.member".
    nulls: list[str] = []
    for attr, value in attrs.items():
        if value is None:
            nulls.append(attr)
        elif isinstance(value, dict):
            nulls.extend(f"{attr}.{member}" for member, mv in value.items() if mv is None)
    out = []
    for attr in nulls:
        if attr not in terms:
            continue
        for term in terms[attr]:
            for m in re.finditer(re.escape(term.lower()), low):
                start, end = max(0, m.start() - window), min(len(text), m.end() + window)
                span = text[start:end]
                if neg.search(span):
                    out.append({"attribute": attr, "term": term, "span": span.strip()})
                    break
            else:
                continue
            break
    return out


class NullNegationSuppress:
    """Suppress contract: disprove a NULL_AS_NEGATION finding the response does not support."""

    contract_type = "null_negation"

    def __init__(self, decl: Any) -> None:
        self.flag_code = getattr(decl, "flag_code", "NULL_AS_NEGATION")
        self.params = dict(getattr(decl, "params", None) or {})
        self.version = getattr(decl, "version", "null-negation/1")

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Any:
        from lithrim_bench.harness.grounding import Verdict

        rec = _record(case, self.params)
        if rec is None:
            return Verdict(
                disproved=False,
                reason="inconclusive: the record is not a JSON object; the finding stands",
            )
        arts = case.get("artifacts") or []
        text = (arts[0] or {}).get("content") if arts else None
        if not isinstance(text, str) or not text.strip():
            return Verdict(
                disproved=False, reason="inconclusive: no artifact text; the finding stands"
            )
        hits = null_negations(rec, text, self.params)
        if hits:
            h = hits[0]
            return Verdict(
                disproved=False,
                reason=f"the response negates {h['attribute']!r}, which the record holds as null; the finding stands",
                evidence=f"{h['attribute']}: …{h['span']}…",
            )
        return Verdict(
            disproved=True,
            reason="no null-valued record attribute is negated in the response; the NULL_AS_NEGATION finding is not grounded",
            evidence=None,
        )


SUPPRESS_EXECUTORS = {"null_negation": NullNegationSuppress}
FLOOR_EXECUTORS: dict[str, Any] = {}
