"""RIGOR-1 / Q1 (NEW-G3) — the K-sweep self-consistency aggregator.

RED-before-code. `reliability.sweep_series` takes ONE reviewer's per-case sample scores (the
`scores_raw` already captured in each run blob — a list of per-sample decision scalars in
{0.0=block, 0.5=needs_review, 1.0=pass}) and reports, for each K = 1..K_max, the self-consistency
of the single reviewer as you spend more samples:

  - flip_rate           — share of cases whose majority verdict at K differs from the K_max
                          "converged" reference verdict (the anecdote→curve of Coin-Flip-Judge).
  - majority_convergence — share of cases already decided-and-agreeing-with-K_max at K.
  - variance            — mean per-case variance of the first-K sample scores.

Each per-K row carries Wilson CIs on flip_rate + majority_convergence (z=1.96), and the honest
insufficiency contract: a thin/degenerate input (no cases, or every case shorter than K) yields a
flagged null, NEVER a fabricated 0.0-as-data.

No numpy/scipy — stdlib only. No network. Small hand-checkable fixtures.
"""
from __future__ import annotations

from lithrim_bench import reliability as R

BLOCK, MID, PASS = 0.0, 0.5, 1.0


# ── shape + insufficiency contract ────────────────────────────────────────────


def test_no_cases_is_insufficient_not_zeros():
    m = R.sweep_series([], k_max=5)
    assert m["insufficient"] is True
    assert m["series"] == []
    assert m["reason"]


def test_k_max_defaults_to_the_longest_sample_run():
    # k_max omitted -> the aggregator sweeps up to the longest scores_raw it sees.
    m = R.sweep_series([[PASS, PASS, BLOCK]])
    ks = [row["k"] for row in m["series"]]
    assert ks == [1, 2, 3]


def test_series_is_k_1_through_k_max():
    m = R.sweep_series([[PASS, PASS, PASS, PASS, PASS]], k_max=5)
    assert [row["k"] for row in m["series"]] == [1, 2, 3, 4, 5]
    assert m["insufficient"] is False
    assert m["k_max"] == 5


# ── flip-rate (self-consistency vs the converged K_max verdict) ───────────────


def test_unanimous_case_never_flips():
    # a perfectly self-consistent reviewer: every K agrees with K_max -> flip_rate 0 at every K.
    m = R.sweep_series([[PASS, PASS, PASS, PASS, PASS]], k_max=5)
    for row in m["series"]:
        assert row["flip_rate"]["value"] == 0.0


def test_flip_at_low_k_resolves_by_k_max():
    # scores: B B P P P  -> K=1 majority=BLOCK, K=5 majority=PASS (3P/2B). The K=1 verdict FLIPS
    # relative to the converged K=5 verdict; by K=5 flip_rate is 0 (it IS the reference).
    case = [BLOCK, BLOCK, PASS, PASS, PASS]
    m = R.sweep_series([case], k_max=5)
    by_k = {row["k"]: row for row in m["series"]}
    assert by_k[1]["flip_rate"]["value"] == 1.0  # K=1 says BLOCK, K_max says PASS -> flipped
    assert by_k[5]["flip_rate"]["value"] == 0.0  # K_max agrees with itself
    # a real proportion carries a Wilson CI (z=1.96), never a bare number
    assert isinstance(by_k[1]["flip_rate"]["ci"], tuple)


def test_flip_rate_is_a_proportion_over_cases():
    # two cases: one flips at K=1 (B P), one is stable (P P). flip_rate at K=1 = 1/2.
    flips = [BLOCK, PASS]  # K=1 BLOCK, K=2 PASS -> flipped at K=1
    stable = [PASS, PASS]
    m = R.sweep_series([flips, stable], k_max=2)
    by_k = {row["k"]: row for row in m["series"]}
    assert abs(by_k[1]["flip_rate"]["value"] - 0.5) < 1e-9
    assert by_k[1]["flip_rate"]["n"] == 2  # the denominator is the case count with >= K samples


# ── majority-convergence ──────────────────────────────────────────────────────


def test_majority_convergence_rises_to_one_at_k_max():
    # by construction the K_max verdict IS the reference -> every case that is decisive at K_max
    # counts as converged there. A decisive unanimous case is converged from K=1.
    m = R.sweep_series([[PASS, PASS, PASS]], k_max=3)
    by_k = {row["k"]: row for row in m["series"]}
    assert by_k[1]["majority_convergence"]["value"] == 1.0
    assert by_k[3]["majority_convergence"]["value"] == 1.0


def test_tie_is_not_converged():
    # B P at K=2 is a tie -> undecided -> NOT converged at K=2 (it never agrees with a decisive ref).
    # single case whose K_max is itself a tie -> the reference is undecided; convergence stays 0.
    m = R.sweep_series([[BLOCK, PASS]], k_max=2)
    by_k = {row["k"]: row for row in m["series"]}
    assert by_k[2]["majority_convergence"]["value"] == 0.0


# ── variance (self-consistency spread) ────────────────────────────────────────


def test_variance_zero_for_unanimous_grows_with_disagreement():
    unanimous = R.sweep_series([[PASS, PASS, PASS]], k_max=3)
    split = R.sweep_series([[BLOCK, PASS, PASS]], k_max=3)
    u3 = {r["k"]: r for r in unanimous["series"]}[3]["variance"]["value"]
    s3 = {r["k"]: r for r in split["series"]}[3]["variance"]["value"]
    assert u3 == 0.0
    assert s3 > 0.0


# ── per-K denominator respects short runs (only cases with >= K samples count) ─


def test_short_runs_drop_out_of_high_k():
    # one 5-sample case, one 2-sample case. At K=3 only the 5-sample case has >= 3 samples.
    m = R.sweep_series([[PASS] * 5, [PASS, PASS]], k_max=5)
    by_k = {row["k"]: row for row in m["series"]}
    assert by_k[2]["flip_rate"]["n"] == 2  # both cases have >= 2 samples
    assert by_k[3]["flip_rate"]["n"] == 1  # only the 5-sample case has >= 3
    assert by_k[5]["flip_rate"]["n"] == 1
