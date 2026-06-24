# DRIVER — MODEL-REGISTRY-1a: the configured-model pool + capability-aware catalog (backend)

**Read first:** `docs/specs/SPEC_COMMUNITY_EDITION.md` §8 (the locked design + the owner decision).

**Goal:** a **configured model becomes a first-class, reusable, capability-aware entity** (the LiteLLM
`model_list` pattern), decoupled from the judge role. Backend only (UI = 1c). Phase-1 keeps the 3 fixed
roles — a role *binds* to a pool entry instead of re-typing provider/model/key.

## REUSE — do NOT re-architect (Build A already exists)
- `_probe_provider(...)` (`apps/bff/app.py` ~3286) — the read-only test-probe. Reuse for register.
- `_provider_env_vars(req)` (~3254) + `_PROVIDER_AZURE_ROLE_DEPLOYMENT`/`_PROVIDER_OPENAI_ROLE_MODEL`
  (~3245) — provider→env-var mapping.
- `_persist_and_reload_provider(env_vars)` (~3323) — write-only `.provider_env` + os.environ + refresh
  the council `settings` singleton (the no-restart env-reload). Reuse for BIND.
- `_parse_env_file` / `_PROVIDER_ENV_PATH` / `.provider_status.json` patterns.
- **Frozen council seam UNTOUCHED** (`compliance_council.py`/`_apply_consensus`). NEVER `app.jsx`.

## DELIVERABLES
1. **`GET /v1/models/catalog`** — static curated presets per provider, each capability-annotated.
   **Capabilities are the point, esp. `logprobs`** (OpenAI ✓ → calibrated confidence; Anthropic ✗;
   Azure = deployment-based; Mistral/Llama ✗). A small honest map, e.g.:
   - openai: `gpt-4o`(logprobs ✓), `gpt-4o-mini`(✓), `gpt-4.1`(✓), `o3-mini`(✗ reasoning)
   - anthropic: `claude-3-5-sonnet-latest`(✗), `claude-3-5-haiku-latest`(✗)
   - azure: `[]` + a note "deployment-name-based — bring your deployment"
   Plus a `capabilities_for(provider, model)` helper that infers a CUSTOM model's flags by family
   (`gpt-*`/`o*` heuristics), so a non-preset model still gets an honest logprobs flag.
2. **Registry pool CRUD** — a configured model = `{id, provider, model_or_deployment, endpoint?,
   capabilities, last_tested}` (non-secret) persisted to a gitignored `.models_registry.json`; the key
   is WRITE-ONLY (never SQLite/manifest/response/logs/the registry json):
   - `POST /v1/models` `{id, provider, model, endpoint?, api_key}` → `_probe_provider` → on pass store
     metadata + capabilities + persist the key write-only (a namespaced var in `.provider_env`, e.g.
     `LITHRIM_MODEL__<id>__KEY`, or a `.models_env`) → return `{id, provider, model, capabilities,
     last_tested}` (NEVER the key). On probe fail → 400, nothing written.
   - `GET /v1/models` → the pool (never keys). `DELETE /v1/models/{id}` → drop the entry + its key.
3. **`POST /v1/models/{id}/bind` `{role}`** — bind a pool entry to one of the 3 roles: map the entry's
   `{provider, model, endpoint, key}` to the role's env vars via the SAME mechanism as
   `_provider_env_vars`+`_persist_and_reload_provider` (so `build_judge_lm` routes that role to the
   chosen model, no restart). **Verify** `build_judge_lm` honors a per-role provider override (BYOC-1
   did per-role BYO-Claude) — if a cross-provider mix (role A openai, role B azure) is NOT supported
   (the global `LITHRIM_LLM_PROVIDER`), DO NOT fake it: bind the same-provider case (the trio within a
   provider, e.g. the Azure deployments) and flag a SEAM for the cross-provider case. Honest > broad.

## TESTS (RED first) — bare-CE, mock the probe (pattern = `tests/bff/test_provider_config.py`)
- A: `GET /v1/models/catalog` returns presets with a `logprobs` flag per model (gpt ✓, claude ✗).
- B: `POST /v1/models` (passing probe) → 200; metadata + capabilities stored; key NOT in the response,
  NOT in `.models_registry.json`; key persisted write-only (read it back via the env file).
- C: `POST /v1/models` (failing probe) → 400, nothing written.
- D: `GET /v1/models` lists the pool, NEVER a key; `DELETE` removes the entry + key.
- E: `capabilities_for("openai","gpt-4o")["logprobs"] is True` and `(...,"claude-3-5-sonnet")` is False.
- F: `POST /v1/models/{id}/bind {role:"policy_judge"}` → the role's env (provider+model[+deployment])
  is written so a subsequent `build_judge_lm`/grade reads it (mock the LM; assert the env, no restart).

## GATES
- `PYENV_VERSION=debuglithrim python -m pytest -q` → green, ≥727 passed / 0 failed. `ruff check .` clean.
- `git diff --name-only` excludes `apps/shell/src/app.jsx`. Scoped commit(s). DO NOT PUSH. Commit msg
  ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + messages + `git show --stat` (no app.jsx). 3. RED→GREEN +
full bare-CE count. 4. The catalog/capability map + the registry-entry shape you shipped + whether
cross-provider per-role bind works (or the seam) — so 1b (live fetch) + 1c (UI) can build on it.