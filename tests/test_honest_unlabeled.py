"""HONEST-1 — honest unlabeled mode.

The grade path must NOT fabricate an accuracy/calibration number on data with no
ground truth (the honesty-thesis contradiction; [[byo-data-ingestion-cliff]] blocker
#4). Today calibration_check keys on ``expected_compliance_verdict`` and
``normalize_expected_verdict(None) -> set()`` collapses an unlabeled case to a
``verdict_match_rate 0.0 / status WARN`` + a meaningless ECE. The labeled path stays
byte-equivalent. Pure over report.py — no pack load, no network.
"""

from lithrim_bench.harness.report import calibration, calibration_check


def _rec(expected, verdict="reject", *, n_conf=2, ece=0.1):
    return {
        "provenance": {"expected_compliance_verdict": expected},
        "composite": {"verdict": verdict},
        "calibration": {"n_with_confidence": n_conf, "ece": ece},
    }


# A1 — unlabeled is honest (RED today: returns 0.0 / WARN + a fabricated ECE)
def test_calibration_check_unlabeled_is_honest():
    out = calibration_check([_rec(None)])
    assert out["label_status"] == "unlabeled"
    assert out["status"] == "unlabeled"
    assert out["verdict_match_rate"] is None
    assert out["ece"] is None
    assert out["caveat"]  # an explicit "no ground truth" note
    # neither a manufactured FAILURE nor a manufactured WIN may leak
    assert out["status"] not in ("PASS", "WARN")
    assert out["verdict_match_rate"] not in (0.0, 1.0)


# A1b (W2) — the per-case calibration() suppresses ECE when unlabeled; labeled path real
def test_calibration_unlabeled_suppresses_ece():
    result = {
        "semantic": {
            "judge_votes": [
                {"vote": "BLOCK", "confidence": 0.9},
                {"vote": "PASS", "confidence": None},
            ]
        }
    }
    out = calibration(result, expected_block=False, labeled=False)
    assert out["ece"] is None
    assert out["reliability_bins"] == []
    assert out["n_with_confidence"] == 1  # counts stay factual
    lab = calibration(result, expected_block=False, labeled=True)
    assert lab["ece"] is not None  # labeled path unchanged: a real ECE is produced


# A2a — labeled + match is unchanged (PASS / 1.0 / labeled)
def test_calibration_check_labeled_match_unchanged():
    out = calibration_check([_rec("reject", "reject")])
    assert out["label_status"] == "labeled"
    assert out["status"] == "PASS"
    assert out["verdict_match_rate"] == 1.0


# A2b — labeled + mismatch STILL reports a genuine WARN (non-vacuous both directions)
def test_calibration_check_labeled_mismatch_still_warns():
    out = calibration_check([_rec("approve", "reject")])
    assert out["label_status"] == "labeled"
    assert out["status"] == "WARN"
    assert out["verdict_match_rate"] == 0.0


# A3 — partial batch: rate over the labeled subset, label_status partial, caveat names the gap
def test_calibration_check_partial_batch():
    labeled = _rec("reject", "reject", n_conf=1, ece=0.0)
    unlabeled = _rec(None, "approve", n_conf=1, ece=0.0)
    out = calibration_check([labeled, unlabeled])
    assert out["label_status"] == "partial"
    assert out["verdict_match_rate"] == 1.0  # 1/1 labeled matched
    assert out["status"] == "PASS"
    assert out["caveat"] and "unlabeled" in out["caveat"].lower()
