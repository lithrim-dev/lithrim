# HANDOFF — Lithrim shell "Journey" (Acts 1–4), 2026-06-03

> **Purpose of this doc:** give a *fresh session* everything it needs to run `/ux-copy` and
> `/design-critique` on the activation journey — grounded in the product thesis, the current build,
> and the design bar the founder has set. Read this top-to-bottom, then read
> [`KICKOFF_ux_copy_design_critique_2026-06-03.md`](KICKOFF_ux_copy_design_critique_2026-06-03.md).
>
> **State:** the journey is rebuilt end-to-end and **Act 2 actually executes the real engine**
> (BFF → council). Acts 3 & 4 are still presentational props. Everything from this session is
> **uncommitted**. The BFF + dev server must be running for the real path (see §4).

---

## 1. The product thesis (the lens for both critiques)

**Lithrim Bench is a calibration trainer, not a demo. The product experience *is* the value
proposition.** You hand a technical buyer a real agent exchange, let them watch a confident LLM-judge
be *wrong*, then let them *make the judges right* with their own hands — and they understand the
product because they just did it.

Load-bearing beliefs (do not weaken without founder say-so — `CLAUDE.md`, `docs/PAPER_OUTLINE.md`):
- **Labels are true by construction.** Cases are generated with a known injected defect, so the
  correct verdict is *known*. You score the judge against ground truth, not another model's opinion
  (non-circular). This is what makes a number trustworthy.
- **A deterministic, tool-grounded floor can overrule a confident-but-wrong judge.** The judge sees
  only the transcript; the floor reads the *record / chart / spec*. That's the moat — not "a better
  judge."
- **You cannot prompt your way to a reliable judge** — measured: a "stricter" prompt caught *less*
  (non-monotonic). The floor is the reliable lever. (`docs/research/RUN_calib_progression_2026-06-03`.)
- **Judges are unstable** — the same case flips PASS↔BLOCK between runs (risk_judge did, live). The
  bench exists to expose that.

The journey's emotional/intellectual arc must be **aha → conviction → ownership**:
- **Act 2 (aha):** "your confident, unanimous AI is wrong."
- **Act 3 (conviction / mastery):** "you make it right, measured against known truth — and prove it."
- **Act 4 (ownership):** "now it's yours — your agents, your data, your evalpack."

GTM frame (memory `gtm-launch-and-journey-thesis`, `product-direction-shell-strangler-fig-2026-06`):
open-core + premium annual license + FDE; **no US-hosted surface** (trust wedge); BYOK, local,
airgapped; positioned vs Composo as *by-construction + tool-grounded floor*, NOT "a better judge."

## 2. The founder's design bar (what every prior critique converged on)

These are the exact bars the founder pushed for, in order — the rubric for `/design-critique`:
1. **It must STOP a blind-clicker.** An exec arrow-keying through must hit a moment that arrests them
   (the rug-pull: "3 judges, confident, unanimous — and *wrong*"). Staging, timing, one hook per act.
2. **It must be EVIDENT, not buried.** The value can't live in a tab the user never opens; the loop
   has to be *walked* in the center conversation.
3. **It must be BELIEVABLE + INTELLECTUAL.** Numbers can't be floating props ("1.00") — they must be
   grounded in countable cases vs known truth, with the methodology shown. Something a technical
   leader can *defend to their team* as "the only rigorous way out."
4. **The USER must be the hero**, not the tool. "I tuned it, I re-ran, my accuracy climbed, I iterate."
5. **It must be THEIR problem.** Framed as *any* agent (support, code, RAG, scribe) — not a clinical
   toy. ("the example is a clinical scribe; the method is your agent, your eval.")
