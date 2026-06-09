# Spec-Adherence Critique — `bench-salvage` phase `PACK-2`

> Fresh-critic mode (HARD GATE). Committed alongside close-out artifacts.

## Metadata

- **Stream:** bench-salvage (healthcare-realm-as-pack, layer 2 — judges → pack)
- **Phase:** PACK-2
- **Driver bundle:** `bench-salvage-phasePACK-2-healthcare-pack-judges-layer-driver`
- **Commits audited:** `11b3811..5efbc1c` (6 atomic, parent `a43597b`)
- **Spec(s) read against:** the PACK-2 driver §2/§5, `SPEC_PLUGIN_ARCHITECTURE` (Phase-1 judge layer), `tests/_seam_freeze.py` (carve-out precedent), [[healthcare-realm-as-pack]]
- **Critique mode:** `fresh-critic` (separate worktree-isolated session, agent `afda337585b683404`)
- **Date:** 2026-06-09
- **Reviewer:** critic `afda337585b683404` + monitor close-out reconciliation

---

## Verdict

**`NON-BLOCKING FINDINGS`** — `[0 BLOCKING / 1 NON-BLOCKING / 1 OQ]`, recommend PROCEED.

One sentence: the layer-2 judges relocation is a clean, grep-verifiable, byte-behavior-identical move — the carve-out is exactly one path-only hunk at `compliance_council.py:470`, the 5 prompts are R100 SHA256-matched, the frozen consensus engine/roster/owners/taxonomy are byte-0-delta, the judges gate is non-vacuous and fail-closed without importing the council, both moat guards defeat-test correctly, and PACK-2 introduces **0 new test failures**.

---

## 1. Surface fidelity (the pack API + the carve-out)

| Driver deliverable | Implementation | Match? | Severity |
|---|---|---|---|
| D1 `pack_prompts_path()` + `assert_pack_judges_consistent()` + `council_roster()` | `harness/pack.py` (+102 lines), stdlib-only, AST-no-import | ✓ | — |
| D1 manifest `council_roles` ref | `packs/healthcare/pack.json` +1 line | ✓ | — |
| D2 `git mv` 5 prompts (R100) | all 5 `rename … (100%)`, SHA256-matched vs `a43597b` | ✓ | — |
| D3 both readers via `pack_prompts_path()` | `judge_assignment.py:25` (direct) + `compliance_council.py:470` (carve-out) | ✓ | — |
| D5 carve-out freeze guard (difflib one-hunk) | `assert_compliance_council_prompts_dir_relocated_only` | ✓ non-vacuous | — |
| D5 content-identity guard | `assert_council_roles_relocated_only` | ✓ non-vacuous | — |

