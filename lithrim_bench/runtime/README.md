# `runtime/` — the 2026-05-29 in-process salvage (the "M1 spine")

> **Status: not on the active composition path except where the harness imports it
> explicitly. Touch with care — the council consensus seam in `council/` is byte-frozen
> (see the repo-root CLAUDE.md non-negotiables).**

## What this is

The vendored, in-process copy of an upstream compliance council + the
`/v1/pipeline/evaluate` orchestrator path, produced by the **2026-05-29 bottoms-up
"salvage-and-compose" session**. It let the council run fully in-process (no Mongo /
Pinecone / Celery / etlp-mapper) and reproduced a `scribe_v1` verdict end-to-end —
the "M1 spine."

- `council/` — vendored `ComplianceCouncil` + judges + `safety_flags` + `_compat` stubs
- `pipeline/` — vendored orchestrator/stages/models; `retrieval.py` + `provenance.py` are **stubs**
- `services/artifact_evaluator.py` — structural/artifact stages stubbed (skip)
- driven by `../backends/local_pipeline.py`, run via `../../scripts/run_local_scribe.py`

## History

On **2026-05-30** the project pivoted from bottom-up vendoring to a **top-down,
compose-over-live** walking skeleton: the milestone path composed over live external
services, and this in-process M1 was demoted to the *last* milestone (the fully-local /
airgapped runtime). The in-process council was later re-adopted as the default grading
path (`LITHRIM_COUNCIL_BACKEND` unset/`in_process`).

## When (and how) to touch the stubbed parts

Before reviving the stubbed pipeline pieces, re-verify:

- imports against the *current* `backends/base.py` + `backends/lithrim_pipeline.py` (both
  changed since 2026-05-29 — `BackendVerdict` gained structural / rich-finding fields);
- grounding/retrieval is **stubbed** (no Pinecone, no local vector) — a revival must wire a
  local vector store (sqlite-vec vs numpy is an open decision);
- this is a snapshot of an upstream pipeline service; reconcile against upstream drift
  before extending it.
