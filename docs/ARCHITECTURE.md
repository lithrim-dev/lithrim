# Architecture

What ships in this repo, and how the pieces connect. For what each layer can
honestly claim, see [`CAPABILITY_CARD.md`](CAPABILITY_CARD.md); for the hands-on
setup path, see [`../SETUP.md`](../SETUP.md).

## The grade path

One evaluation run, end to end:

```
                 case (case_id · response · context)
                                │
                                ▼
              ┌───────────────────────────────────┐
              │  judge council                    │  lithrim_bench/runtime/council/
              │  multi-model LLM judges, per-role │
              │  lenses, evidence-based consensus,│
              │  logprob-calibrated confidence    │
              └───────────────┬───────────────────┘
                              │  findings + calibrated confidence
                              ▼
              ┌───────────────────────────────────┐
              │  grounding floor (deterministic)  │  lithrim_bench/harness/grounding.py
              │  contract_type → executor, checked│
              │  against a pinned reference       │
              │  (record / schema / terminology)  │
              └───────────────┬───────────────────┘
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
     suppress a wrong   block a missed      inconclusive →
     finding            defect              surfaced, never flipped
                              │
                              ▼
              ┌───────────────────────────────────┐
              │  verdict + immutable audit record │  lithrim_bench/harness/audit.py,
              │  (votes, floor decision, evidence,│  persist.py
              │  provenance), replayable at $0   │
              └───────────────────────────────────┘
```

The floor is three-state by design: grounded-true, grounded-false, or
inconclusive. An unconfigured or unreachable grounding tool resolves to
inconclusive, the run still grades, it just says what it could not verify.

## The services

`docker compose up` starts three services; the first two are the core stack:

```
 browser ──▶  UI (React shell, :5180)          apps/shell/
                │  /v1 …
                ▼
              BFF (FastAPI, :8787)             apps/bff/
                │  imports lithrim_bench.harness (in-process grade,
                │  config plane, run trail)
                │
                ├──▶ your model provider (BYOK: OpenAI / Azure /
                │    Anthropic / Gemini / OpenAI-compatible)
                │
                └──▶ JUTE mapper (:3031, optional)   external service, bundled
                     ingest of arbitrary agent-trace JSON
```

- **BFF** (`apps/bff/`), the backend-for-frontend the UI talks to. It fronts the
  harness: agents (the things under evaluation), ontologies, judges, cases, runs,
  packs, provider config, and the conversational assistant loop.
- **UI** (`apps/shell/`), the conversational evaluation workspace. The center
  conversation is the primary surface; verdicts, votes, and calibration render as
  inline cards over real BFF data.
- **JUTE mapper** (`:3031`), a separate service (bundled in compose) used only
  to ingest arbitrary/nested JSON: the harness generates a JUTE transform that
  maps your shape into eval cases, previews it, and pins it on approval. Never
  needed for grading authored cases or the offline demo; see
  [`JUTE_MAPPER_ADDON.md`](JUTE_MAPPER_ADDON.md). JUTE (a JSON-to-JSON transform
  DSL) is the only server-executed transform language, models never emit
  server-executed Python/JS.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `lithrim_bench/harness/` | The config plane and grade engine: agents/ontologies/judges in a local SQLite config DB, in-process grading (`grade.py`), the grounding floor (`grounding.py`), pack resolution (`pack.py`), the plugin registry (`plugins.py`), audit + persistence (`audit.py`, `persist.py`), replay (`replay.py`). |
| `lithrim_bench/runtime/council/` | The judge council: role prompts, multi-model dispatch, evidence-based consensus, calibrated-confidence extraction. The consensus mechanism is frozen against a pinned baseline (guard tests keep it byte-stable). |
| `lithrim_bench/verification/` | The JUTE plane: generating, gating, and pinning JSON-transform templates for ingestion and extraction floors; MCP client for tool-grounded checks. |
| `lithrim_bench/` (top level) | Case generation and admissibility: encounter schema, Synthea CSV/FHIR loaders, defect injectors, the packager that enforces by-construction labels, taxonomy handling. |
| `packs/` | Shipped packs: the neutral `_core` default, the synthetic `clinical_scribe` sample, the non-clinical `support_ticket_qa` fixture. |
| `apps/bff/` | FastAPI backend-for-frontend (`:8787`) + the conversational agent loop. |
| `apps/shell/` | React/Vite UI (`:5180`): conversation, gen-UI cards, artifact pane. |
| `scripts/` | Operational entry points: the offline demo, taxonomy snapshot, lint gates. |
| `repro/` | The published study's reproduction surface (see [`../REPRODUCING.md`](../REPRODUCING.md)). |

## Packs: the domain is a plugin

The core is domain-agnostic. A **pack** supplies a domain: ontology, taxonomy
snapshot, judge roster + per-role lenses, prompts, grounding floors, and optional
seed agents. Resolution order (`lithrim_bench/harness/pack.py`):

1. an installed entry point in the `lithrim_bench.packs` group (the pip path);
2. `LITHRIM_BENCH_PACKS_DIR`, external directories (the drop-in / air-gap path),
   pinned active with `LITHRIM_BENCH_PACK`;
3. the in-repo `packs/`.

With no pack configured, the core stays on the neutral `_core` default and grades
fine. An undiscoverable pack fails closed, never a silent fallback. The pack
carries *which* judges run; the per-role deployment binding (provider, model id)
stays in core, so a pack never carries infra or secrets.

## Plugins and tools

`lithrim_bench/harness/plugins.py` is one registry for packs, grounding
contracts, judge providers, and tools. Adding one is manifest-only, zero engine
edits (pinned by an open/closed test). Tools are `kind: tool` declarations; MCP
is the tool-transport standard (`transport: service` for external MCP/HTTP
services, `in_process` for SDK tools). Secrets ride environment variables, never
a manifest. The contract details are in
[`specs/SPEC_TOOL_CONNECTORS.md`](specs/SPEC_TOOL_CONNECTORS.md).

## The run trail

Every grade produces an append-only audit record: which cases, which judges on
which models, every vote with its confidence, the floor's decision and evidence,
and the active config. Records are replayable, `make demo` replays a captured
council baseline through the live floor at $0, and the immutable record is what
makes a verdict auditable after the fact.

## By-construction labels

Where this repo ships labeled benchmark cases, the label is generated, not
annotated: a case is admissible only if its injection recipe (defect type,
mutated field/span, pre/post values) fully justifies the expected flags, every
flag code exists in the active pack's taxonomy snapshot, and every flag has an
owner in the running judge roster. Clean negatives are first-class. The spec is
[`EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`](EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md).
