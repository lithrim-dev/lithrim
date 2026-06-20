# CRITIQUE — bench-salvage phase NARR-5-CRIT-a (fresh cold critic, GOVERNANCE HARD-GATE)

> Persisted verbatim by the monitor from the cold-critic subagent's return (the `devloop-critic`
> agent has no Write tool). The critic RAN Gate 0, demonstrated RED→GREEN in a worktree, AND
> empirically forced the atomicity rollback end-to-end. Range: `0fa20e1..462fa78` (3 commits).

verdict: **CLEAN** (one NON-BLOCKING coverage note — since ADDRESSED, see Monitor corroboration)

gate0: { suite: PASS, lint: PASS, types: N/A, tests_first: YES }

## Gate 0 — verbatim (run in-place, env `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare`)
- HEAD `462fa78`: **38 failed, 713 passed, 26 skipped**
- Parent `0fa20e1`: **38 failed, 700 passed, 26 skipped** (+13 = 7 writer + 6 endpoint new tests)
- **Parent↔HEAD failure-set diff: IDENTICAL** (0 net-new, 0 swap). The 38 are the documented pre-existing external-pack drift.
- `tests/test_criterion_writer.py` → **7 passed**; `tests/bff/test_criterion_endpoint.py` → **6 passed**.
- **RED-worktree** (`git worktree add /tmp/narr5_red 5269f6b`): the endpoint tests → **6 failed, all `AttributeError` (create_criterion_endpoint missing)** → GREEN at `462fa78`. RED→GREEN demonstrated. Worktree removed.
- Lint: ruff on the 4 touched files → All checks passed. Repo-wide 404==404 (pre-existing).
- Commit order: `6ee408d` (writer+tests) → `5269f6b` (endpoint tests RED) → `462fa78` (endpoint GREEN). Tests-first satisfied.

## The 4 questions (governance focus)
1. **Writer correct AND invariant preserved, not weakened — YES.** `harness/criterion.py:91` tier:core gate (NonCorePackError, tested `:120`); `:98` owner ∈ production_judges (UnknownOwnerError); `:103` dup (DuplicateCriterionError). **All validation BEFORE any `write_text` (`:113`)** — the 3 rejection tests capture `snap_before` + assert `_snapshot == snap_before` after the raise (non-vacuous: no-write-on-rejection). Splices `tiers` + `lenses` (+ `tier1_owners` only for T1). The gate `admissibility.gradeable_flags_outside_snapshot` is **0-diff**; the writer enters codes THROUGH it (a never-created gradeable code STILL 422s, `test_criterion_endpoint.py:172`), not around it.
2. **Endpoint atomic + audited — YES.** `app.py:1859` splice → `:1862` overlay append under `_validate_ontology` → ONE AuditRecord `Target(type="criterion")`. **Atomicity wired + empirically forced:** the critic pre-seeded an unblessed overlay flag → endpoint raised AND the snapshot was byte-restored (spliced code not stranded). 409 dup / 422 others. Tier-aware 422 (`_gradeable_offender_detail`, `app.py:1742`): core→create_gradeable_criterion, pro→backend re-snapshot, Exception→core fallback. No existing test pinned the old message; healthcare-default (pro) still gets the backend message; 0 existing tests broke.
3. **MOAT / scope / no engine edit — CLEAN.** 0-diff vs `0fa20e1`: `runtime/council/`, `harness/grounding.py`, `harness/pack.py`, `harness/admissibility.py`, `verification/spec.py`, AND `apps/bff/agent/` (no new SDK tool → NARR-5-CRIT-b deferral honored, tool count unchanged). Scope = exactly `apps/bff/app.py` + `harness/criterion.py` (new) + 2 test files (611+/8-). No `packs/` repo-source mutation in the 3 commits (tests mutate a tmp copy of `packs/_core` only).
4. **Honesty — no over-claim.** Nothing claims a healthcare/case-10/tier:pro flip is enabled (grep empty); the writer docstring states tier:pro snapshots are backend-derived, not self-authored. Round-trip preserves all 6 snapshot keys (deepcopy + targeted mutation; no silent drop).

## Finding
- **[NON-BLOCKING → ADDRESSED]** No ENDPOINT-level test exercised the atomic-rollback path (the writer A7 unit test + the critic's manual repro covered it). The critic proposed `test_atomic_rollback_on_ontology_failure`. **Monitor added it** (`tests/bff/test_criterion_endpoint.py`, commit `91d9edf`): pre-seed an unblessed overlay flag → endpoint raises AND `_snapshot(pack) == before` AND GOOD_CODE absent. 7/7 endpoint tests green.

## New seam
`harness/criterion.py` is the FIRST sanctioned writer above the "never hand-edit the snapshot" invariant — `splice_gradeable_criterion` + `restore_snapshot`, gated to tier:core. Governance-load-bearing: future packs must keep the tier:core gate intact (a tier:pro pack must never reach the splice). `POST /v1/criterion` is the live writer endpoint with the `criterion` audit target.

## Bottom line
A faithful, honestly-scoped NARR-5-CRIT-a. Gate 0 green, byte-identical failure set (0 net-new/0 swap), RED→GREEN via worktree, ruff clean. The four governance hazards are each closed: the labels-true-by-construction gate is byte-untouched and the writer enters codes through it (a never-created code still 422s); the rollback is wired AND was forced end-to-end with a clean restore; no snapshot key is dropped (all 6 preserved); no repo-source mutation swept in; nothing over-claims a healthcare/case-10 flip — the cycle ships only the tier:core WRITER. Moat (council/grounding/pack/spec) 0-diff, no new agent tool. **CLEAN.**

---

## Monitor corroboration
- MOAT + grounding.py + pack.py + spec.py + `apps/bff/agent/` **0-diff** vs `0fa20e1` re-confirmed; failure-set diff parent↔HEAD IDENTICAL (38==38).
- The NB coverage note is **discharged** (the endpoint-level atomic-rollback test, `91d9edf`, 7/7 green).
- Governance HARD-GATE **satisfied** — owner signed off on the first snapshot writer (2026-06-21); the independent cold critic ran Gate 0 + forced the rollback + returned CLEAN; the gate is preserved, not weakened.
- **NEXT:** NARR-5-CRIT-b (the `create_gradeable_criterion` SDK-MCP tool over `POST /v1/criterion`, A-SAFE re-proof, tool count 20→21) · then the case-10 GOVERNED flip on a tier:core pack (mint DISSENT_ERASURE the sanctioned way + register value_presence there + grade). Open: S-BS-FAUTH4b-1 (spec §123 two-mode lock).
