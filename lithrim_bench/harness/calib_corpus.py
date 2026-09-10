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
scores against) — plus the ``split`` tag (``calibration`` = trainset, ``test`` = held-out; a
corpus built from a labeled dataset's calibration split carries ``dev`` instead, see
:func:`carve_dev`, and the optimizer is told to hold out on it).
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


# HOLDOUT-DEV-1: the share of each stratum's sources carved out of the calibration split as the
# DEV slice the pin gate scores on, so the gate never reads the test cut.
DEV_FRACTION = 0.3


def carve_dev(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_of,
    group_of=None,
    fraction: float = DEV_FRACTION,
) -> list[dict[str, Any]]:
    """Relabel a deterministic, source-disjoint ``fraction`` of the ``calibration`` rows as
    ``dev``. Per stratum (``group_of``, e.g. the task), the distinct sources are ordered by the
    SHA-256 of their id and the first ``round(fraction * n)`` go to dev (at least one when the
    stratum has two sources or more, never all of them); every row of a dev source moves with it.
    Order-independent, input rows untouched, rows of any other split passed through as they are."""
    import hashlib

    if not 0 < fraction < 1:
        raise ValueError(f"dev fraction must be between 0 and 1, got {fraction!r}")

    def _src(r: Mapping[str, Any]) -> str:
        s = source_of(r)
        return str(s if s not in (None, "") else r.get("case_id"))

    strata: dict[str, set[str]] = {}
    for r in rows:
        if r.get("split") == "calibration":
            g = str(group_of(r)) if group_of else ""
            strata.setdefault(g, set()).add(_src(r))
    dev: set[tuple[str, str]] = set()
    for g, sources in strata.items():
        n = len(sources)
        if n < 2:
            continue
        k = min(n - 1, max(1, int(fraction * n + 0.5)))
        ordered = sorted(sources, key=lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest())
        dev.update((g, s) for s in ordered[:k])
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        if r.get("split") == "calibration":
            g = str(group_of(r)) if group_of else ""
            if (g, _src(r)) in dev:
                row["split"] = "dev"
        out.append(row)
    return out
