# Handoff — `bench-salvage` → next session (2026-06-15, EVAL-FLOW)

> EVAL-FLOW closed PROCEED-WITH-CAVEATS via the full monitor loop run with **subagents**:
> S-BS-156 hygiene fix → scope recon (5-reader fan-out) → driver → **executor subagent** (plan-review
> approved by monitor, then implement test-first) → **HARD-GATE fresh-critic subagent** (CLEAN) →
> monitor 7-item audit (CLEAN). **The author→process loop now ticks Ground truth → Run, rail-faithfully.**

## What landed (branch `bench-salvage/ws6c-dspy`, LOCAL — NOT pushed)

**Pre-step — S-BS-156 CLOSED** (`684f0f4` + `3d38ebe`): `council_known_codes()` was `@lru_cache(maxsize=1)`
staleness across an in-process active-pack flip (NOT snapshot drift, as the prior handoff guessed).
Pack-keyed cache fixes it; moat byte-untouched. Opened **S-BS-158** (the broader module-level path-constant
import-freeze twin → the `LITHRIM_BENCH_PACK=healthcare` export requirement; memory `[[bench-test-env-pack-export]]`).

**EVAL-FLOW CLOSED PROCEED-WITH-CAVEATS** (`77bcb60..60618e0`, 6 commits, test-red-first, pathspec-only).
- **§0 fix (CONFIRMED):** the rail-predicate mismatch — `add_grounding_contract` writes
  `ontology.verification_contracts`, but `journey.js:39` checked `eval_profile.tools/grounding_checks`, so a
  saved contract never ticked Ground truth.
- **W1a (E-D1):** `deriveSteps` gains a 5th `contracts=[]` param; `isDone("Ground truth")` ORs
  `verification_contracts` (KEEPS the old clauses as a superset; pure). `app.jsx refreshJourney` fetches
  `getOntology` + threads contracts.
- **W1b (R1 honest-tick, monitor-pre-authorized):** a thin `POST /v1/grounding-contract` **reuses** the bound
  `ctx.put_grounding_contract` (the SAME audited write the chat tool uses; **zero new write logic**).
  `ContractBuilder` self-persists, firing `onResult` **only on a successful write** → the rail can never tick
  on an unsaved/failed contract. **No `eval_profile.tools` stuffing.**
- **W1c/W2b:** additive `loop.py` stanza prose (Judges→Ground-truth + Ground-truth→Run); `_deny_non_lithrim`
  byte-unchanged.
- **W2a (S-BS-69):** RunPanel's paid gate is the in-DOM `CostModal` (CDP-driveable); `window.confirm` gone.
- **MOAT byte-frozen:** `compliance_council.py` / `_apply_consensus` / `signals.py` / `judge_metric.LENS_BY_ROLE`
  + `tools.py` = 0 diff.

## Verification — CLEAN (both audit + fresh critic)
- **Gate 0 (env exported):** pytest **556p / 2 pre-existing S-BS-96 / 4 skip**; vitest **122p / 1 pre-existing
  S-BS-145** — 0-new both. ruff clean. RED→GREEN source-verified at the test commit.
- **Monitor 7-item:** CLEAN. **HARD-GATE fresh-critic** (cold, agent `ab1a4548`): **0 BLOCKING / 0 NB / 1 OQ**
  — the R1 honest tick verified real, moat 0-diff, A2/A3 non-vacuous. Critique:
  `.devloop/sessions/critique-bench-salvage-phaseEVAL-FLOW-2026-06-15.md`.

## Open seams (none block the close)
- **S-BS-159 (low)** — the live-chat shepherd emits the post-write FlagEditor, not the fill-in ContractBuilder
  card; surfacing it live needs an adapter map or a forbidden `tools.py` emit change. The SETUP_PARTS card
  self-persists honestly today. **Relevant to the A-LIVE re-drive:** drive the grounding-contract add via the
  setup-journey ContractBuilder card, not (only) the conversational `add_grounding_contract` tool.
- **S-BS-160 (low, the 1 OQ)** — the App fetch→tick e2e link isn't cleanly unit-testable (dynamic
  `import('./bff.js')` not mock-intercepted). Both ends covered (A1 persist + A2 predicate); the link is what the
  A-LIVE re-drive proves (honest-Δ).
- **S-BS-161 (low)** — `contract_type` not pre-validated at authoring (driver §4 DEFER).
- Carried: S-BS-155/157 (low), S-BS-145 (vitest titlebar), S-BS-96 (2 observation guards), S-BS-158.

## OWED — the A-LIVE PAID re-drive (the proof capsule)
The driver's A-LIVE step is the monitor's post-close job and is **owner-gated** (live BFF `:8787` + UI `:5180`
up via `make up`/`make health` — do NOT autostart — plus a ~$0.10–0.20 paid run the user authorizes). The beat:
from `eval-1` (judge rostered, Ground truth = NOW) the shepherd guides adding a grounding contract via the
ContractBuilder card → **Ground truth ticks** → guides a live/in_process paid run via RunPanel "Run now" →
in-DOM CostModal → verdict renders → **Run ticks**. Capture the proof capsule (PROOF doc + zyng video,
`[[proof-capsule-convention]]`), honest-Δ only — no verdict flip is promised.
**A-LIVE residue:** `eval-1` carries `risk_judge` rostered (+ whatever ground-truth state a prior drive left);
reset for a clean from-scratch drive if desired.

## Next moves (do NOT autostart — user steers)
1. **A-LIVE paid re-drive** of EVAL-FLOW (owner-gated services + cost) → the proof capsule. The honest finale.
2. **PROVIDER-1** — the env-BYOK frontend provider picker (the cheap open-core "use your own provider" cut; the
   dispatch seam is mostly solved, no secrets subsystem). Recon already done this session.
3. **SHEPHERD-2** — the teach-mode curriculum (`SPEC_ONBOARDING_JOURNEY`), ~4 cycles.
4. Cleanups: S-BS-158 (the broader import-freeze twin), S-BS-159 (live ContractBuilder surfacing), S-BS-155/157.

Resume: `/devloop-resume bench-salvage`; authoritative state in `streams.json current_phase` + this handoff +
the EVAL-FLOW session log + critique. Memory `[[shepherd-harness-direction]]`, `[[bench-test-env-pack-export]]`.