6. **It must not be HANDWAVY.** The decisive fix: the journey must *actually run the engine* and show
   real output, not narrate hardcoded strings. (Act 2 now does; 3 & 4 don't yet — §3.)
7. **Conversational-first.** The bot creates tension with timing; reveals auto-scroll into view.

## 3. The journey today — Act by Act (files in §5)

Four acts, left-rail nav + keyboard (←/→). Center = the conversation (the blind-clicker's path);
right pane = the "drawer" (detail/evidence). `JourneyApp.jsx` owns phase + the verify/calib state +
the BFF fetches + the auto-scroll-to-latest-beat.

- **Act 1 · First contact** (`jp1.jsx`) — install, pick agent (Clinical Scribe), BYOK key. Static.
- **Act 2 · The reveal** (`jp2.jsx`) — **REAL.** The Verify button calls the BFF (`/v1/run-eval`),
  renders the **real verdict + per-judge votes + verbatim reasoning + the real graded note**
  (`/v1/case`). Provenance shown ("real grade · replay · $0"). A **"Run live"** button does a fresh
  paid in-process Azure council call (`in_process:true`). Staging: verdict lands BIG → held beat →
  timed reversal ("it's calling the patient's *real* history *fabricated*") → cliffhanger. Falls back
  to bundled fixtures (`EXCHANGE`/`JUDGES` in `journeyData.js`) if the BFF is down.
- **Act 3 · Calibration** (`jp3.jsx`) — **PROP (not yet wired).** "You make the judges right." A
  grounded-feeling scorecard *"Judge accuracy vs ground truth: 3/6"* with a by-construction
  methodology callout, the council's visible errors (2 false-blocks + 1 miss), the prompt-trap
  finding, then the user applies floors (record-grounding, dosage-grounding) and the number climbs
  3/6 → 5/6 → 6/6 (hero loop, `calibStep`). The right drawer has 4 tabs: The pair / Prompt vs floor /
  Generate·JUTE (the real generator prompt + run) / Floor contracts. **All numbers are hardcoded in
  `CALIB`/`PROGRESSION`/`JUTE_RUN` in `journeyData.js`** — the grade record already carries the real
  `grounded` floor result to wire this to (the open task).
- **Act 4 · Own it** (`jp4.jsx`) — **PROP/semi.** Ownership arc: your judges → your agent via the SDK
  (`capture.ts`) → a session from "your stream" (the real case-10 audio + verdict + 8-link audit
  chain) → promote to golden set + regression suite → defensible eval → Pro. The session is a real
  recording but the surrounding numbers (24 golden / 60 regression) are props.

**The bot's "what went wrong / how it improved" notes** (`BOT_HINTS`) cite real run files
(`logged · RUN_calib_progression_2026-06-03`).

## 4. How to run it (REQUIRED for the real path; else Act 2 falls back to fixtures)

```bash
# 1. dev server (the shell)  → http://localhost:5180
cd apps/shell && npm run dev          # vite, port 5180

# 2. the BFF (the engine API the journey calls) → http://localhost:8787
#    needs the `debuglithrim` pyenv + Azure creds in env for in_process/live grades
cd <repo-root>
export $(grep -E '^AZURE_OPENAI_' ../lithrim-backend/.env | sed 's/ #.*//' | xargs)  # see note
export LITHRIM_LLM_PROVIDER=azure COMPLIANCE_COUNCIL_VERSION=v2 PYENV_VERSION=debuglithrim
uvicorn app:app --app-dir apps/bff --port 8787
```
- **BFF endpoints:** `POST /v1/run-eval {agent, live, in_process}` (replay `$0` | `:8002` live |
  in-process Azure live), `GET /v1/case?agent=`, `GET /v1/corpus`, `GET /v1/ontology`, `PUT /v1/ontology`.
- **Tell-tale of a dead BFF:** the journey shows the old "3 judges unanimous conf 1.0" fixture
  instead of "real grade · replay · $0". (This bit us — the BFF was reaped between turns; run it
  with a persistent process, not `nohup &` inside a one-shot shell.)
- **Driving the founder's own browser:** use the `Claude_in_Chrome` MCP (`tabs_context_mcp` →
  `navigate` → `computer`/`browser_batch`), NOT the `Claude_Preview` MCP — the preview is a *separate
  session* the founder can't see. That mismatch is why "my reveal looked different" came up.

## 5. Files

| What | Path |
|---|---|
| Journey shell (compose, state, BFF fetch, auto-scroll) | `apps/shell/src/journey/JourneyApp.jsx` |
| Act 1 / 2 / 3 / 4 | `apps/shell/src/journey/jp1.jsx … jp4.jsx` |
| All journey copy + data (props live here) | `apps/shell/src/journey/journeyData.js` |
| Shared chrome (AgentMsg, rail, statusbar) | `apps/shell/src/journey/chrome.jsx` |
| The BFF (engine API) | `apps/bff/app.py` |
| The real engine | `lithrim_bench/harness/{grade,grounding,ontology,report}.py`, `runtime/council/` |
| `dosage_grounding` floor (committed + tests) | `lithrim_bench/verification/tools.py`, `harness/grounding.py`, `tests/verification/test_dosage_floor.py` |
| JUTE generator (DSPy, bench-gated) | worktree `.claude/worktrees/agent-adefc36309f77ed1b/experiments/dspy_council_smoke/jute_dspy_smoke.py` |
| Specs | `docs/specs/SPEC_CALIBRATION_TRAINER.md`, `SPEC_PRODUCT_SHELL.md`, `docs/design/JOURNEY_brief.md` |
| Real run evidence | `docs/research/RUN_calib_progression_2026-06-03.{json,py}`, `RUN_jute_dspy_2026-06-03.{json,md,jute}` |

## 6. Real vs prop (the honesty map — critical for an honest critique)

- **REAL (executes / has receipts):** Act 2 council grade (replay + live via BFF); the
  `dosage_grounding` floor (+ 6 tests); the JUTE generate→test→enforce run (mapping id 101); the
  prompt-non-monotonic finding; the judge-instability (risk_judge PASS↔BLOCK across runs).
- **PROP (hardcoded in `journeyData.js`):** Act 3's `3/6 → 6/6` climb + the levers' effects; Act 4's
  golden/regression counts; the agent being "yours" (it's the bundled scribe case).

## 7. Open items (not for the critique session to fix — context only)

1. Wire **Act 3's floor** to the real `grounded` result (the grade record already has it).
2. Wire **Act 4's** session grade for real.
3. **Commit** this session's work (BFF `/v1/case` + `in_process`; the journey rebuild; the
   `dosage_grounding` engine + tests; the RUN docs + the spec). The `case10.mp3` (~2.95 MB) is a
   git-vs-LFS decision. Use explicit pathspecs (dirty-index hazard — memory
   `git-commit-pathspec-dirty-index`).
