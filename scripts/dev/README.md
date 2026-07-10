# Dev stack — start / stop the local Lithrim services

One script + a Makefile to run the two local services the shell journey needs, without
re-discovering the env/pyenv/port dance each time.

| service | what | port | runtime |
|---|---|---|---|
| **BFF** | `uvicorn app:app` (`apps/bff`) — the judge-capability API the journey calls | **8787** | `debuglithrim` pyenv |
| **UI** | vite dev server (`apps/shell`) — the shell + activation journey | **5180** | node / npm |

## Usage

```bash
make up            # start both (BFF + UI), wait for health
make status        # ports + health at a glance
make health        # BFF up? + run a $0 replay grade and print the votes
make down          # stop both
make restart       # stop + start
make logs-bff      # tail -f .devstack/bff.log
make logs-ui       # tail -f .devstack/ui.log
make probe         # per-deployment Azure health (see below) — tiny PAID calls
```

Or call the script directly for per-service control:

```bash
scripts/dev/devstack.sh start bff      # just the BFF
scripts/dev/devstack.sh stop ui
scripts/dev/devstack.sh restart bff
```

Logs and pidfiles live in `.devstack/` (gitignored). Processes are `nohup`-detached, so
they survive the shell that launched them closing.

## How config loads (so live grades work)

- The BFF starts with **CWD = repo root**, and the vendored council reads its Azure config
  from the **repo-root `.env`** (`runtime/council/settings.py`, `env_file=".env"`).
- That `.env` is a copy of the lithrim-backend env and carries many backend-only vars; the
  council settings declare only the ~16 they use and set **`extra="ignore"`**, so the extras
  don't crash startup. (Before that fix, the live/in-process council died with
  `extra_forbidden` the moment the backend `.env` grew.)
- **Replay grades are `$0`** and don't touch the council. **Live grades** ("Run live" →
  `in_process`) make real **paid Azure** calls and need the Azure deployments healthy.

## When "Run live" fails

A live grade can fail with `semantic_evaluation_error: no healthy upstream` (or a timeout)
when one of the council's **Azure deployments** is unhealthy — typically a serverless/MaaS
judge (`Mistral-Large-3` / `Llama-4-Maverick`), which lapse more often than the standard
`gpt-4.1`. To find the culprit:

```bash
make probe         # fires 1 token at each deployment; prints OK / FAIL per judge
```

Then check that deployment in the Azure portal (`<your-azure-resource>` resource → Deployments).
The bench is fine in this case — it's Azure-side health.

## Requirements

- The **`debuglithrim` pyenv** with the `[bff]` extra installed (`pip install -e '.[bff]'`
  in that env). Override the env name with `PYENV_VERSION=...`.
- Node + npm for the UI (`npm install` is run automatically if `node_modules` is missing).
- A repo-root `.env` with the `AZURE_OPENAI_*` + `LITHRIM_LLM_PROVIDER=azure` +
  `COMPLIANCE_COUNCIL_VERSION=v2` values (only needed for **live**; replay works without it).
- Override ports with `LITHRIM_BFF_PORT` / `LITHRIM_UI_PORT`.
