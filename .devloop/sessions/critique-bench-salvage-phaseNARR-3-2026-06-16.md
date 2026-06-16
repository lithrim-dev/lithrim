# Critique — bench-salvage NARR-3 (deterministic narrative floor executors + ATTACH-VALIDATORS)

> **HARD GATE — fresh cold critic** (spawned with no implementation context; agent `a395280677970c2d3`). Mandate: Gate 0 (supreme) → 4 spec-fidelity questions → adversarial verification of the moat freeze + the named claims. Edited nothing; ran tests in scratch worktrees (removed).
>
> **Verdict: NON-BLOCKING FINDINGS.** Gate 0 green; the NARR-3 driver contract (A1–A6) is met; the moat is byte-frozen; the two highest-risk items (the clean-case reshape + the headline-flip coverage) resolved favorably. One material spec-ambiguity seam opened (`S-BS-NARR3-3`) that will bite NARR-4.

Date: 2026-06-16 · Cycle commits: parent `582ee94` → `0b2b58d` (6 commits) · Monitor 7-item audit: CLEAN (independently re-run).

---

## Gate 0 — supreme, re-run cold from clean state (parent parity via scratch worktrees)

- **pack=healthcare (the conftest-green regression gate): `3 failed, 586 passed, 8 skipped` → 0 NEW.** The 3 are EXACTLY the documented pre-existing set: `tests/test_pack_dist.py::test_a2` (fails identically at parent — needle-hits are NARR-1/2 `_provenance.note` prose, not NARR-3) + the 2 observation order-pollution tests (PASS in isolation, `2 passed in 0.01s`). Clinical floor + moat guards regression-clean: `tests/verification/ tests/test_6bclean_seam_guard.py tests/test_6bclean_attestation.py → 74 passed, 1 skipped`.
- **pack=narrative (targeted floor gate): `tests/test_narrative_floor.py → 8 passed`; `tests/test_narrative_pack.py → 3 passed`.** Full narrative run = 104 failures + 1 collection error, ALL pre-existing pack-activation (identical at parent 582ee94); none in NARR-3 files except the verification-test artifact in NON-BLOCKING #1.
- **Lint:** touched files (`floors.py`, `spec.py`, both test files) → `All checks passed!`. Full-repo `ruff check .` = 398 errors, identical count at parent (NARR-3 added 0).
- **Tests-first:** `git log` → `bb3759f test(...)` first; at that commit `floors.py` is absent + `spec.py` carries 0 new tool-names → all 8 tests FAIL. RED→GREEN non-vacuous.

## The 4 spec-fidelity questions

1. **Surface fidelity — CLEAN.** `_KNOWN_TOOLS` = 9 (6 prior + 3 new, disjoint); registry is real (rejects an unknown tool with `ValueError`). Tool-names match §4.3. `_REQUIRED_REFERENCE_KEYS` exactly the driver §2 shape. `VerificationResult` tri-state honored on all 3 tools; the `ground()` floor-dispatch contract (inject on `False`, surface on `None`, no-op on `True`) matched.
2. **Behavioral fidelity — CLEAN; the headline-flip challenge resolves favorably.** The SPEC §5 headline (`SILENT_DEGRADATION` PASS→BLOCK, end-to-end) is genuinely asserted in CI even under the conftest-green healthcare default — NOT skip-guarded into never running. The 3 in-process `ground()` flip tests (A4) skip under pack≠narrative, but **A5 (`test_narrative_floor_grades_under_pack_narrative`) is a subprocess test with NO skip-guard**: forces `pack=narrative`, loads the by-construction `narrative_jinn_silent_degradation` via `load_case`, runs real `ground()`, asserts `stage_verdict=="BLOCK"`, `verdict=="reject"`, `floor_block_count>=1`, `"SILENT_DEGRADATION" in active_codes`, `healthcare_reads==[]`. Confirmed RUNS+PASSES under pack=healthcare. All 4 example cases grade to their `expected_safety_flags` exactly.
3. **Out-of-scope intrusion — NONE.** 8 files = 6 deliverables + `tests/test_narrative_pack.py` (in-scope NARR-1→NARR-3 test-contract update: the `verification_contracts==[]` / `n_verification_contracts==0` invariants are superseded, commit body candid) + the session log. `spec.py` purely additive; `pack.json` = the single `"floors"` key.
4. **Spec ambiguity — ONE material seam (S-BS-NARR3-3).** LENGTH_VIOLATION's preamble-vs-whole-scene scope; the executor did not surface it.

## Adversarial verification of the named claims

