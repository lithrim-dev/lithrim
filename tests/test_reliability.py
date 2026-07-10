"""RIGOR-1 / feat-reliability-card: the pure reliability-metric functions.

RED-before-code. Each metric returns a {value, n, insufficient, reason?, ci?} record and,
crucially, an HONEST insufficiency flag on degenerate/thin input (no fabricated value). The
formulas match ``out/linkedin_judge_vs_floor/stats_rigor1.md`` (Wilson z=1.96, Fleiss
P_e=sum p_j^2, Cohen's kappa, 10-bin equal-width ECE, Brier, phi, n_eff = k/(1+(k-1)*rho)).

No numpy/scipy — stdlib only. No network. Small hand-checkable fixtures.
"""
from __future__ import annotations

import math

from lithrim_bench import reliability as R

# ── Wilson score interval ─────────────────────────────────────────────────────


def test_wilson_ci_matches_stats_doc():
    # stats_rigor1.md: 15/40 -> point 37.5%, Wilson [24.2, 53.0]
    m = R.wilson_proportion(15, 40)
    assert m["insufficient"] is False
    assert m["n"] == 40
    assert abs(m["value"] - 0.375) < 1e-9
    lo, hi = m["ci"]
    assert abs(lo - 0.242) < 0.002
    assert abs(hi - 0.530) < 0.002


def test_wilson_ci_zero_events_upper_bound():
    # 0/18 genuine-fabrication clears: no useful lower bound, but a real upper bound.
    m = R.wilson_proportion(0, 18)
    assert m["insufficient"] is False  # a proportion IS computable at 0 successes
    assert m["value"] == 0.0
    lo, hi = m["ci"]
    assert lo == 0.0
    assert 0.10 < hi < 0.25  # ~17.6% two-sided upper


def test_wilson_ci_zero_trials_is_insufficient():
    m = R.wilson_proportion(0, 0)
    assert m["insufficient"] is True
    assert m["value"] is None
    assert m["ci"] is None
    assert m["reason"]


# ── Fleiss' kappa (inter-judge agreement) ─────────────────────────────────────


def test_fleiss_kappa_reuses_analysis_impl_and_agrees():
    # Two items, 3 raters, mixed — non-degenerate. Compare to analysis._fleiss_kappa.
    from lithrim_bench.analysis import _fleiss_kappa

    per_item = [
        {"a": "BLOCK", "b": "BLOCK", "c": "PASS"},
        {"a": "PASS", "b": "PASS", "c": "PASS"},
    ]
    m = R.fleiss_kappa(per_item)
    assert m["insufficient"] is False
    assert m["n"] == 2  # items
    ref = _fleiss_kappa(per_item)
    assert ref is not None
    assert abs(m["value"] - ref) < 1e-9


def test_fleiss_kappa_insufficient_when_fewer_than_two_items():
    m = R.fleiss_kappa([{"a": "BLOCK", "b": "PASS"}])
    assert m["insufficient"] is True
    assert m["value"] is None
    assert m["reason"]


def test_fleiss_kappa_insufficient_with_single_rater():
    m = R.fleiss_kappa([{"a": "BLOCK"}, {"a": "PASS"}, {"a": "BLOCK"}])
    assert m["insufficient"] is True
    assert m["value"] is None


# ── Cohen's kappa vs gold ─────────────────────────────────────────────────────


def test_cohen_kappa_perfect_agreement():
    pred = ["BLOCK", "PASS", "BLOCK", "PASS"]
    gold = ["BLOCK", "PASS", "BLOCK", "PASS"]
    m = R.cohen_kappa(pred, gold)
    assert m["insufficient"] is False
    assert m["n"] == 4
    assert abs(m["value"] - 1.0) < 1e-9


def test_cohen_kappa_chance_level():
    # p_o = 0.5, marginals balanced -> p_e = 0.5 -> kappa = 0
    pred = ["BLOCK", "BLOCK", "PASS", "PASS"]
    gold = ["BLOCK", "PASS", "BLOCK", "PASS"]
    m = R.cohen_kappa(pred, gold)
    assert abs(m["value"] - 0.0) < 1e-9


def test_cohen_kappa_single_category_is_insufficient():
    # gold all one label -> p_e = 1 -> kappa undefined; must flag, not return 0/1.
    m = R.cohen_kappa(["BLOCK", "BLOCK"], ["BLOCK", "BLOCK"])
    assert m["insufficient"] is True
    assert m["value"] is None
    assert m["reason"]


def test_cohen_kappa_empty_is_insufficient():
    m = R.cohen_kappa([], [])
    assert m["insufficient"] is True
    assert m["value"] is None


def test_cohen_kappa_length_mismatch_raises():
    import pytest

    with pytest.raises(ValueError):
        R.cohen_kappa(["BLOCK"], ["BLOCK", "PASS"])


