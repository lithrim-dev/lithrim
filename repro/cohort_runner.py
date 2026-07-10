#!/usr/bin/env python3
"""Full cohort runs for the judge-vs-floor study: every case x 5 streams, sequential,
per-case resilient (Zenodo DOI 10.5281/zenodo.21270268; ~540 PAID grades at full scale,
see the cost note in REPRODUCING.md).

Per-case POST /v1/run-eval (live, in_process, confirmed) so every grade persists
independently; a failure logs and continues. A stream whose first 3 cases ALL fail
is marked failed and skipped (systematic breakage, e.g. provider outage).
Progress -> $LITHRIM_REPRO_OUT/progress.log ; summary -> cohort_summary.json ;
sentinel -> COHORT_DONE.

Parameterized (see REPRODUCING.md): LITHRIM_REPRO_BASE (default http://localhost:8787),
LITHRIM_REPRO_OUT (default ./out/repro), LITHRIM_REPRO_ACTOR,
LITHRIM_REPRO_HOME_WORKSPACE (optional switch-back at the end).
"""
import json
import os
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("LITHRIM_REPRO_BASE", "http://localhost:8787")
OUT_DIR = Path(os.environ.get("LITHRIM_REPRO_OUT", "./out/repro"))
ACTOR = os.environ.get("LITHRIM_REPRO_ACTOR", "repro@lithrim-bench")
HOME_WS = os.environ.get("LITHRIM_REPRO_HOME_WORKSPACE", "")
STREAMS = ["stream-a-single", "stream-b-ensemble", "stream-c-same",
           "stream-c-mixed", "baseline-scalar-reward"]


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}\n"
    print(line, end="")
    with open(OUT_DIR / "progress.log", "a") as f:
        f.write(line)


def call(m, p, b=None, t=420):
    r = urllib.request.Request(
        BASE + p, method=m,
        data=json.dumps(b).encode() if b is not None else None,
        headers={"Content-Type": "application/json", "X-Actor": ACTOR})
    with urllib.request.urlopen(r, timeout=t) as x:
        return json.loads(x.read() or b"{}")


def run_stream(ws):
    call("POST", "/v1/workspace", {"name": ws})
    cases = call("GET", "/v1/cases")
    rows = cases.get("cases", cases) if isinstance(cases, dict) else cases
    ids = [c["case_id"] for c in rows]
    log(f"=== {ws}: {len(ids)} cases ===")
    ok, failed = 0, []
    t0 = time.time()
    for i, cid in enumerate(ids, 1):
        try:
            t1 = time.time()
            call("POST", "/v1/run-eval",
                 {"agent": "ws0_default", "live": True, "in_process": True,
                  "confirm": True, "case_id": cid})
            ok += 1
            log(f"  [{ws} {i}/{len(ids)}] {cid} ok ({round(time.time()-t1,1)}s)")
        except Exception as e:  # noqa: BLE001 — log + continue; one case never kills a stream
            failed.append({"case_id": cid, "error": f"{type(e).__name__}: {e}"[:300]})
            log(f"  [{ws} {i}/{len(ids)}] {cid} FAILED: {type(e).__name__}: {str(e)[:160]}")
            if i == 3 and ok == 0:
                log(f"  {ws}: first 3 cases all failed — marking stream failed, moving on")
                return {"ws": ws, "ok": ok, "failed": failed, "aborted": True,
                        "secs": round(time.time() - t0)}
    return {"ws": ws, "ok": ok, "failed": failed, "aborted": False,
            "secs": round(time.time() - t0)}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for ws in STREAMS:
        try:
            results.append(run_stream(ws))
        except Exception:  # noqa: BLE001 — a stream-level crash logs and moves on
            log(f"{ws} STREAM CRASH:\n{traceback.format_exc()[:500]}")
            results.append({"ws": ws, "ok": 0, "failed": [], "aborted": True, "crash": True})
    if HOME_WS:
        call("POST", "/v1/workspace", {"name": HOME_WS})
    (OUT_DIR / "cohort_summary.json").write_text(json.dumps(results, indent=1))
    log("ALL STREAMS DONE " + json.dumps(
        [{"ws": r["ws"], "ok": r["ok"], "failed": len(r["failed"])} for r in results]))
    (OUT_DIR / "COHORT_DONE").write_text("done")


if __name__ == "__main__":
    main()
