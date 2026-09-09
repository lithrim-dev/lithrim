#!/usr/bin/env python
"""ARM E1, model diversity: the ragtruth_detector prompt on three models, one council (ENSEMBLE-1).

Three judge roles carry the SAME lens and role prompt; each is bound to its own deployment on
the workspace's Foundry resource: ``ragtruth_detector`` stays on gpt-4.1 with the round-1 demos
pinned, the two new roles run BARE (the pinned demos file is keyed by role, so they inherit
none). Consensus is the frozen mechanism, untouched. Nothing here edits the engine: roles are
authored through POST /v1/judges, bound through POST /v1/provider/config (the per-role
LITHRIM_LLM_*_<ROLE> binding, openai_compatible on the resource's ``/openai/v1`` route), and
rostered through POST /v1/council/roster; the grade and the scorer are the cycle's own.

Sub-commands:
  roster    author the two extra roles, bind them (one ~16-token probe each), set the roster
  grade     grade the slice under the roster (PAID, ~450 x 3 calls); refuses without --confirm-cost
  report    the per-judge table from the grade file + run trail: agreement with gold, errors,
            served models, latency, tokens and list-price cost per case per judge
  restore   roster back to the single detector

Usage:
    set -a; . ./.provider_env; set +a
    python scripts/ragtruth_ensemble.py roster
    python scripts/ragtruth_ensemble.py grade --tag e1 --confirm-cost
    python scripts/ragtruth_ensemble.py report --tag e1 --baseline v4
    python scripts/ragtruth_ensemble.py restore
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cycle = _load("ragtruth_cycle")

# USD per 1M tokens (input, output), list price as published for the deployment family; the
# report labels every cost line as list-price and names the table it used.
LIST_PRICE = {
    **{k: v for k, v in getattr(_load("ragtruth_spend"), "LIST_PRICE", {}).items()},
    "mistral-large-3": (2.00, 6.00),
    "llama-4-maverick-17b-128e-instruct-fp8": (0.25, 1.00),
}

MEMBERS = [
    {"role": cycle.ROLE, "provider": "azure", "model": "gpt-4.1", "demos": "round-1 pinned"},
    {
        "role": "ragtruth_detector_mistral",
        "provider": "openai_compatible",
        "model": "Mistral-Large-3",
        "demos": "bare",
    },
    {
        "role": "ragtruth_detector_llama",
        "provider": "openai_compatible",
        "model": "Llama-4-Maverick-17B-128E-Instruct-FP8",
        "demos": "bare",
    },
]


def v1_route(endpoint: str) -> str:
    """The resource's OpenAI-compatible route from its Azure OpenAI endpoint."""
    host = endpoint.rstrip("/").split("/openai")[0]
    return f"{host}/openai/v1"


def price_for(model: str) -> tuple[float, float] | None:
    m = (model or "").lower().split("/")[-1]
    for key in sorted(LIST_PRICE, key=len, reverse=True):
        if m.startswith(key.lower()):
            return LIST_PRICE[key]
    return None


def per_judge_table(grade: dict, blobs: dict[str, dict]) -> list[dict]:
    """One row per judge role: verdict agreement with gold (the scorecard's by_judge), errors,
    served models, mean latency, tokens and list-price cost per case, from the run trail."""
    sc = grade.get("scorecard") or {}
    by_judge = {j["judge_role"]: j for j in sc.get("by_judge") or []}
    acc: dict[str, dict] = {}
    for row in grade.get("matrix") or []:
        blob = blobs.get(row.get("run_id")) or {}
        votes = ((blob.get("stage_results") or {}).get("semantic") or {}).get("judge_votes") or []
        if not votes:
            votes = row.get("votes") or []
        for v in votes:
            role = str(v.get("judge_role") or "judge")
            j = acc.setdefault(
                role,
                {
                    "judge_role": role,
                    "model": v.get("model"),
                    "votes": 0,
                    "errors": 0,
                    "served": {},
                    "latency_sum": 0,
                    "latency_n": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "usage_n": 0,
                },
            )
            j["votes"] += 1
            j["errors"] += 1 if v.get("errors") else 0
            served = str(v.get("served_model") or "None")
            j["served"][served] = j["served"].get(served, 0) + 1
            if isinstance(v.get("latency_ms"), (int, float)):
                j["latency_sum"] += v["latency_ms"]
                j["latency_n"] += 1
            usage = v.get("usage") or {}
            if usage:
                j["input_tokens"] += int(usage.get("input_tokens") or 0)
                j["output_tokens"] += int(usage.get("output_tokens") or 0)
                j["usage_n"] += 1
    out = []
    for role, j in acc.items():
        price = price_for(j["model"] or "")
        cost = (
            (j["input_tokens"] / 1e6 * price[0] + j["output_tokens"] / 1e6 * price[1])
            if price
            else None
        )
        n = j["votes"] or 1
        bj = by_judge.get(role) or {}
        out.append(
            {
                "judge_role": role,
                "model": j["model"],
                "votes": j["votes"],
                "errors": j["errors"],
                "matches_gold": bj.get("matches_gold"),
                "misses": bj.get("misses"),
                "over_flags": bj.get("over_flags"),
                "served_models": j["served"],
                "latency_ms_mean": int(j["latency_sum"] / j["latency_n"])
                if j["latency_n"]
                else None,
                "input_tokens": j["input_tokens"],
                "output_tokens": j["output_tokens"],
                "votes_with_usage": j["usage_n"],
                "usd_list": round(cost, 2) if cost is not None else None,
                "usd_list_per_case": round(cost / n, 4) if cost is not None else None,
                "priced_with": f"{price[0]}/{price[1]} per M" if price else "no list price on file",
            }
        )
    return out


