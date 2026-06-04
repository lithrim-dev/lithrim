# Driver STUB — `bench-salvage` phase `UAP-4-opt`: the optimize bind→re-run round-trip

> **STATUS: STUB.** Authored at UAP-4 close (2026-06-05). The SPLIT-OUT bind/re-run
> round-trip backend (driver §4 / R2 right-size). **GATED ON A POSITIVE held-out Δ** —
> do not expand until an optimize run produces a real lift (today the Δ is a loss,
> S-BS-49). Expand via `/devloop-expand-driver bench-salvage UAP-4-opt`.

> **Bundle ID:** `bench-salvage-phaseUAP-4-opt-bind-rerun-roundtrip-driver`

---

## Why this is split out (the UAP-4 right-size)

UAP-4 shipped the demonstrable-live **optimize→honest-Δ loop** (the SME edits a lens,
optimizes, sees the held-out Δ win-or-loss in `JudgeEditor`). It did **NOT** build the
bind→re-run round-trip, because:

1. **It can't be demonstrated live until optimize WINS.** The WS-6c-DSPy-3b / UAP-4
   held-out Δ is **negative** (S-BS-49): binding a loss-making demo set into the
   production judge and re-running would show a verdict get *worse* — not a demo. The
   "watch the verdict improve after binding" leg is dark until a positive Δ exists.
2. **The re-run surface already exists.** The `Run evaluation` card (`RunPanel`) +
   `Run history` + the in_process paid grade already render the per-judge verdict, so
   binding is cheap to add LATER (no new run surface needed).
3. Building the bind-persistence backend now = machinery for a dark path.

## Scope when expanded (the deferred backend — DO NOT build until a positive Δ)

- `JudgeConfig.compiled_demos` (`harness/judges.py`) — persist the compiled few-shot
  demos on the judge config (today `bind_compiled_demos` is mechanism-only, test-only).
- A **positive-Δ-gated bind endpoint** — `POST /v1/judges/{role}/bind` (or fold into
  `/optimize` with an `apply=true` only when `delta.graded > 0`). NEVER bind a
  loss-making demo set (the S-BS-48 guard).
- The `authored_stage.py` demo-load — `build_trio` / the authored evaluator loads the
  bound `compiled_demos` onto each `Judge.predict.demos` (the `bind_compiled_demos`
  move, today deferred). **Touches the FROZEN `authored_stage` + `judges_dspy` set —
  re-open the freeze deliberately, gated + tested.**
- bind → re-run → the `Run evaluation` card renders the verdict-CHANGE (the visceral
  "my optimized judge now votes differently" finale).

## Preconditions / gates

- **A positive held-out Δ from `/optimize`** (the coverage-aware + corpus-widening
  attempt must actually lift — or a follow-on lever: MIPROv2 / a higher-recall teacher
  / more positives). Until then this stays a stub. (S-BS-48 + S-BS-49.)
- HARD-GATE-class (it changes production judge behavior + re-opens the frozen
  `authored_stage`/`judges_dspy` freeze): fresh-critic required when expanded.
- Seams: **S-BS-48** (bind-back-by-default), **S-BS-49** (the lift must exist first),
  **S-BS-70** (the visceral live finale this completes).

## References
- UAP-4 driver `.devloop/prompts/bench-salvage_phaseUAP-4_optimize-calibration-loop_driver.md` (§4 the split)
- `lithrim_bench/runtime/council/judge_optimize.py` `bind_compiled_demos` (the mechanism)
- The UAP-4 session log `.devloop/sessions/session-bench-salvage-phaseUAP-4-2026-06-05.json` (the measured Δ + the disposition)