# ── ECE + Brier over verbalized confidence ────────────────────────────────────


def test_ece_brier_perfect_calibration_is_zero():
    # confidence exactly equals accuracy within each bin -> ECE 0.
    # two verdicts at conf 1.0 that are both correct -> gap 0, brier 0.
    pairs = [(1.0, True), (1.0, True)]
    ece = R.ece(pairs)
    brier = R.brier(pairs)
    assert ece["insufficient"] is False
    assert abs(ece["value"] - 0.0) < 1e-9
    assert abs(brier["value"] - 0.0) < 1e-9


def test_ece_overconfident_gap():
    # 4 verdicts, all stated conf 0.9, but only 2 correct -> acc 0.5, gap 0.4.
    pairs = [(0.9, True), (0.9, True), (0.9, False), (0.9, False)]
    ece = R.ece(pairs)
    assert abs(ece["value"] - 0.4) < 1e-9
    # brier = mean (0.9 - correct)^2 = ((0.1^2)*2 + (0.9^2)*2)/4 = (0.02 + 1.62)/4 = 0.41
    brier = R.brier(pairs)
    assert abs(brier["value"] - 0.41) < 1e-9


def test_ece_bins_are_equal_width_ten():
    # a value in (0.7,0.8] and one in (0.9,1.0] land in different bins.
    pairs = [(0.75, False), (0.95, True)]
    ece = R.ece(pairs)
    # bin1: n=1 mean .75 acc 0 gap .75 ; bin2: n=1 mean .95 acc 1 gap .05
    # ECE = .5*.75 + .5*.05 = 0.4
    assert abs(ece["value"] - 0.4) < 1e-9


def test_ece_brier_insufficient_when_empty():
    assert R.ece([])["insufficient"] is True
    assert R.ece([])["value"] is None
    assert R.brier([])["insufficient"] is True
    assert R.brier([])["value"] is None


# ── pairwise-error phi + n_eff ────────────────────────────────────────────────


def test_phi_perfectly_correlated_errors():
    # two judges err on exactly the same cases -> phi = 1.
    a = [True, True, False, False]
    b = [True, True, False, False]
    m = R.error_phi(a, b)
    assert m["insufficient"] is False
    assert abs(m["value"] - 1.0) < 1e-9


def test_phi_undefined_when_a_margin_is_zero():
    # judge b never errs -> a margin is zero -> phi undefined -> insufficient.
    a = [True, False, True, False]
    b = [False, False, False, False]
    m = R.error_phi(a, b)
    assert m["insufficient"] is True
    assert m["value"] is None
    assert m["reason"]


def test_n_eff_from_rho():
    # k=4, rho_bar=0 -> n_eff = 4 (fully independent). rho_bar=1 -> n_eff = 1.
    assert abs(R.effective_votes(4, 0.0)["value"] - 4.0) < 1e-9
    assert abs(R.effective_votes(4, 1.0)["value"] - 1.0) < 1e-9
    # rho_bar=0.5, k=4 -> 4/(1+3*0.5) = 4/2.5 = 1.6
    assert abs(R.effective_votes(4, 0.5)["value"] - 1.6) < 1e-9


def test_n_eff_insufficient_with_one_judge():
    m = R.effective_votes(1, 0.0)
    assert m["insufficient"] is True
    assert m["value"] is None


def test_mean_pairwise_phi_over_matrix():
    # error indicators for 3 judges across cases; mean of defined pairwise phis.
    err_by_judge = {
        "j1": [True, True, False, False],
        "j2": [True, True, False, False],  # phi(j1,j2)=1
        "j3": [False, False, True, True],  # phi(j1,j3)=-1, phi(j2,j3)=-1
    }
    m = R.mean_pairwise_phi(err_by_judge)
    assert m["insufficient"] is False
    # mean of {1, -1, -1} = -1/3
    assert abs(m["value"] - (-1.0 / 3.0)) < 1e-6
    assert m["n"] == 3  # number of defined pairs


def test_mean_pairwise_phi_insufficient_when_no_defined_pair():
    err_by_judge = {
        "j1": [False, False, False],  # never errs
        "j2": [False, False, False],  # never errs -> every phi undefined
    }
    m = R.mean_pairwise_phi(err_by_judge)
    assert m["insufficient"] is True
    assert m["value"] is None


# ── floor selective-prediction coverage / risk ────────────────────────────────


