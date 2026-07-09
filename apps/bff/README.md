# Lithrim Shell BFF (`apps/bff`)

The local **FastAPI backend-for-frontend** — the *judge-capability API v1*.
It is the React↔Python bridge: a thin app that imports
`lithrim_bench.harness` + `scripts/run_eval` and fronts them for the React/Tauri shell.

The BFF targets the **harness** (which can compose over external services such as the
`:3031` JUTE mapper). No Mongo, no separate backend checkout. One BFF, two packagings
(Tauri sidecar desktop ↔ containerized VPC).

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
real, paid council run on the configured backend — `LITHRIM_COUNCIL_BACKEND` selects it:
unset/`in_process` (the OSS default, BYO Azure/Claude key, fully local) or `http` (a live
hosted council deployment). See [`SETUP.md`](../../SETUP.md).

Override the BFF target with `VITE_BFF_URL` (e.g. an absolute Tauri/VPC URL); unset, the
client uses a relative base through the vite proxy.

## v1 endpoint surface (locked)

| Endpoint | Returns |
|---|---|
| `POST /v1/run-eval` `{agent?="ws0_default", live?=false}` | the `run_eval.run()` record (`composite`, `grounded`, `calibration`, `provenance`, …) **+ a folded `calibration_check([record])`** + `grade_path`. `live=false` is the **$0 replay** default; `live=true` is exactly one paid council call. |
| `GET /v1/corpus` | `{rows: [...]}` — `corpus.read_corpus()` (corpus-row/1); empty until a correction is written. |
| `GET /v1/ontology` `{agent?}` | the agent's committed ontology JSON (the same "stored ontology" sent to the live council). **Read-only in v1.** |
| `GET /health` | `{status: "ok"}` |

> `PUT /v1/ontology` is **deferred** to the phase that wires an ontology editor. The
> folded `calibration_check` is a degenerate **N=1 diagnostic** on the seed baseline
> (`ece==0.5`, small-N caveat) — **not** the locked calibration gate.

## Test

```bash
pytest tests/test_ws5_bff.py          # hermetic round-trip smoke (replay, no network)
```
