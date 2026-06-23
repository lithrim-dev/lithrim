# DRIVER — SESSION-MENU-1: always-on session control (Sign in / Sign out) in the rail

**Goal:** make BFF auth ALWAYS reachable from the UI. Today login is reactive-only (shows only on a
401) and the Sign-out button is hidden whenever no token is stored — so on an open/local server (the
default) there is NO way to sign in or out, and the rail-footer "⋯" is a dead button. Fix: a small
always-present **session menu** in the rail footer with proactive **Sign in…** / **Sign out**.

This is a UI-LOGIN-1 follow-on (the gate, reactive login, logout(), hasStoredToken() already exist).

## CONSTRAINTS (hard)

- **NEVER touch `apps/shell/src/app.jsx`** (foreign-modified). Build in `panes.jsx` (the `LeftRail`
  footer) + `auth.jsx` + `bff.js` only.
- **Conversational-first holds:** the session menu is passive rail chrome (it does NOT operate panes/
  top-bar to advance the product).
- Hand-compact JSX, no prettier; INLINE styles using the shell CSS vars (`--panel/--border/--text/
  --muted/--accent/--bg`) — do NOT edit CSS files. Tests-first (vitest).

## CURRENT STATE

`panes.jsx` `LeftRail` footer (~lines 108-120):
```jsx
<div className="rail-foot">
  <div className="avatar">L</div>
  <div style={{ minWidth: 0, flex: 1 }}><div className="who">You</div><div className="org">Local workspace</div></div>
  {hasStoredToken() && (<button className="icon-btn" title="Sign out" aria-label="Sign out" onClick={logout}><Icon name="key" size={16} /></button>)}
  <button className="icon-btn"><Icon name="dots" size={16} /></button>   {/* DEAD — no onClick */}
</div>
```
`bff.js` already exports `hasStoredToken`, `logout` (clears token + dispatches `"lithrim:auth-required"`).
`auth.jsx` `AuthGate` shows `<LoginScreen>` on the `"lithrim:auth-required"` window event; `LoginScreen`
has NO cancel (a hard 401 gate).

## DESIGN

1. **`bff.js`** — add a proactive sign-in trigger (reuses the gate event AuthGate already listens to):
   ```js
   export const signIn = () => { try { window.dispatchEvent(new Event("lithrim:auth-required")); } catch {} };
   ```

2. **`auth.jsx`** — make `LoginScreen` cancelable so a PROACTIVE sign-in (esp. on an open server) isn't
   a trap:
   - `LoginScreen({ onSuccess, onCancel })`: add a subtle text button "Continue without signing in"
     (`data-testid="auth-cancel"`) that calls `onCancel`.
   - `AuthGate`: pass `onCancel={() => setNeedsLogin(false)}` to `LoginScreen` (dismiss the gate). On a
     genuine 401 the next call simply re-raises it; on a proactive/open-server sign-in, cancel returns
     to the app. Keep the existing `onSuccess` (setNeedsLogin(false) + epoch remount).

3. **`panes.jsx` `LeftRail` footer** — replace the dead `⋯` + the conditional key-button with a session
   MENU:
   - `const [sessionMenu, setSessionMenu] = useState(false)` in `LeftRail`; `const authed = hasStoredToken()`.
   - The footer button (`aria-label="Session menu"`, keep the `dots` icon) toggles `sessionMenu`.
   - When open, render a small popover ABOVE the footer (absolute; `.rail-foot` gets
     `position: relative`) containing:
     - a muted status line: authed → "Signed in with an access token"; else → "Not signed in · server is open".
     - authed → a **"Sign out"** item → `() => { setSessionMenu(false); logout(); }`.
     - not authed → a **"Sign in…"** item → `() => { setSessionMenu(false); signIn(); }`.
   - Menu items are TEXT-labeled (so we don't depend on a specific icon; an optional leading `Icon`
     is fine only if a fitting one exists — do NOT reuse the ambiguous `key` icon for sign-out).
   - A click-outside backdrop (`position: fixed; inset: 0`) closes the menu on click.
   - REMOVE the old `hasStoredToken() && <key button>` (it's folded into the menu).
   - Import `hasStoredToken, logout, signIn` from `./bff.js`.

## TESTS — RED first (`apps/shell/src/session_menu.test.jsx`, or extend `auth.test.jsx`)

Mount `LeftRail` (import from `panes.jsx`) with minimal props. jsdom localStorage is polyfilled in
`test/setup.js`. Mock `./bff.js` (or spy on `signIn`/`logout`/`hasStoredToken`).
- A — the session-menu trigger (`aria-label="Session menu"`) is ALWAYS present (authed or not).
- B — clicking it opens the menu (the status line + an action item appear).
- C — NOT authed (`hasStoredToken` → false): the menu shows **"Sign in…"**; clicking it calls `signIn`.
- D — authed (`hasStoredToken` → true): the menu shows **"Sign out"**; clicking it calls `logout`.
- E — clicking the backdrop closes the menu.
- F — (`auth.jsx`) `LoginScreen` renders a cancel affordance; clicking it calls `onCancel`; `AuthGate`'s
  cancel dismisses the gate (children render again after a `"lithrim:auth-required"` event + cancel).
- G — (`bff.js`) `signIn()` dispatches `"lithrim:auth-required"` (spy on `window`).

KEEP the existing `auth.test.jsx` (A-E) GREEN. The whole-surface bff mocks in `panes.conv.test.jsx`,
`panes.chat.test.jsx`, `app.chat.test.jsx` mount `LeftRail` (via App) — ADD `signIn` to each so they
don't hit an undefined export; re-run those three suites to confirm green.

## GATES

- `cd apps/shell && npx vitest run` → all green EXCEPT the 1 pre-existing foreign `app.test.jsx` fail
  (ModeSwitch). The new session-menu suite + the existing auth/panes suites pass. Paste the tail.
- No Python touched → skip pytest.
- `git diff --name-only` must NOT include `apps/shell/src/app.jsx`.

## COMMIT

Tests-first (RED), then impl (GREEN). Scoped pathspec: `apps/shell/src/{panes.jsx, auth.jsx, bff.js}` +
the test file(s) (+ the 3 whole-surface mock files if edited). Verify with `git show --stat HEAD`. NEVER
`app.jsx`. Do NOT push. End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
