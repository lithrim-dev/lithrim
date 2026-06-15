# Handoff — `bench-salvage` → next session (2026-06-15, SHEPHERD-1c)

> SHEPHERD-1c closed PROCEED-WITH-CAVEATS via the full monitor loop: scope (read-fan-out workflow) →
> driver → executor (workflow: plan-review then implement) → HARD-GATE fresh-critic (4-lens workflow
> fan-out) → monitor A-LIVE re-drive → close. **The SHEPHERD-1b A3 honest-loss now reproduces as an
> honest WIN — live.**

## What landed (branch `bench-salvage/ws6c-dspy`, LOCAL — NOT pushed)

- **SHEPHERD-1c CLOSED PROCEED-WITH-CAVEATS** — authoring a judge in-pack is now admissible (no 422) AND
  ticks the rail.
  - **Scope correction first.** A read-fan-out (4 readers + 4 adversarial verifiers, all CONFIRMED)
    **overturned** the 1b handoff: **S-BS-153 is a two-store split**, not a field-name mismatch — write and
    read both key on `eval_profile.judges`; the per-role JudgeEditor save (`PUT /v1/judges/{role}`) wrote a
    *separate* `JudgeConfig` store and never rostered.
  - **W1 (S-BS-154 closed)** — `apps/bff/app.py`: new `_active_lens_by_role()` (lazy pack+workspace import,
    mirrors `_active_snapshot_codes`) → `pack.pack_lenses(get_active_workspace().pack)`. Rewired the offered
    lens (`_judge_summary`), the owner↔emit gate + 404 role guard (`_validate_judge_assignment`), and the
    GET `/v1/judges` role enumeration onto it. **`judge_metric.LENS_BY_ROLE` left BYTE-FROZEN** (signals.py
    byte-imports it as the withstands-gate default — making it lazy was disqualified). Snapshot
    defense-in-depth retained.
  - **W2 (S-BS-153 closed, user-locked Option A)** — `PUT /v1/judges/{role}` gained an optional `agent`
    param; on save it idempotently rosters `role` onto that agent's `eval_profile.judges` via the **same
    audited** `put_agent_endpoint`. Shell `putJudge`/JudgeEditor pass the active agent; the existing
    `refreshJourney` loop re-derives the rail. `journey.js` unchanged.
  - Commits: `132f24c` (driver) → `a003863` (impl, 8 files). **HARD-GATE fresh-critic fan-out (4 lenses)
    PASS 0-blocking**: moat + `tools.py` + `loop.py`(`_deny_non_lithrim`) + `judge_metric.LENS_BY_ROLE`
    byte-frozen (0 diff), W1 confined to `app.py`, tests non-vacuous both directions (controlled revert).
    Critique: `.devloop/sessions/critique-bench-salvage-SHEPHERD-1c-2026-06-15.md`.

## A-LIVE :5180 re-drive (monitor, demo-clinical · healthcare, $0) — HONEST WIN

From the from-scratch state (eval-1, rail 1/5, Judges = NOW, `judges:[]`), sent "Author the first judge".
The shepherd led proactively (read state → reasoned → drove the 3rd pane "Opened the Config panel" →
rendered the `risk_judge` card).

- **W1 CONFIRMED LIVE** ✓ — the "ASSIGN LENS" toggles offered the **healthcare** lens (`FABRICATED_ALLERGY`,
  `MEDICATION_NOT_IN_TRANSCRIPT`, `MISSED_ESCALATION`, `SEVERITY_ESCALATION`, `WRONG_DOSAGE`) with
  by-construction examples — **no `_core` leak**. Assigning `MISSED_ESCALATION` + Save → **"saved ✓"**, no
  422 (the 1b blocker is gone).
- **W2 CONFIRMED LIVE** ✓ — `getAgent('eval-1').eval_profile.judges` → **`["risk_judge"]`** (the per-role
  save rostered it, audited).
