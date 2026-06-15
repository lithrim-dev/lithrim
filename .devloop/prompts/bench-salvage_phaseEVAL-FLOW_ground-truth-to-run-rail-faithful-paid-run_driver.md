# EVAL-FLOW — driver (executor)

> The author→process loop's payoff, rail-faithful: from SHEPHERD-1c's end state (`eval-1`,
> judge rostered, rail **2/5, Ground truth = NOW**) the shepherd guides the SME through
> **Ground truth → Run**, so a real grounding contract ticks the Ground-truth step and a
> **live/in_process paid** eval run renders a verdict and ticks the Run step. Walking skeleton
> of "the shepherd shepherds you through running your eval."
>
> **User-locked decisions (AskUserQuestion 2026-06-15):** spine = **Ground-truth → Run
> (rail-faithful)**; run mode = **include a live/in_process paid run** (which pulls the in-DOM
> cost modal, S-BS-69, into scope so the gate is CDP-driveable for the A-LIVE re-drive).
>
> **Bundle ID:** `bench-salvage-phaseEVAL-FLOW-ground-truth-to-run-driver`
> **Version:** v1 · **Authored:** 2026-06-15 · **Last re-verified against code:** 2026-06-15 (monitor, §Phase 1a)
> **Hardness:** HARD GATE (fresh-critic) — touches the journey predicate + the paid-run gate + the live run surface.

---

## KICKOFF (paste this block into a fresh executor session)

```
You are the EXECUTOR for the .devloop/ cycle: bench-salvage phase EVAL-FLOW (ground-truth-to-run, rail-faithful, paid run).

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseEVAL-FLOW_ground-truth-to-run-rail-faithful-paid-run_driver.md  (this doc)
  3. The §1 pre-flight files, in order.

Then post your plan-review per EXECUTOR.md §"Plan-review (non-negotiable)", resolving E-D1..E-D5 (§3).
Do not write code until the monitor says "go".

Bundle ID: bench-salvage-phaseEVAL-FLOW-ground-truth-to-run-driver
Driver doc: .devloop/prompts/bench-salvage_phaseEVAL-FLOW_ground-truth-to-run-rail-faithful-paid-run_driver.md
```

---

## §0 — Verbatim evidence (diagnose-before-edit)

### The rail-predicate mismatch (CONFIRMED) — a saved grounding contract does NOT tick Ground truth today

The rail's Ground-truth predicate reads the **agent's `eval_profile`** (`tools` / `grounding_checks`):

```javascript
// apps/shell/src/journey.js:38-39  (isDone, pure over agentCfg.eval_profile)
case "Ground truth":
  return (ep.tools || []).length > 0 || (ep.grounding_checks || []).length > 0;
```

But the real grounding-contract authoring path writes to the **ontology's `verification_contracts`** — it
never touches `eval_profile.tools`/`grounding_checks`:

```python
# apps/bff/app.py:1794-1818  (_put_grounding_contract — bound by the add_grounding_contract tool)
entry = {"contract_type": contract_type, "flag_code": flag_code, "question": question,
         "params": params or {}, "version": version}
contracts = ontology.get("verification_contracts") or []
...
ontology["verification_contracts"] = contracts          # <-- writes the ONTOLOGY draft
put = put_ontology_endpoint(ontology=ontology, agent=ag_name, rationale=..., ...)   # audited
```

And the shepherd prompt already CLAIMS Ground truth completes on a verification contract:

```python
# apps/bff/agent/loop.py:158  (the SUPERSET stanza's step-completion criteria)
"    - Ground truth: at least one grounding/verification contract is attached "
```

**So: `add_grounding_contract` lands a real contract in `ontology.verification_contracts`, the grade consumes
it, the shepherd says it completes Ground truth — but the rail predicate checks a different store and never
ticks.** W1 reconciles this HONESTLY (the rail must read the same source the grade consumes — the ontology's
`verification_contracts`), NOT by stuffing `eval_profile.tools` to flip a UI step (a manufactured tick —
forbidden by honest-Δ). The reconciliation locus is **E-D1**.

### The run surface is built (the Run half is COMPOSE) — CONFIRMED

```python
# apps/bff/app.py:368  POST /v1/run-eval -> run_eval.run() ; scripts/run_eval.py:172 run() routes
#   grade_replay ($0) | grade_live (:8002, paid) | grade_inprocess (v2 authored trio, paid)
```
```jsx
// apps/shell/src/genui/RunPanel.jsx — renders votes + verdict + run-history; the paid gate is:
// :28  const COST_CONFIRM = ...        :57  if (m.paid && !window.confirm(COST_CONFIRM)) return;
```
`window.confirm` **freezes the renderer to CDP** (the browser-MCP confirm trap) so a paid run is NOT
driveable in the A-LIVE re-drive. The optimize path already uses an **in-DOM** modal
(`apps/shell/src/components/CostModal.jsx`). W2a swaps RunPanel onto it (S-BS-69).

