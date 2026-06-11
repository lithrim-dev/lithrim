# Driver — `bench-salvage` phase `CE-PACK-6b-ROUTE`: authored path = the only live grade

> **Bundle ID:** `bench-salvage-phaseCE-PACK-6b-ROUTE-authored-path-only-live-grade-driver`
> **Version:** v1 · **Authored:** 2026-06-12 · **Last re-verified:** 2026-06-12 (HEAD 2742d32)
> **Execution:** monitor-spawned subagent in the main tree; pathspec-scoped commits; monitor audits at close.

**The product-correctness cut.** Make the in-process grade dispatch ALWAYS use the AUTHORED path (the ontology/role-prompt path the UI edits), so `ComplianceCouncil.build_prompt` (the legacy clinical default council) becomes **dead code on the product path**. One live source of prompt truth — a hardcoded `build_prompt` would silently ignore UI prompt edits (OQ-1, memory `generic-ce-demarcation`). Non-frozen: `build_prompt` is NOT deleted here (that's the FROZEN 6b-CLEAN); this only stops *routing* to it.

**MEASURED context (monitor, 2026-06-12):** at `scripts/run_eval.py:256-273`, no-assignment runs set `semantic_stage=None` → the default council → `build_prompt` (`compliance_council.py:2459`). `build_authored_semantic_stage(assignments=None)` already works (renders the pack's base role prompts). `build_prompt` is ALSO reached via `runtime/pipeline/stages.py` + `ab_harness` + a `test_consensus.py:311` unit test — those are **OUT of scope** (6b-CLEAN / they keep build_prompt as a still-present unit). This cycle reroutes ONLY the in-process product grade dispatch.

---

## 1. Pre-flight (verified 2026-06-12, HEAD 2742d32)
1. `scripts/run_eval.py:256-273` — the dispatch: `semantic_stage=None; if assignments or models or roles: semantic_stage = build_authored_semantic_stage(...)`. **The reroute site.**
2. `lithrim_bench/runtime/council/authored_stage.py:41-53` `build_authored_semantic_stage(*, ontology, assignments=None, predictors=None, ...)` — works with `assignments=None` (base prompts) or a lens map. `judge_assignment.py:46-101` `render_role_questions`.
3. `lithrim_bench/harness/pack.py` `pack_lenses()` + `pack_production_judges()` — the default-assignment source.
4. `tests/test_uap3_grade.py:80-91` — constructs `build_authored_semantic_stage` directly (assignments=None vs a lens) with mock predictors; the authored-marker FLIP semantics. NOT via run_eval → unaffected by the reroute, but the precedent for the default-assignment choice.
5. `tests/fixtures/ws0/baseline.*.json` — the ws0_default REPLAY baseline (the old default-council verdict). Replay reads it without grading → unaffected; the live authored verdict differs (`docs/research/RUN_ws0_default_post2c_in_process_2026-06-11.md` + the support_ticket_qa live smoke `RUN_ce_standalone1_live_smoke_2026-06-12.md`).
6. `lithrim_bench/harness/grade.py:130-165` `grade_inprocess(semantic_stage=...)` — the consumer; `semantic_stage=None` falls through to the default council.

---

## 2. Deliverables

**D0 — MEASURE (HALT-gate).** Patch run_eval so no-assignment → the authored stage (default assignments = `{role: pack_lenses()[role] for role in pack_production_judges()}`), then run the full suite (debuglithrim). **Report what breaks.** Expected: tests that drive `run()`/run_eval WITHOUT assignments and assert the default-council verdict. **HALT-and-report if** the breakage is beyond a handful of test updates (the scope is then larger → monitor re-scope). Tests that construct `build_authored_semantic_stage` directly (test_uap3_grade, standalone, neutral_default) are unaffected.

**D1 — the reroute.** `scripts/run_eval.py:256-273`: replace the `semantic_stage=None` no-assignment fall-through with a default authored stage — when `not (assignments or models or roles)`, set `assignments = {role: pack_lenses()[role] for role in pack_production_judges()}` (a "full-lens default") and build the authored stage. So `semantic_stage` is NEVER `None` on the in-process path. **Plan-review decision:** default to the full pack lens (recommended — each judge grades at its full scope) vs `assignments=None` (base prompts only, no refinement) — validate against D0's breakage + `test_uap3_grade`'s "unassigned" semantics; pick the one that's behavior-honest and surface it.

**D2 — handle the dispatch's downstream.** Update the run_eval docstring/comments (`:253-256`, `:208`, `:456`) that say "no assignments → the default council (back-compat)" to the new reality (authored-by-default). Confirm `grade_inprocess` callers in CI still pass (D0).

**D3 — the ws0_default re-pin (lightweight).** Verify the ws0_default REPLAY tests still pass (they read the baseline, don't grade) — no fixture change needed. Add a note (in the baseline fixture's sibling doc or a comment) that the reference verdict is now via the authored path post-6b-ROUTE; the recorded baseline is the historical default-council verdict. **Do NOT regenerate the baseline via a live/non-deterministic run.** If a CI test actually grades ws0_default through the rerouted dispatch and asserts the old verdict, surface it in D0 and update it to the authored expectation (deterministic mock, like test_uap3_grade).

**D4 — prove build_prompt is off the product path.** A test/assertion that the in-process dispatch no longer yields `semantic_stage=None` (e.g. a unit test that run_eval's no-assignment path builds an authored stage). Note in a comment that `build_prompt` remains physically present (reached only by `stages.py`/`ab_harness`/the consensus unit test) and is deleted in 6b-CLEAN.

**D5 — docs.** `SPEC_STANDALONE_CORE_VALIDATION.md` §4 CE-PACK-6b-ROUTE → DONE. CLAUDE.md one-line note (the in-process grade is authored-path-only; build_prompt is legacy/off-path). Reference the live-smoke evidence (the authored path is the live grade).

---

## 3. Plan-review / report
Subagent: post the D0 measurement FIRST. If bounded, proceed D1–D5; if the breakage is large, HALT + report the true blast radius. Surface the default-assignment choice (full-lens vs None) with the test evidence.

## 4. Scope guardrails — NOT in scope
- **The FROZEN council** — `compliance_council.py` (incl. `build_prompt` itself), `judges_dspy.py`, `safety_flags.py`. Do NOT delete build_prompt (6b-CLEAN). This cycle changes ROUTING only.
- **The pipeline `stages.py` / `ab_harness` / `test_consensus.py:311`** — other build_prompt entrypoints; left for 6b-CLEAN. Don't reroute them.
- **Regenerating the ws0_default baseline via a live run** — fragile/paid; do not.
- **The `_build_signature` clinical residue (S-BS-129)** — 6b-CLEAN.
- No frozen edit; no service autostart; no push.

## 5. Acceptance
- **A1:** run_eval's in-process path with no assignments builds an authored stage (never `semantic_stage=None`); `build_prompt` is not reached on that path (D4).
- **A2:** full suite **0-new vs `2742d32`** (debuglithrim); ruff clean on touched files. Any default-path test updated to the authored expectation with a deterministic mock (no paid run, no flake).
- **A3:** the standalone + neutral_default + uap3_grade authored-path tests stay green (the authored path is unchanged; only the DEFAULT routing changed).
- **A4:** docs updated; the run_eval "back-compat default council" comments corrected.

## 6. Commits (pathspec-scoped — foreign files `apps/shell/src/app.jsx` + `journeys/*` + the demo HANDOFF MUST stay untouched)
1. `refactor(run_eval): authored path is the only in-process grade — default judges to their pack lens (6b-ROUTE D1/D2)`
2. `test(ce): prove build_prompt is off the product grade path + any default-path test re-pin (D0/D3/D4)`
3. `docs: 6b-ROUTE done — in-process grade is authored-only; build_prompt legacy/off-path (D5)`
End bodies: `Executed per bench-salvage-phaseCE-PACK-6b-ROUTE-... by a monitor-spawned subagent 2026-06-12.` + Co-Authored-By trailer.

## 7. Verification
- [ ] A1–A4 PASS · D0 HALT-gate honored · commits exist, foreign files untouched (`git status --porcelain` check after each commit) · no frozen-council file touched · tests+ruff clean (record env) · session log written

## 8. Hardness
- [x] **Routine** (monitor inline critique) — non-frozen. The suite-0-new gate (A2) + the D0 HALT-gate are load-bearing (a routing change to the default grade path). If D0 shows wide breakage, return to the monitor before D1+.
