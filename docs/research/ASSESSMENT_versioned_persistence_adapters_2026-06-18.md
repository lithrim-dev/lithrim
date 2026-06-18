# Assessment — adopt etlp-mapper's versioned-blob + PG/SQLite adapter pattern for bench persistence & audit

> Owner steer (2026-06-18): *"have Postgres/SQLite adapters, leverage Postgres versioning (historical
> changes) like etlp-mapper, also for audit ledgers; users may start with SQLite (reduced capabilities)
> but that streamlines persistence + auditability."* This studies the etlp-mapper / etlp-mapper-sqlite
> reference (CONFIRMED) and maps it onto the bench's `ProvenanceStore` + audit ledger. **Design proposal —
> no code yet.** It also subsumes and upgrades the replay-from-provenance P1.

## The reference pattern (etlp-mapper, CONFIRMED)
A **temporal live + `_history` model with copy-on-write versioning**, behind a backend-agnostic store, with
a **PG/SQLite adapter split**:
- **Two tables:** live `mappings(id, content JSONB, org_id, created_at, updated_at)` holds the *current*
  version; `mappings_history(id, original_id→mappings.id, txnid, content JSONB, org_id, created_at,
  updated_at)` is **append-only** and holds every *superseded* version.
- **Copy-on-write:** a `BEFORE UPDATE` trigger (`insert_mapping_history()`) snapshots the **OLD** row into
  history, stamped with `txid_current()` as the version id; a second trigger bumps `updated_at`. History
  captures the version being *replaced*; the live row is the head.
- **Version-addressable history API:** `GET /mappings/{id}/_history` (list versions, org-scoped JOIN on
  `original_id`) + `GET /mappings/{id}/_history/{txnid}` (point-lookup). `txnid` is the client-facing
  version key. (Read-only — "going back" = re-PUT an old blob, no privileged rollback.)
- **Adapter split:** `pgtypes.clj` (JSONB via `PGobject`) vs `sqlitetypes.clj` (JSON-as-TEXT), swapped by
  **load order**; the migration set is swapped by `JDBC_URL` at boot. **The handler + SQL layer is
  byte-identical across both backends** — that's the whole point: one store, two adapters.
- **SQLite parity (etlp-mapper-sqlite, CONFIRMED):** same `mappings`+`_history` shape, but `content TEXT`,
  **SQLite triggers** (no plpgsql), `txnid` = a `strftime+randomblob` surrogate (no `txid_current()`), a
  nested self-UPDATE for `updated_at` (can't assign `NEW.*`), and a `WHEN content changed` guard to prevent
  recursion/double-write. **Reduced vs PG:** no JSONB query/GIN index (opaque TEXT), no stored procedures,
  no real txn id, single-writer concurrency. **Kept identical:** the API, the history model, the blob shape,
  the application code, org-scoping.

## The bench today (CONFIRMED)
- **`ProvenanceStore` Protocol** (`runtime/pipeline/provenance.py:22`, `save`/`find_by_id`) — the run-blob
  tier; the docstring already commits *"PG/Aurora drops in later behind this same interface (VPC tier,
  future phase)."* `SqliteProvenanceStore` writes one `PIPELINE_RUNS` doc-shim row per run.
- **The audit ledger is a SEPARATE substrate** (`harness/audit.py`, table `config_audit`): a real relational
  append-only log — `AuditRecord` (why/when/who/what + `before`/`after` diff + `run_id`/`case_id`),
  `AuditLog` is **INSERT-only** ("immutability enforced by absence of update/delete"), `GET /v1/audit`.
- **Nothing is versioned today.** The config doc-shim `ON CONFLICT DO UPDATE` **overwrites** `json` +
  re-stamps `created_at` (S-BS-68) — last-write-wins, **no `_history` table, no version column**. The audit
  log preserves the **change-stream (diffs)** but does **not** version the config **objects** — you cannot
  reconstruct "the exact judge config as of version X." (Provenance partly dodges via a fresh `uuid4` per
  run, but config-plane objects keyed on a stable id are genuinely clobbered.)
- **What the bench lacks:** (a) **no migration framework** (schema is inline `CREATE TABLE IF NOT EXISTS`
  re-run per call), (b) **no psycopg/asyncpg dep** (stdlib `sqlite3` only — needs a `[pg]` extra), (c) no
  `_history`/temporal table, (d) no trigger/stored-proc surface.
- **Moat-frozen boundary:** all persistence/audit sits **above** `_apply_consensus` (byte-frozen vs
  `acc4973`) — a provenance sink *after* `evaluate()` + the config-write audit log. A PG adapter +
  versioning is **moat-safe by construction**.

## The design — port the pattern onto the two bench stores, behind one adapter seam
**Adopt the temporal live+`_history` model + the PG/SQLite adapter split, with versioning *below* the
`save()`/`insert()` seam so the engine and handlers stay backend-agnostic** (exactly etlp-mapper's
"byte-identical handlers across backends").

**1. Two stores get versioning — both above the moat:**
- **Run-provenance blobs** (`ProvenanceStore`/`PIPELINE_RUNS`): each grade becomes a **version** of
  `(agent, case_id)`; the head is the latest, `_history` is every prior grade. This is *the calibration
  audit trail* — "here's how the verdict changed as I tuned `risk_judge`" — and the head is the
  replay-from-provenance baseline (P1 folds in here).
- **Config-plane objects** (agent / judge / ontology): add a `_history` shadow so a point-in-time object is
  reconstructable ("the judge config as of the version that produced this verdict"). This **complements**
  the existing diff-stream audit log (which stays) and is the *"I can prove what the config was"* half of
  the auditability moat.

