# Assessment — incorporate "grade once → durable replayable artifact" into the core persistence model

> Owner steer (2026-06-18): *"look into our backend's data persistence model — these kinds of actions
> need to be incorporated from the core."* The "action" is capture-baseline / replay-from-a-persisted-grade
> (the thing that was missing when every `run it` on an ingested case dead-ended at "no captured baseline").
> This is a **design assessment + recommendation** — no code yet. All findings CONFIRMED against the source.

## TL;DR
The persistence model already has the right bones: a single **`ProvenanceStore` Protocol** with an
immutable **blob tier** (source-of-truth, RLVR/lake-bound) behind it, the moat byte-frozen *above* that
seam. **An in_process/live grade already persists a full provenance blob.** The only reason "grade once →
replay free" doesn't work is that the replay path reads a *separate committed fixture* (`dataset.baseline`)
instead of the blob it already wrote — and the blob isn't **addressable by `(agent, case_id)`** nor
**shaped for replay**. So this isn't a new subsystem; it's **closing three small gaps so the blob the
grade persists IS the baseline** — exactly the lakehouse north-star ("the lake is the durable asset; the
DB/replay/report are projections of it"). All three gaps live *above* the frozen consensus seam.

## The current model (CONFIRMED)
- **One seam:** `ProvenanceStore` Protocol (`runtime/pipeline/provenance.py:22`) — `save(provenance, *,
  agent_id)` + `find_by_id(pipeline_run_id)`. Impls: `NoOpProvenanceStore` (hermetic default) +
  `SqliteProvenanceStore` (product path → `PIPELINE_RUNS`). This is *the* extension point — S3/PG impls
  "drop in behind the same seam." Mongo retired; persistence is **bench-side** (`:8002` owns none).
- **What a grade persists:** the nested `result['provenance']` → a `PipelineProvenance` doc in
  `PIPELINE_RUNS` (doc-shim: one `json TEXT` col, id=`pipeline_run_id`, fk=`org_id`, `agent_id` backfilled
  as an extra field). **All three grade paths now persist** (replay+live+in_process — S-BS-52 closed). A
  *second* store (`harness/persist.py`) also writes `out/<ws>/<case_id>.json` + a `records(case_id PK, json)`
  row — a per-case mirror, keyed by `case_id`, idempotent.
- **Blob tier built; projection deferred:** WS-6d shipped the blob tier only; the SQL projection (verdict/
  scores/ECE/cost as queryable columns) is S-BS-38, deliberately **not** built (don't add projection
  columns early — S-BS-4 doc-shim-minimal). Swappable to Mongo/PG/S3 behind the Protocol.
- **Moat boundary:** `_apply_consensus` + the consensus/withstands mechanism are **byte-frozen vs
  `acc4973`**. Persistence is freely modifiable *behind the ProvenanceStore seam, above the frozen
  consensus*. **Precedent (S-BS-72):** the withstands ruling was embedded into the run blob via a
  *post-save* `find_by_id → embed → re-insert` patch above the seam, returned dict byte-identical. That is
  the exact pattern this work follows.

## The three gaps (CONFIRMED)
1. **Addressability** — you cannot fetch "the latest run for `(agent, case_id)`". `PIPELINE_RUNS` is keyed
   by `pipeline_run_id` only (+ an `org_id` fk scan); `agent_id` rides as an un-indexed doc field, and
   **`case_id` is not on `PipelineProvenance` at all** (it carries `request_hash` + `artifact_type`, not the
   case id). So the blob the grade just wrote can't be found by the case it graded.
2. **Shape** — `grade_replay` expects a full **`PipelineResult`** (top-level `verdict`/`gate_decision`/
   `findings`/`semantic:StageResult` + nested `provenance`). The persisted blob is the **`provenance`
   sub-tree alone** — the replay-critical `semantic` (judge votes/evidence that `ground`/`composite`/
   `calibration` read) sits *inside* it as `stage_results['semantic']`, not at the top level. A nesting/
   scope mismatch, not a field rename.
3. **Resolution** — `run_eval.py:307-317` *hard-fails* (`raise SystemExit "no captured baseline"`) when
   `dataset.baseline is None`. It never tries the persisted blob.

## Recommended design — "the persisted grade IS the baseline" (replay-from-provenance)
Three moves, all **above the frozen seam**, all **extending the one `ProvenanceStore` Protocol** — no new
abstraction, no model edit, no `_apply_consensus` touch.

**Move 1 — make the blob addressable by `(agent, case_id)`.**
- Persist `case_id` as an **extra doc field** on the run blob (exactly how `agent_id` already rides —
  set in `_persist_run_provenance` / the orchestrator save), **not** a `PipelineProvenance` model edit and
  **not** a projection column (stays doc-shim-minimal, S-BS-4-clean). The case id is in scope at every grade.
- Add `ProvenanceStore.latest_for(agent_id, case_id) -> dict | None` to the Protocol (+ the Sqlite impl: a
  doc-shim query filtering `agent_id`+`case_id` via `json_extract`, newest by the blob's own `timestamp`).
  `NoOp` returns `None`. This is the seam's natural next read method (it already has `find_by_id`/`list_all`).

**Move 2 — a pure shape adapter `provenance_to_result(blob) -> PipelineResult-dict`.**
- Lift the blob's `verdict`/`gate_decision`/`findings` to the top level, promote
  `stage_results['semantic']` → the top-level `semantic` StageResult, and re-nest the blob under
  `provenance`. A pure function above the seam; the moat path never sees it. *(Alternative considered:
  persist the full `PipelineResult` instead of the `provenance` sub-tree — heavier, changes the stored
  shape, and `PipelineProvenance` is the canonical lake doc; the adapter is the lighter, shape-stable choice.)*

**Move 3 — resolve the baseline from the store when no fixture exists.**
- `run_eval.py:307-317`: replace the hard `raise` with *"if `dataset.baseline is None`, try
  `store.latest_for(agent, case_id)` → `provenance_to_result` → `grade_replay`-equivalent; only raise if
  the store has nothing."* Either an automatic fallback or an explicit `mode='auto'` on `Dataset`.

**Net effect:** a grade persists the blob (already happens) → the next run resolves its baseline *from that
blob* at $0. No separate "promote baseline" step, no committed fixture for ingested cases, no new concept.
The blob **is** the baseline — and `replay`, `report`, the cohort matrix, calibration, and the RLVR
corrections all read the same source-of-truth, which is the whole point of the lakehouse tier.

## Why this is the right altitude (not a bolt-on)
- It **unifies two concepts** that are accidentally separate today: "captured baseline" (a committed
  fixture) and "persisted grade output" (the blob). After this, there is one — the blob.
- It makes the persistence model serve **every** downstream action uniformly (replay/report/cohort/
  calibration/RLVR all read `latest_for`/`find_by_id`), which is the documented north-star
  ("a report is reconstructable from the blobs; the projection is rebuildable, never the source of truth").
- It is **forward-compatible by construction**: `latest_for` + the adapter live behind the same Protocol
  that S3/PG will implement; nothing here blocks or pre-commits the projection tier (S-BS-38).

## Moat & invariant safety
- **Frozen seam untouched:** Moves 1–3 are all above `_apply_consensus` (the S-BS-72 precedent: enrich/read
  the blob via post-save patches + new store reads). The in_process grade's returned dict stays
  byte-identical (the adapter runs only on the *replay* resolution path).
- **A-SAFE preserved + improved:** the **first** grade of an ingested case is still a PAID in_process/live
  run the human authorizes via the cost modal — the agent can't fire it. After that, every "run it" is a
  $0 replay of the captured blob. So the cost-gate moves to *"pay once to capture, replay free forever,"*
  which is both honest and exactly what the demo wants (and resolves AHA-BLOCKER #1 from the experience
  audit — the hero case's verdict becomes a repeatable $0 replay after one authorized grade).

## Open tensions to respect (from the persistence ledger)
- **S-BS-68** (append-only vs `created_at` re-stamp on upsert): order `latest_for` by the blob's own
  `timestamp` field, not `created_at` (which re-stamps on the withstands re-insert). Runs are distinct rows
  (fresh `pipeline_run_id` per grade), so "latest" is well-defined.
- **S-BS-4 / "no projection columns early":** keep `case_id`/`agent_id` as **doc fields queried via
  `json_extract`**, not promoted to indexed relational columns, unless/until the projection phase (S-BS-38
  P1) decides otherwise. (If desktop-scale scans ever bite, promoting *only the two key columns* — like
  `id`/`fk` — is the doc-shim-clean escalation, distinct from projection columns.)
- **Two stores (`PIPELINE_RUNS` vs `records`):** prefer the `ProvenanceStore`/`PIPELINE_RUNS` tier as the
  replay source (canonical, lake-bound, agent-scoped) over the `harness/persist.py` `records` mirror
  (per-case, no agent dimension, workspace-fs). The `records` store stays the human-readable mirror.

## Phasing (maps onto the existing S-BS-38 plan)
- **P1 — replay-from-provenance (this assessment):** Moves 1–3. Closes "grade once → replay free" + unblocks
  the $0 aha. Bench-side, behind the one Protocol, moat-frozen.
- **P2 — projection tier (S-BS-38 P1, already planned):** promote verdict/scores/ECE/cost to queryable
  columns; `latest_for` then becomes an indexed lookup instead of a `json_extract` scan.
- **P3 — object-store blob backend (S-BS-38 P2):** `S3/AdlsProvenanceStore` behind the same seam (VPC tier).

## Recommendation
Build **P1** as a small, well-scoped, moat-frozen change behind the `ProvenanceStore` Protocol. It is the
cheapest path to the repeatable $0 aha **and** it's the architecturally-correct version of what you asked
for — the persistence model treating every graded output as a durable, addressable, replayable artifact,
which is the lakehouse thesis. It does not pre-commit P2/P3. **Awaiting your go before writing code** (this
session has been findings-only); the first build step would be tests-first against `latest_for` + the
adapter + the replay-fallback branch, with the byte-identical-moat attestation.
