# SPEC — PERSIST-3: the relational data model (single linked SSOT)

**Status:** PROPOSED 2026-06-19 (owner-confirmed: global DB + `workspace_id` column; content
as linked JSON, S3-movable per-workspace). Build sequence = **PERSIST-3a** (relational index +
backfill) → **PERSIST-3b** (object-store mover). The moat is untouched — all of this lives
ABOVE the frozen council seam (`_apply_consensus` / `extract_verdict_confidence` byte-frozen
vs `acc4973`).

## The claim

The bench has **one** source-of-truth database (Postgres or SQLite, selected by
`LITHRIM_DB_URL` — never both). Every durable object — workspaces, cases, evaluations,
reports, and the config plane (agents / judges / ontologies / audit) — lives in that one DB,
**FK-linked**, with `workspace_id` as the scoping dimension. Heavy content rides as JSON that
can relocate to per-workspace object storage **without breaking the link** (the row and its
foreign keys never move; only the bytes do).

This realizes the [[persistence-blob-projection-architecture]] blob+projection (lakehouse-lite)
model: the relational tables are the **projection/index** (identity + FKs + the small queryable
columns); the JSON / object-store payloads are the **blob tier**.

## Why (the deployment shape)

Today isolation is *physical*: a workspace is a directory (`out/workspaces/<name>/`) holding
two per-workspace SQLite files plus loose JSON/JSONL. That layout (a) scatters one logical
system across files + two SQLite DBs + a third (`ws0.sqlite`), and (b) **breaks under a single
shared DB** — pointing `LITHRIM_DB_URL` at one Postgres silently *merges* every workspace's
config + run-history, because the isolation was the filesystem, not a column.

The target deployment: a customer in their **VPC connects one Postgres** and points **each
workspace at its own storage bucket** they control. Relational identity/linkage in the DB;
bytes in customer-owned object storage, per-workspace. The `storage_ref` on each content row
resolves against the **bucket bound to that row's workspace** (`workspaces.manifest.storage`).

## Current state (what is stored where, today)

| Object | Today | In the single SSOT? |
|---|---|---|
| Workspaces (registry) | `out/workspaces/<name>/workspace.json` + `.active` pointer | ❌ files |
| Cases (corpus) | `out/.../ingested_cases.jsonl` + pack JSONL | ❌ files |
| Evaluations (run provenance) | `pipeline_runs` (+`_history`) | ✅ (PERSIST-2c) |
| Reports (per-case grade result) | `out/<case>.json` + `ws0.sqlite` `records` | ❌ files + a 3rd SQLite |
| Agents / judges / audit / `_history` | `config.sqlite` | ✅ (PERSIST-2c-3) — but **global**, not workspace-scoped |
| Ontology drafts | `ontology/<agent>.json` | ❌ files (history in `config_audit`) |

## Target schema (one DB, `workspace_id`-scoped, content as linked JSON)

```
workspaces        (workspace_id PK, manifest JSONB, created_at)            ← replaces workspace.json
active_workspace  (workspace_id FK, singleton)                            ← replaces the .active file
   │
   ├─< cases       (workspace_id FK, case_id, source, payload JSONB|storage_ref, created_at)
   │      │          PK(workspace_id, case_id)                            ← ingested_cases.jsonl
   │      └─< evaluations (run_id PK, workspace_id FK, case_id FK, agent,
   │             │          doc JSONB|storage_ref, ins_seq, +_history)    ← pipeline_runs, now FK-linked
   │             └─ reports (workspace_id FK, case_id FK, run_id FK,
   │                         verdict, scores JSONB, report JSONB|storage_ref)   ← ws0.sqlite + <case>.json
   │
   ├─< agents      (workspace_id FK, name, json, created_at)  + agents_history
   ├─< judges      (workspace_id FK, role, json, created_at)  + judges_history
   ├─< ontologies  (workspace_id FK, agent, ontology JSONB|storage_ref)   ← ontology/*.json
   └─< config_audit(workspace_id FK, seq, ts, actor, action, target, json)
```

### The blob seam (the "linked, S3-movable" rule)

Every content-bearing table carries the **same** column pair:

