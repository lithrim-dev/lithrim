"""In-corpus calibration (GENERALIST-1 / Phase 2): project a workspace's graded/ingested
cases into the judge-calibration corpus shape ``run_optimize`` reads, with a deterministic
calibration/test split.

This is the bridge that replaces the hardcoded, single-pack ``examples/judge_calib_v1.jsonl``
with the ACTIVE workspace's OWN cases in the ACTIVE pack's taxonomy — so "as you build a corpus,
you calibrate" is in-domain, not against a foreign pack's labels. Pure + stdlib-only (no council /
dspy / pack import), so it stays testable on the default core and importable from the optimize
subprocess.

A calib row carries exactly the fields ``judge_optimize._example_fields`` /
``ab_harness._artifact_text`` read off a row — ``transcript`` + ``artifacts`` (the list flattened
into the DSPy ``artifact`` input) + ``expected_safety_flags`` (the by-construction gold the metric
scores against) — plus the ``split`` tag (``calibration`` = trainset, ``test`` = held-out).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def build_calib_rows(
    cases: Sequence[Mapping[str, Any]], *, test_stride: int = 3
) -> list[dict[str, Any]]:
    """Project workspace case payloads into calibration rows + a deterministic split.

    Only LABELED cases are included — a case carrying a defined ``expected_safety_flags`` list
    (positives AND clean negatives, both first-class by construction); an unlabeled case has no
    gold to score against, so it is dropped. Order is by ``case_id`` (deterministic, replay-safe),
    then every ``test_stride``-th case (the last of each window) → ``test``, the rest →
    ``calibration`` — so positives SPREAD across both splits rather than clustering at one end (a
    narrow tail-split could starve the held-out set of the very flags the role raises).

    Returns rows shaped ``{case_id, transcript, artifacts, expected_safety_flags, split}`` — the
    fields the optimizer's example projection reads. ``test_stride`` defaults to 3 (≈70/30)."""
    labeled = [c for c in cases if isinstance(c.get("expected_safety_flags"), list)]
    labeled = sorted(labeled, key=lambda c: str(c.get("case_id") or ""))
    rows: list[dict[str, Any]] = []
    for i, c in enumerate(labeled):
        split = "test" if i % test_stride == (test_stride - 1) else "calibration"
        rows.append(
            {
                "case_id": c.get("case_id"),
                "transcript": c.get("transcript", ""),
                "artifacts": list(c.get("artifacts") or []),
                "expected_safety_flags": list(c.get("expected_safety_flags") or []),
                "split": split,
            }
        )
    return rows


def write_calib_jsonl(rows: Sequence[Mapping[str, Any]], path: str | Path) -> Path:
    """Write calib rows as one-JSON-object-per-line (the ``load_corpus`` format). Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def split_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """{'calibration': n, 'test': m} — the honest split sizes (surfaced so a tiny held-out set
    reads as small-sample, never hidden)."""
    out = {"calibration": 0, "test": 0}
    for r in rows:
        s = str(r.get("split") or "")
        if s in out:
            out[s] += 1
    return out
