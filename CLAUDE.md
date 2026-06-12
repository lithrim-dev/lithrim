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

`packs/healthcare/taxonomy_snapshot.json` is the only coupling point to `lithrim-backend` — the snapshot relocated INTO the `healthcare` pack (PACK-1, layer-1a: the invariant *moves* into the pack, it does not weaken). Refresh it via `scripts/snapshot_taxonomy.py --backend-path … --out packs/healthcare/taxonomy_snapshot.json` (the `--out` default already points there). Never hand-edit. If the lint script starts failing after a backend taxonomy change, the fix is to re-snapshot, not to soft-pass cases. The core resolves the snapshot via the **active pack** (`lithrim_bench/harness/pack.py`), not a hardcoded path. As of PACK-1b/2b/2c the live council reads its `KNOWN_TAXONOMY_CODES` + tier sets (`pack_tiers()`), its Tier-1 owner-map `_TIER1_OWNERS` (`pack_tier1_owners()`, the `tier1_owners` block), its **v2 roster IDENTITY** (`pack_production_judges()`, the `production_judges` block — which judges run, and in what order), AND its **lens authority** (`judge_metric.LENS_BY_ROLE` via `pack_lenses()`, the `lenses` block — the per-role "codes you may raise" the withstands-gate scope-checks) FROM this snapshot at runtime, so it is load-bearing at runtime, not just a lint contract. PACK-2c is an identity↔deployment split: the snapshot carries WHICH judges run; the per-role DEPLOYMENT binding (provider / Azure model id / capability flags, the core-side `_ROLE_DEPLOYMENT`) stays in core — a pack must never carry infra (a pack judge with no core deployment fails-clean at council construction). The `lenses` block, like the role NAMES, is bench-curated (not council-derived), so `scripts/snapshot_taxonomy.py` carries it over from the prior snapshot on re-snapshot — never hand-edit beyond that. CE-STANDALONE-1 adds `packs/support_ticket_qa/` — a `tier: core` **non-clinical sample pack** (the standalone-CE fixture / OSS sample): a genuinely independent pack (its own ontology + `council_roles` + snapshot, no `packs/healthcare/` reuse) proving the core grades a non-clinical case via the authored path with the healthcare pack unloaded + `:8002` down + 0 clinical leakage (`tests/test_standalone_ce.py`; spec `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md`). **CE-PACK-NEUTRAL-DEFAULT:** the core-shipped `DEFAULT_PACK` is the neutral `_core` pack (`packs/_core/`, `pack.py`), NOT `healthcare` — the core boots + grades standalone with no Pro pack on disk (`council_roster()` reads `packs/_core/`; `tests/test_neutral_default.py` proves zero `packs/healthcare/` reads under the env-unset default). `healthcare` is an **opt-in** domain pack (`LITHRIM_BENCH_PACK=healthcare`); the existing test suite pins it back via `tests/conftest.py`. Closes S-BS-130 + retires the S-BS-125 tripwire. **CE-PACK-6b-ROUTE:** the in-process grade (`scripts/run_eval.py`, the `in_process` branch) is **authored-path-only** — it ALWAYS builds `build_authored_semantic_stage` (no-assignment agents default each judge to its full pack lens, `pack_lenses()[role]` over `pack_production_judges()`), so `semantic_stage` is never `None`. The legacy `ComplianceCouncil.build_prompt` clinical default council is **dead code on the product path** (physically present, reached only by `stages.py`/`ab_harness`/`test_consensus`; deleted in 6b-CLEAN) — UI-authored prompts (ontology + role prompts) are the single live prompt source. The `ws0_default` replay baseline is the historical default-council verdict (kept, replay-only). **CE-PACK-6b-CLEAN (DONE 2026-06-12):** the FROZEN endgame — `build_prompt` + the core `safety_flags.py` are now **DELETED**; `evaluate()`'s transcript branch raises (the authored stage is the single live prompt source; `evaluate()` then served `source_message` only — retired in 6c below — and `stages.py`'s default transcript path also reroutes to the authored trio, so nothing live reaches a default council). The 23-flag healthcare seed RELOCATED to `packs/healthcare/safety_flags_seed.py` (D2-a; `scripts/seed_ontology.py` reads it by file path, build output byte-identical; the `_provenance.flag_source` literal is kept VERBATIM so the moat-frozen `ontology.json` stays byte-identical). `_build_signature` is genericized (**S-BS-129/G4 closed**). `_apply_consensus` + the consensus/withstands MECHANISM are **byte-frozen vs `acc4973`** (the moat is 0-delta), authorized by the `tests/_seam_freeze.py` deletion + signature carve-outs (non-vacuous in both directions — `tests/test_6bclean_seam_guard.py`). The core council's prompt-builder + flag-definition residue is clinical-clean. **CE-PACK-6c (DONE 2026-06-12):** `build_source_message_prompt` (the last live clinical prompt builder) is **DELETED** — the source_message stage reroutes to the authored stage exactly as the transcript stage did (Fork A: *retire*, not relocate; re-confirmed bench-dead — no live path sets `context_kind=source_message`), so `evaluate()` now builds NO prompt for any `context_kind` (its source_message branch raises a `CE-PACK-6c` sentinel; a 5th D4-authorized frozen deletion, moat byte-frozen vs `acc4973`, guard non-vacuous both ways — `tests/test_6bclean_seam_guard.py`). `phi_redaction` is **kept-as-generic** in core (Fork B: a domain-agnostic PII/PHI redaction mechanism, live via the observation agents independent of the council; PROSE genericized, `HIPAA_*` config keys kept for compat). The **honest** bar is **no live clinical CODE** (`grep 'def build_source_message_prompt\|def build_prompt' runtime/council/` → empty, pinned by `tests/test_6bclean_attestation.py::test_no_live_clinical_code`), NOT literal grep-empty — the FROZEN carve-out/provenance comments + the load-bearing `HIPAA_*` config keys are PASSIVE residual (enumerated + pinned). **Closes S-BS-131; the generic-CE demarcation program is DONE.**

