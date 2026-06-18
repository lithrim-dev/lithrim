# Driver, `bench-salvage` phase `PERSIST-2b`: config-object versioning (`_history` shadow) + the `_history` read API

> **Bundle ID:** `bench-salvage-phasePERSIST-2b-config-object-versioning-driver`
> **Version:** v1 · **Authored:** 2026-06-18 · **Hardness:** ROUTINE (monitor inline critique at close)
> Follows PERSIST-2a (`6d19079..6037159`); the second cycle of the PERSIST-2 program (arc in 2a driver §10).

---

## Scope note — why, and the owner decision

The auditability moat's two halves: the **why/when/who change-stream** (the `config_audit` ledger, append-only,
already shipped) and the **"prove what the config WAS"** object-version timeline (this cycle). The owner chose
the **etlp-faithful `_history` shadow** (copy-on-write shadow tables, symmetric with 2a's `pipeline_runs_history`
and the native shape for the 2c PG adapter) over a read-API-over-the-ledger projection — even though the ledger
already stores full `before`/`after` snapshots — for mechanism symmetry + to capture un-audited (seed) versions.

**The inherent asymmetry (CONFIRMED, not a shortcut):** `agent` + `judge` are **table-backed** (`agents` keyed
on `name`, `judges` on `role`, both written through the single `upsert_with_audit` chokepoint) → they get the
`_history` shadow. **`ontology` is file-backed** (`PUT /v1/ontology` writes `workdir/<agent>.json` + an
`AuditRecord(target.type='ontology', before, after)`) → it has **no table to shadow**, so its history is the
ledger projection (the snapshots already exist there). The read API is uniform; the backing differs by storage.

**Frozen-contract rule:** the config plane is nowhere near `_apply_consensus`; this is additive read + a
config-tier shadow. `_apply_consensus`/`extract_verdict_confidence` stay byte-frozen vs `acc4973`; 2a's
`PIPELINE_RUNS`/`DocShimCollection` versioning + the four config collections stay untouched.

---

## 1. Pre-flight (every cite read 2026-06-18)
- `lithrim_bench/harness/audit.py` — `config_audit` (INSERT-only: `seq` PK, `ts`, `actor_*`, `action`,
  `target_type`, `target_id`, `json=AuditRecord.model_dump_json()` carrying `before`/`after`); `AuditLog.query`
  (filter by `target_type`/`target_id`, ORDER BY `seq`); `upsert_with_audit` (the config-write chokepoint —
  reads `before` in-txn, upserts, records, ONE transaction); `delete_with_audit`.
- `lithrim_bench/harness/config.py:188 save_agent` / `judges.py:76 save_judge` — both route through
  `upsert_with_audit`; the upsert SQL re-stamps `created_at=excluded.created_at` (drop this → first-write-wins);
  `created_at` is WRITE-ONLY (never read for ordering/display — CONFIRMED, so the change is safe).
- `lithrim_bench/harness/collections.py` (2a) — `DocShimCollection.versioned` copy-on-write + `pipeline_runs_history`
  + `find_by_json`; the mechanism to mirror (config tables are NOT DocShimCollection — hand-rolled, same shape).
- `apps/bff/app.py` — `GET /v1/agent?name=` (query) · `GET /v1/judges/{role}` (path) · `PUT /v1/ontology?agent=`
  + the `target.type='ontology'` audit record · `GET /v1/audit` (`get_audit_endpoint` → `AuditLog.query`).

## 2. Deliverables (tests FIRST — §5, RED then GREEN)

### D1 — `lithrim_bench/harness/versioning.py` (new, stdlib)
- `archive_prior(conn, *, table, id_col, id_val, archived_at)` — in the caller's txn, if a row for `id_val`
  exists in `table`, snapshot its `(json, created_at)` into `{table}_history` (`hist_id` PK, `original_id`,
  `txnid=<archived_at>#<seq>`, monotonic `seq`, `json`, `created_at` PRESERVED, `archived_at`). Creates the
  `_history` schema if absent. The portable Python copy-on-write (mirrors 2a; the "one tested place").
- `list_versions(db_path, *, table, id_col, id_val) -> list[dict]` — the live head (version = `len(history)+1`,
  `status='current'`) + every `_history` row (`status='superseded'`, its `seq`/`archived_at`), newest-first.
- `version_at(db_path, *, table, id_col, id_val, version) -> dict | None` — the object at a specific version
  (head when `version == len(history)+1`, else the `_history` row `seq=version`).
- `ledger_history(db_path, *, target_type, target_id) -> list[dict]` — the file-backed/ledger projection: each
  `config_audit` record's `after` = a version (`version=seq`, `+ts/actor/action`), newest-first; for `ontology`.

