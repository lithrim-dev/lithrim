# HANDOFF — `bench-salvage` phase `WS-5c` → phase `WS-5d` kickoff

> **Written by the monitor on cycle close.** Load-bearing context for
> the next monitor session that takes over after a compaction or
> after-hours break. Committed alongside the close-out commit.
>
> **Path:** `.devloop/sessions/HANDOFF_bench-salvage_phaseWS-5d_kickoff_2026-06-01.md`

---

## What just landed

- **Closed phase:** `WS-5c` — generative-UI components + Tailwind v4/`@theme`/shadcn foundation + mode-switch integration + first React↔BFF test + S-BS-17 reconcile (commits `efefaa8..e9f863b`, 10 code commits: 8 planned D0–D7 + `0c13d3f` post-close chrome-align + `e9f863b` stray-`}` fix)
- **Critique verdict:** `NON-BLOCKING FINDINGS` (fresh-critic; 1 BLOCKING→RESOLVED + 1 NB + 2 OQ) — `.devloop/sessions/critique-bench-salvage-phaseWS-5c-2026-06-01.md`
- **Audit verdict:** `CLEAN` (7/7; monitor re-verified through `e9f863b` — 38 files all `apps/shell/`, build clean, 19/19 tests, 0 new Python deps)
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseWS-5c-2026-06-01.json`

## What's next

- **Next phase:** `WS-5d` — artifacts pane wired (judge-council + config/ontology tabs → BFF) + corpus/flywheel view + the deferred `PUT /v1/ontology` write surface
- **Driver bundle:** `bench-salvage-phaseWS-5d-…` (does NOT exist yet — author it)
- **Driver path:** run `/devloop-expand-driver bench-salvage WS-5d` (no WS-5d task-pack entry exists yet either — same reconcile pattern as WS-5c: author the pack task + stub + driver. SPEC §8:131 is the authoritative scope source.)
- **Blocked by:** none (independent of WS-2's paused backend; composes over the existing BFF + `GET /v1/corpus`). The `PUT /v1/ontology` half does touch the BFF API surface (`apps/bff/app.py`) → HARD-GATE, fresh-critic.

## Open seams for `bench-salvage`

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-BS-17 | Shell demo-domain split (customer-support vs clinical/Scribe) | low | `apps/shell/src/data.jsx` | WS-5 | **RESOLVED/CLOSED (WS-5c)** — converged to clinical/Scribe; shell/journey/harness agree |
| S-BS-18 | React↔BFF binding manual-smoke-only | low | `apps/shell/src/{bff.test.jsx,app.test.jsx}` | WS-5-BFF | **RESOLVED/CLOSED (WS-5c)** — Vitest+RTL infra + `bff.js`→`ReportTab` binding test |
| S-BS-19 | scripted journey doesn't yet emit input `tool-parts` mounting FlagEditor/ContractBuilder/KbPicker; + datapoint `part.output` prop convention inconsistent (VerdictCard `{data}` vs CalibrationChart spread) | low | `apps/shell/src/journey/*` + `panes.jsx` | WS-5c | **open → WS-5d** (the conversational-host job + the prop-convention lock) |
| S-BS-20 | Radix Select/Slider popover/drag not E2E-tested (jsdom has no layout) | low | `apps/shell/src/genui/*.test.jsx` | WS-5c | **open → WS-5e** (Playwright/E2E) |
| S-BS-13 | floor-apply offline replay missing (`run_eval` `http_client=None`) | medium | `scripts/run_eval.py run()` | WS-3a | open → WS-4b (gate; inert — clinical_v1 floor-less) |
| S-BS-16 | floor-injected flag bypasses gradeable/owner + severity validation | medium | `grounding.py:355-365` / ontology-load | WS-3a | open → WS-4b GATE (core invariant; inert today) |
| S-BS-12 | one-directional snapshot↔runtime lint | medium | `scripts/seed_ontology.py:152-160` | WS-2 | open → WS-2 backend driver |
| S-BS-11 | `build_prompt` hardcoded clinical prose (full templating = large rewrite) | medium | `../lithrim-backend/.../compliance_council.py build_prompt:517` | WS-2 | open (deferred) |

*(S-BS-1..S-BS-10 resolved/superseded; S-BS-5 open → WS-3b; S-BS-2 open → WS-3b; S-BS-14/15 low cosmetic → WS-3b. Full table in `STREAM_bench-salvage.md`.)*

## Load-bearing context the next monitor MUST know

1. **WS-5c locked two contracts — treat them as frozen for WS-5d/e.** The §5b generative-UI **`tool-<name>` → component registry** (`genui/registry.js`: `KNOWN_TOOLS` 5 tools + `registerTool`/`getTool`/`renderTool(part)` on `state==='output-available'`, AI-SDK message-`parts` shape) and the **Tailwind v4/`@theme` token bridge** (`theme.css` `@theme inline` over the single `styles.css` `:root`/`[data-theme="dark"]` source; `@custom-variant dark` maps to `[data-theme="dark"]`, NOT `.dark`). Both consume one token source — keep it that way. Incremental adoption is a SPEC §4 invariant: **`styles.css`/`journey.css` were NOT rewritten** and must not be in WS-5d. The two ported datapoint cards stay on `.icard` CSS deliberately (fresh-critic Ambiguity-1, accepted).

2. **The fresh-critic caught a *visible* defect that the mechanical audit + build + 18 tests all missed** — a stray `}` literal rendered in the Shell titlebar (introduced by the post-close chrome-align fix `0c13d3f`, fixed in `e9f863b` + a new `app.test.jsx` Shell-`TopBar` guard). Lesson with teeth: **build-green + unit-tests-green is necessary but NOT sufficient for shell phases** — no test rendered the Shell `TopBar`. The **60-second `:5180` visual-parity smoke (light/dark × Shell/Journey) is OWED on WS-5c and is now standing practice for every shell phase.** It's the one human-eyeball gate; under the no-autostart rule the USER runs it (`cd apps/shell && npm run dev` → `:5180`). The WS-5c close carries this as a documented caveat, de-risked by the new regression guard but not eliminated.

3. **WS-5d is the natural home for three carried items** the user/spec-author should fold into its driver: (a) **S-BS-19** — wire the scripted journey to emit input `tool-parts` (FlagEditor/ContractBuilder/KbPicker currently render-on-demand + tested but are mounted by no host) and **lock the datapoint `part.output` prop convention** (Ambiguity-2); (b) the deferred **`PUT /v1/ontology`** write surface (SPEC §10:144 — WS-5c's FlagEditor reads-only against `GET /v1/ontology`; the editor's *persistence* was explicitly deferred so an unexercised PUT couldn't clobber the committed `clinical_v1.json`); (c) wiring `artifact.jsx` JudgeTab/ConfigTab (still mock `JUDGES`/`CONFIG_YAML`) to the BFF. Note WS-5d touches `apps/bff/app.py` (the PUT) → it's a contract-touching HARD-GATE → **fresh-critic close** (the same call that paid off this cycle).

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (especially the phase table and open seams).
3. Read this handoff doc.
4. Read the most recent session log: `.devloop/sessions/session-bench-salvage-phaseWS-5c-2026-06-01.json`.
5. Run `git log --oneline -12` in `lithrim-bench` to see the commit timeline.
6. Wait for user input. Don't autonomously start the next cycle.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseWS-5c-2026-06-01.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseWS-5c-2026-06-01.md`
- Driver: `.devloop/prompts/bench-salvage_phaseWS-5c_generative-ui-foundation_driver.md`
- Roadmap/spec: `docs/specs/SPEC_PRODUCT_SHELL.md` (§8:131 WS-5d row; §10:144 PUT-ontology) + `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md`
