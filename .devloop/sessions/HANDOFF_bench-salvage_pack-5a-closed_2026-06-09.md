# HANDOFF — bench-salvage — 2026-06-09 (PACK-5a layer-5a scribe generation CLOSED → packs-as-generation; the unify landed)

> **For the next session.** PACK-5a (healthcare-realm-as-pack, layer-5a scribe dataset-generation) closed PROCEED-WITH-CAVEATS (HARD-GATE fresh-critic `a0fe2678a1243f468` NON-BLOCKING [0/1/0]). The scribe generation realm is OUT of the core and in the `healthcare` pack — the FIRST packs-as-GENERATION step, **unifying** the two "pack" concepts so a pack = **data + grading + generation**. **Resume:** `/devloop-resume bench-salvage`, read memory `healthcare-realm-as-pack`.

## ✅ What landed (PACK-5a)
The clinical **scribe** generation realm — 5 injectors (`wrong_dosage`/`missing_allergy`/`fabricated_history`/`value_mismatch`/`hallucinated_detail`) + `_soap.py` + 2 synthesizers (`transcript.py`/`scribe_artifact.py`) + the `SCRIBE_PACK` recipe — relocated **byte-verbatim** (only imports re-pointed pack→core) into `packs/healthcare/generators/`, behind a NEW pack-generator registration interface: `harness/pack.py:load_pack_generators` importlib-loads the manifest's `generators` as a **multi-file PACKAGE** (`submodule_search_locations` + `sys.modules`, cached on the resolved pack id — the generation twin of PACK-3's `load_pack_floors`); `packs.py` keeps the `PackDefinition` class + the 4 non-scribe instances + a lazy `active_packs()` merge (pack→core, no cycle, `import packs` heavy-dep-free). The generic framework (`DefectInjector`/`InjectionRecipe`/`InjectionResult`, `EncounterSpec`, `packager`, the Synthea loaders) stays core. Build `aeb0ac0..aab2f8f` (4 atomic pathspec-only, NOT pushed — LOCAL is SSOT).

- **The crux — by-construction byte-identity — CONFIRMED (strongest evidence yet):** the critic's worktree had the cohort present, so the gate ran — regenerating the full corpus at parent (scribe-in-core) vs HEAD (scribe-in-pack) is **byte-for-byte identical**, all 83 rows' `injection_recipe` + `expected_safety_flags` unchanged. The labels-true-by-construction invariant survived the relocation intact.
- Monitor 7-item CLEAN + independent crux ground-truth + the critic CONFIRMED byte-verbatim (`_soap` R100, rest R092–096, every changed line an import), package-loader non-vacuity 5/5 (scribe-from-pack module identity, no-generators degrades, `_soap` resolves + ran injectors live, stable `sys.modules`, no eager-load/cycle), no core→pack leak (AST-verified), frozen/generic 0-delta. Full close: `critique-bench-salvage-PACK-5a-2026-06-09.md`.
- **Infra note:** the FIRST critic (`abb94f7ffb7e2cb32`) STALLED on a watchdog (no progress 600s) after confirming the architecture — re-spawned with anti-stall tuning (targeted suites, non-interactive). Not a finding.

## 🔴 NEXT — PACK-5b (the layer that finishes the core boundary; do NOT autostart)
**PACK-5b — relocate the remaining agent-type generators + the `_pmh` residual + thin out core `packs.py`.** After 5b, `grep lithrim_bench/ → empty` holds for everything EXCEPT the frozen council → the 1b/2b endgame.
- Move the **coding / hl7 / scheduling / triage** generators (their injectors + synthesizers + `PackDefinition` instances) into the pack via the same `load_pack_generators` interface.
- **MUST include `synthesizers/_pmh.py`** (the scribe-only residual, S-BS-121) — it relocates with coding (then pack→pack).
- Empty core `packs.py` to a thin resolver (just `PackDefinition` + `active_packs()`); `injectors/__init__.py` drops the remaining agent-type registries.
- **LESSON (own it):** re-grep cites **per-pattern**, not combined — PACK-5a's driver mis-attributed `_pmh` as "shared with coding" from a combined `_pmh|_soap` grep (it's scribe-only; coding uses `_coding_dx`). Don't repeat it.

## ⚠️ DURABLE NOTE — the green-bar baseline (read before the next fresh critic)
Worktree-isolated critics see env/path-sensitive pre-existing failures the canonical checkout doesn't: **`examples/proof_case.jsonl` is gitignored** (S-BS-119) and the committed corpora carry a machine-**absolute `cohort_path`** (S-BS-117) → bare worktrees regenerate with their own path and the corpus-determinism tests fail. **All are 0-new at parent.** PACK-5a's critic saw `test_pack_layer5a::test_judge_calib_regenerates_byte_identical` + `test_uap4_corpus_superset` fail on `cohort_path` — both fail identically at parent. **Judge green by *0-new at parent in the same env*, never by absolute counts.**

## ⚠️ Seams + owed
- **S-BS-120** (low) — `generate_pack.py` stamps a wall-clock `generated_at` → its scribe corpus isn't byte-deterministic across runs (the A2 gate uses `generate_judge_calib.py`'s frozen timestamp). Fix = freeze/parameterize `generated_at`.
- **S-BS-121** (low) — `synthesizers/_pmh.py` scribe-only-in-core residual (the citation-drift) → relocates in PACK-5b.
- Carried: S-BS-117 (corpus abspath), S-BS-118 (packs-as-code trust surface), S-BS-119 (gitignored fixtures), S-BS-113/114/115/116, S-BS-96.
- **OWED:** the PAID before/after on `ws0_default` (user-fires; A2 proven $0 by byte-identity).

## 🗺️ Finish-line map
`PACK-1/2/3 (ontology/judges/floors) ✓ → PACK-5a (scribe generation) ✓ → PACK-5b (coding/hl7/scheduling/triage + _pmh) → grep lithrim_bench/ ≈ empty → 1b/2b (un-freeze the council) = the true finish.` Layer-4 (FE journey) DROPPED — a frozen pitch demo in a separate app, a product follow-on, not a core-boundary layer.

## Standing context (unchanged)
No autostart; **no push — LOCAL is SSOT (no remote)**; LLM-cost-conscious (the user fires paid/live runs); honest-Δ only; **pathspec-only commits** (the dirty shared index); shell JSX hand-compact **NO prettier**; council suite via `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python`. HARD-GATE critics: `isolation:'worktree'`, scan the close-commit output for `[detached HEAD]`; re-spawn on infra stall.

## Pointers
- **Authority:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the Layer-5a entry + the unified pack model: data + grading + generation; the BE registration interface) + CLAUDE.md (labels true by construction).
- **Memory:** `healthcare-realm-as-pack` (the layered plan + the unify + the citation-drift lesson), `conversational-first-core-plugin-line`.
- **The pack:** `packs/healthcare/{pack.json,generators/,floors.py,council_roles/,ontology.json,taxonomy_snapshot.json}` + `harness/pack.py` (`load_pack_generators`/`load_pack_floors`/`active_pack`) + `lithrim_bench/packs.py` (`active_packs()` merge).
