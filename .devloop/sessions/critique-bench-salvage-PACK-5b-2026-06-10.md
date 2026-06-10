# Critique — bench-salvage PACK-5b (healthcare-realm-as-pack, layer 5b: the core-boundary finisher)

**Date:** 2026-06-10 · **Mode:** monitor 7-item audit + **HARD-GATE fresh critic** (isolated worktree `a5bec7f38933138d6`, no prior impl context)
**Build:** `d185b56..426914b` (6 atomic commits) on parent `362c041`; log `bbe806f`. Branch `bench-salvage/ws6c-dspy`, NOT pushed.
**Verdict:** **NON-BLOCKING [0 BLOCKING / 3 NB / 2 OQ] → CLOSE PROCEED-WITH-CAVEATS.**

---

## What landed
The last 4 clinical agent-type generators (hl7_adt / coding / scheduling / triage) + the `_pmh` scribe residual relocated **byte-verbatim** out of the core into `packs/healthcare/generators/` through the proven `load_pack_generators` interface; core `lithrim_bench/packs.py` thinned to a resolver (`_CORE_PACKS = {}`), `injectors/__init__.py` reduced to the generic base re-exports, and `synthesizers/` git-removed. This **finishes the core-boundary relocation**: `lithrim_bench/` now carries no relocatable clinical generation CODE — only the intentionally-frozen council remains (the 1b/2b endgame).

## Monitor 7-item audit — CLEAN
| # | Check | Result |
|---|---|---|
| 1 | Commits exist, tree clean | ✅ `d185b56..426914b` (6) + log `bbe806f`; clean; not pushed (no remote) |
| 2 | Files match driver D1–D7 | ✅ 23 `git mv` relocations + thin packs.py + base-only injectors + `test_pack_layer5b.py` + docs |
| 3 | Tests pass | ✅ `test_pack_layer5b.py` 10/10 (py3.12); relocation surface 51/51 (debuglithrim py3.10.15) |
| 4 | Scope held | ✅ council seam **0-delta**, generic base **0-delta**, no `runtime/`/`backends/`/docstring-scrub |
| 5 | User prefs | ✅ not pushed, **no foreign files** (dirty-index seam avoided), $0 offline |
| 6 | Session log shape | ✅ correct |
| 7 | Deviations justified | ✅ 2 APPROVED-AT-PLAN + 3 disclosed caveats |

## Fresh-critic crux checks — all 7 CONFIRMED (verbatim evidence in the agent return)
1. **Byte-verbatim moves** — every changed line across all 23 relocated files is an import (core→absolute, intra-pack→relative). (Critic caught + corrected its own shell word-split bug, then re-ran clean — honest method.)
2. **4 byte-identity gates — INDEPENDENTLY** (strongest evidence): cohort present in the worktree → regenerated the 4 corpora at `d185b56` (pre-move) vs HEAD (post-move) with a fixed `--generated-at`; **all 4 sha256-identical** (coding `9b3fc487…`, hl7_adt `fdbe1c11…`, scheduling `061412c7…`, triage `4fbb8c5e…`). Labels-true-by-construction survives the relocation across all 4 agent-types.
3. **FabricatedConsent-excluded invariant** — the comment + `SCHEDULING_INJECTORS` (PhiDisclosure-only) block moved byte-identical; `FabricatedConsentInjector` re-exported but in no pack's list. **Proven non-vacuous**: transiently adding it → `scheduling_v1` gate FAILED (`FABRICATED_CONSENT` appeared), then reverted.
4. **Boundary milestone** — `injectors/` = base-only, `synthesizers/` git-removed, `_CORE_PACKS == {}`, `active_packs()` yields exactly 5 recipes all `is` the pack's `PACKS[name]`.
5. **No core→pack leak** — AST: zero top-level `packs` imports in `lithrim_bench/`; the only ref is the lazy file-path load inside `_active_packs` (packs.py:55); `import lithrim_bench.packs` heavy-dep-free.
6. **`active_packs()` non-vacuous + fail-clean** — real module/5 recipes for healthcare; `FileNotFoundError` (not silent) for an unknown pack; `test_no_generators_pack_degrades` real (monkeypatches `generators: None` → recipe disappears, no core fallback).
7. **Generic framework 0-delta** — `base.py`/`encounter_spec.py`/`packager.py`/`synthea*` empty diff; `PackDefinition` class body byte-identical.

