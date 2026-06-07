# Driver — `bench-salvage` phase `UX-1`: chat markdown rendering + cadence + clean-default chat (S-BS-89)

> **Bundle ID:** `bench-salvage-phaseUX-1-chat-markdown-ux-driver`
> **Stream:** `bench-salvage` · **Target repo:** `lithrim-bench` (shell-only) · **Branch:** `bench-salvage/ws6c-dspy` (dirty shared — pathspec-only commits)
> **Hardness:** NOT a HARD-GATE (no spec/API contract, no paid path, no core invariant). Inline critique at close. **BUT the live `:5180` visual smoke is load-bearing** — the shell's history is that `vite build` + Vitest passed while a *visible* defect shipped (WS-5c). Treat A7 as mandatory.
> **Objective served:** user objective #3 — "add markdown parsing on the UI… fix various UX issues like chat experience so I can actually use it." Scope locked by two user decisions (2026-06-07): **markdown + cadence fixes**, and **clean chat by default with the demo opt-in** (folds S-BS-89).

---

## KICKOFF (paste into a fresh executor session)

```
You are the executor for bench-salvage phase UX-1 (shell chat UX: markdown + cadence + clean-default).
Read EXECUTOR.md first, then this driver in full:
  .devloop/prompts/bench-salvage_phaseUX-1_chat-markdown-ux_driver.md

This is SHELL-ONLY (apps/shell/). Do NOT touch apps/bff/ or apps/shell/src/journey/ (the journey is FROZEN).
The dev server is already running on :5180 (HMR) and the BFF on :8787 — do NOT autostart anything; curl /health first if unsure.

What you're building (3 deliverables + tests):
  D1  Markdown rendering for chat assistant text (react-markdown + remark-gfm; raw HTML INERT — no rehype-raw).
  D2  Chat cadence: autoscroll-to-latest, composer auto-grow, dead-affordance cleanup.
  D3  Clean default chat + demo opt-in (empty-state by default; scripted cards behind "Show example"; wire the
      "New evaluation" + button to reset to a clean slate = S-BS-89). The frozen Journey stays the canonical demo, untouched.
  D4  Tests (Vitest) for markdown render + HTML-sanitization + empty-state default + New-eval reset.

Post a plan-review resolving D-A..D-F (see §3) BEFORE writing any code. Do not code until I say "go".
Branch is a dirty shared tree — commit ONLY your own files via explicit pathspec (never `git commit -a`/bare).
```

---

## 0. Why

The conversational shell is the product surface, but you can't actually *use* it today:

1. **Assistant output renders as literal text.** `panes.jsx:269,277` render `<p style={{whiteSpace:"pre-wrap"}}>{m.text}</p>`. The agent streams markdown (`**bold**`, headings, `- lists`, fenced code, tables, links) and it all shows as raw source. No markdown lib is installed.
2. **No chat cadence.** Streaming text doesn't autoscroll; the composer doesn't grow with multi-line input; two composer buttons are dead.
3. **A wall of canned demo content sits above every real conversation.** `panes.jsx:173-259` hardcodes 8 scripted messages ("Jordan" / "Scribe Agent v4" / fake verdict+calibration+config cards) + static header chips ("Run in progress" / "2,400 samples", `:158-159`). Your live turns appear *below* all of it. This is the "seed conversation buries live turns" clutter (S-BS-89).

**User decision (2026-06-07):** default to a **clean chat**; keep the scripted showcase as an **opt-in** ("Show example"); the frozen 4-act Journey (`root.jsx mode="journey"`) remains the canonical demo and is **not touched**.

---

## 1. Pre-flight (citations re-grepped against HEAD 2026-06-07 — re-grep before you cite in commits)

