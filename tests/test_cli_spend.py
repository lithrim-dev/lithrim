"""The spend line: run blobs projected and priced at list price (UI-JOURNEY-1 B9 shares the
projection between the CLI's SQLite read and the service route)."""

from __future__ import annotations

from lithrim_bench.cli import spend as sp


def _doc(agent, run, tokens, served="gpt-4.1-2025-04-14", cost=True):
    return {
        "agent_id": agent,
        "pipeline_run_id": run,
        "timestamp": "2026-09-10T00:00:00+00:00",
        "cost_tokens": {"prompt": tokens, "completion": 100, "total": tokens + 100}
        if cost
        else None,
        "stage_results": {
            "semantic": {"judge_votes": [{"served_model": served, "model": "azure/gpt-4.1"}]}
        },
    }


def test_rows_from_docs_filters_by_agent_and_projects_the_priced_fields():
    docs = [_doc("a", "r1", 1000), _doc("b", "r2", 1000), _doc("a", "r3", 0, cost=False)]
    rows = sp.rows_from_docs(docs, "a")
    assert [r["served_model"] for r in rows] == ["gpt-4.1-2025-04-14", "gpt-4.1-2025-04-14"]
    assert rows[0]["cost_tokens"]["total"] == 1100 and rows[1]["cost_tokens"] is None
    assert len(sp.rows_from_docs(docs)) == 3


def test_spend_prices_at_list_and_counts_what_it_cannot_price():
    rows = sp.rows_from_docs(
        [
            _doc("a", "r1", 1_000_000),
            _doc("a", "r2", 1000, served="mystery-9"),
            _doc("a", "r3", 0, cost=False),
        ],
        "a",
    )
    out = sp.spend(rows)
    assert out["usd_list_price"] == round(1_000_000 / 1e6 * 2.00 + 100 / 1e6 * 8.00, 2)
    assert (
        out["runs_priced"] == 1
        and out["runs_unpriced_model"] == 1
        and out["runs_without_cost_record"] == 1
    )
    assert out["prompt_tokens"] == 1_001_000 and out["completion_tokens"] == 200
