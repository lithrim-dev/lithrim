#!/usr/bin/env python3
"""$0 consolidation after the cohort run: per-stream scorecards (replay-from-provenance),
reliability metrics, stream-a K-sweep, and the floor-flip ledger (verdict vs grounded_verdict
per case). Pure reads + $0 replays — no paid calls. (Zenodo DOI 10.5281/zenodo.21270268)

Parameterized (see REPRODUCING.md): LITHRIM_REPRO_BASE (default http://localhost:8787),
LITHRIM_REPRO_OUT (default ./out/repro), LITHRIM_REPRO_ACTOR,
LITHRIM_REPRO_HOME_WORKSPACE (optional switch-back at the end),
LITHRIM_REPRO_WS_SUFFIX (workspace-name suffix; matches setup_streams.py /
cohort_runner.py so the preregistered v2 rerun consolidates the fresh workspaces).
"""
import json
import os
import urllib.request
from pathlib import Path

BASE = os.environ.get("LITHRIM_REPRO_BASE", "http://localhost:8787")
OUT_DIR = Path(os.environ.get("LITHRIM_REPRO_OUT", "./out/repro"))
ACTOR = os.environ.get("LITHRIM_REPRO_ACTOR", "repro@lithrim-bench")
HOME_WS = os.environ.get("LITHRIM_REPRO_HOME_WORKSPACE", "")
WS_SUFFIX = os.environ.get("LITHRIM_REPRO_WS_SUFFIX", "")
STREAMS = [ws + WS_SUFFIX for ws in
           ("stream-a-single", "stream-b-ensemble", "stream-c-same",
            "stream-c-mixed", "baseline-scalar-reward")]


def call(m, p, b=None, t=900):
    r = urllib.request.Request(
        BASE + p, method=m,
        data=json.dumps(b).encode() if b is not None else None,
        headers={"Content-Type": "application/json", "X-Actor": ACTOR})
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read() or b"{}")


def latest_runs_by_case(limit=400):
    runs = call("GET", f"/v1/runs?limit={limit}&agent=ws0_default")
    rows = runs.get("runs", runs) if isinstance(runs, dict) else runs
    latest = {}
    for r in rows:  # newest-first: keep the first (latest) LIVE row per case
        cid = r.get("case_id")
        if cid and cid not in latest and r.get("grade_path") != "replay":
            latest[cid] = r
    return latest


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for ws in STREAMS:
        call("POST", "/v1/workspace", {"name": ws})
        entry = {"ws": ws}
        # 1) consolidated scorecard from the persisted runs ($0 replay-from-provenance)
        try:
            g = call("POST", "/v1/cases/grade", {"agent": "ws0_default", "live": False})
            entry["summary"] = g.get("summary")
            entry["scorecard"] = g.get("scorecard")
        except Exception as e:  # noqa: BLE001
            entry["scorecard_error"] = f"{type(e).__name__}: {str(e)[:300]}"
        # 2) floor-flip ledger from the live runs
        latest = latest_runs_by_case()
        flips, upcode_ok, cg_council_block, cg_floor_pass = [], 0, 0, 0
        for cid, r in latest.items():
            v, gv = r.get("verdict"), r.get("grounded_verdict")
            if "_clean_generalization_" in cid:
                if v == "BLOCK":
                    cg_council_block += 1
                if gv == "PASS":
                    cg_floor_pass += 1
                if v == "BLOCK" and gv == "PASS":
                    flips.append(cid)
            elif "_upcode_" in cid and gv == "BLOCK":
                upcode_ok += 1
        entry["floor"] = {
            "n_live_cases": len(latest),
            "clean_gen_council_blocks": cg_council_block,
            "clean_gen_floor_pass": cg_floor_pass,
            "council_block_floor_cleared_flips": len(flips),
            "flip_cases": flips[:25],
            "upcode_grounded_block": upcode_ok,
        }
        # 3) reliability metrics
        try:
            entry["reliability"] = call("GET", "/v1/reliability/ws0_default").get("metrics")
        except Exception as e:  # noqa: BLE001
            entry["reliability_error"] = f"{type(e).__name__}"
        # 4) K-sweep (stream-a only)
        if ws == "stream-a-single":
            try:
                entry["sweep"] = call(
                    "GET", "/v1/reliability/ws0_default/sweep?role=single_generalist&k_max=8")
            except Exception as e:  # noqa: BLE001
                entry["sweep_error"] = f"{type(e).__name__}"
        out[ws] = entry
        print(f"{ws}: consolidated (live cases: {entry['floor']['n_live_cases']})")

    if HOME_WS:
        call("POST", "/v1/workspace", {"name": HOME_WS})
    (OUT_DIR / "consolidated.json").write_text(json.dumps(out, indent=1))
    print(f"WROTE {OUT_DIR / 'consolidated.json'}")


if __name__ == "__main__":
    main()
