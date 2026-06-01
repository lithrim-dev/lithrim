# Spec-Adherence Critique — `bench-salvage` phase `WS-5c`

> Fresh-critic session (HARD GATE). Cold read of the spec + the diff, no prior
> implementation context. Read the spec/driver/diff/tests before the executor's
> session log; log was read last, for cross-check only.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-5c` — generative-UI foundation
- **Driver bundle:** `bench-salvage-phaseWS-5c-generative-ui-foundation-driver` (v1)
- **Commits audited:** `a617d42..0c13d3f` (9 commits: `efefaa8` D0 · `0e309c4` D1 · `1c6a9a6` D2 · `d5ad02b` D3 · `9e2ab93` D4 · `67492a0` D5 · `043ece4` D6 · `3e143b8` D7 · `0c13d3f` post-close chrome fix)
- **Spec(s) read against:** `docs/specs/SPEC_PRODUCT_SHELL.md` §2/§2.1/§4(:54-63)/§5b(:87-89)/§5c/§6/§8(:129)/§10(:144); `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (BFF targets harness; Mongo-out)
- **Critique mode:** `fresh-critic`
- **Date:** `2026-06-01`
- **Reviewer:** `critic session-2026-06-01 (fresh)`

---

## Verdict

**`BLOCKING DRIFT` (original) → RESOLVED by `e9f863b` → effective `NON-BLOCKING FINDINGS`** *(see Reverification addendum, 2026-06-01)*

The two newly-locked contracts (§5b `tool-<name>` registry + §4 `@theme`-over-`:root` token bridge) and the §10 read-only-ontology surface are implemented **exactly** to spec, with closing spec→test→impl chains across all three picked behaviors. The single blocker is **not** in the gated D0–D7 work — it is a syntactic defect introduced by the **9th, post-close commit** (`0c13d3f`): a stray `}` text node shipped into the Shell titlebar at `apps/shell/src/app.jsx:23`, which renders a literal `}` in the chrome and survives `npm run build` clean + 18 green tests undetected. It directly negates that commit's own stated goal (chrome alignment) and the §8:127 "pixel-faithful" chrome contract. One-character correction commit required; everything else is CLEAN or OPEN-QUESTION.

---

## Reverification addendum (2026-06-01, post-critique)

User requested **reverify**. The sole BLOCKING finding has been corrected on-branch.

- **Fix commit:** `e9f863b` — *"fix(shell): remove stray `}` literal in the Shell titlebar + guard with a render test"* (HEAD is now `e9f863b`, one past the audited `0c13d3f`).
- **Defect cleared:** `apps/shell/src/app.jsx:23` now reads `<div className="tb-right">` (stray `}` deleted). `grep -rn '">}' src/` → none found anywhere in `src/`.
- **Root-cause coverage gap closed:** new `apps/shell/src/app.test.jsx` renders `<App mode="shell">` and asserts (`:14-15`) the mode-switch tabs are present, (`:20`) the Scribe crumb renders, and (`:22`) `titlebar.textContent` does **not** contain `}` — i.e. the exact "no test rendered the Shell `TopBar`" gap the critique named is now guarded against regression.
- **Re-run (critic, this session):** `npm run build` clean (357.82 kB JS / 59.45 kB CSS); `npm run test:run` → **19 passed (4 files)** — up from 18/3, the +1 being the new chrome smoke.

The fix is faithful to the critique's "Required actions" (one-character deletion **plus** the recommended Shell-TopBar guard). The deferred `:5180` light/dark × Shell/Journey visual-parity smoke (A1/A4) remains the one human-eyeball step still owed before HARD-GATE close — unchanged by this fix. The two OPEN-QUESTIONs (Q4) stand as documented for the spec author; neither blocks.

**Effective verdict after reverification: `NON-BLOCKING FINDINGS`.** Cycle MAY close once the monitor runs the deferred 60-second `:5180` visual-parity smoke.

---

## 1. Surface fidelity