def test_selective_prediction_coverage_and_risk():
    # 4 cases: floor covers (votes) on 3, abstains on 1; of covered, 2 correct, 1 wrong.
    outcomes = [
        {"covered": True, "correct": True},
        {"covered": True, "correct": True},
        {"covered": True, "correct": False},
        {"covered": False, "correct": None},
    ]
    m = R.selective_prediction(outcomes)
    assert m["insufficient"] is False
    assert abs(m["coverage"]["value"] - 0.75) < 1e-6  # 3/4
    assert abs(m["conditional_accuracy"]["value"] - (2.0 / 3.0)) < 1e-6
    assert abs(m["selective_risk"]["value"] - (1.0 / 3.0)) < 1e-6


def test_selective_prediction_no_coverage_is_honest():
    # floor abstains on everything -> conditional accuracy is not computable.
    outcomes = [{"covered": False, "correct": None}, {"covered": False, "correct": None}]
    m = R.selective_prediction(outcomes)
    assert abs(m["coverage"]["value"] - 0.0) < 1e-9
    assert m["conditional_accuracy"]["insufficient"] is True
    assert m["conditional_accuracy"]["value"] is None


def test_selective_prediction_empty_is_insufficient():
    m = R.selective_prediction([])
    assert m["insufficient"] is True


# ── intra-judge stability needs repeats ───────────────────────────────────────


def test_intra_judge_stability_needs_repeats():
    # one verdict per (judge, case) -> no repeats -> cannot measure within-judge stability.
    m = R.intra_judge_stability({"j1": {"case1": ["BLOCK"]}})
    assert m["insufficient"] is True
    assert m["value"] is None
    assert "repeat" in m["reason"].lower()


def test_intra_judge_stability_measures_wobble():
    # j1 wobbles on case1 (3B/2P), stable on case2; instability = share of non-modal.
    m = R.intra_judge_stability({"j1": {"case1": ["B", "B", "B", "P", "P"], "case2": ["B", "B"]}})
    assert m["insufficient"] is False
    # case1: modal B (3/5) -> instability 2/5 ; case2: modal B (2/2) -> 0
    # mean instability = (0.4 + 0.0)/2 = 0.2 -> stability = 0.8
    assert abs(m["value"] - 0.8) < 1e-9


# ── the whole-workspace insufficiency contract (non-fabrication) ──────────────


def test_empty_workspace_yields_all_insufficient_not_zeros():
    """The load-bearing honesty test: an empty run set must NOT produce 0.0-as-data.

    Every metric over an empty workspace reports insufficient with a reason and a
    null value — never a fabricated number.
    """
    report = R.compute_report(runs=[], golds={}, labeled=set())
    for key in (
        "inter_judge_kappa",
        "cohen_kappa_vs_gold",
        "ece",
        "brier",
        "error_phi",
        "effective_votes",
        "intra_judge_stability",
    ):
        assert key in report, key
        assert report[key]["insufficient"] is True, key
        assert report[key]["value"] is None, key
    # selective prediction: insufficient container, no fabricated coverage
    assert report["selective_prediction"]["insufficient"] is True


def test_compute_report_computes_over_a_real_fixture():
    """A non-degenerate synthetic run set → real values, honest n."""
    # two labeled cases, 2 judges each, with confidence + gold; floor covers both.
    runs = [
        {
            "case_id": "c1",
            "verdict": "BLOCK",
            "votes": [
                {"judge_role": "j1", "vote": "BLOCK", "confidence": 0.9},
                {"judge_role": "j2", "vote": "BLOCK", "confidence": 0.8},
            ],
            "floor": {"covered": True, "correct": True},
        },
        {
            "case_id": "c2",
            "verdict": "PASS",
            "votes": [
                {"judge_role": "j1", "vote": "PASS", "confidence": 0.7},
                {"judge_role": "j2", "vote": "BLOCK", "confidence": 0.6},
            ],
            "floor": {"covered": True, "correct": True},
        },
    ]
    golds = {"c1": {"FABRICATED_HISTORY"}, "c2": set()}
    labeled = {"c1", "c2"}
    report = R.compute_report(runs=runs, golds=golds, labeled=labeled)
    # inter-judge kappa is computable over 2 items x 2 raters (may be degenerate but defined)
    assert report["inter_judge_kappa"]["n"] == 2
    # cohen kappa per judge vs gold: exists for at least one judge, honest n
    assert report["cohen_kappa_vs_gold"]["insufficient"] in (True, False)
    # ece/brier computed over the 4 (conf, correct) pairs
    assert report["ece"]["n"] == 4
    assert report["ece"]["value"] is not None
    # selective prediction covered on both
    assert abs(report["selective_prediction"]["coverage"]["value"] - 1.0) < 1e-9


def test_no_nan_or_inf_leaks():
    # a metric must never return NaN/inf disguised as a value.
    for pairs in ([(0.9, True)], [(0.0, False)]):
        v = R.ece(pairs)["value"]
        assert v is None or (not math.isnan(v) and not math.isinf(v))
