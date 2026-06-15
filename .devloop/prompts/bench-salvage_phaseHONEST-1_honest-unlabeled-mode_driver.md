# HONEST-1 — honest unlabeled mode — driver (executor)

> **Phase 0 of the open-core MVP program** (the [[lithrim-doubledown-decision]] roadmap). The product
> currently FABRICATES an accuracy/calibration number on unlabeled data: a run over a case with no
> `expected_compliance_verdict` reports `verdict_match_rate 0.0 / status WARN` and a meaningless ECE — as if
> the system *failed*, when in truth there is no ground truth to check against. This directly contradicts the
> honesty-is-the-moat thesis on the **exact surface a new BYO user sees first**. HONEST-1 makes the unlabeled
> path tell the truth: show the (label-free, real) verdict + per-judge reasoning + grounding overrides, and
> **suppress** accuracy/ECE behind an explicit "no ground truth — author labels to unlock calibration" state.
>
> **Why first:** it is a *contradiction, not a feature* — shipping ingestion (Phase 1) while the Review pane
> still fakes 0.0/WARN would actively break the brand on first contact. It is also tiny (3–5 days), entirely
> ABOVE the frozen moat, and a pure precondition for the BYO-INGEST slice.
>
> **Bundle ID:** `bench-salvage-phaseHONEST-1-honest-unlabeled-mode-driver`
> **Version:** v1 · **Authored:** 2026-06-16 (monitor) · **Last re-verified against code:** 2026-06-16 (§0)
> **Hardness:** HARD GATE (fresh-critic) — it IS the honesty surface; a cold critic must confirm no fabricated
> number leaks on the unlabeled path AND the labeled path is byte-unchanged (non-vacuous both directions).

---

## KICKOFF (paste this block into a fresh executor session)

```
You are the EXECUTOR for the .devloop/ cycle: bench-salvage phase HONEST-1 (honest unlabeled mode).

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseHONEST-1_honest-unlabeled-mode_driver.md  (this doc)
  3. The §1 pre-flight files, in order.

Then post your plan-review per EXECUTOR.md §"Plan-review (non-negotiable)", resolving H-D1..H-D5 (§3).
Do not write code until the monitor says "go".

Bundle ID: bench-salvage-phaseHONEST-1-honest-unlabeled-mode-driver
Driver doc: .devloop/prompts/bench-salvage_phaseHONEST-1_honest-unlabeled-mode_driver.md
```

---

## §0 — Verbatim evidence (diagnose-before-edit)

### The honesty bug: unlabeled data → a fabricated `0.0 / WARN` accuracy (CONFIRMED, end-to-end)

The run-level summary is keyed entirely to the case's planted label:

```python
# lithrim_bench/harness/report.py:178-189  (calibration_check)
expected = normalize_expected_verdict(rec["provenance"]["expected_compliance_verdict"])
if rec["composite"]["verdict"] in expected:          # unlabeled: expected == set() → never matches
    n_matched += 1
...
verdict_match_rate = round(n_matched / n_cases, 4) if n_cases else 0.0   # → 0.0 on unlabeled
ece = round(ece_weighted_sum / n_pooled, 4) if n_pooled else 0.0
status = "PASS" if n_cases and n_matched == n_cases else "WARN"          # → WARN on unlabeled
```

On unlabeled data `expected_compliance_verdict` is absent → the empty-set collapse is the root:

```python
# lithrim_bench/picklist.py:83-84  (normalize_expected_verdict)
if value is None:
    return set()                  # → `rec["composite"]["verdict"] in set()` is ALWAYS False
```

The BFF folds this into **every** run-eval response unconditionally:

```python
# apps/bff/app.py:446
record["calibration_check"] = calibration_check([record])
```

And the Review pane renders the fabricated number + mislabels the case:

```jsx
// apps/shell/src/artifact.jsx:58   const cal = runResult.calibration_check;
// apps/shell/src/artifact.jsx:130-131   <span>Verdict match</span>
//                                       <span>{cal.verdict_match_rate} · {cal.status}</span>   // "0 · WARN"
// apps/shell/src/artifact.jsx:454   "clean negative — nothing planted (expected verdict: approve)"  // unknown-truth mislabeled
```

**So: a BYO user's own note grades fine (the verdict + grounding are LABEL-FREE and real — confirmed below), but
the Review pane reports a `0.0 / WARN` "accuracy" and calls their unknown-truth note a "clean negative."** That
is the product lying on the honesty surface. HONEST-1 fixes it by making the absence of labels an *explicit,
honest state* — never a fabricated failure. The manufactured-pass inverse (defaulting unlabeled to PASS/1.0) is
EQUALLY forbidden — honest-Δ cuts both ways.

### The grade is label-free (the de-risk — CONFIRMED). Only the SUMMARY assumes labels.

