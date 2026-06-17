# Critique — bench-salvage NARR-5 (narrative-eval demo — offline foundation D1-D4 + LIVE 3-model run D5)

> **HARD GATE — fresh cold critic** (no implementation context; agent `a8583f597408f62cf`). Mandate: Gate 0 (supreme, both envs + vitest) → 4 spec-fidelity questions → **the load-bearing D5 honest-Δ check** (does the proof capsule match the run artifacts? any manufactured win?) → moat-freeze. Edited nothing; scratch worktrees removed.
>
> **Verdict: CLEAN.** Gate 0 green both envs + vitest (0-new); tests-first non-vacuous; moat byte-frozen; scope clean; **and the D5 proof capsule is an honest match to the run artifacts with NO manufactured win.** One NON-BLOCKING coverage gap + 3 honestly-disclosed open-questions.

Date: 2026-06-17 · Cycle: `a4efd0f..550f1f5` (D1-D4 by executor `a4a3be421311ac8fa` 2f65ce6..e74e6a9; D5 driven by the monitor; proof capsule 550f1f5) · Monitor 7-item audit: CLEAN.

---

## Gate 0 — supreme, re-run cold
- **Targeted (pack=narrative):** `pytest -q tests/test_narrative_{floor,pack,multimodel_seam,corpus_bridge}.py` → **19 passed / 0 failed.** D4 named `test_policy_judge_fires_length_violation_with_evidence_MOCK` (contains MOCK).
- **Regression (pack=healthcare full):** HEAD = 5 failed / 587 passed / 13 skipped. Classified cold: 4 are order-pollution flakes (PASS in isolation); 1 deterministic (`test_pack_dist::test_a2`) is **pre-existing** (needle prose in `packs/narrative/{ontology,taxonomy_snapshot}.json`, byte-identical at parent; this cycle did NOT touch `packs/narrative/`). **0 NEW deterministic.**
- **vitest:** 1 failed / 133 passed — the 1 is pre-existing S-BS-145 (`app.test.jsx`, untouched file); `artifact.test.jsx` 13/13 incl. both D2 tests. **0 new.**
- **Tests-first:** checked out RED commit `2f65ce6` — D1 (`test_narrative_corpus_bridge.py`) + D2 (`artifact.test.jsx` floor-block) genuinely FAIL → **RED→GREEN non-vacuous** for the two production deliverables. (D3/D4 are test-only proofs of pre-existing wiring — green-on-existing per the honestly-disclosed plan-review form.)
- **Lint:** ruff clean on touched `.py`.

## The 4 spec-fidelity questions
1. **Surface — MATCH.** D1 (`picklist.py:101-145`): lazy-guarded `workspace` import; fallback runs **strictly last** (the `if pack_row is not None: return` guard short-circuits → S-BS-9 PACK_FILES-first preserved in code; source-pin still first). D2 (`artifact.jsx:111-132`): renders `comp.floor_adjustments`, color-codes `floor_block` vs `floor_inconclusive`, gated `length>0` (no false BLOCK on empty/null). D3 (`test_narrative_multimodel_seam.py:63`): `models={'risk_judge':'byo-claude'}` with **NO predictors** — critic independently proved zero network egress; names say SEAM/WIRING not judge quality. D4: MOCK.
2. **Behavioral — tests assert the spec** (D1 grades a real enveloped case end-to-end; D2 renders the SILENT_DEGRADATION floor_block row), with **one NON-BLOCKING coverage gap** (see Findings).
3. **Out-of-scope intrusion — NONE.** `git diff a4efd0f HEAD --stat` = the 7 expected files (picklist.py, artifact.jsx, artifact.test.jsx, 2 new test files, session-log, proof capsule). `apps/bff/app.py` untouched (enumeration intact); no re-snapshot; no healthcare; no core.
4. **Spec ambiguity → 3 OPEN-QUESTIONs** (honestly disclosed; see Seams).

## D5 honest-Δ — CAPSULE MATCHES THE ARTIFACTS. No overclaim. No manufactured win.
The critic verified every capsule claim against `out/narr5_d5/*.json`:
- Run 1 (silent_degradation, default GPT/Mistral/Llama trio): composite **reject** / stage **BLOCK** / 1 `SILENT_DEGRADATION` floor_block (`conforms=false`, `disposition=VIOLATION`); `risk_judge` conf **0.970535**. ✓
- Run 2 (clean): **approve** / PASS / 0 floor blocks / 0 findings. ✓
- Run 3 (`risk_judge=byo-claude`): still **reject** / BLOCK; `risk_judge` conf **None** (the swap signature). ✓
- The headline honest-Δ: `risk_judge` vote **WARN (GPT) → PASS (Claude)** — the LLM judge disagreed with itself across models, **yet the deterministic floor caught it BOTH ways → reject** (the moat thesis live; an honest LOSS-flavored result, not a tuned win). `faithfulness_judge`: BODY_CONTRADICTION (run1) → BODY_CONTRADICTION + PERSONALIZATION_MISS (run3). All EXACT.
- **No overclaim:** the capsule explicitly states "3 distinct models" is NOT evidenced by the record's `model` field (which shows the role name) — it grounds the claim in `_ROLE_DEPLOYMENT` + the D3 offline proof + the confidence-swap. Gaps (a)-(d) all disclosed and all TRUE in the artifacts.

## Moat-freeze — PASS (0-diff)
`git diff a4efd0f HEAD --` empty across compliance_council/signals/withstands/judge_metric.py + harness/grounding.py + verification/{spec,tools}.py + apps/bff/agent/tools.py. No re-snapshot; app.py untouched.

## Findings
- **NON-BLOCKING (coverage) → `S-BS-NARR5-2`:** `test_pack_files_first_precedence_preserved_on_collision` (`tests/test_narrative_corpus_bridge.py:115-149`) is **vacuous under the canonical env** — its collision id `narrative_jinn_exposure_clean` isn't in `PACK_FILES` (which maps only clinical `out/*.jsonl`), so `resolve_case_fixtures` returns empty and the test always takes the `else` branch, never exercising the PACK_FILES-first assertion. The precedence is CORRECT in code (guard short-circuits) → not reducible to a failing test → NON-BLOCKING. Strengthen with a real PACK_FILES case_id. (Minor twin: the D2 fixture uses `disposition:"inject_block"` while the live pipeline emits `"VIOLATION"` — harmless, the component renders any string.)

## Seams (open)
- **`S-BS-NARR5-1`** (low, NARR-6 / a provenance cycle) — the subprocess `in_process` grade path does NOT surface `provenance.cost_tokens` (returns `{0,0,0}`); a real PAID run's spend isn't captured.
- **`S-BS-NARR5-2`** (low) — the precedence test is vacuous under the canonical env (above); strengthen it.
- **`S-BS-97`** (low, pre-existing, re-confirmed live) — per-vote `.model` carries the role name; `deployment`/`provider` are null. Surface the real per-judge deployment in the vote record/UI.
- **`S-BS-NARR4-1`** (low, **NARR-6 obligation**) — the REAL live `LENGTH_VIOLATION` positive-catch is still owed (D4 is a mock; D5's cases weren't over-length).

## Disposition
The NARR-5 contract is met (D1-D5); Gate 0 green on both envs; the moat is byte-frozen; scope is clean; **the D5 proof capsule is honest (the load-bearing check).** **Cycle closes CLEAN.** The polished browser walkthrough + zyng video + the 4 seams are NARR-6.
