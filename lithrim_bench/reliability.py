"""Statistical-rigour reliability metrics, computed from a workspace's OWN graded runs.

RIGOR-1 in code: the Fleiss/Cohen kappa, 10-bin ECE + Brier, pairwise-error phi + effective
independent votes, Wilson CIs, floor selective-prediction, and intra-judge stability that the
paper's ``stats_rigor1.md`` computes by hand — recomputed here as pure functions over the
persisted run records the product already stores. Stdlib only (no numpy/scipy).

Every function returns a metric record ``{value, n, insufficient, reason?, ci?}``. The
INSUFFICIENCY flag is load-bearing: a thin / degenerate input (no repeats, no gold, a
zero-variance category, n too small for chance-correction) yields ``insufficient=True`` and a
``None`` value with a human ``reason`` — NEVER a fabricated 0.0-as-data. This is the honesty
contract the product surface renders.

Formulas (verbatim from ``out/linkedin_judge_vs_floor/stats_rigor1.md``):
  - Wilson score interval, z = 1.96 (two-sided 95%).
  - Fleiss' kappa: P_i = (sum_j n_ij^2 - n)/(n(n-1)); kappa = (mean_i P_i - P_e)/(1 - P_e),
    P_e = sum_j p_j^2. (Delegated to ``analysis._fleiss_kappa`` for the core arithmetic.)
  - Cohen's kappa: kappa = (p_o - p_e)/(1 - p_e).
  - ECE (10-bin, equal-width): sum_b (n_b/N) |acc_b - meanconf_b|.
  - Brier: mean (p - 1{correct})^2.
  - phi (pairwise error correlation): (n11 n00 - n10 n01)/sqrt(n1. n0. n.1 n.0); undefined
    when a margin is zero.
  - n_eff = k/(1 + (k-1) rho_bar) with rho_bar the mean pairwise phi of the error indicators.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from lithrim_bench.analysis import _fleiss_kappa

_Z = 1.96  # two-sided 95%


def _metric(
    value: float | None,
    n: int,
    *,
    insufficient: bool = False,
    reason: str | None = None,
    ci: tuple[float, float] | None = None,
    **extra: Any,
) -> dict:
    out: dict = {"value": value, "n": n, "insufficient": insufficient}
    if reason is not None:
        out["reason"] = reason
    out["ci"] = ci
    out.update(extra)
    return out


def _insufficient(reason: str, n: int = 0, **extra: Any) -> dict:
    return _metric(None, n, insufficient=True, reason=reason, **extra)


def _blocked(verdict: Any) -> bool:
    return str(verdict or "").strip().upper() in {"BLOCK", "FAIL", "REJECT"}


# ── Wilson score interval ─────────────────────────────────────────────────────


def wilson_proportion(successes: int, trials: int) -> dict:
    """Wilson 95% score interval for ``successes/trials`` (z = 1.96).

    0 successes is a valid proportion (value 0.0, a real upper bound). 0 TRIALS is
    insufficient — there is nothing to estimate."""
    if trials <= 0:
        return _insufficient("no trials to estimate a proportion")
    p = successes / trials
    z2 = _Z * _Z
    denom = 1.0 + z2 / trials
    center = (p + z2 / (2 * trials)) / denom
    half = (_Z / denom) * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials))
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return _metric(round(p, 6), trials, ci=(round(lo, 6), round(hi, 6)))


# ── Fleiss' kappa (inter-judge agreement across raters, over items) ───────────


def fleiss_kappa(per_item_verdicts: list[dict[str, str]]) -> dict:
    """Fleiss' kappa across raters, over items (reuses ``analysis._fleiss_kappa``).

    ``per_item_verdicts`` is one dict per item, mapping rater -> verdict. Needs >= 2 items
    and >= 2 raters; otherwise the coefficient is undefined and we say so."""
    n_items = len(per_item_verdicts)
    if n_items < 2:
        return _insufficient(
            "need at least 2 graded cases with per-judge votes to measure inter-judge agreement",
            n=n_items,
        )
    n_raters = len(per_item_verdicts[0]) if per_item_verdicts else 0
    if n_raters < 2:
        return _insufficient(
            "need at least 2 judges (raters) to measure inter-judge agreement", n=n_items
        )
    value = _fleiss_kappa(per_item_verdicts)
    if value is None:
        return _insufficient("kappa is undefined on this rater set", n=n_items)
    return _metric(round(value, 6), n_items)


# ── Cohen's kappa vs gold ─────────────────────────────────────────────────────


def cohen_kappa(pred: list[str], gold: list[str]) -> dict:
    """Cohen's kappa between two paired label sequences (a judge vs gold).

    Undefined when either marginal is a single category (p_e == 1) — flagged, never 0/1."""
    if len(pred) != len(gold):
        raise ValueError("pred and gold must be the same length")
    n = len(pred)
    if n == 0:
        return _insufficient("no paired cases to compare against gold")
    p_o = sum(1 for a, b in zip(pred, gold, strict=True) if a == b) / n
    cats = sorted(set(pred) | set(gold))
    pred_marg = Counter(pred)
    gold_marg = Counter(gold)
    p_e = sum((pred_marg.get(c, 0) / n) * (gold_marg.get(c, 0) / n) for c in cats)
    if p_e >= 1.0:
        return _insufficient(
            "kappa is undefined here — every case shares one verdict, so chance agreement is total",
            n=n,
        )
    return _metric(round((p_o - p_e) / (1 - p_e), 6), n)


# ── ECE + Brier over verbalized confidence ────────────────────────────────────


def _confidence_pairs(pairs: list[tuple[float, bool]]) -> list[tuple[float, bool]]:
    out = []
    for conf, correct in pairs:
        if conf is None:
            continue
        out.append((float(conf), bool(correct)))
    return out


def ece(pairs: list[tuple[float, bool]], bins: int = 10) -> dict:
    """10-bin equal-width Expected Calibration Error over (confidence, correct) pairs."""
    pts = _confidence_pairs(pairs)
    N = len(pts)
    if N == 0:
        return _insufficient(
            "no verdicts with both a stated confidence and a gold label to calibrate against"
        )
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for conf, correct in pts:
        # equal-width bins (0,1/b], ..., ((b-1)/b, 1]; conf 0 lands in the first bin.
        idx = min(bins - 1, max(0, math.ceil(conf * bins) - 1)) if conf > 0 else 0
        buckets[idx].append((conf, correct))
    total = 0.0
    for b in buckets:
        if not b:
            continue
        mean_conf = sum(c for c, _ in b) / len(b)
        acc = sum(1 for _, ok in b if ok) / len(b)
        total += (len(b) / N) * abs(acc - mean_conf)
    return _metric(round(total, 6), N)


def brier(pairs: list[tuple[float, bool]]) -> dict:
    """Brier score: mean (confidence - 1{correct})^2 over (confidence, correct) pairs."""
    pts = _confidence_pairs(pairs)
    N = len(pts)
    if N == 0:
        return _insufficient(
            "no verdicts with both a stated confidence and a gold label to score"
        )
    total = sum((conf - (1.0 if correct else 0.0)) ** 2 for conf, correct in pts)
    return _metric(round(total / N, 6), N)


# ── pairwise-error phi + effective independent votes ──────────────────────────


def error_phi(a: list[bool], b: list[bool]) -> dict:
    """Phi coefficient between two judges' per-case error indicators.

    Undefined when a margin is zero (a judge never errs, or always errs) — flagged."""
    if len(a) != len(b):
        raise ValueError("error indicator lists must be the same length")
    n = len(a)
    if n == 0:
        return _insufficient("no shared cases to correlate errors over")
    n11 = sum(1 for x, y in zip(a, b, strict=True) if x and y)
    n10 = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    n01 = sum(1 for x, y in zip(a, b, strict=True) if not x and y)
    n00 = sum(1 for x, y in zip(a, b, strict=True) if not x and not y)
    r1, r0 = n11 + n10, n01 + n00
    c1, c0 = n11 + n01, n10 + n00
    denom = r1 * r0 * c1 * c0
    if denom == 0:
        return _insufficient(
            "error correlation is undefined here — a judge never (or always) errs on these cases",
            n=n,
        )
    phi = (n11 * n00 - n10 * n01) / math.sqrt(denom)
    return _metric(round(phi, 6), n)


def mean_pairwise_phi(err_by_judge: dict[str, list[bool]]) -> dict:
    """Mean of the DEFINED pairwise error-phis across all judge pairs.

    Insufficient when fewer than 2 judges, or when no pair has a defined phi."""
    judges = list(err_by_judge)
    if len(judges) < 2:
        return _insufficient("need at least 2 judges to correlate errors", n=len(judges))
    phis: list[float] = []
    for i in range(len(judges)):
        for j in range(i + 1, len(judges)):
            m = error_phi(err_by_judge[judges[i]], err_by_judge[judges[j]])
            if not m["insufficient"]:
                phis.append(m["value"])
    if not phis:
        return _insufficient(
            "no judge pair has a defined error correlation (each judge is all-right or all-wrong)"
        )
    return _metric(round(sum(phis) / len(phis), 6), len(phis))


def effective_votes(k: int, rho_bar: float) -> dict:
    """n_eff = k / (1 + (k-1) rho_bar), the effective independent votes.

    A heuristic (Kish variance-matching); needs >= 2 judges."""
    if k < 2:
        return _insufficient("need at least 2 judges to reduce to an effective count", n=k)
    denom = 1.0 + (k - 1) * rho_bar
    if denom <= 0:
        return _insufficient("effective-votes denominator is non-positive (anti-correlated)", n=k)
    return _metric(round(k / denom, 6), k)


# ── floor selective-prediction (coverage / conditional accuracy / risk) ───────


def selective_prediction(outcomes: list[dict]) -> dict:
    """Coverage + conditional accuracy + selective risk from floor outcomes.

    Each outcome: ``{covered: bool, correct: bool|None}``. Coverage = covered/total.
    Conditional accuracy = correct/covered (insufficient when the floor covers nothing —
    the honest "it never spoke" state). Selective risk = 1 - conditional accuracy."""
    total = len(outcomes)
    if total == 0:
        return _insufficient("no cases for the floor to cover or abstain on")
    covered = [o for o in outcomes if o.get("covered")]
    n_cov = len(covered)
    coverage = _metric(round(n_cov / total, 6), total)
    if n_cov == 0:
        cond = _insufficient("the floor covered no case here — nothing to score its accuracy on")
        risk = _insufficient("no covered cases, so selective risk is undefined")
        return {
            "insufficient": False,
            "n": total,
            "coverage": coverage,
            "conditional_accuracy": cond,
            "selective_risk": risk,
        }
    n_correct = sum(1 for o in covered if o.get("correct"))
    cond_acc = n_correct / n_cov
    cond = _metric(round(cond_acc, 6), n_cov, ci=wilson_proportion(n_correct, n_cov)["ci"])
    risk = _metric(round(1.0 - cond_acc, 6), n_cov)
    return {
        "insufficient": False,
        "n": total,
        "coverage": coverage,
        "conditional_accuracy": cond,
        "selective_risk": risk,
    }


# ── K-sweep self-consistency curve (RIGOR-1 / Q1 — NEW-G3) ────────────────────


def _majority_verdict(scores: list[float]) -> str | None:
    """The majority BLOCK/PASS verdict of a reviewer's per-sample decision scores.

    Scores are the sampling layer's ``scores_raw`` (0.0=block, 0.5=needs_review, 1.0=pass); a
    sample votes BLOCK iff its score < 0.5, PASS iff > 0.5, and abstains at exactly 0.5. The
    majority is BLOCK / PASS by count, or ``None`` on a tie (or all-abstain) — an undecided case,
    never a coin-flip guess. This is the self-consistency reduction, NOT the frozen consensus."""
    block = sum(1 for s in scores if s < 0.5)
    passed = sum(1 for s in scores if s > 0.5)
    if block > passed:
        return "BLOCK"
    if passed > block:
        return "PASS"
    return None  # tie / all needs_review → undecided


def _variance(scores: list[float]) -> float:
    n = len(scores)
    if n == 0:
        return 0.0
    mean = sum(scores) / n
    return sum((s - mean) ** 2 for s in scores) / n


def sweep_series(cases: list[list[float]], k_max: int | None = None) -> dict:
    """The single-reviewer K-sweep self-consistency curve (Coin-Flip-Judge, arXiv:2606.13685).

    ``cases`` is one list of per-sample decision scores (``scores_raw``) per case — the SAME
    reviewer sampled K times on each case. For each K = 1..``k_max`` we take the first K samples
    of each case (only cases with >= K samples count at that K) and report:

    - ``flip_rate`` — share of ELIGIBLE cases (>= K samples) whose majority verdict at K differs
      from the ``k_max`` converged reference verdict. A tie (``None``) is its own value, so a
      decided-at-K vs undecided-reference (or the reverse) also counts as a flip — the honest
      "you would have answered differently with fewer samples" measure.
    - ``majority_convergence`` — share of cases already decided AND agreeing with the ``k_max``
      reference verdict at K (rises to the decided-share at ``k_max``).
    - ``variance`` — mean per-case variance of the first-K sample scores (the spread that k
      averages out).

    ``flip_rate`` + ``majority_convergence`` carry a Wilson 95% CI (proportions over cases). An
    empty / all-empty input is flagged insufficient — never a fabricated 0.0-as-data. ``k_max``
    defaults to the longest sample run seen (and is clamped to it, so the series never reports a
    K no case can reach)."""
    runs = [c for c in cases if c]
    if not runs:
        return {
            "insufficient": True,
            "reason": "no sampled runs — the K-sweep needs a reviewer's per-sample scores (k >= 1)",
            "k_max": 0,
            "series": [],
        }
    longest = max(len(c) for c in runs)
    kmax = longest if k_max is None else max(1, min(int(k_max), longest))

    # the converged reference verdict per case = its majority over ALL its samples (its own k_max).
    reference = [_majority_verdict(c) for c in runs]

    series: list[dict] = []
    for k in range(1, kmax + 1):
        eligible = [(c, reference[i]) for i, c in enumerate(runs) if len(c) >= k]
        n = len(eligible)
        # flip: majority-at-K != the k_max reference verdict, over ALL eligible cases. A tie
        # (None) is a distinct value, so decided-vs-undecided counts as a flip too.
        flips = sum(1 for c, ref in eligible if _majority_verdict(c[:k]) != ref)
        flip = wilson_proportion(flips, n) if n else _insufficient(
            "no eligible case at this K", n=0
        )
        # convergence: decided-at-K AND == reference.
        converged = sum(
            1 for c, ref in eligible
            if ref is not None and _majority_verdict(c[:k]) == ref
        )
        conv = wilson_proportion(converged, n) if n else _insufficient(
            "no eligible case at this K", n=0
        )
        variances = [_variance(c[:k]) for c, _ in eligible]
        var = _metric(round(sum(variances) / n, 6), n) if n else _insufficient(
            "no eligible case at this K", n=0
        )
        series.append({
            "k": k,
            "flip_rate": flip,
            "majority_convergence": conv,
            "variance": var,
        })

    return {"insufficient": False, "k_max": kmax, "series": series}


# ── intra-judge stability (needs repeats) ─────────────────────────────────────


def intra_judge_stability(repeats_by_judge_case: dict[str, dict[str, list[str]]]) -> dict:
    """Within-judge stability = 1 - mean(per-case instability), where a case's instability
    is the share of NON-modal repeats. Needs at least one (judge, case) with >= 2 repeats;
    otherwise there is nothing to be stable about and we say so."""
    instabilities: list[float] = []
    for _judge, by_case in repeats_by_judge_case.items():
        for _cid, votes in by_case.items():
            if len(votes) < 2:
                continue
            counts = Counter(votes)
            modal = counts.most_common(1)[0][1]
            instabilities.append(1.0 - modal / len(votes))
    if not instabilities:
        return _insufficient(
            "no repeated runs of the same case — intra-judge stability needs repeats (K >= 2)"
        )
    return _metric(round(1.0 - sum(instabilities) / len(instabilities), 6), len(instabilities))


# ── the workspace report (compose all metrics from run records + gold) ────────


def _run_votes(run: dict) -> list[dict]:
    """Per-judge votes from a run record — either the grade-matrix ``votes`` shape or a
    persisted provenance blob's ``stage_results.semantic.judge_votes`` shape."""
    if run.get("votes"):
        return run["votes"]
    semantic = (run.get("stage_results") or {}).get("semantic") or {}
    return semantic.get("judge_votes") or []