```python
# lithrim_bench/harness/report.py:95   def calibration(result, *, expected_block, ...)   # report-only
# lithrim_bench/harness/grade.py        composite(grounded) consumes verdict + grounding ONLY — no label arg
# scripts/run_eval.py:101-102           expected_* are written to provenance FOR LATER COMPARISON ONLY
```

The verdict path (`composite`, the council, the grounding floor) never reads a label. **HONEST-1 touches ONLY
the accuracy/calibration SUMMARY (`calibration_check` / `calibration`), the BFF fold, and the UI render.** The
verdict the user sees is unchanged.

### SEAM REACH — none of this touches the moat

`compliance_council.py`, `_apply_consensus`, `signals.py`, `judge_metric.py LENS_BY_ROLE`, and `composite()`
(the verdict/grade path) are NOT in scope. Every edit is the report summary + the BFF pass-through + the UI.

---

## 1. Pre-flight reading (ordered)

1. `lithrim_bench/harness/report.py:95-206` — `calibration` + `calibration_check` (the two functions to make
   label-aware). Note the existing `caveat`/small-N machinery to mirror.
2. `lithrim_bench/picklist.py:75-99` — `normalize_expected_verdict` (the empty-set source) + `expected_block`.
3. `apps/bff/app.py:108` (import) + `:388-460` (the run-eval endpoint + the `:446` fold) — confirm the fold is
   pass-through (no other consumer reshapes `calibration_check`).
4. `apps/shell/src/artifact.jsx` (whole) — `:58` cal read, `:126-142` the calibration block, `:440-460` the
   CaseTab "clean negative / expected verdict" panel. The two render surfaces to branch.
5. `apps/shell/src/artifact.test.jsx` (esp. `:158` "nothing planted") + `apps/shell/src/bff.test.jsx`
   (`:24,:55` the `calibration_check` mock + "1/1 · PASS" assertion) — the existing tests; identify which carry
   a label (keep) vs assert obsolete unconditional behavior (update).
6. `scripts/run_eval.py:90-110` — where `expected_*` enter `provenance` (confirm a BYO/unlabeled case simply
   has them absent/None; no upstream defaulting to a fake label).
7. Prior driver for house style: `.devloop/prompts/bench-salvage_phaseEVAL-FLOW_ground-truth-to-run-rail-faithful-paid-run_driver.md`.

> **Citation discipline:** re-verify every file:line against current code before plan-review; halt + surface on
> drift (EXECUTOR.md §Citation drift).

---

## 2. Deliverables (file-by-file) — tests FIRST

1. **Tests (RED first)** — `tests/…` (pytest, debuglithrim) for A1–A3 + `apps/shell/src/*.test.jsx` (vitest)
   for A4–A5. Network-free, fixture-based. RED recorded before any code.

2. **W1 — label-aware `calibration_check`** (`lithrim_bench/harness/report.py`). Compute a per-run
   `label_status` ∈ {`"labeled"`, `"unlabeled"`, `"partial"`} from whether each record's
   `normalize_expected_verdict(provenance.expected_compliance_verdict)` is non-empty. When **no** case is
   labeled: set `verdict_match_rate: None`, `ece: None`, `status: "unlabeled"`, and a `caveat`
   ("no ground truth — author labels to unlock accuracy/calibration"); keep the factual counts
   (`n_cases`, `n_with_confidence`). The LABELED path is byte-unchanged. (H-D1 fixes the exact shape.)

3. **W2 — gate the per-case ECE/reliability honesty** (`report.py` `calibration`). On an unlabeled case the
   "correct = vote agrees with `expected_block`" computation is meaningless (scored against an empty expected).
   Per H-D3: on unlabeled, do NOT emit reliability-as-accuracy / ECE; at most a raw confidence distribution
   clearly NOT labeled "accuracy". Smallest honest cut = suppress (null) it; the confidence-histogram-as-its-
   own-thing is DEFERRED. Keep `expected_block`-driven behavior intact when a label IS present.

4. **W3 — BFF pass-through stays honest** (`apps/bff/app.py:446`). The fold must surface the new
   `label_status` + nulled fields verbatim (no reshaping that re-introduces a 0.0/WARN). Likely zero logic
   change — confirm no other endpoint code coerces the summary.

5. **W4 — honest Review render** (`apps/shell/src/artifact.jsx`). When `cal.status === "unlabeled"` (or
   `cal.label_status === "unlabeled"`): the calibration block (`:130-131`) renders
   "No ground truth — verdict & grounding shown; accuracy/calibration withheld. Author labels to unlock."
   instead of "{rate} · {status}". The verdict + per-judge reasoning + grounding-override panels render
   UNCHANGED (they are real + label-free).

