# PROOF — SHEPHERD-1c: judge roster-advance + pack-aware lens offer (honest-Δ live win)

**Date:** 2026-06-15 · **Branch:** `bench-salvage/ws6c-dspy` (LOCAL, not pushed) ·
**Commits:** `132f24c` (driver) → `a003863` (impl) → close.
**Verdict:** CLOSED PROCEED-WITH-CAVEATS. The deferred SHEPHERD-1b **A3 honest-loss now reproduces, live.**

## Claim

Closing the two pre-existing seams the SHEPHERD-1b A3 honest-loss surfaced makes *authoring a judge
in-pack* both **admissible** (no 422) and **rail-advancing** (the Judges step ticks to done) — so the
"rail ticks to done on Save" demo beat reproduces end-to-end against the live stack.

## What was wrong (corrected diagnosis — see §0 of the driver)

A read-fan-out (4 readers + 4 adversarial verifiers, all CONFIRMED) **overturned** the SHEPHERD-1b
handoff framing:

- **S-BS-153 was NOT a field-name mismatch.** Write and read both key on `eval_profile.judges`. The real
  mechanism is a **two-store split**: the per-role JudgeEditor save (`PUT /v1/judges/{role}`) wrote a
  *separate* global `JudgeConfig` store and never rostered onto the agent, so configuring a judge never
  ticked the rail (the rail reads the per-agent `eval_profile.judges`, written only by `PUT /v1/agent`).
- **S-BS-154 (confirmed):** the JudgeEditor's offered `available_flags` were built from the import-time
  process-pack global `judge_metric.LENS_BY_ROLE` (the BFF boots `_core` → it offered
  `INTERNAL_INCONSISTENCY`/`UNSUPPORTED_ASSERTION`), while the admissibility gate checks the **per-request
  active workspace** pack (healthcare). A `_core` code offered under a healthcare workspace → the live
  SHEPHERD-1b `422 … ['INTERNAL_INCONSISTENCY']`.

## The fix (commit `a003863`)

- **W1 (S-BS-154), BFF-only:** new `_active_lens_by_role()` (lazy pack+workspace import, mirrors
  `_active_snapshot_codes`) → `pack.pack_lenses(get_active_workspace().pack)`. Rewired the offered lens
  (`_judge_summary`), the owner↔emit gate + 404 role guard (`_validate_judge_assignment`), and the GET
  `/v1/judges` role enumeration onto it. **`judge_metric.LENS_BY_ROLE` left BYTE-FROZEN** — `signals.py`
  byte-imports it as the withstands-gate default `lens_by_role`; making it lazy would change the moat's
  runtime scope-check (the adversarial verifier disqualified that). Snapshot defense-in-depth retained.
- **W2 (S-BS-153), user-locked Option A:** `PUT /v1/judges/{role}` gained an optional `agent` param; on
  save it idempotently adds `role` to that agent's `eval_profile.judges` via the **same audited**
  `put_agent_endpoint` path (active-agent-only; lens-edit never strips a roster). Shell `putJudge`/
  JudgeEditor pass the active agent; the existing `refreshJourney` loop re-derives the rail. `journey.js`
  `deriveSteps`/`isDone` **unchanged**.

## HARD GATE — fresh-critic fan-out (4 lenses), PASS 0-blocking

Moat + `tools.py` + `loop.py` (`_deny_non_lithrim`) + `judge_metric.LENS_BY_ROLE` byte-frozen (0 diff vs
`132f24c`); W1 confined to `app.py` (no council re-entry); roster-add idempotent + audited + active-agent
only; tests **non-vacuous in both directions** (verified by controlled revert). Critique:
`.devloop/sessions/critique-bench-salvage-SHEPHERD-1c-2026-06-15.md`. Suites green on cleared bytecode:
BFF `tests/test_shepherd1c_judge.py` 10/10, shell 29/29.

## A-LIVE (monitor, demo-clinical · healthcare workspace, $0) — HONEST WIN

