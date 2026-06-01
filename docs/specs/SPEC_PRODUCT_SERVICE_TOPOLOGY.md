# SPEC: Lithrim Product Service Topology

> The service architecture for the product: **a strangler-fig that retires the Mongo backend, not a fix of it.** Sequencing = **(B) strangle incrementally** (user 2026-06-01).
> Companion to [`SPEC_PRODUCT_SHELL.md`](SPEC_PRODUCT_SHELL.md) (the UI layer) and [`../LITHRIM_BENCH_PRODUCT_SPEC.md`](../LITHRIM_BENCH_PRODUCT_SPEC.md) (product/pricing).
> **Status:** v1 — direction approved; the one load-bearing assumption (v2-council Mongo-separability) is tagged below and gated for verification at consolidation kickoff.

---

## Decision

Do **not** de-Mongo / retrofit the existing `lithrim-backend` for the product. **Complete the strangler-fig already underway** and retire Mongo from the product path. The clean, Mongo-free nucleus already exists:

- **M1** — vendored the council **in-process, no Mongo/Pinecone/Celery/etlp-mapper** (`lithrim_bench/runtime/council/`). *(CONFIRMED separable for the v1 council.)*
- **WS-1** — the **SQLite config plane** + ontology data model.
- **WS-3a** — the **DSPy generator / verification** module (`lithrim_bench/verification/`), composing over `:3031`, Mongo-free.

The live `:8002` Mongo backend becomes a **dev-time dependency being strangled**, not a product component. Mongo is **retired from the product** (it survives only in the legacy hosted backend, if kept alive separately).

> Why not fix the backend: it's a Celery + Mongo monolith built for the old hosted SaaS; de-Mongo-ing it is more work + risk than growing the clean core, and it doesn't fit the 3-layer deployable shape. The DSPy generator already lives in the clean core — it never needed the backend.

## Sequencing — (B) strangle incrementally

The shell **BFF targets the harness as it already composes over live `:8002`/`:3031`**, so the shell (WS-5) **never blocks** on consolidation. The Python-Layer consolidation runs as a **parallel track**; as each capability internalizes (council → in-process, KB → local/`:8002`-kb, etc.), the BFF re-points from live-`:8002` to in-process. The live Mongo backend is scaffolding, removed when the last piece is strangled.

## Topology — 3 layers + DB

| Layer | What | Notes |
|---|---|---|
| **UI Platform** | Tauri/React shell ([`SPEC_PRODUCT_SHELL.md`](SPEC_PRODUCT_SHELL.md)) | the **BFF = the Python Layer's API**; they unify |
| **Python Layer** | FastAPI: harness + **ported v2 council** + copilot/DSPy + agentic/tools/MCP/websearch | the consolidated nucleus; persistence behind a **repository interface** |
| **ETLP Services** | `etlp-mapper` `:3031` (Clojure): connectors (pinecone/s3/adls/http ingest) + JUTE mapper + execution | already a clean separate service; **desktop packaging = bundled JVM sidecar (uberjar + JRE)** — the packaging long pole |
| **DB** | **SQLite** (desktop/BYOK) ↔ **PG/Aurora** (VPC) behind a repository interface | the **WS-1 doc-shim** already chose a swappable shape — lean into it. **Mongo retired.** |

## The consolidation track (WS-6, reframed + pulled forward, parallel)

Port the **validated v2 council** Mongo-free — extends the M1 v1 salvage → v2 (cross-provider trio + llama-veto-approve + calibration + the NKA patches + prompts). **PORT, do not rewrite** — this is validated IP (the calibration + NKA work is load-bearing). Swap persistence Mongo → SQLite/PG behind the repository interface.

- **First step / GATE: audit `../lithrim-backend`** to confirm (a) the **v2 council's Mongo-coupling surface** — *CONFIRMED separable for v1 by M1; v2 separability is **INFERRED** (same architecture, cross-provider config + prompt deltas), verify before porting*; (b) the **persistence surface** to swap (`pipeline_runs`, `eval_packs`/`eval_cases`, `artifact_profiles`, …).

### Phased breakdown (WS-6a…e) — broken out 2026-06-01 (user)

