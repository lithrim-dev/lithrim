# CRITIQUE — bench-salvage phase FAUTH-4 / NARR-FLOOR-1 (fresh cold critic)

> Persisted verbatim by the monitor from the cold-critic subagent's return (the `devloop-critic`
> agent type has Read/Bash/Grep/Glob — no Write tool by design). The critic RAN Gate 0 itself.
> Commit range: parent `21cd859` → RED `54f6c18` (test-only) → GREEN `e85203a`.

verdict: **CLEAN**

gate0: { suite: PASS, lint: PASS, types: N/A (no type-checker in CLAUDE.md; ruff is the lint), tests_first: YES }

**Gate 0 — deterministic (ran it myself, verbatim):**
- Env: `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare python -m pytest -q -p no:cacheprovider` (Python 3.10.15).
- **Full suite, HEAD `e85203a` (real repo root):** `38 failed, 698 passed, 26 skipped`.
- **Full suite, parent `21cd859` (real repo root, apples-to-apples):** `38 failed, 693 passed, 23 skipped`. The +5 passed at HEAD are exactly the 5 new `value_presence` tests that run under the healthcare default.
- **Parent↔HEAD failure-set diff (same physical repo root): IDENTICAL — 0 net new, 0 swapped.** My first comparison used a `/tmp` worktree and showed a 1-for-1 "swap" (`test_a1_council_binds_from_external_pack` ↔ `test_build_trio_no_models_is_all_azure_back_compat`). I ran that down: it is a **worktree-path artifact**, not a value_presence effect. `tests/test_pack_dist.py:37,153` computes `_HAS_SIBLING` from `REPO_ROOT.parent / "lithrim-pack-healthcare"` (hardcoded by filesystem layout; ignores the env var), so in `/tmp/fauth4_parent` that test SKIPS while at the real checkout it RUNS and fails on `assert 21 == 19` — pure external-pack drift (the sibling now ships 21 codes / 9 owners). The byoc swap is full-suite ordering/state pollution (passes in isolation at HEAD). Re-running parent in the **same** physical root eliminated both and yielded an identical 38-set.
- The 38 failures are the documented pre-existing `../lithrim-pack-healthcare` drift (e.g. `test_a5_frozen_seam_guards_green` fails on `clinical_v1.json` drift vs `acc4973` — present in BOTH parent and HEAD sets; nothing to do with this cycle).
- **Zero `value_presence` tests fail.** New file under healthcare default: `5 passed, 3 skipped`; under `LITHRIM_BENCH_PACK=narrative`: `8 passed` (A4 flip trio + A5 subprocess all green).
- **Lint:** `ruff check` on the 3 cycle files → "All checks passed!" (repo-wide ruff has 404 pre-existing errors, none in the cycle's files; project standard is touched-file-clean).
- **Tests-first:** `git log` confirms `54f6c18` (RED test, "value_presence is an unknown tool") precedes `e85203a` (GREEN impl). RED→GREEN demonstrated.

**The 4 questions:**

1. **Driver intent met — YES.** Core name-only registration: `lithrim_bench/verification/spec.py:46` `TOOL_VALUE_PRESENCE = "value_presence"`, added to `_KNOWN_TOOLS` (:59) and `_REQUIRED_REFERENCE_KEYS[TOOL_VALUE_PRESENCE] = {"value_regex"}` (:87, `source_path` optional). Tool + executor pack-local: `packs/narrative/floors.py:201` `ValuePresenceTool` (reuses core `_dig`/`_norm` from `verification/tools.py:57,61`, not reimplemented) + `_value_presence_reference` (:317) + `FLOOR_EXECUTORS["value_presence"]` (:342). Tri-state matches spec: `absent→False`, `present→True`, empty/non-str/no-source/no-token/`re.error`→`None`. The EXIT is the offline `$0` `ground()` pair (A4).

2. **Flip is non-vacuous, both directions — YES.** `tests/test_value_presence_floor.py:265` PASS→BLOCK (`g.original_verdict=="PASS" and g.verdict=="BLOCK"`, composite "reject", `VALUE_DROPPED` injected); `:278` clean twin stays PASS with `floor_blocks==[]`; `:289` inconclusive (no source) STANDS (`injected_finding is None`, verdict PASS). Default `match='all'` exercised both ways at `:159` (drop one of two doses→False; both preserved→True). Oracle is deterministic surface-form only — `re.findall(...)` at floors.py:264 + `_norm` substring; **no LLM/dspy/openai/network in the path** (grep-confirmed). A malformed regex `r"("` is caught (`except re.error`, floors.py:265) → `conforms=None`, asserted at `:155` — inconclusive, not a grade-abort.

3. **Moat / scope / spec-fidelity — CLEAN.** The 4 moat files + `harness/grounding.py` are **byte-0-diff** vs `21cd859` (`git diff --stat` empty). Scope is exactly `spec.py` + `floors.py` + the new test (`apps/bff/agent/` 0-diff; no FE/ontology/JSON touched; `value_presence` appears in only those 3 files). Both `floor_executors()` equality snapshots are **unperturbed** — `_EXPECTED_FLOOR = {"structural_jute","jute_gen","dosage_grounding"}` (test_plugin_phase1.py:59) and the `_core ⊊ healthcare` assertion (test_grounding_contract_gate.py:269) both run under healthcare/`_core` where the narrative-local floor is absent; both pass at HEAD. Spec-fidelity: SPEC_CLINVERDICT §122 mandates pack-local tool/executor + name-only core — honored (NOT a core floor). No new SDK-MCP tool.

4. **Honesty gap — none.** No commit or the driver claims a live *clinical* (healthcare-pack) flip; the grep for "clinical flip / live clinical / case-10 live" is empty. The driver explicitly scopes the demonstrable flip to the narrative crafted pair and defers the clinical case-10 to a DATA follow-on ("Do NOT wire the clinical case-10 contract into the EXTERNAL healthcare pack here"). The honest limit is stated in-code (floors.py:215, "surface-form matching is brittle vs paraphrase; the SNOMED-coded oracle is the richer swap-in, FAUTH-3b").

**New seams:** one — `value_presence` as the second `FLOOR` direction floor type, registered name-only in core (`spec.py`) with the executor pack-local. Authoring is now params-only via the existing ContractBuilder + FAUTH-2 author-time gate; a second inverse floor needs no new code.

**Bottom line.** This is a tight, spec-faithful cycle. Gate 0 is green: the full suite's pre-existing 38-failure external-pack-drift baseline is byte-identical parent↔HEAD when measured from the same physical repo root (the apparent "swap" was a `_HAS_SIBLING`-by-layout worktree artifact, not the change), zero `value_presence` tests fail, lint is clean on the touched files, and RED preceded GREEN. The implementation does exactly what the driver and SPEC_CLINVERDICT §122-124 specify — a pure-stdlib, deterministic (no-LLM, OQ-3) inverse-direction completeness floor that flips PASS→BLOCK on an absent spoken value, stays PASS on the clean twin, and stands on the inconclusive case, all proven offline through the unchanged tri-state `ground()` loop. The moat (4 council files + grounding.py) is byte-frozen, scope is exactly the 3 promised files, both equality snapshots are unperturbed, and nothing over-claims a clinical flip. I tried to break it on the failure-set swap, the malformed-regex abort path, the `match='all'` non-vacuity, and a stray-wiring/over-claim scan — all held. **CLEAN.**

---

## Monitor corroboration (independent, post-critic)
- MOAT + `grounding.py` 0-diff vs `21cd859` re-confirmed; scope = `spec.py` + `floors.py` + the new test + the driver (untracked, in the bookkeeping commit).
- Failure-set diff parent↔HEAD captured independently by the monitor (`/tmp/fauth4_parent_fails.txt` vs `/tmp/fauth4_mine_fails.txt`) = IDENTICAL, 38==38, 0 swap — matches the critic.
- The critic's `_HAS_SIBLING`-by-layout finding is a useful tripwire for any future worktree-based baseline measurement (measure the parent in the SAME physical root, or the `test_pack_dist` skip toggles spuriously). Logged as **S-BS-FAUTH4-1** (low; measurement hygiene, not a product defect).
- HARD-GATE (verdict-path) **satisfied** — independent cold critic ran Gate 0 + the 4 questions and returned CLEAN.