**2. The adapter split (port the `pgtypes`/`sqlitetypes` seam to Python):**
- Extract store **interfaces**: `ProvenanceStore` exists; extract `CollectionStore` / `AuditStore` (today
  concrete `sqlite3`). Two impls each — `Sqlite*` (entry tier) + `Postgres*` (managed/VPC tier) — swapped
  by a **connection-factory / `LITHRIM_DB_URL`** (the Python analogue of etlp's `JDBC_URL` + load-order
  swap). A **JSON adapter** centralizes encode/decode (`json.dumps`→`text`/`jsonb`; `json.loads`→dict) so
  call sites pass plain dicts — the one boundary the engine sees.
- **Versioning mechanism = portable in-transaction copy-on-write by default** (snapshot-then-update in one
  txn), which works identically on SQLite **and** PG and is trivially testable — with **DB-side triggers as
  a PG-tier optimization** (the etlp plpgsql path, invisible to writers). Recommending portable-Python
  default over triggers-everywhere so versioning lives in *one* tested place, not split across two trigger
  dialects + a migration framework just to ship.
- **Version identity = `(original_id, txnid)`** like etlp — plus an **integer `seq`** for cheap monotonic
  ordering (an improvement; etlp's txnids aren't globally ordered). SQLite `txnid` = a ULID/timestamp
  surrogate; PG `txnid` = `txid_current()`.
- **`_history` read API** mirroring etlp: `GET …/_history` + `…/_history/{version}` (org-scoped on both
  tables). Read-only; "restore" = re-write an old blob.

**3. The reduced-SQLite / full-PG tiering (the user's framing):**
- **SQLite = the OSS/desktop entry tier:** same API, same history model, same blob shape; `content` as TEXT
  (no JSONB query/GIN), single-writer, Python copy-on-write. The stdlib-only core stays dependency-free.
- **Postgres = the Pro/VPC tier:** JSONB + (optional) plpgsql trigger versioning + concurrency + the
  projection columns (S-BS-38 P1) + system-versioned/temporal tables. This is the plugin **`tier: pro`**
  boundary (the registry's tier field is the Core/Pro line) and the deferred S-BS-38 SQLite→PG/Aurora
  swap, now *pulled forward with the versioning layer the user wants*.

## What this resolves / realizes
- **S-BS-68 (the `created_at` re-stamp / not-append-only):** the temporal model **is** the correct fix —
  scoped exactly to the blob/PIPELINE_RUNS tier the ledger flagged, made first-write-wins + versioned.
- **S-BS-38 (SQLite→PG/Aurora behind the one Protocol):** realized, with versioning on top.
- **Replay-from-provenance P1 + the freshness guard:** the **head version** is the replay baseline;
  a re-grade **appends a version** (never overwrites), so the history is the calibration journey; the
  pending **freshness** decision rides as a stamped grade-signature on each version (drift ⇒ the head is
  stale ⇒ prompt a re-grade). P1 is no longer a bolt-on — it's "read the head of the versioned blob."
- **The auditability moat ("I can prove it"):** versioned config objects + the append-only run history +
  the existing diff ledger = a reconstructable, point-in-time, tamper-evident record — the regulated-AI
  evidence story the pitch rests on.

## What the bench must add (the cost — be honest)
- A **migration framework** (today there is none) — needed for `_history` tables + (PG) types/triggers.
  Smallest viable: a tiny homegrown versioned-DDL runner (stdlib, OSS-clean) over `yoyo`/`alembic` to avoid
  a heavy dep in the core; the PG/Pro extra can pull a richer one.
- An optional **`[pg]` extra** (psycopg/asyncpg) — gated so the OSS/SQLite core stays stdlib-only.
- The **`_history` shadow tables + the copy-on-write store logic + the `_history` read API**, behind the
  extracted store interfaces.
- **Moat untouched:** every change is above `_apply_consensus`, below the `save()`/`insert()` seam.

## Revised phasing (delivers the aha cheaply, builds the foundation incrementally)
- **P1 — SQLite temporal model + replay-from-provenance (stdlib, OSS, no new deps):** add the `_history`
  shadow + in-transaction copy-on-write to the provenance + config stores; `latest_for(agent, case)` reads
  the head; replay reads the head + the freshness guard; the `_history` read API. **Resolves S-BS-68,
  delivers the $0 aha + the calibration history.** A minimal homegrown migration runner lands here.
- **P2 — extract the store interfaces + the adapter seam:** `CollectionStore`/`AuditStore` Protocols + the
  `LITHRIM_DB_URL` connection-factory + the JSON adapter; still SQLite-default. The clean PG-ready seam.
- **P3 — the Postgres tier (`[pg]`/VPC, `tier: pro`):** `Postgres*Store` impls — JSONB + plpgsql trigger
  versioning + the S-BS-38 projection columns + system-versioned tables. The managed/streamlined upgrade.

## Open decisions (for you)
1. **Versioning mechanism:** portable Python in-transaction copy-on-write (recommended — one tested place,
   works on both) vs DB-side triggers everywhere (etlp-exact, DB-enforced, two dialects + a migration home).
2. **Scope of P1:** version **both** stores (provenance + config objects) up front, or **provenance-only**
   first (delivers the aha) and config-object history in P2?
3. **Phasing:** SQLite-temporal-first (above — aha + S-BS-68 fix on stdlib, PG later) vs stand up the
   PG adapter sooner because the managed-tier auditability is the near-term pitch need.
4. **Migration framework:** tiny homegrown stdlib runner (keeps the core dep-free) vs adopt `yoyo`/`alembic`.

(Still pending from you: the **freshness** answer — "let me tell you something…" — which sets how the head
version's drift is handled. I'll fold it into P1's replay-resolution branch once you give it.)
