# HANDOFF — bench-salvage — NARR-3 closed → NARR-4 (2026-06-16)

> **For the next session.** The **narrative-eval wedge** now has its grade-time anti-circularity floor.
> **NARR-3 (the 3 deterministic floor executors + ATTACH-VALIDATORS) is CLOSED PROCEED-WITH-CAVEATS**
> (HARD GATE; fresh cold critic NON-BLOCKING + monitor audit CLEAN). Next is **NARR-4** (the frontend
> demo + multi-model council on real Lenador data) — but **`S-BS-NARR3-3` is a NARR-4 precondition.**
> **Resume:** `/devloop-resume bench-salvage`, then read `docs/specs/SPEC_NARRATIVE_EVAL.md` + this doc.

---

## What just landed (NARR-3 — the floor codes that make narrative grading honest)

| Commit | What |
|---|---|
| `bb3759f` | **test-RED** — `tests/test_narrative_floor.py` (A1–A6); at this commit `floors.py` + the 3 tool-names are absent → 8 failed (genuine RED) |
| `ed99e27` | **`lithrim_bench/verification/spec.py`** — the ONE owner-chosen (Option A) additive core edit: +3 tool-names to `_KNOWN_TOOLS`/`_REQUIRED_REFERENCE_KEYS` (6 prior + `__post_init__` byte-unchanged) |
| `f8e60f3` | **`packs/narrative/floors.py`** (NEW) — `BracketLeakTool`/`LengthViolationTool`/`SilentDegradationTool` + `FLOOR_EXECUTORS` (pure-stdlib `in_process`) + `pack.json` `"floors"` key |
| `1877d71` | **`packs/narrative/ontology.json`** `verification_contracts` (3 floor decls) + 3 by-construction violation cases + the honest clean-case reshape + the 2 superseded NARR-1 test invariants |
| `24c72fc` | Gate-0 corrections — needle-scrub `floors.py` docstring (test_a2) + pack-guard the 3 in-process A4 flip tests |
| `0b2b58d` | the NARR-3 session log |

**The proof (SPEC §5 day-one headline):** `SILENT_DEGRADATION` — a scene that hit `content_filter` and silently fell back to `source: baseline` yet was shipped as final — is caught **deterministically** and flips a clean council PASS→**BLOCK**→`reject`. Asserted NON-VACUOUSLY in the canonical green bar via the A5 subprocess (`tests/test_narrative_floor.py:395`, no skip-guard; the critic confirmed it RUNS+PASSES under pack=healthcare). All 4 example cases grade to their `expected_safety_flags` exactly. **Honest-Δ** — a defect invisible in the finished PDF, caught by the floor.

**The architecture (the correction the NARR-2 handoff needed):** the floor codes register in the active pack's **`FLOOR_EXECUTORS`** (the inject-a-BLOCK direction), merged by `floor_executors()` (`harness/grounding.py:386-390`) — **NOT** `_CONTRACT_EXECUTORS` (the SUPPRESS registry the handoff wrongly cited). The floor runs in `ground()` downstream of the frozen council. **MOAT byte-frozen** (compliance_council/signals/withstands/judge_metric/tools.py + `grounding.py` itself = 0-diff). The only core touch is the additive `spec.py` registration (the CLOSED `_KNOWN_TOOLS` rejects an unregistered `contract_type`; this is the known design-debt the owner accepted under Option A — Option B, a pack-extensible registry, was NOT chosen).

**Gate 0:** healthcare (canonical gate) **3 failed / 586 passed / 8 skipped = 0 new** (the 3 are the documented pre-existing set); narrative-floor tests 8/8; ruff clean on touched files; tests-first RED→GREEN demonstrated.

---

## ⚠️ NARR-4 PRECONDITION — `S-BS-NARR3-3` (the one thing to fix first)

**`LENGTH_VIOLATION` over-fires on real data.** It counts sentences over the WHOLE scene (`claim.subject = artifacts[0].content`, `floors.py:132`), but the spec §4.3 / ontology define it for **"the added preamble"** (3–4 sentences). The eval-case record carries no separate `preamble` span — only the full `clean_text`. The critic empirically FALSE-BLOCKED **3 of the 4 real enhanced StoryWorld scenes** (`scene_mountain_road` 7, `scene_the_warning` 5, `scene_the_descent` 5). It is invisible in the green bar only because the test corpus uses the one scene that fits (and it is the unstated cause of the otherwise-honest clean-case reshape). **Before NARR-4 grades real Lenador scenes, the spec author must LOCK** one of:
- (a) the eval-case carries a separate `preamble` span (the AI-added text) that `LengthViolationTool` reads, OR
- (b) the spec redefines `LENGTH_VIOLATION` as whole-scene and re-pins the band (real scenes are 4–7 sentences).