**The chat surface — `apps/shell/src/panes.jsx`:**
- `CenterPane(...)` `:80`; chat state `const [chat, setChat] = useState([])` `:90`; `input`/`sending`/`paid`/`taRef` `:91-94`.
- `send()` `:96`; history snapshot `chat.map(m => ({role, content: m.text||""}))` `:102` (ONB-0 contract — **don't change it**); optimistic append `:105`; `assistant_delta` append `:118`; `tool_result` part append `:119-120`; error append `:122,127`.
- `onComposerKey` (⌘↵/Ctrl↵ only) `:133-138`.
- **Scripted preamble (the 8 canned messages):** `:173-259`. Static header chips `:158-159`. `SETUP_PARTS` `:13-17`.
- **Live chat render:** `:263-287` — user turn `:264-271` (avatar `"JR"` `:266`, name `"Jordan"` `:268`, raw `<p whiteSpace:pre-wrap>{m.text}</p>` `:269`); assistant turn `:272-285` (name `"Lithrim setup assistant"` `:276`, raw `<p>` `:277`, parts `:278-280`, `"Thinking…"` `:281-283`).
- `CostModal` `:292-300` (the in-DOM paid gate — leave it). `composer` `:302-332`: `<textarea ref={taRef} rows="1" …>` `:305-313`; dead buttons `attach`/`layers` `:316-317`; the paid-run `bolt` `:318-321` (leave it); `⌘↵` hint `:323`; send button `:324-327`.
- **LeftRail** `:20-77`: the **"New evaluation" + button has NO onClick** `:29` (S-BS-89 fix site); rail footer canned identity `"Jordan Reyes / acme-health · Pro"` `:67-72`.

**The BFF bridge — `apps/shell/src/bff.js`:** `chatStream({message, agent, actor, history}, {onEvent, signal})` `:122`; SSE events `assistant_delta | tool_call | tool_result | error | done` `:118-121` (the comment). **The chat contract is FROZEN this cycle — body stays `{message, agent, history}`** `:131`.

**The mode switch — `apps/shell/src/root.jsx`:** `mode` default `"journey"` (the demo) `:13`; `return mode === "journey" ? <JourneyApp/> : <App/>` `:19`. → **The Shell's `CenterPane` preamble is independent of the frozen Journey.** `app.jsx:122` mounts `<CenterPane onOpenArtifact … artifactOpen … />` (sibling of `LeftRail`).

**Styles — `apps/shell/src/styles.css`:** scroll container `.convo { flex:1; overflow-y:auto; padding:26px 0 8px }` `:295`; `.convo-inner { max-width:720px; margin:0 auto }` `:296`; `.msg` `:298-311`; `.msg p` `:308-310`; existing inline-code style `code.inl` `:312`; the JSON viewer's `.code` block `:520-528` (artifact pane — **not** the chat; do not reuse blindly). Composer `:415-429`; `.composer textarea` `:422-426`.

**Test setup — `apps/shell/package.json`:** React `^18.3.1`, Vite `^6.0.7`, Vitest `^4.1.8`, `@testing-library/react ^16.3.2`, `jsdom ^29.1.1`; `"test": "vitest"`. Existing chat tests: `panes.chat.test.jsx`, `panes.test.jsx` — **these assert scripted-preamble content and will break when the default becomes empty-state; update them.** Also green-bar guards: `app.test.jsx`, `bff.test.jsx`, `artifact.test.jsx`, `journey/JourneyApp.test.jsx`.

---

## 2. Deliverables (file-by-file)

### D1 — Markdown rendering (HTML-inert)
- **`apps/shell/package.json`** — add `react-markdown` (`^9`) + `remark-gfm` (`^4`) (React-18 compatible; confirm at install — D-A). No other deps. No Tailwind.
- **New `apps/shell/src/components/Markdown.jsx`** — a thin wrapper: `ReactMarkdown` with `remarkPlugins={[remarkGfm]}` and **no `rehype-raw`** (raw HTML in model output stays inert text = XSS-safe by construction). Constrain link rendering (`target="_blank" rel="noopener noreferrer nofollow"`). Keep it small.
- **`apps/shell/src/panes.jsx`** — replace the **assistant** live render `:277` `<p whiteSpace:pre-wrap>{m.text}</p>` → `<Markdown>{m.text}</Markdown>` (wrapped so the `⚠ error` appends still render). **User** turn `:269`: per D-B (recommend keep plain text — a user's literal input shouldn't be markdown-interpreted).
- **`apps/shell/src/styles.css`** — add a scoped `.msg .md` block (headings, `ul/ol/li`, `p`, `a`, `blockquote`, `table/th/td`, `pre code` fenced blocks, inline `code`). Reuse the existing tokens (`var(--mono)`, `var(--surface-muted)`, `code.inl` style for inline code). Place near `.msg p` (`:308`).

### D2 — Chat cadence
- **Autoscroll** — add a `bottomRef` `<div>` at the end of `.convo-inner` and an effect in `CenterPane` that scrolls it into view when `chat` changes / on stream delta. Respect a user who has scrolled up (only autoscroll when near the bottom; otherwise show an unobtrusive "↓ latest" affordance) — D-F.
- **Composer auto-grow** — `panes.jsx` textarea `:305-313`: on change, auto-size (reset `height='auto'` then set to `scrollHeight`, capped ~5 rows / ~200px); reset after send. Add `max-height` + `overflow-y:auto` to `.composer textarea` in `styles.css`.
- **Dead-affordance cleanup** — `attach`/`layers` buttons `:316-317`: per D-C, **hide** them (recommended — don't ship dead buttons) or render disabled with a "coming soon" title. Leave the paid `bolt` `:318-321` and send `:324` exactly as-is.
- **(nice-to-have)** a streaming caret on the actively-streaming assistant message; keep `"Thinking…"` for the no-token-yet state `:281-283`.

### D3 — Clean default chat + demo opt-in (folds S-BS-89)
- **Empty-state default** — `CenterPane`: when `chat.length === 0 && !showExample`, render a clean empty-state (a real greeting + 2-3 suggested prompts) instead of the scripted preamble. Add `const [showExample, setShowExample] = useState(false)`.
- **Gate the scripted showcase** — wrap the preamble `:173-259` + the fake header chips `:158-159` behind `showExample`. Add a small **"Show example"** toggle (header or empty-state — D-E). The canned gen-UI card showcase is preserved, just opt-in.
- **Neutral live-turn identity** — `:266-268` `"JR"`/`"Jordan"` and `:276` `"Lithrim setup assistant"` → a neutral identity for *live* turns (e.g. "You" + initials, "Lithrim"). Source per D-D. (The rail-footer identity `:67-72` is canned chrome — OPTIONAL in this cycle; note it if you skip it.)
- **S-BS-89 — wire "New evaluation"** — `panes.jsx:29` button: add `onClick` that resets to a clean slate (`chat=[]`, `setup={}`, `showExample=false`). `LeftRail` and `CenterPane` are siblings under `App` (`app.jsx:122`), so lift the reset into `App` (D-E: recommend an `App`-held `sessionKey` int bumped on New-eval and passed as `key={sessionKey}` to `CenterPane` to remount it clean — simplest, clears all CenterPane state; pass `onNewEval` to `LeftRail`).

### D4 — Tests (`apps/shell/src/panes.chat.test.jsx` + as needed)
- Markdown: an assistant turn with `**bold**` → `<strong>`; a `- list` → `<li>`; a fenced ```code``` block → `<code>`/`<pre>`.
- **Sanitization (load-bearing):** an assistant turn containing raw `<script>…</script>` / `<img onerror=…>` renders as inert text, NOT a live DOM node.
- Empty-state: a fresh `CenterPane` (chat empty, `showExample` false) shows NO scripted content ("Scribe Agent v4" / "Jordan" / "2,400 samples" absent); clicking "Show example" reveals it.
- New-eval reset: send a message (mock `chatStream`), then trigger New-evaluation → chat cleared.
- Composer/autoscroll: jsdom has no layout — assert at the handler level (auto-grow sets `style.height`; autoscroll calls `scrollIntoView` — mock it).
- **Update `panes.test.jsx` + `panes.chat.test.jsx`** for the new empty-state default. Keep `app.test.jsx` / `bff.test.jsx` / `artifact.test.jsx` / journey test green.

---

## 3. Plan-review decisions (resolve ALL before coding)
- **D-A (load-bearing).** Markdown lib + versions (`react-markdown ^9` + `remark-gfm ^4`) confirmed React-18-compatible at install; sanitization posture = **no `rehype-raw`** (raw HTML inert). State it explicitly.
- **D-B.** User turns: plain text (recommended) vs markdown-rendered.
- **D-C.** Dead buttons (`attach`/`layers`): hide (recommended) vs disabled-with-tooltip.
- **D-D.** Live-turn identity source: neutral literals ("You"/"Lithrim") vs a prop threaded from `App`/`root`; is the rail-footer identity `:67-72` in scope?
- **D-E.** New-eval reset mechanism (remount-by-`key` recommended vs lifted chat/setup state) + where "Show example" lives (header vs empty-state).
- **D-F.** Autoscroll behavior: always-scroll vs only-when-near-bottom + a "jump to latest" affordance (recommended).

---

## 4. Scope guardrails — NOT in scope
- **`apps/shell/src/journey/*` — the FROZEN 4-act demo.** Do NOT touch it. "Demo opt-in" reuses the in-Shell scripted cards behind a toggle; it is NOT journey rework. [memory `unified-authoring-product-frozen-journey`, `shell-journey-chrome-parity`]
- **`apps/bff/*` — no backend/route/loop/prompt changes.** UX-1 is shell-only. (S-BS-91 "post-deny agent UX" is a `loop.py _SYSTEM_PROMPT` fix → ASAFE-1-gated → a *separate* cycle. Note-don't-fix here.)
- **The chat SSE contract** (`bff.js chatStream` body `{message, agent, history}`; the ONB-0 `history` map at `panes.jsx:102`) — unchanged.
- **The gen-UI cards / artifact pane** (`genui/`, `cards.jsx`, `artifact.jsx`) — markdown is for the chat assistant text only, not the cards.
- **No CRUD / judge / flag / agent work** (that's objective #2, a later cycle). **No BYO-Claude / provider work** (BYOC-1).
- **No new deps** beyond the markdown renderer + its required plugin. **No Tailwind.** Plain CSS per the shell convention.

---

## 5. Acceptance
- **A1 — markdown LIVE.** On `:5180`, an assistant message with a heading + list + bold + inline + fenced code + a table renders **formatted** (not literal). **A model message containing raw `<script>`/`<img onerror>` is INERT** (no execution, no injected node).
- **A2 — clean default LIVE.** A fresh Shell (`mode !== "journey"`) opens to the empty-state — NO "Jordan" / "Scribe Agent v4" / fake chips. "Show example" reveals the scripted showcase. "New evaluation" returns to a clean slate.
- **A3 — cadence LIVE.** Streaming autoscrolls to the latest token (and respects scroll-up per D-F); the composer grows with multi-line input; no dead/clickable-no-op buttons remain.
- **A4 — frozen-journey 0-touch.** `git diff` shows ZERO changes under `apps/shell/src/journey/`; `mode="journey"` still renders the unchanged 4-act demo (spot-check live).
- **A5 — green bar.** `cd apps/shell && npm test` (Vitest) all pass — existing (updated) + new; `npm run build` (`vite build`) clean.
- **A6 — shell-only.** `git diff --stat <parent> HEAD` touches ONLY `apps/shell/`.
- **A7 — the load-bearing `:5180` visual smoke (MANDATORY).** Light + dark × the chat surface: markdown formatting, empty-state, autoscroll, composer grow. Executor-driven via Chrome MCP (services are up) or user-run. The shell ships visible defects past build+tests — this gate is not optional. Capture a screenshot for the session log.

---

## 6. Commit structure (atomic, pathspec-only — dirty shared branch)
1. `feat(shell): markdown rendering for chat — react-markdown + remark-gfm, HTML-inert` — `package.json` + `src/components/Markdown.jsx` + `panes.jsx` (assistant render swap) + `styles.css` (`.msg .md`).
2. `feat(shell): chat cadence — autoscroll-to-latest + composer auto-grow + dead-affordance cleanup` — `panes.jsx` + `styles.css`.
3. `feat(shell): clean default chat + demo opt-in; wire New-evaluation reset (S-BS-89)` — `panes.jsx` + `app.jsx`.
4. `test(shell): markdown render + HTML-sanitization + empty-state default + New-eval reset` — `panes.chat.test.jsx` (+ `panes.test.jsx` updates) + the session log `.devloop/sessions/session-bench-salvage-phaseUX-1-2026-06-07.json`.

> **Pathspec-only.** `git add apps/shell/<file> …` then `git commit -- apps/shell/<file> …` (or `git commit` after an explicit-pathspec add). NEVER `git commit -a` / bare — foreign `.claude/` + stray files are in the index. Verify scope with `git diff <parent> HEAD --stat` before each commit. [memory `git-commit-pathspec-dirty-index`]

---

## 7. Verification checklist (before you return)
- [ ] D-A..D-F resolved in the posted plan-review; user said "go".
- [ ] A1-A7 met; A7 screenshot captured.
- [ ] `git diff --stat` = `apps/shell/` only; `apps/shell/src/journey/` 0-touch; `apps/bff/` 0-touch.
- [ ] `npm test` + `npm run build` green (paste counts).
- [ ] Commits are pathspec-only; `package-lock.json`/`package.json` change is intentional + scoped.
- [ ] Session log written (`session-bench-salvage-phaseUX-1-2026-06-07.json`) with the plan-review deviations, A1-A7 evidence, the A7 screenshot path, and any seams opened.
- [ ] `next_session_hint`: monitor runs `/devloop-critique bench-salvage UX-1` (inline) + the `:5180` re-smoke, then closes.

---

## 8. First move
1. Read `EXECUTOR.md` then this driver in full.
2. `curl -s localhost:5180 -o /dev/null -w "%{http_code}\n"` + `curl -s localhost:8787/health` — confirm up; do NOT autostart.
3. Skim `panes.jsx` (`CenterPane` `:80-335`) + `bff.js chatStream` + `styles.css` (`.convo`/`.msg`/`.composer`) + `root.jsx`.
4. Resolve D-A (markdown lib + sanitization) first; post the plan-review (D-A..D-F). Do NOT write code until "go".

---

## 9. References
- The surface: `apps/shell/src/panes.jsx`, `bff.js`, `root.jsx`, `app.jsx`, `styles.css`, `data.jsx`.
- Frozen demo (DO NOT TOUCH): `apps/shell/src/journey/*`; `root.jsx mode="journey"`.
- Seams: **S-BS-89** (blank-slate New-eval — closed by D3) · **S-BS-91** (post-deny agent UX — OUT, ASAFE-1-gated loop change).
- Memories: `unified-authoring-product-frozen-journey`, `shell-journey-chrome-parity`, `browser-mcp-confirm-blocks-renderer` (Chrome-MCP can't accept a native `window.confirm`; UX-1 doesn't add one — the paid gate is the in-DOM `CostModal`), `git-commit-pathspec-dirty-index`.
- Stream state: `.devloop/state/STREAM_bench-salvage.md`.