The two contracts this cycle was chartered to **lock** are the priority. All three surfaces match.

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| §5b:89 — 5 tools: `tool-flag_editor`, `tool-contract_builder`, `tool-kb_picker`, `tool-verdict_card`, `tool-calibration_chart` | `genui/registry.js:20-26` `KNOWN_TOOLS` — same 5, same names | exact | — |
| §5b:89 — "AI SDK message-`parts` (`part.state === 'output-available'` → render component)" | `genui/registry.js:56-75` `renderTool(part)` resolves component when `state === "output-available"`; spreads `part.output` as props | exact (incl. plan-review decision 4) | — |
| §6.2 — "`tool-<name>` ↔ component registry; components return results into the conversation" | `registerTool`/`getTool` (`registry.js:30-36`); inputs return via `onResult()` (`FlagEditor.jsx:97`, `ContractBuilder.jsx:54`, `KbPicker.jsx:41`) | exact | — |
| §5b:89 — unknown tool degrades | `registry.js:42-49,60` `toolFallback()` → "Unsupported component" (never throws/blank) | exact | — |
| §4:61 — "both consume one token source (`:root` custom properties ↔ `@theme`)" | `src/theme.css:30-57` `@theme inline { --color-background: var(--bg); … }` bridging `styles.css` `:root` tokens | exact | — |
| §4:61 — shell dark selector is `[data-theme="dark"]`, **not** `.dark` | `theme.css:18` `@custom-variant dark (&:where([data-theme="dark"] *))` | exact | — |
| §10:144 — `GET /v1/ontology` **read-only**; `PUT`/write **deferred** to WS-5c/d | `bff.js:26-28` only `getCorpus`/`getOntology` (GET); **no `PUT` method exists** in the client | exact | — |

**Findings:**

- No surface drift detected. All locked symbols — the 5-tool registry key list, `renderTool`/`registerTool`/`getTool`, the `@theme` token bridge, the GET-only ontology client — match spec exactly.
- Documented (not drift): registry shape uses the AI-SDK message-`parts` plain registry rather than `assistant-ui makeAssistantToolUI` — plan-review **decision 4** (`session…json` `plan_review.deviations[3]`), consistent with §5c zero-LLM. The spec offers both (§5b:89 "or"); the chosen one is spec-listed.

---

## 2. Behavioral fidelity

### Behavior 1: tool-call → registered component; unknown degrades gracefully (§5b)

- **Spec assertion:** §5b:89 — "the shell maps it to a registered React component … Unknown tool → graceful fallback" (driver A2).
- **Test:** `genui/registry.test.jsx:32-48` — loops all 5 `KNOWN_TOOLS`, asserts each renders its own title from `{type, state:"output-available"}` and **not** the fallback; `:40-43` asserts `tool-does_not_exist` → "Unsupported component"; `:45-48` typeless part → fallback; `:50-58` `output-error`/`input-streaming` branches.
- **Implementation:** `registry.js:56-75` `renderTool`; `genui/index.js:4-8` barrel imports trigger each component's `registerTool()` side-effect.
- **Chain closes?** **YES.** Test exercises the registered path, the unknown path, and the non-output states against the real `renderTool`.

### Behavior 2: ontology read via GET only, no PUT (§10 / driver A3)

- **Spec assertion:** §10:144 — "`GET /v1/ontology` (**read-only**). **`PUT`/write-ontology DEFERRED**"; driver §4 NOT-in-scope: "WS-5c reads ontology via **GET only**".
- **Test:** `genui/inputs.test.jsx:8-16,24-41` mocks `bff.getOntology`, asserts it is called **once** (`:29`) and `FlagEditor` returns `{severity_map, flags[]}` via `onResult` on Apply; `bff.test.jsx:63-68` asserts `getOntology()` hits `GET /v1/ontology?agent=…`.
- **Implementation:** `FlagEditor.jsx:49` reads via `getOntology(agent)`, returns edited config via `onResult` (`:86-98`) — no persistence; `bff.js:8-28` exposes only GET reads + the existing `POST /v1/run-eval`; **no PUT path exists**.
- **Chain closes?** **YES.** PUT-absence is structurally guaranteed (the client has no write method), stronger than a test could assert. Minor note: the tests assert *presence-of-GET*, not *absence-of-PUT* — but since no PUT symbol exists, the absence is enforced at the module surface.

