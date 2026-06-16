# HANDOFF — bench-salvage — NARR-4 closed → NARR-5 (2026-06-16)

> **For the next session.** The narrative-eval wedge's deterministic floor is now **right on real data**.
> **NARR-4 (the `S-BS-NARR3-3` lock-fix — demote `LENGTH_VIOLATION` out of the floor → the `policy_judge`
> lens) is CLOSED CLEAN** (HARD GATE; fresh cold critic CLEAN + monitor audit CLEAN). Next is **NARR-5**
> — the SPLIT-OUT visceral end-to-end demo (multi-model council + frontend on real Lenador data + the
> `S-BS-NARR2-1` corpus-gradeable bridge). **Resume:** `/devloop-resume bench-salvage`, then read
> `docs/specs/SPEC_NARRATIVE_EVAL.md` (§3 loop, §6 P1, §8 — NARR-4 was the demo; it SPLIT, see below) + this doc.

---

## What just landed (NARR-4 — the floor is honest on real scenes)

| Commit | What |
|---|---|
| `c009358` | **test-RED** — `test_real_enhanced_scenes_are_not_length_blocked` (A1) + `test_shipped_ontology_has_no_length_violation_floor_contract` (A2); RED at parent for `scene_mountain_road`/`scene_the_warning`/`scene_the_descent` (7/5/5) — `scene_ranger_arrival` (4, in-band) NOT blocked → non-vacuous |
| `abcbaa9` | **green** — `ontology.json` (3→2 contracts) + `floors.py` (`FLOOR_EXECUTORS` drops `length_violation`; **`LengthViolationTool` KEPT**, retained/unattached) + `narrative_v1.jsonl` (corpus 4→3, the `narrative_length_violation` case removed) |
| `b88c523` | consequence-edits — `_NARR3_FLOOR_TYPES` + `n_verification_contracts==2` (both `tests/test_narrative_floor.py:398` subprocess and `tests/test_narrative_pack.py`) + the test-local `_NARRATIVE_ONT_DICT` |
| `eb8cd1a` | spec sync — `SPEC_NARRATIVE_EVAL.md` §4.3 `LENGTH_VIOLATION` row `floor (det.)`→`judge` + §11 RESOLVED note (mechanical) |
| `7eba320` | the NARR-4 session log |

**The lock (`S-BS-NARR3-3`), now implemented:** the shipped per-scene record carries only `clean_text` (no separable preamble span) and §4.2 emits the whole scene, so preamble-length is **not machine-true-by-construction** → it does not belong in the deterministic floor. The demote was **purely subtractive** because `LENGTH_VIOLATION` was already a `policy_judge` lens code (`taxonomy_snapshot.json` lenses + ontology question ordinal 2). **`verification/spec.py` is 0-diff** (the tool-name stays registered; the `LengthViolationTool` class is retained, unattached — zero-code re-attach if a future preamble span ever exists, option (a)). **MOAT byte-frozen** (council four + `grounding.py` + `verification/{spec,tools}.py` + `apps/bff/agent/tools.py` = 0-diff; no re-snapshot).

**The active deterministic floor set is now `{bracket_leak, silent_degradation}`.** The headline (`SILENT_DEGRADATION` flips a clean council PASS→BLOCK→reject) holds, asserted in the canonical green bar via the not-skip-guarded subprocess `test_narrative_floor_grades_under_pack_narrative`. **Gate 0:** pack=narrative 14p/0f; pack=healthcare 587p / 3 pre-existing / 10s = **0 NEW**.

---

## ⚠️ NARR-5 PHASE NOTE — NARR-4 was the spec-§8 "demo"; it SPLIT

Spec §8 names "NARR-4 = the frontend demo + multi-model council." During the S-BS-NARR3-3 lock we **split** that: this NARR-4 shipped the floor-honesty precondition (the demote), and the visceral demo moves to **NARR-5**. Treat §8's NARR-4 row as NARR-5. (The split is recorded in the NARR-4 driver §0 and the STREAM doc.)

## What's next — NARR-5 (the visceral end-to-end demo)

