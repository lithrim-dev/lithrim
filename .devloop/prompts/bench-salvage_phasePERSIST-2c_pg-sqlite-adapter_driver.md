# Driver, `bench-salvage` phase `PERSIST-2c`: the PG/SQLite adapter split + migration framework + tier:pro PostgresProvenanceStore

> **Bundle ID:** `bench-salvage-phasePERSIST-2c-pg-sqlite-adapter-driver`
> **Version:** v1 · **Authored:** 2026-06-18 · **Hardness:** HARD GATE (fresh critic)
> Third cycle of the PERSIST-2 program. Realizes the deferred **S-BS-38** (SQLite→PG/Aurora behind the one Protocol).

---

## Scope note — the owner decisions + the honesty bar

Owner chose (AskUserQuestion): **(1) seam + contract-tested PG impl** (not seam-only, not full
etlp-faithful-with-testcontainers) and **(2) yoyo-migrations** (not the homegrown stdlib runner,
not alembic).

**The hard constraint (CONFIRMED):** a real Postgres impl CANNOT be CI-live-tested offline
(testcontainers needs Docker + network, violating the bench's "tests runnable without network"
invariant), and the OSS core MUST stay stdlib-`sqlite3` + offline. So: the SQLite tier is the
100%-tested default; `psycopg`/`yoyo` live ONLY in the `[pg]` extra (never imported by the core —
pinned by a test); the **PostgresProvenanceStore ships contract-shaped + SQLite-proven, NOT
CI-live-verified** — the gated contract test (`LITHRIM_DB_URL=postgresql://…`) is its proof when
run against a real PG. Honesty-is-the-moat: this caveat is stated, not hidden.

**Target = the ProvenanceStore / `PIPELINE_RUNS` blob tier** (the S-BS-38 target — "PG/Aurora drops
in behind this same interface"). The config plane (agents/judges/`_history`) stays SQLite + adopts
the factory in a follow-on. Moat untouched: storage is above the `save()` seam; `_apply_consensus`
0-delta vs `acc4973`; 2a's `PIPELINE_RUNS`/`DocShimCollection` + 2b's `_history` shadow unchanged.

## Deliverables (built tests-first)
- **D1 `harness/backend.py`** — `resolve_db_url` (`LITHRIM_DB_URL`, the etlp `JDBC_URL` analogue;
  unset → SQLite default) + `backend_of` + `Dialect` (`?`/`%s`, `TEXT`/`JSONB`, JSON codec) +
  `make_provenance_store` (factory: SQLite default never-gated, Postgres tier:pro license-gated,
  lazy) + `provenance_store_for` (the grade-path precedence helper).
- **D2 `PostgresProvenanceStore`** (provenance.py) — a PARALLEL `ProvenanceStore` impl, psycopg-lazy,
  the same versioned copy-on-write (live `pipeline_runs` JSONB + `pipeline_runs_history`,
  first-write-wins `created_at`, `ins_seq` lineage order). `SqliteProvenanceStore` byte-identical.
- **D3 yoyo migrations** — `harness/migrations.py` (`apply_migrations`/`reset_provenance`, lazy yoyo) +
  `migrations/0001.provenance.sql` (the managed-tier schema). The SQLite core self-provisions inline.
- **D4 the `[pg]` extra** (`psycopg[binary]` + `yoyo-migrations`) + the factory's tier:pro gate +
  routing `run_eval` (in_process grade + replay resolve) through `provenance_store_for`.
- **D5 tests** (`tests/test_persist2c.py`, A1–A6) + the session log.

## Acceptance (each a test)
- **A1** url resolution + the factory (SQLite default / Postgres construction / `provenance_store_for`
  precedence). **A2** the Dialect (param + JSON type + the SQLite codec round-trip). **A3** the
  ProvenanceStore contract — SAME assertions vs SQLite (always) + Postgres (gated). **A4** the
  Postgres backend is tier:pro license-gated (fail-closed under deny; SQLite never gated). **A5** the
  PG store implements the Protocol + is importable WITHOUT psycopg (lazy). **A6** frozen/scope:
  SqliteProvenanceStore byte-identical; the core imports no DB driver at load; core deps unchanged
  (the `[pg]` extra carries them); `_apply_consensus` 0-delta vs `acc4973`; full suite byte-identical
  to the pre-2c baseline (zero regressions).

## Scope guardrails — NOT in 2c
- NO config-plane PG (agents/judges stay SQLite; the factory is ready for them — follow-on) · NO
  projection columns (2d) · NO testcontainers/Docker CI · NO live-PG CI gate (contract-test-gated) ·
  do NOT re-touch 2a/2b versioning or the frozen council · the core stays stdlib (no driver at load).

## Commits
`3c66db3` test red · `281fb05` backend seam + PG store · `6dc23a0` yoyo migrations + `[pg]` extra +
contract test · `04a36dd` route the grade path through the factory.

## Hardness — HARD GATE
New (gated) deps + the grade-path wiring + the tier:pro boundary, adjacent to the moat (though
0-delta). The fresh critic re-runs A1–A6 + the zero-regression diff + the acc4973 0-delta
independently, and audits the HONESTY of the PG-not-live-verified caveat (the deterministic gate
covers the SQLite side + the seam + the contract SHAPE; PG correctness is gated by construction).
