"""In-corpus calibration (Phase 2) — the pure corpus→calib-rows projection + split.

Pins: only labeled cases ride along; the calibration/test split is deterministic + SPREAD (both
splits carry positives, not clustered); the row shape is exactly what the optimizer reads; the
JSONL round-trips through the optimizer's own ``load_corpus``. Stdlib-only (no council/dspy)."""

import json

from lithrim_bench.harness.calib_corpus import (
    build_calib_rows,
    split_counts,
    write_calib_jsonl,
)


def _cases():
    # 10 by-construction cases: 9 positive (varied flags), 1 clean negative (empty gold list).
    out = []
    for i in range(1, 10):
        out.append(
            {
                "case_id": f"case{i:02d}",
                "transcript": f"t{i}",
                "artifacts": [{"content": f"a{i}"}],
                "expected_safety_flags": ["HISTORY_OMISSION"] if i % 2 else ["VALUE_MISMATCH"],
            }
        )
    out.append({"case_id": "case10", "transcript": "t10", "artifacts": [], "expected_safety_flags": []})
    return out


def test_only_labeled_cases_ride_along():
    cases = _cases() + [{"case_id": "unlabeled", "transcript": "x"}]  # no expected_safety_flags
    rows = build_calib_rows(cases)
    ids = {r["case_id"] for r in rows}
    assert "unlabeled" not in ids  # dropped — no gold to score against
    assert len(rows) == 10  # the 9 positives + 1 clean negative


def test_split_is_deterministic_and_spread():
    rows = build_calib_rows(_cases(), test_stride=3)
    counts = split_counts(rows)
    # ≈70/30 over 10 cases → 7 calibration / 3 test
    assert counts == {"calibration": 7, "test": 3}
    # SPREAD: both splits carry ≥1 positive (a tail split could starve the held-out set)
    def positives(split):
        return [r for r in rows if r["split"] == split and r["expected_safety_flags"]]
    assert positives("calibration") and positives("test")
    # deterministic: same input → same split assignment
    assert [r["split"] for r in build_calib_rows(_cases(), test_stride=3)] == [r["split"] for r in rows]


def test_row_shape_matches_the_optimizer_inputs():
    rows = build_calib_rows(_cases())
    r = rows[0]
    assert set(r) == {"case_id", "transcript", "artifacts", "expected_safety_flags", "split"}
    assert isinstance(r["artifacts"], list) and isinstance(r["expected_safety_flags"], list)


def test_jsonl_round_trips_through_load_corpus(tmp_path):
    rows = build_calib_rows(_cases())
    path = write_calib_jsonl(rows, tmp_path / "calib.jsonl")
    # read back the SAME way the optimizer does (one JSON object per line)
    back = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(back) == 10
    assert {r["split"] for r in back} == {"calibration", "test"}
    # the artifact text the optimizer flattens is present
    assert back[0]["artifacts"][0]["content"].startswith("a")