Per `SPEC_NARRATIVE_EVAL` §3/§6 P1/§8: the **frontend demo** on real Lenador data with the **Claude/GPT/Llama multi-model council** (the judge-layer codes `BODY_CONTRADICTION`/`MODE_INAPPROPRIATE`/`TONE_INFIDELITY`/`PERSONALIZATION_MISS` + now **`LENGTH_VIOLATION` as a judge lens**) layered over the shipped deterministic floor. **Order of work:** (1) the **`S-BS-NARR2-1` D-C bridge** — make ingested cases gradeable through `load_case`/the picklist (the NARR-2→demo bridge; `app.py:1964` + `picklist.py`); (2) the **multi-model council** (`_ROLE_DEPLOYMENT` / `build_judge_lm` / pack `production_judges`); (3) the **frontend surface**. **Do a live reassessment first** (per the standing "live-reassess before driver lock" practice — services permitting) to right-size and prefer the smallest demonstrable-live cut.

**`S-BS-NARR4-1` is the NARR-5 proof obligation:** NARR-4 verified the demote *subtractively* (the floor no longer false-blocks). NARR-5's council must prove the **positive** direction — that the `policy_judge` lens correctly FIRES `LENGTH_VIOLATION` on a genuine over-length preamble (an honest live catch, honest-Δ).

## Open seams
- **`S-BS-NARR4-1`** (low, **NARR-5**) — LENGTH_VIOLATION's judge positive-catch is unproven offline (subtractive verification only); prove it live in the multi-model council.
- **`S-BS-NARR4-3`** (low, **spec-author reconcile**) — `SPEC_NARRATIVE_EVAL.md` §4.3:127-130 still lists `POV_VIOLATION`/`LANGUAGE_DRIFT`/`CLICHE_OVERUSE`/`REPETITION` as `floor (det.)`, but the shipped floor set is only `{bracket_leak, silent_degradation}` (PRE-EXISTING — NARR-3 shipped 3 floors, the draft table was never reconciled). Reconcile the §4.3 draft table vs the live floor set. Not reducible to a failing test.
- **`S-BS-NARR4-2`** (low, = `S-BS-NARR3-2`) — `test_pack_dist::test_a2` needle-scanner trips on the narrative pack's own `_provenance` disclaimer prose; the A2 carve-out / needle-regex refinement is pack-dist follow-on territory.
- **`S-BS-NARR3-1`** (medium) — the conftest pack-gate keys on healthcare-discoverable vs bare-CE, never the active pack, so the full suite can't run green under the canonical narrative env (~104 pre-existing). A conftest import-isolation + narrative-active hygiene cycle settles it.
- Carried from NARR-2: **`S-BS-NARR2-1`** (the D-C corpus-gradeable bridge — folds into NARR-5 step 1), **`S-BS-NARR2-3`** (bridge→scene stub, P1).

## Standing prefs (unchanged)
No autostart (`:3031` not needed for the shipped floors — pure-stdlib `in_process`; **NARR-5's demo WILL need live services** — `curl /health` first, never autostart) · no push without owner approval (branch `bench-salvage/ws6c-dspy`, **NOT pushed**) · pathspec-only atomic commits · tests-first (RED before code) · canonical env `LITHRIM_BENCH_PACK=healthcare LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare PYENV_VERSION=debuglithrim` for the green bar (and `LITHRIM_BENCH_PACK=narrative` for the targeted floor tests) · diagnose-before-edit · honest-Δ / BYO-key $0 first · MOAT byte-frozen.

## First move (next session)
1. Read this doc + `docs/specs/SPEC_NARRATIVE_EVAL.md` (§3/§6 P1/§8) + the NARR-4 critique (`.devloop/sessions/critique-bench-salvage-phaseNARR-4-2026-06-16.md`).
2. **Live reassessment** (services permitting): ground-truth the "compose-not-build" reuse claims for the council + frontend + bridge; right-size NARR-5 to the smallest demonstrable-live cut; split any speculative backend to a precondition-gated follow-on.
3. `/devloop-expand-driver bench-salvage NARR-5` (author from the spec; re-grep every anchor; fold in the `S-BS-NARR2-1` bridge + the `S-BS-NARR4-1` live positive-catch proof obligation).
