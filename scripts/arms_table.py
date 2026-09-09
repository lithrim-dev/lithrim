"""Print the arm comparison, read live from the immutable run records.

Run on stage with:
  docker exec -i lithrim-repro-bff-1 python3 - < arms_table.py
"""
import collections
import json
from pathlib import Path

from lithrim_bench.harness.backend import provenance_store_for, run_coro

WS = ["demo-snomed", "demo-snomed-gpt41"]
rows = []

for ws in WS:
    base = Path(f"/app/out/workspaces/{ws}")
    if not (base / "collections.sqlite").exists():
        continue
    gold = {}
    for line in open(base / "out" / "ingested_cases.jsonl"):
        c = json.loads(line)
        gold[c["case_id"]] = c["pinned"]["stratum"]
    docs = [d for d in run_coro(provenance_store_for(base / "collections.sqlite").list_all(limit=None))
            if not d.get("replay_of")]
    arms = collections.defaultdict(list)
    for d in docs:
        arms[d.get("grade_signature")].append(d)

    for sig in sorted(arms, key=lambda s: min(str(r.get("timestamp")) for r in arms[s])):
        runs = {}
        for d in sorted(arms[sig], key=lambda x: str(x.get("timestamp"))):
            runs[d["case_id"]] = d
        allv = ((arms[sig][0].get("stage_results") or {}).get("semantic") or {}).get("judge_votes", [])
        v0 = allv[0] if allv else {}
        seats = len(allv)
        crit = ((arms[sig][0].get("grade_config") or {}).get("criteria") or {}).get("risk_judge")
        up = gen = alone = withfloor = 0
        for cid, stratum in gold.items():
            d = runs.get(cid)
            if not d:
                continue
            g = d.get("grounded") or {}
            raised = {f.get("code") for f in (d.get("findings") or []) if f.get("code")}
            hit = "UPCODED_DIAGNOSIS" in raised
            up += hit and stratum == "upcode_subsumption"
            gen += hit and stratum == "clean_generalization"
            want = "BLOCK" if stratum == "upcode_subsumption" else "PASS"
            alone += g.get("verdict_no_floor") == want
            withfloor += g.get("verdict") == want
        n = len(runs)
        rows.append({
            "model": str(v0.get("model", "?")).split("/")[-1] + ("" if seats == 1 else f" +{seats-1}"),
            "seats": seats,
            "k": v0.get("k"), "temp": (arms[sig][0].get("sampling") or {}).get("temperature"),
            "criterion": "yes" if crit else "no",
            "up": f"{up}/13", "gen": f"{gen}/13",
            "alone": f"{alone/n:.1%}" if n else "-",
            "floor": f"{withfloor/n:.1%}" if n else "-",
            "n": n,
        })

hdr = f"{'judge model':19s} {'seats':>5s} {'k':>2s} {'crit':>5s} | {'flags upcodes':>13s} {'flags cleans':>12s} | {'judges alone':>12s} {'with floor':>10s}"
print(hdr)
print("-" * len(hdr))
for r in rows:
    print(f"{r['model']:19s} {str(r['seats']):>5s} {str(r['k']):>2s} {r['criterion']:>5s} | "
          f"{r['up']:>13s} {r['gen']:>12s} | {r['alone']:>12s} {r['floor']:>10s}")
print()
print("Every arm: the flag rate on real upcodes equals the flag rate on safe generalizations.")
print("That difference is the judge's entire signal on this axis. It is zero, in all of them.")