- **MOAT byte-freeze — CONFIRMED NON-VACUOUS.** `git diff 582ee94 HEAD --` of all 5 moat files = EMPTY; all 5 exist + are real (compliance_council 119KB / signals 8KB / withstands 7.6KB / judge_metric 12.8KB / tools 45KB). `grounding.py` (the floor dispatch) is ALSO unchanged — the floor registers entirely via the pack.
- **spec.py additive-only — CONFIRMED.** 3 constants + 3 `_KNOWN_TOOLS` + 3 `_REQUIRED_REFERENCE_KEYS`; `__post_init__` + the 6 prior entries not in any diff hunk.
- **conforms=None never flips — CONFIRMED asserted** (`test_inconclusive_silent_degradation_never_flips` + the A3 unit on `{}` / missing-source / missing-finish_reason).
- **marker-targeted BRACKET_LEAK false-positive guard — CONFIRMED non-vacuous both directions:** A1 asserts `[READER FEELING: tense]` → `False` AND a legitimate lowercase `[it was faded]` → `True` (regex `\[[A-Z][^\]]*\]`).

## Adjudication — the clean-case reshape (commit `1877d71`): HONEST per-scene-contract correction, NOT bent-to-code

1. SPEC §4.2's `jute_transform` emits ONE case per scene. The original `narrative_jinn_exposure_clean` glued TWO scenes (`scene_ranger_arrival` 4 + `scene_mountain_road` 7 = 11 sentences under the splitter) — a genuine §4.2 violation, a NARR-1 authoring artifact.
2. The reshaped content is a faithful single real scene (`scene_ranger_arrival`, 4 sentences, source=enhanced) that the case transcript's beat references; the clean negative stays `expected_safety_flags: []` because a single in-band scene is genuinely length-clean (label true by construction).
3. The reshape corrected a real fidelity defect the floor exposed — not a dodge. **Caveat:** it works only because that scene happens to be exactly 4 sentences, which *masks* the real over-fire below.

## Findings

**NON-BLOCKING #1 — pack-activation artifact extends to a verification test.** Under pack=narrative, `tests/verification/test_grounding_floor.py::test_backward_compat_default_ontology_has_no_floor` now fails (bare `load_ontology()` resolves the narrative ontology, which NARR-3 made floor-bearing). PASSES under pack=healthcare (canonical). Not in the canonical green bar → route into `S-BS-NARR3-1`.

**NON-BLOCKING #2 → S-BS-NARR3-3 (NEW, material) — LENGTH_VIOLATION grades the WHOLE scene against a band defined for "the added preamble," and over-fires on real day-one data.** The case record carries no separate `preamble` field — only the full `clean_text` (§4.2 `response` → §4.1 `artifacts[0].content`); `floors.py:132` counts sentences over the whole subject (`grounding.py:530,555`). Empirically, **3 of the 4 real enhanced StoryWorld scenes** — `scene_mountain_road` (7), `scene_the_warning` (5), `scene_the_descent` (5) — grade as complete `stop`/`enhanced` generations get **FALSELY BLOCKED** with LENGTH_VIOLATION. The test corpus only uses `scene_ranger_arrival` (the one scene that fits), so the over-fire is invisible in the green bar — and is the unstated cause of the clean-case reshape. **NON-BLOCKING for NARR-3** (driver A2 only requires the tool to fire on crafted in/out-of-band inputs — it does; R2 declared the band a tunable; bounds are SME-pinnable; real-data calibration is explicitly NARR-4), but it WILL bite NARR-4 and needs the spec author to LOCK the definition.
- Proposed failing test (NARR-4): `test_real_enhanced_scenes_are_not_length_blocked` — load each `source=="enhanced"` scene from `storyworld_session.json` as a single per-scene case, grade through the narrative ontology, assert `verdict=="PASS"` for all (currently FAILS for mountain_road/the_warning/the_descent).

## Seams

- **`S-BS-NARR3-3` (NEW, medium, spec + `packs/narrative/floors.py:132` / the case record):** LENGTH_VIOLATION subject scoping — counts the whole `clean_text`, but the spec/ontology describe "the added preamble"; over-fires on ≥3 real enhanced scenes. Spec author must lock: (a) the case carries a separate preamble span the floor reads, OR (b) the spec redefines LENGTH_VIOLATION as whole-scene and re-pins the band (real scenes are 4–7 sentences). Carry into NARR-4 calibration.
- **Route into `S-BS-NARR3-1`:** the verification-test pack-activation failure (NON-BLOCKING #1).

## Disposition

The NARR-3 contract is met; Gate 0 is green on the canonical gate; the moat is byte-frozen; the two highest-risk items resolved honestly. **Cycle closes PROCEED-WITH-CAVEATS.** `S-BS-NARR3-3` is the one item the spec author (owner) should lock before NARR-4 — it is the difference between a floor that's right on crafted tests and one that's right on real Lenador data.
