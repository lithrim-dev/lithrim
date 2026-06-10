# Critique — bench-salvage PACK-1b (council taxonomy un-freeze, layer 1b)

**Date:** 2026-06-10 · **Mode:** monitor 7-item audit + **HARD-GATE fresh critic** (isolated worktree `aeb96d98f752fc53f`, no prior impl context)
**Build:** `856deba..728c5fb` (6 commits) on parent `604e17e` (= `75507a2` code-wise); freeze baseline `acc4973`. Branch `bench-salvage/ws6c-dspy`, NOT pushed.
**Verdict:** **NON-BLOCKING [0 BLOCKING / 2 NB / 2 OQ] → CLOSE PROCEED-WITH-CAVEATS.**

---

## What landed — the first substantive edit inside the frozen council seam
The FROZEN `compliance_council.py` now resolves its 3 tier sets (`TIER_1_NEVER_EVENTS`/`TIER_2_HIGH_RISK`/`TIER_3_MEDIUM`) **from the active pack's `taxonomy_snapshot.json`** via the PACK-2 inline-`__import__` carve-out (`pack_tiers()`). The pack snapshot is now the single source of truth; the 1a one-way ⊆ gate became a self-consistency no-op; the equivalence is re-pinned by a new `[council]`-env test. **Behavior is 0-delta — same 19 values, different source.** This is the cleaner half of the council-un-freeze endgame; 2b (roster/`_TIER1_OWNERS`/`LENS_BY_ROLE`) remains.

## Monitor 7-item audit — CLEAN
| # | Check | Result |
|---|---|---|
| 1 | Commits exist, tree clean | ✅ `856deba..728c5fb` (6); clean; not pushed (no remote) |
| 2 | Files match driver D1–D6 + S-BS-123 fix | ✅ 13 in-scope files |
| 3 | Tests pass (canonical crux) | ✅ core 27p/3skip; `[council]` 33p (equivalence + seam guards + seed regression) |
| 4 | Scope held — **frozen seam** | ✅ council = **exactly 2 hunks** vs `acc4973` (taxonomy carve-out + the pre-existing prompts-dir); **0** `_TIER1_OWNERS`/`CouncilModel`/`_apply_consensus`/`LENS_BY_ROLE` lines; moat/LENS/dspy/ontology/snapshot 0-delta vs parent |
| 5 | User prefs | ✅ pathspec-only, not pushed, $0 offline |
| 6 | Session log shape | ✅ correct + 3 deviations logged |
| 7 | Deviations justified | ✅ 1 APPROVED-AT-PLAN (A3i) + 2 CITATION-DRIFT (incl. S-BS-123) |

## Fresh-critic crux checks — all 8 CONFIRMED (verbatim evidence in the agent return)
1. **Exactly 2 authorized hunks** vs `acc4973` (taxonomy + prompts-dir, both marker-bearing); `KNOWN_TAXONOMY_CODES` union line unchanged; no 2b/moat symbols.
2. **Value preservation (the safety claim)** — reproduced in `[council]`: `council-resolved TIER_1/2/3 + KNOWN == acc4973 literals == snapshot == load_taxonomy().known_codes == 19`.
3. **Guard non-vacuous BOTH directions** — induced all 3 failure modes (unauthorized line / revert taxonomy carve-out / revert prompts carve-out) + control passes. The disclosed residual (malicious line inside a marker-bearing hunk passes) is **parity with the PACK-2 guard** (the critic read the prior guard at `604e17e` — the bar is not lowered; 1b *adds* a revert-detector the old guard lacked).
4. **S-BS-123 — closed.** Independent repo-wide re-grep → the tier-literal AST-reader set is **exactly two** (`harness.pack.council_known_codes` + `scripts/seed_ontology.parse_tiers_and_owners`), **no 3rd** (`council_roster()` reads only the still-literal `_TIER1_OWNERS`/`CouncilModel`). Seed fix tier-output-neutral (TIER diffs = 0); committed ontology files 0-delta; `test_ws2` green.
5. **2b + moat byte-frozen** — `signals.py`/`withstands.py`/`judge_metric.py`/`judges_dspy.py`/ontology/snapshot all 0-delta vs parent `604e17e`; surviving freeze guards green.
6. **Subprocess non-vacuity** — a fresh interpreter under `LITHRIM_BENCH_PACK=_tiers_fixture` resolves `KNOWN_TAXONOMY_CODES == {sentinels}`, disjoint from the 19 → the council genuinely follows the pack. Fixture inert (discovery is active-pack-only; nothing iterates `packs/*`).
7. **No import cycle + heavy-dep-free** — `import lithrim_bench.harness.pack` pulls no `openai`; `pack_tiers()` reads the snapshot directly (no `load_taxonomy()` → no gate re-entry).
8. **Behavior 0-delta** — consensus oracle (`test_consensus.py`) 20p unchanged; no tier-set mutations (grep-empty); DSPy `sorted(TIER_*)` prompt byte-identical.

