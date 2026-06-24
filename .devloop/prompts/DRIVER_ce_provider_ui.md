# DRIVER — CE-PROVIDER-UI (Build B): the in-app "Connect AI" surface — AFTER Build A

**Read first:** `docs/specs/SPEC_COMMUNITY_EDITION.md` §3.2 + §3.3 + §5.2-B. Depends on Build A's
`POST /v1/provider/config` + `GET /v1/provider/status`.

**Goal:** a capability-oriented provider-connect UI — "Grading engine" (required) + "Authoring
assistant" (optional) — reachable from the rail session-menu, reusing the masked-password +
test-then-save idiom of the existing `ConnectorForm`.

## CONSTRAINTS (hard)
- **NEVER edit/stage `apps/shell/src/app.jsx`** (foreign-modified). Build in `genui/ProviderSettings.jsx`
  (new) + `panes.jsx` (the `LeftRail` session-menu) + `bff.js` only.
- Hand-compact JSX, NO prettier (format touched lines by hand; keep `git diff --stat` small).
  Inline styles using the shell CSS vars. Conversational-first holds (a passive settings panel, it
  does not operate panes/top-bar to advance the product).
- Tests-first (vitest). No push.

## DELIVERABLES
1. `apps/shell/src/genui/ProviderSettings.jsx` — two capability slots:
   - **Grading engine** (required): Simple (one OpenAI key → trio on gpt-4o) | Advanced (per-role
     model + provider/endpoint/deployment rows for the Azure trio). Masked password input(s),
     provider select, **Test & save** → `configProvider`, status badge ← `getProviderStatus`.
   - **Authoring assistant** (optional): Anthropic key + model, or "skip (use forms)".
   - Graceful degradation copy: "You can grade now; chat-author unlocks with an assistant."
2. `apps/shell/src/bff.js` — `configProvider({plane, provider, api_key, endpoint, model, role})` →
   `POST /v1/provider/config`; `getProviderStatus()` → `GET /v1/provider/status`. Both via `call()`
   (so they carry the auth header).
3. `panes.jsx` `LeftRail` session-menu — add a **"Connect AI"** item that opens the ProviderSettings
   panel (a modal/popover; reuse the session-menu backdrop pattern). Keep it a passive entry.

## TESTS (RED first, vitest)
- A — ProviderSettings renders both slots; grading marked required, assistant optional.
- B — entering a key + Test calls `configProvider` with the masked value (password input, not echoed).
- C — a passing status renders the connected badge (`getProviderStatus` mocked).
- D — the rail session-menu shows "Connect AI" and opens the panel.
- KEEP the existing rail/session-menu/auth suites green. Add `configProvider`/`getProviderStatus` to
  the 3 whole-surface bff mocks (`app.chat.test.jsx`, `panes.conv.test.jsx`, `panes.chat.test.jsx`).

## GATES
- `cd apps/shell && npx vitest run` → green except the 1 known foreign `app.test.jsx` ModeSwitch fail.
- `git diff --name-only` MUST NOT include `apps/shell/src/app.jsx`. Scoped commit. Do NOT push.
- Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