### Behavior 3: Tailwind adopted incrementally; chrome CSS NOT rewritten (§4)

- **Spec assertion:** §4:61 — "adopted **incrementally** — the existing bespoke chrome CSS is **not** rewritten into utilities."
- **Test/evidence:** `git diff --stat a617d42..0c13d3f -- apps/shell/src/styles.css apps/shell/src/journey.css` → **empty** (both files untouched across all 9 commits). `theme.css` is **additive** (`main.jsx:3` imports it alongside the untouched `styles.css`/`journey.css`). Build clean; CSS bundle 38.9→59.2 kB = utilities generated only from net-new components.
- **Implementation:** D2 input widgets (`genui/FlagEditor/ContractBuilder/KbPicker.jsx`) use shadcn primitives + Tailwind utilities; D3 cards (`genui/VerdictCard.jsx:25`, `CalibrationChart.jsx:17`) stay on `.icard` chrome CSS.
- **Chain closes?** **YES.** The incremental-adoption invariant is verifiable in the diff itself — the bespoke chrome CSS files never appear.

**Findings:**

- All three picked behaviors close. No behavioral drift.

---

## 3. Out-of-scope intrusion

Driver deliverables (verbatim, §2 / §6 commit structure): **D0** Tailwind/`@theme`/shadcn foundation · **D1** registry · **D2** 3 input widgets · **D3** promote verdict+calibration cards · **D4** mode-switch into chrome · **D5** S-BS-17 demo reconcile · **D6/D7** Vitest infra + binding test + README. Eight commits (`efefaa8..3e143b8`).

`git diff --stat a617d42..0c13d3f` — all **37** files under `apps/shell/`. No `apps/bff/`, `lithrim_bench/`, or `../lithrim-backend` edits; `pyproject.toml` unchanged (no new Python deps). **File-boundary scope (A7) holds.**

**The 9th commit (`0c13d3f`) — the flagged item.** It is **not** in the driver's 8-commit structure (§6) and **not** in the session log (which ends at `3e143b8`, 8 commits, verdict `PROCEED-WITH-CAVEATS`). It is a post-close, user-reported chrome-parity correction. Contents:

1. `journey/chrome.jsx:46-48` — add the 46px rail-brand bar + `Wordmark` to `LeftRailJ`, drop the coral-avatar `Mark` block.
2. `app.jsx:14` + `chrome.jsx:106` — move `<ModeSwitch>` from `tb-right` to a stable slot right after the window lights.
3. `journey/JourneyApp.jsx:28-29,87,107` — align pane defaults (`leftW 280→270`, `rightW 460→440`) + drag bounds to the Shell.

**Findings:**

- `[NON-BLOCKING]` The 9th commit is **out of the WS-5c D0–D7 deliverables list** (chrome-parity is WS-5/WS-5b chrome territory, not a WS-5c deliverable). It is mitigated: it was **user-reported + user-approved** (commit trailer: "post-close correction, user-approved"), stays inside `apps/shell/`, and aligns with the documented `[[shell-journey-chrome-parity]]` decision (canonical rail logo = full Wordmark; shared pane defaults). Disposition: accept as a deliberate post-close fix, but note it was **never inside the gated cycle** the executor reported.
- `[BLOCKING]` **Stray `}` shipped into the Shell titlebar.** `app.jsx:23` reads `<div className="tb-right">}` — the `}` is a JSX **text child** that renders a literal `}` in the titlebar's right cluster (before the theme button). Introduced by `0c13d3f` (the move of `<ModeSwitch>` out of `tb-right` left a dangling brace). Verified: `npm run build` is clean (357.82 kB; valid JSX) and `npm run test:run` is 18/18 green — **neither catches it** (no test renders the Shell `TopBar` or asserts the absence of stray text). This negates the 9th commit's own stated purpose ("align chrome … stable mode-switch") and violates the **pixel-faithful, Claude-desktop-class chrome contract** (spec §2:18-26 + §8:127 "pixel-faithful Claude Design port"). Spec: `SPEC_PRODUCT_SHELL.md:127` / §2:24. Impl: `apps/shell/src/app.jsx:23`.

