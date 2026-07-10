# Lithrim Bench (Community Edition)

A domain-agnostic evaluation harness for AI-generated artifacts: a configurable LLM judge
council plus a deterministic grounding floor, with by-construction labels and a first-class
audit trail. Synthetic clinical note review is the reference domain; the shipped core is
generic. Read `README.md` first; `SETUP.md` covers installation. This file guides both
human contributors and coding agents (`AGENTS.md` symlinks here).

## Orientation (read before editing)

- `README.md`: what this is, quickstart, intended use and limits.
- `docs/ARCHITECTURE.md`: engine diagram and module responsibilities.
- `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`: the spec the engine implements.
- `docs/CAPABILITY_CARD.md`: the honest capability and limits summary.
- `docs/specs/SPEC_TOOL_CONNECTORS.md`: the tool / MCP connector (grounding) plane.
- `docs/ONTOLOGY_FLAG_LIFECYCLE.md` and `docs/POLICY_HOLDOUT_HYGIENE.md`: flag lifecycle,
  calibration/holdout hygiene.
- `CONTRIBUTING.md`: dev setup, optional extras, PR expectations.

## Layout

- `lithrim_bench/`: the engine (generators, `harness/` config plane + grounding,
  `runtime/council/` judge council, `verification/`).
- `packs/`: neutral open packs (`_core` is the default; `clinical_scribe` is the sanctioned
  synthetic clinical sample; `support_ticket_qa` is a standalone non-clinical fixture).
- `apps/bff/` (FastAPI backend-for-frontend, port 8787) and `apps/shell/` (React UI, port 5180).
- `examples/`, `samples/`, `data/`: shipped sample corpora and data pointers (all synthetic).
- `tests/`: pytest suite; offline by design (LLM-dependent tests use mocks/replay). The full
  run needs the documented extras (see `CONTRIBUTING.md`); pack-dependent tests skip when the
  external pack is absent.

## Commands

- Test: `pytest -q`. On a fresh clone with the documented extras installed
  (`pip install -e ".[dev,council,verification,bff,agent]"`, see `CONTRIBUTING.md`) the suite
  runs with no model key and no external pack: pack-dependent tests skip when the pack is
  absent. A minimal `.[dev]` install collects cleanly but runs only a subset.
- With the external `healthcare` pack checked out as a sibling directory, the full dev suite is
  `LITHRIM_BENCH_PACK=healthcare LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare pytest -q`.
- Lint: `ruff check .` and `ruff format .` (the frozen council seam is excluded in `ruff.toml`).
- UI tests: `cd apps/shell && npx vitest run`. UI build: `cd apps/shell && npm run build`.
- Zero-cost demo: `make demo` (offline, no keys, no pack; shows the floor flipping a council
  PASS to BLOCK).
- Dev services: `make up` starts the BFF (`:8787`) and UI (`:5180`); `make health` checks them.
  Agent sessions: never autostart services; check health first and stop if they are down.

## Non-negotiables

1. **The moat is byte-frozen.** The consensus/withstands mechanism (`_apply_consensus`,
   `extract_verdict_confidence` in `lithrim_bench/runtime/council/`) is frozen against a pinned
   baseline. Never edit it. Guard tests: `tests/test_6bclean_seam_guard.py`,
   `tests/test_6bclean_attestation.py` (non-vacuous in both directions).
2. **Labels are true by construction.** A benchmark case is admissible only if every
   `expected_safety_flags` code exists in the active pack's `taxonomy_snapshot.json`, its
   `injection_recipe` fully justifies the label (defect type, mutated projection, field/span,
   pre/post values), and every flag has an owner in the running judge roster. Clean negatives
   (`injection_recipe: null`, empty flags) are first-class. A case that cannot prove its label
   does not ship.
3. **Sanctioned clinical surfaces are enumerated.** The tracked tree is clinical-free except
   for the deliberately sanctioned synthetic samples: `packs/clinical_scribe/` +
   `examples/clinical_scribe/`, `samples/quickstart/`,
   `tests/fixtures/subsumption_bidirectional/`, `repro/` (the published
   study's reproduction surface: sanitized corpus + graded ontologies; see
   `REPRODUCING.md`), `tests/fixtures/standalone/` (the standalone-demo case fixtures),
   `data/verification_packs/` (synthetic Synthea-derived FHIR validator corpora), and
   `apps/shell/public/demo/` (the demo narration audio). This is pinned by the clinical
   sweep in `tests/test_pack_dist.py`; do not add clinical content anywhere else. The curated
   `healthcare` domain pack is distributed separately and never merges back into this core.
4. **Never hand-edit a taxonomy snapshot.** Refresh via `scripts/snapshot_taxonomy.py`; the
   curated `lenses` block and role names are carried over on re-snapshot. If lint fails after
   a taxonomy change, re-snapshot; never soft-pass cases.

## Pack system

- The active pack is the contract: taxonomy, tiers, tier-1 owners, judge roster identity, and
  per-role lens authority all resolve from the active pack's snapshot at runtime via
  `lithrim_bench/harness/pack.py`. Never a hardcoded path.
- Identity vs deployment: the pack says WHICH judges run; the per-role deployment binding
  (provider, model id, capability flags) stays in core. A pack never carries infra or secrets.
- The default pack is the neutral `_core` (`packs/_core/`); the core boots and grades
  standalone with no domain pack on disk (`tests/test_neutral_default.py`).
- Discovery order: installed entry point (`lithrim_bench.packs`), then
  `LITHRIM_BENCH_PACKS_DIR`, then in-repo `packs/`. An undiscoverable pack fails closed
  (`FileNotFoundError`), never a silent fallback.

## Plugin registry and tools

- `lithrim_bench/harness/plugins.py` is the unified registry for packs, grounding contracts,
  judge providers, and tools (stdlib + pydantic only). `tier` is the single core/pro boundary
  field; under a denying license a `tier: pro` plugin is absent (fails closed), never stubbed.
- Adding a contract/pack/tool is manifest-only, zero engine edits (the open/closed test:
  `tests/test_plugin_phase1.py`).
- Tools are `kind: tool` declarations; MCP is the tool-transport standard (`transport:
  service` for external MCP/HTTP, `in_process` for SDK tools). Secrets ride env vars, never a
  manifest. See `docs/specs/SPEC_TOOL_CONNECTORS.md`.

## Stack and conventions

- Python 3.10+, Pydantic v2 (no v1 syntax). Default sync; async only where it earns its keep.
- Generation is deterministic and offline by design (template-based synthesizers,
  byte-deterministic given the same seed and injector params). No LLM dependency to generate.
- Tests must run without network and without the Synthea CSV (use fixtures).
- No code comments unless the why is non-obvious. Keep diffs minimal; no drive-by refactors
  or formatting passes on untouched lines.

## Working agreements (humans and agents)

- Diagnose before edit: post verbatim evidence (test output, JSON row, log line, file:line)
  before stating a diagnosis; verify which surface you are reading (live service vs stale
  state, latest fixture vs an old one) before concluding anything.
- Tests first: write the failing acceptance test, watch it fail for the right reason, then
  implement to green. The deterministic gate (tests, lint) is supreme.
- Scope is explicit: do what the issue/PR names; propose out-of-scope findings separately.
- Never push, publish, or deploy without maintainer approval; keep commits atomic.

## What this repo is NOT

- Not an LLM training pipeline: it generates and grades eval cases.
- Not a FHIR validator: it consumes FHIR-shaped artifacts, it does not validate them.
- Not a medical device and not clinically validated (see the README intended-use note). All
  bundled sample data is synthetic.
