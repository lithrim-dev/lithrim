# Spec-Adherence Critique — `bench-salvage` phase `WS-5`

> Inline-mode critique (monitor self-audit). Committed alongside close-out artifacts.
> **Note on mode:** WS-5 is **HARD-GATE** (`prompts/index.json` →
> `bench-salvage-phaseWS-5-frontend-shell-plugin-driver.hardness = "HARD-GATE"`,
> `hardness_reason`: "First UI layer … + a new plugin-contract surface + a live :8002
> side-effect … Fresh-critic close."). The strict path is a fresh critic with no build
> context. **User consciously elected inline** (decision captured 2026-06-01: offered
> fresh-critic vs inline vs accept-build-verified; chose inline). Recorded as an override;
> the independent-cognition property is forfeited and noted in the self-check.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-5` (real 3-pane product-shell skeleton — the re-scoped program, not the superseded thin stdlib driver)
- **Driver bundle:** **none.** The shell was built directly by the prior monitor session from the Claude Design handoff; the registered WS-5 bundle (`bench-salvage-phaseWS-5-frontend-shell-plugin-driver`) is `superseded_by docs/specs/SPEC_PRODUCT_SHELL.md`. No replacement driver was authored. Deliverable contract for this critique = **`SPEC_PRODUCT_SHELL.md` §8 (WS-5 row)** + §2/§3/§4/§5.
- **Commits audited:** none — `apps/shell/` is **uncommitted working tree** (18 files, `git add -n apps/`). The "diff" is the working tree vs empty.
- **Spec(s) read against:** `docs/specs/SPEC_PRODUCT_SHELL.md` §2 (3-pane experience, ll.20–26), §2.1 (4-phase journey, ll.28–37), §3 (journey→primitive mapping, ll.43–52), §4 (stack, ll.56–61), §5/§5b/§5c (BFF bridge + protocols, ll.65–91), §8 (phasing, l.112), §9 (the honest bet, l.122); `docs/design/JOURNEY_brief.md` (Phase 1 Scribe/healthcare, ll.14, 34).
- **Critique mode:** `inline` (monitor self-audit; HARD-GATE override noted above)
- **Date:** 2026-06-01
- **Reviewer:** monitor (resumed session)

---

## Verdict

**BLOCKING DRIFT**

The shell faithfully realizes the **§2 3-pane experience surface** (pixel-clean, brand-exact, resizable panes, journey rail, inline cards, fullscreenable artifact pane) — but it does so on **100% hardcoded mock data** with **no FastAPI BFF, no `run_eval` vertical, and no Tauri wrapper**, which are three of the five components the spec's WS-5 row explicitly requires ("the **real 3-pane shell skeleton** — React/Vite + **Tauri v2** + Tailwind/brand + **the FastAPI BFF sidecar** — with **ONE vertical working end-to-end** … **Proves the whole stack + the bridge with one real artifact**"). The build is a strong **front-end skeleton**, but it is **not** the spec's WS-5 acceptance, so "WS-5 = done / whole stack proven" must not enter canon without an explicit phasing re-cut. The single BLOCKING finding's correction is administrative (amend §8 to a front-end-first cut, then carve the BFF+vertical into its own phase) — not a code rework — and aligns with the user's evident FE-first sequencing (WS-5b journey next). User decides the correction path per the HARD-GATE halt rule.

---

## 1. Surface fidelity

> Contract = `SPEC_PRODUCT_SHELL.md` §2/§3/§4/§8. (No "public API" in the harness sense — this is a UI surface; "public symbols" = the panes/components/artifact-types the spec names + the §8 WS-5 component list.)

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| §2 l.20–24: 3 panes — left navigator/journey rail · center conversation+generative-UI · right artifacts/preview | `app.jsx:80–102` (`LeftRail`/`CenterPane`/`ArtifactPane`, resizable) | ✓ realized | — |
| §2 l.22 left rail: journey checkpoints `domain → judge → oracle → KB → eval → review` | `data.jsx:12–19` STEPS = Domain · Judge · Oracle · Knowledge Base · Run · Review; rendered `panes.jsx:36–53` | ✓ match (eval→"Run") | — |
| §2 l.26: large outputs "slide into pane 3 as inspectable, **fullscreenable** artifacts" | `artifact.jsx:130–168` (`full` prop); `app.jsx:57,96` fullscreen toggle | ✓ realized | — |
| §3 l.43–52 artifacts: eval-report · judge-council · ontology-config | `artifact.jsx:153–157` tabs `report`/`judges`/`config` | ✓ surface present (mock) | NON-BLOCKING |
| §8 WS-5 (l.112): **FastAPI BFF sidecar** | absent — `grep fetch/localhost/run_eval/fastapi src/` = none; `vite.config.js:1–8` no proxy | ✗ **absent** | **BLOCKING** |
| §8 WS-5 (l.112): **Tauri v2** wrapper | absent — no `src-tauri/`, no `tauri.conf.json` | ✗ **absent** | **BLOCKING** |
| §8 WS-5 (l.112): **ONE vertical e2e** — eval-report over WS-4a `run_eval.run` (replay default + one live run) | `artifact.jsx:3` imports mock `TILES/FAILURE_MODES/JUDGES`; `ReportTab:5–61` renders them; `app.jsx:34–51` StatusBar hardcodes "Run #218", "κ 0.88", "v0.9.4" | ✗ **mock, not harness output** | **BLOCKING** |
| §4 l.58–59: Tailwind v4 + shadcn/ui | plain CSS port (`main.jsx:3` imports only `styles.css`; `styles.css`/`journey.css` are the verbatim prototype CSS) | ✗ — **documented decision** (user decision 2026-06-01: commit as-is, Tailwind additive/incremental at WS-5b) | NON-BLOCKING (decided) |
| §4 l.60–61: TanStack Query + Zustand + assistant-ui | none present (`package.json:12–15` deps = react/react-dom only) | ✗ — expected at no-server-state skeleton stage | NON-BLOCKING |
| JOURNEY_brief Phase 1 (l.14, 34): first domain = **Scribe / healthcare pack** | shell content is **customer-support** (`app.jsx:14` "acme-support"; `data.jsx:50` `domain: "customer_support"`, `support_transcripts.jsonl`) | ✗ domain mismatch | NON-BLOCKING |

**Findings:**

- `[BLOCKING]` **The BFF, the `run_eval` vertical, and Tauri — three of the five §8 WS-5 components — are absent; the shell renders hardcoded mock data, so the spec's load-bearing WS-5 acceptance ("Proves the whole stack + the bridge with one real artifact", §8 l.112) is unmet.** This is the headline finding (also restated behaviorally in §2). Evidence: `data.jsx:1` ("representative content"), no network call anywhere in `src/`, no Tauri files.
- `[NON-BLOCKING]` **Domain mismatch.** The skeleton's mock content is customer-support, not the clinical/Scribe/healthcare first domain the harness (`clinical_v1` ontology) and `JOURNEY_brief` Phase 1 specify. Harmless as throwaway demo content, but it must be reconciled when WS-5b ports the (Scribe/healthcare) journey.
- `[NON-BLOCKING]` **Tailwind/shadcn + state/chat libs absent** — a documented decision (commit-as-is; Tailwind is additive at WS-5b), recorded here so it isn't mistaken for silent drift.

---

## 2. Behavioral fidelity

> **Structural caveat:** `apps/shell/` ships **zero tests** (`package.json:7–11` scripts = dev/build/preview only; no vitest/jest, no test files). The spec assertion → **test** → impl chain therefore **cannot close via a test** for any behavior; behavioral verification was manual only (clean `vite build` + the live `:5180` render). This is itself a NON-BLOCKING finding for a visual skeleton, but it means Q2 traces to impl + manual-render, not to tests.

### Behavior 1: resizable 3-pane shell

- **Spec assertion:** §2 l.20 — three panes (navigator / conversation / artifacts).
- **Test:** none.
- **Implementation:** `app.jsx:64–76` (`drag`/`clamp` pointer handlers), `app.jsx:87,90` resize handles, panes at `app.jsx:86–98`.
- **Chain closes?** PARTIAL — impl present + manually verifiable at :5180; no test.

### Behavior 2: fullscreenable artifact pane

- **Spec assertion:** §2 l.26 — "fullscreenable artifacts."
- **Test:** none.
- **Implementation:** `artifact.jsx:138,160` (`full` class + centered max-width), `app.jsx:57,96` toggle.
- **Chain closes?** PARTIAL — impl present + manually verifiable; no test.

### Behavior 3: eval-report artifact over the WS-4a vertical (the §8 WS-5 acceptance behavior)

- **Spec assertion:** §8 l.112 — "the **eval-report artifact** in pane 3 over the WS-4a vertical (`run_eval.run`, replay default + one live run). **Proves the whole stack + the bridge.**"
- **Test:** none.
- **Implementation:** **none.** `ReportTab` (`artifact.jsx:5–61`) renders mock `TILES`/`FAILURE_MODES` from `data.jsx`; `report.composite`/`calibration_check` from the harness are never called; no BFF to call them through.
- **Chain closes?** **NO** — neither impl nor test. The behavior that the spec says WS-5 exists to prove is absent.

**Findings:**

- `[BLOCKING]` Behavior 3 (the WS-5 acceptance behavior) does not exist — restatement of the §1 BLOCKING finding from the behavioral angle.
- `[NON-BLOCKING]` Zero tests in `apps/shell/`; behavioral fidelity is manual-only. Acceptable for a pixel-port skeleton, recorded for the phase where a vertical lands (a vertical should arrive with at least a smoke test of the BFF round-trip).

---

## 3. Out-of-scope intrusion

> No driver → deliverables contract = `SPEC_PRODUCT_SHELL.md` §2/§3/§8. "Intrusion" = built surface beyond the WS-5 skeleton scope.

Working-tree files (`git add -n apps/`, 18 files): `apps/shell/{.gitignore, README.md, index.html, package.json, package-lock.json, vite.config.js}` + `public/{icon.svg, lithrim-logo.png}` + `src/{main,app,panes,cards,artifact,brand,icons,data}.jsx` + `src/{styles,journey}.css`. **All confined to `apps/shell/`** — no edits leaked into `lithrim_bench/`, `docs/`, `data/`, or `.devloop/` (git status confirms only `apps/`, `.claude/`, and the handoff doc are untracked; nothing under the harness changed).

**Findings:**

- `[NON-BLOCKING]` **Scope pulled forward into WS-5d.** The artifact pane already ships the **Judge-council** (`artifact.jsx:63–98`) and **Config-editor** (`artifact.jsx:100–128`) tabs as mock UI. §8 assigns "judge-council view + ontology-config editor" to **WS-5d** ("Artifacts pane thickened"), not WS-5. Harmless (mock, and a faithful port of the design), but it means WS-5d inherits *wiring* the already-built shells rather than building them — note so WS-5d scope is re-cut accordingly.
- `[NON-BLOCKING]` **`src/journey.css` is pre-staged but unused** — present (`src/journey.css:2` "activation-journey components") but **not imported** (`main.jsx:3` imports only `styles.css`; `grep journey.css` matches only its own comment). Inert; deliberately staged for the WS-5b journey port. Carries no runtime effect.
- No genuine out-of-scope intrusion (no drive-by refactors, no harness edits, no dependency churn beyond react/react-dom + vite).

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: front-end-first vs thin-vertical-first sequencing

- **Spec text:** §8 l.108 — "thin vertical first, then thicken"; the WS-5 row (l.112) bundles BFF + Tauri + one real vertical **into WS-5 itself**. §9 (l.122) separately frames the program as "front-running the semantic moat … a conscious GTM/demo/fundraise bet."
- **Implementation decided:** front-end **surface**-first — a broad, polished, mock-data 3-pane shell with **no vertical**, deferring the BFF to WS-5c (per `apps/shell/README.md:43–45`).
- **Alternatives that would also be spec-compliant:** the literal §8 reading (skeleton + BFF + one real eval-report vertical, narrow but live) before any journey/component breadth.
- **Question for spec author (user):** ratify the re-cut — does WS-5 become "front-end shell skeleton (mock)" with a **new dedicated phase** (e.g. WS-5-BFF) for "FastAPI BFF + one real `run_eval` eval-report vertical + Tauri", or do we hold WS-5 open until the vertical lands?
- **Recommended resolution:** **update spec §8** to a front-end-first cut (it matches the as-built reality and the user's WS-5b-next intent), and carve the BFF+vertical into its own HARD-GATE phase so "proves the whole stack" is still owed and tracked, not dropped. This is the proposed correction for the BLOCKING finding.

### Ambiguity 2: which domain seeds the skeleton's demo content

- **Spec text:** §2 is domain-agnostic ("the shell loads UI 'apps' as plugins", §6 l.95); `JOURNEY_brief` Phase 1 (l.14, 34) names **Scribe / healthcare** as the first activation domain.
- **Implementation decided:** customer-support throughout (`data.jsx`, `app.jsx:14`).
- **Alternatives:** clinical-scribe content (matches the harness `clinical_v1` + the journey brief) vs a neutral non-clinical demo (de-risks showing un-vetted clinical text in a fundraise demo).
- **Question for spec author (user):** does the shipped demo content track the real first domain (Scribe/healthcare) or stay a neutral support demo? It matters at WS-5b, where the journey port is explicitly Scribe/healthcare.
- **Recommended resolution:** decide at WS-5b plan-review; likely converge demo content onto Scribe/healthcare so the journey, the harness, and the brief agree.

### Ambiguity 3: the §6 plugin/pane contract + §5b generative-UI protocol

- **Spec text:** §6 l.95–96 — the shell "loads UI 'apps' as plugins (a plugin declares an id + which pane(s) + its routes)"; §5b — `tool-<name>` ↔ component registry.
- **Implementation decided:** neither contract exists yet — panes/cards are imported statically (`app.jsx:3–5`, `panes.jsx:4`); no plugin registry, no tool→component map.
- **Question for spec author (user):** these are explicitly later phases (plugin contract unscoped; generative-UI = WS-5c). Confirm they stay deferred — no action needed now, recorded so their absence isn't read as drift.
- **Recommended resolution:** accept as deferred (WS-5c).

**Findings:**

- `[OPEN-QUESTION]` Ratify the front-end-first §8 re-cut (Ambiguity 1) — paired with the BLOCKING correction.
- `[OPEN-QUESTION]` Demo-content domain: support vs Scribe/healthcare (Ambiguity 2) — settle at WS-5b.
- `[OPEN-QUESTION]` Plugin + generative-UI contracts deferred to WS-5c (Ambiguity 3) — confirm.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 1 | 3 | 0 |
| 2 | Behavioral fidelity | 0 (restate of #1) | 1 | 0 |
| 3 | Out-of-scope intrusion | 0 | 2 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 3 |

**Total BLOCKING: 1** → cycle CANNOT close as "WS-5 per spec §8" without the correction below.

---

## Required actions

**BLOCKING finding:** The BFF + `run_eval` vertical + Tauri (3 of 5 §8 WS-5 components) are absent; the shell is a mock-data front-end skeleton, so §8's "Proves the whole stack + the bridge with one real artifact" is unmet.

1. **Proposed correction (Owner: spec author = user, executed by monitor in close-out):**
   **Amend `SPEC_PRODUCT_SHELL.md` §8** to a front-end-first cut that matches the build and the user's sequencing —
   - **WS-5** ≔ "real 3-pane shell **skeleton** (React/Vite, brand-exact, mock data) + journey rail + inline cards + artifact pane" — **the as-built**, now honestly scoped.
   - **new WS-5-BFF** (HARD-GATE) ≔ "FastAPI BFF sidecar + ONE `run_eval` eval-report vertical (replay default + one live run) + Tauri shell" — the displaced "prove the whole stack" half, still owed and tracked, not dropped.
   - Re-cut WS-5d to "**wire** the already-built judge-council + config artifact surfaces to the BFF" (they exist as mock today, per §3 finding).
   Then WS-5 (skeleton) closes cleanly against the amended spec, and the commit + WS-5b proceed.
   **Alternative (rejected as off-intent):** hold WS-5 open and build the BFF+vertical now before committing — contradicts the user's WS-5b-next choice.

**NON-BLOCKING / OPEN-QUESTION dispositions:**

1. **Domain mismatch (support vs Scribe/healthcare)** → log as a WS-5b plan-review input (reconcile demo content with the journey + harness domain). Candidate new seam **S-BS-17** if not resolved at WS-5b kickoff.
2. **Zero tests in `apps/shell/`** → accept for the skeleton; require a BFF round-trip smoke test when the vertical lands (WS-5-BFF acceptance).
3. **WS-5d surfaces pulled forward (judge-council + config tabs as mock)** → re-cut WS-5d to "wire, don't build" in the §8 amendment.
4. **`journey.css` pre-staged unused** → accept (intentional WS-5b staging).
5. **Tailwind/shadcn deferral** → accept (documented decision); revisit incrementally at WS-5b.

---

## Critic discipline self-check

- [x] Read the spec(s) before any session-log/handoff anchoring — but **inline-mode caveat:** this critique was performed by the **monitor**, not a fresh critic; the prior handoff was already in working context from resume. The independent-cognition property is **forfeited** (HARD-GATE override, user-elected). A fresh-critic pass would be the discipline-pure path and remains available if the user wants it before the §8 amendment.
- [x] No commits to `git show` (working tree); read the actual `src/*.jsx` + `vite.config.js` + `package.json` directly rather than trusting the handoff's "shell built" prose.
- [x] Each finding cites spec file:line AND impl file:line.
- [x] Did NOT edit any code, spec, or driver during this pass (only wrote this critique file).

---

## Appendix: "diff" audited

No commits — `apps/shell/` is uncommitted. `git add -n apps/` (respecting `apps/shell/.gitignore` = node_modules/dist/.vite/*.local):

```
apps/shell/.gitignore
apps/shell/README.md
apps/shell/index.html
apps/shell/package.json
apps/shell/package-lock.json
apps/shell/vite.config.js
apps/shell/public/icon.svg
apps/shell/public/lithrim-logo.png
apps/shell/src/app.jsx
apps/shell/src/artifact.jsx
apps/shell/src/brand.jsx
apps/shell/src/cards.jsx
apps/shell/src/data.jsx
apps/shell/src/icons.jsx
apps/shell/src/journey.css
apps/shell/src/main.jsx
apps/shell/src/panes.jsx
apps/shell/src/styles.css
```

Live verification at critique time: shell `:5180` → HTTP 200; live deps `:8002` → 200, `:3031` → 200 (the shell does not call them — confirmed mock).
