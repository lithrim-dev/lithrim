# `runtime/` — PARKED: 2026-05-29 in-process salvage (the "M1 spine")

> **Status: parked / not on the active path. Do NOT wire into WS-0..WS-5.**
> **Touch this only at WS-6 (compartmentalize-local).**

## What this is

The vendored, in-process copy of the `lithrim-backend` compliance council + the
`/v1/pipeline/evaluate` orchestrator path, produced by the **2026-05-29 bottoms-up
"salvage-and-compose" session**. It let the council run fully in-process (no Mongo /
Pinecone / Celery / etlp-mapper) and reproduced a `scribe_v1` verdict end-to-end —
the "M1 spine."

- `council/` — vendored `ComplianceCouncil` + judges + `safety_flags` + `_compat` stubs
- `pipeline/` — vendored orchestrator/stages/models; `retrieval.py` + `provenance.py` are **stubs**
- `services/artifact_evaluator.py` — structural/artifact stages stubbed (skip)
- driven by `../backends/local_pipeline.py`, run via `../../scripts/run_local_scribe.py`

## Why it's parked

On **2026-05-30** the `bench-salvage` stream pivoted from bottom-up vendoring to a
**top-down, compose-over-live** walking-skeleton (commit `24d1239`): WS-0..WS-5 call the
live `:8002` / `:3031` services. The in-process M1 was explicitly **demoted to WS-6
(compartmentalize-local)** — the *last* milestone, when the product needs a fully-local /
airgapped runtime. It is **not** the current spine, and nothing on the WS-0..WS-5 path
imports it.

## When (and how) to touch

Revisit at **WS-6 (compartmentalize-local)**. Before reviving, re-verify:

- imports against the *current* `backends/base.py` + `backends/lithrim_pipeline.py` (both
  changed since 2026-05-29 — `BackendVerdict` gained structural / rich-finding fields);
- grounding/retrieval is **stubbed** (no Pinecone, no local vector) — WS-6 must wire a local
  vector store (the sqlite-vec / numpy decision, seam `S-BS-5`);
- this is a snapshot of `lithrim-backend@mvp-ready`; reconcile against upstream drift.

## Provenance

- `docs/SALVAGE_FINDINGS_2026-05-29.md` — salvage map + composition spec
- `docs/HANDOFF_BENCH_SALVAGE_2026-05-29.md` — the session handoff (file inventory + M1 result)
- plan: `~/.claude/plans/toasty-twirling-forest.md`
