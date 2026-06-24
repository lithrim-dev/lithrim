# DRIVER — MODEL-REGISTRY-1c: the model-pool UI + pick-from-pool role bind (frontend)

**Read first:** `docs/specs/SPEC_COMMUNITY_EDITION.md` §8 ("Phase 1 scope: the registry + catalog + the
3 fixed roles bind to pool entries — pick-from-pool, not re-type").
**Builds on:** MODEL-REGISTRY-1a (backend pool: `GET /v1/models/catalog`, `POST/GET/DELETE /v1/models`,
`POST /v1/models/{id}/bind {role}`) + the existing Connect AI panel
`apps/shell/src/genui/ProviderSettings.jsx` (opened from the rail session-menu, `panes.jsx`).

## Goal
A **Model pool** surface inside Connect AI: register capability-annotated models into a reusable pool,
then have each of the 3 fixed judge roles **PICK a pool entry** (pick-from-pool) instead of re-typing
provider/model/key per role. **Capabilities are the UX point — esp. `logprobs`:** a model with
`logprobs:false` shows a **⚠ "no logprobs — confidence dark"** hint at pick time (the differentiated
catalog vs a cosmetic dropdown). Honor the conversational-first invariant: this is **passive rail chrome**
(it never drives panes / the top-bar to advance the product).

## REUSE — do NOT re-architect
- The Connect AI panel `ProviderSettings.jsx` (masked-password + Test&save idiom, `--bg/--ink/--muted/
  --border/--accent/--surface-muted/--teal/--amber` inline-style vocabulary) — add the pool section; do
  NOT remove the existing Simple/Advanced grading or the assistant section (non-destructive).
- `bff.js` `call()` (carries the auth header) + the `configProvider`/`getProviderStatus` export idiom.
- The vitest + `vi.mock("./bff.js", …)` idiom of `apps/shell/src/provider_settings.test.jsx`.
- **NEVER edit `apps/shell/src/app.jsx`** (foreign-modified — out of scope). No prettier (hand-compact JSX;
  format only your touched lines — keep `git diff --stat` small).

## DELIVERABLES
1. **`bff.js` client helpers** (mirror `configProvider`'s doc-comment + body-spread style; via `call()`):
   - `getModelCatalog({ live = false } = {})` → `GET /v1/models/catalog?live=…`
   - `registerModel({ id, provider, model, endpoint, api_key })` → `POST /v1/models`
   - `listModels()` → `GET /v1/models` · `deleteModel(id)` → `DELETE /v1/models/{id}`
   - `bindModel(id, role)` → `POST /v1/models/{id}/bind { role }`
2. **`apps/shell/src/genui/ModelRegistry.jsx`** — a self-contained section component:
   - **Register a model:** provider select (openai|azure|anthropic) → a model `<select>` built from
     `getModelCatalog` presets (+ live when present), each option showing the **⚠ no-logprobs** hint when
     `logprobs===false`; a **custom** free-text option (always available — never block an unknown model;
     Azure is deployment-name free-text by design); an `id` field; a masked (type=password) key input;
     **Register & test** → `registerModel`. On success: clear the key, refresh the pool.
   - **The pool:** list `listModels()` entries — id · provider · model · the **logprobs** capability chip ·
     `bound_roles` · a **Delete** (`deleteModel`) — NEVER a key.
   - **Bind roles:** the 3 roles (`risk_judge`/`policy_judge`/`faithfulness_judge`), each with a `<select>`
     of pool entries → **Bind** → `bindModel(id, role)`. (Cross-provider-per-role is a backend seam from
     1a — a small inline note is fine; do NOT fake it.)
3. **Compose** `ModelRegistry` into `ProviderSettings.jsx` as a new "Model pool" section (between Grading
   and Authoring is fine), behind the same panel. Keep it additive.

## TESTS (RED first) — `apps/shell/src/genui/ModelRegistry.test.jsx` (vitest, `vi.mock("../bff.js", …)`)
- A: renders the register form; the model `<select>` lists catalog presets from a mocked `getModelCatalog`;
  a `logprobs:false` model surfaces the ⚠ "no logprobs"/"confidence dark" hint.
- B: register → fill `id` + pick a model + type a key → **Register & test** calls `registerModel` with the
  entered values; the key input is `type="password"`.
- C: the pool list renders entries from a mocked `listModels` (id/provider/model/logprobs chip), NEVER a
  key; **Delete** calls `deleteModel(id)`.
- D: a role's pool `<select>` lists pool entries; choosing one + **Bind** calls `bindModel(id, role)`.
- E (secret hygiene — non-vacuous): after a successful register the typed key is NOT present in the DOM
  (input cleared / never rendered as text).
- F: `ProviderSettings` renders the Model pool section (compose check) — the existing grading/assistant
  sections still render (non-destructive).

## GATES
- `cd apps/shell && npx vitest run` → green (new file + the whole shell suite; 0 failures).
- `cd apps/shell && npm run build` → succeeds (no broken import).
- `git diff --name-only` excludes `apps/shell/src/app.jsx`. Scoped commit(s) (`test…red`, `feat…green`).
  DO NOT PUSH. Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + messages + `git show --stat` (no app.jsx). 3. RED→GREEN +
the vitest pass count + the `npm run build` result. 4. The ModelRegistry component contract (props/exports)
+ the bff.js helpers added + how the ⚠ logprobs hint renders (so it stays consistent with 1b's catalog).
