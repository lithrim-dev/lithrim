# HANDOFF — `bench-salvage` → WS-5b (product shell) · monitor resume brief

> **Written by the monitor on session close, 2026-06-01.** This session pivoted the
> stream from the backend eval-harness into the **product** (a React/Tauri shell) and
> implemented the WS-5 shell from a Claude Design handoff. Read this first on resume.
>
> **Authority docs:** `docs/specs/SPEC_PRODUCT_SHELL.md` · `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` · `docs/design/JOURNEY_brief.md` · monitor memory `product-direction-shell-strangler-fig-2026-06`.

---

## What just landed (this session)

**Product direction set + specced** (commits `a925b09`, `e49d93a`, `b277122`):
- `SPEC_PRODUCT_SHELL.md` — Claude-desktop-class 3-pane React/Tauri/Tailwind conversational shell over the WS-0→WS-4a harness; BFF = the Python-Layer API; phased WS-5→WS-5e.
- `SPEC_PRODUCT_SERVICE_TOPOLOGY.md` — **strangler-fig** (retire Mongo; grow the M1/WS-1/WS-3a nucleus into the Python Layer; SQLite↔PG; ETLP as a JVM sidecar; **sequencing B**).
- `docs/design/JOURNEY_brief.md` — the 4-phase activation journey + the Claude Design prompt + brand tokens.
- `.devloop` re-scoped: WS-5 = the shell program (WS-5..WS-5e); thin stdlib WS-5 driver **SUPERSEDED**; WS-6 reframed = the Python-Layer consolidation track.

**bench-salvage closes:** WS-3a (`59a3cba..d6fe96f` + close-out `1788ed5`; verification core + structural floor) · WS-4a (`894cc4d..da05779` + close-out `b5d6e89`; flywheel: corpus + eval-pack + calibration).

**paper-1-copilot:** N5-PILOT monitor-closed (`860d472`) · S-P1-22 resolved (`5c1d3d1`; DSPy generator = §2 method, full disclosure).

**WS-5 shell BUILT** — `apps/shell/` — a Vite + React, pixel-faithful port of the Claude Design handoff (`api.anthropic.com/v1/design/h/pIAWkwsx2ASYYEZ-7lHzjQ`): floating window, 3 resizable panes, journey stepper, inline cards (config/verdict/calibration), artifact pane (report/judge-council/config + fullscreen), light/dark. **Real Lithrim logo** (`src/brand.jsx` — the two-bars mark + wordmark from the marketing site). `vite build` clean (33 modules); dev server verified on `:5180`.

## ⚠️ Uncommitted / live state (handoff hygiene)

- **`apps/shell/` is BUILT + build-verified but NOT committed** (18 source files; `node_modules`/`dist` gitignored; `package-lock.json` tracked). Held for the user's "go" pending the Tailwind decision below.
- The **Vite dev server is left running** on `:5180` (background, per user) — the shell is live there now. A fresh session won't inherit a prior session's background process, so if `:5180` is unreachable, `cd apps/shell && npm install && npm run dev`.
- `?? .claude/` is parked tooling (do not commit).

## Open decisions (resolve with the user first)

> **✅ RESOLVED 2026-06-01 (resuming monitor session).** (1) Commit `apps/shell/` **as-is**
> (Tailwind additive/incremental at WS-5b). (2) WS-5 HARD-GATE closed via **inline critique**
> (user-elected over fresh-critic) → **BLOCKING DRIFT** (mock data; BFF+vertical+Tauri absent)
> → resolved by **amending SPEC §8 to front-end-first** (WS-5 = skeleton; new WS-5-BFF phase
> for the bridge). Critique: `.devloop/sessions/critique-bench-salvage-phaseWS-5-2026-06-01.md`.
> (3) Logo placement accepted as-is. **Next = WS-5b journey port.** See `STREAM_bench-salvage.md`
> (WS-5 row + First move) for current truth; the decisions below are the original snapshot.

1. **Commit `apps/shell/` as-is, or set up Tailwind first?** User said "we may port to Tailwind." Monitor recommendation: **commit as-is (option A)** — it's verified + valuable; Tailwind is **additive** (the build is Tailwind-ready by construction: CSS variables in `src/styles.css` `:root`, same as the marketing site's `@theme` bridge). Do Tailwind+shadcn **incrementally at WS-5b** (new components), not as a rewrite. Option B = add Tailwind v4 + map `@theme`→existing tokens before the first commit (~15 min).
2. **WS-5 is HARD-GATE** — a fresh-critic close is nominally required. This session fast-tracked the build (the Claude Design handoff + `vite build` clean = the spec + verification). User decides whether to run a formal `/devloop-critique bench-salvage WS-5` or accept build-verified.
3. **Logo placement** — wordmark lockup in the rail header + the mark as the assistant avatar. Adjust if the user wants it elsewhere/bigger.

