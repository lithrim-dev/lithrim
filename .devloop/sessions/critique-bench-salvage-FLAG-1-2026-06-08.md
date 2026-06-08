# Fresh-critic critique — `bench-salvage` FLAG-1 (reference-flag create/delete local + the honest gradeable-from-clean gate)

> **Mode:** HARD-GATE → genuinely-fresh critic (Agent `aca2db88ac2ec11f8`, cold context, isolated worktree) + monitor 7-item audit.
> **Date:** 2026-06-08 · **Verdict: NON-BLOCKING** (fresh-critic [0 BLOCKING / 1 NB / 1 OQ-resolved]; monitor audit CLEAN). FLAG-1 closes **CLEAN**. With CRUD-1 + FLAG-1, objective #2 (CRUD-from-clean) is done — **all 3 of the user's 2026-06-07 objectives are complete.**

## Monitor 7-item audit (independent)
1. **Commits** `6592a2a..67d3025` (5 atomic + the session log) on `bench-salvage/ws6c-dspy`, parent `6592a2a` (the prior monitor's handoff commit), NOT pushed; tree clean except the concurrent `root.jsx` (M) + the 3 foreign untracked. Per-commit `--stat`: no foreign file in any commit. ✓
2. **Files** = 9: `apps/bff/app.py` + `apps/bff/agent/{tools,loop}.py` + `docs/ONTOLOGY_FLAG_LIFECYCLE.md` + `tests/{test_flag_crud[new],test_crud_delete,test_uap5b_chat,test_uap5c_journey}.py` + the session log. Matches the driver + the approved deviation. ✓
3. **Tests** — monitor re-ran the targeted suite (81 passed); full debuglithrim 478/2/3 (the 2 = the S-BS-96 observation pair); ruff clean on all 7 touched `.py`. ✓
4. **Scope** — `taxonomy/taxonomy_snapshot.json` **BYTE-UNTOUCHED** (git diff empty + sha re-confirmed); council/consensus frozen seam 0-delta (no council file in the diff); no `examples/*.jsonl` golden row touched; golden lint OK. ✓
5. **Prefs** — pathspec-only (`root.jsx` + the 3 foreign untracked never swept), no autostart (the executor probed `:8787` via 404-not-405, not a restart), no pushes. ✓
6. **Session log** CLEAN — the 3 deviations + S-BS-99 logged with evidence; the net-zero live-smoke caveat documented. ✓
7. **Deviations** justified — the 11th-tool deviation is `APPROVED-AT-PLAN` and matches the monitor go; citation-drift logged; create-audit shape logged. ✓

## The approved deviation (logged)
**① delete = an 11th conversational tool** (`delete_flag`), superseding the driver's route-only recommendation (count 9→11: `create_flag` 10th, `delete_flag` 11th). Monitor-ratified at the go **on the merits**, not on attribution: consistent with CRUD-1's risk-tiering (reversible / low-blast-radius deletes → conversational, like `delete_judge`; high-blast → human-only, like `delete_agent`), and **guard-bounded by construction** — the load-bearing condition (PIN 1) is that all three delete guards live in `delete_flag_endpoint`, NOT the `_delete_flag` wrapper, so they hold for every caller. CONFIRMED honored (C5).

## Fresh-critic — load-bearing checks (all CONFIRMED; every required perturbation flipped a real test)
- **C1 — the one law, STRUCTURAL (A-SAFE) — CONFIRMED + NON-VACUOUS.** `CREATE_FLAG_SCHEMA` carries no `gradeable`/`tier`/`owner_roles`; tool surface `== 11`; no `PAID_KEYS` in any schema. Perturb proofs: adding `"gradeable": bool` → `test_create_flag_schema_has_no_gradeable_field` FAILS; adding `"live": bool` to `DELETE_FLAG_SCHEMA` → the no-paid-knob test FAILS (`assert ['live'] == []`).
- **C2 — the one law, BEHAVIORAL hardcode — CONFIRMED + NON-VACUOUS.** `_create_flag` hardcodes `gradeable=False/tier=None/owner_roles=[]` (never from args). Flipping it to `gradeable=True` → `test_create_hardcodes_gradeable_false_nonvacuous` FAILS (the create returns `is_error` because `_validate_ontology` 422s the out-of-snapshot gradeable code) — load-bearing through the real validator.
- **C3 — A2 the honest gradeable-from-clean REFUSAL — CONFIRMED, non-vacuity REAL.** Out-of-snapshot `gradeable:true` → 422 naming the re-snapshot path + the offender; the 200-accept leg PUTs the committed seed whose **19 gradeable codes are all in the 19-code snapshot tier-union** (verified directly) — not a degenerate zero-gradeable body. The legs differ by exactly the violating dimension. `author_flag`-flip-to-gradeable also surfaces the refusal.
- **C4 — the three DELETE guards — CONFIRMED, two perturbed.** All 4 guard tests + 404 + audited-allow pass; disabling GUARD 2 (`if False and …`) → `test_delete_guard_refuses_judge_assigned` FAILS (`200 == 422`); disabling GUARD 3 → `test_delete_guard_refuses_case_emitted` FAILS. The audited-allow asserts `before≠None, after=None, action=delete, target=flag, actor.id=sme`.
- **C5 — PIN 1 / PIN 2 — CONFIRMED, airtight.** `_delete_flag` only binds-and-forwards; all guards in the endpoint; the agent's `ToolContext` exposes exactly 11 bound ops with **no raw `put_ontology` callable** → no backdoor to remove a flag via PUT and bypass the guards. The critic tried to find an unguarded path and could not; `test_agent_reachable_delete_is_bounded_by_the_endpoint_guards` passes.
- **C6 — core invariant untouched — CONFIRMED.** Snapshot byte-untouched; no golden row modified; golden lint passes (exit 0); create/delete write only `workdir/<agent>.json`.
- **C7 — frozen-seam 0-delta + scope/pathspec — CONFIRMED.** No council/seed/consensus file in the diff; the 9 changed files are exactly the declared set; per-commit `--stat` shows no foreign file; the 3 count-bump files carry only the 9→11 update + the two `_noop` stub-ctx fields (no behavioral test weakened).
- **C8 — full-suite, no regression — CONFIRMED.** The FLAG-1 failure set is identical parent→HEAD (zero new failures); FLAG-1 adds +18 passing.

## Baseline reconciliation (monitor — diagnose-before-edit)
The fresh-critic (in its isolated worktree) reported debuglithrim **6 failed / 473 passed** vs the executor's **2 failed / 478 passed**, flagging the "2 pre-existing" characterization as understated. **Monitor ground-truthed it (CONFIRMED, verbatim):**

```
=== FULL debuglithrim SUITE (main checkout, HEAD 67d3025) ===
FAILED .../test_observation_pipeline.py::test_importing_observation_does_not_load_compliance_modules
FAILED .../test_observation_pipeline.py::test_default_run_pulls_no_heavy_deps
2 failed, 478 passed, 3 skipped
=== the 4 critic-flagged tests, in the MAIN checkout ===
15 passed
```

The canonical MAIN-checkout suite is **2 failed / 478 passed / 3 skipped** — the 2 being exactly the S-BS-96 observation-isolation pair; the 4 extra tests the critic saw fail (`test_byoc_provider`, `test_uap4_corpus_superset`, `test_uap3b2_provenance`, `test_uap3b_withstands`) **all pass in the main checkout**. **INFERRED (high-confidence):** they fail only in a fresh `git worktree` because a worktree carries tracked-at-HEAD files but NOT the main tree's **untracked generated artifacts** (out/ packs, seeded config DB) those tests depend on — consistent with the 2 observation tests (no such dependency) failing in both environments. So the critic's NON-BLOCKING verdict + zero-regression finding are robust; the "6-failure" reading is a **worktree-isolation artifact, not a baseline correction**. **Canonical for the record: 478/2/3** (+18 over CRUD-1's 460/2/3, same 2 failures). Process note folded into S-BS-96 (a worktree-isolated critic under-reports green unless untracked artifacts are regenerated; read the baseline in the main checkout).

## Findings
- **S-BS-99 (low, NEW — executor-opened, monitor-confirmed).** The flag-delete corpus-orphan guard (`_cases_emitting_flag`) is best-effort: it scans `examples/*.jsonl` only (not `out/*.jsonl` generated packs) and silently skips a malformed JSON row. **Near-zero exposure** — a reference (out-of-snapshot) code cannot legally appear in a golden pack (the golden lint rejects it), and the lint remains the real enforcer; the endpoint documents this. Acceptable for FLAG-1's reference-only delete; flagged if delete ever extends to scanning generated packs.
- **NB-1 (cosmetic — stale test names; monitor records).** Two count-bump functions retain pre-FLAG-1 names while now asserting `== 11`: `test_asafe_delete_judge_is_the_ninth_tool_no_paid_knob` (test_crud_delete.py) and `test_split_and_crud_tools_grow_the_set_to_nine_with_no_paid_knob` (test_uap5c_journey.py). Harmless naming drift; a future touch can rename. Not blocking.
- **OQ (resolved by the monitor, no action).** The critic's "the baseline is 6, not 2" open-question is resolved above as a worktree-isolation artifact; the canonical baseline is 2.

## Disposition
NON-BLOCKING → **FLAG-1 CLOSED CLEAN.** The flags half of objective #2 is delivered: local reference-flag CREATE + DELETE (guarded, audited, reversible) + the HONEST refusal of gradeable-from-clean (the core invariant — a scoreable flag's code comes only from a lithrim-backend re-snapshot). The one law is enforced at three independent layers (schema absence, behavioral hardcode, the `_validate_ontology` 422), each proven non-vacuous; PIN 1 (guards in the endpoint, no agent PUT backdoor) is airtight. The honest gate ran LIVE on `:8787` (422 + re-snapshot message, non-vacuous) and `:5180` (the BYO-Claude agent refused conversationally — *"the manufactured-win failure mode this product exists to prevent"* — honesty-is-the-moat demonstrated). Opened **S-BS-99** (low). No proof capsule (CRUD-mechanics, not a capability A-LIVE with honest-Δ; the live `:8787`/`:5180` create→try-gradeable→refuse→delete smoke + the audit trail are the record). **With CRUD-1 + FLAG-1, all three of the user's 2026-06-07 objectives (UX-1 + BYOC-1 + CRUD-from-clean) are complete.**
