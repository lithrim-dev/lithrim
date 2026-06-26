# UI teething / cadence — findings & devloop phase plan (2026-06-26)

**Context.** During the ClinVerdict Step-One validation (author a clinical eval entirely from the
UI, match the physician's verdicts) the engine work landed, but the **shell chrome has teething
issues that break the conversational-first UX** the moment you actually drive it. This is the
punch-list for a focused UI-polish devloop phase, kept ahead of the tooling (MCP/API connector)
work. Every issue below is **CONFIRMED** against source (file:line), per the diagnose-before-edit
rule — no story-shaped UI diagnoses.

Cross-references: the engine/authoring findings from Step-One live in memory
`ui-pack-authoring-gap.md` (the Core/Pro authoring boundary + the `when_to_use` field bug) and
`clinverdict-step-one-roadmap.md`. This doc is the **UI chrome** layer only.

---

## Part A — confirmed teething issues (the devloop phase)

### T1 — Missing theme tokens → transparent popovers + mis-colored inline-card text  **[DONE — verified live 2026-06-26]**

> Shipped: `--panel`/`--text`/`--fg` defined in both theme blocks of `styles.css` (aliased to `--ink`;
> `--panel` = elevated surface). Guard test `theme_tokens.test.js` (RED→GREEN; also pins the whole
> class — any used-without-fallback custom prop must be defined). Verified live: the session-menu
> popover now renders opaque, no bleed-through over the journey rail.


Three CSS custom properties are referenced in inline styles but **never defined** in `styles.css`
or `theme.css`, and used **without a fallback** — so `var(--x)` resolves to *nothing*:

```
--panel   used: apps/shell/src/auth.jsx:31  (LoginScreen card background)
                apps/shell/src/panes.jsx:146 (session-menu popover background)
          → background: var(--panel)  ⇒ TRANSPARENT popover
--text    used: apps/shell/src/auth.jsx:34,44 · panes.jsx:153,158,163
          → color: var(--text)        ⇒ inherited color, not the intended ink
--fg      used: apps/shell/src/genui/CaseCard.jsx:41 (case body)
                apps/shell/src/genui/VerdictCard.jsx:100 (verdict reasoning)
          → color: var(--fg)          ⇒ wrong color on the INLINE GEN-UI (primary surface)
```

Verification sweep (used-vs-defined custom props): **52 defined, 34 referenced; 3 referenced are
undefined-with-no-fallback** (`--panel`, `--text`, `--fg`). `--accent-bg`/`--surface` are used with
fallbacks; `--radix-select-trigger-width` is injected by Radix at runtime — neither is a bug.

**Symptom (screenshot 1):** the footer session menu ("Not signed in · server is open / Connect AI /
Sign in…") renders over the Setup-journey text below it because its background is transparent.

**Why it matters beyond the popover:** `--fg` colors the **CaseCard body and the VerdictCard
reasoning** — the inline gen-UI that `SPEC_CONVERSATIONAL_FIRST` makes the *product surface*. A
theme-token gap there is not cosmetic; it degrades the canonical surface.

**Fix.** Define the three tokens in **both** themes (`:root` light + the `.dark`/dark block) in
`styles.css`, aliased to existing tokens so they track the palette:
- `--text` → `var(--ink)` · `--fg` → `var(--ink)` (both are body-text foregrounds)
- `--panel` → an elevated surface: light `#FFFFFF`, dark `#1B2336` (= `--surface-muted` dark),
  so a popover/card lifts above the `--surface-2` rail with the existing border + `--shadow-pop`.

**Risk:** low — additive token definitions; no existing rule changes. **Test (RED first):** assert
the session-menu popover (`data-testid="session-menu"` region) computes a non-transparent
`background-color`, and that `--panel`/`--text`/`--fg` resolve to a non-empty value in both themes
(or a focused unit assertion on the resolved style). **This is the headline driver** — it closes a
*class* of bug across the menu, the login card, and the two inline cards in one small change.

---

### T2 — Non-monotonic Setup journey ("③ NOW" sitting before two ✓ steps)  **[CONFIRMED]**

`apps/shell/src/journey.js` derives each step's done-ness from **independent** predicates, and
`current` = the *first incomplete required step*. Because `Ground truth` is `done ⟺
verification_contracts present` (a strict gate) while `Run`/`Review` are done from run state, a user
who ran + reviewed **without** authoring a ground-truth contract gets:

```
✓ Domain   ✓ Judges   ③ Ground truth [NOW]   ④ Knowledge base   ✓ Run   ✓ Review     (4 / 5)
```

The count `4 / 5` is numerically correct (KB is the one optional step, excluded from the
denominator — `journey.js:24,81`). But the **state reads as a render glitch**: a "NOW" badge on
step 3 with completed steps 5 & 6 after it, and node glyphs interleaving `✓ ✓ 3 4 ✓ ✓`.

**Root cause (journey.js:32-56, 64-86):** `isDone(...)` is per-step and order-independent; nothing
reconciles a *leapfrogged* required step against the `current` pointer.

**Fix options (final treatment is a plan-review call):**
- **(A) Monotonic + "skipped" affordance (recommended).** `current` = the first incomplete required
  step that has **no completed required step after it** (the true frontier). A required step that is
  incomplete *but* has completed work downstream renders as **"skipped / needs a fact-check"** (an
  attention marker + an "add this" chip), **not** "NOW". This *keeps* the legitimate nudge (Ground
  truth is the moat — you ran without a floor) while killing the you-are-here-and-also-past-here
  contradiction.
- (B) Pure monotonic hide: never mark an earlier step current once a later one is done (loses the
  nudge — not recommended; the floor-skipped signal is valuable).

**Risk:** medium — touches the shepherd plan surface; `journey.test.jsx` already pins the existing
state machine, so the driver writes new RED cases for the leapfrog scenario and keeps the green ones.

---

### T3 — Connect AI "Assign models" rows starve the model input  **[DONE — verified live 2026-06-26]**

> Shipped: `AssignModelsSection.jsx` rows are now one shared CSS grid (`ROW_GRID`:
> `150px 128px minmax(120px,1fr) auto`) so label · provider · model · action align across all rows;
> the `✓ provider · model` status moved to its own line (`STATUS_INDENT`) so it can never starve the
> input. The Connect AI modal widened `560 → 620px` (`panes.jsx`) to clear a residual horizontal
> scrollbar from the wider "Apply to 3 judges" button. Verified live: aligned grid, no overflow, full
> labels. (Existing `provider_center`/`connect_ai_consolidate`/`AssignModels` tests stay green.)


`apps/shell/src/genui/AssignModelsSection.jsx`: each consumer row is a single flex line holding a
150px role label + a 130px provider `<select>` + the model `<input style={width:"100%"}>`
(`:106`) + the **Assign** button + a **non-wrapping** `✓ {provider} · {model}` assigned label
(`:152`, `whiteSpace:"nowrap"`). The long assigned label (e.g.
`✓ azure · Llama-4-Maverick-17B-128E-…`) consumes the row, and a `width:100%` (non-`flex`) input
collapses to a sliver — screenshot 2's cramped/truncated `faithfulness_judge` box.

**Fix.** Make the input a real flex child: `flex: 1; min-width: <~140px>` (drop `width:100%`); let
the assigned `✓ provider · model` label `text-overflow: ellipsis` (or wrap to a second line) instead
of `nowrap`-starving the row. Consider stacking the picker controls above the status on narrow
widths.

**Risk:** low — local layout in one component; `provider_center` / `connect_ai_consolidate` tests
already cover the binding flow, so keep them green and add a width/overflow assertion if practical.

---

### T4 — Connect AI controls don't reflect an already-saved binding  **[DONE — code complete, live-blocked]**

Surfaced while verifying T3's populated state: a role that is **already assigned** (`✓ azure · gpt-4.1`
on its own line) still shows an empty `— provider —` dropdown and empty model field — so a fully
configured panel reads as unconfigured. **[CONFIRMED]** root cause: `AssignModelsSection` seeds its
editable pickers from local `sel` state (empty until the user types), never from the saved `bindings`
the `✓` line reads.

> Shipped (code): a `useEffect` seeds each row's `{provider, model}` from its saved binding
> (`CONNECT-AI-PREFILL-1`), only for rows the user hasn't touched (never clobbers an in-progress
> edit; no-op once seeded). Tests-first: `connect_ai_azure.test.jsx` E (pre-fills from the `ALL_FOUR`
> azure fixture) + E2 (non-vacuous: an unbound role stays empty) — RED→GREEN.