Critic's proposed failing test (write it in NARR-4): `test_real_enhanced_scenes_are_not_length_blocked` — load each `source=="enhanced"` scene from `storyworld_session.json` as a single per-scene case, grade, assert `verdict=="PASS"` for all (currently FAILS for 3 of 4).

---

## What's next — NARR-4 (the visceral end-to-end demo)

Per `SPEC_NARRATIVE_EVAL` §8 cycle 4 + §6 P1: the **frontend demo** on real Lenador data with the **Claude/GPT/Llama multi-model council** (the judge-layer codes `BODY_CONTRADICTION`/`MODE_INAPPROPRIATE`/`TONE_INFIDELITY`/`PERSONALIZATION_MISS` assigned across models) layered over the now-shipped deterministic floor. **Order of work:** (1) lock + fix `S-BS-NARR3-3` (above) so the floor is right on real data; (2) the `S-BS-NARR2-1` D-C bridge (make ingested cases gradeable through `load_case`/the picklist — the NARR-2→NARR-4 bridge); (3) the multi-model council + the frontend surface. The visceral two-domain demo (narrative now; FHIR reuse as P2).

## Open seams (NARR-3)
- **`S-BS-NARR3-3`** (medium, **NARR-4 precondition**) — LENGTH_VIOLATION preamble-vs-whole-scene scope; over-fires on real scenes. **Spec-author lock required.** (see above)
- **`S-BS-NARR3-1`** (medium, `conftest.py:237-256`) — the conftest pack-gate keys on healthcare-discoverable vs bare-CE, never the active pack, so the full suite can't run green under the canonical narrative env (~104 pre-existing + `test_grounding_floor.py::test_backward_compat_default_ontology_has_no_floor` now joins under pack=narrative since the narrative ontology became floor-bearing — pack-activation artifact, canonical pack=healthcare gate clean). Generalizes S-BS-NARR2-4. A conftest import-isolation + narrative-active hygiene cycle settles it.
- **`S-BS-NARR3-2`** (low, `test_pack_dist::test_a2`) — `test_a2`'s naive needle-scanner flags the narrative pack's own "needle-free (no HIPAA/patient/…)" DISCLAIMER prose (pre-existing; floors.py needle-scrubbed; 2 flagged lines, same as parent). A test-a2 refinement (exempt negated/disclaimer prose) settles it.
- Carried open from NARR-2: **`S-BS-NARR2-1`** (the D-C corpus-gradeable bridge — NARR-4), **`S-BS-NARR2-3`** (bridge→scene stub, P1).

## Standing prefs (unchanged)
No autostart (`:3031` not needed for the floors — pure-stdlib `in_process`) · no push without owner approval (branch `bench-salvage/ws6c-dspy`, **NOT pushed**) · pathspec-only atomic commits · tests-first (RED before code) · canonical env `LITHRIM_BENCH_PACK=healthcare LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare PYENV_VERSION=debuglithrim` for the green bar (and `LITHRIM_BENCH_PACK=narrative` for the targeted floor tests) · diagnose-before-edit · honest-Δ / BYO-key $0 first · MOAT byte-frozen.

## First move (next session)
1. Read this doc + `docs/specs/SPEC_NARRATIVE_EVAL.md` (§4.1/§4.3/§5/§8 NARR-4) + the NARR-3 critique (`.devloop/sessions/critique-bench-salvage-phaseNARR-3-2026-06-16.md`).
2. **LOCK `S-BS-NARR3-3`** with the spec author (preamble-vs-whole-scene) — this is the gate to a floor that's right on real data.
3. Read `lithrim_bench/harness/grounding.py:506-681` (the floor dispatch) + `packs/narrative/floors.py` (what shipped).
4. `/devloop-expand-driver bench-salvage NARR-4` (author from the spec; re-grep every anchor; fold S-BS-NARR3-3 + the S-BS-NARR2-1 bridge into the deliverables).