### SEAM REACH — none of this touches the moat

Every cited symbol is the journey predicate / a shell card / the shepherd prompt prose / the run surface.
The wired grounding tool (`add_grounding_contract`, `tools.py:492/723`) is **reused as-is** (no `tools.py`
edit). NONE of W1–W4 touches `compliance_council.py`, `_apply_consensus`, `signals.py`,
`judge_metric.py:64 LENS_BY_ROLE`, or `_deny_non_lithrim`.

---

## 1. Pre-flight reading (ordered)

1. `apps/shell/src/journey.js` (whole; the rail predicate + `deriveSteps`) — the Ground-truth + Run ticks.
2. `apps/bff/app.py:1777-1818` (`_put_grounding_contract`) + `:368-473` (`run_eval` endpoint + council view).
3. `apps/bff/agent/tools.py:120-127` (schema), `:492-522` (handler), `:723-724` (registration) — the
   already-wired `add_grounding_contract` tool (reused, NOT edited).
4. `apps/shell/src/genui/RunPanel.jsx` (whole) + `apps/shell/src/components/CostModal.jsx` (the in-DOM modal
   to reuse) + `apps/shell/src/genui/ContractBuilder.jsx` (the card to wire).
5. `apps/bff/agent/loop.py:139-200` — the SUPERSET stanza (the additive prose surface) + `_deny_non_lithrim`
   (`:203`, BYTE-FROZEN — do not touch) + the one-step pacing hook.
6. `apps/shell/src/app.jsx` (`refreshJourney` + `onConfigSaved` wiring) + `apps/shell/src/panes.jsx`
   (`captureSetup`, the card→onConfigSaved signal path) — the re-derive hook to reuse.
7. `.devloop/prompts/bench-salvage_phaseSHEPHERD-1c_judge-roster-advance-and-pack-aware-lens_driver.md` —
   the immediately-prior driver; mirror its W1/W2/W3/W4 + guardrail shape.
8. `.devloop/sessions/HANDOFF_bench-salvage_SHEPHERD-1c_2026-06-15.md` — end state + carried seams
   (S-BS-155/157; A-LIVE residue: `eval-1` has `risk_judge` rostered, reset judges to baseline if re-driving from scratch).

> **Citation discipline:** re-verify every file:line above against current code before plan-review. The
> `app.jsx`/`panes.jsx` refresh-hook lines were grepped by the recon fan-out this session but not personally
> re-verified by the monitor — CONFIRM them on read; if drift, halt and surface (EXECUTOR.md §Citation drift).

---

## 2. Deliverables (file-by-file) — tests FIRST

1. **`apps/bff/tests` (BFF, debuglithrim) + `apps/shell/src/*.test.jsx` (vitest)** — the acceptance tests for
   A1–A5 (§5), written first, RED before any code. Network-free, fixture-based.

2. **W1a — Ground-truth rail reconciliation (E-D1).** Make a SAVED grounding contract honestly tick Ground
   truth. **Recommended (E-D1 option i):** the rail reads the ontology's `verification_contracts` for the
   active agent — `app.jsx` fetches it (or extends the existing agent/ontology fetch) and threads a
   contracts signal into `deriveSteps`; `journey.js` `isDone("Ground truth")` returns true when a
   verification contract exists for the agent's flags (KEEP the existing `tools`/`grounding_checks` OR-clause
   as a superset). Predicate stays PURE. (Alternative E-D1 option ii — mirror into `eval_profile.grounding_checks`
   server-side — is allowed if plan-review prefers a smaller shell change; pick ONE, justify.)

3. **W1b — wire `ContractBuilder` into the shepherd flow.** Emit `ContractBuilder.jsx` as a gen-UI part
   (mirror the FlagEditor card: form → preview → onResult → the bound `add_grounding_contract` → audited
   `_put_grounding_contract` → `onConfigSaved`/`refreshJourney`). No new tool — reuse `add_grounding_contract`.

4. **W1c — Judges→Ground-truth shepherd stanza** (`apps/bff/agent/loop.py`, the SUPERSET prose only). The
   shepherd reads state (judges rostered, no contract), proposes EXACTLY the grounding-contract step. Additive
   prose; one-step pacing preserved. **Do NOT touch `_deny_non_lithrim`.**

5. **W2a — in-DOM cost modal for RunPanel (S-BS-69).** Replace `RunPanel.jsx:57` `window.confirm(COST_CONFIRM)`
   with the in-DOM `CostModal` (reuse `apps/shell/src/components/CostModal.jsx`): paid run shows the modal;
   confirm → fires the run; cancel → aborts, no call. CDP-driveable + testable + a11y.