> **Live demo blocked (honest):** the dev-server BFF currently returns `connected_providers: []` and
> all roles `null` (`GET /v1/roles/bindings`), because the configured azure key + role bindings lived
> in the **Docker stack that was stopped** — the standalone dev BFF doesn't load them. So the live
> panel correctly shows empty (nothing to pre-fill), and the populated pre-fill can't be screenshotted
> here without re-entering an azure key (a credential the user enters, not the agent). The fix is
> proven by the E/E2 tests; it will pre-fill the moment the BFF returns real bindings.

---

## Part B — feature direction surfaced alongside (NOT in the teething phase)

From the product-brainstorm: *"provide commonly available models + support configuring them; create
one or multiple judges with one of the configured providers."* The Connect AI panel already does
most of this — connect a provider + key (`ProvidersSection`), assign a `{provider, model}` per
consumer with a **preset catalog + free-text** model field (`getModelCatalog`, Azure-deployment
typing). Two gaps remain, and they are **features, sequenced after the teething fixes**:

1. **Commonly-available-model presets** — surface/extend the catalog so the "model" field offers the
   well-known models per provider (OpenAI/Anthropic/Gemini/Bedrock/Azure) as first-class picks, not
   only free text. (Catalog plumbing exists via `getModelCatalog`.)