### D2 — wire versioning into the config write path (agent + judge shadows)
- `harness/audit.py upsert_with_audit` + `delete_with_audit` gain an optional `version_spec={"table","id_col",
  "id_val"}`; when set, call `archive_prior(conn, ...)` in-txn BEFORE the upsert/delete — INDEPENDENT of
  `audit_log` (so seed + un-audited writes version too).
- `config.save_agent` / `judges.save_judge`: pass `version_spec` + DROP `created_at=excluded.created_at` from the
  upsert SQL (the live row keeps first-write `created_at`; the prior is archived). `delete_*` archive the final
  state before removal (the lifecycle is fully versioned).

### D3 — the `_history` read API (harness primitives already in D1) + BFF endpoints
- `GET /v1/agent/_history?name=` + `/v1/agent/_history/{version}?name=` (shadow-backed).
- `GET /v1/judges/{role}/_history` + `/v1/judges/{role}/_history/{version}` (shadow-backed).
- `GET /v1/ontology/_history?agent=` + `/v1/ontology/_history/{version}?agent=` (ledger-backed projection).
- Each returns `{versions: [...], current: <head object>}`; 404 on unknown id (mirror the GET routes).

### D4 — tests (§5) + `.devloop/sessions/session-bench-salvage-phasePERSIST-2b-2026-06-18.json`

## 3. Decisions (resolved at plan-review)
1. **Mechanism = etlp `_history` shadow** (OWNER-CHOSEN) for agent/judge; ledger-projection for the file-backed
   ontology (no table). 2. **`created_at` → first-write-wins** on the config tables (CONFIRMED safe — write-only).
3. **Versioning fires regardless of `audit_log`** (storage property, captures seed versions). 4. **Shared
   mechanism** in `harness/versioning.py` (config tables use it now; a follow-on may refactor 2a's
   `DocShimCollection` onto it — NOT this cycle, to keep 2a's critic-passed code untouched).

## 4. Scope guardrails — NOT in 2b
- NO PG / `[pg]` / adapter extraction (2c) · NO projection columns (2d) · NO UI/shell wiring · NO new dependency
  (stdlib sqlite3) · NO `_apply_consensus`/council/grade-path edit (0-delta vs `acc4973`) · do NOT re-touch 2a's
  `collections.py`/`PIPELINE_RUNS` versioning · NO `../lithrim-backend` edit · no autostart/push/publish.

## 5. Acceptance (each a test written FIRST)
- **A1 (agent/judge shadow + first-write-wins).** A 2nd `save_agent`/`save_judge` for the same id archives the
  prior into `{table}_history` (created_at PRESERVED) + the live row keeps first-write `created_at`; seed
  (un-audited) writes version too. `tests/test_persist2b.py::test_config_upsert_versions_into_history`.
- **A2 (read API / addressability).** `list_versions` returns `[current, …superseded]` newest-first;
  `version_at(k)` reconstructs the object at version k; `current` == the live row. `::test_list_versions_and_version_at`.
- **A3 (ontology via the ledger).** `ledger_history(ontology, agent)` projects the `config_audit` `after`-snapshots
  into the version timeline (file-backed object). `::test_ontology_history_from_the_ledger`.
- **A4 (BFF endpoints).** `GET /v1/{agent,judges,ontology}/…/_history[/{version}]` return the timelines; 404 on
  unknown id. `::test_history_endpoints` (debuglithrim + `importorskip fastapi`).
- **A5 (frozen / scope).** 2a's `PIPELINE_RUNS`/`DocShimCollection` versioning + the four config collections
  untouched; the audit ledger change-stream behavior unchanged (additive); `_apply_consensus` 0-delta vs
  `acc4973`; no new dep; `save_agent` without `audit_log` still works (back-compat) + now versions.
  `::test_frozen_and_scope`.

## 6. Commits (tests FIRST)
1. `test(persist): config-object _history shadow + read API — red`
2. `feat(persist): shared versioning primitive (archive + list_versions/version_at + ledger projection)`
3. `feat(persist): version agent/judge config writes into _history (first-write-wins created_at)`
4. `feat(persist): the _history read API (agent/judge shadow + ontology ledger projection)`
5. `docs(persist): PERSIST-2b session log`

## 7. Verification
A1–A5 PASS (RED before GREEN); full suite delta vs `89fd270`-baseline = no NEW failures (the 38 pre-existing
pack-drift stay, diff the set); ruff clean; no new dep; 2a versioning + `_apply_consensus` untouched; session log.