```
payload      JSONB  NULL   -- inline content (the default; bytes live in the DB)
storage_ref  TEXT   NULL   -- when set, bytes live in object storage at this key
-- INVARIANT: exactly one of (payload, storage_ref) is non-null.
```

A single resolver `read_blob(row, workspace)` returns the inline JSON or fetches
`storage_ref` from the bucket bound to `workspace` (`manifest.storage`). The **identity +
FKs never move**, so the link survives relocation. `storage_ref` is **reserved in 3a, unused**
— the column exists, the mover is 3b.

### Scoping (resolved)

**Global DB + `workspace_id` column** — multi-tenant-shaped. NOT PG-per-workspace: that
cannot share a single object-store deployment and re-fragments the SSOT. `workspace_id` on
every table is what makes "one DB, linked" both true and isolated. The factory + `Dialect`
(PERSIST-2c) already give PG-or-SQLite through one seam; 3a adds tables, not an engine.

## Build sequence

### PERSIST-3a — relational index + backfill (THIS cycle)

1. New tables: `workspaces`, `active_workspace`, `cases`, `reports`. Add `workspace_id`
   to `evaluations`/`pipeline_runs`, `agents`, `judges`, `ontologies`, `config_audit`
   (+ the `_history` shadows). All through the existing `db.connect` / `Dialect`.
2. Stores for the new tables (`workspace.py`, `picklist.py`, `persist.py` routed through the
   factory) — mirroring the config-plane store discipline (schema-on-connect, single-txn writes).
3. Backfill: `workspace.json → workspaces`, `.active → active_workspace`,
   `ingested_cases.jsonl → cases`, `<case>.json`/`ws0.sqlite` → `reports`, and stamp existing
   global config/eval rows with their `workspace_id`.
4. `storage_ref` column present on every content table but **unused** (inline JSONB only).

After 3a: cases + reports + the workspace registry are in the one SSOT, FK-linked, and a
single `LITHRIM_DB_URL` points the whole system — config, cases, runs, reports — at one DB.

### PERSIST-3b — object-store mover (follow-on, trigger when blob size justifies)

The `read_blob` / `write_blob` resolver + a `move_to_storage(row)` path + the per-workspace
bucket binding (`manifest.storage`). Inline⇄object-store, link-stable. Deferred per the
owner's "if need be."

## Acceptance criteria (PERSIST-3a — tests-first, RED before code)

- **A1** — schema: the new tables provision through `db.connect` on BOTH dialects (SQLite
  inline; Postgres via the factory under `LITHRIM_DB_URL`), `storage_ref` column present.
- **A2** — back-compat: with `LITHRIM_DB_URL` unset, behavior is byte-identical to pre-3a for
  the existing file/SQLite paths during the transition (no silent data loss; cases/reports
  still readable). The 38-failure suite baseline is unchanged (diff the FAILED set vs `89fd270`).
- **A3** — single linked SSOT (gated, live PG): author a workspace + ingest a case + grade it
  under `LITHRIM_DB_URL=postgres`; assert `workspaces`, `cases`, `evaluations`, `reports`,
  and the config rows ALL carry the same `workspace_id` and FK-resolve, with **zero** loose
  files written for those objects.
- **A4** — isolation: two workspaces in one DB do NOT see each other's cases / runs / config
  (the bug that one global PG would otherwise have).
- **A5** — moat: `_apply_consensus` / `extract_verdict_confidence` byte-frozen vs `acc4973`;
  in-process grade record byte-identical with the store on/off.

## Open questions

- **OQ-1** — transition: dual-write (files + DB) during 3a, or DB-authoritative with a
  one-shot backfill migration? Leaning DB-authoritative + a `yoyo` backfill (managed tier) /
  inline backfill (SQLite), with the file readers kept as a fallback until 3a is proven live.
- **OQ-2** — ontology: a first-class `ontologies` table (JSONB) vs keep file + the
  `config_audit` ledger projection (today's 2b posture). Leaning table for SSOT-completeness.
- **OQ-3** — `reports` as a stored table vs a pure view/projection of `evaluations` (the
  latest run's grade). Leaning a stored table (it mirrors `ws0.sqlite` `records` 1:1 and
  carries the small queryable columns), with `report` JSONB as the linked blob.
