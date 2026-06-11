# Fresh-critic critique — bench-salvage PACK-2c (council ROSTER + LENS_BY_ROLE un-freeze)

**Date:** 2026-06-11 · **Mode:** FRESH CRITIC (HARD GATE, `isolation: worktree`, no implementation context) · **Verdict:** PASS
**Critic agent:** `a0034f63d8cf8a259` · **Commits:** `0c4eab8..6e09c44` (build `7eeaee0..6e09c44`)
**Result line:** 0 BLOCKING / 3 NON-BLOCKING / 1 OQ — PASS the HARD GATE.

The critic read the spec/driver + `tests/_seam_freeze.py` cold, diffed independently against `acc4973`, ran the full suite + targeted probes, and adversarially attacked the freeze guard. It did NOT trust the session log.

## The 4 questions (cold)
- **Q1 Surface fidelity — PASS.** `pack_lenses()`/`pack_production_judges()` (`harness/pack.py:137-168`) mirror the `pack_tier1_owners` precedent exactly (same resolve/read, frozenset coercion, ungated stdlib-only). Snapshot `lenses` block well-formed, ⊆ taxonomy, **set-equal** to the old `judge_metric.py` constants (verified programmatically).
- **Q2 Behavioral fidelity — PASS.** (a) Resolved `LENS_BY_ROLE` == acc4973 values; roster identity+order == acc4973; the `CouncilModel` deployment literals **byte-identical** to acc4973 (only the tuple renamed `models`→`_ROLE_DEPLOYMENT_ALL` + indexed by pack identity); `council_roster()` AST-collect still yields all 5 canonical roles. (b) `signals.py`/`withstands.py` **byte-frozen** (`git diff 7eeaee0..HEAD` empty); the gate reads the lens by-VALUE membership → pack-resolved equal frozensets behavior-identical. (c) `test_pack_layer2c.py` runs a REAL subprocess with `LITHRIM_BENCH_PACK=story_audit`, asserts roster==`[risk,policy]` AND lenses==story AND `!=` healthcare — airtight, not vacuous. 12/12 pass.
- **Q3 Out-of-scope — CLEAN.** Exactly the 17 driver files; no foreign working-tree files (apps/shell, journeys/) swept in; council MECHANISM untouched; v1 `else` roster byte-frozen.
- **Q4 Judgment calls — honestly documented** (OQ-1 v2-only, OQ-3 carry-over, OQ-4 derived refs, S-BS-125 re-scope).

## HARD-GATE adversarial probes (all held)
1. **Freeze guard:** exactly 4 carve-outs; real tree passes; REVERT fails; marker-LESS smuggled line fails — critic reproduced all three independently.
2. **Identity↔deployment split:** pack supplies only identity strings + lenses, never provider/Azure-id; A8 fail-clean (`behavior_judge` ∉ `_ROLE_DEPLOYMENT` → KeyError naming the judge) genuinely exercised by `_nondeployable_fixture`.
3. **v1 path:** honestly disclosed as frozen/non-decoupled (the decoupling claim is v2-scoped).
4. **S-BS-125 re-scope:** sound (`council_roster()` = canonical *capability universe*; packs subset-validate; re-pointing would break story_audit's prompt reuse) and tripwired.
5. **Suite (critic re-ran):** 2 failed / 614 passed / 3 skipped — both failures the pre-existing S-BS-96 observation guard pollution (confirmed: parent `7eeaee0` has 3 failures incl. a byoc flake; both observation tests pass in isolation at parent). **0 new** (one fewer than parent). `ruff check` clean on all non-frozen touched files.

## NON-BLOCKING findings (3)
1. **Marker-substring residual in the freeze guard** (`_seam_freeze.py:237-244`). A line that *contains* an authorized marker substring (e.g. `_ROLE_DEPLOYMENT = __import__("os").system(...)`) PASSES the per-line check. INHERENT to the S-BS-124 marker design (it closed the marker-LESS hole, not the marker-bearing one); **not a regression** — the same guard protects 1b/2b. Docs correctly claim only "marker-LESS fails." → tracked as **S-BS-127** (low).
2. **A8 fail-clean is a bare `KeyError`**, not a custom surfaced error (driver D6 said "surfaced error"). The KeyError names the non-deployable judge (test asserts), so traceable; a `CouncilDeploymentError` would be cleaner. Acceptable judgment call. → noted (low, cosmetic; not separately seamed).
3. **`judge_metric.py` + `_seam_freeze.py` fail `ruff format --check`** on PRE-EXISTING lines (identical at parent); reformatting = a §4-forbidden drive-by. The frozen council's 96 ruff errors are likewise pre-existing/exempt-by-precedent. Honestly disclosed in the SPEC.

## OPEN QUESTION (1)
1. `test_pack_layer2c.py` top-level imports `compliance_council`/`judge_metric`, making it an *additional* polluter of the `openai not in sys.modules` observation guard (S-BS-96). Pre-existing pollution, doesn't change the gate — but if S-BS-96 is ever fixed via test isolation, this new file is in scope. → folded into the S-BS-96 note.

## Disposition
PASS. PACK-2c lands PROCEED-WITH-CAVEATS → CLOSED. The strangler-fig decoupling endgame is complete: the frozen council reads ALL its domain content (taxonomy + owners + lenses + roster identity) from the active pack; the second-pack subprocess proof makes "completely decoupled (v2 path)" a CONFIRMED claim, not INFERRED. S-BS-125 RE-SCOPED with tripwire (not closed); opened S-BS-127 (guard marker-substring residual, low). CITATION-DRIFT (driver under-enumerated 2 frozen-seam pins) = monitor-owned, S-BS-123-class.
