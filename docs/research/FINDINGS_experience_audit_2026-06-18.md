# Findings — the hand-the-laptop experience audit (2026-06-18)

> Goal of this session (per owner): make the experience such that you hand a non-engineer the laptop,
> say "talk to Lithrim," and they hit the **aha moment**. This is a findings pass — **no code changes**.
> Method: a 4-agent code/doc audit (pitch context · batch+genui · refresh · convo polish) + a live
> conversational drive of the running shell (`localhost:5180`, BFF `clinverdict_clean`) via browser MCP.

## The aha moment we're aiming at (from the pitch context)
A clinician ("Sharif" persona — reads JSON, not a coder) handed the laptop should feel:
**"I — without writing code — made the AI's grade match MY clinical judgment, and I can prove WHY to an
auditor."** Concretely the experience must walk, in order:
1. read a recognizable clinical case (transcript + SOAP),
2. see a verdict that matches the clinician's judgment **for the right reason** — Case 9 → **reject** on
   `PROXY_MISATTRIBUTION` (dropped family cardiac hx), active findings shown, not a bare score,
3. trace verdict → flag → **source span** (hash-sealed) — "I can prove it",
4. the counter-beat: a *correct* note (Case 8) is **approved**, not over-flagged — "calibrated, not
   trigger-happy",
5. ideally the authoring beat: a plain-English rule (no code) produced the catch (the Calibrator litmus).

The aha **fails** if the verdict reads as a black-box number, if the source trace isn't clickable to
origin, or if the Case 8 over-flag answer is missing.

## How the story looks right now — honest read
The **single-case conversational spine is solid, honest, and A-SAFE** after this session's 3 commits
(`6b94c22` ingest→grade loop + conversational case-flow, `6dd3f18` A-LIVE, `89fd270` ToolSearch fix):
talk → list cases → open a case (transcript + SOAP + FHIR render) → run → verdict. The agent never
spends, never rounds up, opens the case it was asked for, and the timeline is clean (the ToolSearch
chip is gone). **But the experience does not yet LAND the aha** — there are five gaps between "it works"
and "it lands," ranked below by impact on the hand-the-laptop scenario.

---

## AHA-BLOCKER #1 — the ingested cases have NO $0 path to a verdict, by construction (HIGH)
*(Corrected 2026-06-18 after the owner switched to `clinverdict` and it made no difference.)*
The aha *is* the verdict (Case 9 → reject). Every conversational `run it` → **"no captured baseline …
$0 replay is unavailable for imported/live-only cases; run it live or in_process instead."** **This was
NOT a workspace problem** — `clinverdict` (the thesis workspace) returns the IDENTICAL error.

The real mechanism (CONFIRMED in code, not inferred):
- `$0 replay` reads `agent.dataset.baseline` (a fixed captured-baseline fixture on the agent config).
  For `healthcare_default` the dataset is `{baseline: null, mode: "in_process"}` — the ingested
  clinverdict cases ship **no baseline** (`scripts/run_eval.py:308` raises when `baseline is None`).
- **Running a grade does NOT capture a replayable baseline.** There is no writer that promotes a grade
  result back into `dataset.baseline` (grep: only `baseline_abspath()` reads it). An in_process/live
  grade persists a run-history *provenance blob* (auditable) — but it does not create a `$0` replay path.
- Therefore the ingested cases' verdict comes **only from a live / in_process PAID council run** (the
  agent is literally `mode: in_process`). The "Case 9 → reject, UI-validated" footage was a **paid
  in_process grade**, not a $0 replay.

So the pitch's *"replay a graded run, not a fresh paid call"* assumes the case **ships with a captured
baseline** (like the by-construction pack / ws0 cases). The *ingested* corpus does not.

**Two honest resolutions:**
1. **Live demo (today, ~cents):** the hero case's verdict is one **in_process paid run** — the human
   clicks "Run live (paid)" in the cost modal (the A-SAFE gate is itself part of the trust story), the
   council grades it live, Case 9 → reject lands. No code; one authorized paid click per take.
2. **Repeatable $0 (for zyng video capture + letting many people drive cost-free):** build a small
   **capture-baseline** step — grade a case once in_process, then promote that result blob to the agent's
   `dataset.baseline`, so every subsequent `run it` is a $0 replay of the captured verdict. This is the
   "run once → free replays" workflow; it is **NOT wired today** (a small, well-scoped feature — a persist
   + a config write, no engine edits). This is what would make the owner's expectation real.

