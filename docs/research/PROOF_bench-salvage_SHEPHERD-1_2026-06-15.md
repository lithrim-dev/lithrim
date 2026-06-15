# PROOF capsule — SHEPHERD-1: the agent-led onboarding "shepherd" harness (plan + approval gates)

> **Status: STUB — code/test layer DONE; the A-LIVE re-drive (A1–A4) is the MONITOR's.**
> Authored by the executor (session-2026-06-15-1) per the hand-back contract: the BEFORE
> + the two decisions used are recorded now; the AFTER (live `:5180` captures) is left for
> the monitor's live re-drive. Honest-Δ binds: if the shepherd does not actually lead
> end-to-end live, the AFTER must say so.

Bundle: `bench-salvage-phaseSHEPHERD-1-agent-led-onboarding-harness-driver`
Branch: `bench-salvage/ws6c-dspy` · parent `5b966ff` · commits `95c427e..725b2e7` (NOT pushed)

---

## The claim (honest)

The conversational onboarding shifts from **reactive** (a stateless-per-turn agent that
answers one message; a static all-`todo` rail with a literal "4 / 6") to **proactive**: a
LIVE plan surface (the rail derives from real config + run state), a plan-aware shepherd
prompt that leads the next incomplete step, and an approval-gated save→advance loop (the
human's Save flips the step done and the agent proposes the next one).

This is mostly COMPOSE: the 16 SDK-MCP tools, the per-tool audit, the save-pending editor
cards, the history-replay memory (S-BS-87), and the 3-pane shell are all reused. NET-NEW =
the rail wired to state (`journey.js`), the shepherd stanza, and the save→advance callback.

---

## BEFORE (the reactive baseline — verifiable at `5b966ff`)

- **Rail:** `apps/shell/src/data.jsx` `STEPS` is hardcoded all-`state: "todo"`; `panes.jsx`
  rendered it static with a literal `<span>4 / 6</span>`. No live data source — `LeftRail`
  received only `agents`/`activeAgent`; nothing fetched `GET /v1/agent` or `GET /v1/runs`.
- **Agent:** `apps/bff/agent/loop.py` `_system_prompt` = base persona + HONESTY contract +
  active-agent naming. Operator posture: it answers what is asked; it does not know a journey
  order and does not lead the next step.
- **Empty state:** 3 static generic chips ("Create a risk judge / Add a safety flag / Run a
  $0 replay") that fill the composer.

---

## The two monitor decisions used (recorded for honest-Δ)

### Review-step signal — **runResult (the distinct-beat option), as the monitor preferred.**
- **Run** done ⟺ ≥1 run for the active agent (`GET /v1/runs`, client-filtered by
  `row.agent === activeAgent`).
- **Review** `current` when Run is done but no run result is loaded/viewed yet; **Review
  done ⟺ `runResult` is non-null** (the user is looking at a verdict). This makes Review a
  genuinely distinct guided beat past Run, not a duplicate. Threading `runResult` into
  `deriveSteps` was clean (App already owns `runResult` state), so the approved fallback
  (Review ⟺ ≥1 run) was NOT needed.

### W3 save→advance event — **a new minimal callback (no existing reload path existed).**
- The rail had NO live data source before W1, so there was nothing to "re-run." W1 introduced
  `refreshJourney()` (fetch `getAgent(activeAgent)` + `getRuns()`) into App. W3 is the
  smallest possible callback: the editor cards (Agent/Judge/Flag) ALREADY call `onResult` on
  a successful audited Save, and `CenterPane`'s existing `captureSetup` is that signal — it
  now also fires a new `onConfigSaved` prop, bubbled `App → CenterPane`, wired to
  `refreshJourney`. The frozen card components are untouched (they already emit `onResult`);
  no new GenUI card type; no server-side session state.

---

## AFTER (the live plan + proactive shepherd + approval-gated advance)

> **OWED to the MONITOR (A-LIVE re-drive of `:5180`).** Fill with screenshots:
> 1. A fresh eval (empty agent) → rail shows **Domain `current` (NOW pill) + 0 / 5**, the
>    empty state offers **"Start guided setup"** + **"Next: Domain"**.
> 2. The shepherd OPENS with guidance and leads Domain → … (proactive, not pure reaction).
> 3. Proposing a judge renders a **save-pending JudgeEditor** (no auto-commit); on **Save**,
>    the rail's **Judges** flips **done** and the count advances; the shepherd proposes the
>    next step.
> 4. Non-onboarding chat on a fully-configured agent is behavior-unchanged (operator posture).
>
> Honest-Δ: if the shepherd does not lead end-to-end (e.g. it stalls or skips a gate), say so.

---

## Code/test evidence (DONE — the executor's layer)

- **W1** `apps/shell/src/journey.js` `deriveSteps` (pure) + `panes.jsx` LeftRail wired +
  `app.jsx` `refreshJourney`. The active-step literal is **`"current"`** (matches the existing
  `.step.current` NOW-pill CSS, styles.css:254).
- **W2** `apps/bff/agent/loop.py` `_SHEPHERD_STANZA` appended in `_system_prompt` — a SUPERSET;
  `_build_options` / the A-SAFE deny-hook byte-identical.
- **W3** `onConfigSaved` callback (App → CenterPane → `captureSetup` → `refreshJourney`).
- **W4** shepherd-aware empty state ("Start guided setup" + "Next: <step>", fill-only).
- **W5** `journey.test.jsx` (15-of-15 with `panes.shepherd.test.jsx`) + `tests/test_shepherd.py`
  (4/4): the derivation ladder, the rail render ('4 / 6' literal gone), the save→advance flip,
  the prompt's journey-order + next-step + back-compat invariants.
- **Moat:** `compliance_council.py` / `signals.py` / `tools.py` zero-diff vs `5b966ff`; the
  guard trio (`test_6bclean_seam_guard.py` + `test_6bclean_attestation.py`) green.