Drove the live shell (:5180) + BFF (:8787, serving `a003863` via `--reload`). Started from the from-scratch
state: agent `eval-1`, rail **1/5 (Domain ✓, Judges = NOW)**, `getAgent('eval-1').eval_profile.judges = []`.

Sent "Author the first judge for this evaluation". The shepherd **led proactively** — read eval-1's state,
reasoned "domain bound (`clinical/1`) but empty judge roster → authoring the first judge is the right next
step", drove the 3rd pane ("Opened the Config panel", healthcare ontology: 23 flags), and rendered a
`risk_judge` JudgeEditor card.

| # | Claim | Live evidence |
|---|---|---|
| A1 | **W1 — in-pack lens offered (no `_core` leak)** | The "ASSIGN LENS (OWNED + EMITTED CODES)" toggles offered the **healthcare** lens — `FABRICATED_ALLERGY` (TIER_1), `MEDICATION_NOT_IN_TRANSCRIPT` (TIER_2), `MISSED_ESCALATION` (TIER_1), `SEVERITY_ESCALATION` (TIER_1), `WRONG_DOSAGE` — with by-construction examples. `INTERNAL_INCONSISTENCY`/`UNSUPPORTED_ASSERTION` **absent.** Also confirmed via API: `GET /v1/judges/risk_judge?agent=eval-1` → healthcare codes. |
| A2 | **W1 gate — no 422** | Assigned `MISSED_ESCALATION` (header → "+13 lines vs seed · 1 flag") and saved → card footer **"saved ✓ as rahul@local"**. The SHEPHERD-1b `422 INTERNAL_INCONSISTENCY` blocker is gone. |
| A3 | **W2 — roster-add (ground truth)** | `getAgent('eval-1').eval_profile.judges` → **`["risk_judge"]`** (the per-role save rostered it onto the active agent, audited via the rationale field). |
| A3 | **rail ticks to done** | SETUP JOURNEY **1/5 → 2/5**; **Judges → ✓ done**; shepherd advanced to **Ground truth = NOW**. The deferred demo beat reproduces. |

Proof screenshot captured (`ss_8211b0bzz`): rail at 2/5 with Judges ✓, card "saved ✓", healthcare ontology
in the Config pane.

## Honest caveats (no manufactured win)

- **S-BS-157 (low, NEW, cosmetic) — judge seed-prompt preview not pack-aware.** The "JUDGE PROMPT PREVIEW
  (CODES YOU MAY RAISE)" seed text still lists the generic `_core` codes (`UNSUPPORTED_ASSERTION`,
  `INTERNAL_INCONSISTENCY`) under a healthcare workspace. This is a **separate surface** from the (correct,
  healthcare) assignment toggles + the admissibility gate that W1 fixed — the functional path is
  pack-correct; the seed *preview text* is generic. Misleading in the UI; file for a follow-on (a parallel
  pack-awareness gap in the seed role-prompt builder, not the lens offer/gate).
- **S-BS-155 (low) — W1 scope:** the DELETE-judge / optimize / `_assemble_agent` 404 guards still read the
  process-global `LENS_BY_ROLE`. Correct today (healthcare roles == the `_core` trio); a future Pro pack
  with a different role set would 404 a valid active-pack role. Clean follow-on: fold them onto
  `_active_lens_by_role`.
- **S-BS-156 (low/med, PRE-EXISTING) — council↔pack snapshot drift:** two `tests/test_flag_crud.py`
  delete-guard tests fail at HEAD independent of this cycle (`PackConsistencyError`: the external healthcare
  pack declares taxonomy codes the frozen council's `KNOWN_TAXONOMY_CODES` lacks). Likely a
  `scripts/snapshot_taxonomy.py` re-snapshot of the external pack, not a code fix.
- The A-LIVE left `eval-1` with `risk_judge` rostered (the natural, audited result of the demo save) — a
  future from-scratch re-drive should reset `eval_profile.judges = []` first.

## Video capsule

Proof-capsule convention (LOCKED) = doc + zyng-narrated video. The doc + live screenshot are captured here;
the narrated walkthrough (mode-2 capture→narrate of the before→after rail tick) is produced via the zyng
pipeline on request (publishing is a permissioned step).
