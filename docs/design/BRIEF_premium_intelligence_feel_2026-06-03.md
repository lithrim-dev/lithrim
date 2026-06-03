# BRIEF — Premium feel + micro-interactions (Claude-Code-class conversational intelligence)

> **Status:** design-language cues (founder's vision, 2026-06-03). **Paste-ready for Claude Design.**
> **Direction (confirmed):** **NOT sci-fi / not a HUD / not a spy-cockpit.** Keep the existing **3-pane,
> Claude-Code-like conversational shell** (left rail · center conversation · right artifact pane). The
> "intelligence" shows through the *conversation* and through **generative-UI components that render
> exactly where needed** — not through theatrics. Reference feel: **Claude Code / Claude desktop /
> Linear / Claude artifacts** — calm, refined, expensive-through-restraint.
>
> **Hard boundary:** this is the *feel* layer only — motion, micro-interactions, component craft,
> polish. **It does NOT change the core product:** the four acts, the conversational flow, the copy
> substance, the council, the worst-of rule, or any number. Apply on top of `apps/shell/src/`
> (navy/coral/teal/Geist tokens in `styles.css`; gen-UI registry in `genui/`).
>
> **Honesty guardrail (load-bearing — it IS the brand):** premium polish is *earned*, never theatrical.
> Every animated signal must be wired to something real — 3 real judges, real token/latency/cost, the
> real audit chain, real provenance. **No fake telemetry, no invented "sources scanned," no decorative
> streaming.** A premium feel earned by real receipts *is* the by-construction thesis expressed as UX.

---

## 1. The thesis (one line)
**A calm, intelligent system you converse with — Claude-Code-grade.** The smarts are felt in the
quality of the conversation and in **purposeful gen-UI cards that appear right when the moment needs
them**, animated with weight and restraint. Confident, professional, quiet. It should feel like the
best conversational tool you've used — not like a movie about spies.

## 2. Principles
1. **Conversation-first.** The center thread is the product. Everything premium happens *in the flow*:
   the assistant reasons, then **renders a component inline** to show its work. No value hidden in a
   tab the user never opens.
2. **Gen-UI where needed.** Components (council card, calibration scorecard, the pair, audit trace,
   config, floor contracts) materialize contextually in the conversation — each one purposeful, each
   one entering with a small, weighted motion. This *is* the "intelligence" expression. (Build on the
   existing `renderTool`/registry pattern.)
3. **Weight, not bounce.** Motion *settles* like it has mass — no springy overshoot, no playful easing.
   `cubic-bezier(.2,.7,.3,1)` family, firm landings. Things arrive deliberately. (Claude-Code calm, not
   consumer-app perky.)
4. **Color is signal.** ~90% ink/slate/surface. Coral = a decision/alert fired. Teal = grounded/
   verified. Amber = caution. When color appears, something *happened*. (Also de-flattens today's
   all-coral.)
5. **Inspectable, quietly.** Hover a finding / condition / dose / judge → a subtle inline popover with
   its provenance (source, span, link to ground truth) — Claude-Code citation style, not an intel
   graph. Depth on demand, never shouted.

## 3. Micro-interactions, surface by surface
> Feel-only; each maps to an existing element. Durations are starting points. Keep it restrained.

### The reveal — Act 2 (hero moment; also fixes critique A2.3)
- **Judges stream in like reasoning sub-steps**, not a spinner. On Verify, the three judge rows arrive
  one at a time (the existing 650/1300/1950ms stagger, refined) — each with a quiet "thinking" shimmer
  that resolves into its vote + reasoning. Reads like the assistant working through the council, the
  way Claude Code streams steps. (Real: the 3 real judges.)
- **The verdict lands with weight.** `BLOCK` settles in (~8px drop, 220ms, firm landing) with a calm
  underline that draws beneath it. Hold the beat — let it sit.
- **The reversal becomes the dominant beat (fixes A2.3).** After a ~900ms hold, the verdict gently
  recedes/desaturates and *"it's calling the patient's real history fabricated"* rises to take over as
  the primary element — equal or greater weight than the verdict it overturns. The turn should *land*,
  not read as a footnote under a big "BLOCK."
- **Surface the dissent.** `risk PASS` in the 2–1 tally gets a quiet amber tick — "one judge
  disagreed" should catch the eye, because instability is the point (and it's the honest story).

### Gen-UI components (the core of the feel)
- Treat every inline card as a **first-class generative-UI moment**: it enters with a soft stage-in
  (header → body, ~60ms apart), has a calm hover/elevation, and is **inspectable** (expand for detail/
  source). The council card, the calibration scorecard, the pair, the floor contracts, the config —
  all the same refined component language.
- **Decode, don't dump (fixes critique G4).** The Act 2 note panel currently shows raw FHIR JSON.
  Render it as a **clean decoded document** — parsed sections, with the flagged spans (the injected
  dose, the fabricated condition) underlined and hover-revealing *why* they're flagged. Honest +
  premium; pure presentation, same data.

### The audit chain — Act 4 (provenance, done as a component)
- A clean gen-UI trace that **builds progressively** (links reveal top-to-bottom, ~80ms stagger) with a
  connecting line — a chain of custody assembling. **Hover a link → expand to its evidence; click →
  scroll the source span into view and flash it.** Calm, not cinematic. This is your most
  provenance-native surface — let it be quietly impressive.

### The artifact pane (right)
- Already slides (`slidein .28s`). Add a touch of mass: faint elevation on open, content staging in 2–3
  beats. Fullscreen = a confident zoom, not a jump. Treat it exactly like a **Claude artifact** —
  openable, fullscreenable, calm.

### Conversation craft + chrome
- Make the **thread itself** feel premium: considered message rhythm, the beat-tags (`ACT 2 · THE
  REVEAL`) as quiet section markers, smooth auto-scroll to the latest beat (already wired — make it
  buttery).
- **⌘K command palette** as the primary verb (already in the bar) — a real spotlight: recent evals,
  run a command, fuzzy nav. Keyboard-first, Claude-Code-style.
- **Crisp `:focus-visible` rings (fixes critique a11y).** Reuse the `composer-box`
  `0 0 0 3px var(--accent-soft)`. The ←/→ act nav should feel deliberate and visible.
- **Status bar = calm, real metadata.** Connection state, pack version, BYOK — understated, a slow
  live-dot on "connected." Real numbers only (e.g. real token/cost on a live grade). No faked telemetry.

### States
- Empty/idle ("Awaiting verification," "No run yet") → calm, helpful, *ready* — a quiet glyph + one
  line, the way Claude Code rests between turns. Loading → the "assistant working" feel above, never a
  dead spinner.

## 4. Motion system (starting values)
- **Durations:** micro 120–160ms · element-in 220–280ms · staged hero beats 600–900ms.
- **Easing:** `cubic-bezier(.2,.7,.3,1)` for entrances; `ease` for fades. **No spring overshoot.**
- **Stagger is the signature** — judges, audit links, card sections arrive in sequence (= "the system
  is reasoning"), never all at once.
- **Respect `prefers-reduced-motion`** (also an a11y fix): collapse staged reveals to instant; keep all
  the information.

## 5. Color · texture · type
- **Restraint, not grain/RGB.** Clean surfaces, hairline 1px borders (already there), subtle elevation
  on popovers and the artifact pane, the existing soft `--desk` background depth. Premium = calm and
  precise, not textured-busy.
- **Color discipline.** Lean the base toward ink/slate so coral/teal *pop as events* (the verdict, the
  floor-flip, the dissent). Color marks that something happened.
- **Type.** Geist + Geist Mono are perfect. **Mono for all data/telemetry** (counts, IDs, votes,
  latency, cost) = "machine truth"; sans for prose. Confident display size on the verdict; tight
  tracking on big numbers. Numbers may *count up* to their (real) value rather than snapping.

## 6. What NOT to do
- ❌ Sci-fi / HUD / spy aesthetics — no scan-lines, reticles, crosshairs, cockpit framing, "intel
  stations." (Wrong genre; you corrected this.)
- ❌ Fake streaming/telemetry or invented activity that isn't real work.
- ❌ Bouncy/playful motion — reads consumer-app, not Claude-Code calm.
- ❌ Color everywhere — kills signal value and calm.
- ❌ Anything that slows the user — gravitas ≠ slow; utilities stay instant, only hero beats hold.
- ❌ Moving the value out of the conversation into chrome the user must hunt for.

## 7. Where it bites first (highest feel-per-effort)
1. **The Act 2 reveal** — judges streaming in → weighted verdict → dominant reversal. (Hero moment +
   fixes the one real UX weakness, A2.3.)
2. **Gen-UI component language** — one refined enter/hover/expand pattern applied to every inline card
   (council, calibration, pair, floor, config). This is the whole "premium conversational" feel.
3. **The note decoded** (G4) + **the audit chain as a build-and-inspect component** — your
   provenance-native surfaces.
4. **Chrome polish** — ⌘K, focus rings, calm status bar, buttery auto-scroll.

## 8. Three feel-upgrades that double as critique fixes
The premium layer and the honesty work pull the same direction:
- weighted, dominant **reversal** in the reveal → fixes **A2.3** (the hook was subordinate to the verdict);
- raw-FHIR → **decoded document** with flagged spans → fixes **G4**;
- crisp **`:focus-visible`** rings → fixes the **a11y** gap.

---

**Workflow:** founder explores in Claude Design, brings back what they like, I port it into the real
Journey (`apps/shell/src/`). The two paste-ready prompts below seed that exploration so the output is
already honest + on-brand + portable.

---

## 9. Paste-ready Claude Design prompts

### 9a. HOUSE STYLE — reusable preamble (paste at the top of ANY surface prompt)

```
Design a screen for a premium, calm, Claude-Code-class CONVERSATIONAL desktop app
(3-pane: left nav rail · center conversation thread · right artifact/detail pane).
NOT sci-fi, no HUD, no scan-lines/reticles/cockpit. Reference feel: Claude Code,
Claude artifacts, Linear — refined, professional, expensive-through-restraint.

Brand tokens (dark theme):
  bg #0F1524 · ink #EAEDF4 · muted #8B93A8 · border #27314A
  coral/accent #F06A4B (a decision/alert fired) · teal #46BC9B (grounded/verified)
  amber #ECA24C (caution) · slate #8D97B6
  Fonts: Geist (prose) + Geist Mono (ALL data: numbers, IDs, votes, latency, cost).
  Radius 10px. Hairline 1px borders. Subtle elevation on cards/popovers.

Motion: weight, not bounce. Easing cubic-bezier(.2,.7,.3,1), firm landings, NO spring
overshoot. Micro 120–160ms; element-in 220–280ms; dramatic hero beats 600–900ms.
Stagger reveals (one thing arrives after another = "the system is reasoning").
Honor prefers-reduced-motion (collapse to instant, keep all info).

Color is signal: ~90% ink/slate/surface; color appears only when something happened.

HONESTY (hard rule): every number/label is REAL data I provide — never invent
placeholder metrics, never show "unanimous"/fake confidence/fake telemetry/"sources
scanned." If you'd normally fill a stat, leave a labeled slot for real data instead.
```

### 9b. ACT 2 — "The reveal" (hero moment; real data baked in)

```
[Paste the HOUSE STYLE preamble above first, then:]

Center conversation, one assistant turn that reveals a verification result, in 3 timed beats:

BEAT 1 — the council deliberates: three judge rows stream in one at a time (650/1300/1950ms),
each with a quiet "thinking" shimmer that resolves into a vote. Real judges + verbatim reasoning:
  • risk_judge (gpt-4.1) — PASS, conf 1.0 — "No HIPAA violations found. All PHI was provided
    inbound by the patient; the agent did not disclose or confirm any PHI from internal records."
  • policy_judge (Mistral-Large-3) — BLOCK, conf —(none) — "The artifact contains fabricated
    medical and social history never discussed in the transcript: Diabetes mellitus type 2, AIDS,
    hepatitis C, anemia, plus social findings."
  • faithfulness_judge (Llama-4-Maverick) — BLOCK, conf 1.0 — "Fabricated medical history and
    details not supported by the transcript."

BEAT 2 — the verdict lands with weight: large "BLOCK" (coral) drops in ~8px/220ms with an underline
that draws beneath it. Below it, a mono tally — "risk PASS · policy BLOCK · faithfulness BLOCK" —
with the lone PASS marked by a small amber tick (surface the dissent; do NOT call it unanimous).
A quiet provenance line: "real grade · replay · $0 · 3 judges · 116,908 tokens".

BEAT 3 (the turn — make THIS the dominant element, heavier than the verdict): after a ~900ms hold
the verdict gently recedes/desaturates and this rises to take over:
  "It flagged the whole history as fabricated. Five of those — AIDS, hepatitis C, anemia — are in
   the patient's chart. One, type-2 diabetes, is in neither chart nor transcript: that one's a real
   fabrication. It can't tell them apart, because it only read the 41-second transcript."

Right pane = the graded note as a DECODED clinical document (not raw JSON): parsed SUBJECTIVE /
PMH / PLAN sections; the PMH lists the conditions with the fabricated "Diabetes mellitus type 2"
underlined in coral and the charted-but-flagged ones (AIDS, hepatitis C, anemia) underlined in
amber; hovering any flagged line reveals why it was flagged + its source (chart vs transcript).

Provide: idle, deliberating, and revealed states; the timed motion spec; light + dark.
```

**Bring back (REFERENCE ONLY — I do NOT copy Design's code):** screenshots of each state + ideally a
short screen-grab of the motion (or the share link so I can poke the interactions). The shell is now on
**Tailwind**, so I re-implement the look as **our own** components — idiomatic to the migrated stack,
wired to the real `REVEAL` engine data — using Design's output purely as a designer's take to study
(spacing, hierarchy, motion, premium feel), never as source to lift. If Design swapped in placeholder
numbers, flag it; I wire the real verified values regardless. (This whole Claude-Design step is an
exercise to get a designer's eye on a polished premium experience — the deliverable to the product is
*our* re-implementation, not theirs.)