6. **W5 — CaseTab unknown-truth branch** (`apps/shell/src/artifact.jsx:454`). Branch the
   "clean negative — nothing planted (expected verdict: approve)" line on label presence: only show it when the
   case actually declares a clean-negative label; for an unlabeled case render "unknown ground truth (your
   data) — no planted label." Update the obsolete `artifact.test.jsx:158` assertion to be label-gated (A5).

---

## 3. Plan-review checkpoint (non-negotiable) — resolve these decisions

Post Understanding · file-by-file · test plan · risks · proposed deviations, and **resolve**:

- **H-D1 (load-bearing): the unlabeled `calibration_check` shape.** (i) keep the dict, set
  `verdict_match_rate: None` + `ece: None` + `status: "unlabeled"` + `label_status` + caveat [recommended:
  shape-stable for the BFF/UI, explicit honest marker] vs (ii) omit the misleading keys entirely + a top-level
  `label_status`. Pick one. FORBIDDEN: leaving `0.0`/`"WARN"` (manufactured failure) OR defaulting to
  `1.0`/`"PASS"` (manufactured win).
- **H-D2: where `label_status` is computed** — in `calibration_check` (report.py) [recommended: same module,
  BFF stays pass-through] vs in the BFF fold. Keep ONE source of truth.
- **H-D3: per-case `calibration()`/ECE on unlabeled** — suppress (null) [recommended for the skeleton] vs
  re-surface as a raw confidence distribution explicitly NOT labeled "accuracy" [defer]. Don't show an
  accuracy-shaped number with no ground truth.
- **H-D4: `partial` semantics (batch / eval-pack).** For a mixed batch, report the rate over the LABELED
  subset + `label_status: "partial"` + a caveat naming the unlabeled count [recommended] vs suppress entirely.
  (run-eval is single-case; eval-pack batches — A3 pins this.)
- **H-D5: existing-test disposition** — confirm `bff.test.jsx:24/55` (the "1/1 · PASS" mock) and
  `artifact.test.jsx:158` ("nothing planted") run on LABELED fixtures (keep) vs assert obsolete unconditional
  behavior (update to label-gated). Replaced tests must be replaced by a STRONGER test of the new behavior, not
  deleted.

Wait for "go" before writing code.

---

## 4. Scope guardrails — NOT in scope

- **The ingest endpoint / note→FHIR→case adapter / bind-on-ingest / `ingest_case` tool** — that's Phase 1
  (BYO-INGEST), a separate driver. HONEST-1 makes the *existing* grade path honest; it does NOT add a way to
  get user data in.
- **A label-AUTHORING write path** (let the user supply their own per-record ground truth to UNLOCK accuracy)
  — Phase 3 / deferred. HONEST-1 only SUPPRESSES the fake number and INVITES labeling; it does not implement
  label authoring.
- **`composite()` / the council / the grounding floor / the verdict path** — untouched; the verdict is already
  honest + label-free.
- **The moat** (`compliance_council.py`, `_apply_consensus`, `signals.py`, `judge_metric.py LENS_BY_ROLE`) —
  byte-frozen, zero diff.
- **The WS-4b locked calibration gate** — `calibration_check` is explicitly the ADVISORY summary, not the
  preregistered gate; do not turn it into one.
- Drive-by prettier on `apps/shell` JSX (`[[shell-no-prettier-handcompact-jsx]]`), dep bumps, "while I was here".

If something feels load-bearing-but-not-listed, halt and surface it in plan-review.

---

## 5. Acceptance criteria (each a test written FIRST)

- **A1 (unlabeled is honest).** `calibration_check([rec])` with `rec.provenance.expected_compliance_verdict
  is None` returns `status == "unlabeled"`, `verdict_match_rate is None`, `ece is None`,
  `label_status == "unlabeled"`, and a non-empty `caveat`; and contains NO `0.0`/`"WARN"`/`"PASS"`/`1.0` for
  the suppressed fields — `tests/…::test_calibration_check_unlabeled_is_honest`. **RED today** (returns
  0.0/WARN).
- **A2 (labeled path UNCHANGED — non-vacuous both directions).** A labeled rec whose composite verdict ∈
  expected → `status == "PASS"`, `verdict_match_rate == 1.0`, `label_status == "labeled"`. A labeled rec whose
  verdict ∉ expected → `status == "WARN"`, `verdict_match_rate == 0.0` (a GENUINE failure is still reported) —
  `tests/…::test_calibration_check_labeled_unchanged`.
- **A3 (partial batch).** `calibration_check([labeled, unlabeled])` → `label_status == "partial"`, the rate is
  over the labeled subset (per H-D4) + a caveat naming the unlabeled count; never a fabricated pooled
  0.0/WARN — `tests/…::test_calibration_check_partial_batch`.
