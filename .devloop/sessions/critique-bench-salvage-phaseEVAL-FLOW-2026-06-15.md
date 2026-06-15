# Critique — bench-salvage phase EVAL-FLOW (HARD GATE, fresh critic)

**Cycle:** commits `77bcb60..60618e0` on `bench-salvage/ws6c-dspy`
**Critic:** fresh session (agent `ab1a4548d5c6c84a8`), cold read, no implementation context. Edited nothing; non-mutating git only.
**Date:** 2026-06-15

## VERDICT: 0 BLOCKING / 0 NON-BLOCKING / 1 OQ — **CLEAN** (clear to close)

## Gate 0 — deterministic (SUPREME) — PASS
Re-run from clean (env exported, per S-BS-158):
- **pytest 556 passed / 2 failed / 4 skipped** — the only 2 fails are the pre-existing S-BS-96 observation guards (`test_observation_pipeline.py`, untouched). 0-new.
- **vitest 122 passed / 1 failed** — the only fail is the pre-existing S-BS-145 `app.test.jsx` titlebar (untouched). 0-new.
- **ruff clean.** Tests-first verified at the SOURCE level: at the test commit `9e4b72c`, `journey.js` lacked the `contracts` param (A2/A4 RED), RunPanel still had `window.confirm` (A3 RED), and `POST /v1/grounding-contract` did not exist. RED→GREEN demonstrated, not asserted.

## The 4 questions (cold read of spec + diff)
1. **Surface fidelity — CLEAN.** `deriveSteps` 5th `contracts=[]` param (back-compat); `POST /v1/grounding-contract` shape; RunPanel in-DOM `CostModal` (no `window.confirm`). Every deviation is a documented E-D1..E-D5 decision or the R1-authorized mid-cycle route.
2. **Behavioral fidelity — CLEAN (all 3 chains close).**
   - **(a) Honest tick (R1):** the new route reuses the byte-stable `_put_grounding_contract` closure (its body is in NO diff hunk); `ContractBuilder.apply` `await`s the write and fires `onResult` ONLY inside the try after success; the catch never fires `onResult`. `captureSetup` → `onConfigSaved` → `refreshJourney` re-fetches the REAL ontology and re-derives. No manufactured path; no `eval_profile.tools` stuffing. Negative direction pinned (`inputs.test.jsx`: a 404 write does NOT fire onResult).
   - **(b)** predicate ORs `contracts` while KEEPING `tools`/`grounding_checks`; pure.
   - **(c)** paid run gated by the in-DOM modal (open/cancel → no run; confirm → one run; `window.confirm` never called).
3. **Out-of-scope intrusion — NONE.** All 13 files map to W1a/W1b/W1c/W2a/W2b/W3 + tests + session log. MOAT byte-frozen (0 diff lines): `compliance_council.py`, `signals.py`, `judge_metric.py LENS_BY_ROLE`, `_apply_consensus`. `tools.py` = 0 diff; `loop.py` = additive stanza prose only, `_deny_non_lithrim` not in the diff. The 3 replaced tests (2 `window.confirm` + 1 sync-onResult) were legitimately obsolete (asserted intentionally-removed behavior), each replaced by a stronger test of the new behavior. Not a hidden regression.
4. **Acceptance non-vacuity — CLEAN.** A2/A3 confirmed non-vacuous both directions (reverting W1a/W2a fails them); A1/A4/A5 verified green directly + non-vacuous.

## Honest-Δ check — PASS
The contract-tick is genuinely real: the rail ticks Ground truth only after a successful **audited** write to `ontology.verification_contracts` (the store the grade consumes), re-read from the server — never from card-local state, never via `eval_profile.tools`. No manufactured win. No verdict flip promised (spec §4); no paid run fired (deferred to the monitor's A-LIVE re-drive, correctly).

## Seams (all NON-BLOCKING, in the session log)
- **S-BS-159** (low) — the live-chat shepherd emits the post-write FlagEditor, not the fill-in ContractBuilder card; surfacing it live would need an adapter map or a forbidden `tools.py` emit change. The SETUP_PARTS card self-persists honestly today.
- **S-BS-160** (low, the 1 OQ) — the App-level fetch→tick e2e link is not cleanly unit-testable (dynamic `import('./bff.js')` isn't mock-intercepted); both ends are deterministically covered (A1 persist + A2 predicate), the App wire is a direct reviewable edit. Not reducible to a failing test in this harness → OQ, not BLOCKING. Covered by the monitor's A-LIVE re-drive.
- **S-BS-161** (low) — `contract_type` not pre-validated at authoring; explicit driver §4 DEFER.

## Recommendation
0 BLOCKING → clear to close. Proceed to the A-LIVE paid re-drive (honest-Δ proof capsule), services + cost owner-gated.
