# Critique — bench-salvage PACK-2b (council owner-map un-freeze, layer 2b)

**Date:** 2026-06-11 · **Mode:** monitor 7-item audit + **HARD-GATE fresh critic** (isolated worktree `acd21d7a9dc830223`, no prior impl context)
**Build:** `833cfc8..d996cf7` (6 commits) on parent `7fa8d91` (= `92f1689` code-wise); freeze baseline `acc4973`. Branch `bench-salvage/ws6c-dspy`, NOT pushed.
**Verdict:** **NON-BLOCKING [0 BLOCKING / 0 NB / 1 OQ] → CLOSE PROCEED-WITH-CAVEATS.** (The cleanest verdict of the un-freeze endgame.)

---

## Milestone — the frozen council's clinical DATA is fully pack-resolved
PACK-2b flips the Tier-1 owner-map (`_TIER1_OWNERS`, 8 entries) to resolve FROM the active pack's `taxonomy_snapshot.json` `tier1_owners` via the same inline-`__import__` carve-out PACK-1b used for the tier sets (`pack_tier1_owners()`). With **1b (taxonomy) + 2b (owners)** done, the FROZEN `compliance_council.py` reads all its clinical *data* from the pack. What remains hardcoded is **not clinical data**: the `CouncilModel` roster (infra-tangled — identity already externalized as `snapshot.production_judges`) and `LENS_BY_ROLE` (the moat's authority) — both deferred as an optional "2c", neither blocking the clinical-data completion.

## Monitor 7-item audit — CLEAN
| # | Check | Result |
|---|---|---|
| 1 | Commits exist, tree clean | ✅ `833cfc8..d996cf7` (6); clean; not pushed |
| 2 | Files match driver D1–D6 + regression fix | ✅ 9 code files + log |
| 3 | Tests pass (canonical crux) | ✅ core 36p/6skip; `[council]` 73p (oracle + lens⊆owners + guards + regression-fixed 1b subprocess) |
| 4 | Scope held — **frozen seam** | ✅ council = **exactly 3 hunks** vs `acc4973`; roster/`_apply_consensus`/LENS/moat/ontology **0-delta**; no foreign |
| 5 | User prefs | ✅ pathspec-only, not pushed, $0 |
| 6 | Session log shape | ✅ correct + 3 deviations, S-BS-124 closed, S-BS-125 opened |
| 7 | Deviations justified | ✅ APPROVED-AT-PLAN + APPROVED-MID-CYCLE (regression) + CITATION-DRIFT |

## Fresh-critic crux checks — all 8 CONFIRMED (verbatim evidence in the agent return)
1. **Exactly 3 carve-out hunks** vs `acc4973` (prompts-dir + tiers + owners); roster + `_apply_consensus` (547-line body) + `self.models` + `LENS_BY_ROLE` byte-identical (the only keyword hit is a comment).
2. **Value preservation** — 4-way set equality: `acc4973` literal == snapshot `tier1_owners` == live council == `load_taxonomy().tier1_owners` (8 codes, per-key identical); `:2071` one-strike read byte-unchanged.
3. **Behavior 0-delta** — the consensus oracle (`test_consensus.py`) + the lens⊆owners invariant (`test_trio_dspy.py`) green (38p), both unchanged in the diff.
4. **Guard + S-BS-124 hardening — non-vacuous AND the closure works.** All 4 revert/unauthorized directions FAIL; the comment/blank exemption PASSES; and **the critic reconstructed the 1b guard at `92f1689` and proved the smuggled-code-line PASSED pre-2b but FAILS at HEAD** — the residual was real and is now closed.
5. **The regression fix (`9813e2c`) — CONFIRMED CORRECT by reproduction.** `council_roster()` is the council's pack-*independent* validation identity (used by `assert_judges_known`/`assert_pack_judges_consistent` at council import); `source_message_judge` is owner-only (not in the `CouncilModel` names), so the roster's owner-leg needs the canonical identity. The critic checked out pre-fix `a0edcfa` → the 3 subprocess tests FAIL with the exact `PackConsistencyError`; HEAD → pass. The carve-out's bare `pack_tier1_owners()` correctly follows the *active* pack (the real 2b flip). No deeper issue.
6. **S-BS-125 asymmetry — principled.** Post-1b `council_known_codes()` is a vacuous self-check (active is harmless), so only `council_roster()` needed a fixed identity. Low/revisit-at-2c is the right severity.
7. **No 3rd owner-literal AST reader** — exactly 2 re-points (`council_roster` owner-leg + `seed_ontology`); `snapshot_taxonomy.py` reads the *upstream backend*, correctly unchanged.
8. **2b-deferred + moat byte-frozen** — `judge_metric.py`/`signals.py`/`withstands.py`/ontology/healthcare-snapshot all 0-delta vs parent (no re-snapshot); roster + `_apply_consensus` byte-frozen; surviving freeze guards green.

