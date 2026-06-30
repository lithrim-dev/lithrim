# SPEC — Run Audit Trail (the immutable, rehydratable record of every grade)

> **Status:** DRAFT for review · authored 2026-06-30
> **Stream:** `bench-salvage` · phases `RUNTRAIL-0 … RUNTRAIL-4`
> **Why:** Lithrim's core pillar is an **auditable trail of every grade on every
> case** — the AuditRecord *is* the product. Live demo work surfaced that the
> current persistence is not delivering this: the default ($0 replay) path
> **overwrites** a prior run row instead of appending, and a winning cohort grade
> left **no per-run audit blob** in the run store. This spec locks the invariant
> and the two-tier contract, then phases the fixes.

---

## 0. Evidence (the gaps this spec closes)

CONFIRMED against current code 2026-06-30:

- `lithrim_bench/runtime/pipeline/provenance.py:75-77` — `pipeline_run_id` is a
  fresh `uuid4` per `evaluate()`, but **re-running the SAME id UPSERTS to one row**
  (`ON CONFLICT(id) DO UPDATE`). The doc-shim is idempotent-on-id, not append.
- `apps/bff/app.py:1140` (comment on `_pipeline_run_id`) — *"replay carries the
  baseline's id; in_process/live carry a fresh id."* So the **default replay path
  reuses the baseline `run_id` → a re-grade overwrites the baseline row**, the
  trail does not grow per execution.
- `lithrim_bench/harness/persist.py:24-30,73` — `reports_store`/`persist()` is keyed
  by `case_id` **PRIMARY KEY** with UPSERT → last-write-wins. A second, case-keyed
  store overlapping the run store, with no crisp "which one is the trail" contract.
- `collections.py:231` — `PIPELINE_RUNS = DocShimCollection(..., versioned=True)`
  (PERSIST-2a): a same-`run_id` re-save DOES copy-on-write archive the prior doc into
  the `_history` shadow on BOTH backends — archival is **not** missing. The real gap is
  **read-back parity at the store interface**: `SqliteProvenanceStore` exposes no
  accessor that surfaces the `_history` archive for a `run_id`. `list_versions`
  (`provenance.py:128-137`) queries the **live** `PIPELINE_RUNS` head rows for a
  `(agent, case)` lineage (`find_by_json`), not a run's archived prior versions; so at
  the interface a same-id re-save's prior is unreadable.
  *(Corrected at RUNTRAIL-0 close — the original "SQLite has no history table" was stale;
  verified against `collections.py:231` + `provenance.py:128-137` 2026-06-30.)*

Net: the append-only, uniquely-id'd, timestamped, rehydratable run-history store
*exists* (`pipeline_runs`, keyed by `id`, `created_at`, `find_by_id`; archival exists
via `versioned=True`) but is **not fed uniformly, the archive is not readable at the
store interface, and the head row is overwritten on the default replay path**.

---

## 1. The invariant (the one rule)

> **Every grade execution produces exactly one immutable, uniquely-identified,
> timestamped, rehydratable run-history record. The run-history is append-only:
> a record is never overwritten or deleted.**

This holds across the full cross-product of entrypoints and modes:

| Entrypoint | Modes |
|---|---|
| single-case (`POST /v1/run-eval`) | replay · in_process · live |
| cohort (`POST /v1/cases/grade`) | replay · in_process · live |
| `_core` in-process and non-`_core` subprocess (pack) paths | all of the above |

Re-grading the same case N times yields **N distinct records**, each with its own
`run_id` and `ts`. Nothing about a grade — including a $0 replay — overwrites a
prior record.

---

## 2. The two-tier contract (SoT vs projection)

Per the established blob-SoT + rebuildable-projection design:

1. **Run-history (`pipeline_runs`) is the append-only Source of Truth.** One row
   per grade execution, keyed by `run_id`. Immutable. The audit trail.
