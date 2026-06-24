# DRIVER — PROVIDER-CENTER-B: the provider-first config surface (frontend, Cline-style)

**Read first:** the memory `provider-center-cline-style-direction` (the target UX — the user's two Cline
screenshots) + the existing `apps/shell/src/genui/ProviderSettings.jsx` (Connect AI) +
`apps/shell/src/genui/ModelRegistry.jsx` (MR-1c: catalog/pool/bind helpers).

**Goal:** reshape Connect AI into a **provider-FIRST** config center (the Cline pattern): a searchable
**provider** picker (OpenAI · Anthropic · Azure · **Gemini · Bedrock · OpenAI-compatible**), per-provider
auth, the provider's **models** (catalog presets + `?live=true`), and a **per-consumer picker** — each
judge role picks `{provider, model}` from the shared pool (grading), and the conversation picks a model
(Anthropic-only near-term — the assistant runs on the Anthropic Agent SDK; do NOT imply otherwise).

**Depends on PROVIDER-CENTER-A** (backend, merged): the broadened provider Literal
(`gemini`/`bedrock`/`openai_compatible`), the per-role provider bind, and `_provider_supports_logprobs`.
Build against that contract (mock `bff.js` in vitest).

**FRONTEND-ONLY:** `apps/shell/src/genui/ProviderSettings.jsx` (reshape), maybe a new
`apps/shell/src/genui/ProviderPicker.jsx`, `apps/shell/src/bff.js`, + `*.test.jsx`. Do NOT touch
`apps/bff/` or python. **NEVER touch `apps/shell/src/app.jsx`.** NO prettier (hand-compact JSX; format only
touched lines; keep `git diff --stat` small). Reuse the inline-style vocab
(`--bg/--ink/--muted/--border/--accent/--surface-muted/--teal/--amber`).

## DELIVERABLES
1. **Provider-first surface** in Connect AI: a provider `<select>`/search (the broadened set), per-provider
   auth (masked key + endpoint where needed: Azure/openai-compatible), Test&save (reuse `configProvider`),
   and a live status badge. Configuring a provider + registering its models REUSES the MR-1c plane
   (`registerModel`/`getModelCatalog`/`listModels`) — do NOT rebuild the pool.
2. **The per-consumer picker** — the Cline "use different models for X" pattern:
   - **Grading:** the 3 judge roles, each a `{provider, model}` picker from the shared pool → `bindModel`
     (PC-A makes the bind cross-provider). Each option shows the **⚠ no-logprobs** hint when the model's
     `logprobs===false` (MR-1c consistency; now also gemini/bedrock/anthropic → dark).
   - **Conversation:** an Anthropic model picker from the pool (honest inline note that chat is
     Anthropic-only today; other providers grade but don't yet drive the conversation).
3. **`bff.js`**: only the thin additions needed (the provider Literal values; reuse existing
   `configProvider`/`registerModel`/`bindModel`/`listModels`/`getModelCatalog`). No new endpoints.
4. Keep it **passive rail chrome** (conversational-first invariant — never drives panes/top-bar). Don't
   delete the working grading/assistant flows in one shot — reshape additively so nothing regresses.

## TESTS (RED first) — vitest, `vi.mock("../bff.js", …)` (patterns: `provider_settings.test.jsx`,
`ModelRegistry.test.jsx`)
- A: the provider picker lists the broadened set incl. Gemini / Bedrock / OpenAI-compatible.
- B: selecting a provider + key + Test&save calls `configProvider` with that provider; endpoint field
  appears for azure/openai-compatible.
- C: the per-judge picker lists pool entries; choosing `{provider, model}` for a role calls `bindModel(id,
  role)`; a `logprobs:false` pool model shows the ⚠ hint.
- D: a MIXED binding renders — risk on one provider, policy on another (the cross-provider council the UI
  now expresses); the conversation picker is Anthropic-scoped with the honest note.
- E: secret hygiene — a typed key is never rendered after save (cleared); no key in the DOM.
- F: the existing Connect AI grading/assistant surfaces still render (non-destructive reshape).

## GATES
- `cd apps/shell && npx vitest run` → green (new/changed tests + the whole shell suite; the ONLY acceptable
  red is the pre-existing `app.test.jsx:14`). `npm run build` succeeds.
- `git diff --name-only` excludes `apps/shell/src/app.jsx`. Scoped commits. DO NOT PUSH. Commit msg ends
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + `git show --stat` (no app.jsx). 3. RED→GREEN + vitest count +
`npm run build`. 4. The provider-first surface contract + how the per-judge cross-provider picker + the ⚠
hint + the Anthropic-only conversation note render.
