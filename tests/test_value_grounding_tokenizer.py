"""VALUE-GROUNDING tokenizer: a number token must be whole or absent, never a truncated prefix.

Found 2026-09-08 on the RAGTruth Data2txt test slice: ``4.5-star`` was extracted as ``4`` and
``7:30am`` as ``7``, producing 16 of the floor's 18 false blocks. The documented rule (hyphen-bound
tokens are names, not values) is kept; only the leak is closed.
"""

import pytest

from lithrim_bench.verification.spec import Claim, VerificationSpec
from lithrim_bench.verification.tools import (
    ValueGroundingTool,
    _vg_artifact_values,
    _vg_source_values,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("a 4.5-star rating", []),  # hyphen-bound decimal is a name: nothing, never a truncated '4'
        ("a 3.5-star rating", []),
        ("rated 4.5-stars by 20 people", ["20"]),
        ("1.5x faster", []),  # letter-bound decimal: nothing, never '1'
        ("open from 7:30am to 4:00pm", ["7:30", "4:00"]),  # am/pm suffix is part of the time
        ("open 7:30AM-4:00PM", ["7:30", "4:00"]),
        # documented behaviour that must not move
        ("COVID-19 and a 5-star vibe", []),
        ("10-15 minutes", []),
        ("$15 to $25", ["15", "25"]),
        ("$1,200", ["1200"]),
        ("5.0", ["5"]),
        ("from 9 to 5", ["9", "5"]),
        (
            "Rated 4.5 stars with 312 reviews. Open Sundays from 9:00 am to 2:00 pm.",
            ["9:00", "2:00", "4.5", "312"],
        ),
    ],
)
def test_artifact_values_are_whole_or_absent(text, expected):
    assert _vg_artifact_values(text, 1) == expected


def test_source_side_accepts_am_pm_times():
    vals = _vg_source_values('{"hours": {"Mon": "7:30am-16:0"}, "business_stars": 4.5}')
    assert {"7:30", "16:00", "4.5"} <= vals
    assert "7" not in vals or "7:30" in vals


def _verify(artifact: str, record: str):
    claim = Claim(
        claim_type="reference_conformance",
        flag_code=None,
        subject=artifact,
        locus="",
        source={"transcript": record, "source_kind": "record"},
    )
    spec = VerificationSpec(
        tool="value_grounding",
        applies_to_flags=(),
        locus="",
        reference={"source_path": "transcript", "on_missing": "by_source_kind", "min_digits": 1},
        version="value-grounding/1",
    )
    return ValueGroundingTool().verify(claim, spec)


def test_hyphenated_rating_is_not_a_false_violation():
    record = '{"business_stars": 4.5, "review_count": 20}'
    r = _verify("With a 4.5-star rating and 20 reviews.", record)
    assert (
        r.conforms is True and r.evidence["missing"] == []
    )  # '20' checked and present; no phantom '4'
    r2 = _verify("With a 4.5-star rating.", record)
    assert r2.conforms is None  # nothing checkable: never a violation on a value the record holds