Folded the `../lithrim-backend` **baseline** in as step **a** — you can't cleanly audit/strangle a dirty tree, and the pending WIP holds moat/paper-relevant work that shouldn't be lost:

| Phase | Scope | Repo |
|---|---|---|
| **WS-6a** | **Backend baseline** — curate + commit the pending `../lithrim-backend` WIP (8 modified files = the structural-verdict/severity remediation, S-P1-15-adjacent; + ~12 untracked docs/scripts/tests; + transient `out/`/`test-results/`). Atomic per-concern commits, gitignore transients, **backend tests green first**. *Baseline + preserve — NOT invest (strangle-not-fix holds).* | `../lithrim-backend` |
| **WS-6b** | **Consolidation audit (the GATE)** — read-only: confirm the v2-council Mongo-coupling surface (INFERRED→CONFIRMED) + map the persistence surface (`pipeline_runs`, `eval_packs`/`eval_cases`, `artifact_profiles`). Produces the port plan. *(Unblocked by 6a's clean tree.)* | reads `../lithrim-backend` |
| **WS-6c** | **Port the v2 council Mongo-free** → `lithrim_bench/runtime/council/` (extends the M1 v1 salvage → v2; **PORT, not rewrite** the calibration/NKA/prompt IP), **behind the frozen harness/§10 BFF contract.** | `lithrim-bench` |
| **WS-6d** | **Persistence swap** — repository interface + SQLite(desktop)/PG(VPC); **Mongo out.** | `lithrim-bench` |
| **WS-6e** | **ETLP JVM sidecar** packaging — coordinate with [`SPEC_PRODUCT_SHELL.md`](SPEC_PRODUCT_SHELL.md) WS-5e. | `lithrim-bench` |

The **frozen-contract rule** (WS-6c+ ports *behind* `run_eval.run` / `report.composite` / the §10 v1 BFF surface — it swaps the implementation, never the signature) keeps this whole track **parallel-safe with the WS-5c shell work**.

## Packaging tiers

| Tier | Shape |
|---|---|
| **Open-core desktop (BYOK)** | Tauri shell + Python-Layer sidecar + ETLP JVM sidecar + SQLite — the e2e packaged experience |
| **Open-core Docker** | Python Layer + ETLP as containers + SQLite/PG — internal hosting |
| **Premium hosted** | same containers in the customer VPC + desktop app as a thin **webview client** to the deployment + premium features (consistent with the no-US-hosted trust wedge) |

## Honest flags

- This **pulls WS-6 (the heaviest, last milestone) forward** as a parallel track — defensible (the product needs a Mongo-free service + the shell needs something clean to sit on), but it's a real chunk, not a side quest.
- **Port-don't-rewrite the v2 council** — losing the validated calibration/NKA/prompt IP is the chief risk of "new service."
- **JVM-in-desktop (ETLP sidecar) is the packaging long pole** — derisk JRE+uberjar bundling early.
- The nucleus has **v1**; the product wants **v2** — the v1→v2 port is the real cost (not greenfield, but not free).

## Relationship to the `.devloop` plan

- **WS-5 → WS-5e** (shell program, [`SPEC_PRODUCT_SHELL.md`](SPEC_PRODUCT_SHELL.md) §8) — proceeds against the harness now (sequencing B); the BFF is the Python Layer's API.
- **WS-6, reframed** = this consolidation track (port v2 council Mongo-free + persistence swap), parallel; opens with the `../lithrim-backend` audit.
- Both need the `.devloop` task pack re-scoped to match (the next monitor bookkeeping action).

## References
- [`SPEC_PRODUCT_SHELL.md`](SPEC_PRODUCT_SHELL.md) · [`../LITHRIM_BENCH_PRODUCT_SPEC.md`](../LITHRIM_BENCH_PRODUCT_SPEC.md)
- M1 (council-separable, Mongo-free): `.devloop/tasks/TASK_PACK_bench-salvage.json#M1` + `lithrim_bench/runtime/council/`
- WS-1 SQLite config plane (doc-shim, swappable): `.devloop/state/STREAM_bench-salvage.md` (S-BS-4)
- WS-3a DSPy/verification: `lithrim_bench/verification/`
