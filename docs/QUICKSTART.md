# Lithrim — Product Quickstart (the conversational eval platform)

Run the conversational, tool-grounded clinical-AI eval product locally: the 3-pane
shell + the in-process v2 council + the grounding floor + the audit trail. **The OSS
core is self-contained** — a real council run needs only a **BYO Azure or Claude key**.
**No `lithrim-backend`, no `:8002`, no Mongo.**

> Cost model: the `$0` **replay** is the default and needs **no key**. A real council
> run (the **Run eval** button's live path, or `run_eval --in-process`) is the human's
> explicit, cost-confirmed action and is the only thing that spends.

> The other quickstart in [`../README.md`](../README.md) is the *engine* (Synthea →
> labeled cases). This one is the *product*.

---

## 1. Prerequisites

- Python 3.10+
- Node 18+ (for the shell)
- One of, for a **paid** run (replay needs neither):
  - an **Azure OpenAI** endpoint + key (the default council provider), or
  - the **Claude** CLI authed locally (`claude` on PATH — the BYO-Claude provider; no API key).

## 2. Install

From the repo root:

```bash
pip install -e ".[bff,council,agent]"     # the BFF + the in-process council + the chat loop
cd apps/shell && npm i && cd ../..        # the React shell
```

The default `pip install -e .` is the offline pydantic+pandas engine only; the extras
above add the product surface (FastAPI/uvicorn, the vendored council, the chat agent).

## 3. Configure a key (only for a paid run)

Skip this section entirely if you only want the `$0` replay.

Set env vars (or a `.env` at the repo root). **Azure** (the default trio):

```bash
export AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com"
export AZURE_OPENAI_API_KEY="<your-key>"
# the three v2-council deployment names (risk / policy / faithfulness):
export AZURE_OPENAI_DEPLOYMENT_COUNCIL="gpt-4.1"
export AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3="<your-mistral-large-3-deployment>"
export AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK="<your-llama-4-maverick-deployment>"
```

**BYO-Claude** (no API key — uses your local `claude` CLI / desktop auth): authenticate
the CLI (`claude` once), then bind a judge's `model` to `byo-claude` via the authoring
flow (the chat or `PUT /v1/judges`). A judge with no model binding stays on Azure.

> **Standalone (the OSS default):** `LITHRIM_COUNCIL_BACKEND` is unset → a non-replay run
> routes to the **bundled in-process council** (no `:8002`). Set
> `LITHRIM_COUNCIL_BACKEND=http` only if you are running against a `lithrim-backend`
> deployment on `:8002`.

## 4. Run it

Two processes. The shell's vite proxy forwards `/v1` → `:8787`.

```bash
# terminal 1 — the BFF (the judge-capability API)
uvicorn app:app --app-dir apps/bff --port 8787

# terminal 2 — the shell
cd apps/shell && npm run dev                 # http://localhost:5180
```

Or, if you have the dev-stack wrapper: `make up` (starts both) / `make down`.

Open <http://localhost:5180>, switch to **Shell** mode (top-center).

- **Run eval** → the `$0` **replay** composite renders in the right artifact pane. No key.
- **Run live** → one real, **paid** council run on the configured backend (in-process by
  default, BYO key). This is the cost-confirmed action.
- The **chat** authors judges/flags and reads/replays — it never spends (`$0`, by design).

## 5. Verify (no key, `$0`)

A pure-offline smoke that exercises the engine + grounding floor without the shell:

```bash
python scripts/run_eval.py                   # agent 'ws0_default', replay ($0)
```

Expected: a `reject` verdict (stage BLOCK), a composite score, and a grounded-correction
line (`MEDICATION_NOT_IN_TRANSCRIPT -> SUPPRESSED via med-presence-check/v1`) — the
tool-grounded floor at work.

## 6. The CI/CD gate (optional)

The eval-pack gate ships as `lithrim-bench-pack` (reliability ≥ threshold AND
never_events == 0; exit 0/1) — the Mongo-free lithrim-sdk parity. See
[`harness/pack_gate.py`](../lithrim_bench/harness/pack_gate.py).
