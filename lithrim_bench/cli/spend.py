"""The running spend line: sum ``cost_tokens`` over an agent's runs in the trail and price
them at LIST price for the served model (USD per 1M tokens). A run with no cost record
contributes nothing (never fabricated)."""

from __future__ import annotations

import json
import urllib.request

# USD per 1M tokens (input, output), list price; extend as models appear in the trail.
LIST_PRICE = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def price_for(model: str | None) -> tuple[float, float] | None:
    m = (model or "").split("/")[-1].lower()
    for key in sorted(LIST_PRICE, key=len, reverse=True):
        if m.startswith(key):
            return LIST_PRICE[key]
    return None


def spend(runs: list[dict]) -> dict:
    """Total USD + tokens + counted/uncounted runs from run-summary rows carrying cost_tokens."""
    usd = 0.0
    prompt = completion = 0
    counted = unpriced = nocost = 0
    for r in runs:
        cost = r.get("cost_tokens") or {}
        if not isinstance(cost, dict) or cost.get("total") is None:
            nocost += 1
            continue
        pin, pout = int(cost.get("prompt") or 0), int(cost.get("completion") or 0)
        prompt += pin
        completion += pout
        price = price_for(r.get("served_model") or r.get("model") or "gpt-4.1")
        if price is None:
            unpriced += 1
            continue
        usd += pin / 1e6 * price[0] + pout / 1e6 * price[1]
        counted += 1
    return {
        "usd_list_price": round(usd, 2),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "runs_priced": counted,
        "runs_unpriced_model": unpriced,
        "runs_without_cost_record": nocost,
    }


def rows_from_docs(docs, agent: str | None = None) -> list[dict]:
    """Project run blobs (``agent_id``, ``cost_tokens``, the first judge vote's served model,
    the timestamp) into the rows ``spend`` prices; ``agent`` filters when given."""
    out: list[dict] = []
    for d in docs:
        if agent and d.get("agent_id") != agent:
            continue
        votes = ((d.get("stage_results") or {}).get("semantic") or {}).get("judge_votes") or []
        v0 = votes[0] if votes else {}
        out.append(
            {
                "cost_tokens": d.get("cost_tokens"),
                "served_model": v0.get("served_model"),
                "model": v0.get("model"),
                "ts": d.get("timestamp"),
            }
        )
    return out


def runs_from_db(db_path: str, agent: str) -> list[dict]:
    """Every run blob for ``agent`` straight from the workspace's collections SQLite (the
    runs endpoint caps at 500 rows). Projects the fields ``spend`` reads."""
    import sqlite3

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return rows_from_docs(
        (json.loads(raw) for (raw,) in con.execute("SELECT json FROM pipeline_runs")), agent
    )


def add_arguments(ap) -> None:
    ap.add_argument("--bff", default="http://localhost:8787")
    ap.add_argument("--agent", default="ws0_default")
    ap.add_argument("--since", default=None, help="ISO timestamp; count runs at or after it")
    ap.add_argument("--limit", type=int, default=500, help="runs endpoint cap (500)")
    ap.add_argument(
        "--db",
        default=None,
        help="read the workspace collections SQLite directly (no 500-row cap), e.g. "
        "out/workspaces/default/collections.sqlite",
    )


def cmd_spend(a) -> int:
    if a.db:
        runs = runs_from_db(a.db, a.agent)
    else:
        with urllib.request.urlopen(
            f"{a.bff}/v1/runs?agent={a.agent}&limit={a.limit}", timeout=600
        ) as r:
            runs = json.load(r)["runs"]
    if a.since:
        runs = [x for x in runs if (x.get("ts") or "") >= a.since]
    out = spend(runs)
    out["runs"] = len(runs)
    print(json.dumps(out))
    return 0