My earlier "wrong workspace" framing was wrong; corrected here.

## AHA-BLOCKER #2 — the "Thinking…" tail makes every finished answer look frozen (HIGH, code)
`panes.jsx` has **no handler for the SSE `done` event** (loop.py emits it). The working indicator is tied
to the coarse `sending` flag (`inFlight = sending && isLast`), so after the answer fully streams the
spinner stays pinned underneath it — and with all tool steps done, its label falls back to the generic
**"Thinking…"**. The reader sees a complete answer with a "Thinking…" spinner still spinning. On a
hand-the-laptop demo this reads as a hang on *every* turn. It also hides the BYO-Claude `cost_label`
the backend computes. **Biggest single cadence bug.** (Confirmed in the live screenshots — the "Thinking…"
tail sat under finished turns.)
*Fix direction (describe-only):* add an `else if (ev.event === 'done')` branch that clears the per-turn
indicator (and optionally renders `cost_label` as a muted footer); decouple "turn finished" from the
network promise.

## YOUR QUESTION — batch run on cases + report as a genui card in the convo (MEDIUM, code)
**Today: PARTIAL — and the chat reaches for the wrong primitive.** When I asked *"evaluate all 10 cases
and show me a summary report"*, the agent called **`run_eval_pack`** — which batches over **agents**
(`pack_id, agents`), i.e. it would grade the agent's *one* dataset case N times, **not** the 10 ingested
cases. It honestly failed on no-baseline and surfaced the cost modal (A-SAFE held), so the mismatch never
mattered this time — but the primitive is wrong for "evaluate all 10 cases."

The **right** primitive already exists server-side: **`POST /v1/cases/grade`** (`grade_cases_endpoint`)
grades the whole ingested corpus (or a `case_ids` subset) and returns a **cohort matrix**
`{matrix: [{case_id, verdict, findings, votes, run_id}], summary: {n, graded, errors, verdicts}}`. It is
**not bound to any chat tool**, and there is **no cohort-report genui card** — the 10 registered cards are
single-verdict (`tool-verdict_card`) etc.; a `{matrix, summary}` payload would hit "Unsupported component."

**Smallest wiring (describe-only, ~2 thin additions, zero engine edits — mirrors the `list_cases`
pattern):**
- a **`grade_cases` chat tool** (SDK-free schema `{case_ids, agent}`, **no paid knob** — the bound op
  hardcodes `live=False`, the A-SAFE crux exactly like `run_eval`/`run_eval_pack`) wrapping
  `grade_cases_endpoint`; +1 `ToolContext` field; auto-covered by the A-SAFE test sweep.
- a **`CohortReport.jsx` genui card** + `tool-cohort_report` in `KNOWN_TOOLS` + a `cohort_part(result)`
  adapter builder — renders one row per case (case_id · verdict badge reusing VerdictCard's tone map ·
  findings count · run_id) + a summary header.

That closes both halves: one conversational move grades the corpus, one inline card renders the cohort
matrix. (Note: same baseline caveat as #1 — a $0 cohort needs captured baselines; otherwise it's a paid
batch the human authorizes.)

## YOUR QUESTION — page refresh clears everything (MEDIUM, code)
**Confirmed the "poof" live.** A reload **loses**: the entire chat history (in-memory `useState([])`,
no load path), the active case (resets to the *first* ingested case), the last run result / verdict
(Report goes blank), run status/error, pane layout/tab, composer draft, theme. It **keeps** (server-side,
re-fetched on mount): the active **workspace**, the agent list + configs + ontology + run history, the
ingested corpus, and a **`?agent=<name>` deep-link** is honored on load.

So the *data* survives; only the *session UI state* is lost. **Minimal rehydration (describe-only, no BFF
change):**
- **Tier 1 — URL params** (reuse the proven `?agent=` pattern): on switch, `history.replaceState` a
  `?agent=&case=&tab=` and read all three in the `useState` initializers. F5 restores agent + case +
  focused pane, and it's shareable/deep-linkable.
- **Tier 2 — localStorage** for theme + pane widths/open state.
- Chat history is the heavy one (no `GET /v1/chat`): accept the poof, or `sessionStorage` keyed by agent,
  or a server-side conversation store (out of scope). Recommend Tier 1 + 2 now; chat = accepted-poof for the
  demo (a fresh chat per session is fine — the *case + verdict + report* surviving is what matters).