def _vote_verdict(v: dict) -> str:
    return str(v.get("vote") or "").strip().upper()


def compute_report(
    *, runs: list[dict], golds: dict[str, set], labeled: set
) -> dict:
    """Compose the full reliability metric set from a workspace's run records + gold.

    ``runs`` are normalized run records (each with ``case_id``, ``verdict``, ``votes``
    [judge_role/vote/confidence/model], and optional ``floor`` {covered, correct}). ``golds``
    maps case_id -> expected flag set; ``labeled`` is the set of gold-bearing case ids.

    Only LABELED runs feed the gold-dependent metrics. Every metric carries its own honest
    insufficiency flag — an empty / thin workspace produces flagged nulls, never zeros."""
    labeled_runs = [r for r in runs if r.get("case_id") in labeled]

    # inter-judge kappa: one item per labeled run, raters = judge roles, verdict = vote.
    per_item: list[dict[str, str]] = []
    for r in labeled_runs:
        votes = _run_votes(r)
        if not votes:
            continue
        item = {str(v.get("judge_role") or f"judge{i}"): _vote_verdict(v) for i, v in enumerate(votes)}
        if item:
            per_item.append(item)
    inter_judge = fleiss_kappa(per_item)

    # cohen kappa vs gold: pooled per-judge BLOCK/PASS vs the case gold verdict.
    # gold-blocked <=> the case carries a non-empty gold flag set.
    pred: list[str] = []
    gold_seq: list[str] = []
    conf_pairs: list[tuple[float, bool]] = []
    err_by_judge: dict[str, list[bool]] = {}
    for r in labeled_runs:
        cid = r.get("case_id")
        gold_block = bool(golds.get(cid))
        gold_label = "BLOCK" if gold_block else "PASS"
        for v in _run_votes(r):
            role = str(v.get("judge_role") or "judge")
            judge_block = _blocked(_vote_verdict(v))
            pred.append("BLOCK" if judge_block else "PASS")
            gold_seq.append(gold_label)
            err_by_judge.setdefault(role, []).append(judge_block != gold_block)
            conf = v.get("confidence")
            if conf is not None:
                conf_pairs.append((float(conf), judge_block == gold_block))
    cohen = cohen_kappa(pred, gold_seq) if pred else _insufficient(
        "no labeled cases with judge votes to compare against gold"
    )

    ece_m = ece(conf_pairs)
    brier_m = brier(conf_pairs)

    phi_m = mean_pairwise_phi(err_by_judge)
    if phi_m["insufficient"]:
        n_eff = _insufficient(
            "cannot reduce to effective votes without a defined error correlation",
            n=len(err_by_judge),
        )
    else:
        n_eff = effective_votes(len(err_by_judge), phi_m["value"])

    # intra-judge stability: repeats of the SAME (judge, case). Grouped from the run set;
    # a workspace with one run per case has no repeats and this reports insufficient.
    repeats: dict[str, dict[str, list[str]]] = {}
    for r in runs:
        cid = r.get("case_id")
        if not cid:
            continue
        for v in _run_votes(r):
            role = str(v.get("judge_role") or "judge")
            repeats.setdefault(role, {}).setdefault(cid, []).append(_vote_verdict(v))
    stability = intra_judge_stability(repeats)

    # floor selective prediction, from each labeled run's floor outcome.
    floor_outcomes: list[dict] = []
    for r in labeled_runs:
        fl = r.get("floor")
        if isinstance(fl, dict) and "covered" in fl:
            floor_outcomes.append({"covered": bool(fl.get("covered")), "correct": fl.get("correct")})
    sel = selective_prediction(floor_outcomes)

    return {
        "n_runs": len(runs),
        "n_labeled_runs": len(labeled_runs),
        "inter_judge_kappa": inter_judge,
        "cohen_kappa_vs_gold": cohen,
        "ece": ece_m,
        "brier": brier_m,
        "error_phi": phi_m,
        "effective_votes": n_eff,
        "intra_judge_stability": stability,
        "selective_prediction": sel,
    }
