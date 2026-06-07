# A7 — load-bearing `:5180` visual smoke (bench-salvage UX-1)

**Date:** 2026-06-07 · **Surface:** `apps/shell` Shell mode (`mode !== "journey"`) · **Services:** dev `:5180` (HMR) + BFF `:8787` (already running; not autostarted) · **Driver:** Chrome MCP (live), executor-run.

> The shell's history (WS-5c) is that `vite build` + Vitest passed while a *visible* defect shipped, so this gate is mandatory. Screenshots are embedded in the executor session transcript (Chrome MCP `save_to_disk` does not expose a local path); the IDs below index them. The numbers/strings here are what was observed live, not asserted from code.

## What was exercised (light + dark)

| Check | Result | Evidence |
|---|---|---|
| **A4 — frozen Journey 0-touch** | PASS | Default `mode="journey"` renders the unchanged 4-act demo ("Welcome to Lithrim · First contact", agent picker). Screenshot `ss_602830u8a`. |
| **A2 — clean default (light)** | PASS | Shell opens to the empty-state: neutral title **"New evaluation"** (NOT "Scribe Agent v4"), **no** "Run in progress"/"2,400 samples" chips, greeting "What do you want to evaluate?" + 3 suggested prompts + "Show example conversation". Composer left-bar shows ONLY the paid bolt (attach/layers removed). Screenshot `ss_6132xbgui`. |
| **R4 — suggestions FILL, not send** | PASS | Clicking "Create a risk judge for clinical scribe notes" filled the composer (text in textarea, focused) and did not send; empty-state still shown. Screenshot `ss_1098nz960`. |
| **A3 — composer auto-grow** | PASS | Typing a 2-line prompt grew the textarea to 2 rows; after send it reset to a single row (placeholder restored). Screenshots `ss_2922uk6a4` (grown) → `ss_1413pkcca` (reset). |
| **A1 — markdown LIVE (light)** | PASS | A real assistant turn rendered **formatted**: a bold heading "Heading", a real bulleted list, a rendered **bold phrase**, and an inline `code` chip (mono, boxed). The user turn rendered the literal `**bold**`/`` `code` `` as plain text (D-B contrast). Screenshot `ss_1413pkcca` / `ss_4659x80y2`. |
| **Neutral live-turn identity** | PASS | Live user turn = **"You"** (not "Jordan"); assistant = **"Lithrim"** (not "setup assistant"). Same screenshots. |
| **A1 — markdown LIVE (dark)** | PASS | Theme toggled to dark; the same assistant turn (heading + list + bold + inline `code` chip) renders correctly on the dark surface. Screenshots `ss_5835auzgb` / `ss_9052mc55o`. |

## Prompt used for the markdown turn (read-only, no side effects)

> "In markdown only (no tools, no config changes): a level-2 heading, a 2-item bulleted list, one `**bold**` phrase, and an inline `` `code` `` token."

The agent replied text-only (honored "no tools"); the status bar ("Run #218 … judge council: 3 active") was unchanged before/after — **no config write observed**.

## Not separately forced

- **Autoscroll-on-stream / jump-to-latest** — the latest turn was visible after streaming (short thread fit the viewport, so the "↓ latest" pill did not need to appear). Covered at the handler level by `panes.chat.test.jsx` ("autoscrolls to the latest turn on stream").
- **Sanitization** — proven exhaustively (and non-vacuously) by `components/Markdown.test.jsx`; not re-driven live (would require a model to emit raw `<script>`).

## Chrome MCP screenshot IDs (in transcript)
`ss_602830u8a` (journey) · `ss_6132xbgui` (clean default, light) · `ss_1098nz960` (suggestion fill) · `ss_2922uk6a4` (composer grown) · `ss_1413pkcca` + `ss_4659x80y2` (markdown live, light) · `ss_5835auzgb` + `ss_9052mc55o` (markdown live, dark).
