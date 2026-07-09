# Lithrim Product Shell (`apps/shell`)

The 3-pane conversational eval workspace, the shell skeleton, ported from a
design prototype into a real Vite + React app, pixel-faithful to the prototype.

## Run

```bash
cd apps/shell
npm install
npm run dev          # http://localhost:5180
```

### With the real eval-report

The **Report** tab in **Shell** mode renders a real `run_eval` result over the BFF. Start
the BFF alongside vite (see [`../bff/README.md`](../bff/README.md)):

```bash
pip install -e ".[bff]"                              # from the repo root
uvicorn app:app --app-dir apps/bff --port 8787       # the judge-capability API
npm run dev --prefix apps/shell                      # http://localhost:5180
```

The vite dev proxy forwards `/v1` → `:8787` (override with `VITE_BFF_URL`). Switch to
**Shell** mode and press **Run eval** (replay, $0) or **Run live** (one paid live council call).

### Tests

```bash
npm test            # vitest (watch)
npm run test:run    # vitest run (CI / one-shot)
```

Vitest + React Testing Library + jsdom (the shell's first JS test infra). Covers
the gen-UI registry (all 5 tools render + graceful fallback + the locked flat-spread
datapoint prop convention), the 3 input widgets (collect + return a result; FlagEditor
reads ontology via GET + persists a draft via PUT), the `bff.js → ReportTab` binding,
the wired artifact tabs (Judge council / Config / Corpus over real BFF data),
and the Shell host mounting the input tool-parts. 30 tests.

## What's here

- **Pixel-faithful port** of the design's shell: floating window, 3 resizable panes,
  the Domain→Judge→Oracle→KB→Run→Review journey stepper, three inline cards
  (config / verdict / calibration), and the right artifact pane (Report · Judge council ·
  Config · Corpus — all over real BFF data) with fullscreen + a light/dark theme toggle.
- **Generative-UI layer** — a `tool-<name>` → React component registry
  (`src/genui/`, AI-SDK message-parts shape): input widgets (flag/severity editor,
  contract builder, KB picker) + datapoint cards (verdict, calibration). `renderTool(part)`
  resolves the component on `state === "output-available"`; unknown tools degrade gracefully.
- **Real brand** — `src/brand.jsx` recreates the Lithrim logo (the two-vertical-bars
  mark + LITHRIM wordmark) from the marketing site as inline SVG (theme-able); the
  raster `public/lithrim-logo.png` + `public/icon.svg` (favicon) come from
  `v0-lithrim-landing-page`. The conversation's assistant avatar is the Lithrim mark.
- **Design system** — two layers, one token source. `src/styles.css` / `src/journey.css`
  are the prototype's bespoke chrome CSS, kept verbatim (coral `#E85C3D`, navy `#1A2845`,
  Geist + Geist Mono, 10px radius). `src/theme.css` adds the **Tailwind v4 + shadcn**
  foundation via an `@theme inline` bridge over those same `:root` tokens, so the net-new
  gen-UI components (`src/components/ui/`, `src/genui/`) stay brand-consistent. Adopted
  **incrementally** — the chrome CSS is not rewritten into utilities.

## Structure

| File | Role |
|---|---|
| `src/main.jsx` | entry — mounts `App` |
| `src/app.jsx` | shell composition: titlebar, resizable panes, status bar, theme |
| `src/panes.jsx` | left rail (brand + threads + journey stepper) + center conversation |
| `src/cards.jsx` | inline cards: config widget / verdict / calibration chart |
| `src/artifact.jsx` | right pane: Report / Judge council / Config / Corpus tabs — all real BFF data + fullscreen |
| `src/bff.js` | the React↔Python bridge client (run-eval / corpus / get+put ontology) |
| `src/brand.jsx` | the real Lithrim logo (mark + wordmark) |
| `src/icons.jsx` · `src/data.jsx` | line-icon set · representative content — clinical/Scribe demo (rail threads / journey stepper) |
| `src/theme.css` | Tailwind v4 + `@theme` token bridge over `styles.css` |
| `src/components/ui/` | shadcn/ui copy-ins (button/input/label/card/separator/switch/slider/select/dialog) |
| `src/components/ModeSwitch.jsx` | the Shell↔Journey segmented control (in the titlebar) |
| `src/genui/` | gen-UI registry (`registry.js`) + 5 tool components + tests |
| `src/lib/utils.js` | the shadcn `cn()` helper |

## Status & next

- **Done:** the shell skeleton + the conversational **journey layer** —
  the 4-act activation arc (`src/journey/`, ESM port of `jp1–jp4`) with a top-level
  Shell↔Journey switch (`src/root.jsx`, default Journey) sharing the window theme.
- **BFF wire-up:** the FastAPI BFF + React↔Python bridge + one real `run_eval`
  eval-report vertical (the Report tab renders live harness output; see above).
- **Generative-UI layer:** the generative-UI `tool-<name>` registry + input widgets +
  datapoint cards; the **Tailwind v4 / `@theme` / shadcn foundation**; the mode-switch
  moved into the titlebar chrome; the demo domain reconciled to clinical/Scribe;
  and the shell's first JS test infra (Vitest + RTL) incl. the `bff.js → ReportTab`
  binding test.
- **Artifact-pane wiring:** the artifact pane is **wired** — JudgeTab renders the realized
  per-case council votes + ConfigTab the live ontology (`GET /v1/ontology`); a 4th
  **Corpus** tab renders the correction flywheel (`GET /v1/corpus`); the deferred
  **`PUT /v1/ontology`** write surface landed (clobber-safe working copy + validated),
  making the FlagEditor read-write; the Shell host input tool-part mounting landed
  (mount + thread `onResult` into config-plane state) + the datapoint prop convention
  locked to flat-spread. *Edits persist as a draft working copy — they do not yet feed
  an eval run (run_eval reads the committed seed); wiring drafts into grading is a
  follow-up.*
- **Next:** Tauri desktop installers + the deferred Tauri sidecar + VPC packaging +
  offline-license + the Playwright/E2E layer for Radix popover/drag interactions.
  Journey-act (`jp1–jp4`) tool-part mounting is also still open.

### Journey layer (`src/journey/`)

| File | Role |
|---|---|
| `journeyData.js` | the 4-act content (ACTS, PILLARS, AGENT_TYPES, PACK, EXCHANGE, SCENARIOS, ALIGN, JUTE, SDK_LINES, PRO_FEATURES) |
| `chrome.jsx` | journey rail / top bar / status bar / phase footer + the shared `AgentMsg` |
| `jp1.jsx … jp4.jsx` | the four acts (center conversation + right-pane artifact); jp2 verify-reveal + jp3 calibration are the hero screens |
| `JourneyApp.jsx` | composition: phase state machine (1–4), `runVerify`/`runCalib` hero timers, ←/→ nav, resizable panes |
- Fonts use the system font stack (the `--sans`/`--mono` tokens carry the
  fallbacks); no external font CDN is fetched.
- Stack note: the design's bespoke chrome CSS is kept verbatim for fidelity; the
  Tailwind v4 + shadcn foundation layers in over the same token source for the
  net-new components, without rewriting the chrome.
