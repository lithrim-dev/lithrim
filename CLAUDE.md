# Lithrim Bench

Synthetic clinical-AI benchmark generator. Backs the Lithrim research paper and the developer product. **Read `README.md` and `docs/PAPER_OUTLINE.md` before doing anything.**

## Diagnose-before-edit (inherited from lithrim-backend)

When fixing a labeling / verdict / determinism bug, post the verbatim evidence (golden row JSON, taxonomy entry, run JSON) in a fenced code block before stating the diagnosis. Tag every causal claim **CONFIRMED** / **INFERRED** / **HYPOTHESIS**. The bench exists precisely because story-shaped diagnoses have polluted the eval before; do not repeat that here.

## Core invariant: labels are true by construction

This is the entire reason this repo exists. A case is admissible **only** if:

1. Every `expected_safety_flags` code is in `packs/healthcare/taxonomy_snapshot.json` `KNOWN_TAXONOMY_CODES`.
2. The `injection_recipe` block specifies `defect_type`, `mutated_projection`, `mutated_field_or_span`, `pre_value`, `post_value`. The recipe **is** the label justification.
3. Clean negatives have `injection_recipe: null` and `expected_safety_flags: []`. They are first-class, not residue.
4. Every flag has a `production_judges`-resident owner per `tier1_owners`. Flags whose only owner is `source_message_judge` (declared but not running) must be excluded or reassigned; never silently scored.

If a case cannot meet (1)–(4), it does **not** ship. Do not append to `examples/*.jsonl` without the lint script passing.

## Stack

- Python 3.10+
- Pydantic v2 for schemas (no v1 syntax)
- Pandas for Synthea CSV loading
- No LLM dependency for v1 deterministic synthesis. The `synthesizers/transcript.py` and `synthesizers/scribe_artifact.py` are template-based on purpose, so the benchmark generator runs offline and is byte-deterministic given the same Synthea seed + injector params.

## Conventions

- Async only where it earns its keep (it doesn't, for a CLI generator). Default sync.
- `ruff check .` / `ruff format .` is the lint.
- Tests with `pytest`. Tests must be runnable without network and without the Synthea CSV (use fixtures).
- No comments unless the *why* is non-obvious. Don't write what the code already says.

## What this repo is NOT

- Not a copy of `lithrim-backend`. The backend imports nothing from here.
- Not an LLM training pipeline. It generates eval cases; scoring lives in `lithrim-backend`.
- Not a FHIR validator. That is etlp-mapper. We *consume* FHIR; we don't validate it here.
- Not a UI. CLI + JSONL until phase 4.

## Taxonomy snapshot is the contract

`packs/healthcare/taxonomy_snapshot.json` is the only coupling point to `lithrim-backend` — the snapshot relocated INTO the `healthcare` pack (PACK-1, layer-1a: the invariant *moves* into the pack, it does not weaken). Refresh it via `scripts/snapshot_taxonomy.py --backend-path … --out packs/healthcare/taxonomy_snapshot.json` (the `--out` default already points there). Never hand-edit. If the lint script starts failing after a backend taxonomy change, the fix is to re-snapshot, not to soft-pass cases. The core resolves the snapshot via the **active pack** (`lithrim_bench/harness/pack.py`), not a hardcoded path. As of PACK-1b the live council reads its `KNOWN_TAXONOMY_CODES` + tier sets FROM this snapshot at runtime (`pack_tiers()`), so it is load-bearing at runtime, not just a lint contract.

## Document organization

- `docs/PAPER_OUTLINE.md` — the locked, one-claim paper outline. Do not weaken the claim without explicit user say-so.
- `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` — the spec this engine implements. Defects D1–D7 are the acceptance criteria.
- `docs/ARCHITECTURE.md` — engine diagram + module responsibilities.
- `docs/LITHRIM_BENCH_PRODUCT_SPEC.md` — the developer-product framing (API surface, pricing, onboarding flow).
- `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` — **LOCKED 2026-06-04.** THE product: the UI-driven author→process loop (create judges → create flags → run processing) over the config plane, with a first-class why/when/who/what audit trail. The 4-act journey is a frozen demo inside it. Entity model: judges = assigned ontologies + execute-not-generate validators; the Ralph-Loop withstands-gate; independent GroundingChecks. Build sequence = UAP-1..4.
