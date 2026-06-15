# Handoff — `bench-salvage` → next session (2026-06-15, SHEPHERD-1b)

> SHEPHERD-1b closed PROCEED-WITH-CAVEATS via the full monitor loop: scope → driver → executor
> (plan-review then implement) → HARD-GATE fresh-critic → monitor A-LIVE re-drive → close. The two
> target seams are fixed + live-confirmed; the deferred demo beat is an **honest loss** that the
> live drive surfaced two pre-existing causes for.

## What landed (branch `bench-salvage/ws6c-dspy`, LOCAL — NOT pushed)

- **SHEPHERD-1b CLOSED PROCEED-WITH-CAVEATS** — made the shepherd lead *cleanly*.
  - **W1 (S-BS-149 closed)** — `apps/shell/src/app.jsx:265-267`: a `useEffect([agents])` that mirrors
    the BFF `_resolve_chat_agent` contract (`apps/bff/app.py:1479-1483`) on the initial-mount path —
    `activeAgent ∉ agents → agents[0]`, a valid one honored, empty unchanged. `setActiveAgent` only
    (no `sessionKey` bump → no CenterPane remount), idempotent. Rail + chat shepherd now converge on
    one agent.
  - **W2 (S-BS-150 closed)** — `apps/bff/agent/loop.py`: **W2a** foregrounded the one-step rule in
    `_SHEPHERD_STANZA` (SUPERSET preserved); **W2b** an **additive** turn-scoped `PreToolUse` pacing
    hook (`_pace_one_step`) capping the 7 step-proposing WRITE tools to 1/turn — composed **alongside**
    the **byte-unchanged** A-SAFE `_deny_non_lithrim` (registered first), fail-open-for-itself, counter
    resets per turn (`_build_options` is per-turn).
  - Commits: `da2a0a8` (driver+register) → `ec87e77`/`34dda18`/`35add13`/`593395e` (impl+tests) →
    `37927d2` (fresh-critic critique) → `f3cb4c6` (S-BS-152 renumber) → docs/close commit.
  - **HARD-GATE fresh-critic PASS** (0 blocking / 1 NB / 3 OBS): independently re-ran guard trio (17) +
    canonical suite (2 pre-existing flakes / 542 passed); confirmed `tools.py` + `_deny_non_lithrim` +
    the moat byte-untouched, the pacing hook additive + fail-closed-safe, tests non-vacuous, honest-Δ
    clean. Critique: `.devloop/sessions/critique-bench-salvage-SHEPHERD-1b-2026-06-15.md`.

## A-LIVE :5181 re-drive (monitor, demo-clinical workspace, $0) — honest-Δ

- **A1 CONFIRMED LIVE** ✓ — in `demo-clinical` (agents `eval-1`+`snomed-demo`, no `ws0_default`) the
  rail showed a coherent "1/5, Domain ✓, Judges NOW" for `eval-1`, and the shepherd (asked "which
  agent am I setting up?") surfaced `Agent · eval-1`. Rail + shepherd converge on `eval-1` — the
  S-BS-149 fix holds. (Bonus: the A-SAFE deny hook fired gracefully on a stray `ToolSearch`; the
  CONV-UX-1 activity timeline rendered.)
- **A2 CONFIRMED LIVE** ✓ — a single message asking for **two** config steps produced exactly **one**
  config write + the verbalized rule "*one config step per turn … judges now, then the grounding
  contract on the next turn once you've saved*". Free reads flowed unthrottled. The S-BS-150 fix holds.
- **A3 DID NOT REPRODUCE** ✗ (honest loss) — saving the Agent roster committed (audited ✓) but the rail
  stayed "1/5"; ground truth (`getAgent('eval-1')`) showed `eval_profile.judges:[]`. A second path
  (judge lens-assign) returned `422 assigned flags outside taxonomy snapshot`. The rail derivation is
  *correct*; the break is two **pre-existing** gaps (not 1b regressions). No video captured (no honest
  "rail ticks" beat to film yet).

## Open seams (none block 1b)

- **S-BS-153 (med)** — rail↔authoring **field-mapping gap**: the Agent-roster Save commits but leaves
  `eval_profile.judges` (the rail's `Judges` predicate, `journey.js` `isDone`) empty — it writes a
  roster/`council_config`-shaped field the rail doesn't read, so the live save→advance never ticks
  Judges. CONFIRMED via `getAgent` post-save.
- **S-BS-154 (med)** — JudgeEditor **lens options ⊄ pack taxonomy snapshot**: the `risk_judge` card
  offers `INTERNAL_INCONSISTENCY`/`UNSUPPORTED_ASSERTION`, which the demo-clinical admissibility gate
  rejects (`422`). A judge can't be authored via the offered lenses in this pack. CONFIRMED via the 422.
- **S-BS-152 (low)** — pre-existing prompt-honesty: the `_SHEPHERD_STANZA` line "the Save IS the
  approval gate / never auto-commit" overstates the mechanism (authoring persists immediately-audited,
  `save_judge` at `app.py:1018-1019`). Reword to the honest 3-part gate (pacing + re-editability +
  audit trail). Filed by the fresh critic; NOT a 1b regression (line predates `da2a0a8`).
- Carried from before (unchanged): S-BS-147 (low, coalesce timeline labels), S-BS-148/151 (low,
  getMeta-mock / dead KB step-prompt), pre-existing S-BS-96 (2 observation flakes), S-BS-145
  (app.test.jsx titlebar).

## Next moves (do NOT autostart — user steers)

1. **SHEPHERD-1c** (recommended) — close **S-BS-153 + S-BS-154** so the live save→advance actually
   ticks the rail and a judge is authorable in-pack: (a) make the chat/Agent authoring write
   `eval_profile.judges` (or align the rail predicate to the field the authoring writes); (b) the
   JudgeEditor must offer only lens codes admissible in the active pack's taxonomy snapshot. Then the
   A3 "rail ticks to done" beat reproduces and the demo video becomes worth capturing. Lower priority:
   S-BS-152 (reword the stanza's gate line).
2. **SHEPHERD-2** — the teach-mode CURRICULUM (deferred from SHEPHERD-1).
3. **EVAL-FLOW** — the run-the-eval use-case the shepherd guides toward.
4. Owner-gated push (LOCAL SSOT — user keeping LOCAL, explicitly fine).

Resume: `/devloop-resume bench-salvage`; authoritative state in `streams.json` current_phase + the
SHEPHERD-1b session log + PROOF capsule; memory `[[shepherd-harness-direction]]`.