## Green-bar reconciliation (0-new-at-parent)
The critic's bare worktree showed 3 `[council]` failures (`test_S_BS_72_provenance`, `test_MOAT_EXHIBIT_gate_flips`, `test_consensus_decision_flips_with_validator_disprove`) — all `openai.OpenAIError: Missing credentials` **live-key** tests, **identical at parent `604e17e`** (critic verified by checking out parent in its isolated worktree). These are the same tests that **passed** in the monitor's credentialed canonical run (the 33-passed). Consistent: live-key tests pass in the credentialed main tree, fail-identically-at-parent in a bare worktree (the S-BS-117/119 caveat). The freeze-guard tests pass in both. **0-new at parent — green.** ruff: authored files clean; frozen council 96→96 (pre-existing legacy typing, none in the carve-out range).

## Findings dispositions
- **NB-1 (informational, not a defect).** `signals.py`/`withstands.py` are ~200 lines diff vs `acc4973` but **0-delta vs parent `604e17e`** — the moat legitimately evolved (GROUND-FLOOR-1 era) between the council's UAP-3b freeze baseline `acc4973` and 1b's parent. The freeze comparison for the moat is correctly against parent; only the *council file* is pinned to `acc4973`. No action.
- **NB-2 → opened S-BS-124 (low).** The carve-out guard's residual (a malicious line inside an authorized marker-bearing hunk passes) is parity with PACK-2, not a new weakness — but it compounds as 2b relaxes the guard further. Tracked as a someday-hardening (assert the changed-hunk line-count/shape matches the carve-out's expected signature). Out of scope for 1b.
- **OQ-1 (→ S-BS-113).** Whether to wire `seed --check` into CI: it currently exits non-zero on the pre-existing S-BS-113 owner_roles drift, so wiring it now would red-bar on unrelated drift. Stays under S-BS-113.
- **OQ-2 (accepted).** `assert_pack_council_consistent` is now a cached self-consistency no-op (it preserves the fail-closed shape for a hypothetical non-active pack mismatch); the active-pack equivalence moved to the `[council]`-env test. Acceptable design; locus-shift noted.

## Seams
- **Closed:** **S-BS-123** (the driver-under-enumerated 2nd AST-reader; fixed in-cycle, output-neutral, critic-confirmed complete — no 3rd reader). *(This is a driver-citation correction the monitor owns; the §1.5 under-enumeration is logged at close per diagnose-before-edit.)*
- **Opened:** **S-BS-124** (low — the carve-out guard's inside-an-authorized-hunk residual; harden before/with 2b).
- **Carried:** S-BS-113 (the seed `--check` owner_roles drift, pre-existing), S-BS-117/118/119, S-BS-96.

## Diagnose-before-edit — record correction
The PACK-1b driver §1.5 named ONLY `harness.pack.council_known_codes` as the atomic-coupling landmine; `scripts/seed_ontology.py:parse_tiers_and_owners` was a **second** `ast.literal_eval`-of-the-tier-literals site the carve-out broke. The executor surfaced it (S-BS-123), fixed it as the natural completion of D3, and the critic independently confirmed the reader set is now complete (exactly 2, no 3rd). The driver citation is corrected in the canonical record.

## The 4-question read (critic, cold)
- **(a) Surface fidelity** — `pack_tiers()`/`pack_taxonomy_codes()` + the re-pointed `council_known_codes` + the renamed `assert_compliance_council_carveouts_only` match driver §3/§6.
- **(b) Behavioral fidelity** — value-preservation, council-follows-pack, 2b/moat-frozen all trace spec→test→impl.
- **(c) Out-of-scope intrusion** — NONE (the 13 files = D1–D6 + the S-BS-123 fix + caller re-points + log; clinical provenance preserved verbatim).
- **(d) Spec ambiguity** — OQ-1 (CI-wiring `seed --check`) + OQ-2 (the vacuous gate locus).

## Disposition
The first substantive frozen-council edit succeeded, **value-preserving**. The taxonomy source-of-truth is flipped to the pack; the relaxed guard stays non-vacuous; 2b + the moat are byte-frozen; the AST-reader coupling is fully closed; both envs 0-new-at-parent. **CLOSE PROCEED-WITH-CAVEATS.** No proof capsule (offline/$0 mechanism; no A-LIVE attestation). **NEXT = 2b** (the roster/`_TIER1_OWNERS`/`LENS_BY_ROLE` un-freeze — the meatier half, raising the "pack-resolve the moat's owner authority?" decision); its driver re-greps against 1b's changes when the user directs.
