# Fresh-critic critique — `bench-salvage` CRUD-1 (judge + agent DELETE + runnable blank-slate)

> **Mode:** HARD-GATE → genuinely-fresh critic (Agent `a989dc135dc2d4d6a`, cold context) + monitor 7-item audit.
> **Date:** 2026-06-07 · **Verdict: NON-BLOCKING** (fresh-critic [0 BLOCKING / 2 NB / 2 OQ]; monitor audit CLEAN). CRUD-1 closes **CLEAN**.

## Monitor 7-item audit (independent)
1. **Commits** `893d7a7..eff4911` (5 atomic + log) on `bench-salvage/ws6c-dspy`, parent `8f59407`, not pushed; tree clean except the concurrent `root.jsx` (M) + the 3 foreign untracked. ✓
2. **Files** = 15: harness {audit,config,judges} + bff {loop,tools,app} + shell {app,bff,panes,bff.test,rail.test} + tests {test_crud_delete,uap5b,uap5c} + session log. Matches the driver. ✓
3. **Tests** (targeted re-run 33 passed; full = critic's A). ✓
4. **Scope** — council frozen seam 0-delta (compliance_council/judge_metric/judges_dspy/authored_stage/seeds all empty); `collections.py` 0-delta (runs append-only, no delete); ontology/taxonomy untouched (FLAG-1 territory); `loop.py` = `_SYSTEM_PROMPT` only (deny-hook + `_build_options` byte-identical). ✓
5. **Prefs** — pathspec-only (`root.jsx` never swept), no autostart (used the running `--reload` BFF + the preview), no pushes. ✓
6. **Session log** CLEAN, S-BS-98 opened, the mutate-then-restore process caveat documented. ✓
7. **Deviations** justified (BFF-edge guards / harness pure; no-op-no-audit; both pre-approved at plan-review). ✓

## Fresh-critic — load-bearing checks (all PASS, independently reproduced)
- **A — green bar, no new failures:** debuglithrim `460 passed / 2 failed / 3 skipped` (stable ×3; the 2 = the pre-existing observation-isolation pair, CRUD-1 touches no observation file), plain `347/0/27`, vitest `69/69`, ruff clean on all 9 touched .py.
- **B — A-SAFE 9-tool bound NON-VACUOUS:** all 9 `mcp__lithrim__*`, none paid; `delete_judge` schema = `{role, rationale}`; `ToolContext` has `delete_judge`, NO `delete_agent`. Proven by 2 scratch perturbations (inject a paid key → fail; add a `delete_agent` field → fail), reverted.
- **C — deny-hook byte-identical:** `loop.py` diff = 3 `_SYSTEM_PROMPT` lines only; `_deny_non_lithrim`/`_build_options`/`setting_sources`/`bypassPermissions`/`HookMatcher` unchanged; runtime allow(`mcp__lithrim__delete_judge`)/deny(`Bash`) confirmed; fail-closed on missing tool_name.
- **D — delete semantics/guards/audit (live TestClient, tmp DB):** 422 seed-default, 422 last-agent (isolation test), 404 unknown, 200 + `action="delete"` audit row (before→after, who/when/what/why); judge-revert idempotent (200 removed:true → 200 removed:false → 404); the no-op writes NO row (change-only trail; `delete_with_audit` records only when `before is not None`, removal + audit in one txn).
- **E — frozen 0-delta + no run-delete:** all council/seed/ontology/taxonomy/collections diffs empty; journey + `root.jsx` not in the CRUD-1 commits.
- **F — runnable blank-slate + S-BS-98 honesty:** `judges` table is `role TEXT PRIMARY KEY` (no agent column); `run_eval_endpoint` reads `list_judges` GLOBALLY (app.py:294), never `agent.eval_profile.judges`. `createAgent` clones the seed Dataset+ontology with an empty roster → runnable from clean. **S-BS-98 is TRUE and honestly disclosed in 5 places** (seam, plan-review deviation, report, A3 nuance, + a shipped `bff.js` code comment); "clean state" is consistently scoped to roster+dataset+chat, never judge-clean. Not an overclaim.
- **G — scope/hygiene:** 15 files, 6 pathspec-clean commits, no `index.json`/`TASK_PACK`/`MONITOR.md`/`.claude`/`root.jsx`/`STREAM_` swept; no remote.

## Findings
- **NB-1 (session-log bookkeeping miscount — monitor records the correction).** The committed session log's `diagnostic_stats.diff_stat` says "14 files / 818 ins" and A6 says "shell ×4." The true range `8f59407..eff4911` is **15 files / 958 ins** (the executor measured before its own session-log commit → 14 code files + the log = 15; code-only is 14/818/31). But **shell is genuinely ×5** (app.jsx, bff.js, bff.test.jsx, panes.jsx, rail.test.jsx), not ×4 — a prose miscount. Substance in-scope; bookkeeping only. (The committed log is a historical record; corrected here, not rewritten.)
- **NB-2 (S-BS-96 is order-non-deterministic, not a fixed pair — SHARPENED).** At the parent `8f59407`, canonical `pytest -q` yields a *shifting* failure SET across runs (6 failed both times, different members; the 2 observation tests pass in isolation = `sys.modules`-pollution/order-sensitive). Post-CRUD-1 HEAD is **deterministic 460/2/3** (CRUD-1's added test file stabilizes collection order). CRUD-1 introduced no failures and is *more* stable, but the underlying isolation debt is bigger than "2 fixed failures." → S-BS-96 text sharpened.
- **OQ-1 (the "baseline" is a moving target).** "The SAME 2 failures" is robust only because CRUD-1's order is stable; a future cycle that reorders tests could surface a different "pre-existing" set. Folds into S-BS-96 (the real fix = subprocess-isolate the observation tests + deterministic pytest ordering).
- **OQ-2 (guard precedence — no action).** If `ws0_default` were ever the sole agent, the seed-default 422 fires before the last-agent 422 → "seed default" message instead of "last remaining." Both 422, both correct refusals; message-precedence nuance only.

## Disposition
NON-BLOCKING → **CRUD-1 CLOSED CLEAN.** The judges+agents half of objective #2's "complete CRUD" is delivered (DELETE + guards + audit + runnable blank-slate). Opened **S-BS-98** (global judge-config store → "clean state" is roster/dataset/chat-clean, not judge-clean; candidate per-agent-judges refactor — relevant to FLAG-1's "clean" narrative). **Sharpened S-BS-96** (order-non-deterministic isolation debt). No proof capsule (CRUD-mechanics cycle, not a capability A-LIVE with honest-Δ; the live :8787 + :5180 create→switch→delete smoke + the audit trail are the record). **Next = FLAG-1** (reference-flag create/delete local; the last objective-#2 piece; driver already authored at `8f59407`).
