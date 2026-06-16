# Critique — bench-salvage NARR-4 (demote `LENGTH_VIOLATION` out of the floor → the `policy_judge` lens)

> **HARD GATE — fresh cold critic** (spawned with no implementation context; agent `ac6fe5ce636fe0678`). Mandate: Gate 0 (supreme, re-run cold) → 4 spec-fidelity questions → adversarial verification of the moat freeze + the headline + the honesty of the example removal. Edited nothing; ran tests in scratch worktrees (removed).
>
> **Verdict: CLEAN.** Gate 0 green on both envs (0 NEW failures); the demote is purely subtractive and HONEST; the moat is byte-frozen; the headline (`SILENT_DEGRADATION`) is preserved; RED→GREEN reproduced non-vacuously from a checkout of the red commit. Two NON-BLOCKING observations (both pre-existing, neither owned by NARR-4).

Date: 2026-06-16 · Cycle commits: parent `591741d` (== `22bf3c6` code-identical, doc-only lock) → `7eba320` (5 commits) · Monitor 7-item audit: CLEAN (independently re-run).

---

## Gate 0 — supreme, re-run cold

- **Targeted floor gate** (`pack=narrative`): `pytest -q tests/test_narrative_floor.py tests/test_narrative_pack.py` → **14 passed, 0 failed.**
- **Regression green bar** (`pack=healthcare`, full suite): HEAD = **`3 failed, 587 passed, 10 skipped`**; parent `22bf3c6` = `8 failed, 578 passed`. **HEAD's 3 are a strict SUBSET of the parent's 8 → 0 NEW.** `test_pack_dist::test_a2_data_surface_is_clinical_free` fails identically at parent **in isolation** (needle hits `ontology.json:3` + `taxonomy_snapshot.json:4`, pre-existing NARR-1/3 prose, not clinical, not introduced by NARR-4). The 2 observation import-isolation tests PASS in isolation at both parent and HEAD (order-pollution). The parent's other 5 failures all PASS in isolation at HEAD — pollution-chain artifacts the NARR-4 test edits incidentally cleared. No real regression in either direction.
- **Tests-first / RED→GREEN non-vacuous:** `git log` order is `c009358 test — red` → `abcbaa9 feat — green` → … . The critic **checked out `c009358`** (source still parent-state) and ran the new tests: A1 `test_real_enhanced_scenes_are_not_length_blocked` FAILS for exactly `scene_mountain_road` (7), `scene_the_warning` (5), `scene_the_descent` (5) — all `BLOCK`/`['LENGTH_VIOLATION']`; `scene_ranger_arrival` (4, in-band) is NOT in the failure list → **non-vacuous**. A2 FAILS at RED (3 contracts incl. length). Both GREEN at HEAD.
- **Lint:** `ruff check` clean on all touched `.py`.

## The 4 spec-fidelity questions