6. **W2b — Ground-truth→Run shepherd stanza + run drive.** Stanza guides "now run your eval" after the
   contract is attached. The live/in_process **paid** run is driven through the existing RunPanel "Run now"
   path → W2a modal → `POST /v1/run-eval` (live/in_process). The run record (`agent === activeAgent`) +
   `refreshJourney` ticks the Run step. Confirm `propose_live_run`/the run record round-trips (no new tool).

7. **W3 — refresh wiring** (make both ticks visible). Confirm the grounding-save AND the run-complete each
   trigger `refreshJourney`/`onConfigSaved` so Ground truth + Run visibly tick. Reuse the SHEPHERD-1c W3 path;
   wire minimally only if a card doesn't already emit the signal. No new re-derive mechanism.

---

## 3. Plan-review checkpoint (non-negotiable) — resolve these decisions

Post Understanding · file-by-file · test plan · risks · proposed deviations, and **resolve**:

- **E-D1 (load-bearing): Ground-truth tick reconciliation** — (i) rail predicate reads ontology
  `verification_contracts` [recommended: matches the grade's source + `loop.py:158`'s claim] vs (ii)
  `_put_grounding_contract` also mirrors into `eval_profile.grounding_checks` [smaller shell change, but
  conflates two stores]. Pick one; the manufactured-tick (stuff `eval_profile.tools`) is FORBIDDEN.
- **E-D2: ContractBuilder surface** — emit a gen-UI `tool-contract_builder` part (mirror FlagEditor)
  [recommended] vs an inline conversational propose.
- **E-D3: contract_type coaching depth** — minimal generic "add a verification contract for your flag"
  [recommended for the skeleton] vs a per-flag-type decision tree [defer to a follow-on / SHEPHERD-2].
- **E-D4: paid-run drive locus** — RunPanel "Run now" → in-DOM CostModal (the A-LIVE-driveable path)
  [recommended] vs the shepherd's `propose_live_run` tool. (W2a is required either way for CDP-drive.)
- **E-D5: carry or close S-BS-155 (3 remaining 404 guards on process-global `LENS_BY_ROLE`) + S-BS-157
  (judge seed-prompt preview lists `_core` codes)** — both low; recommend CARRY (out of EVAL-FLOW scope),
  re-verify they don't block the flow in plan-review.

Wait for "go" before writing code.

---

## 4. Scope guardrails — NOT in scope

- **Teach-mode curriculum** (concept cards / your-turn / reveal) — that's SHEPHERD-2; do not build.
- **contract_type pre-validation** (the handler accepts any `contract_type`, fails at grade time) — real
  seam, but DEFER; flag it, don't fix it here.
- **Verdict-delta / before-after visualization, A/B case grouping, eval-pack batch UI** — later cycles.
- **A live verdict FLIP/suppression as a promised outcome** — the skeleton demonstrates the LOOP (grounding
  ticks → paid run renders a verdict → Run ticks); a flip is a stretch, never promised (honest-Δ; memory
  `[[live-overfire-context-primed]]` warns it is hard to reproduce live).
- **`tools.py` edits / a new SDK-MCP tool** — `add_grounding_contract` is already wired; reuse it.
- **The moat** (`compliance_council.py`, `_apply_consensus`, `signals.py`, `judge_metric.py:64
  LENS_BY_ROLE`) + **`_deny_non_lithrim`** — byte-frozen. Zero diff.
- Drive-by prettier on `apps/shell` JSX (`[[shell-no-prettier-handcompact-jsx]]`), dep bumps, "while I was here".

If something feels load-bearing-but-not-listed, halt and surface it in plan-review.

---

## 5. Acceptance criteria (each a test written FIRST)

- **A1.** `add_grounding_contract` / `PUT` writes the contract to the active agent's ontology
  `verification_contracts` (idempotent on re-save by `flag_code`), emits an AuditRecord, and 404s on an
  unknown flag — test `apps/bff/tests/…::test_grounding_contract_persists_audited_and_404s` (BFF, debuglithrim).
- **A2.** `deriveSteps` flips **Ground truth** `done` once the chosen E-D1 source is non-empty, and stays
  `current`/not-done when empty (NON-VACUOUS both directions) — test `…journey*.test.jsx::test_ground_truth_ticks_on_contract`.
- **A3.** RunPanel's paid gate is the **in-DOM CostModal**, not `window.confirm`: confirm fires the run,
  cancel aborts with no `/v1/run-eval` call — test `…RunPanel*.test.jsx::test_paid_run_uses_indom_costmodal`.
