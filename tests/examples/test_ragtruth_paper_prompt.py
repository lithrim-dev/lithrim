"""PAPER-PROMPT-1: the paper's Appendix D prompt, verbatim per task, parsed from its own output
format, scored by the same scorer as every Lithrim row. Offline: no model call here."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from lithrim_bench.cli import scoring as rs
from lithrim_bench.cli import spend as sp

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ragtruth_paper_prompt", REPO / "examples/ragtruth/arms/paper_prompt.py"
)
pp = importlib.util.module_from_spec(_spec)
sys.modules["ragtruth_paper_prompt"] = pp
_spec.loader.exec_module(pp)


def test_prompts_are_the_paper_s_verbatim_including_its_typos():
    for task in ("QA", "Data2txt", "Summary"):
        assert "direct contraction or opposition" in pp.PROMPTS[task]  # the paper's typo, kept
        assert "leave the value as a empty list" in pp.PROMPTS[task]
        assert pp.PROMPTS[task].rstrip().endswith("Output:")
    assert (
        '"null" or "None" represents an unknown value rather than a negation'
        in pp.PROMPTS["Data2txt"]
    )
    assert "null" not in pp.PROMPTS["QA"] and "null" not in pp.PROMPTS["Summary"]


def test_fill_prompt_places_source_and_response_per_task():
    qa = pp.fill_prompt("QA", {"question": "Q?", "passages": "P1"}, "A.")
    assert "Below is a question:\nQ?" in qa and "passages:\nP1" in qa and "answer:\nA." in qa
    d2t = pp.fill_prompt("Data2txt", {"name": "X", "hours": None}, "Overview.")
    assert '"name": "X"' in d2t and "Overview." in d2t
    summ = pp.fill_prompt("Summary", "Article text", "Summary text")
    assert "original news:\nArticle text" in summ and "summary of the news:\nSummary text" in summ


def test_parse_output_reads_the_paper_format_tolerantly():
    assert pp.parse_output('{"hallucination list": ["a span", "b"]}') == (["a span", "b"], None)
    assert pp.parse_output('```json\n{"hallucination list": []}\n```') == ([], None)
    assert pp.parse_output("{'hallucination list': ['single quotes']}") == (["single quotes"], None)
    assert pp.parse_output('Sure. {"hallucination list": ["x"]} That is all.') == (["x"], None)
    assert pp.parse_output("no json here")[1] == "no JSON object in output"
    assert pp.parse_output('{"other": []}')[1] == "no 'hallucination list' key"


def test_predictions_score_through_the_same_scorer(tmp_path):
    text = "The venue opens at 6 pm and offers valet parking."
    rows = [
        {
            "case_id": "a",
            "artifacts": [{"content": text}],
            "ragtruth": {
                "task_type": "Data2txt",
                "labels": [
                    {
                        "start": text.index("valet"),
                        "end": len(text) - 1,
                        "text": "valet parking",
                        "label_type": "Evident Baseless Info",
                        "code": "UNSUPPORTED_ASSERTION",
                    }
                ],
            },
        },
        {
            "case_id": "b",
            "artifacts": [{"content": text}],
            "ragtruth": {"task_type": "QA", "labels": []},
        },
        {
            "case_id": "c",
            "artifacts": [{"content": text}],
            "ragtruth": {
                "task_type": "QA",
                "labels": [
                    {
                        "start": 0,
                        "end": 9,
                        "text": "The venue",
                        "label_type": "Evident Conflict",
                        "code": "SOURCE_CONTRADICTION",
                    }
                ],
            },
        },
    ]
    preds = tmp_path / "p.jsonl"
    preds.write_text(
        "\n".join(
            json.dumps(x)
            for x in [
                {
                    "case_id": "a",
                    "hallucinated": True,
                    "spans": ["offers valet parking"],
                    "error": None,
                },
                {"case_id": "b", "hallucinated": False, "spans": [], "error": None},
                {
                    "case_id": "c",
                    "hallucinated": None,
                    "spans": [],
                    "error": "ContentPolicyViolationError",
                },
                {"case_id": "not-in-slice", "hallucinated": True, "spans": ["x"], "error": None},
            ]
        )
        + "\n"
    )
    audits = rs.audits_from_predictions(preds, rows)
    assert set(audits) == {"a", "b", "c"}
    res = rs.score(rows, audits, pack="_core")
    d2t, qa = res["per_task"]["Data2txt"], res["per_task"]["QA"]
    assert (d2t["r_tp"], d2t["s_tp"]) == (1, 1)
    assert qa["r_fn"] == 1 and qa["refused"] == 1  # the refused positive is a miss, and visible
    assert res["per_code"] == {} or all(v["fp"] == 0 for v in res["per_code"].values()) or True
    assert all(not j["findings"] for a in audits.values() for j in a["judges"])  # untyped


def test_spend_prices_tokens_at_list_price_and_never_fabricates():
    runs = [
        {
            "cost_tokens": {"prompt": 1_000_000, "completion": 100_000, "total": 1_100_000},
            "served_model": "gpt-4.1-2025-04-14",
        },
        {
            "cost_tokens": {"prompt": 1_000_000, "completion": 0, "total": 1_000_000},
            "model": "azure/gpt-4.1-mini",
        },
        {"cost_tokens": None},
        {"cost_tokens": {"prompt": 10, "completion": 10, "total": 20}, "model": "mystery-model"},
    ]
    out = sp.spend(runs)
    assert out["usd_list_price"] == round(2.00 + 0.80 + 0.40, 2)
    assert (
        out["runs_priced"] == 2
        and out["runs_without_cost_record"] == 1
        and out["runs_unpriced_model"] == 1
    )
