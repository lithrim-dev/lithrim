# Lithrim Bench

Synthetic clinical-AI benchmark generator + the generic eval-harness core (CE). Backs the Lithrim research paper and the developer product. **Read `README.md` and `docs/PAPER_OUTLINE.md` before doing anything.**

## Non-negotiables

1. **Diagnose before edit.** Post verbatim evidence (golden row JSON, taxonomy entry, run JSON, DB query output) in a fenced block before stating a diagnosis. Tag every causal claim CONFIRMED / INFERRED / HYPOTHESIS. Story-shaped diagnoses have polluted this eval before; do not repeat that.
2. **Verify which surface you are reading before concluding anything.** Docker DB vs local DB, live service vs stale UI state, latest fixture/YAML vs a stale one. Print the check first (`curl /health`, `docker ps`, fixture diff), then diagnose. Stale-read misdiagnosis is this repo's most common historical failure.
3. **The moat is byte-frozen.** `_apply_consensus`, the consensus/withstands mechanism, and `extract_verdict_confidence` are byte-frozen vs commit `acc4973`. Never edit them. Guard tests: `tests/test_6bclean_seam_guard.py`, `tests/test_6bclean_attestation.py` (non-vacuous in both directions).
4. **Labels are true by construction** (next section). A case that cannot prove its label does not ship.

## Core invariant: labels true by construction

This is the entire reason this repo exists. A case is admissible **only** if:

1. Every `expected_safety_flags` code is in the active pack's `taxonomy_snapshot.json` `KNOWN_TAXONOMY_CODES`.
2. The `injection_recipe` block specifies `defect_type`, `mutated_projection`, `mutated_field_or_span`, `pre_value`, `post_value`. The recipe **is** the label justification.
3. Clean negatives have `injection_recipe: null` and `expected_safety_flags: []`. They are first-class, not residue.
4. Every flag has a `production_judges`-resident owner per `tier1_owners`. Flags whose only owner is a declared-but-not-running judge must be excluded or reassigned, never silently scored.

Do not append to `examples/*.jsonl` without the lint script passing.

## Pack system (current state)

- **The active pack is the contract.** The core resolves taxonomy, tiers, tier1 owners, judge roster identity (`production_judges`, which judges run and in what order), and lens authority (`lenses`, the per-role "codes you may raise") from the active pack's snapshot at runtime via `lithrim_bench/harness/pack.py`. Never a hardcoded path.
- **Identity vs deployment split:** the pack carries WHICH judges run; the per-role deployment binding (provider, model id, capability flags: core-side `_ROLE_DEPLOYMENT`) stays in core. A pack must never carry infra. A pack judge with no core deployment fails clean at council construction.
- **Never hand-edit a snapshot.** Refresh via `scripts/snapshot_taxonomy.py`. The `lenses` block and role names are bench-curated, and the script carries them over on re-snapshot. If lint fails after a backend taxonomy change, re-snapshot; never soft-pass cases.
- **Default pack is the neutral `_core`** (`packs/_core/`). The core boots and grades standalone with no Pro pack on disk (`tests/test_neutral_default.py`).
- **`healthcare` is opt-in** (`LITHRIM_BENCH_PACK=healthcare`) and **physically external** at `../lithrim-pack-healthcare/` (local git, NOT pushed). Discovery order: installed entry point (`lithrim_bench.packs`) -> `LITHRIM_BENCH_PACKS_DIR` -> in-repo `packs/`. The dev/CI suite sets `LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare`; clinical tests skip-when-absent (root `conftest.py`: `RELOCATED` + `NEEDS_PACK` sets). The taxonomy snapshot lives at `../lithrim-pack-healthcare/healthcare/taxonomy_snapshot.json`.
- **CE's shipped tree is clinical-free** except two sanctioned samples: `packs/clinical_scribe/` + `examples/clinical_scribe/` (the ONLY clinical surface, pinned by the A2 sweep in `tests/test_pack_dist.py`) and the non-clinical `packs/support_ticket_qa/` standalone fixture. Do not add clinical content anywhere else in CE; the curated Pro healthcare pack stays external. HPACK builds in the pack repo, never back in this core.

## Plugin registry = the Core/Pro boundary

- `lithrim_bench/harness/plugins.py` is the unified registry for packs, grounding contracts, judge providers, and tools (`PluginManifest`/`PackManifest`: `kind/tier/transport/implements`). Spec: `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md`.
- **`tier` is the single Core/Pro boundary field.** Under a denying `License` (`LITHRIM_BENCH_LICENSE`; default permit-all so grading is byte-identical), a `tier: pro` plugin is ABSENT (fails closed), never stubbed.
- **R-GUARD:** the license gate sits ONLY on the ontology/taxonomy/prompts `*_path` resolvers, NEVER on `pack_tiers`/`pack_tier1_owners`/`pack_lenses`/`pack_production_judges` (gating those re-enters the frozen council import).
- Adding a contract/pack/tool is **manifest-only, zero engine edits** (the open/closed test, `tests/test_plugin_phase1.py`). `plugins.py` stays stdlib+pydantic only.
- Tools are `kind: tool` declarations; **MCP is the tool-transport standard** (`transport: service` for external MCP/HTTP, `in_process` for SDK tools); secrets via env, never the manifest. Legacy `EvalProfile.tools`/`kb_bindings` are inert; the live plane is `kind: tool` + `verification_contracts`.