## Green-bar (0-new-at-parent)
Core (py3.12) 46p/9skip/0fail. `[council]` (debuglithrim) 91p/**2fail** — both (`test_S_BS_72_provenance_blob`, `test_MOAT_EXHIBIT_gate_flips`) are the **S-BS-117/119** missing-fixture class (`load_case(...)` → None in a bare worktree), failing **identically at parent `7fa8d91`** (80p/2fail, same 2). **0-new → green.** ruff: authored files clean; frozen council 96→96 (the `Dict[str,set]` UP006 deliberately preserved for symbol-shape 0-delta).

## Seams
- **Closed:** **S-BS-124** (the carve-out guard residual) — the executor's per-line hardening (every added *code* line in an authorized hunk must carry a marker; comments/blanks exempt); critic-proven non-vacuous + that it closes the real residual.
- **Opened:** **S-BS-125** (low) — the `council_roster()` (canonical `DEFAULT_PACK`) vs `council_known_codes()` (active) pack-resolution asymmetry. **Sharpened by the critic's OQ-1: at the 2c/multi-pack cut, BOTH halves need revisiting** — `council_roster()` would validate a 2nd real judge-bearing pack against healthcare's roster (wrong), AND `council_known_codes()`'s vacuous self-check should become a real cross-pack check. The 2c driver must inherit both halves, not just the roster.
- **Carried:** S-BS-113, S-BS-117/118/119, S-BS-96.

## Diagnose-before-edit — the regression-fix claim, verified
The APPROVED-MID-CYCLE deviation (commit `9813e2c`) claimed `council_roster()` must read `DEFAULT_PACK`. The critic INDEPENDENTLY reproduced the regression (pre-fix `a0edcfa` → `PackConsistencyError: pack '_tiers_fixture' carries council-role prompt(s) for unknown role(s): ['source_message_judge']`) and confirmed the root cause (`source_message_judge` is owner-only; coupling the validation identity to the active pack dropped it under the sentinel fixture). The fix restores exact pre-2b behavior. CONFIRMED, not inferred.

## The 4-question read (critic, cold)
- **(a) Surface fidelity** — `pack_tier1_owners()` mirrors `pack_tiers()`; the 2 AST re-points + the 3-carve-out guard + the S-BS-124 hardening match driver §3/§6.
- **(b) Behavioral fidelity** — value-preservation, owners-follow-the-pack (fixture sentinel subprocess), roster/LENS/moat frozen all trace spec→test→impl.
- **(c) Out-of-scope intrusion** — NONE (the `test_pack_layer2.py` touch is docstring-only; no roster creep, no LENS edit).
- **(d) Spec ambiguity** — the canonical-vs-active asymmetry, resolved + logged as S-BS-125 / OQ-1.

## Disposition
The owner-map un-freeze is value-preserving, behavior-0-delta, and the self-caught regression fix is correct (reproduced). The guard is non-vacuous and the S-BS-124 residual is genuinely closed. 2b-deferred + the moat are byte-frozen. **CLOSE PROCEED-WITH-CAVEATS.** No proof capsule (offline/$0 mechanism; no A-LIVE). **The clinical-data un-freeze of the frozen council is COMPLETE (1b taxonomy + 2b owners).** Remaining (optional, non-clinical-data): the roster un-freeze (infra-aware) + `LENS_BY_ROLE` (moat authority) = a future "2c" — the user directs whether to pursue it.