- **A3 CONFIRMED LIVE** ✓ — rail ticked **1/5 → 2/5**, Judges → ✓ done, advanced to **Ground truth = NOW**.
  The deferred demo beat reproduces. Proof screenshot `ss_8211b0bzz`. PROOF:
  `docs/research/PROOF_bench-salvage_SHEPHERD-1c_2026-06-15.md`.

## Open seams (none block 1c)

- **S-BS-157 (low, NEW, cosmetic)** — the judge PROMPT PREVIEW seed text ("CODES YOU MAY RAISE") still lists
  the generic `_core` codes (`UNSUPPORTED_ASSERTION`, `INTERNAL_INCONSISTENCY`) under a healthcare
  workspace. A **separate surface** from the (correct, healthcare) assignment toggles + gate W1 fixed — the
  functional path is pack-correct; the seed *preview text* is generic. A parallel pack-awareness gap in the
  seed role-prompt builder. Misleading in the UI.
- **S-BS-155 (low)** — W1 scope: the DELETE-judge (`app.py:1104`), optimize (`:1136`), and `_assemble_agent`
  add_judge (`:1757`) 404 guards still read the process-global `LENS_BY_ROLE`. Correct today (healthcare
  roles == the `_core` trio); a future Pro pack with a different role set would 404 a valid role. Fold them
  onto `_active_lens_by_role`.
- **S-BS-156 (low-med, PRE-EXISTING)** — `tests/test_flag_crud.py` 2 delete-guard tests fail at HEAD
  (`PackConsistencyError`: the external healthcare pack declares taxonomy codes the frozen council's
  `KNOWN_TAXONOMY_CODES` lacks — council↔pack snapshot drift). Likely a `scripts/snapshot_taxonomy.py`
  re-snapshot of the external pack.
- Carried (unchanged): S-BS-152 (low, reword the stanza's "approval gate" line), S-BS-147/148/151 (low),
  S-BS-96 (2 observation flakes), S-BS-145 (app.test.jsx titlebar).
- **A-LIVE residue:** the demo left `eval-1` with `risk_judge` rostered (the natural audited result) — a
  future from-scratch re-drive should reset `eval_profile.judges = []` first.

## Process note (recorded, not a defect)

The HARD-GATE was run as a **workflow review fan-out on the shared working tree**; two critics did in-place
revert experiments + a concurrent .devloop session left foreign `.devloop/*` changes. The monitor
independently re-verified the delivered state (frozen 0-diff, no revert markers, W1/W2 logic present,
cleared bytecode, suites green) and committed **pathspec-only** (8 files; foreign `.devloop/*` NOT swept in).
Lesson: future review fan-outs that need reverts should use isolated worktrees, not the shared tree.

## Next moves (do NOT autostart — user steers)

1. **SHEPHERD-2** — the teach-mode CURRICULUM (concept cards / "your turn" / reveal / `capabilities_v1.json`)
   from the LOCKED `SPEC_ONBOARDING_JOURNEY`; the tutorial layer (SHEPHERD-1/1b/1c were operate-mode only).
2. **EVAL-FLOW** — the run-the-eval use-case the shepherd guides toward. eval-1 now has a judge rostered and
   the rail at **Ground truth = NOW** — a natural continuation.
3. Cleanups: **S-BS-157** (make the judge seed-prompt preview pack-aware), **S-BS-155** (fold the 3 remaining
   404 guards), **S-BS-156** (re-snapshot the external healthcare pack), **S-BS-152** (reword the gate line).
4. Optional: produce the **SHEPHERD-1c zyng-narrated video capsule** (the A3 beat is now worth filming —
   publishing is permissioned).
5. Owner-gated push (LOCAL SSOT — user keeping LOCAL, explicitly fine).

Resume: `/devloop-resume bench-salvage`; authoritative state in `streams.json` current_phase + the
SHEPHERD-1c session log + PROOF capsule; memory `[[shepherd-harness-direction]]`.