## Prompt plane (post CE-PACK-6b/6c)

- **UI-authored prompts are the single live prompt source**: the in-process grade always builds `build_authored_semantic_stage`; `semantic_stage` is never `None`. All clinical prompt builders (`build_prompt`, `build_source_message_prompt`) are DELETED; `evaluate()` raises sentinels on the transcript/source_message branches. Do not resurrect a default council.
- The honest bar is **no live clinical CODE** in `runtime/council/` (pinned by `tests/test_6bclean_attestation.py::test_no_live_clinical_code`); frozen carve-out comments and the load-bearing `HIPAA_*` config keys are enumerated passive residual.
- `phi_redaction` is kept-as-generic in core (domain-agnostic PII/PHI mechanism, live via observation agents).

Full cycle-by-cycle history and justifications: `docs/CLAUDE_MD_ARCHIVE.md` (PACK-1..2c, CE-PACK-*, PLUGIN-1, TOOL-1, PACK-DIST-1 + amendment). Deferred work lives there too (PACK-DIST-2, TOOL-2, the `frontend` kind, HPACK).

## Stack + conventions

- Python 3.10+, Pydantic v2 (no v1 syntax), Pandas for Synthea CSV loading.
- v1 synthesis is deterministic and offline by design: `synthesizers/transcript.py` and `synthesizers/scribe_artifact.py` are template-based on purpose (byte-deterministic given the same Synthea seed + injector params). No LLM dependency for generation.
- Default sync; async only where it earns its keep (it doesn't, for a CLI generator).
- `ruff check .` / `ruff format .`. Tests with `pytest`, runnable without network and without the Synthea CSV (use fixtures). Always confirm you are testing against the LATEST fixtures before recalibrating anything.
- No comments unless the why is non-obvious.

## What this repo is NOT

- Not a copy of `lithrim-backend`; the backend imports nothing from here.
- Not an LLM training pipeline: it generates eval cases; scoring lives in `lithrim-backend`.
- Not a FHIR validator (that is etlp-mapper). We consume FHIR, we don't validate it.

## Docs map

- `docs/PAPER_OUTLINE.md`: the locked, one-claim paper outline. Never weaken the claim without explicit user say-so.
- `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`: the spec this engine implements; defects D1-D7 are the acceptance criteria.
- `docs/ARCHITECTURE.md`: engine diagram + module responsibilities.
- `docs/LITHRIM_BENCH_PRODUCT_SPEC.md`: developer-product framing.
- `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md`: **LOCKED 2026-06-04.** THE product: UI-driven author->process loop (create judges -> create flags -> run processing) with a first-class why/when/who/what audit trail. Build sequence UAP-1..4.
- `docs/specs/SPEC_CONVERSATIONAL_FIRST.md`: **LOCKED 2026-06-19 (owner). PRODUCT INVARIANT, never violate.** The center conversation IS the product; the artifact pane is auxiliary, CLOSED by default, opened only on explicit drill-down. Everything actionable renders as inline gen-UI (verdict, per-judge votes, clinician-verdict/dissent form, calibration). A demo or agent that operates the chrome (pane tabs, top-bar Run) to advance has FAILED the invariant. 3-layer contract: `apps/shell/src/app.jsx` (`open=false`), `genui/VerdictCard` + `genui/ClinicianVerdict`, `apps/bff/agent/loop.py` (`focus_artifact` only on explicit "open the full X").
- `docs/CLAUDE_MD_ARCHIVE.md`: provenance record for every rule above.

<!-- devloop:begin -->
## .devloop workflow

This repo uses the `.devloop/` monitor / executor / critic workflow. Before acting as a
dev agent here, read `.devloop/personas/MONITOR.md` (or `EXECUTOR.md` / `CRITIC.md` for
those roles). Slash commands: `/devloop-status`, `/devloop-resume`, `/devloop-kickoff`,
`/devloop-audit`, `/devloop-critique`, `/devloop-close-phase`, `/devloop-expand-driver`,
`/devloop-run` (autonomous: native subagents + Gate 0 + evidence capture, opt-in module).

**Standing preferences (never override):** no autostart services (curl /health first) ·
no auto-commit (stage + propose) · no push/publish without owner approval · plan-review
before code · tests-first (write acceptance tests RED before code; deterministic gate is
supreme, LLM-judge critic is the weak complement) · per-repo atomic commits ·
diagnose-before-edit (evidence block + tag CONFIRMED / INFERRED / HYPOTHESIS).

**Project commands** — test: `pytest -q` · ui-test: `cd apps/shell && npx vitest run` · lint: `ruff check .` · build: `cd apps/shell && npm run build`.
**Services** (curl /health before use; never autostart):
- BFF=:8787 (make up / make bff; check via `make health`)
- UI=:5180 (make up / make ui)
<!-- devloop:end -->