def blobs_for(grade: dict, db_path: Path) -> dict[str, dict]:
    wanted = {r.get("run_id") for r in grade.get("matrix") or [] if r.get("run_id")}
    if not wanted or not db_path.exists():
        return {}
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    out: dict[str, dict] = {}
    for (raw,) in con.execute("SELECT json FROM pipeline_runs"):
        d = json.loads(raw)
        if d.get("pipeline_run_id") in wanted:
            out[d["pipeline_run_id"]] = d
    return out


def cmd_roster(a) -> None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not endpoint or not api_key:
        sys.exit(
            "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY are not set (source the provider file)"
        )
    route = v1_route(endpoint)
    for m in MEMBERS[1:]:
        body = {
            "role": m["role"],
            "lens_codes": cycle.LENS,
            "owned_codes": [],
            "role_prompt": cycle.ROLE_PROMPT,
        }
        try:
            cycle._post(a.bff, "/v1/judges?rationale=RAGTruth%20ensemble%20E1", body, timeout=120)
            print(f"authored judge {m['role']}")
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                raise
            print(f"judge {m['role']} exists")
        res = cycle._post(
            a.bff,
            "/v1/provider/config",
            {
                "plane": "grading",
                "provider": m["provider"],
                "role": m["role"],
                "model": m["model"],
                "endpoint": route,
                "api_key": api_key,
            },
            timeout=300,
        )
        print(f"bound {m['role']} -> {m['provider']}/{m['model']} on {route}: {res}")
        cycle._put(
            a.bff,
            f"/v1/judges/{m['role']}?rationale=pin%20the%20ensemble%20member%27s%20model",
            {"model": m["model"], "assigned_flags": cycle.LENS, "validator_refs": []},
        )
    roster = [m["role"] for m in MEMBERS]
    cycle._post(a.bff, "/v1/council/roster", {"agent": a.agent, "roster": roster}, timeout=120)
    print(f"roster = {roster}")
    (a.out / "ensemble_manifest.json").write_text(
        json.dumps({"members": MEMBERS, "route": route, "roster": roster}, indent=2)
    )


def cmd_grade(a) -> None:
    if not a.confirm_cost:
        sys.exit(
            f"REFUSING a paid grade of {sum(1 for _ in a.slice.open())} cases x {len(MEMBERS)} judges; "
            "re-run with --confirm-cost"
        )
    cycle._grade_and_score(a, a.tag)


def cmd_report(a) -> None:
    grade = json.load((a.out / f"grade_{a.tag}.json").open())
    table = per_judge_table(grade, blobs_for(grade, a.collections_db))
    sc = grade.get("scorecard") or {}
    lines = {
        "tag": a.tag,
        "majority": sc.get("majority"),
        "per_judge": table,
        "usd_list_total": round(sum(r["usd_list"] or 0 for r in table), 2),
    }
    if a.baseline:
        base = json.load((a.out / f"grade_{a.baseline}.json").open())
        lines["baseline"] = {
            "tag": a.baseline,
            "majority": (base.get("scorecard") or {}).get("majority"),
        }
    slice_rows = [json.loads(line) for line in a.slice.open()]
    lines["cohort"] = cycle.cohort_summary(grade, slice_rows)
    print(json.dumps(lines, indent=2))
    (a.out / f"ensemble_report_{a.tag}.json").write_text(json.dumps(lines, indent=2))


def cmd_restore(a) -> None:
    cycle._post(
        a.bff, "/v1/council/roster", {"agent": a.agent, "roster": [cycle.ROLE]}, timeout=120
    )
    print(f"roster = [{cycle.ROLE}]")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("cmd", choices=["roster", "grade", "report", "restore"])
    ap.add_argument("--bff", default="http://localhost:8787")
    ap.add_argument("--agent", default="ws0_default")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "ragtruth")
    ap.add_argument(
        "--slice", type=Path, default=REPO_ROOT / "out" / "ragtruth" / "slice_full.jsonl"
    )
    ap.add_argument("--tag", default="e1")
    ap.add_argument("--baseline", default=None)
    ap.add_argument(
        "--collections-db",
        type=Path,
        default=REPO_ROOT / "out/workspaces/default/collections.sqlite",
    )
    ap.add_argument("--confirm-cost", action="store_true")
    a = ap.parse_args()
    a.workspace_out = REPO_ROOT / "out/workspaces/default/out"
    {"roster": cmd_roster, "grade": cmd_grade, "report": cmd_report, "restore": cmd_restore}[a.cmd](
        a
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
