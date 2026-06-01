# Lithrim Product Shell (`apps/shell`)

The 3-pane conversational eval workspace — the WS-5 shell skeleton, ported from the
Claude Design handoff (`api.anthropic.com/v1/design/h/pIAWkwsx2ASYYEZ-7lHzjQ`) into a
real Vite + React app, pixel-faithful to the prototype.

## Run

```bash
cd apps/shell
npm install
npm run dev          # http://localhost:5180
```

## What's here

- **Pixel-faithful port** of the design's shell: floating window, 3 resizable panes,
  the Domain→Judge→Oracle→KB→Run→Review journey stepper, three inline cards
  (config / verdict / calibration), and the right artifact pane (Report · Judge council ·
  Config) with fullscreen + a light/dark theme toggle.
- **Real brand** — `src/brand.jsx` recreates the Lithrim logo (the two-vertical-bars
  mark + LITHRIM wordmark) from the marketing site as inline SVG (theme-able); the
  raster `public/lithrim-logo.png` + `public/icon.svg` (favicon) come from
  `v0-lithrim-landing-page`. The conversation's assistant avatar is the Lithrim mark.
- **Design system** — `src/styles.css` / `src/journey.css` are the prototype's CSS,
  copied verbatim (coral `#E85C3D`, navy `#1A2845`, Geist + Geist Mono, 10px radius).

## Structure

| File | Role |
|---|---|
| `src/main.jsx` | entry — mounts `App` |
| `src/app.jsx` | shell composition: titlebar, resizable panes, status bar, theme |
| `src/panes.jsx` | left rail (brand + threads + journey stepper) + center conversation |
| `src/cards.jsx` | inline cards: config widget / verdict / calibration chart |
| `src/artifact.jsx` | right pane: Report / Judge council / Config tabs + fullscreen |
| `src/brand.jsx` | the real Lithrim logo (mark + wordmark) |
| `src/icons.jsx` · `src/data.jsx` | line-icon set · representative content |

## Status & next

- **Done:** the shell (this).
- **Next (WS-5b–e per `docs/specs/SPEC_PRODUCT_SHELL.md`):** port the 4-phase **journey**
  (`jp1–jp4` from the handoff) into `src/journey/`; wire the conversational layer +
  generative-UI components to the FastAPI BFF; Tauri desktop wrapper + VPC packaging.
- Fonts load from Google Fonts (dev). WS-5e swaps to self-hosted `@fontsource` for
  offline/desktop.
- Stack note: kept the design's CSS system verbatim for fidelity; Tailwind/shadcn
  (per the spec) can layer in later without visual change.
