# Spec-Adherence Critique — `bench-salvage` phase `WS-5b`

> Inline-mode critique (monitor self-audit). Committed alongside close-out artifacts.
> **HARD-GATE override (recorded):** `index.json` → the WS-5b bundle is `hardness: "HARD-GATE"`;
> the strict path is a fresh critic. **User delegated inline** ("inline or fresh-critic as you
> elected for WS-5" → WS-5 was inline; same UI-port situation). Independent-cognition property
> forfeited; recorded in the self-check. A fresh-critic pass remains available on request.

## Metadata

- **Stream:** `bench-salvage` · **Phase:** `WS-5b` (conversational journey layer — ESM port of the 4-act activation journey)
- **Driver bundle:** `bench-salvage-phaseWS-5b-journey-driver` (`.devloop/prompts/bench-salvage_phaseWS-5b_journey_driver.md`)
- **Commits audited:** `460b677..00c68b9` (base `57743ee`)
- **Spec(s) read against:** `docs/specs/SPEC_PRODUCT_SHELL.md` §2 (3-pane, ll.20–26), §2.1 (4-phase journey, ll.28–37), §5b (gen-UI protocol, ll.86–87), §5c (scripted-default engine, ll.90–91), §8 (amended FE-first — WS-5b row + Tailwind-at-WS-5c); `docs/design/JOURNEY_brief.md` (ll.12–22, 34); the prototype `/tmp/lithrim_design/x/lithrim-bench/project/{journeyapp,journeyrail,journeydata,jp1–jp4}.jsx` (port source of record).
- **Critique mode:** `inline` (HARD-GATE override, user-delegated) · **Date:** 2026-06-01 · **Reviewer:** monitor

---

## Verdict

**NON-BLOCKING FINDINGS**

A **faithful, in-scope ESM port** of the 4-act activation journey. Every spec-load-bearing surface is realized: SPEC §2.1's four phases (First contact / Reveal / Calibration / Own it) map 1:1 to `jp1–jp4`; the two **hero beats** — Phase 2's staggered four-pillar verify reveal (`JourneyApp.jsx:54-59` + `jp2.jsx:105-134`) and Phase 3's before→after calibration (`JourneyApp.jsx:61-64` + `jp3` compare) — are preserved verbatim; the 3-pane shape and the Shell↔Journey switch (`root.jsx`) work as specced. The globals→ESM conversion (the cycle's central task) is clean — `window.Center{n}` → `CENTERS` import maps, React globals → `react` imports, `createRoot` dropped. No blocking drift. The findings are: one **NON-BLOCKING** cosmetic (the mode switch is a fixed-position overlay near the titlebar's centered command pill); and two **OPEN-QUESTIONs** that are already tracked decisions (S-BS-17 domain split; behavioral verification is manual-only by the §8-amended design). Cycle closes.

---

## 1. Surface fidelity

> Contract = SPEC §2/§2.1 + JOURNEY_brief + the driver §2 deliverable surface. (UI surface, not a harness API.)

| Spec assertion | Implementation | Match? | Severity |
|---|---|---|---|
| §2.1 ll.31–36: 4 phases — First contact · Reveal · Calibration · Own it | `journeyData.js` `ACTS` (First contact/The reveal/Calibration/Own it) + `jp1–jp4.jsx` `Center{n}`/`Artifact{n}` | ✓ 1:1 | — |
| §2.1 l.37: "Phase 2's verify moment + Phase 3's calibration loop are the **hero screens**" | `jp2.jsx:105-134` (staggered pillar reveal + PASS 8.6 banner) + `jp3` (before/after compare); driven by `JourneyApp.jsx:54-64` timers | ✓ both heroes | — |
| §2 ll.20–24: 3 panes (journey rail · conversation · artifacts) | `JourneyApp.jsx:84-128` — `LeftRailJ` (4-act stepper) / center `AgentMsg` conversation / `artifact` pane w/ fullscreen | ✓ | — |
| §2.1 l.34: Phase 1 "pick agent (Scribe) + BYOK config" | `jp1.jsx` agent picker + BYOK key field + provider select; `AGENT_TYPES` = Clinical Scribe + 3 | ✓ | — |
| §2.1 l.35: Phase 3 "plain English → Jute structural conditionals" | `jp3` rule textarea → `JuteBlock` (`MED_DOSAGE_OMITTED`) | ✓ | — |
| §5c ll.90–91: **scripted-default**, zero-LLM journey | the journey is a deterministic phase state machine over `journeyData.js` — no LLM, no network (grep-confirmed) | ✓ | — |
| Driver §2 #8: Shell↔Journey switch | `root.jsx:51-64` (`mode` default journey; renders `<JourneyApp/>`/`<App/>`) | ✓ | — |
| JOURNEY_brief l.14/34: first domain = **clinical/Scribe** | `journeyData.js` (acme-health, Healthcare Scribe Pack, hypertension/lisinopril) | ✓ (shell stays support — S-BS-17) | OPEN-QUESTION |
| §5b ll.86–87: generative-UI `tool-<name>`↔component protocol | not implemented | — (deferred to **WS-5c** by §8) | — |

**Findings:**
- No surface drift. All spec-load-bearing journey surfaces (4 phases, both heroes, 3-pane, switch, scripted-default, Scribe domain) are realized.
- `[OPEN-QUESTION]` Demo-domain split (S-BS-17): journey is clinical, shell skeleton is customer-support. A tracked decision (plan-review #2), not drift.

---

## 2. Behavioral fidelity

> **Structural caveat (by design):** WS-5b ships **zero tests** — the §8 amendment explicitly moves the first test bar to **WS-5-BFF**. So spec→**test**→impl cannot close via a test; chains close via impl + the user's visual smoke at `:5180`. Recorded, not a drift against this cycle's (amended) contract.

### Behavior 1: 4-act navigation (§2.1)
- **Spec:** §2.1 — a four-act arc the user moves through.
- **Test:** none. **Impl:** `JourneyApp.jsx:27` phase state + `:40-49` keyboard ←/→ + `chrome.jsx` `LeftRailJ` rail-click `setPhase` + `PhaseFoot`.
- **Chain closes?** PARTIAL — impl present + user smoke ("all working as expected"); no test.

### Behavior 2: Phase-2 verify reveal (§2.1 l.35 "click Verify → four pillar badges animate in")
- **Spec:** §2.1 / JOURNEY_brief l.16 — Verify → Faithfulness/Completeness/Safety/Structural badges animate in → verdict.
- **Test:** none. **Impl:** `JourneyApp.jsx:54-59` (`runVerify` staggers `revealed` 1→4 at 600ms, `verify→done` at +2.9s) + `jp2.jsx:105-115` (`i < revealed` gated badges) + `:125-134` (PASS 8.6 banner). Faithful to the prototype.
- **Chain closes?** PARTIAL — impl faithful + user smoke; no test.

### Behavior 3: Phase-3 calibration before→after (§2.1 l.35 "re-run + compare before/after")
- **Spec:** §2.1 / JOURNEY_brief l.18 — tweak judges → re-run → compare before/after (improved/regressed).
- **Test:** none. **Impl:** `JourneyApp.jsx:61-64` (`runCalib`) + `jp3` Artifact3 compare table + `chrome.jsx` rail/status agreement `0.62→0.91` gated on `calib==="done"`.
- **Chain closes?** PARTIAL — impl faithful + user smoke; no test.

**Findings:**
- `[OPEN-QUESTION]` Behavioral fidelity is **manual-only** (no test layer) — by the §8-amended design (tests at WS-5-BFF). Recorded so the WS-5-BFF acceptance carries the first real behavioral test (e.g. a render/interaction test for the hero reveal).

---

## 3. Out-of-scope intrusion

Diff = 11 files, **all under `apps/shell/`** (audit Item 4). Grep-confirmed absent: Tailwind/`@theme`/shadcn, network (`fetch`/axios/localhost/`/v1/`), Tauri, test infra. `package.json` unchanged (zero new deps). No icon additions, no CSS-file rewrite (switch is inline-styled).

**Findings:**
- `[NON-BLOCKING]` `app.jsx` (`:50-66`, +8/-4) is outside the driver §2 list — but it is the **pre-authorized** additive theme-prop deviation (`function App({theme: themeProp, setTheme: setThemeProp})` + `theme = themeProp ?? themeLocal`), required for A3's shared theme, with the standalone fallback preserved. Authorized by the monitor at plan-review ("will not count as out-of-scope intrusion at the critique close") and logged in `plan_review.deviations[0]`. **Not intrusion.**
- No other out-of-scope edits. Scope held.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: mode-switch placement / final form
- **Spec text:** silent — §6 names a plugin/pane architecture but the Shell↔Journey *switch UI* is unspecified; the driver §3 #1 left it a plan-review decision.
- **Impl decided:** `root.jsx:16-49` — a thin fixed-position (`top:3, left:50%`) segmented control, inline-styled, `aria` tablist; default mode `"journey"`. The executor's own comment scopes it as "a thin dev/demo switch; real first-run activation gating is product logic for a later phase."
- **Question for spec author:** at WS-5c, integrate the mode control into the titlebar/chrome (it currently floats near the titlebar's centered command pill) and/or replace it with the real first-run activation gating?
- **Recommended resolution:** accept for now (user smoke-approved "all working"); revisit at WS-5c when the chrome is touched. **Severity: NON-BLOCKING.**

### Ambiguity 2: when do shell + journey converge domains (S-BS-17)
- **Spec text:** §2 is domain-agnostic; JOURNEY_brief is clinical. The shell skeleton shipped customer-support.
- **Impl decided:** journey ported clinical as-is; shell mock left customer-support (plan-review #2; no `data.jsx` edit).
- **Question:** reconcile to one demo domain (clinical) — and when?
- **Recommended resolution:** keep **S-BS-17** open; settle when the shell mock is next touched (WS-5c/WS-5-BFF). **Severity: OPEN-QUESTION (already tracked).**

**Findings:**
- `[NON-BLOCKING]` Mode-switch is a dev/demo overlay; integrate/replace at WS-5c (Ambiguity 1).
- `[OPEN-QUESTION]` S-BS-17 domain convergence timing (Ambiguity 2).

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 1 |
| 2 | Behavioral fidelity | 0 | 0 | 1 |
| 3 | Out-of-scope intrusion | 0 | 1 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 1 | 1 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions / dispositions

No BLOCKING findings. Dispositions for the record:

1. **Mode-switch is a dev/demo overlay (NB).** → fold a "integrate switch into chrome / replace with activation gating" note into the WS-5c scope. No action this cycle.
2. **Behavioral verification manual-only (OQ).** → WS-5-BFF acceptance must carry the first behavioral test (the §8 amendment already states this). No action this cycle.
3. **S-BS-17 domain split (OQ).** → stays open; settle when the shell mock is next touched. Already tracked.
4. **`app.jsx` deviation (NB).** → authorized; recorded. No action.

---

## Critic discipline self-check

- [x] Inline-mode caveat: performed by the **monitor**, not a fresh critic (HARD-GATE override, user-delegated). Independent-cognition forfeited — flagged. A fresh-critic pass is available if desired before close.
- [x] Read the spec + the diff (the actual committed `JourneyApp.jsx`/`root.jsx`/`jp2.jsx` + the `app.jsx`/`main.jsx` diffs) before anchoring on the session log.
- [x] Each finding cites spec file:line AND impl file:line.
- [x] No code/spec/driver edits during this pass (only wrote this critique file).

---

## Appendix: commits audited

```
00c68b9 feat(ws5b): JourneyApp composition + Shell↔Journey switch
4a9ef16 feat(ws5b): the four activation acts (jp1–jp4)
460b677 feat(ws5b): journey data + chrome (ESM port of the activation journey)
(base 57743ee)
```

## Appendix: files changed

```
apps/shell/README.md                  |  20 +-
apps/shell/src/app.jsx                |   8 +-   (authorized theme-prop deviation)
apps/shell/src/journey/JourneyApp.jsx | 134 +
apps/shell/src/journey/chrome.jsx     | 156 +
apps/shell/src/journey/journeyData.js |  80 +
apps/shell/src/journey/jp1.jsx        | 119 +
apps/shell/src/journey/jp2.jsx        | 154 +
apps/shell/src/journey/jp3.jsx        | 173 +
apps/shell/src/journey/jp4.jsx        | 126 +
apps/shell/src/main.jsx               |   5 +-
apps/shell/src/root.jsx               |  65 +
11 files changed, 1032 insertions(+), 8 deletions(-)
```
