"""Per-case + pack-level analysis of an N-run NDJSON output.

Eval spec §2.3 metrics, layer 1 + layer 2:

Layer 1 (decision-layer):
- verdict_distribution per case (counts of each verdict over N runs)
- modal_verdict
- verdict_instability = 1 - (modal_count / N)
- verdict_match_rate against expected (per case + pack-level)
- decision_layer_kappa: Fleiss' kappa across the per-judge decision
  outputs when per_judge is populated; None otherwise

Layer 2 (code-attribution):
- per-flag attachment rate: across N runs, fraction in which a given
  expected flag was attached
- false-block rate (clean negatives): fraction of clean_negative=True
  cases that received BLOCK or WARN

Pack-level rollups:
- instability_rate: fraction of cases with verdict_instability > 0
- mean verdict_match_rate with bootstrap 95% CI (B=1000 by default)
- false_block_rate
"""
from __future__ import annotations

import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _bootstrap_ci(
    values: list[float], iterations: int = 1000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    samples = [
        statistics.fmean(rng.choices(values, k=n)) for _ in range(iterations)
    ]
    samples.sort()
    lo = samples[int(iterations * (alpha / 2))]
    hi = samples[int(iterations * (1 - alpha / 2))]
    return (lo, hi)


def _matches_expected(observed: str, expected: Any) -> bool:
    if isinstance(expected, list):
        return observed in expected
    return observed == expected


def _fleiss_kappa(per_judge_verdicts: list[dict[str, str]]) -> float | None:
    """Fleiss' kappa on per-judge decision outputs across N runs.

    `per_judge_verdicts` is one dict per run, mapping judge_name ->
    verdict. Returns None if any run is missing per_judge data or
    fewer than 2 raters.
    """
    if not per_judge_verdicts:
        return None
    judges = list(per_judge_verdicts[0].keys())
    if len(judges) < 2:
        return None

    categories = sorted({v for run in per_judge_verdicts for v in run.values()})
    if len(categories) <= 1:
        return 1.0

    n = len(judges)
    N = len(per_judge_verdicts)
    P_e = 0.0
    p_j: dict[str, float] = {}
    for cat in categories:
        total = sum(1 for run in per_judge_verdicts for v in run.values() if v == cat)
        p_j[cat] = total / (N * n)
        P_e += p_j[cat] ** 2

    P_i_sum = 0.0
    for run in per_judge_verdicts:
        c = Counter(run.values())
        agree = sum(v * (v - 1) for v in c.values())
        P_i_sum += agree / (n * (n - 1)) if n > 1 else 0.0
    P_bar = P_i_sum / N

    if P_e >= 1.0:
        return 1.0
    return (P_bar - P_e) / (1 - P_e)


def read_runs(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def analyze_per_case(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_case[r["case_id"]].append(r)

    out: list[dict[str, Any]] = []
    for case_id, runs in by_case.items():
        runs.sort(key=lambda r: r["run_index"])
        verdicts = [r["compliance_verdict"] for r in runs]
        dist = Counter(verdicts)
        modal, modal_count = dist.most_common(1)[0]
        n = len(runs)
        expected_verdict = runs[0].get("expected_compliance_verdict")
        match_count = sum(1 for v in verdicts if _matches_expected(v, expected_verdict))

        expected_flags = runs[0].get("expected_safety_flags") or []
        attachment: dict[str, float] = {}
        for flag in expected_flags:
            attached = sum(1 for r in runs if flag in (r.get("flags") or []))
            attachment[flag] = attached / n if n else 0.0

        per_judge_runs = [r["per_judge"] for r in runs if r.get("per_judge")]
        decision_kappa = None
        if len(per_judge_runs) == n:
            per_judge_decisions = [
                {name: payload["verdict"] for name, payload in run.items()}
                for run in per_judge_runs
            ]
            decision_kappa = _fleiss_kappa(per_judge_decisions)

        out.append(
            {
                "case_id": case_id,
                "n": n,
                "verdict_distribution": dict(dist),
                "modal_verdict": modal,
                "verdict_instability": round(1 - (modal_count / n), 4),
                "verdict_match_rate": round(match_count / n, 4),
                "expected_compliance_verdict": expected_verdict,
                "expected_safety_flags": expected_flags,
                "flag_attachment_rate": attachment,
                "decision_layer_kappa": decision_kappa,
            }
        )
    return out


def analyze_pack(
    per_case: list[dict[str, Any]], pack_rows: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    if not per_case:
        return {"cases": 0}
    instabilities = [c["verdict_instability"] for c in per_case]
    match_rates = [c["verdict_match_rate"] for c in per_case]
    instability_rate = sum(1 for x in instabilities if x > 0) / len(instabilities)
    mean_match = statistics.fmean(match_rates)
    ci_lo, ci_hi = _bootstrap_ci(match_rates)

    false_block = None
    if pack_rows is not None:
        by_case_pack = {r["case_id"]: r for r in pack_rows}
        clean = [
            c for c in per_case
            if by_case_pack.get(c["case_id"], {}).get("clean_negative") is True
        ]
        if clean:
            blocked = sum(1 for c in clean if c["modal_verdict"] in ("reject", "needs_review"))
            false_block = blocked / len(clean)

    kappas = [c["decision_layer_kappa"] for c in per_case if c["decision_layer_kappa"] is not None]
    mean_kappa = statistics.fmean(kappas) if kappas else None

    return {
        "cases": len(per_case),
        "n_per_case": per_case[0]["n"],
        "mean_verdict_match_rate": round(mean_match, 4),
        "verdict_match_rate_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
        "instability_rate": round(instability_rate, 4),
        "false_block_rate": round(false_block, 4) if false_block is not None else None,
        "mean_decision_layer_kappa": round(mean_kappa, 4) if mean_kappa is not None else None,
    }