## CONVO POLISH — the rest of the rough edges (MEDIUM/LOW, code)
Beyond the "Thinking…" tail (#2), the audit found:
- **Activity steps not deduped** (MEDIUM): a repeated tool shows e.g. "Listing the cases…" twice — reads
  as the system fumbling. *(Seen live: the first "show me the cases" rendered "Listing the cases" twice.)*
  Fix: coalesce adjacent identical steps.
- **One-step-per-turn pacing** (MEDIUM, by design): scoped to the 7 config-*write* tools — reads + $0
  runs are exempt, so a pure explore→run path is unimpeded (the likely demo path). Friction only when the
  human asks for multiple setup steps in one breath; the pacing-deny is **silent** to the human, so the
  pause reads as a stall. Fix: surface a friendly "I'll set the next one up after you save this," and let
  an explicit multi-step ask relax the cap.
- **Raw error UX** (MEDIUM): a loop/transport error renders as `⚠ <raw detail>` concatenated into the
  assistant bubble — no styled block, no retry. Fix: a distinct inline error block + human copy + retry.
- **Residual jargon on the live timeline** (MEDIUM): "Running a $0 replay", "Surfacing the cost-confirm",
  "Adding a grounding contract", "Reverting the judge", "Show the ontology ▸". Insider terms for a clinician.
  Fix: soften the timeline vocab ("Running a free preview", "Asking you to confirm the paid run", "Adding a
  fact-check"); keep precise terms in the artifact panels where they're earned.
- **Reasoning disclosure is non-deterministic** (LOW) + **"Start guided setup" fills-not-sends** (LOW,
  the chip fills the composer; first-timers may not know to press send).

---

## On the thesis A/B/C/D menu (analyzed, deferred — this session is experience-focused)
Per your instruction I **analyzed** the orientation prompt for context, not to execute it. The strategic
state it encodes: the value prop is **reframed** off "LLM judges can't be trusted / our floor beats them"
(model-curve-exposed — frontier+grounded judges hit 94–97% physician agreement) **onto** "liability +
auditability + a clinician owns *correct*" (the durable story). Proven: ClinVerdict → bench (10 cases),
Case 9 WARN→reject for the right reason, WS-2 codes registered (local). Gaps: the over-flag-vs-blindness
disentanglement on a frontier grounded judge across all 10 (Front B, the paper's core) is **not done**;
claim 6 (regulatory mandate) has zero coverage and is now load-bearing for the *services* story; the
non-engineer **authoring** beat (the Calibrator litmus) is unverified in the shell.

Recommended research default remains **B** (scale to all 10 + ab_harness + the honest over-flag-vs-blindness
measurement) — it absorbs A's useful half (SD-2/SD-3 omission scorer) and stress-tests the biggest risk.
**But for THIS session's goal (the aha experience), the sequence is the five gaps above, not B.** Await
your pick before executing either track.

## Recommended experience sequence (to land the aha — describe-only, your call to greenlight)
1. **#1 workspace/baseline** (setup, no code) — demo on `clinverdict` (graded verdicts) or capture
   baselines for `clinverdict_clean`, so `run it` replays Case 9 → **reject** at $0. *Without this, nothing
   below matters — the aha is the verdict.*
2. **#2 the "Thinking…" tail** (small code) — the highest-leverage polish; every turn currently looks frozen.
3. **batch + cohort card** (your Q; medium code) — "evaluate all 10 → a cohort report card" is the
   "100% of outputs, not a sample" pitch beat made visible.
4. **refresh rehydration Tier 1+2** (medium code) — so a mid-demo F5 doesn't wipe the case/verdict/report.
5. **polish sweep** (activity dedup · friendly pacing-deny · styled errors · de-jargon timeline).

## Evidence anchors
- Live: `run it` on `clinverdict_05` (and the 10-case batch) → "no captured baseline" → cost modal (×3);
  the "Thinking…" tail under finished turns; "Listing the cases" rendered twice; refresh → empty chat +
  blank Report + active-case reset; workspace/agent survived.
- Code: `POST /v1/cases/grade` (`grade_cases_endpoint`) returns `{matrix, summary}` but is unbound to
  `_TOOL_SPECS`; `run_eval_pack` batches over agents; `KNOWN_TOOLS` has no cohort card; `panes.jsx` onEvent
  has no `done` branch; chat/activeCase/runResult are in-memory `useState`; `?agent=` is the only URL param.
- Workspaces: `clinverdict` (2026-06-17, graded) vs `clinverdict_clean` (2026-06-18, fresh ingest, no
  baselines) — the demo is on the latter.