## What's next

- **WS-5b — port the 4-phase journey** (`jp1–jp4` + `journeyapp`/`journeyrail`/`journeydata` + `journey.css`) into `apps/shell/src/journey/` + a Shell↔Journey switch. Heroes = Phase 2 verify-badges + Phase 3 calibration before/after. (`journey.css` is already copied into `apps/shell/src/`.)
- **WS-5c/d/e** — generative-UI components · artifacts thickened · Tauri desktop + VPC packaging (+ Tailwind/shadcn incremental; self-hosted `@fontsource` for offline).
- **Python-Layer consolidation** (WS-6 reframed, parallel, strangler-fig) — port the validated **v2 council Mongo-free** + Mongo→SQLite/PG persistence swap. **GATE: audit `../lithrim-backend`** (v2-council Mongo-coupling + persistence surface) before porting.
- **paper-1-copilot** — S-P1-22 now unblocks the §2/§4/§6 drafting (P1-§2 full disclosure of the DSPy generator); plus P1-PACK-V2-WIDEN, the S-P1-21 policy-judge narrowing, the §5.4 draft.

## Load-bearing context the next monitor MUST know

1. **The shell is a faithful port, kept on the design's plain CSS by design.** `src/styles.css`/`journey.css` are the prototype's CSS copied verbatim (pixel-perfect, brand-exact). It is **Tailwind-ready, not Tailwind-blocked** — the `:root` tokens are the single source; Tailwind's `@theme` consumes them (exactly how `../v0-lithrim-landing-page/app/globals.css` works). So "port to Tailwind" = additive + incremental, never a teardown.
2. **The Claude Design handoff was extracted to `/tmp/lithrim_design/x/lithrim-bench/`** — the journey prototype files (`jp1–jp4.jsx`, `journeyapp.jsx`, `journeyrail.jsx`, `journeydata.jsx`) live in `…/project/` for the WS-5b port. If `/tmp` is gone, re-fetch the tar.gz from the design URL above (`curl -L <url> -o handoff.tar.gz`).
3. **Brand:** navy `#1A2845` + coral `#E85C3D` + Geist; tokens in `apps/shell/src/styles.css` `:root`; real logo in `src/brand.jsx` + `public/{lithrim-logo.png,icon.svg}`. Brand source = `../v0-lithrim-landing-page/app/globals.css`.
4. **Strangler-fig is the spine** (per the topology spec): the shell BFF targets the harness (composes over live `:8002`/`:3031`) now; the Mongo backend is a dev-dep being strangled, not a product component. **Port, don't rewrite** the v2 council.

## How to resume (monitor)

1. Read `.devloop/personas/MONITOR.md`.
2. Read **this handoff**, then `SPEC_PRODUCT_SHELL.md` + `SPEC_PRODUCT_SERVICE_TOPOLOGY.md` + `JOURNEY_brief.md`.
3. Read `.devloop/state/STREAM_bench-salvage.md` (WS-5 row + First move) + `STREAM_paper-1-copilot.md`.
4. `git status` (check whether `apps/shell/` got committed) + `git log --oneline -12`.
5. The shell may already be live at **http://localhost:5180** (left running from the prior session); if it's not reachable, `cd apps/shell && npm install && npm run dev`.
6. Resolve the open decisions with the user; then prepare the WS-5b driver. **Never autonomously start a cycle.**

## References
- Specs: `docs/specs/SPEC_PRODUCT_SHELL.md`, `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` · Journey: `docs/design/JOURNEY_brief.md` · Shell: `apps/shell/README.md`
- Memory: `product-direction-shell-strangler-fig-2026-06`, `walking-skeleton-architecture`, `gtm-launch-and-journey-thesis`
- Design handoff: `api.anthropic.com/v1/design/h/pIAWkwsx2ASYYEZ-7lHzjQ` (extracted at `/tmp/lithrim_design/`)
- Prior cycle close: WS-4a critique `.devloop/sessions/critique-bench-salvage-phaseWS-4a-2026-06-01.md`
