# Inline critique — `bench-salvage` UX-1 (chat markdown + cadence + clean-default)

> **Mode:** inline (driver is NOT a HARD-GATE — shell-only, no spec/API contract, no paid path, no core invariant).
> **Critic:** monitor (cold-read of driver §2-§5 + the committed diff `c58d7f2..f8bed47`).
> **Date:** 2026-06-07 · **Verdict: NON-BLOCKING** (0 blocking / 2 NB / 0 OQ).

The 7-item mechanical audit passed (commits real, scope shell-only, 61/61 re-run green, build clean, foreign files never swept, session log well-formed, deviations justified). This critique is the spec-adherence pass.

## Q1 — Surface fidelity
Every decision matches the driver's recommendation as ruled at GO:
- **D-A** `react-markdown@^9.1.0` + `remark-gfm@^4.0.1`, **no `rehype-raw`**, links hardened `target=_blank rel="noopener noreferrer nofollow"` — `Markdown.jsx` is minimal and exactly this. ✓
- **D-B** user turns stay plain (`<p whiteSpace:pre-wrap>`); only the assistant render swaps to `<Markdown>`. ✓
- **D-C** dead `attach`/`layers` buttons removed; paid `bolt` + send untouched (CONFIRMED live: composer left-bar shows only the bolt). ✓
- **D-D** neutral live identity (You / Lithrim); chrome left per R1. ✓
- **D-E** New-eval = remount-by-key (`App` `sessionKey` `:75` → `onNewEval` `:124` → `key={sessionKey}` `:126`); "Show example" lives in the empty-state. ✓
- **D-F** autoscroll only-when-near-bottom + a "↓ latest" pill. ✓

## Q2 — Behavioral fidelity (3 chains traced spec → test → impl)
1. **Raw HTML is inert (A1).** `Markdown.test.jsx:32-48` renders a message mixing `**markdown**` + `<script>` + `<img onerror>`; asserts `<strong>` rendered AND `querySelector('script'|'img'|'[onerror]')` all null AND `window.__xss` undefined. → `Markdown.jsx` omits `rehype-raw`. **Non-vacuous** (the markdown-rendered half proves it isn't an empty render; the guard fails if anyone adds `rehype-raw`). Strongest test in the cycle. ✓
2. **Clean default (A2).** `panes.chat.test.jsx:154-167` asserts the greeting present + "Scribe Agent v4"/"Jordan"/"2,400 samples" absent, then clicks "Show example conversation" and asserts they appear. → `panes.jsx` `showExample` gate + empty-state. CONFIRMED live (`:5180` Shell opens clean). ✓
3. **New-eval reset (A2/S-BS-89).** `panes.chat.test.jsx:179-190` renders `<App mode="shell">`, sends "reset me please", asserts it shows, clicks "New evaluation", asserts it's **gone** + the empty-state is back. → drives the real `App→LeftRail→onNewEval→sessionKey→remount` chain. Non-vacuous. ✓

## Q3 — Out-of-scope intrusion
None. The diff is exactly the deliverable files (9 `apps/shell/` + 2 `.devloop/sessions/` bookkeeping). BFF, `apps/shell/src/journey/`, `bff.js` (SSE contract), `genui/`, `cards.jsx`, `artifact.jsx` are all git-verified 0-touch. The ONB-0 history contract is intact (`panes.jsx:107`). Two documented deviations, both sound: (a) commit 3 folded the `.empty-state` CSS so markup+styles ship together (driver §6 literal was `panes.jsx + app.jsx`); (b) the session-log/A7-note split into a 5th commit so cited hashes are real (EXECUTOR.md). Neither is scope creep.

## Q4 — Spec ambiguity surfaced
- **R1 (chat-surface vs chrome)** — the executor correctly read A2's "no Scribe Agent v4/Jordan" as scoped to the **CenterPane chat surface**, leaving the test-locked TopBar crumb + rail-footer as chrome. Surfaced at plan-review, ruled by the monitor, recorded as **S-BS-93**. Correct call (the driver itself declared the rail-footer optional).

## Findings
- **NB-1 (broaden S-BS-93).** `app.jsx` `StatusBar` (`:42-58`) still renders fake status ("Run #218 / 1,488 / 2,400 / κ 0.88 / acc 92.4%") — the same persistent-fake-chrome category as the rail-footer + crumb, but not named in S-BS-93. Broaden S-BS-93 to cover the StatusBar too, so the future "real chrome from auth + the active run" cycle doesn't miss it. Not a UX-1 defect (out of the chat-surface scope by R1).
- **NB-2 (A7 evidence durability).** The executor's A7 screenshots live only in its transcript (Chrome MCP exposed no on-disk path), indexed by ID in the A7 note. **Mitigated:** the monitor independently re-ran the `:5180` smoke (A2/A3/A4 confirmed live, light) at close. For future load-bearing visual smokes, prefer an on-disk artifact path or a monitor re-smoke (done here).

## Disposition
NON-BLOCKING. S-BS-89 CLOSED. S-BS-93 opened (broaden per NB-1). No proof capsule: UX-1 is a UX-polish cycle, not a product-capability A-LIVE attestation with an honest-Δ — the proof-capsule ritual does not apply. Next cycle: **BYOC-1**.
