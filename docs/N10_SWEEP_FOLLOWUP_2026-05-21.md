# N=10 sweep follow-up — Phase 2 item 4

**Status at session close:** sweep running detached, PID written to `out/logs/n10_sweep.pid`, log streaming to `out/logs/n10_sweep.log`. The sweep is gitignored output; only this doc and `scripts/_run_n10_sweep.sh` are committed.

## What's running

```
4 packs × 50 cases × N=10 runs = 2000 live council invocations
backend: lithrim-pipeline (live gpt-4.1) via POST /v1/pipeline/evaluate
artifact-profile binds:
  scribe_v1      -> live council only (no structural)
  scheduling_v1  -> + lithrim/scheduling-action/v1
  coding_v1      -> + CARIN Claim Validator (etlp mapping 15)   ← v3 synth (clean recall 4/4 at N=1)
  triage_v1      -> + FHIR R4 RiskAssessment Validator (etlp mapping 19)   ← v3 synth (clean recall 4/4 at N=1)
launched: 2026-05-21T05:58:14Z
first call wall clock: ~15s (faster than kickoff's 25s estimate)
revised total wall clock: ~8 hours (kickoff said ~14h)
expected completion: ~2026-05-21T13:58Z
```

## How to check progress mid-run

```bash
cd ~/Workspace/github.com/lithrim-bench

# Is the process still alive?
ps -p $(cat out/logs/n10_sweep.pid) -o pid,etime,command

# How many calls completed across all 4 packs?
wc -l out/{scribe,scheduling,coding,triage}_v1.n10.ndjson 2>/dev/null

# What pack is it on right now?
tail -5 out/logs/n10_sweep.log

# How fast are calls landing on the current pack?
ls -la out/*.n10.ndjson | awk '$5 > 0 {print}'
```

## Kill switch (if needed)

```bash
kill $(cat out/logs/n10_sweep.pid)
# or, if needed, hard-kill:
kill -9 $(cat out/logs/n10_sweep.pid)
```

Then either re-launch (`nohup bash scripts/_run_n10_sweep.sh > out/logs/n10_sweep.log 2>&1 < /dev/null &`) or treat the partial NDJSONs as the result — `analyze_runs.py` handles partial rows fine.

## When the sweep completes

The log will end with `[<ts>] N=10 sweep complete`. At that point run:

```bash
# 1. Per-pack analysis (CIs, instability, false-block, structural)
for p in scribe_v1 scheduling_v1 coding_v1 triage_v1; do
    python scripts/analyze_runs.py --runs "out/$p.n10.ndjson" --pack "out/$p.n10.jsonl"
done

# 2. Per-judge calibration at N=10
python scripts/calibrate_judges.py \
    --runs out/scribe_v1.n10.ndjson out/scheduling_v1.n10.ndjson \
           out/coding_v1.n10.ndjson out/triage_v1.n10.ndjson \
    --packs out/scribe_v1.n10.jsonl out/scheduling_v1.n10.jsonl \
            out/coding_v1.n10.jsonl out/triage_v1.n10.jsonl \
    --out out/judge_calibration_n10.json \
    --md-out docs/JUDGE_CALIBRATION_N10_2026-05-22.md
```

## Acceptance gate (Item 4 per KICKOFF_PHASE2)

- [ ] 4 NDJSON files with 500 rows each (`wc -l` confirms)
- [ ] `verdict_match_rate_ci95` width ≤ 0.1 per pack (CI-tight enough for paper §7)
- [ ] `instability_rate` reported per pack (eval-spec §2.4 reportability gate)

If a pack's CI width > 0.1 at N=10, that itself is a reportable finding (the pack is too noisy to use as a §7 row anchor without N=25+).

## What to draft next, while the sweep runs

Kickoff item 5 (paper drafting) does NOT depend on item 4 — §3 (related work), §4 (method), §5 (benchmark provenance), §6 (experiment design protocol minus the actual N=10 cells), §7b (threats to validity), and the abstract minus the results sentence are all drafting-ready today against the v3 anchors in [JUDGE_CALIBRATION_2026-05-21.md](JUDGE_CALIBRATION_2026-05-21.md). Only §7 results table needs the n10 data.

So a productive use of the 8-hour gap: open `docs/PAPER_OUTLINE.md`, start `docs/paper_draft/04_method.md` and `docs/paper_draft/05_benchmark.md`. Both anchor against committed code and stable measurements.

## If something breaks

- **Backend rate limit / 429s:** the LithrimPipelineBackend doesn't retry. The NDJSON will be short by however many calls 429'd. Re-running with `--case-filter` (after a small patch to run_determinism — not in tree yet) can fill the gaps without re-running everything.
- **Process killed by OS reboot / sleep:** the NDJSON is written line-by-line as each call completes (eval_runner.py:111 — no buffering issues). Partial results are recoverable. Re-launch the script and it will start over from scribe_v1 (the script doesn't currently resume); consider adding `--skip-existing` if a reboot happens early.
- **etlp-mapper down:** `LithrimPipelineBackend` doesn't detect this directly. The compliance_verdict will collapse to the semantic side only, and `structural_verdict` will read PASS by default. The Aug 2025 backend has a circuit breaker (5 fails → 30s cooldown) so it self-recovers. Check `out/logs/n10_sweep.log` for unexpected approve runs on known-defective cases as the canary.
