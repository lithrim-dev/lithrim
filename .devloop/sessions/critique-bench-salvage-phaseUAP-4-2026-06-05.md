# Fresh-critic critique — bench-salvage phase UAP-4 (the calibration-trainer optimize loop, R5)

**Date:** 2026-06-05
**Critic:** genuinely-fresh (no prior implementation context)
**Range:** `d494ba9^..HEAD` (7 commits `d494ba9..faf06b5`)
**Gate:** HARD-GATE (paid labels-true-by-construction claim; honest-Δ load-bearing; frozen-seam-adjacent; corpus-widening admissibility)

**VERDICT: NON-BLOCKING [0 BLOCKING / 4 NB / 2 OQ]**

The cycle ships the demonstrable-live optimize→honest-Δ loop exactly as right-sized in driver v3. The accept-gate is genuinely not loosened (the most important check), A4 frozen seam is byte-0-delta, the corpus widening is a verified content-superset with the held-out split frozen and the admissibility lint GREEN, and the honest-loss render is honest. No round-trip backend leak. All deviations are documented decisions, not drift.

---

## Q1. Surface fidelity — route / client / Δ render vs the driver

**MATCH.** Every surface deviation is a documented decision.

- **The `/optimize` route** (`apps/bff/app.py:619-661`): `POST /v1/judges/{role}/optimize`, in the `:424` judge block, over `run_optimize(role, corpus_path=…, confirm_cost=True, out_dir=…, limit=…, coverage_aware=True)`. Returns `{role, n_train, n_heldout, baseline, optimized, delta, compile_config}`. Cost-gated: 422 unless `confirm=true`. 404 on unknown role. 502 (not silent-500) on a live Azure/dspy failure. Matches D1 verbatim.
- **The `optimizeJudge` client** (`apps/shell/src/bff.js:108-111`): routed through `call()` → `BASE`/`VITE_BFF_URL` (S-BS-50; no hardcoded `:8787`), `{confirm, limit}` body. Matches D1.
- **The Δ render** (`apps/shell/src/genui/JudgeEditor.jsx`, new `OptimizeDelta` component + an Optimize section + an in-DOM `Dialog` cost modal): inline in JudgeEditor (D-G monitor lean = inline), `data-testid="optimize-delta"`, explicitly NOT the `calibration_chart` reliability diagram (docstring says so + it's a bespoke component). Matches D2 + R4 (embedded, one continuous surface).
- **§10 ratify** (`docs/specs/SPEC_PRODUCT_SHELL.md`): the UAP-4 route ratified (D-C / S-BS-51), correctly worded ("accept-gate is NEVER loosened... a manufactured win = FAIL"; "No bind/persist... UAP-4-opt").

```
$ git diff d494ba9^..HEAD -- apps/bff/app.py | grep -A2 'OptimizeRequest\|/optimize"'
+class OptimizeRequest(BaseModel):
+    confirm: bool = False
+    limit: int | None = None
+@app.post("/v1/judges/{role}/optimize")
...
+    if not req.confirm:
+        raise HTTPException(status_code=422, detail=("optimize makes PAID Azure calls ...
+    return run_optimize(role, corpus_path=corpus_path, confirm_cost=True, out_dir=resolved_out, limit=req.limit, coverage_aware=True)
```

---

## Q2. Behavioral fidelity — 3 spec-claimed behaviors traced spec→test→impl

### (a) Honest Δ renders a LOSS as a loss [R1] — CONFIRMED

- **spec:** driver R1 — "a loss renders AS a loss... NEVER manufacture a win."
- **impl** (`JudgeEditor.jsx` `OptimizeDelta`): `const improved = (delta.graded ?? 0) > 0;` → loss path renders `data-testid="optimize-loss-note"`: *"optimize did not improve this judge... A trainer, not a demo: the accept-gate is never loosened to manufacture a win."* The win path points to UAP-4-opt for binding — it does NOT render a bind action.
- **test** (`JudgeEditor.test.jsx` "a ≤0 Δ renders EXPLICITLY as a loss (R1)"): asserts `data-outcome="loss"`, the loss-note text present, AND `queryByText(/optimize improved/)` is null (no manufactured-win copy on the loss path). The win test asserts the inverse.
- **route layer** (`tests/test_uap4_optimize_bff.py`): `_FAKE_RESULT` is a LOSS (`delta.graded == -0.1`, the real WS-6c-DSPy-3b prior); `test_optimize_returns_the_honest_delta_shape` asserts the loss passes through verbatim.

```
$ cd apps/shell && npx vitest run src/genui/JudgeEditor.test.jsx
 Test Files  1 passed (1)
      Tests  5 passed (5)
```

### (b) The accept-gate is NOT loosened by the coverage-aware fix [S-BS-49] — CONFIRMED (the load-bearing check)

The coverage-aware change is a **pure trainset reorder**, not a gate change.

```
$ git diff d494ba9^..HEAD -- lithrim_bench/runtime/council/judge_optimize.py | sed -n '/def order_positive_first/,/return positives + rest/p'
+def order_positive_first(trainset, *, lens):
+    """Reorder a trainset so in-lens POSITIVES come first ...
+    Surfacing positives first gives every nailable positive first crack at a demo slot
+    WITHOUT touching the accept-gate (judge_metric is FROZEN) and WITHOUT extra teacher
+    calls (a single compile pass) ... It cannot manufacture a win — a teacher that nails
+    no positive still yields none, honestly."""
+    positives = [ex for ex in trainset if _example_raises_in_lens(ex, lens)]
+    rest = [ex for ex in trainset if not _example_raises_in_lens(ex, lens)]
+    return positives + rest
```

`compile_judge` (lines 280-294): the ONLY behavioral insertion is `if coverage_aware: trainset = order_positive_first(...)` BEFORE an otherwise byte-identical `BootstrapFewShot`:

```
$ sed -n '282,294p' lithrim_bench/runtime/council/judge_optimize.py
    if coverage_aware:
        trainset = order_positive_first(trainset, lens=LENS_BY_ROLE[role])
    program = build_judge_program(lm=lm, predictor=predictor)
    metric = make_judge_metric(lens_codes=LENS_BY_ROLE[role], co_raise_aware=True)
    teleprompter = dspy.teleprompt.BootstrapFewShot(
        metric=metric,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_labeled_demos=max_labeled_demos,
    )
```

- `metric` = `make_judge_metric(...)` — unchanged, imported from the **FROZEN** `judge_metric.py` (0-delta, see A4 below).
- `max_bootstrapped_demos` / `max_labeled_demos` — unchanged defaults (4 / 0).
- No second positive-only bootstrap pass; no relaxed accept criterion. A positive demo is still kept ONLY if the teacher produces a clean/accepted trace (the BootstrapFewShot hard-accept). The reorder only changes WHICH nailable cases get first crack at the (still-gated) demo slots.

**test** (`test_judge_optimize.py`): `test_order_positive_first_surfaces_positives_preserving_order` (positives-first, stable within-group); `test_order_positive_first_on_the_corpus_has_positives_to_surface` (the widened cal split has in-lens positives). These prove it's a reorder, never a gate change.

**INFERRED:** because the gate is preserved, a positive demo only enters when the teacher genuinely nails it; if no positive is nailable the result is honestly 0 positive demos (matching the WS-6c-DSPy-3b finding). This is not a manufactured win.

### (c) Corpus widening is a content-superset with the held-out split FROZEN — CONFIRMED (independent re-derivation, not the test)

```
$ python3 - (load both files, key by case_id)
pre_widen rows: 47   |  pre is 47?: True
current rows  : 83   |  n added: 36  |  removed (must be empty): []
changed pre-existing (must be []): []          # canonical-JSON byte-identity
added not calibration: []   added not positive: []
pre splits : {'calibration': 17, 'test': 30}
cur splits : {'calibration': 53, 'test': 30}
test split frozen (30==30 and equal): 30 30 True
```

- Every pre-existing case_id present and byte-identical (canonical compare); 0 removed; 0 relabeled.
- All 36 additions are `split=calibration` positives.
- The `test` held-out split is the IDENTICAL 30-case set before and after — a lift can't be a test-set artifact.
- All 36 additions carry a complete `injection_recipes` (the field is plural; my first grep used the singular and false-flagged — corrected) with all 5 mandated fields (`defect_type`, `mutated_projection`, `mutated_field_or_span`, `pre_value`, `post_value`), and none are mislabeled `clean_negative`. CLAUDE.md inv#2 (recipe = label justification) holds.

```
$ python3 scripts/lint_golden_against_taxonomy.py --golden examples/judge_calib_v1.jsonl
lint_golden_against_taxonomy: 83 cases scanned ... scored: 83
  [OK] ... MISSING_ALLERGY x14 / WRONG_DOSAGE x14 / FABRICATED_CONSENT x12 / FABRICATED_HISTORY x12
       MISSED_ESCALATION x12 / PHI_DISCLOSURE_PRE_VERIFICATION x12 / VALUE_MISMATCH x1
OK: every expected_safety_flags code resolves ...  (exit 0)
```

positives-per-code roughly doubled (6→12, 8→14) for every code EXCEPT `VALUE_MISMATCH` (1→1) — exactly the S-BS-46 Synthea cohort cap, honestly **logged-not-padded** per D-H (the generator appends a `widen VALUE_MISMATCH` shortfall rather than fabricating). The commit message "6→12/code" is accurate.

---

## Q3. Out-of-scope intrusion — round-trip leak / FROZEN 0-delta

**NO INTRUSION. The FROZEN set is truly 0-delta.**

```
$ git diff d494ba9^..HEAD -- lithrim_bench/runtime/council/compliance_council.py \
    lithrim_bench/runtime/council/judges_dspy.py lithrim_bench/runtime/council/judge_metric.py \
    lithrim_bench/runtime/council/authored_stage.py data/ontology/clinical_v1.json \
    data/config/agents/ws0_default.json | wc -l
0
$ git diff d494ba9^..HEAD -- 'lithrim_bench/runtime/council/council_roles/*' | wc -l
0
$ git diff d494ba9^..HEAD -- 'data/config/agents/*' | wc -l
0
```

Each frozen file isolated = 0 lines: `judge_metric.py` 0, `judges_dspy.py` 0, `authored_stage.py` 0, `compliance_council.py` 0, role prompts 0, ws0_default 0, clinical_v1 0.

**No round-trip backend leak:**

```
$ git diff d494ba9^..HEAD --name-only -- lithrim_bench/harness/judges.py | wc -l
0                                          # harness/judges.py NOT in the diff
$ git diff d494ba9^..HEAD -- apps/bff/app.py | grep -in 'bind\|compiled_demos'
66:+    bind/persist of the compiled demos this cycle (the round-trip is UAP-4-opt)."""   # docstring DISCLAIMER only
```

Every other `compiled_demos`/`bind`/`authored_stage` token in the diff lives in the **UAP-4-opt stub driver** + `index.json` + `TASK_PACK` (the deferral docs) — i.e. the SPLIT was registered, not built. `bind_compiled_demos` in `judge_optimize.py` is the pre-existing mechanism (untouched this cycle, no new call site). No `JudgeConfig.compiled_demos` field, no `/bind` endpoint, no `authored_stage` demo-load.

**Full touched-file list (16):** all in-scope — BFF route, bff.js, JudgeEditor(+test), judge_optimize(+test), generate_judge_calib, corpus + frozen fixture, 2 test files, SHELL §10, session log, + the UAP-4-opt scaffolding (stub driver / index / task-pack). Nothing beyond D1–D5.

**A3/A-LIVE correctly NOT fired:** no paid-run artifact in the diff (no `out/`, `.sqlite`, provenance fixture, or optimize-result JSON). Per R3 the live attestation is a USER-RUN close gate, owed — its absence is CORRECT, not a gap.

---

## Q4. Spec ambiguity — judgment calls the spec was silent on

- **D-G render form:** the spec offered inline-vs-`tool-optimize_delta`; impl chose **inline** (the monitor lean, smallest). Defensible.
- **502 on live failure:** the route wraps the live Azure/dspy path in `try/except → 502` rather than a silent 500. Spec was silent; a sound call (the route is a thin pass-through to a fallible paid backend).
- **`get_calib_corpus_path` as a FastAPI dependency:** added so tests can override the corpus path without reading the committed corpus. Spec silent; clean and test-honest.
- **`coverage_aware` defaults to `False`** in `compile_judge`/`run_optimize`; the BFF route opts in (`coverage_aware=True`). This preserves the WS-6c-DSPy-3b reproduction path (the prior negative-Δ run is re-derivable with the flag off) while the product surface gets the S-BS-49 fix. A good additive-default choice; spec didn't specify the default.

---

## Findings

### [NON-BLOCKING] `_demo_raises` helper is defined + tested but not called in product code
```
$ grep -rn "_demo_raises" lithrim_bench/ apps/ | grep -v test
lithrim_bench/runtime/council/judge_optimize.py:149:def _demo_raises(demo: Any) -> bool:
# run_optimize line 405 uses an inline d.get("findings") instead of calling _demo_raises:
405:    n_positive_demos = sum(1 for d in demos if d.get("findings"))
```
`_demo_raises` is exercised only by `test_demo_raises_detects_non_silent_exemplar`; `run_optimize` re-implements the same predicate inline. Minor redundancy — either call the helper or drop it. Diagnostic-only either way (`n_positive_demos` is reported in `compile_config`, never gates). CONFIRMED. No correctness impact.

### [NON-BLOCKING] The win-path copy is aspirational (the live path is a LOSS today)
`JudgeEditor.jsx:75-77` win path: *"✓ optimize improved this judge (+X held-out graded). Binding the compiled demos back ... is the next step (UAP-4-opt)."* Per the WS-6c-DSPy-3b prior + S-BS-49, the real held-out Δ is currently a LOSS, so the live A-LIVE attestation will almost certainly render the loss note, not this. The win copy is correct IF a win occurs and correctly points to UAP-4-opt (no bind action this cycle). It is not misleading — just unlikely to fire until S-BS-49 actually lifts. CONFIRMED.

### [NON-BLOCKING] Coverage-aware fix is sound but UNMEASURED against a live Δ (S-BS-49 stays open)
The reorder is correct and gate-preserving, but whether it actually LIFTS the held-out Δ is the cost-gated A-LIVE measurement, not run this cycle (correct per R3). Per the driver A3 this is the **PASS-honest / halt-to-surface** branch by default: the mechanism ships, S-BS-49 stays open with the measurement owed. The diagnostic intuition (more positives + positives-first → the teacher has ≥1 nailable in-lens positive → ≥1 positive demo) is plausible but HYPOTHESIS until the paid run. The cycle does not claim a win, so this is honest. INFERRED.

### [NON-BLOCKING] `run_optimize` line 405 duplicates the `n_positive_demos` predicate
Same root as finding 1 — a one-line DRY cleanup. No behavior impact. CONFIRMED.

### [OPEN-QUESTION] Is the `VALUE_MISMATCH x1` floor acceptable for the faithfulness lens's coverage-aware path?
The widening doubled every code except VALUE_MISMATCH (cohort-capped at 1, S-BS-46). For the **faithfulness** judge specifically, the in-lens positive pool is thinner than for risk/policy, so coverage-aware demo selection has fewer positives to surface there. Honestly logged-not-padded (correct by-construction), but a future faithfulness-judge optimize run may still under-cover. Not a defect of THIS cycle — flagging that S-BS-46 still gates the faithfulness arm of the S-BS-49 fix. CONFIRMED (the cap), HYPOTHESIS (the optimize impact).

### [OPEN-QUESTION] The honest-Δ render keys "win-or-loss" on `delta.graded` only
`OptimizeDelta` decides win/loss via `delta.graded > 0`. A run could improve precision while `graded` (the hard-accept composite) is flat/down, and it would render as a "loss." This is defensible (graded = the production hard-accept = the right headline), and all three metrics are shown with per-metric signs/colors, so a precision-only lift is still visible. But the binary headline is graded-only. Spec said "win-or-loss" without naming the discriminant. Verdict-neutral; surfacing for the monitor. CONFIRMED.

---

## Load-bearing invariant ledger

| Invariant | Result | Evidence |
|---|---|---|
| A4 FROZEN 0-delta (seam + seeds + role prompts) | **PASS (0)** | `git diff ... \| wc -l` = 0 across all frozen files; each isolated = 0 |
| NO round-trip leak (`harness/judges.py`, `/bind`, `compiled_demos`) | **PASS** | judges.py not in diff; only a docstring disclaimer + UAP-4-opt stub mention bind |
| Accept-gate NOT loosened | **PASS** | reorder-only; `BootstrapFewShot` config byte-identical; `judge_metric.py` 0-delta; "cannot manufacture a win" |
| `judge_metric.py` untouched | **PASS (0)** | isolated diff = 0 lines |
| Corpus honesty (superset / byte-identical / cal-only adds / test frozen / lint GREEN) | **PASS** | independent load: 47→83, 0 changed, 36 cal positives, test=30 frozen; lint exit 0; recipes complete |
| Honest-Δ UI (loss renders as loss; win → UAP-4-opt not a bind action) | **PASS** | `optimize-loss-note`; win copy points to UAP-4-opt; no bind button |
| Default tests | **280 passed / 10 skipped** | `pytest tests/ -q` (skips = dspy/openai absent) |
| UAP-4 default tests | **10 passed** | `pytest tests/test_uap4_corpus_superset.py tests/test_uap4_optimize_bff.py -q` |
| debuglithrim optimize unit | **10 passed / 1 skipped** | live optimizer skip is cost-gated (correct) |
| debuglithrim full council | **98 passed / 3 skipped** | all skips live-Azure cost-gated |
| Vitest (JudgeEditor) | **5 passed** | win + loss + cancel + 2 pre-existing |
| ruff (changed files) | **clean** | `All checks passed!` |
| import-clean (no dspy/openai at core import) | **PASS** | `dspy`/`openai` not in `sys.modules` after importing `judge_optimize` |
| A3 + A-LIVE (paid, user-run) NOT fired | **CORRECT** | no paid-run artifact in diff (R3) |

---

## Test counts (actual, re-run by the critic)

- **default:** `tests/test_uap4_corpus_superset.py tests/test_uap4_optimize_bff.py` → **10 passed**; full `tests/` → **280 passed / 10 skipped**
- **debuglithrim:** `test_judge_optimize.py` → **10 passed / 1 skipped**; full council → **98 passed / 3 skipped**
- **Vitest:** `JudgeEditor.test.jsx` → **5 passed**

All causal claims tagged CONFIRMED unless marked INFERRED/HYPOTHESIS above.
