# HANDOFF — `bench-salvage` phase `WS-5d` → phase `WS-5e` kickoff

> **Written by the monitor on cycle close.** Load-bearing context for
> the next monitor session that takes over after a compaction or
> after-hours break. Committed alongside the close-out commit.
>
> **Path:** `.devloop/sessions/HANDOFF_bench-salvage_phaseWS-5e_kickoff_2026-06-01.md`

---

## What just landed

- **Closed phase:** `WS-5d` — artifacts pane wired (JudgeTab + ConfigTab off mock → BFF) + corpus/flywheel 4th tab + the deferred **`PUT /v1/ontology`** write + **S-BS-19** (input tool-parts mounted in the Shell host + datapoint prop-convention locked). Commits `38e4071..b065f14` (7 atomic D0–D6) + `5518ffb` (fresh-critic copy-fix) + close-out.
- **Audit verdict:** `CLEAN` (7/7; monitor re-verified **both** halves — `pytest` 181/3, BFF 10/10, Vitest 30/30; diff confined to `apps/shell/`+`apps/bff/`+`tests/test_ws5_bff.py`; the committed `clinical_v1.json` is byte-unchanged and not in the cycle diff).
- **Critique verdict:** `NON-BLOCKING FINDINGS` (fresh-critic, HARD GATE; 0 BLOCKING / 1 NB→fixed `5518ffb` / 1 NB / 2 OQ) — `.devloop/sessions/critique-bench-salvage-phaseWS-5d-2026-06-01.md`
- **A7 smoke:** `:5180` visual-parity **PASS (user-attested 2026-06-01)** — light/dark × Shell/Journey + the 4 wired tabs.
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseWS-5d-2026-06-01.json`

## What's next

- **Lead phase:** `WS-5e` — the **last shell phase**: Tauri installers (desktop, macOS/Windows/Linux) + the **deferred Tauri sidecar** (PyInstaller-bundle the `apps/bff/` FastAPI BFF as a `tauri.conf.json` `externalBin`, from the WS-5-BFF plan-review #4 defer) + the **VPC-hosted** packaging (same BFF containerized + static React, no code fork) + **offline-license** (SPEC §7/§10 — the named GTM execution risk) + **S-BS-20** (Playwright/E2E for Radix Select popover / Slider drag — jsdom can't).
- **Driver bundle:** `bench-salvage-phaseWS-5e-…` (does NOT exist yet — author it). No task-pack entry yet either → **same reconcile pattern as WS-5d/WS-5c** (author the pack task + stub + driver in one pass). Authoritative scope: `SPEC_PRODUCT_SHELL.md` §8:132 (WS-5e row) + §7 (packaging/GTM) + §5 (sidecar packaging detail at :80).
- **Run:** `/devloop-expand-driver bench-salvage WS-5e`.
- **Blocked by:** none. WS-5e is packaging over the now-complete React→Python stack.

## Optional small follow-up (monitor's call)

- **WS-5d-follow (S-BS-26)** — two honest-close riders, both inert for the demo, either folded into WS-5e or a tiny cycle: (a) wire the **journey acts jp1–jp4** to emit input `tool-parts` (S-BS-19 is closed for the Shell `CenterPane` host only; the 4-act journey — the real activation surface per SPEC §3 — still emits none); (b) decide whether a **`PUT /v1/ontology` draft should feed an eval run** (today the BFF working copy is decoupled from `run_eval.py:118`, which reads the committed seed — by design). Both are fresh-critic OPEN-QUESTIONs for the spec author.

## Open seams for `bench-salvage` (shell-relevant)

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-26 | (a) journey acts mount no input tool-parts (S-BS-19 closed for Shell host only); (b) PUT draft does not feed an eval run (decoupled from `run_eval.py:118`) | low | **open → WS-5e / WS-5d-follow** (WS-5d fresh-critic; both inert for the demo) |
| S-BS-20 | Radix Select/Slider popover/drag not E2E-tested (jsdom no layout) | low | **open → WS-5e** (Playwright/E2E) |
| S-BS-19 | input tool-parts mounted + datapoint prop-convention locked | low | **CLOSED for the Shell host (WS-5d, `20474ed`)** — journey-act half → S-BS-26 |
| S-BS-17 / S-BS-18 | demo-domain converged / React↔BFF binding test | low | **CLOSED (WS-5c)** |

*(Backend/harness seams S-BS-5/11/12/13/14/15/16 + the WS-6a S-BS-21..25 are tracked in `STREAM_bench-salvage.md`; not shell-blocking.)*

## Load-bearing context the next monitor MUST know

1. **The v1 BFF API now has a WRITE.** WS-5d landed `PUT /v1/ontology` on the locked v1 surface (SPEC §10:144 reconciled — the read surface was ratified at WS-5-BFF, the write at WS-5d). It is **clobber-safe by construction**: the handler writes `out/bff/ontology/<agent>.json` (gitignored) and **never** touches the committed `data/ontology/clinical_v1.json`; `GET /v1/ontology` prefers the working copy so a PUT round-trips in the UI. Validation = `ontology.from_dict` round-trip + the `seed_ontology.gradeable_flags_outside_snapshot` S-BS-10/12 lint → `422`. This is the contract WS-5e packages — treat `out/bff/` as runtime state the installer must provision a writable home for.

2. **The fresh-critic earned its keep a SECOND time (WS-5c was the first).** Build-green + 30 unit tests missed a *visible* defect: the FlagEditor's subtitle/docstring still said "read-only — no PUT this phase" after it gained a Persist-draft PUT button (coherent-but-wrong copy, not garbage). Fixed in `5518ffb` before the A7 smoke. **The `:5180` visual-parity smoke is the one gate build+unit-tests cannot cover — keep it load-bearing for every shell phase, WS-5e included.** Under no-autostart the USER runs it (`cd apps/bff && uvicorn app:app --app-dir . --port 8787` ‖ `cd apps/shell && npm run dev`).

3. **S-BS-26 is the gap between "wired" and "the journey is the product."** The Shell `CenterPane` mounts the 3 input tool-parts and threads `onResult` into config-plane state — but the 4-act *journey* (jp1–jp4), which SPEC §2.1/§3 calls the activation spine, still runs on static `journeyData` and emits no input tool-parts. WS-5d honestly closed S-BS-19 *for the Shell host only* and did NOT over-claim. If the journey is the demo surface a design-partner sees, fold S-BS-26(a) into WS-5e (or a small follow) before that demo.

4. **Two ratified shape decisions to hold frozen for WS-5e:** the datapoint `part.output` prop convention is **flat-spread** (component destructures `part.output` fields directly — VerdictCard was conformed, `{data}` wrapper dropped; documented in `genui/registry.js`); and `putOntology(ontology, agent)` ships arg-order-flipped vs the driver's stated signature (internally consistent, NB — don't "fix" it into a breaking change without checking call sites).

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + open seams + first-move §1).
3. Read this handoff doc.
4. Read the most recent session log: `.devloop/sessions/session-bench-salvage-phaseWS-5d-2026-06-01.json`.
5. Run `git log --oneline -14` in `lithrim-bench` for the commit timeline.
6. Wait for user input. Don't autonomously start the next cycle.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseWS-5d-2026-06-01.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseWS-5d-2026-06-01.md`
- Driver: `.devloop/prompts/bench-salvage_phaseWS-5d_artifacts-wired_driver.md`
- Roadmap/spec: `docs/specs/SPEC_PRODUCT_SHELL.md` (§8:132 WS-5e row; §7 packaging/GTM; §5:80 sidecar packaging) + `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (one BFF, two packagings)
