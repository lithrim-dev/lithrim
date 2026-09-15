"""SPLIT-HYGIENE-1: the stride path never runs over a corpus that already carries split tags.

Found 2026-09-15 reviewing v0.1.30: with ``split`` omitted, an optimize request builds its
calibration corpus with :func:`build_calib_rows`, which orders every LABELLED workspace case by
id and strides every third one into ``test`` — ignoring the ``split`` each case was imported
with. On a workspace loaded from a labelled dataset (RAGTruth's own train/test cut) that means
imported TEST rows train the demos and decide the pin: a held-out set that is not held out.
Refuse the stride path when the corpus carries tags; naming a split is the only honest way in."""

from __future__ import annotations

import pytest

from lithrim_bench.harness.calib_corpus import build_calib_rows, split_counts

UNTAGGED = [
    {"case_id": f"c{i}", "transcript": "t", "artifacts": [], "expected_safety_flags": []}
    for i in range(6)
]


def test_an_untagged_corpus_still_strides_into_calibration_and_test():
    rows = build_calib_rows(UNTAGGED)
    assert split_counts(rows) == {"calibration": 4, "test": 2}


def test_a_tagged_corpus_refuses_the_stride_and_names_the_tags():
    cases = [
        {**c, "split": "calibration" if i < 4 else "test"} for i, c in enumerate(UNTAGGED)
    ]
    with pytest.raises(ValueError) as exc:
        build_calib_rows(cases)
    msg = str(exc.value)
    assert "split" in msg and "calibration" in msg and "test" in msg
    assert "4" in msg and "2" in msg


def test_one_tagged_case_among_untagged_ones_is_enough_to_refuse():
    cases = [dict(c) for c in UNTAGGED]
    cases[0]["split"] = "test"
    with pytest.raises(ValueError, match="split"):
        build_calib_rows(cases)


def test_an_unlabelled_tagged_case_does_not_trigger_the_refusal():
    """The stride only ever reads LABELLED cases; an ungraded row carrying a tag is not in it."""
    cases = [dict(c) for c in UNTAGGED]
    cases.append({"case_id": "u1", "split": "test"})  # no expected_safety_flags → not labelled
    assert split_counts(build_calib_rows(cases)) == {"calibration": 4, "test": 2}
