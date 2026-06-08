# Fresh-critic critique — `bench-salvage` CHATBIND-2 (the chat drives the artifact pane)

> **Mode:** HARD-GATE → genuinely-fresh critic (Agent `a55dc0be504726cde`, cold context, isolated worktree) + monitor 7-item audit.
> **Date:** 2026-06-09 · **Verdict: NON-BLOCKING (effectively CLEAN)** (fresh-critic [0 BLOCKING / 1 NB / 1 nit]; monitor audit CLEAN). CHATBIND-2 closes **PROCEED-WITH-CAVEATS** — all offline acceptance green; **A-LIVE is the user's pending `$0` run.**

## What landed
The conversational chat now drives the 3rd pane. **D1–D2** (`loop.py`/`tools.py`): a new `$0` read-only **`focus_artifact({tab})`** tool emits a `tool-open_artifact` DIRECTIVE (`adapter.open_artifact_part`); a `_system_prompt` pane-control stanza tells the agent WHEN to focus (judges/report after a verdict, config after an edit, corpus for the flywheel). **D3** (`panes.jsx`): the shell honors the directive — `onOpenArtifact(tab)` guarded by `ARTIFACT_TABS`, rendered as a tiny non-card affordance, **never** via `renderTool`/`KNOWN_TOOLS`. **D4 (Option D, per GO):** a new `run_result` SSE event lifts the chat's `$0` replay record (byte-same to the manual Run-eval result) into the shared `runResult` so the focused Report/Judge tab shows THIS run. **GO decisions honored:** D4=lift-event, the ConfigTab `activeAgent` thread is in, **`ref` dropped**.

## Monitor 7-item audit (independent)
1. **Commits** `e7b0806` (bff) + `4bf3c89` (shell) + `d8d9e70` (tests) + `961140d` (session log) on `bench-salvage/ws6c-dspy`; my `1ba6291` (SPEC_EVAL_SCENARIOS) interleaved (no conflict); tree clean except the foreign `root.jsx` (M) + 3 untracked. ✓
2. **Files** = the planned set: BFF (adapter/loop/tools), shell (app/artifact/panes), 8 test files, session log. No foreign file swept into any commit. ✓
3. **Tests** — monitor re-ran (`debuglithrim`): `test_chatbind2_pane.py`+`test_asafe_tool_gate.py`+`test_chatbind_active_agent.py` = **17 passed**; executor full-suite 408 (with creds); ruff check clean on touched. ✓
4. **Scope** — A-SAFE byte-identical (`git diff d0edcdd..HEAD -- loop.py` touches ZERO `_build_options` gate lines); no paid knob (`FOCUS_ARTIFACT_SCHEMA={tab}`, no `PAID_KEYS`; `emit_run` only from the replay-only `run_eval_handler`); the one ruff-reflow is WITHIN the edited `tools.py` (allowed). ✓
5. **Prefs** — pathspec-only; A-LIVE skipped (user-run `$0`); no autostart; no push. ✓
6. **Session log** present + well-formed. ✓
7. **Deviations** justified — D4=Option D, the ConfigTab thread, `ref` dropped (all APPROVED-AT-GO); the pre-existing ruff drift (CITATION-DRIFT, not introduced). ✓

## Fresh-critic — C1–C5 (all CONFIRMED), independently
- **C1 loop.py A-SAFE byte-identity** — CONFIRMED *by full-function diff*: `_build_options` byte-identical `d0edcdd..HEAD` (deny-hook, `bypassPermissions`, `setting_sources=[]`, `skills=[]`, allowlist-construction, `max_turns=12` all unchanged). The only loop.py changes are the SSE docstring, the `_SYSTEM_PROMPT` bullet, the `_system_prompt` stanza, and the `run_chat` drain. Allowlist value grows by exactly `mcp__lithrim__focus_artifact` via the `_TOOL_SPECS` derivation.
- **C2 no paid path** — CONFIRMED (load-bearing): `focus_artifact` carries no `PAID_KEY` + wraps no op; **`emit_run` is called from EXACTLY ONE site** (`run_eval_handler:220`), `run_results` written only by `emit_run` + drained only at `loop.py:233`; `run_eval_handler` → `_run_eval_replay` hardcodes `live=False, in_process=False` (no agent-reachable paid path). So the `run_result` event can only ever carry a `$0` replay. `_run_eval_pack` byte-unchanged, still `live=False`.
- **C3 directive non-vacuous + never a card** — CONFIRMED: fires `onOpenArtifact` guarded by `ARTIFACT_TABS`; special-cased OUT of `renderTool` (`data-testid="pane-directive"`); absent from `KNOWN_TOOLS`; tab validated on both sides; tests fail if ignored/inline.
- **C4 run_result lift correct + replay-only-shaped** — CONFIRMED: byte-same shape to the manual Run-eval; ConfigTab `activeAgent` thread wired (`getOntology(agent)`, not hardcoded `ws0_default`).
- **C5 scope held** — CONFIRMED: `app.py` (frozen ops + audit/owner↔emit gates + paid wrappers) byte-unchanged; `registry.js`/`KNOWN_TOOLS` unchanged; no unrelated file reformatted.
- **No cross-agent leak**: the directive carries only `{tab}` — the pane always reflects the shell's own `activeAgent`/`runResult`.

## Green-bar note (honest)
The critic's hermetic worktree showed 393 passed / 14 failed / 1 skipped — the **14 are pre-existing missing-OpenAI/Azure-credentials council tests + 1 corpus-regen, in files CHATBIND-2 never touched** (the executor's 408-green ran under `debuglithrim` *with* the `.env` creds). The CHATBIND-2 tests are hermetic (17 green in both envs). Consistent with the repo's known "needs credentials" green-bar caveat — not a regression.

## Findings (seams + nits)
- **S-BS-108 (low, HYPOTHESIS — renumbered from the session log's "S-BS-106", which collided with the CHATBIND-1 review_runs seam).** ConfigTab self-fetch via `getOntology(agent)` may render the error state for a brand-new blank `eval-N` agent before its ontology working-copy exists. The error branch already prevents a crash; cosmetic. Verify in the A-LIVE.
- **S-BS-107 (low, CONFIRMED).** Pre-existing `ruff format` drift in `tests/test_uap5c_journey.py` + `tests/test_crud_delete.py` (untouched regions; confirmed at HEAD). Left as-is (no drive-by); a future `ruff format` sweep cleans them in its own commit.
- **nit (pre-existing, not introduced).** `ReportTab` reads `composite.active_findings.length` etc. without null-guarding sub-fields; safe in production (a real replay record is always complete) + the A4 test's mock record defends the transient render. Out of scope.
- **NB (by-design).** The `run_result` lift overwrites the shared `runResult` (a chat replay clobbers a prior manual run) — the existing single-slot "latest run" semantics; identical to a second manual run.

## Disposition
NON-BLOCKING → **CHATBIND-2 CLOSED PROCEED-WITH-CAVEATS.** The chat drives the artifact pane (open/focus + the run lifted into the pane) with the **A-SAFE invariant provably intact** — `_build_options` byte-identical, the allowlist +1-exactly, no paid knob, and the `run_result` lift traced end-to-end to a single replay-only call site that can never stream a paid run. Scope tight (`app.py` byte-untouched). Opened **S-BS-107** + **S-BS-108** (both low). **A-LIVE owed** (user-run `$0`): on `:5180`, chat "run a `$0` replay and show me the judge council" → the pane opens, focuses Judge council, shows the run; then "show its config" → Config. This completes the fully-chat-driven demo (the CHATBIND-2 unlock).
