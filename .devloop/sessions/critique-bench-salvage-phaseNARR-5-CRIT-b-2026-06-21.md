# CRITIQUE — bench-salvage phase NARR-5-CRIT-b (fresh cold critic, A-SAFE HARD-GATE)

> Persisted verbatim-in-substance by the monitor from the cold-critic subagent's return.
> Range: `c1e3771..d4030d6` (3 commits: `294f873` tests RED → `64807c1` backend GREEN → `d4030d6` FE).

verdict: **CLEAN**

gate0: { suite: PASS, lint: PASS (baseline-parity), types: N/A, tests_first: YES }

## Gate 0 — ran in-place (per S-BS-FAUTH4-1)
- HEAD `d4030d6`: **38 failed, 724 passed, 26 skipped** · Parent `c1e3771`: **38 failed, 719 passed, 26 skipped**.
- **Failure-set diff IDENTICAL — 0 net new, 0 swap** (+5 passing = `tests/bff/test_criterion_part.py`).
- Tests-first: worktree at `294f873` → the criterion test file is **RED** (tool absent: `AttributeError ... AUTHOR_CRITERION_SCHEMA`) → GREEN at `64807c1`.
- vitest: **1 failed | 158 passed** — the 1 fail is `src/app.test.jsx` (titlebar/ModeSwitch), **0-diff this cycle + fails at parent too** (pre-existing, not a regression); `CriterionBuilder.test.jsx` **4/4 green**.
- Lint: ruff 404==404 (baseline parity); the touched files are clean.

## The 4 questions (A-SAFE / containment)
1. **Emit-only containment — PASS, STRUCTURALLY guaranteed.** `author_criterion_handler` only `ctx.emit(criterion_builder_part(...))` + `_text(...)`; no bound write op. The `ToolContext` dataclass has NO criterion-write field; `_build_tool_context` binds 16 ops, none a criterion writer; `grep splice_gradeable_criterion|create_criterion_endpoint apps/bff/agent/` is EMPTY. The only mint path is the human's Save → `postCriterion` (`CriterionBuilder.jsx`). The emit-only stub-ctx test is non-vacuous (all 16 ops raise).
2. **A-SAFE — PASS.** `AUTHOR_CRITERION_SCHEMA` has no PAID_KEY (+ the all-schemas sweep); allowlist DERIVED from `_TOOL_SPECS` (count 20→21, no hardcode bypass); `_deny_non_lithrim` + isolation byte-unchanged; the pass-through test iterates all 21 → author_criterion gate-verified.
3. **MOAT / scope / no engine edit — PASS.** The 4 council files + `grounding.py` + `criterion.py` + `verification/spec.py` are 0-diff vs `c1e3771` (no new writer — reuses NARR-5-CRIT-a's `POST /v1/criterion`). Scope = `apps/bff/agent/{adapter,loop,tools}.py` + `apps/shell/src/{bff.js,genui/index.js,CriterionBuilder.jsx,CriterionBuilder.test.jsx}` + 6 tool-count updates + the new test. The 6 updates are honest GROWTH (20→21; the explicit expected sets ADD `author_criterion` — strengthened, not weakened).
4. **Honesty — PASS.** `loop.py`'s create_flag correction is accurate (create_flag reference-only; author_criterion mints on tier:core). FE `CODE_RE` is byte-identical to the server F1 guard `_CODE_RE`. No text implies the agent mints directly; A-LIVE correctly OWED (services down).

## Seams
1. **[FIXED] Branch-ref hazard.** The critic observed `bench-salvage/ws6c-dspy` at `462fa78` while the audited chain `91d9edf..d4030d6` (the rollback test, all bookkeeping, CRITIC-FIX-1, NARR-5-CRIT-b) descended from it un-reffed — a **critic-subagent `git checkout` in the SHARED working tree** reset HEAD+ref back to a baseline it measured. The commits were intact objects; the monitor **fast-forwarded** the branch to `d4030d6` (`git merge --ff-only`, tree clean, zero loss) + verified the full chain reachable. **PROCESS GUARD (S-BS-CRITIC-WORKTREE):** the devloop-critic checks out commits in the shared tree → after any cold critic, the monitor MUST re-verify `git rev-parse bench-salvage/ws6c-dspy == <expected tip>` and fast-forward if behind. (Prefer `isolation: worktree` for future critics, or have the critic restore the ref.)
2. **[DISCHARGED] Pin the containment invariant.** The emit-only guarantee is load-bearing on ToolContext having no criterion-write field; the existing test only checks the EXISTING ops raise. **Added** `test_toolcontext_carries_no_criterion_write_op` (`6b9f149`) — `assert not any("criterion" in f for f in ToolContext.__dataclass_fields__)` — so a future op-binding can't silently weaken it.

## Bottom line
A CLEAN, well-contained A-SAFE-widening cycle. Gate 0 green (38==38, RED→GREEN worktree, the one vitest fail is pre-existing app.test.jsx). The emit-only containment is structurally guaranteed (no ToolContext field, no binding, no grep path to the writer; the sole mint path is the human's Save). A-SAFE holds (no paid key, derived 20→21 allowlist, byte-frozen deny hook). Moat 0-diff (reuses NARR-5-CRIT-a's endpoint). 6 tool-count updates are honest growth. Two seams: the branch-ref hazard (FIXED + process guard logged) + the containment invariant (now pinned). No BLOCKING findings.
