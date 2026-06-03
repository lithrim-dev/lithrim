# KICKOFF — `/ux-copy` + `/design-critique` on the Lithrim journey

> **You are a fresh session resuming a long build.** Your job: run **`/ux-copy`** and
> **`/design-critique`** on the Lithrim shell "Journey" (Acts 1–4), **grounded in the product thesis
> and the founder's design bar** — not generic best-practices. Do not re-build the journey; critique
> it and propose copy/design fixes.
>
> **Read first:** [`HANDOFF_shell_journey_2026-06-03.md`](HANDOFF_shell_journey_2026-06-03.md) — the
> full context (thesis §1, the design bar §2, the act-by-act state §3, how to run §4, files §5, the
> real-vs-prop honesty map §6). Everything below assumes you've read it.

## 0. Why a fresh session
The build session that produced this is context-saturated. This is a clean room with the same
context, loaded from the handoff. Resume from the exact point: journey rebuilt, **Act 2 wired to the
real engine**, Acts 3 & 4 still props, all uncommitted.

## 1. Set up so you critique the REAL thing (not the fallback)
A dead BFF makes Act 2 silently show the *old prop* reveal — you'd critique the wrong artifact.
Before anything:
1. Start the dev server + the BFF per **HANDOFF §4**. Confirm `curl localhost:8787/health` → `ok`
   and `POST /v1/run-eval {live:false}` returns a real verdict + 3 judge votes.
2. **See it running.** Prefer driving the founder's own browser via the `Claude_in_Chrome` MCP
   (`tabs_context_mcp` → `navigate http://localhost:5180` → `browser_batch` of clicks + screenshots)
   so they can follow — NOT the `Claude_Preview` MCP (separate session they can't see; see HANDOFF §4).
   Walk all 4 acts; in Act 2 click **Verify** (replay) and read the real judge reasoning in the panel.

## 2. The mandate
Invoke the two skills on `apps/shell/src/journey/` (copy lives in `journeyData.js`; structure/staging
in `JourneyApp.jsx` + `jp1–jp4.jsx`):

- **`/design-critique`** — judge the journey against the founder's bar (HANDOFF §2), in order:
  does it *stop a blind-clicker*; is the value *evident* (not buried in tabs); is it
  *believable + intellectual* (grounded numbers, not props); is the *user the hero*; is it *their
  problem* (any agent, not a clinical toy); is it *not handwavy* (does it actually run / show
  receipts); is it *conversational-first* (staging, timing, auto-scroll). Call out where Acts 3 & 4
  being props (HANDOFF §6) undercuts believability, and where the real Act 2 is strongest.
- **`/ux-copy`** — review + rewrite the journey copy against the thesis: **honest** (no overclaiming
  beyond what actually ran — e.g. don't say "unanimous" when risk_judge can PASS), **sharp**,
  **conversational-first**, **hero-centric** ("you tuned it"), **maps to *their* agent**, and lands
  the **aha → conviction → ownership** arc. The current copy is in `journeyData.js` (`ACTS`, `EXCHANGE`,
  `CALIB`, `PROGRESSION`, `JUTE_PROMPT`, `BOT_HINTS`, `SESSION`, …) and inline in `jp2–jp4.jsx`.

## 3. Honesty constraints (hard — from the thesis + `CLAUDE.md`)
- Critique against **what actually executes** (HANDOFF §6). Flag any copy that asserts more than the
  engine shows. The whole project exists to kill handwavy/story-shaped claims — your critique must
  hold the same bar.
- Don't weaken the paper claim or the moat framing without founder say-so.
- **Cost:** replay grades are `$0`; each **"Run live"** is a real paid Azure call (~$0.30). Use
  replay for walkthroughs; only fire live deliberately.

## 4. Deliverable
Write the findings to `docs/design/` as a dated critique doc (e.g.
`CRITIQUE_journey_ux_design_<date>.md`): per-act, prioritized, with concrete copy rewrites and design
fixes, each tagged by which bar (§2) it serves. Separate **quick wins** (copy/staging tweaks) from
**structural** (e.g. "wire Act 3's floor to the real `grounded` so the number stops being a prop").
End with the single highest-leverage change.

## 5. Out of scope for this session
Building the Act 3/4 real wiring and committing (HANDOFF §7) — note them as recommendations; the
founder will decide whether to act on them in a follow-up build session.