- **A4 (UI withholds honestly).** The Review/artifact component given `calibration_check.status ===
  "unlabeled"` renders the "no ground truth / accuracy withheld" copy and does NOT render a "· WARN" or "· PASS"
  verdict-match line; the verdict + grounding panels still render — `artifact*.test.jsx::test_review_unlabeled_withholds_accuracy`.
  **RED today.**
- **A5 (CaseTab unknown-truth).** The CaseTab given an unlabeled case does NOT render
  "clean negative … expected verdict: approve"; it renders the unknown-truth copy. The existing
  `artifact.test.jsx:158` assertion is updated to be label-gated (kept for the labeled fixture; new test for
  unlabeled) — `artifact*.test.jsx::test_casetab_unlabeled_is_unknown_truth`.
- **A6 (guard — moat + verdict path byte-frozen).** `compliance_council.py`, `_apply_consensus`, `signals.py`,
  `judge_metric.py LENS_BY_ROLE`, and `grade.py composite()` zero-diff; only `report.py` (`calibration*`), the
  BFF fold, and `artifact.jsx` change — existing seam-guard trio green; `git diff <parent> HEAD --stat`
  confirms.

---

## 6. Commit structure (atomic, pathspec-only, tests first)

1. `test(honest-1): unlabeled-mode acceptance — red`
2. `fix(honest-1): calibration_check tells the truth on unlabeled data (W1+W2)`  — report.py
3. `fix(honest-1): honest unlabeled Review render + unknown-truth CaseTab (W4+W5)`  — artifact.jsx (+ W3 if any)

Each body ends with: `Executed per bench-salvage-phaseHONEST-1-honest-unlabeled-mode-driver by session-2026-06-16-N.`
plus the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

**Commit pathspec-only** (`git commit -m <msg> -- <files>`; never bare-commit — concurrent .devloop sessions
stage foreign files; `[[git-commit-pathspec-in-a-dirty-index]]`). Verify scope: `git diff <parent> HEAD --stat`.

---

## 7. Verification checklist (run before the session log)

- [ ] Acceptance tests written first + RED recorded; the `test(...)` commit precedes its fix commits.
- [ ] A1–A6 PASS; A1/A2/A4 NON-VACUOUS (fail on a controlled revert of the fix; A2 fails if the labeled path
      regresses — pins both directions).
- [ ] Canonical `pytest -q` (debuglithrim, **`LITHRIM_BENCH_PACK=healthcare
      LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare` EXPORTED**) + `cd apps/shell && npx vitest run` green,
      0-new-fail vs parent.
- [ ] `git diff <parent> HEAD --stat`: no file outside §2; moat + `composite()` zero-diff.
- [ ] No services autostarted (curl /health first); no push/publish/tags.
- [ ] Session log per `.devloop/templates/SESSION_LOG_TEMPLATE.json`.

> **Env note (load-bearing, S-BS-156/158):** the canonical suite is GREEN only with
> `LITHRIM_BENCH_PACK=healthcare` **exported in the shell** (root `conftest.py` freezes module-level path
> constants under `_core` otherwise). Always export it for the green-bar run.

---

## 8. First move
1. Read `.devloop/personas/EXECUTOR.md` end-to-end.
2. Read §1 pre-flight in order; re-verify the cited file:lines (halt on drift).
3. Post plan-review per §3 (resolve H-D1..H-D5). Wait for "go".

---

## 9. References
- Decision: `[[lithrim-doubledown-decision]]` (Phase 0 of the open-core MVP roadmap) + the 4-analysis
  stress-test workflow (`lithrim-doubledown-decision` run, 2026-06-16).
- The gap it closes: `[[byo-data-ingestion-cliff]]` (blocker #4, the honesty contradiction).
- Brand thesis: `[[self-asserting-loop-honesty-moat]]` (manufactured win = FAIL — applies to manufactured
  LOSS too).
- Prior driver (house style): `.devloop/prompts/bench-salvage_phaseEVAL-FLOW_ground-truth-to-run-rail-faithful-paid-run_driver.md`
- Stream state: `.devloop/state/streams.json` (bench-salvage `current_phase`) + `STREAM_bench-salvage.md`.

## Hardness
- [x] **HARD GATE** — fresh-critic session required. It IS the honesty surface; a cold critic must confirm
  (a) no fabricated number leaks on the unlabeled path (any field), (b) the labeled path is byte-unchanged AND
  still reports a genuine WARN on a real mismatch (non-vacuous both directions), (c) the moat + `composite()`
  are untouched. Trigger via a fresh critic session with `.devloop/prompts/KICKOFF_CRITIC.md`. 0 BLOCKING to close.

## Next phase (after close)
Phase 1 — **BYO-INGEST** (`POST /v1/case` + note/FHIR→case adapter + bind-on-ingest + `ingest_case` tool). Do
NOT ship ingestion before HONEST-1 closes — a new user's first run must not report a fake accuracy.
