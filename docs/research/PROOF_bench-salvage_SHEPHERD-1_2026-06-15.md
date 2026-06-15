# PROOF capsule — SHEPHERD-1: the agent-led onboarding "shepherd" harness (plan + approval gates)

> **Status: ATTESTED (monitor live re-drive, 2026-06-15) — PASS with two honest seams.**
> Code/test layer DONE (executor); the A-LIVE re-drive on `:5180` (workspace `demo-clinical`,
> a fresh "New evaluation") was run by the monitor: W1/W2/W4 confirmed live (strong), W3
> mechanism unit-tested (live save not driven — see the seam). HARD-GATE fresh-critic PASS
> (0 BLOCKING / 3 NB / 1 OQ). Honest-Δ honored: the AFTER reports what the drive actually
> showed, including two tuning seams (S-BS-149 rail↔agent sync; S-BS-150 over-eager pacing).

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

**Monitor A-LIVE re-drive, 2026-06-15 (`:5180`, `demo-clinical`, fresh "New evaluation"):**

1. **W1 — the rail is LIVE: ✅ CONFIRMED.** The rail rendered **"0 / 5"** with **Domain** carrying
   the **NOW pill** (`current`) and the rest `todo` — derived, not the static "4 / 6" all-`todo`.
   The empty state offered **"Start guided setup"** (primary) + **"Next: Domain"** (the computed
   next step). (Note: "N / 5" not "N / 6" — KB is optional and excluded from the required count;
   documented + tested, defensible.)
2. **W2 — the shepherd LEADS: ✅ CONFIRMED (the headline).** On "Start guided setup" the agent
   OPENED with *"Welcome! Let me first read the current state of your evaluation so I can guide you
   from the right starting point"*, then rendered an **explicit plan with per-step status** inline:
   `✅ Domain — bound to clinical/1, done · ☐ Judges — roster empty ← this is your next step ·
   ☐ Ground truth · ☐ KB (optional) · ☐ Run · ☐ Review`, and proactively led into authoring the
   first judge with an approval-gate editor card. The CONV-UX-1 activity timeline composed
   underneath. This is the Claude-Code "here's where you are / next step / proposed action —
   approve?" loop, live.
3. **W4 — shepherd entry: ✅ CONFIRMED** (per #1).
4. **W3 — save→advance: mechanism unit-tested; live save NOT driven.** The monitor did not click
   Save (would mutate `eval-1`'s roster without the user's OK, and the S-BS-149 sync gap below
   would prevent a clean live demo anyway). The flip is proven by the W5 test (deriveSteps
   before/after a JudgeEditor Save + `onConfigSaved`→`refreshJourney`).

### Honest seams the re-drive surfaced (neither a failure — tuning a walking skeleton)
- **S-BS-149 (med) — rail ↔ active-agent sync gap.** The left rail derives from the shell's
  blank "New evaluation" `activeAgent` (showed **0 / 5, Domain NOW**), while the chat shepherd
  resolved its own agent (the CONV-UX-1 `_resolve_chat_agent` fallback → `eval-1`) and correctly
  reported **Domain done**. They disagree on *which agent is being set up*. Fix: bind the rail to
  the agent the shepherd is configuring (or have "New evaluation" bind a concrete agent). This
  also gates a clean live W3 save→advance demo.
- **S-BS-150 (med) — over-eager pacing.** The W2 stanza says "propose **one** step at a time," but
  the agent chained many proposals in one turn (authored judges, edited the roster, edited a flag,
  loaded a case — all as save-pending proposals). It leads — arguably *too* hard. The
  one-step-and-wait gate is prompt-instructed, not mechanically enforced (the critic flagged the
  same); needs firmer enforcement (the natural SHEPHERD-1b scope, with S-BS-149).

**Verdict:** the vision is realized at walking-skeleton level — the agent owns a plan, leads the
next step, and gates with an editor. The two seams are the next iteration, surfaced honestly (no
manufactured "it leads perfectly" claim).

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
