"""Acceptance tests for the reviewer-benchmark scorer (offline; synthetic records + the 10 pilot records)."""

from pathlib import Path

import pytest

from repro.ragtruth import score_reviewer as sr

PILOT = Path("out/ragtruth-pilot10b/runs")
LABELS = Path("out/ragtruth-data2txt/test_cases.jsonl")


def _rec(
    no_floor="BLOCK",
    state="ESCALATED",
    raw="BLOCK",
    codes=(("risk_judge", "UNSUPPORTED_ASSERTION"),),
    floor_block=False,
):
    votes = [
        {"judge_role": r, "vote": "BLOCK", "findings": [c]} for r, c in codes
    ]  # real shape: code strings
    return {
        "result": {
            "verdict": raw,
            "semantic": {"judge_votes": votes},
            "provenance": {"cost_tokens": {"total": 1}},
        },
        "grounded": {
            "verdict_no_floor": no_floor,
            "floor_blocks": [{"contract_type": "value_grounding", "injected": True}]
            if floor_block
            else [],
        },
        "composite": {"review": {"state": state}},
    }


def test_mapping_rules_are_the_preregistered_ones():
    assert sr.council_alone(_rec("BLOCK")) == "halu"
    assert sr.council_alone(_rec("PASS")) == "clean"
    assert sr.council_alone(_rec("WARN")) == "clean"
    assert sr.council_alone(_rec("WARN"), warn_is_halu=True) == "halu"
    assert sr.combined(_rec(state="FLAGGED")) == "halu"
    assert sr.combined(_rec(state="CLEARED")) == "clean"
    assert sr.combined(_rec(state="ESCALATED")) == "abstain"
    assert sr.combined(_rec(state="ESCALATED"), escalate_is_halu=True) == "halu"


def test_abstention_is_a_recall_miss_and_excluded_from_precision():
    m = sr.prf(preds=["halu", "abstain", "clean", "halu"], golds=[True, True, False, False])
    assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 1  # the abstained positive counts as missed
    assert (
        m["precision"] == 0.5
        and m["recall"] == 0.5
        and m["coverage"] == 0.75
        and m["abstained"] == 1
    )


def test_bootstrap_resamples_sources_not_responses_and_is_deterministic():
    # two sources; source A: arm C wins on all 3 rows, source B: arm B wins on all 3 rows
    rows = [dict(source_id="A", gold=True, b="clean", c="halu")] * 3 + [
        dict(source_id="B", gold=True, b="halu", c="abstain")
    ] * 3
    r1 = sr.paired_bootstrap(rows, n=200, seed=0)
    r2 = sr.paired_bootstrap(rows, n=200, seed=0)
    assert r1 == r2
    assert (
        r1["delta_f1_ci"][0] < 0 < r1["delta_f1_ci"][1]
    )  # sources flip the sign -> CI must span 0
    assert r1["draws"] == 200 and r1["unit"] == "source_id"


def test_ledger_reports_precision_with_wilson_bounds_and_excludes_missing_context():
    recs = {
        f"c{i}": _rec(
            codes=(("risk_judge", "UNSUPPORTED_ASSERTION"), ("policy_judge", "MISSING_CONTEXT"))
        )
        for i in range(4)
    }
    golds = {"c0": True, "c1": True, "c2": True, "c3": False}
    led = sr.ledger(recs, golds)
    row = next(r for r in led if r["check"] == "risk_judge:UNSUPPORTED_ASSERTION")
    assert (
        row["n"] == 4
        and row["hits"] == 3
        and row["precision"] == 0.75
        and row["wilson_low"] < 0.75 <= row["wilson_high"]
    )
    assert not [r for r in led if "MISSING_CONTEXT" in r["check"]]
    assert any(
        r["check"] == "MISSING_CONTEXT(excluded)" and r["n"] == 4 for r in sr.excluded_signals(recs)
    )


def test_scorer_refuses_records_that_carry_gold():
    bad = _rec()
    bad["expected_safety_flags"] = []
    with pytest.raises(ValueError, match="gold"):
        sr.score({"c0": bad}, {"c0": {"halu": True, "source_id": "s", "model": "m"}})


@pytest.mark.skipif(not PILOT.exists() or not LABELS.exists(), reason="pilot records not present")
def test_pilot_fixture_smoke_matches_the_hand_count():
    recs = sr.load_records([PILOT])
    golds = sr.load_labels(LABELS, only=set(recs))
    rep = sr.score(recs, golds)
    assert rep["n"] == 10 and rep["base_rate"] == 0.7
    b = rep["arms"]["council_alone_primary"]
    assert b["tp"] == 7 and b["fp"] == 3 and b["fn"] == 0  # hand-counted from the pilot readout
    assert rep["arms"]["combined_primary"]["abstained"] == 8
    assert rep["arms"]["trivial_always_halu"]["precision"] == 0.7
    assert rep["per_generator"] and rep["ledger"]
