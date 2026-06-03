# Critique / verify-and-close — `bench-salvage` WS-7a (journey Phase-2 Verify → live BFF)

**Date:** 2026-06-04
**Mode:** **verify-and-close, inline** (monitor). The BUILD was not produced by a driver-bounded executor cycle — it landed as part of the **parallel-session journey rework** (`26e479f`, committed during the calibration-vertical landing). This pass audits that landed work against the WS-7a driver, fills the missing D4 test, and records the deviations. **Inline** is proportionate (low-risk UI wiring over a proven grade chain); per the driver's own note the **`:5180` visual smoke is the load-bearing gate regardless** and is **OWED** (user-run, no-autostart).
**Driver:** `bench-salvage-phaseWS-7a-journey-verify-live-driver`
**Build provenance:** `26e479f` (journey rework) · **D4 test:** `0b1d2d0` (this close)

## Verdict: CLOSED-WITH-CAVEATS

The pitch is real: Journey Phase-2 "Verify" drives the live grade and renders the real composite. A1/A2/A4 met + tested; A5 build+test met; **A3 deviated** (the journey added BFF surface — justified but outside the locked §10 contract) and the **`:5180` smoke is owed**.

## Acceptance audit (against driver §5)

- **A1 (the pitch is real) — PASS.** `JourneyApp.runVerify` (`:88`) → `POST /v1/run-eval` and renders the real composite — `Center2` reads `gradeResult.council.votes` (`jp2:262`) + `gradeResult.result.verdict` (`jp2:264`); `GET /v1/case` (`:74`) fetches the real graded note. Tested (`JourneyApp.test.jsx` A1/A2 — the real `REJECT` verdict renders from a mocked record, not `journeyData`).
- **A2 ($0 default, live on demand) — PASS.** The body hardcodes `live:false` (`:97`) = `$0` replay default; "Verify" → `runVerify()` (`in_process:false`), "Run live" → `runVerify({live:true})` → `in_process:true` (`:89`). **Note:** the journey's "live" toggle exercises **`grade_inprocess`**, never `grade_live(:8002)` (`live` is always false) — a reasonable choice (the in-process v2 council), narrower than the driver's "exercises `grade_live`/`grade_inprocess`". Tested (both bodies asserted).
- **A3 (leverage held — the governing gate) — ⚠️ DEVIATED (accepted, recorded).** The driver required **zero new BFF endpoint / zero new Python**. The journey rework instead **extended the BFF**: a new `GET /v1/case` endpoint (`apps/bff/app.py:186`), a `council` view shaped onto `/v1/run-eval` (`_council_view`, the `votes` the pillars read), and an `in_process` request field. **Justified** — the verify act genuinely needs the real case (to display the same note it grades) + a per-judge votes view + the in-process toggle; all additive, confined to `apps/bff/` (zero `../lithrim-backend` edit, no new `:8002` endpoint). **But** the driver said *halt-and-surface* if a field is missing; the parallel session (outside devloop) didn't, and it touched the **§10-locked v1 BFF surface** without ratification → **S-BS-51**.
- **A4 (graceful degradation) — PASS.** BFF unreachable → `bffDown` (`:101`) → fixture fallback (`FALLBACK_VOTES` + the "bundled example · BFF offline" copy, `jp2:283`), no crash. Tested (A4: rejected fetch → fallback copy renders, no throw).
- **A5 (test + build + smoke) — PARTIAL.** **D4 test ADDED** this close (`JourneyApp.test.jsx`, +3; the journey's *first* test — it surfaced two jsdom gaps the rework never hit: `matchMedia` + `Element.scrollTo`, both polyfilled in-test). **Full shell suite 33/33; `vite build` clean** (the `bff.js` dynamic/static-import warning is pre-existing, unrelated). **`:5180` visual-parity smoke = OWED** (user-run; light/dark; Phase-2 reveal vs the scripted look). This close is **conditional on that smoke** — same posture as the WS-5c owed smoke.

## The 4 questions (brief)

- **Q1 surface fidelity — 0 BLOCKING.** `runVerify` / `gradeResult` / `bffDown` match the driver's D1/D2 intent. Deviation: D1 said "call `bff.js` `runEval({live})`"; the landed code uses its **own** `fetch(BFF_URL/...)` (hardcoded `http://localhost:8787`) instead of the `bff.js` client + its `VITE_BFF_URL` BASE indirection → **S-BS-50** (packaging-breaking).
- **Q2 behavioral fidelity — 0 BLOCKING.** 3 behaviors traced spec→test→impl: real-composite render (A1, test), $0-replay default (A2, test), bffDown fallback (A4, test). All hold.
- **Q3 out-of-scope intrusion — recorded, not blocking.** The journey rework also reworked **Acts 1/3/4** (driver was Phase-2-only). That's the parallel session's broader semantic-moat journey, not WS-7a's scope — committed as `26e479f` (the journey feat), not attributed to WS-7a. Acts 3/4 remain scripted props (their live wiring = WS-7b/7c).
- **Q4 spec-ambiguity — surfaced.** The driver assumed "zero BFF / pure UI wiring"; reality needed a modest BFF extension (case fetch + votes view). The ambiguity ("what does the verify act need that the record doesn't carry") resolved toward *extend the BFF* — defensible, but should have been a plan-review surface (S-BS-51 records the §10-contract angle).

## Seams opened

- **S-BS-50** (low→medium, packaging) — the journey **hardcodes `BFF_URL = "http://localhost:8787"`** and fetches directly, bypassing `bff.js`'s `runEval` + `BASE = VITE_BFF_URL ?? ""` indirection. Works in dev (both hit `:8787`); **breaks a packaged Tauri/VPC build** (no env-driven base). Fix = route the journey's case/grade fetches through `bff.js` (or at least the `VITE_BFF_URL` indirection). → WS-5e packaging / a small journey-bff.js cleanup. Fix loc: `apps/shell/src/journey/JourneyApp.jsx:18,74,95`.
- **S-BS-51** (medium, contract) — the journey **extended the §10-locked v1 BFF surface** (WS-5-BFF ratified) outside ratification: `GET /v1/case` + a `council` view on `/v1/run-eval` + an `in_process` field. Additive + non-regressing (`bff.test.jsx` composite path still 33/33 green), but the locked surface grew without the §10 process. Fix = reconcile/ratify the additions into `SPEC_PRODUCT_SHELL.md §10` (and `bff.js` should expose `/v1/case` + `in_process` so clients don't hand-roll fetches — pairs with S-BS-50). Fix loc: `apps/bff/app.py:186` + `docs/specs/SPEC_PRODUCT_SHELL.md §10`.

## Disposition

WS-7a's deliverable — the pitch's first live act — **is real and tested**; the close is **CLOSED-WITH-CAVEATS** pending the one **OWED `:5180` visual smoke** (user-run). The two seams (S-BS-50 packaging hardcode, S-BS-51 §10 surface drift) are the price of the work landing outside the cycle; both are tracked, neither blocks the demo. The broader journey rework (Acts 1/3/4) is the parallel semantic-moat work, not WS-7a — its live wiring is **WS-7b** (Align: floor + KB) / **WS-7c**.