## Open-question resolutions (monitor)
- **OQ-1 (debuglithrim — A5 "green both envs") — RESOLVED by the monitor.** The critic couldn't run the openai/council env. The monitor ran it: the relocation suites are **51/51 green in py3.10.15**, and the FULL-suite failure set is **exactly the 2 pre-existing S-BS-96 observation guards** (`test_importing_observation_does_not_load_compliance_modules`, `test_default_run_pulls_no_heavy_deps`) — an `import`-isolation check **causally disjoint** from generation-code relocation. **debuglithrim 0-new — CONFIRMED.**
- **OQ-2 (committed baselines carry a machine-absolute `cohort_path`)** — inherited **S-BS-117**, not introduced by 5b. The 4 new baseline corpora widen S-BS-117's footprint; the cohort-gated gates pass byte-exact only in the main worktree (the driver explicitly accepted "judge by 0-new-at-parent"). Tracked under S-BS-117 for the follow-on; not a 5b blocker.

## Findings dispositions
- **NB-1 → opened S-BS-122 (low).** `lithrim_bench/packs.py:64-68` — the `active_packs()` **function docstring** still describes the 5a world ("the core's non-scribe recipes ⊕ … the scribe recipe absent … post-5a"). The module-level comment (41-46) was correctly updated; this one was missed. CODE is correct (`_CORE_PACKS == {}`, monitor-verified); only the prose is stale. Trivial follow-on; a 4-line docstring fix offered as a supplement.
- **NB-2 (intermediate-commit redness) — ACCEPTED.** C3 (`c85594d`) + C4 (`3a8ca85`) left `test_pack_layer5a.py`'s core-identity assertion RED (it asserted the 4 packs were core instances; broke when CODING_PACK left core in C3); fixed in C5 (`c61231d`). This is within the monitor's go-condition (per-commit greenness scoped to "each bundle's own pack-tests"); the assertion was *about the thing being moved*, so per-commit it was legitimately mid-flight. Final state fully green. Low-severity process note, not a defect.
- **NB-3 (ruff tally precision) — RECORDED.** The session log's "5 carried ruff violations" includes `value_mismatch.py` (F401), which is a PACK-**5a**-relocated file, not in the 5b diff. 5b's own byte-verbatim-move carries = **4** (`_hl7.py`/`_soap.py` UP035, `upcoding_risk.py`/`scheduling_transcript.py` F541). Immaterial to the 0-new verdict (whole-repo ruff 455 = 455 parent↔HEAD).

## Diagnose-before-edit — record corrections (monitor)
- **Observation-test path corrected.** The session log cites the guards at `tests/test_observation_pipeline.py`; the real path is `lithrim_bench/runtime/observation/tests/test_observation_pipeline.py`. Substance (2 pre-existing S-BS-96 guards) **CONFIRMED**; only the cited path was abbreviated.
- **ruff tally corrected** to 4 (see NB-3).

## Seams
- **Closed:** S-BS-120 (the `--generated-at` frozen-timestamp flag landed on `generate_pack.py`; critic-confirmed additive, default-None) · S-BS-121 (`_pmh` relocated to `packs/healthcare/generators/_pmh.py`; the 2 pack scribe synths flip to relative `._pmh`; critic-confirmed scribe-only, no core residual).
- **Opened:** S-BS-122 (low — NB-1 stale `active_packs()` docstring).
- **Scope grew:** S-BS-117 (the 4 new baseline corpora inherit the absolute-`cohort_path` property).

## The 4-question spec-adherence read (critic, cold)
- **(a) Surface fidelity** — MATCHES §3/§6: `active_packs()` (5 pack-sourced, `_CORE_PACKS=={}`), the pack `__init__` exports (5 recipes + re-exported injectors/synths/helpers), `generate_pack.py --generated-at` (additive, default-None).
- **(b) Behavioral fidelity** — traced spec→test→impl for byte-identity×4, the `_CORE_PACKS=={}` resolver, and the S-BS-121 `_pmh` closure; all hold.
- **(c) Out-of-scope intrusion** — NONE. No council/compliance/judge/ontology/taxonomy/floors edits; the §5-forbidden `runtime/pipeline`/`backends` docstring scrub correctly NOT done.
- **(d) Spec ambiguity** — OQ-1 (resolved) + OQ-2 (inherited S-BS-117).

## Disposition
Clean by-construction relocation finisher. All 4 corpora byte-identical across the move (independently regenerated), the FabricatedConsent label-invariant proven non-vacuously protected, the boundary milestone met, no core→pack leak, generic base 0-delta, frozen council untouched, 0-new both envs (debuglithrim monitor-confirmed). **CLOSE PROCEED-WITH-CAVEATS.** No proof capsule (offline/$0 mechanism; A2 proven $0 by byte-identity — no A-LIVE attestation this cycle). The 1b/2b council un-freeze remains the deferred endgame (explicit authorization).