> Why this is BLOCKING and not cosmetic: the cycle's whole bet (§9) is that a *polished* shell is the wedge; A4's verification was an unrun "manual smoke at `:5180`" (the executor's own A4 evidence still cites `app.jsx:23` as the ModeSwitch site — a citation made **stale** by the very commit that broke that line). The deferred smoke is exactly the gate that would have caught this. A literal brace in the demo chrome is a one-character fix but a material defect in shipped UI.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: D3 "re-home on Tailwind/shadcn" vs §4 "chrome CSS not rewritten"

- **Spec text:** driver D3:89 — "promote … `(re-home on Tailwind/shadcn)`" vs §4:61 — "the existing bespoke chrome CSS is **not** rewritten into utilities."
- **Implementation decided:** `genui/VerdictCard.jsx:25` + `CalibrationChart.jsx:17` keep the cards on `.icard` chrome CSS; they were re-homed into the **registry/protocol** (`registerTool`, rendered via `renderTool` in `panes.jsx:113,122`) but **not restyled** to Tailwind. The foundation is exercised by the D2 input widgets instead.
- **Alternatives also spec-compliant:** rewrite the two cards to Tailwind utilities (literal D3 "re-home on Tailwind") — but that would contradict §4:61.
- **Question for spec author:** Does "re-home on Tailwind/shadcn" mean *protocol* re-homing (done) with Tailwind-restyle of datapoint cards **deferred/optional**, or is keeping them on `.icard` under-adoption owed in WS-5d?
- **Recommended resolution:** **accept** — the §4:61 incremental principle governs; the literal D3 parenthetical is the looser of the two. Already surfaced + monitor-blessed at plan-review (session log `plan_review.deviations` "D3 interpretation … monitor-blessed"). Lock the wording so D3 is not later read as under-adoption.

### Ambiguity 2: datapoint-component prop convention is inconsistent

- **Spec text (absence):** §5b:89 says only "render component" — silent on the **prop-passing shape** from a `tool-<name>` part's `output`.
- **Implementation decided:** `renderTool` spreads `...(part.output || {})` as props (`registry.js:74`), but `VerdictCard.jsx:22` destructures `{ data }` while `CalibrationChart.jsx:10` destructures `{ points, ece, brier }`. So to feed real data you would pass `part.output = { data: {...} }` for the verdict card but `part.output = { points, ece, brier }` (spread directly) for the calibration card — two different conventions for two sibling datapoint tools.
- **Alternatives also spec-compliant:** a single convention (either always-wrapped or always-spread).
- **Question for spec author:** Lock one datapoint `part.output` convention before WS-5d wires a host that emits real datapoints.
- **Recommended resolution:** **accept for now, lock in WS-5d.** Low impact today — only `DEMO`/default data flows (S-BS-19: no host emits these parts with real `output` yet), so the inconsistency is inert until WS-5d.

### Ambiguity 3 (resolved on inspection, recorded for completeness): ContractBuilder contract shape

- **Spec text:** driver D2:84 — "the WS-3a structural-floor contract shape"; spec §3 names `verification_contracts` but does not enumerate fields/types.
- **Implementation decided:** `ContractBuilder.jsx:45-51` emits `{ contract_type, flag_code, question, params, version }` + a 4-value `CONTRACT_TYPES` enum (`:23`).
- **Verification:** the emitted shape **matches** the real `data/ontology/clinical_v1.json` seeded contract exactly (`contract_type`/`flag_code`/`params`/`question`/`version`; seeded `contract_type: "presence_check"` = the builder's default). The only invented surface is the *other* enum values (`negation_check`/`code_match`/`range_check`), which the component comment acknowledges as net-new (`clinical_v1` ships one floor contract).
- **Question for spec author:** confirm the additional `contract_type` values are intended to be authorable before WS-5d wires any write.
- **Recommended resolution:** **accept** — field shape is faithful to the live schema; not a finding.

**Findings:**

- `[OPEN-QUESTION]` D3 "re-home" wording (Ambiguity 1) — accept the §4 incremental reading; lock the phrasing.
- `[OPEN-QUESTION]` datapoint `part.output` prop convention (Ambiguity 2) — lock one shape in WS-5d.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 1 | 1 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 2 |

**Total BLOCKING: 1 (original)** → **0 after `e9f863b`** (see Reverification addendum). Cycle MAY close pending only the deferred `:5180` visual-parity smoke.

---

## Required actions

**BLOCKING:**

1. **Finding:** stray `}` text node in the Shell titlebar — `apps/shell/src/app.jsx:23` (`<div className="tb-right">}`), introduced by `0c13d3f`; renders a literal `}` in the chrome; not caught by build or the 18 tests.
   **Proposed correction:** one-character fix commit — delete the stray `}` (`<div className="tb-right">`). Then run the deferred **60s `:5180` visual-parity smoke** (light/dark × Shell/Journey) the executor and `next_session_hint` both flagged, since that smoke is the gate that would have caught this.
   **Owner:** monitor in close-out (trivial), or a follow-up correction cycle.
   **STATUS: RESOLVED** by `e9f863b` — stray `}` deleted at `app.jsx:23` + new `app.test.jsx` Shell-TopBar guard (asserts no `}` leaks); build clean, 19/19 tests pass (verified by critic on reverify). The deferred `:5180` smoke is still owed.

**NON-BLOCKING / OPEN-QUESTION (cycle may proceed once the blocker is fixed):**

1. **Finding:** 9th commit (`0c13d3f`) is out of the WS-5c deliverables list (chrome-parity, not D0–D7) and outside the gated session log.
   **Proposed disposition:** accept as user-approved post-close correction; record that WS-5c's gated scope is D0–D7 (8 commits) and the chrome-parity fix rode along under `[[shell-journey-chrome-parity]]`.
2. **Finding:** D3 "re-home on Tailwind/shadcn" vs §4 incremental (Ambiguity 1).
   **Proposed disposition:** spec/driver wording lock; accept as-is.
3. **Finding:** datapoint `part.output` prop convention inconsistent across VerdictCard/CalibrationChart (Ambiguity 2).
   **Proposed disposition:** lock one convention as a WS-5d acceptance item (tracks with S-BS-19's host-wiring).

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec without reading the executor's session log first (log read last, step 6).
- [x] Read the diff via `git show` against each of the 9 commits, not via the executor's prose summary.
- [x] Each finding cites both spec file:line and implementation file:line.
- [x] Did NOT edit any code, spec, or driver.
- [x] Did NOT confer with monitor or executor before writing the verdict.

Cross-check note: my BLOCKING finding **contradicts** the executor's `A4: PASS` (session log evidence cites `<ModeSwitch> rendered in app.jsx:23`) — that citation predates `0c13d3f`, which both moved the ModeSwitch and broke `app.jsx:23`. The executor's A4 was true at the 8-commit close and stale after the 9th commit. The executor's `PROCEED-WITH-CAVEATS` verdict explicitly deferred the `:5180` smoke; the blocker lives precisely in that deferred gap.

---

## Appendix: commits audited

```
0c13d3f fix(shell): align Journey↔Shell chrome — logo, rail brand bar, pane parity, stable mode-switch  [post-close, not in session log]
3e143b8 docs(shell): README status — gen-UI + Tailwind landed
043ece4 test(shell): Vitest infra + first React↔BFF binding test (S-BS-18)
67492a0 chore(shell): reconcile demo-domain to clinical/Scribe (S-BS-17)
9e2ab93 feat(shell): integrate the Shell↔Journey mode-switch into the chrome
d5ad02b refactor(shell): promote verdict + calibration cards into the gen-UI registry
1c6a9a6 feat(shell): flag/severity editor + contract builder + KB picker
0e309c4 feat(shell): generative-UI tool-<name> component registry
efefaa8 build(shell): Tailwind v4 + @theme token bridge + shadcn foundation
```

## Appendix: files changed

```
37 files changed, 4145 insertions(+), 294 deletions(-) — all under apps/shell/
(no apps/bff/ · lithrim_bench/ · ../lithrim-backend edits; pyproject.toml unchanged)
build: npm run build clean (357.82 kB JS / 59.17 kB CSS)
test:  npm run test:run → 18 passed (3 files: registry / inputs / bff-binding)
```
