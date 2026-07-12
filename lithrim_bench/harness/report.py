"""Composite report + calibration — REPORT-ONLY (no gate).

``composite`` summarizes the grounded result: the harness verdict after
suppression, a severity-weighted risk score, the grounded adjustments (what a
contract flipped), and the ungrounded (null-code) bucket.

``calibration`` builds a reliability diagram + ECE over the council's per-judge
confidences. This is a DIAGNOSTIC, not a gate — the locked calibration gate is
WS-4b. The WS-0 baseline has only two non-null confidences (both 1.0), so the
report is honest about the small N.

``calibration_check`` (WS-4a) aggregates the per-case ``composite`` + ``calibration``
outputs of an eval-run into a one-line ``{verdict_match_rate, ece, status}`` summary.
It is deliberately NOT the WS-4b locked gate: ``status`` is an ADVISORY,
non-preregistered PASS/WARN driven ONLY by verdict-match; ``ece`` is reported as a
pure diagnostic and never drives ``status``. No threshold here is locked.
"""

from __future__ import annotations

from typing import Any

from ..picklist import normalize_expected_verdict
from .grounding import GroundedResult

_STAGE_TO_COMPLIANCE = {"BLOCK": "reject", "WARN": "needs_review", "PASS": "approve"}


def composite(grounded: GroundedResult) -> dict[str, Any]:
    """Composite verdict + score + the grounded adjustments (report shape)."""
    score = max(
        (grounded.weights.get(f.get("severity"), 0.0) for f in grounded.active),
        default=0.0,
    )
    adjustments = []
    for s in grounded.suppressed:
        adjustment = {
            "flag": s["finding"].get("code"),
            "action": "suppressed",
            "contract": s["contract"].version,
            "matched_token": s["verdict"].matched_token,
            "reason": s["verdict"].reason,
        }
        edition = getattr(s["verdict"], "terminology_edition", None)
        if edition is not None:
            # REL-OPS-1 O2: absent (not null) for non-terminology contracts.
            adjustment["terminology_edition"] = edition
        adjustments.append(adjustment)
    n_suppressed = len(grounded.suppressed)
    n_reference = len(grounded.skipped_non_gradeable)

    # WS-3 structural floor: contracts that injected a BLOCK the council missed
    # (or ran inconclusively). Empty whenever no floor is declared — so the floor
    # additions below are inert for the committed clinical default.
    floor_blocks = getattr(grounded, "floor_blocks", []) or []
    floor_adjustments = [
        {
            "flag": (b["injected_finding"] or {}).get("code")
            or b["decl"].params.get("inject_flag_code"),
            "action": "floor_block" if b["injected_finding"] else "floor_inconclusive",
            "contract_type": b["decl"].contract_type,
            "contract": b["decl"].version,
            "conforms": b["result"].conforms,
            "disposition": b["result"].disposition,
        }
        for b in floor_blocks
    ]
    n_floor_block = sum(1 for b in floor_blocks if b["injected_finding"] is not None)
    n_floor_inconclusive = len(floor_blocks) - n_floor_block

    reasoning = (
        f"{len(grounded.active)} active finding(s) after grounding; "
        f"{n_suppressed} suppressed by contract; "
        f"{len(grounded.ungrounded)} null-code finding(s) skip-logged (ungrounded); "
        f"{n_reference} reference finding(s) skip-logged (out-of-snapshot, not scored). "
        f"Composite stage verdict {grounded.verdict} "
        f"(was {grounded.original_verdict} pre-grounding)."
    )
    if floor_blocks:
        reasoning += (
            f" Structural floor: {n_floor_block} block(s) injected"
            f"{f', {n_floor_inconclusive} inconclusive' if n_floor_inconclusive else ''}."
        )

    # FLOOR-COVERAGE-1: per-verdict floor-coverage provenance. ``floor_backstopped=False`` on a
    # BLOCK means the reject rests solely on judge-only findings the deterministic floor never
    # grounded — the record/UI can mark it. Absent on pre-annotation results (defaults to {}).
    coverage = getattr(grounded, "coverage", {}) or {}

    return {
        "verdict": _STAGE_TO_COMPLIANCE.get(grounded.verdict, "needs_review"),
        "stage_verdict": grounded.verdict,
        "score": score,
        "reasoning": reasoning,
        "grounded_adjustments": adjustments,
        "floor_adjustments": floor_adjustments,
        "active_findings": [f.get("code") or f.get("detail") for f in grounded.active],
        "ungrounded_count": len(grounded.ungrounded),
        "skipped_non_gradeable_count": n_reference,
        "floor_block_count": n_floor_block,
        "coverage": coverage,
        "floor_backstopped": coverage.get("floor_backstopped"),
    }