2. **Create N judges bound to a configured provider** — today you bind a model to the **three fixed
   judge roles**; authoring a *new* judge bound to a provider is the tier:core JudgeBuilder path (see
   memory `ui-pack-authoring-gap.md` + `ce-model-registry-and-phase2-judges.md`). The provider-first
   binding (`provider-center-cline-style-direction.md`) is the larger arc this rolls up into.

These do **not** block the teething phase; they are the next program once the chrome is clean.

---

## Part C — Step-One calibration findings (recap — full detail in memory)

Authored a clinical eval **UI-only** on a scaffolded `tier:core` `clinverdict` pack and matched the
physician (Sharif):

| Case | Sharif's classification | Lithrim result |
|---|---|---|
| 02 | Hallucination + Omission | `[HALLUCINATED_DETAIL, HISTORY_OMISSION]` — exact ✓ |
| 06 | Omission + Hallucination | `[HALLUCINATED_DETAIL, HISTORY_OMISSION]` — matches Sharif ✓ (+ minor risk `INTERNAL_INCONSISTENCY` WARN) |
| 08 | None (correct note) | `[]` · PASS — exact ✓ |

**Honest correction:** my answer key had case 06 as `VALUE_MISMATCH`; Sharif actually classified it
"Omission & Hallucination", so the judge's `HALLUCINATED_DETAIL` *matched the physician* and my key
was the mis-mapping. The system reported the physician's real call rather than bending to a flawed
target — honesty-is-the-moat in practice. **The answer key is itself an authored artifact and needs
the same scrutiny as the judges.**

The authoring-loop gaps that forced on-disk edits (so the UI must eventually expose): editable flag
`when_to_use` (the CriterionBuilder `Definition`→`when_to_use` field bug — **priority**), editable
judge base prompts, hard lens scoping, cache-bust-on-edit, UI pack creation, a pack selector on
workspace create. Full punch-list: memory `ui-pack-authoring-gap.md` (2b–2d).

---

## Devloop phase sequence

1. ~~**T1** — theme tokens~~ **DONE** (styles.css + theme_tokens.test.js; verified live).
2. **T2 — journey monotonicity** — reconcile the `current` pointer with leapfrogged required steps
   (option A: "skipped/needs-fact-check" affordance). **NEXT.** Still observable live: the optional
   Knowledge-base node renders a number ("4") interleaved between done (✓) required steps.
3. ~~**T3** — Connect AI Assign-models layout~~ **DONE** (AssignModelsSection.jsx grid + panes.jsx
   modal width; verified live).

Each: tests-first (RED → GREEN), staged + proposed (no auto-commit, no push). The cadence stays
open — surface further teething issues as they appear while driving the live UI.

### Files touched (staged, awaiting commit approval)
- `apps/shell/src/styles.css` — T1 tokens
- `apps/shell/src/theme_tokens.test.js` — T1 guard (new)
- `apps/shell/src/genui/AssignModelsSection.jsx` — T3 grid + T4 prefill effect
- `apps/shell/src/panes.jsx` — T3 modal width
- `apps/shell/src/genui/connect_ai_azure.test.jsx` — T4 prefill tests (E/E2)

> Out of scope / untouched: `apps/shell/src/app.jsx` carries a **pre-existing** WIP edit (the
> `.lights` + `ModeSwitch` chrome commented out) that fails `app.test.jsx`'s mode-switch assertion.
> Not introduced by this phase; left for the owner to resolve.