1. **Surface fidelity — MATCH.** `packs/narrative/ontology.json` (valid JSON) now has exactly 2 `verification_contracts` (`bracket_leak`, `silent_degradation`), no `length_violation`; the LENGTH_VIOLATION flag (`gradeable:true, owner_roles:[], TIER_2`) + policy_judge question ordinal 2 ("preamble") UNTOUCHED. `floors.py` removed `TOOL_LENGTH_VIOLATION` from `FLOOR_EXECUTORS` (line 224) but KEPT `LengthViolationTool` (113), `_SENTENCE_SPLIT` (60), `_length_reference` (207), and the import (45). `verification/spec.py` is **0-diff**. Purely subtractive.
2. **Behavioral fidelity / the headline challenge — PRESERVED.** `test_narrative_floor_grades_under_pack_narrative` (`:373`) is NOT skip-guarded — it spawns its own `pack=narrative` subprocess, so it RAN+PASSED under the `pack=healthcare` green bar (absent from that run's SKIPPED list). It asserts `stage_verdict=="BLOCK"`, `verdict=="reject"`, `SILENT_DEGRADATION in active_codes`, `floor_block_count>=1`, **`n_verification_contracts==2`**. SILENT_DEGRADATION still flips PASS→BLOCK→reject. A1/A2 grade through `_shipped_narrative_ontology()` → `load_ontology(pack_ontology_path())` (the SHIPPED ontology, not the test-local dict) — adversarial probe #1 PASSES.
3. **Out-of-scope intrusion — NONE.** `git diff 591741d HEAD --name-only` = 7 files (6 expected + the executor session-log json). Moat/core freeze EMPTY for all of `compliance_council.py`/`signals.py`/`withstands.py`/`judge_metric.py`/`harness/grounding.py`/`verification/{spec,tools}.py`/`apps/bff/agent/tools.py`. No taxonomy re-snapshot. No healthcare touch. No shell/frontend.
4. **Spec ambiguity / honesty — HONEST, no soft-pass.** The removed `narrative_length_violation` case was genuinely floor-only: its recipe is `mutated_projection: "preamble"` over the WHOLE `artifacts[0].content`, `post_value: "single run-on sentence (1<3)"`, `expected_owner_map: {}`. It was true-by-construction ONLY because it was synthetically a single-sentence artifact (no human-authored body) — exactly the unrepresentative case the diagnosis names. On a real enhanced scene the artifact = (human body + AI preamble) with no separable preamble span, so the whole-scene floor false-blocks (confirmed by the RED: 3-of-4 enhanced scenes). Demoting the floor legitimately makes the case no-longer-true-by-construction (LENGTH_VIOLATION now needs the LLM judge, already its `policy_judge` lens owner). The honest fix, not a dodge.

## Adversarial probes
- A1 uses the shipped `load_ontology()` — CONFIRMED (not test-local).
- No test asserts a corpus count of 4 — CONFIRMED (both `narrative_v1.jsonl` refs are `load_case` by id; no count assertion orphaned).
- LENGTH_VIOLATION is still a gradeable `policy_judge` lens code + TIER_2 + ontology flag + question — CONFIRMED (owned by exactly one lens → owner↔emit intact, no inert flag).
- `test_narrative_snapshot_consistency` still PASSES — every gradeable flag maps to a lens.

## NON-BLOCKING observations (for the record; cycle closes CLEAN)
1. **`S-BS-NARR4-3` (NEW, low — spec-author reconcile, pre-existing):** `SPEC_NARRATIVE_EVAL.md` §4.3 (`:127-130`) still lists `POV_VIOLATION`/`LANGUAGE_DRIFT`/`CLICHE_OVERUSE`/`REPETITION` as `floor (det.)`, but the shipped floor set is only `{bracket_leak, silent_degradation}`. A pre-existing spec-draft/impl gap (byte-identical at parent `591741d`), untouched by NARR-4 — NARR-4 correctly flipped only the one row it owned. The §4.3 "draft codes" table should be reconciled against what NARR-3 actually shipped. Not reducible to a NARR-4 failing test.
2. **`S-BS-NARR4-2` (low, = `S-BS-NARR3-2` instance):** `test_pack_dist::test_a2` keeps failing under `pack=healthcare` on the narrative pack's own `_provenance` needle-naming prose. Pre-existing since NARR-1; the A2 carve-out / needle-regex refinement is NARR-5 / pack-dist follow-on territory.

## Disposition
The NARR-4 contract is met; Gate 0 is green on both envs (0 NEW); the moat is byte-frozen; the demote is purely subtractive and HONEST; the headline is preserved; RED→GREEN reproduced cold. **Cycle closes CLEAN.** Carried seam: `S-BS-NARR4-1` (LENGTH_VIOLATION's judge positive-catch is unproven offline — subtractive verification only; proven live in NARR-5). The S-BS-NARR3-3 lock is fully implemented.