## The plugin registry is the Core/Pro boundary (PLUGIN-1)

`lithrim_bench/harness/plugins.py` is the unified plugin registry (Plugin Phase-1, `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md`). The three former ad-hoc registries — the pack loaders (`harness/pack.py`), the grounding contract registry (`grounding.py` `_CONTRACT_EXECUTORS` + the pack-floors merge → `contract_plugins()`), and the judge provider (`judges_dspy.py` `build_judge_lm` → `plugins.resolve_provider_id`) — are declared as `PluginManifest`/`PackManifest` entries (`kind/tier/transport/implements`). **`tier` is the single Core/Pro boundary field, read at load:** `harness/pack.py` `assert_pack_licensed` gates a `tier: pro` pack — under a denying `License` (env `LITHRIM_BENCH_LICENSE`; **default permit-all** so grading is byte-identical) the pack is ABSENT (the harness import fails closed), not stubbed. **R-GUARD:** the gate sits ONLY on the ontology/taxonomy/prompts `*_path` resolvers (above the frozen-council seam) — NEVER on `pack_tiers`/`pack_tier1_owners`/`pack_lenses`/`pack_production_judges` (the council's inline-`__import__` carve-out targets; gating them re-enters the council import). The contract/provider folds are declaration-only/byte-identical (the moat — `_apply_consensus`, the `signals.py` withstands read — is untouched). The loaded-plugin set is recorded in `PipelineProvenance` (`loaded_plugins`/`active_pack`/`pack_tier`). Adding a new contract/pack + tier-tagging it is **manifest-only, zero engine edits** (the open/closed test, `tests/test_plugin_phase1.py`). `plugins.py` is stdlib+pydantic-only (no `openai`/`dspy`). **Still deferred:** the `frontend` kind (post-CHATBIND-2), Phase-2 HPACK, Phase-3 enforcement/VPC.

## Document organization

- `docs/PAPER_OUTLINE.md` — the locked, one-claim paper outline. Do not weaken the claim without explicit user say-so.
- `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` — the spec this engine implements. Defects D1–D7 are the acceptance criteria.
- `docs/ARCHITECTURE.md` — engine diagram + module responsibilities.
- `docs/LITHRIM_BENCH_PRODUCT_SPEC.md` — the developer-product framing (API surface, pricing, onboarding flow).
- `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` — **LOCKED 2026-06-04.** THE product: the UI-driven author→process loop (create judges → create flags → run processing) over the config plane, with a first-class why/when/who/what audit trail. The 4-act journey is a frozen demo inside it. Entity model: judges = assigned ontologies + execute-not-generate validators; the Ralph-Loop withstands-gate; independent GroundingChecks. Build sequence = UAP-1..4.