**Findings:** No surface drift. The carve-out used an inline `__import__("lithrim_bench.harness.pack", fromlist=["pack_prompts_path"])` wrapped in `Path(...)` to keep the frozen-file touch to a SINGLE hunk (avoiding a 2nd import-statement hunk + an F401) — critic-confirmed SOUND (no circular import; `harness.pack` is stdlib-only, preserving the council's `openai`-free import surface; resolves to `packs/healthcare/council_roles` at runtime).

## 2. Behavioral fidelity

### Behavior 1 — the carve-out is path-only + behavior-preserving (A5)
- **Assertion:** only the `_ROLE_PROMPTS_DIR` path line changes; the consensus engine is untouched.
- **Test/proof:** `git diff a43597b HEAD -- compliance_council.py` = exactly ONE hunk (`grep -c '^@@'` = 1); `_load_role_prompts` (~:523-528) byte-untouched; roster (`485-516`), `_TIER1_OWNERS` (`233-262`), `KNOWN_TAXONOMY_CODES` (`292`), `judge_metric.py`, `judges_dspy.py` consensus seam all byte-identical to parent.
- **Chain closes?** YES. DEFEAT-TEST: reverting only the `:470` line → `assert_compliance_council_prompts_dir_relocated_only` FAILS (0 hunks). Mutating one `.txt` → `assert_council_roles_relocated_only` FAILS.

### Behavior 2 — the boundary is real (A1)
- **Assertion:** no clinical prompt content / `council_roles` load-path literal survives in the core.
- **Proof:** `git ls-files lithrim_bench/runtime/council/council_roles/` = EMPTY; prompts live only under `packs/healthcare/`; a bogus `LITHRIM_BENCH_PACK` raises `FileNotFoundError` (no silent core fallback). Surviving `council_roles` tokens in core are manifest-driven resolutions (`_manifest(pack)["council_roles"]`) or comments — not hardcoded literals.
- **Chain closes?** YES.

### Behavior 3 — the judges gate is non-vacuous + fail-closed + no-import (A3)
- **Assertion:** a mis-configured pack fails closed; the gate runs in the core no-openai env.
- **Proof:** `council_roster()` AST-parses to the 5 role names with neither the council nor `openai` in `sys.modules` after the call. Should-fails all raise: (a) declared judge with no prompt; (b) stray off-roster `.txt`; (c) off-roster declared judge. Positive control passes.
- **Chain closes?** YES.

**Findings:** A2 byte-behavior-identity is INFERRED (byte-identical prompts + 0-delta engine + `_load_role_prompts` glob is stem-keyed/order-independent ⇒ identical votes); the empirical paid live A/B was not fired and is reasonably waived. Owed belt-and-suspenders: a paid before/after on `ws0_default` (user-fires; carried from PACK-1's same OWED).

## 3. Out-of-scope intrusion

`git diff a43597b HEAD --stat` = 16 files: the 15 intended (pack infra, the 5 R100 renames, both readers, `seed_ontology.py:67` ROLE_DIR repoint, the 2 `_seam_freeze.py` helpers, the 2 reconciled frozen-seam tests, `test_pack_layer2.py`, the SPEC doc) + the session log. **No intrusion** — the monitor artifacts (`index.json` mod + the untracked driver doc) were correctly left unstaged per the dirty-index guardrail.

**Approved-at-plan deviations (logged, not intrusion):** (i) the blast radius the driver under-enumerated — the two `test_frozen_seam_zero_delta` tests + `seed_ontology.py:67` — surfaced by the executor at plan-review, monitor-verified independently, blessed (PACK-1 precedent, required for green-bar); (ii) Fork 1 → the inline `__import__` single-line carve-out; (iii) Fork 2 → a single `council_roster()` union for both gate clauses.

## 4. Spec ambiguity / open questions

**OQ-1 (the critic's):** `examples/judge_calib_v1.jsonl` carries a machine-ABSOLUTE `cohort_path`, so the determinism guard `test_uap4_corpus_superset::test_committed_corpus_matches_a_fresh_generator_run` cannot pass on any checkout whose path differs from where the corpus was generated (it failed in the critic's isolated worktree; passes in the canonical checkout). Pre-existing, out of PACK-2 scope. → **logged as seam S-BS-117** (low); fix = record a relative/normalized `cohort_path`.

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity | 0 | 1 | 1 |

**Total BLOCKING: 0** → cycle MAY close.

## The green-bar reconciliation (monitor, load-bearing — diagnose-before-edit)

The executor's handback green bar (`core 398p/0f`; `debuglithrim 554p/2f "S-BS-96 observation-isolation"`) did NOT match the critic's worktree re-run (`core 429p/1f`; `debuglithrim 537p/5f`, none named "observation"). The monitor ground-truthed the conflict in the **canonical main checkout**:

- The 5 critic-flagged failures + `test_pack_layer2` = **18/18 PASS canonical**; `runtime/observation/` = **13/13 PASS canonical**.
- ∴ the critic's extra failures are **isolated-worktree artifacts**: a missing `AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3` env var (`test_byoc_provider`) + the worktree's different absolute path defeating the absolute-`cohort_path` corpus guard + 3 `assert case is not None` **test-ISOLATION** failures (pass in isolation, fail in a full-suite run via shared-state/ordering).
- The pre-existing full-suite failures are isolation/env-sensitive (S-BS-96): ~2 in the canonical checkout, ~5 in a bare worktree.

**Decisive fact — PACK-2 = 0-new, triple-confirmed:** (1) the critic re-ran every observed failure at parent `a43597b` in the same worktree env → identical; (2) the 18 disputed tests pass canonical; (3) observation 13/13 pass canonical. PACK-2 touched only the `test_frozen_seam_zero_delta` fn (passes) + added `test_pack_layer2` (11/11). The executor's "2 = S-BS-96 observation-isolation" label was canonical-env-accurate in spirit (isolation-sensitive, ~2) but loosely worded; no regression.

## Required actions

None blocking. Dispositions:
1. **NON-BLOCKING (stale green-bar expectation):** the kickoff's "~398 / 2 S-BS-96" matches the canonical env; the critic's mismatch was worktree-env-relative. Accept as-is; recorded here.
2. **OQ-1 → S-BS-117 (low):** the absolute `cohort_path` portability bug. Accept/defer; spin off a fix when the corpus-regen layer comes.

## Critic discipline self-check (fresh-critic mode)
- [x] Re-derived from `git show`/code in an isolated worktree, not the executor's summary
- [x] Each finding cites code/diff evidence
- [x] Did NOT edit code/spec/driver; ran in worktree isolation (no shared-tree git ops; no `[detached HEAD]` at close)
- [x] Did NOT confer before the verdict

## Appendix: commits audited
```
5efbc1c chore(devloop): PACK-2 session log
f28942c docs(pack): PACK-2 D6 — record layer-2 in the plugin spec
deed21c test(pack): PACK-2 D5/A1/A3 — layer-2 boundary + judges-gate proof
44e9a24 test(pack): PACK-2 D5 — carve-out freeze guards + reconcile the frozen-seam tests
1795327 feat(pack): PACK-2 D2/D3 — relocate council role prompts into the healthcare pack
11b3811 feat(pack): PACK-2 D1 — pack_prompts_path + judges-consistency gate (dormant)
```
