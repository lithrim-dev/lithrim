"""Composite report + calibration — REPORT-ONLY (no gate).

``composite`` summarizes the grounded result: the harness verdict after
suppression, a severity-weighted risk score, the grounded adjustments (what a
contract flipped), and the ungrounded (null-code) bucket.

``calibration`` builds a reliability diagram + ECE over the council's per-judge
confidences. This is a DIAGNOSTIC, not a gate — the locked calibration gate is
WS-4. The WS-0 baseline has only two non-null confidences (both 1.0), so the
report is honest about the small N.
"""

from __future__ import annotations

from typing import Any

from .grounding import GroundedResult

_STAGE_TO_COMPLIANCE = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}


def composite(grounded: GroundedResult) -> dict[str, Any]:
    """Composite verdict + score + the grounded adjustments (report shape)."""
    score = max(
        (grounded.weights.get(f.get("severity"), 0.0) for f in grounded.active),
        default=0.0,
    )
    adjustments = [
        {
            "flag": s["finding"].get("code"),
            "action": "suppressed",
            "contract": s["contract"].version,
            "matched_token": s["verdict"].matched_token,
            "reason": s["verdict"].reason,
        }
        for s in grounded.suppressed
    ]
    n_suppressed = len(grounded.suppressed)
    reasoning = (
        f"{len(grounded.active)} active finding(s) after grounding; "
        f"{n_suppressed} suppressed by contract; "
        f"{len(grounded.ungrounded)} null-code finding(s) skip-logged (ungrounded). "
        f"Composite stage verdict {grounded.verdict} "
        f"(was {grounded.original_verdict} pre-grounding)."
    )
    return {
        "verdict": _STAGE_TO_COMPLIANCE.get(grounded.verdict, "needs_review"),
        "stage_verdict": grounded.verdict,
        "score": score,
        "reasoning": reasoning,
        "grounded_adjustments": adjustments,
        "active_findings": [f.get("code") or f.get("detail") for f in grounded.active],
        "ungrounded_count": len(grounded.ungrounded),
    }


def calibration(
    result: dict[str, Any], *, expected_block: bool, n_bins: int = 10
) -> dict[str, Any]:
    """Reliability bins + ECE over per-judge confidences. REPORT-ONLY.

    A judge vote is "correct" when its BLOCK/PASS decision agrees with the case's
    expected verdict (``expected_block``). Votes with ``confidence=None`` are
    excluded (they cannot be binned). Returns only non-empty bins plus the counts
    and an explicit small-N caveat.
    """
    votes = (result.get("semantic") or {}).get("judge_votes") or []
    preds: list[tuple[float, bool]] = []
    n_null = 0
    for v in votes:
        conf = v.get("confidence")
        if conf is None:
            n_null += 1
            continue
        correct = (v.get("vote") == "BLOCK") == expected_block
        preds.append((float(conf), correct))

    bins: list[dict[str, Any]] = []
    ece = 0.0
    n = len(preds)
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        # last bin is closed on the right so confidence==1.0 lands in it
        in_bin = [(c, ok) for (c, ok) in preds if (lo <= c < hi) or (i == n_bins - 1 and c == 1.0)]
        if not in_bin:
            continue
        count = len(in_bin)
        avg_conf = sum(c for c, _ in in_bin) / count
        accuracy = sum(1 for _, ok in in_bin if ok) / count
        bins.append(
            {
                "bin_lower": round(lo, 2),
                "bin_upper": round(hi, 2),
                "count": count,
                "avg_confidence": round(avg_conf, 4),
                "accuracy": round(accuracy, 4),
            }
        )
        if n:
            ece += (count / n) * abs(avg_conf - accuracy)

    caveat = None
    if n < 5:
        caveat = (
            f"small N: only {n} non-null confidence(s) in the baseline "
            f"({n_null} judge vote(s) had confidence=None); ECE is indicative only"
        )

    return {
        "reliability_bins": bins,
        "ece": round(ece, 4),
        "n_total": len(votes),
        "n_with_confidence": n,
        "n_null_confidence": n_null,
        "expected_block": expected_block,
        "caveat": caveat,
    }