- **A4.** `deriveSteps` flips **Run** `done` once a run record with `agent === activeAgent` exists
  (NON-VACUOUS) — test `…journey*.test.jsx::test_run_ticks_on_agent_run`.
- **A5.** Guard (unchanged): moat byte-frozen (`compliance_council.py`, `_apply_consensus`, `signals.py`),
  `tools.py` + `_deny_non_lithrim` byte-stable, `judge_metric.py LENS_BY_ROLE` untouched —
  test `tests/test_6bclean_seam_guard.py` (+ the existing guard trio) green, zero diff on those files.

### Diagnostic stats (NOT gates)
- The A-LIVE paid run's verdict + whether any finding was suppressed/flipped — reported in the PROOF capsule,
  honest-Δ; NOT a gate (no flip is promised).

---

## 6. Commit structure (atomic, pathspec-only, tests first)

1. `test(eval-flow): ground-truth→run rail-faithful acceptance — red`
2. `feat(eval-flow): rail ticks Ground truth on a saved grounding contract (E-D1)`  — W1a
3. `feat(eval-flow): wire ContractBuilder card + Judges→Ground-truth shepherd stanza`  — W1b + W1c
4. `feat(eval-flow): in-DOM cost modal for RunPanel paid runs (S-BS-69) + Ground-truth→Run stanza`  — W2a + W2b
5. `feat(eval-flow): refresh wiring so both steps visibly tick`  — W3 (fold into 2–4 if trivial)

Each body ends with: `Executed per bench-salvage-phaseEVAL-FLOW-ground-truth-to-run-driver by session-2026-06-15-N.`
plus the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer.

**Commit pathspec-only** (`git commit -m <msg> -- <files>`; never bare-commit — concurrent .devloop sessions
stage foreign files; `[[git-commit-pathspec-in-a-dirty-index]]`). Verify scope: `git diff <parent> HEAD --stat`.

---

## 7. Verification checklist (run before the session log)

- [ ] Acceptance tests written first + RED recorded; `test(...)` commit precedes its feature commits.
- [ ] A1–A5 PASS; tests NON-VACUOUS (fail on a controlled revert of the fix).
- [ ] Canonical `pytest -q` (debuglithrim, **`LITHRIM_BENCH_PACK=healthcare LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare` EXPORTED** — see note) + vitest green, 0-new-fail vs parent.
- [ ] `git diff <parent> HEAD --stat`: no file outside §2; moat + `tools.py` + `_deny_non_lithrim` + `LENS_BY_ROLE` zero-diff.
- [ ] No services autostarted (curl /health first); no push/publish/tags.
- [ ] Session log per `.devloop/templates/SESSION_LOG_TEMPLATE.json`.

> **Env note (load-bearing, from S-BS-156 close):** the canonical suite is GREEN only with
> `LITHRIM_BENCH_PACK=healthcare` **exported in the shell** (not just relying on conftest `setdefault` — the
> root `conftest.py` imports first under `_core` and freezes module-level path constants, S-BS-158). Always
> export it for the green-bar run.

---

## 8. First move
1. Read `.devloop/personas/EXECUTOR.md` end-to-end.
2. Read §1 pre-flight in order; re-verify the cited file:lines (halt on drift).
3. Post plan-review per §3 (resolve E-D1..E-D5). Wait for "go".

---

## 9. References
- Recon ledger: this cycle's `eval-flow-scope-recon` workflow (5-reader compose-vs-build fan-out, 2026-06-15).
- Prior driver: `.devloop/prompts/bench-salvage_phaseSHEPHERD-1c_judge-roster-advance-and-pack-aware-lens_driver.md`
- Prior handoff: `.devloop/sessions/HANDOFF_bench-salvage_SHEPHERD-1c_2026-06-15.md`
- Stream state: `.devloop/state/streams.json` (bench-salvage `current_phase`) + `STREAM_bench-salvage.md`
- Spec: `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` (the author→process loop) + `SPEC_ONBOARDING_JOURNEY` (rail).

## Hardness
- [x] **HARD GATE** — fresh-critic session required (touches the journey predicate + the paid-run gate + a
  live paid run). Trigger via `/devloop-critique bench-salvage EVAL-FLOW` (fresh context). 0 BLOCKING to close.

## A-LIVE (monitor, after close)
Re-drive demo-clinical: from `eval-1` (judge rostered, Ground truth = NOW) the shepherd guides adding a
grounding contract → **Ground truth ticks** → guides a live/in_process **paid** run (~$0.10–0.20, in-DOM
modal, confirm-gated) → verdict renders → **Run ticks**. Capture the proof capsule (PROOF doc + zyng video,
`[[proof-capsule-convention]]`), honest-Δ only. If a step does not reproduce, report the honest loss + a seam.
