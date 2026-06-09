# Critique — bench-salvage PACK-5a (healthcare-realm-as-pack, layer 5a: scribe dataset-generation → pack)

**Date:** 2026-06-09 · **Verdict:** PROCEED-WITH-CAVEATS · **Hardness:** HARD GATE (fresh-critic required)
**Build:** `aeb0ac0..aab2f8f` (4 atomic pathspec-only, parent `0bcdd1b`, NOT pushed — LOCAL is SSOT)
**Session log:** `session-bench-salvage-phasePACK-5a-2026-06-09.json`

## What this cut is
The strangler-fig **layer 5a** and the **unify** step: the clinical **scribe** dataset-generation realm (5 injectors + `_soap.py` + 2 synthesizers + the `SCRIBE_PACK` recipe) relocated **byte-verbatim** out of the domain-agnostic engine into `packs/healthcare/generators/`, behind a new `load_pack_generators` registration interface (mirroring PACK-3's `load_pack_floors`, but loading a multi-file PACKAGE via `submodule_search_locations` + `sys.modules`). This **unifies the two "pack" concepts** — `packs.py PACKS` (per-agent generation recipes) ⊕ `packs/healthcare/` (eval-config) — so a pack is now **data + grading + generation**. The generic framework (`DefectInjector`/`InjectionRecipe`/`InjectionResult`, `PackDefinition` class, `EncounterSpec`, `packager`, the Synthea loaders) stays core; the core resolves generators via the active pack (`active_packs()` lazy merge).

## Monitor 7-item mechanical audit — CLEAN
1. Scope — 4 commits / 25 files, no foreign; 8 scribe files renamed (`_soap` R100, 7 import-only R092–096); `generators/__init__.py` +94, `test_pack_layer5a.py` +200.
2. A1 boundary — scribe class/def needles ABSENT from `lithrim_bench/`, PRESENT in the pack (relocation ≠ deletion).
3. A4 generic 0-delta — `injectors/base.py`/`encounter_spec.py`/`packager.py`/`synthea_*loader.py` byte-untouched.
4. No core→pack leak — core uses the `load_pack_generators` interface; the pack imports FROM core (`transcript.py` → `lithrim_bench.encounter_spec` + `._pmh`).
5. Byte-verbatim — `git diff -M --diff-filter=R`: every changed line in the 8 relocated files is an `import` (logic/labels untouched).
6. Frozen 0-delta — council seam (`compliance_council`/`judge_metric`/`judges_dspy`) + pack `ontology.json`/`taxonomy_snapshot.json` all empty diff.
7. The A2 by-construction gate + the layer5a suite pass (8/8 canonical).

## HARD-GATE fresh-critic — agent `a0fe2678a1243f468` — NON-BLOCKING [0 BLOCKING / 1 NB / 0 OQ]
> **Infra note:** the FIRST critic (`abb94f7ffb7e2cb32`) STALLED on an infra watchdog (no progress 600s) after confirming the interface architecture is clean — NOT a finding. Re-spawned with anti-stall tuning (targeted suites, non-interactive). The monitor also independently ground-truthed the crux (byte-verbatim, frozen 0-delta, A1/A4, no leak, A2 gate) as belt-and-suspenders.

The re-spawn re-derived everything from git+code in an isolated worktree; "tried to break it; the relocation is a true move."
- **Byte-verbatim CONFIRMED** — `_soap.py` R100 (zero changed lines); the rest R092–096; every changed line is an import re-point; `_DOSE_RE`, drift bands, `FABRICATIONS`/`HALLUCINATIONS` tables, all `InjectionRecipe(...)` blocks identical. Zero logic/label change.
- **By-construction byte-identity (A2) CONFIRMED — strongest evidence.** The cohort was present in the worktree, so the gate ran: regenerating the full corpus at parent (scribe-in-core) vs HEAD (scribe-in-pack) is **byte-for-byte identical** — all 83 rows' `injection_recipe` + `expected_safety_flags` tuples match. The labels-true-by-construction invariant survives the relocation intact.
- **Package-loading non-vacuity + fail-clean CONFIRMED (5/5)** — `scribe_v1.transcript_fn.__module__` = the pack package (not core); the 4 non-scribe = core; a no-`generators` manifest degrades (scribe absent, no core fallback, no crash), bad path → `FileNotFoundError`; `._soap` resolves via `submodule_search_locations` (ran 4/5 injectors live, 21 injections); stable `sys.modules` identity (no re-exec); `import lithrim_bench.packs` pulls no dspy/openai/httpx and does not eagerly load the pack (no cycle).
- **No core→pack leak CONFIRMED** — AST walk of `lithrim_bench/`: zero `import packs`/`from packs.*`; `load_pack_generators` referenced only by `packs.py` (caller) + `harness/pack.py` (definition).
- **Frozen/generic 0-delta CONFIRMED.** **Green bar 0-new CONFIRMED** — python3 444p/2f, debuglithrim (targeted) 121p/1f; both failing tests (`test_pack_layer5a::test_judge_calib_regenerates_byte_identical`, `test_uap4_corpus_superset`) fail ONLY on the embedded absolute `cohort_path` (S-BS-117) and **fail identically at parent in the same worktree** → strictly 0-new, label-clean.

## The deviation I own — the `_pmh` citation-drift (the sole NB)
My driver's D-B claimed `_pmh.py` is "shared with coding" (→ keep core in 5a). **That citation was WRONG** — `_pmh` is scribe-only (coding imports `_coding_dx.resolve_primary_dx`, not `_pmh`); my combined `_pmh|_soap` pre-flight grep mis-attributed a `_soap` hit on `coding_note.py`. The executor caught it (CITATION-DRIFT) and the user chose to keep `_pmh` core for 5a under the (now-false) premise. Consequence: a scribe-only helper (`synthesizers/_pmh.py`) stayed in the core — a thin clinical residual, imported pack→core by the relocated synthesizers (valid, works live). **NON-BLOCKING** (tracked S-BS-121; functional). **Lesson for PACK-5b:** scope `_pmh`'s relocation explicitly + re-grep cites per-pattern (not combined).

## Seams (both low)
- **S-BS-120** — `generate_pack.py` stamps a wall-clock `generated_at` → its scribe corpus isn't byte-deterministic across runs (unlike `generate_judge_calib.py`, which freezes the timestamp; the automated A2 gate uses the latter). Fix = freeze/parameterize `generated_at` at generation. Relates to S-BS-117 (corpus determinism).
- **S-BS-121** — `synthesizers/_pmh.py` is scribe-only but stayed core this cycle (the citation-drift above) — a thin clinical residual; relocates in PACK-5b with coding. The PACK-5b driver MUST include it.

## Disposition
A clean, byte-behavior-identical, grep-verifiable relocation of the scribe generation realm into the pack, behind a sound multi-file package-loading interface; the by-construction labels regenerate byte-identical (the strongest evidence yet); frozen seam 0-delta; 0-new both envs. **CLOSED PROCEED-WITH-CAVEATS.** No proof capsule (offline mechanism; A2 proven $0 by byte-identity). **NEXT = PACK-5b** (coding/hl7/scheduling/triage generators + the `_pmh` residual + empty core `packs.py` → thin resolver), after which `grep lithrim_bench/ → empty` holds except the frozen council → the 1b/2b endgame. Layer-4 (FE journey) remains DROPPED (a product follow-on, not a core-boundary layer).
