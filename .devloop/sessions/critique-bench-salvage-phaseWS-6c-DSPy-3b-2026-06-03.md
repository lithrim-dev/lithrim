# Critique — `bench-salvage` WS-6c-DSPy-3b (judge-optimizer)

**Date:** 2026-06-03
**Mode:** HARD GATE → **spawned fresh-critic** (independent agent `a576212aa4bdcd0d1`, no implementation context; cold read of spec + diff + artifacts). 18 tool calls, ~78k tokens.
**Driver:** `bench-salvage-phaseWS-6c-DSPy-3b-judge-optimizer-driver`
**Base→HEAD:** `c675da0` → `820cf88` (6 cycle commits `781abc4..820cf88`)

## Verdict: CLEAN (1 OPEN-QUESTION, non-blocking)

Monitor 7-item audit CLEAN + fresh-critic CLEAN. The honest-negative loop-closure is **sound** and the frozen consensus seam is **intact**. This is a clean close.

## HARD-GATE focus (the load-bearing items, verified from primary evidence)

- **A1 frozen-seam — PASS (critic re-ran the diff).** `git diff c675da0 HEAD -- compliance_council.py judges_dspy.py judge_metric.py | wc -l` = **0**; per-file 0/0/0. `Judge.forward` (:284), `evaluate_dspy` (:360), `build_trio` (:313), `JudgeSignature` (:192) byte-unchanged. DSPy lives strictly above the seam: `JudgeProgram` is a NEW lazy class in `judge_optimize.py`, not a mutation of `judges_dspy.py`. CONFIRMED.
- **B result-honesty (REPORT ⇄ artifacts) — PASS.** Every §2-table number reproduced from `score_baseline`/`score_optimized`/`result_dspy3b_risk_judge.json`: baseline graded 0.80 / prec 0.7143 / recall 0.7143 / 5·2·2 / accepted False → optimized 0.70 / 0.4444 / 0.5714 / 4·5·3 / False; Δ −0.10 / −0.2699 / −0.14. CONFIRMED from primary JSON.
- **C regression diagnosis — PASS (not falsified).** `compiled_demos_dspy3b_risk_judge.json` = exactly 4 demos, decisions `approve/approve/needs_review/approve`, **all `findings=[]`** — matches REPORT §3 verbatim. The §3 regression rows (VALUE_MISMATCH over-fires on 3 held-out positives; one WRONG_DOSAGE TP lost) appear in `score_optimized`'s per-case rows. CONFIRMED. S-BS-49 stands.
- **D no tuning-to-win — PASS.** Frozen `make_judge_metric` trace path = `bool(one["exact"])` (judge_metric.py:271, 0-delta). `compile_judge`: `max_bootstrapped_demos=4`, `max_labeled_demos=0`, `co_raise_aware=True`. ONE full run, $0.067+$0.197=$0.26, 24 calls — no best-of/cherry/re-run language. A negative Δ honestly reported is the expected pass; a suspiciously-clean positive would be the red flag. CONFIRMED.
- **E 4 caveats — PASS.** REPORT §5: small-N (n=10); precision is the co-raise-aware figure not the lower bound; transcript-only blind spot; NOT a paper claim. CONFIRMED.

## The 4 spec-adherence questions

- **Q1 Surface fidelity — 0 BLOCKING / 0 NB / 1 OQ.** All §2 public symbols present + named (`build_examples`, `load_corpus`, `compile_judge`, `evaluate_program`, `bind_compiled_demos`, `run_optimize`); CLI flags `--role/--corpus/--confirm-cost/--smoke/--out` exact. **OQ-1:** the driver §2 names the deliverable `JudgeProgram`, but the module exposes a `build_judge_program()` factory with the `JudgeProgram` class defined *lazily inside* it (no importable top-level `JudgeProgram`). Deliberate A3 lazy-import accommodation (an eager top-level class would pull `dspy`); internally consistent, breaks no spec behavior — a surface-name expectation gap only.
- **Q2 Behavioral fidelity — 0 BLOCKING.** 3 claims traced spec→test→impl, all hold: (a) `JudgeProgram` runs production `_validate_findings` (judge_optimize.py:162, same import `Judge.forward` uses at :297); (b) `run_optimize` refuses without `confirm_cost` (:306 RuntimeError, `test_run_optimize_refuses` passes); (c) lens-filter → train=12/held-out=10 (`test_load_corpus_and_lens_filter_match_3a_split` asserts 47/17/30 then 12/10). Offline suite 6 passed / 1 skipped on default python3.
- **Q3 Out-of-scope intrusion — 0 BLOCKING.** `git diff c675da0 HEAD --name-only` = exactly the 9 §2 files. None of the 3 staged paper files; none of the concurrent dirty files (`grounding.py`, `verification/*`, `settings.py`, `SPEC_CALIBRATION_TRAINER`, journey `apps/`). No drive-by edits.
- **Q4 Spec-ambiguity / smoke-found fix — 0 BLOCKING.** The `dspy.context(lm=lm)` vs `set_lm` fix (commit `7c9ccc3`) touches ONLY `judge_optimize.py` + its test — **zero** frozen files. Sound: a BootstrapFewShot-compiled program is a deepcopy whose per-predictor LM binding is dropped, so resolving via ambient context is correct (documented at judge_optimize.py:203-205, 329-332).

## Findings

| # | Severity | Finding | Evidence | Falsifies a claim? |
|---|---|---|---|---|
| OQ-1 | OPEN-QUESTION | `JudgeProgram` is not an importable top-level symbol; constructed via `build_judge_program()` (judge_optimize.py:121-169) | module public syms list = `build_judge_program`, not `JudgeProgram` | No — class exists, wraps the same `JudgeSignature`, demos transfer; A3-driven surface-name gap |

## Monitor disposition

- **OQ-1:** accepted as-is. The A3 import-isolation requirement (verified: `compliance_council.py:17 import openai` at module top) makes a lazy factory the correct shape — an eager top-level `JudgeProgram` class would break A3. No action; recorded for the spec author. (Spec authors: a future driver can name the *factory* as the deliverable when A3 forces lazy construction.)
- **Process note (carried, not a finding):** my plan-review adjustments — `max_labeled_demos=0` (corpus carries the metric label, not gold `JudgeSignature` outputs → labeled demos degenerate in dspy 3.2.1) and validate-findings-inside-`JudgeProgram.forward` — both landed verbatim (`plan_review.deviations` #1/#2). The first directly shaped the result (only bootstrapped demos populated); the second made the Δ production-faithful.
- **The smoke earned its keep** (the cost-confirm gate, again): caught the deepcopy-drops-`set_lm` bug before the full spend → committed as an honest broken-then-fixed 4th commit rather than a rebase (the index carried foreign staged paper files — the `git-commit-pathspec-dirty-index` landmine). Correct call.

## Bottom line

The loop is **closed + measured** for `risk_judge`; the −0.27 precision regression is real, correctly diagnosed (4 silent demos; the exact-accept gate harvests only already-perfect/silent cases on a small mixed corpus → S-BS-49), and honestly reported with no tuning-to-win. Frozen seam intact (0-delta ×3). Scope held to exactly 9 files. **CLEAN.** Triage S-BS-49 (positive-exemplar bootstrapping) before any S-BS-48 bind-back-by-default.