2. **`reports_store` is a DERIVED PROJECTION** — "latest result per `(workspace,
   case_id)`". It MAY be last-write-wins (that is its job). It is **rebuildable
   from the run-history** and is never the trail of record.

A consumer asking "what happened, when, with what inputs" reads the run-history.
A consumer asking "what is the current verdict for this case" reads the projection.

---

## 3. The audit record (blob shape — self-sufficient to rehydrate)

Each `pipeline_runs.doc` blob MUST carry enough to **rehydrate the run without
re-grading** (replay-from-blob → same verdict). Required fields:

- **Identity:** `pipeline_run_id` (uuid4), `created_at` (UTC ISO-8601),
  `workspace_id`, `agent_id`, `case_id`, `grade_path` (`replay|in_process|live`).
  **DONE (RUNTRAIL-7, 2026-06-30):** `grade_path` is now stamped onto the persisted
  `PipelineProvenance` blob at persist time for ALL three paths (live/replay via
  `_persist_run_provenance`; in_process via the post-save `_enrich_run_blob` patch —
  above the frozen seam, moat untouched) and projected in the read API. `replay_of` IS
  persisted (RUNTRAIL-1). (The RUNTRAIL-6 finding — `grade_path` computed but unpersisted
  — is closed.)
- **Lineage:** `replay_of` — the `run_id` a replay was derived from (`null` for a
  fresh in_process/live run). A replay is a NEW record that POINTS AT its baseline;
  it never overwrites it. **LOCKED (RUNTRAIL-1):** the replay baseline is the
  most-recent **authoritative** grade for `(agent, case)` — the newest row whose
  `replay_of` is falsy (`SqliteProvenanceStore.latest_authoritative_for`, on every
  store tier). Replays therefore point at the real grade and **never chain**
  replay→replay. This is read-only resolution plumbing; it does NOT alter the
  freshness/`grade_signature` head (`latest_for`/`is_fresh` unchanged).
- **Inputs (provenance):** ontology version/identifier, judge roster + per-role
  config (model, k, temperature, criterion, assigned lens), `loaded_plugins` /
  `active_pack` / `pack_tier` (already on `PipelineProvenance`), and a reference or
  content-hash of the graded case payload.
- **Outputs:** council votes, findings, grounding `validator_outputs` (incl. each
  contract's `disproved`/`reason`), final `verdict`, `verdict_flipped_by_stage`.

A blob that cannot rehydrate its verdict is not a valid audit record.

---

## 4. Rehydration

- `find_by_id(run_id)` returns the full blob (exists: `provenance.py`,
  `GET /v1/runs/{id}/audit` at `app.py:3464-3478`).
- A `rehydrate(run_id)` path reconstructs the graded result from the stored blob
  alone — no live model call, no re-grade — and yields the same verdict. This is
  the proof the record is self-sufficient (§3). **LOCKED (RUNTRAIL-4):**
  `provenance.rehydrate(run_id, *, db_path=None)` = `find_by_id` →
  `provenance_to_result` (the existing adapter, reused unchanged); offline/$0 by
  construction (imports no grade/model module). Missing id → `LookupError`.

---

## 5. Phasing (the seams)

Each phase is one `.devloop` cycle (driver + executor + audit + critique).

- **RUNTRAIL-0 — contract RED test (this is the foundation).** Acceptance tests
  that assert §1 across entrypoints × modes and §2/§3/§4 shape — written to **fail
  against current code** (replay overwrite; cohort trail holes; missing
  `replay_of`; archive not readable at the store interface). No implementation. The
  RED suite is the spine. *(CLOSED 2026-06-30, commit `c3b7425`; G2 partial holds.)*
- **RUNTRAIL-1 — fresh `run_id` per execution + `replay_of` lineage.** Replay mints
  a new id, records `replay_of=<baseline>`, never overwrites. Kills the default-path
  overwrite. *(CLOSED 2026-06-30, commits `fff05ea`..`b1bbf94`; G1+G3 green; inline
  critique CLEAN.)*
- **RUNTRAIL-2 — readable append-only history.** Add a store-interface accessor
  (`list_history(run_id)`-shaped) that surfaces the already-archived `_history` prior
  versions — archival exists (`versioned=True`); this exposes it so the trail's prior
  states are auditable, not just the head. *(CLOSED 2026-06-30, commits `9f0cf8a`..`fb9b5c8`;
  G4 green; `DocShimCollection.history` + `list_history` on all 4 store tiers.)*
- **RUNTRAIL-3 — projection contract.** `reports_store` documented + enforced as a
  derived projection, rebuildable from the run-history (`rebuild_projection()`).
  *(CLOSED 2026-06-30, commits `8373e9d`..`cb1ee10`; G5 green; latest-per-case from the
  append-only run-history.)*
- **RUNTRAIL-4 — rehydrate + replay-from-blob.** `rehydrate(run_id)` path + test
  proving a stored blob reconstructs the verdict with zero model calls.
  *(CLOSED 2026-06-30, commits `f11c9d0`..`8d019dc`; G6 green; contract fully enforced —
  `tests/test_run_audit_trail.py` = 7 passed / 0 xfailed.)*
- **RUNTRAIL-5 — cohort end-to-end guard.** A BFF-layer test pinning the original
  symptom: a cohort grade appends one addressable audit record per case; re-grade grows
  the trail. *(CLOSED 2026-06-30, commit `12b301f`; green-on-first-run + non-vacuous —
  RUNTRAIL-1 already closed the cohort path.)*
- **RUNTRAIL-6 — read-surface (consumable trail).** Project `replay_of` in
  `_run_audit_report`/`_run_summary` + add `GET /v1/runs/{id}/history` (`list_history`)
  and `/rehydrate`. *(CLOSED 2026-06-30, commits `3998d7f`..`e6a8eb0`; `grade_path` split
  to RUNTRAIL-7.)*
- **RUNTRAIL-7 — persist + project `grade_path`.** Stamp `grade_path`
  (`replay|in_process|live`) onto the persisted blob at persist time (all 3 paths, moat
  untouched), then surface it in the audit/list responses. *(CLOSED 2026-06-30, commits
  `7fe95b5`..`54d0ba9`; closes seam `S-RUNTRAIL-6-1`.)*

**RUNTRAIL stream COMPLETE 2026-06-30.** The §1 invariant is enforced by tests (G1–G6,
`7/0`); the trail is append-only with `replay_of`+`grade_path` lineage, readable via the
API (`/v1/runs`, `/audit`, `/history`, `/rehydrate`), and any run rehydrates `$0`. Moat
byte-frozen vs `acc4973` across the whole stream (0-delta; zero moat/council/taxonomy
files touched). Live $0 proof: a replay cohort grade grew the trail +14 with `replay_of`
lineage + `rehydrate` reconstructed a verdict (2026-06-30, `snomed_subsumption` ws).

---

## 6. Out of scope (guardrails)

- **The moat.** `_apply_consensus`, the consensus/withstands mechanism, and
  `signals.py` are byte-frozen vs `acc4973` and MUST NOT be touched. This work is
  persistence plumbing **above** the seam.
- **Object-store mover** (`storage_ref` / S3/ADLS offload of blobs) — deferred
  (`cases_store.py` 3b note); the trail stays inline-blob for now.
- **New verdict semantics** — verdicts are unchanged; we only change *how runs are
  recorded*, never what a run decides.
- **UI** — the `tool-propose_run_all` component bug is a separate task, not this
  stream.

---

## 7. Acceptance (the invariant, as gates)

- **G1.** N re-grades of one case ⇒ N distinct `pipeline_runs` rows (unique
  `run_id`+`ts`), zero overwrites — every mode, every entrypoint.
- **G2.** A cohort grade of M cases ⇒ M new run-history rows, each rehydratable.
- **G3.** A replay row carries `replay_of` = its baseline `run_id`; the baseline
  row is unchanged.
- **G4.** The SQLite store surfaces the archived prior versions for a `run_id` at the
  store interface (read-back parity — archival already exists via `versioned=True`; a
  same-id re-save's prior must be readable, not just the head).
- **G5.** `reports_store` is rebuildable from the run-history alone.
- **G6.** `rehydrate(run_id)` reconstructs the verdict from the blob with no model
  call.

Each gate is a test, written first, in the phase that delivers it (G1–G4 asserted
RED in RUNTRAIL-0).
