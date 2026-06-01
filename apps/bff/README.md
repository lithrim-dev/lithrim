# Lithrim Shell BFF (`apps/bff`)

The local **FastAPI backend-for-frontend** — the *judge-capability API v1* (WS-5-BFF).
It is the React↔Python bridge from `SPEC_PRODUCT_SHELL.md` §5: a thin app that imports
`lithrim_bench.harness` + `scripts/run_eval` and fronts them for the React/Tauri shell.

Strangler-fig (sequencing B): the BFF targets the **harness**, which composes over live
`:8002`/`:3031`. No Mongo, no `../lithrim-backend`. One BFF, two packagings (Tauri sidecar
desktop ↔ containerized VPC) — WS-5e.

## Run (dev)

The BFF lives behind the `[bff]` optional extra (FastAPI/uvicorn/httpx are **not** in the
default install). From the repo root:

```bash
pip install -e ".[bff]"
uvicorn app:app --app-dir apps/bff --port 8787      # the judge-capability API
```

Then, in another shell, start the React shell — its vite dev proxy forwards `/v1` to `:8787`:

```bash
cd apps/shell && npm run dev                        # http://localhost:5180
```

In the shell (switch to **Shell** mode, top-center), press **Run eval** → the real
`run_eval.run()` composite renders in the right artifact pane. **Run live** opts into one
real, paid `:8002` council call (needs the services up + a valid `.live_env`).

Override the BFF target with `VITE_BFF_URL` (e.g. an absolute Tauri/VPC URL); unset, the
client uses a relative base through the vite proxy.

## v1 endpoint surface (locked, SPEC §10)

| Endpoint | Returns |
|---|---|
| `POST /v1/run-eval` `{agent?="ws0_default", live?=false}` | the `run_eval.run()` record (`composite`, `grounded`, `calibration`, `provenance`, …) **+ a folded `calibration_check([record])`** + `grade_path`. `live=false` is the **$0 replay** default; `live=true` is exactly one paid council call. |
| `GET /v1/corpus` | `{rows: [...]}` — `corpus.read_corpus()` (corpus-row/1); empty until a correction is written. |
| `GET /v1/ontology` `{agent?}` | the agent's committed ontology JSON (the same "stored ontology" sent to the live council). **Read-only in v1.** |
| `GET /health` | `{status: "ok"}` |

> `PUT /v1/ontology` is **deferred** to the phase that wires an ontology editor
> (WS-5c/WS-5d). The folded `calibration_check` is a degenerate **N=1 diagnostic** on the
> WS-0 baseline (`ece==0.5`, small-N caveat) — **not** the WS-4b locked calibration gate.

## Test

```bash
pytest tests/test_ws5_bff.py          # hermetic round-trip smoke (replay, no network)
```
