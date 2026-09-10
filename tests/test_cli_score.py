"""``lithrim score``: response-level and span-level scoring against human spans.

The span metric is the paper's: a predicted span is a hit when it overlaps a human span by
character range; a human span is recalled when any predicted span overlaps it. Judge
evidence arrives as quotes, so locating a quote in the response is part of the contract, and
a quote that cannot be located is a counted miss, never a silent drop. Where a case keeps its
task and spans is the importer manifest's business; a bare case uses the top-level fields."""

from __future__ import annotations

from lithrim_bench.cli import scoring as rs

RESPONSE = "The venue opens at 6 pm and offers valet parking. Reservations are accepted."


def _case(cid: str, task: str, labels: list[tuple[int, int]], *, bare: bool = False) -> dict:
    spans = [
        {"start": s, "end": e, "text": RESPONSE[s:e], "label_type": "Evident Conflict"}
        for s, e in labels
    ]
    case = {"case_id": cid, "artifacts": [{"type": "generated_response", "content": RESPONSE}]}
    if bare:
        case.update({"task": task, "gold_spans": spans})
    else:
        case["ragtruth"] = {"task_type": task, "labels": spans}
    return case


def _audit(verdict: str, quotes: list[str], role: str = "ragtruth_detector") -> dict:
    return {
        "grounded_verdict": verdict,
        "judges": [
            {
                "judge_role": role,
                "findings": ["SOURCE_CONTRADICTION"] if quotes else [],
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
    res = rs.score(rows, audits, pack="_core")
    d2t, qa, summ, overall = (res["per_task"][k] for k in ("Data2txt", "QA", "Summary", "OVERALL"))
    assert (d2t["r_tp"], d2t["r_fp"], d2t["r_fn"]) == (1, 1, 0)
    assert (d2t["s_tp"], d2t["s_fp"], d2t["s_fn"]) == (1, 1, 0)
    assert (qa["r_tp"], qa["r_fp"], qa["r_fn"]) == (1, 0, 0)
    assert (qa["s_tp"], qa["s_fp"], qa["s_fn"]) == (0, 1, 1), "an unlocatable quote is a miss"
    assert summ["ungraded"] == 1 and summ["graded"] == 0
    assert (overall["r_tp"], overall["r_fp"], overall["r_fn"], overall["ungraded"]) == (2, 1, 0, 1)
    assert res["unlocated"] == [("c", "definitely not in the text")]
    assert overall.get("refused", 0) == 0


def test_a_bare_case_scores_through_the_top_level_fields_and_renders_both_vocabularies():
    valet = (RESPONSE.index("valet"), RESPONSE.index("valet") + len("valet parking"))
    rows = [_case("a", "Data2txt", [valet], bare=True), _case("b", "Other", [], bare=True)]
    audits = {"a": _audit("BLOCK", ["valet parking"]), "b": _audit("PASS", [])}
    res = rs.score(rows, audits, pack="_core")
    assert res["per_task"]["Data2txt"]["s_tp"] == 1 and res["per_task"]["Other"]["r_tn"] == 1
    text = rs.render(res, rs.resolve_vocabulary("ragtruth", "_core"))
    assert (
        "Data2txt" in text and "SOURCE_CONTRADICTION [Evident Conflict / Subtle Conflict]" in text
    )
    assert "verdict rule:" in text
    assert "per code: not applicable" in rs.render(res, None, predictions=True)


def test_a_failed_judge_call_is_counted_as_refused_per_task():
    rows = [_case("a", "QA", [(0, 3)])]
    audit = _audit("PASS", [])
    audit["judges"][0]["errors"] = ["ContentPolicyViolationError"]
    res = rs.score(rows, {"a": audit}, pack="_core")
    qa = res["per_task"]["QA"]
    assert (
        qa["refused"] == 1 and qa["r_fn"] == 1
    )  # refused positive: a miss, and visible as refused
    assert rs._prf(2, 1, 0) == (2 / 3, 1.0, 0.8)


def test_audits_for_a_grade_file_name_exactly_its_runs(monkeypatch):
    calls = []
    monkeypatch.setattr(rs.http, "get", lambda bff, path: calls.append(path) or {"path": path})
    grade = {"matrix": [{"case_id": "a", "run_id": "r1"}, {"case_id": "b"}]}
    audits = rs.audits_for_grade("http://x", grade, [{"case_id": "a"}, {"case_id": "b"}])
    assert calls == ["/v1/runs/r1/audit"] and list(audits) == ["a"]


def test_table_projects_the_score_as_rows_in_both_vocabularies():
    """UI-JOURNEY-1 (B5): the JSON projection a service serves carries the same numbers
    ``render`` prints, with the dataset's terms and the verdict rule from the manifest."""
    from lithrim_bench.cli.scoring import table
    from lithrim_bench.harness.plugins import importer_vocabulary

    res = {
        "per_task": {
            "QA": {
                "graded": 2,
                "r_tp": 1,
                "r_fp": 0,
                "r_fn": 1,
                "r_tn": 0,
                "s_tp": 1,
                "s_fp": 1,
                "s_fn": 0,
                "refused": 1,
            },
            "OVERALL": {
                "graded": 2,
                "r_tp": 1,
                "r_fp": 0,
                "r_fn": 1,
                "r_tn": 0,
                "s_tp": 1,
                "s_fp": 1,
                "s_fn": 0,
                "refused": 1,
            },
        },
        "per_code": {"SOURCE_CONTRADICTION": {"tp": 1, "fp": 0, "fn": 1}},
        "unlocated": [("c1", "gone")],
    }
    vocab = importer_vocabulary("ragtruth", pack="_core")
    t = table(res, vocab)
    rows = {r["task"]: r for r in t["per_task"]}
    assert [r["task"] for r in t["per_task"]] == ["QA", "OVERALL"]
    assert rows["QA"] == {
        "task": "QA",
        "n": 2,
        "ungraded": 0,
        "refused": 1,
        "P": 100.0,
        "R": 50.0,
        "F1": 66.7,
        "span_P": 50.0,
        "span_R": 100.0,
        "span_F1": 66.7,
        "tp": 1,
        "fp": 0,
        "fn": 1,
        "tn": 0,
    }
    code = t["per_code"][0]
    assert code["code"] == "SOURCE_CONTRADICTION"
    assert code["dataset_terms"] == ["Evident Conflict", "Subtle Conflict"]
    assert code["P"] == 100.0 and code["R"] == 50.0
    assert t["unlocated"] == [{"case_id": "c1", "quote": "gone"}]
    assert (
        t["vocabulary"]["dataset"] == "ragtruth"
        and "Tier-1" in t["vocabulary"]["verdict_rule"]["lithrim"]
    )
    bare = table(res, None)
    assert bare["per_code"][0]["dataset_terms"] == [] and bare["vocabulary"]["dataset"] is None
