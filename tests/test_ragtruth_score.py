"""``scripts/ragtruth_score.py``: response-level and span-level scoring against human spans.

The span metric is the paper's: a predicted span is a hit when it overlaps a human span by
character range; a human span is recalled when any predicted span overlaps it. Judge
evidence arrives as quotes, so locating a quote in the response is part of the contract, and
a quote that cannot be located is a counted miss, never a silent drop."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ragtruth_score", REPO / "scripts/ragtruth_score.py")
rs = importlib.util.module_from_spec(_spec)
sys.modules["ragtruth_score"] = rs
_spec.loader.exec_module(rs)

RESPONSE = "The venue opens at 6 pm and offers valet parking. Reservations are accepted."


def _case(cid: str, task: str, labels: list[tuple[int, int]]) -> dict:
    return {
        "case_id": cid,
        "artifacts": [{"type": "generated_response", "content": RESPONSE}],
        "ragtruth": {
            "task_type": task,
            "labels": [
                {"start": s, "end": e, "text": RESPONSE[s:e], "label_type": "Evident Conflict"}
                for s, e in labels
            ],
        },
    }


def _audit(verdict: str, quotes: list[str], role: str = "ragtruth_detector") -> dict:
    return {
        "grounded_verdict": verdict,
        "judges": [
            {
                "judge_role": role,
                "evidence": [
                    {
                        "judge": role,
                        "violation_code": "SOURCE_CONTRADICTION",
                        "spans": [{"quote": q}],
                    }
                    for q in quotes
                ],
            }
        ],
    }


def test_locate_exact_case_insensitive_and_prefix_fallback():
    assert rs.locate("valet parking", RESPONSE) == (
        RESPONSE.index("valet"),
        RESPONSE.index("valet") + 13,
    )
    assert rs.locate("VALET PARKING", RESPONSE) == rs.locate("valet parking", RESPONSE)
    assert rs.locate("offers valet parking and a bar", RESPONSE) is not None  # prefix match
    assert rs.locate("nothing like this", RESPONSE) is None


def test_scores_response_level_and_span_overlap_per_task():
    valet = (RESPONSE.index("valet"), RESPONSE.index("valet") + len("valet parking"))
    resv = (RESPONSE.index("Reservations"), len(RESPONSE))
    rows = [
        _case("a", "Data2txt", [valet]),  # hallucinated; judge cites the right span
        _case("b", "Data2txt", []),  # clean; judge wrongly flags
        _case("c", "QA", [resv]),  # hallucinated; judge cites a span that misses it
        _case("d", "QA", []),  # clean; judge clears
        _case("e", "Summary", [valet]),  # ungraded
    ]
    audits = {
        "a": _audit("BLOCK", ["offers valet parking"]),
        "b": _audit("BLOCK", ["opens at 6 pm"]),
        "c": _audit("BLOCK", ["definitely not in the text"]),
        "d": _audit("PASS", []),
    }
    res = rs.score(rows, audits)
    d2t, qa, summ, overall = (res["per_task"][k] for k in ("Data2txt", "QA", "Summary", "OVERALL"))
    assert (d2t["r_tp"], d2t["r_fp"], d2t["r_fn"]) == (1, 1, 0)
    assert (d2t["s_tp"], d2t["s_fp"], d2t["s_fn"]) == (1, 1, 0)
    assert (qa["r_tp"], qa["r_fp"], qa["r_fn"]) == (1, 0, 0)
    assert (qa["s_tp"], qa["s_fp"], qa["s_fn"]) == (0, 1, 1), "an unlocatable quote is a miss"
    assert summ["ungraded"] == 1 and summ["graded"] == 0
    assert (overall["r_tp"], overall["r_fp"], overall["r_fn"], overall["ungraded"]) == (2, 1, 0, 1)
    assert res["unlocated"] == [("c", "definitely not in the text")]
    assert overall.get("refused", 0) == 0


def test_a_failed_judge_call_is_counted_as_refused_per_task():
    rows = [_case("a", "QA", [(0, 3)])]
    audit = _audit("PASS", [])
    audit["judges"][0]["errors"] = ["ContentPolicyViolationError"]
    res = rs.score(rows, {"a": audit})
    qa = res["per_task"]["QA"]
    assert (
        qa["refused"] == 1 and qa["r_fn"] == 1
    )  # refused positive: a miss, and visible as refused
    assert rs._prf(2, 1, 0) == (2 / 3, 1.0, 0.8)