def calibration(
    result: dict[str, Any], *, expected_block: bool, labeled: bool = True, n_bins: int = 10
) -> dict[str, Any]:
    """Reliability bins + ECE over per-judge confidences. REPORT-ONLY.

    A judge vote is "correct" when its BLOCK/PASS decision agrees with the case's
    expected verdict (``expected_block``). Votes with ``confidence=None`` are
    excluded (they cannot be binned). Returns only non-empty bins plus the counts
    and an explicit small-N caveat.

    HONEST-1: ``labeled=False`` (no ground truth) means "correct" is undefined, so
    ECE/reliability are suppressed (``ece=None``, no bins) rather than scored against
    a phantom ``expected_block``. The vote counts stay factual.
    """
    votes = (result.get("semantic") or {}).get("judge_votes") or []
    if not labeled:
        n_null = sum(1 for v in votes if v.get("confidence") is None)
        return {
            "reliability_bins": [],
            "ece": None,
            "n_total": len(votes),
            "n_with_confidence": len(votes) - n_null,
            "n_null_confidence": n_null,
            "expected_block": None,
            "caveat": "unlabeled — calibration requires ground truth",
        }
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


def calibration_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Minimal eval-run calibration summary — REPORT-ONLY, NOT a locked gate (WS-4b).

    ``records`` are per-case run records (each carries the ``composite`` and
    ``calibration`` outputs of :func:`composite` / :func:`calibration`, plus a
    ``provenance.expected_compliance_verdict``). Returns:

      - ``verdict_match_rate`` — fraction of cases whose composite verdict is in the
        case's expected verdict set (:func:`normalize_expected_verdict`).
      - ``ece`` — the per-case ECEs pooled by ``n_with_confidence`` (a confidence-
        count-weighted mean). Carried as a DIAGNOSTIC only.
      - ``status`` — ADVISORY ``PASS`` iff every case matched, else ``WARN``. Driven
        ONLY by verdict-match; ``ece`` never moves it. This is intentionally not the
        WS-4b preregistered/locked calibration gate — no threshold is locked here.
    """
    n_cases = len(records)
    n_labeled = 0
    n_matched = 0
    ece_weighted_sum = 0.0
    n_pooled = 0
    for rec in records:
        expected = normalize_expected_verdict(rec["provenance"]["expected_compliance_verdict"])
        if expected:  # a labeled record (a declared expected-verdict set)
            n_labeled += 1
            if rec["composite"]["verdict"] in expected:
                n_matched += 1
        cal = rec["calibration"]
        n = cal["n_with_confidence"]
        ece = cal["ece"]
        if ece is not None and n:  # an unlabeled case carries ece=None (W2) — never pool it
            ece_weighted_sum += ece * n
            n_pooled += n

    if n_labeled == 0:
        label_status = "unlabeled"
    elif n_labeled == n_cases:
        label_status = "labeled"
    else:
        label_status = "partial"

    # HONEST-1: with no ground truth there is NO accuracy/calibration to report — the verdict
    # + grounding (label-free, computed elsewhere) stand; the accuracy/ECE are withheld, NOT
    # fabricated. Neither a 0.0/WARN failure NOR a 1.0/PASS win may leak (honest-Δ both ways).
    if label_status == "unlabeled":
        return {
            "label_status": "unlabeled",
            "verdict_match_rate": None,
            "ece": None,
            "status": "unlabeled",
            "n_cases": n_cases,
            "n_labeled": 0,
            "n_matched": 0,
            "n_with_confidence": n_pooled,
            "caveat": "no ground truth — verdict + grounding shown; author labels to unlock accuracy/calibration",
        }

    verdict_match_rate = round(n_matched / n_labeled, 4)
    ece = round(ece_weighted_sum / n_pooled, 4) if n_pooled else 0.0
    status = "PASS" if n_matched == n_labeled else "WARN"

    notes: list[str] = []
    if label_status == "partial":
        notes.append(
            f"{n_cases - n_labeled} of {n_cases} case(s) unlabeled — rate over the {n_labeled} labeled case(s)"
        )
    if n_pooled < 5:
        notes.append(
            f"small N: only {n_pooled} non-null confidence(s) pooled across "
            f"{n_cases} case(s); ece is indicative only (advisory, not a gate)"
        )
    caveat = "; ".join(notes) if notes else None

    return {
        "label_status": label_status,
        "verdict_match_rate": verdict_match_rate,
        "ece": ece,
        "status": status,
        "n_cases": n_cases,
        "n_labeled": n_labeled,
        "n_matched": n_matched,
        "n_with_confidence": n_pooled,
        "caveat": caveat,
    }
