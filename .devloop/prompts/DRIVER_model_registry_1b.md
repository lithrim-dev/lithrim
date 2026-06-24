# DRIVER — MODEL-REGISTRY-1b: live `/models` fetch for the catalog (backend)

**Read first:** `docs/specs/SPEC_COMMUNITY_EDITION.md` §8 ("The catalog = presets + custom + live").
**Builds on:** MODEL-REGISTRY-1a (`apps/bff/app.py` ~3402–3710, `_MODEL_CATALOG_PRESETS`,
`capabilities_for`, `GET /v1/models/catalog`). 1a shipped the STATIC presets; 1b adds the **live** axis.

## Goal
`GET /v1/models/catalog` gains an **opt-in live fetch** (`?live=true`): for the providers that expose a
`/models` API (**OpenAI, Anthropic**), fetch the live model list using the **already-configured key**
(read server-side from `.provider_env` — Build A's `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`), annotate each
via `capabilities_for`, and **merge** with the presets (dedup by model id, tag `source`). **Graceful-
absent is the contract:** no key / network error / 401 → that provider falls back to **presets only**, a
200 (NEVER a 500), with a per-provider status note. **Azure stays deployment-based** — never fetched.

**Key-safety (non-negotiable):** the key is read SERVER-SIDE from `.provider_env` — it is NEVER a query
param, NEVER in the response, NEVER logged. (Security rule: no secret in a URL/query.)

## REUSE — do NOT re-architect
- `_MODEL_CATALOG_PRESETS`, `_MODEL_CATALOG_AZURE_NOTE`, `capabilities_for(provider, model)` (1a) — the
  preset rows + the family-infer for an arbitrary live model id.
- `_parse_env_file(_PROVIDER_ENV_PATH)` — read the configured key back (the same store Build A writes).
- Lazy SDK imports inside the fetch (like `_probe_provider`): `openai.OpenAI(api_key=…).models.list()` and
  `anthropic.Anthropic(api_key=…).models.list()` — keeps app.py free of the LM deps at module load and is
  trivially mockable. Wrap EACH provider in its own try/except → never a 500.
- **Frozen council seam UNTOUCHED** (`compliance_council.py`/`_apply_consensus`). NEVER `apps/shell/src/app.jsx`.

## DELIVERABLES
1. A helper `_fetch_live_models(provider, api_key) -> list[dict]` (lazy SDK import; OpenAI filters to
   chat-capable ids — keep `gpt-*`, `o1*`/`o3*`/`o4*`, `chatgpt-*`; DROP embeddings/whisper/tts/dall-e/
   moderation/`text-`; Anthropic keeps `claude-*`). Each entry: `{model, **capabilities_for(provider,id),
   "source": "live"}`. Raises on SDK error (caller traps).
2. `GET /v1/models/catalog?live=<bool>` (default **false** → byte-identical 1a response, the regression
   guard). When `live=true`: for openai + anthropic, read the configured key; if present, fetch live +
   merge with presets (preset ⊕ live, dedup by `model`, each tagged `source: "preset"|"live"`); on
   absent-key or fetch-error, that provider = presets-only (each `source:"preset"`). Azure unchanged
   (`{models: [], note}`). Add a top-level **`live`** block: `{openai: {ok, fetched?|error?, source},
   anthropic: {…}}` so the UI (1c) can show "live ✓ N models / presets only (no key)".
3. Keep the response shape additive: the `?live` absent path returns EXACTLY 1a's JSON (no `source`, no
   `live` key) so 1a's catalog test stays green unchanged.

## TESTS (RED first) — bare-CE, MOCK the SDK list calls (pattern = `tests/bff/test_model_registry.py`)
Monkeypatch `_fetch_live_models` (or the lazy `openai`/`anthropic` modules) — NO network, $0.
- A: `?live=true` with a configured `OPENAI_API_KEY` + a mocked openai list `[gpt-4o, gpt-5-x,
  text-embedding-3-large, whisper-1]` → openai catalog CONTAINS `gpt-4o` + `gpt-5-x` (each `source` set,
  `gpt-*`→`logprobs True`), EXCLUDES the embedding/whisper ids; `live.openai.ok is True`, `fetched>=2`.
- B: `?live=true` with a configured `ANTHROPIC_API_KEY` + a mocked anthropic list `[claude-4-x]` → present,
  `logprobs False`, `source:"live"`; `live.anthropic.ok is True`.
- C: `?live=true` with NO key for a provider → that provider = presets only (every `source:"preset"`),
  `live.<p>.ok is False`, HTTP **200** (graceful, not 500).
- D: `?live=true` with the SDK list RAISING (network/401 simulated) → graceful presets-only + `live.<p>`
  carries `ok False` + an `error`, HTTP 200.
- E: `?live=true` → azure is STILL `{models: [], note}`, never fetched (assert the azure SDK path is not
  hit).
- F (regression): `GET /v1/models/catalog` (no `?live`) → byte-identical to 1a (no `source`/`live` keys).
- G (secret hygiene — must be non-vacuous): the configured key string is NEVER present anywhere in the
  `?live=true` response body (assert the literal key absent from `json.dumps(body)`).

## GATES
- `PYENV_VERSION=debuglithrim python -m pytest -q` → green, ≥736 passed / 0 failed. `ruff check .` clean.
- `git diff --name-only` excludes `apps/shell/src/app.jsx`. Scoped commit(s) (`tests…red`, then
  `feat…green`). DO NOT PUSH. Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + messages + `git show --stat` (no app.jsx). 3. RED→GREEN +
full bare-CE count. 4. The final `?live=true` catalog response shape (so 1c can consume it) + confirmation
the no-`?live` path is byte-identical to 1a + the exact filter list you shipped for OpenAI chat models.
