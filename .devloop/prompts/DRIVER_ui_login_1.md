# DRIVER — UI-LOGIN-1: runtime login/logout for the BFF auth gate

**Goal:** make the BFF auth token a **runtime** credential entered/cleared from the UI, instead of a
build-baked `VITE_BFF_TOKEN`. A reactive login gate (appears only on a 401), the token stored in
`localStorage`, and a logout button — so the secret stays out of the JS bundle and is rotatable without
a rebuild. Follows BFF-AUTH-1 (the server-side gate + the `bff.js` Bearer header already exist).

## CONSTRAINTS (hard)

- **NEVER touch `apps/shell/src/app.jsx`** (foreign-modified by a concurrent session). The whole design
  is built in `root.jsx` + a NEW `auth.jsx` + `panes.jsx` (the rail) + `bff.js`.
- **Conversational-first invariant holds:** the login gate is a PRE-AUTH screen that replaces the app
  until authenticated — it is NOT chrome operating the product. The logout button is rail chrome. No
  pane/top-bar driving. (Critic will check this.)
- **Default-OFF stays zero-friction:** when the server gate is off (no `LITHRIM_BFF_TOKEN`), NO 401 ever
  fires, so the login gate NEVER shows — the local one-command run is unchanged.
- Hand-compact JSX, no prettier; keep diffs to touched lines (`[[shell-no-prettier-handcompact-jsx]]`).
- Tests-first (vitest). `cd apps/shell && npx vitest run`.

## DESIGN

**Token storage is client-side (correct here):** a BFF access token is a CLIENT credential with no
backend source-of-truth, so `localStorage` is the right home (this is the OPPOSITE of conversation
history, which is backend-owned). Key: `"lithrim_bff_token"`.

### 1. `apps/shell/src/bff.js`
Replace the build-only `AUTH` const (lines 7-10) with runtime token helpers + a per-request header:
```js
const TOKEN_KEY = "lithrim_bff_token";
export const getToken = () => {
  try { const t = localStorage.getItem(TOKEN_KEY); if (t) return t; } catch {}
  return import.meta.env.VITE_BFF_TOKEN || "";           // fallback: a build-baked token still works
};
export const hasStoredToken = () => { try { return !!localStorage.getItem(TOKEN_KEY); } catch { return false; } };
export const setToken = (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch {} };
export const clearToken = () => { try { localStorage.removeItem(TOKEN_KEY); } catch {} };
const authHeader = () => { const t = getToken(); return t ? { Authorization: `Bearer ${t}` } : {}; };
// validate a candidate token against a gated route — non-401 (incl. 200/500) = the gate accepted it.
export const validateToken = async (candidate) => {
  try {
    const r = await fetch(BASE + "/v1/meta", { headers: candidate ? { Authorization: `Bearer ${candidate}` } : {} });
    return r.status !== 401;
  } catch { return false; }
};
// logout = forget the token + raise the auth-required signal so the gate re-shows (no full reload).
export const logout = () => { clearToken(); try { window.dispatchEvent(new Event("lithrim:auth-required")); } catch {} };
```
- In `call()`: build `merged` with `...authHeader()` (replacing `...AUTH`); and on a 401 raise the signal
  BEFORE throwing: `if (res.status === 401) { try { window.dispatchEvent(new Event("lithrim:auth-required")); } catch {} }`.
- In `chatStream()` (the SSE fetch headers, ~line 291): replace `...AUTH` with `...authHeader()`.

### 2. `apps/shell/src/auth.jsx` (NEW)
- `LoginScreen({ onSuccess })`: a centered card (INLINE styles using the shell CSS vars —
  `var(--bg)/(--panel)/(--border)/(--text)/(--accent)/(--muted)`; render `<Mark size={…}/>` from
  `./brand.jsx`). A masked `type="password"` input (`data-testid="auth-token-input"`, autoFocus) + a
  "Sign in" submit (`data-testid="auth-signin"`) + an error line. On submit: trim; `await validateToken(t)`;
  if ok → `setToken(t); onSuccess()`; else show "That token was rejected — check it and try again." Disable
  while busy / when empty.
- `AuthGate({ children })`: `useState needsLogin=false`, `epoch=0`. `useEffect` adds a `window` listener for
  `"lithrim:auth-required"` → `setNeedsLogin(true)` (cleanup removes it). Render:
  `needsLogin ? <LoginScreen onSuccess={() => { setNeedsLogin(false); setEpoch(e=>e+1); }} /> :
   <div key={epoch} style={{ display: "contents" }}>{children}</div>`
  (bumping `epoch` REMOUNTS the children so the app re-fetches with the new token — no page reload).

### 3. `apps/shell/src/root.jsx`
Import `{ AuthGate } from "./auth.jsx"` and wrap the returned shell:
```jsx
return (
  <AuthGate>
    {mode === "journey" ? <JourneyApp {...shared} /> : <App {...shared} />}
  </AuthGate>
);
```

### 4. `apps/shell/src/panes.jsx` — `LeftRail` footer (lines ~108-115)
Import `{ hasStoredToken, logout }` from `./bff.js`. In the `rail-foot`, add a logout affordance shown
ONLY when a token is stored (so it's absent on an open/local server): a small `icon-btn`
`title="Sign out" aria-label="Sign out"` calling `logout`. Check `icons.jsx` for a fitting icon name; if
none fits, use a short text button. Conditional: `{hasStoredToken() && (<button …/>)}`.

## TESTS — RED first

`apps/shell/src/auth.test.jsx` (jsdom has real `localStorage`):
- A — `AuthGate` renders its children by default (no login screen).
- B — dispatching `window` `"lithrim:auth-required"` makes `AuthGate` show the `LoginScreen` (the token
  input appears).
- C — `LoginScreen`: a VALID token (mock `validateToken` → true) calls `setToken` with it and dismisses
  the gate (children return); an INVALID token (→ false) shows the error and does NOT store.
- D — token helpers round-trip via `localStorage`: `setToken`/`getToken`/`hasStoredToken`/`clearToken`;
  `getToken` falls back to `import.meta.env.VITE_BFF_TOKEN` when nothing is stored.
- E — `logout()` clears the stored token AND dispatches `"lithrim:auth-required"`.

Extend `apps/shell/src/bff.*test*` (or a small new bff test): `call()` on a mocked **401** response
dispatches `"lithrim:auth-required"` (spy on `window`); `validateToken` returns false on a mocked 401 and
true on a mocked 200. Mock `fetch` (the existing tests' pattern). Keep the existing
`panes.conv.test.jsx` / `panes.chat.test.jsx` whole-surface bff mocks GREEN — add `hasStoredToken`/`logout`
(and any new exports the rail now imports) to those mocks so the mounted panes don't hit undefined.

## GATES

- `cd apps/shell && npx vitest run` → all green EXCEPT the 1 pre-existing foreign `app.test.jsx` failure
  (ModeSwitch commented out) — that one stays as-is; everything else passes. The new login/logout suite
  green.
- No Python touched → the pytest suite is unaffected (don't run it unless you changed py).
- `git diff` must NOT include `apps/shell/src/app.jsx`.

## COMMIT

Tests-first (RED commit), then the impl (GREEN). Scoped pathspec: `apps/shell/src/{auth.jsx, root.jsx,
panes.jsx, bff.js}` + the test file(s). Verify with `git show --stat HEAD`. NEVER `app.jsx`. Do NOT push.
End the message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
