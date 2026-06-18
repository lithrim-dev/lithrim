# Findings — driving the "talk to it" flow live (browser MCP, 2026-06-18)

> Drove the running shell (`localhost:5180`, workspace `clinverdict_clean`, 10 ingested ClinVerdict
> cases) **conversationally** via Claude-in-Chrome, to test the pitch scenario: *hand someone the
> laptop and have them talk to the system to explore each case, run an eval, and view the report.*
> Documented for a follow-up fix cycle — not fixed here.

## TL;DR
The UI half works (the de-jargon pass + the case-selector ship): the **Cases** tab lists all 10 with
"transcript ✓", clicking one opens a readable Case tab (SOAP note + FHIR + honest "not labeled"), and
a UI **Run live** produced a clean report (case 10 → PASS, an honest miss vs the physician's reject).
**But the conversational layer is decoupled from the ingested cases** — the chat's case tools always
operate on the agent's bootstrap **seed case** (`bench_coding_v1_clean_negative`), never the ingested
corpus or the case the user is exploring. So "talk to it to explore each case / run eval" is broken at
the tool level, even though the same capability works by clicking. (This mirrors exactly the UI
case-selector gap already fixed — the chat tools need the same `case_id` wiring.)

## CRITICAL — the chat can't explore the ingested cases
1. **`show_case` ignores the requested case — always shows the seed (confident-but-wrong).**
   Asked *"open the case clinverdict_05_psychology and show me its transcript,"* the agent replied
   **"I've opened clinverdict_05_psychology"** — but the inline Case-Summary card it dropped shows
   **`bench_coding_v1_clean_negative_f03b12825b50`** (the bootstrap seed). The tool has no `case_id`
   param; it serves the agent's `dataset.case_id`. Saying one case while showing another is the worst
   failure mode for a demo. *(apps/bff/agent/tools.py `SHOW_CASE_SCHEMA = {}` — no case_id.)*
2. **No `list_cases` tool.** *"show me the cases I can evaluate in this workspace"* → the agent shows
   the single seed case, not the 10 ingested cases (the UI **Cases** tab lists them fine via
   `GET /v1/cases`). The chat cannot enumerate the corpus.
3. **The chat `run_eval` grades the seed, not the explored/selected case.** *"run an evaluation and
   show me the verdict"* → a `$0 replay` against the seed; the UI's selected case (`clinverdict_10`)
   is ignored. The chat run is decoupled from the case on screen.
4. **Three-way case divergence, simultaneously.** The chat *claims* case 05, the chat's Source card
   *shows* the seed, the UI Case pane *shows* case 10. There is no shared "active case" between the
   chat and the UI.

## GOOD — keep (A-SAFE + honesty are working)
5. **The agent never spent.** It attempted the `$0 replay`; on "no captured baseline," it **surfaced
   the cost-confirm modal** ("a live run is a paid action, and I can't spend on your behalf — that's
   yours to authorize") rather than firing it. A-SAFE intact, no manufactured spend.
6. **Honest, legible explanation** of replay-vs-live, and the Case/Report/Calibration render cleanly
   with the de-jargon pass — including the honest *"No answer key for this case — accuracy can't be
   measured yet"* on the unlabeled ingested case (no fabricated 0.0/approve).

## MEDIUM
7. **Unsolicited Agent-editor (config-write) card** dropped on a read-only *"show me cases"* request —
   the agent over-eagerly surfaces the agent-config write form for a read.
8. **Mislabeled the seed** as *"the planted, by-construction defect — the known defect"* — it's a
   clean-negative (no defect). Confidently wrong description of the case.
9. **Inconsistent paid-run gating.** The chat gates a paid run behind the cost-confirm modal; the UI
   **Run live** button fired a paid in-process run with **no** modal. Decide the intent: is the button
   itself the authorization (then fine), or should it also confirm cost?

## LOW (copy the audit missed)
10. Loading state *"Running eval over the harness…"* — "harness" is jargon.
11. Status bar *"judge council: 3"* — "judge council" jargon (the audit didn't cover the status bar).
12. The agent misdiagnosed the seed (a pack case with no baseline set) as *"imported/live-only."*

## The fix (parallels the UI case-selector already shipped)
The UI fix added a `case_id` param to `GET /v1/case` + `run-eval` + an `activeCase` selector. The chat
tools need the same:
- **Add `list_cases`** SDK-MCP tool → `GET /v1/cases`, so "show me the cases" enumerates the corpus.
- **Add `case_id` to `show_case`** → `GET /v1/case?case_id=X` (the endpoint already supports it), so
  "open case X" shows case X (and the agent must never claim a case it didn't open).
- **Thread `case_id` into the chat's run path** (the `/v1/run-eval` endpoint already accepts it), so a
  conversational run grades the case under discussion.
- **Share one "active case"** between the chat and the UI `activeCase`, so "explore the splinter case"
  by talking → the UI Case pane shows it → Run grades it. (The shell already lifts the chat's `$0`
  replay into `runResult`; extend that to a shared case selection.)
- **System-prompt nudge:** for "cases" call `list_cases`; for "open/explore case X" call
  `show_case(case_id=X)`; don't drop the Agent-editor card for a read; describe a clean-negative as
  clean, not as a planted defect.

## Evidence
Live drive on `localhost:5180` / `clinverdict_clean`. Reproductions: "show me the cases…" → seed +
agent-editor card; "run an evaluation…" → $0 replay on the seed → cost-modal (cancelled); "open
clinverdict_05_psychology" → claims 05, shows seed. UI path (click Cases → case 10 → Run live) →
clean PASS report.

---

## RESOLUTION — NARR-CHAT-LOOP (2026-06-18, addressed in this cycle)
The chat tools are now wired to the corpus, mirroring the UI case-selector. **Deterministic gate
GREEN** (`tests/bff/test_chat_case_flow.py` +11; pinned tool-count/A-SAFE tests bumped 17→18;
shell `CaseCard.test.jsx` + `panes.chat.test.jsx` +sync; ruff clean). A live conversational
re-drive (the A-LIVE attestation) needs a **BFF restart** to load the new tool code (FastAPI does
not hot-reload) and spends BYO-Claude — owner-authorized, not done here.

| Finding | Fix |
|---|---|
| #2 no `list_cases` | New **`list_cases`** SDK-MCP tool ($0/read) → `GET /v1/cases`; enumerates the ingested corpus + opens the Cases tab. Tool set 17→18. |
| #1 `show_case` ignores case_id | `SHOW_CASE_SCHEMA = {"case_id": str}`; `case_summary_part` + `CaseCard` carry `case_id` → `getCase(agent, case_id)`; an explicit case_id also updates `ctx.active_case`. The agent is told never to claim a case_id it didn't pass. |
| #3 chat run grades the seed | `RUN_EVAL_SCHEMA` gains `case_id`; `run_eval_handler` defaults it to `ctx.active_case`; `_run_eval_replay(agent, case_id)` threads it (A-SAFE: still no paid knob — a selector). |
| #4 no shared active case | `ChatRequest.active_case` (shell sends `activeCase`) → `ToolContext.active_case` → named in the system prompt. chat→UI: a `case_summary`/`run_result` lifts the case back into the shell's `activeCase` (`onActiveCase`). |
| #5 nudges | System prompt: call `list_cases` for "the cases"; `show_case(case_id=…)` to open one; describe a clean/unlabeled case as clean, not a planted defect. |
| #8 mislabeled seed / #10–11 jargon | `show_case` text + prompt say clean≠planted; StatusBar "judge council"→"judges"; "…over the harness"→"Running the evaluation" / "Collecting the judges' votes". |

GOOD items (#5 A-SAFE, #6 honesty) are untouched — the paid path stays the human's in-DOM
cost-confirm; `case_id` is a selector, never a spend (asserted non-vacuously in the new tests).
