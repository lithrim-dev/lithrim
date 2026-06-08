# HANDOFF — bench-salvage (monitor role) — 2026-06-09 (v1-launch focus)

> **For the NEW monitor session.** This session closed **CHATBIND-1** (+ proof capsule + A-LIVE) and **CHATBIND-2**, pivoted the whole stream to **v1-launch focus** (user: *"launch the first version ASAP, don't digress"*), and authored the **LAUNCH-PREP** driver (the one cycle between us and a release).
> **Resume:** `/devloop-resume bench-salvage`, then read this, then hand the user the LAUNCH-PREP kickoff (or process its return).

## 🔴 IMMEDIATE STATE — LAUNCH-PREP authored + READY (the next cycle)
**v1 critical path: CHATBIND-1 ✅ → CHATBIND-2 ✅ → `LAUNCH-PREP` (ready) → push/release (owner-gated).**
- The **LAUNCH-PREP** driver is authored + registered (`status: ready`): `.devloop/prompts/bench-salvage_phaseLAUNCH-PREP_v1-standalone-and-release-prep_driver.md`. The paste-ready kickoff is the top block of that driver (and was handed to the user). The user runs it in a fresh executor session; **you process the return** (7-item audit + inline critique + the **live standalone smoke**). It is **ROUTINE-with-care, NOT HARD-GATE** — escalate to a fresh-critic ONLY if D1 turns out to touch the A-SAFE conversational gate (it should not).
- **What LAUNCH-PREP does** (packaging, NOT features): **D1 (load-bearing)** a standalone council topology — a `LITHRIM_COUNCIL_BACKEND=in_process|http` selector (default `in_process`) so the OSS core runs the bundled v2 council **BYO Azure/Claude key, NO lithrim-backend (`:8002`), NO Mongo** (the WS-6 port made the council in_process-capable; the shell defaults to `:8002` today). **A-SAFE: the chat stays replay-only/`$0`; D1 changes the human's paid-run backend only — confirm the deny-hook/allowlist byte-identical + the in_process council imports self-contained.** **D2** a product QUICKSTART (the README is engine-only today). **D3** green bar + a seam-triage table. **D4** a RELEASE.md/checklist + notes (the push is owner-gated — PREPARE only).
- **At its close:** audit + inline critique + the **A-LIVE = a live standalone run on `:5180` with lithrim-backend STOPPED** (user-run, BYO-key) — this proves standalone v1 AND doubles as the owed CHATBIND-2 A-LIVE.

## 🧭 THE THROUGH-LINE — v1-launch mode (do NOT re-expand scope)
The user's standing directive (2026-06-09): **launch the first version ASAP, don't digress.** Reassessment: **v1 is ~built** — the clinical conversational, tool-grounded eval platform (3-pane shell + 12 chat tools + the multi-provider v2 council + the **grounding-floor moat** + the audit trail + the CI/CD gate), live-attested + CHATBIND-2. **CUT to the parked post-v1 roadmap — specs WRITTEN, do NOT spec/build until v1 ships:** SCENARIO-1 / FHIR / StoryWorld (`docs/specs/SPEC_EVAL_SCENARIOS.md`), IMPORT-1 (data-ingestion), the provider picker / Claude-council UI (GAP B / S-BS-105), the plugin refactor (`docs/specs/SPEC_PLUGIN_ARCHITECTURE.md`, OQ-1..3 resolved). Memory `conversational-first-core-plugin-line` carries the pivot + the CUT. **If the user adds vision mid-launch, capture it as a parked spec — don't let it delay v1.**

## The arc this session — 2 cycles CLOSED + the launch pivot
| Cycle | Status |
|---|---|
| **CHATBIND-1** (chat bound to the active agent) | ✅ CLOSED PROCEED-WITH-CAVEATS — audit CLEAN + fresh-critic `a543783125606a12c` CLEAN. Closed S-BS-103, opened S-BS-106. Build `574f98f`+`ef6e540` (exec) + close `6e357d4`. **A-LIVE ATTESTED** (live `:5180`, Chrome MCP, `$0`: the chat named the rail-selected imported case + reviewed its run `0343ca99`→BLOCK + refused the paid run). **Proof capsule** `e9f4d8c` (PROOF doc + a `compose_lesson` journey spec + a `$0` silent video; voiced ElevenLabs cut deferred by owner) + state sync `6178b44`. |
| **CHATBIND-2** (chat drives the artifact pane) | ✅ CLOSED PROCEED-WITH-CAVEATS — audit CLEAN + HARD-GATE fresh-critic `a55dc0be504726cde` NON-BLOCKING [0/1 NB/1 nit]. A-SAFE byte-identical (full `_build_options` diff = 0; `emit_run` from the single replay-only `run_eval_handler` → the `run_result` event can't carry a paid run). Build `e7b0806`+`4bf3c89`+`d8d9e70` + log `961140d` (exec) + close `8f87843`. Opened S-BS-107 + S-BS-108. **A-LIVE owed (folds into LAUNCH-PREP's standalone smoke).** |
| **SPEC work** (parked roadmap) | `SPEC_PLUGIN_ARCHITECTURE` OQ-1..3 RESOLVED + `SPEC_EVAL_SCENARIOS` authored (`d0edcdd`, `1ba6291`) — the post-v1 fluid-multi-scenario roadmap. PARKED per the launch pivot. |
| **LAUNCH-PREP** | 🅿️ **READY** (`3790a0e`) — the next cycle. |

## Git state (NOT pushed — owner-gated)
- Branch `bench-salvage/ws6c-dspy`, **HEAD `3790a0e`**. A **large unpushed stack** (everything since the branch diverged — UX-1 through here). **Push/PR/release is the LAUNCH-PREP D4 deliverable + owner-gated** (the executor PREPARES the checklist; the user pushes).
- Working tree: `M apps/shell/src/root.jsx` (a concurrent session's change — LEAVE it) + 3 foreign untracked (`.claude/`, the `KICKOFF_CRITIC_…WS-6c-DSPy…`, `docs/research/REPORT_fhir_agentbench…`). **All monitor commits pathspec-only** (`git commit -- <files>`; never bare — the dirty shared tree). [[git-commit-pathspec-dirty-index]] Note: executor + monitor commits **interleave** on this branch (e.g. my `1ba6291` landed between the executor's CHATBIND-2 commits) — expected, no conflict; verify scope per-commit with `git show <hash> --stat`.
- Services were up earlier (`:8002` council, `:8787` BFF, `:5180` shell). **Don't autostart — `curl /health` first.** For the LAUNCH-PREP A-LIVE the standalone smoke needs lithrim-backend STOPPED.

## Open seams (current)
- **S-BS-108** (low) ConfigTab may render the error state for a brand-new blank agent (renumbered from the CHATBIND-2 log's collided "S-BS-106"; verify in A-LIVE) · **S-BS-107** (low) pre-existing ruff-format drift in `test_uap5c_journey.py`+`test_crud_delete.py` (a future `ruff format` sweep) · **S-BS-106** (low) `review_runs` 200-row global-window ceiling.
- **S-BS-105** (med) the shell can't drive the `in_process` model-mix ladder — **LAUNCH-PREP D1 partially closes this** (the in_process backend becomes the default). · **S-BS-98** (med) the judge store is GLOBAL per-role not per-agent. · carried: S-BS-91/93/95/96/97/99/100/101/102/104.
- **Triage at LAUNCH-PREP D3:** none of these is expected to be a HARD launch-blocker.

## Owed / pending / parked (all POST-v1 or parallel — none blocks LAUNCH-PREP)
- **CHATBIND-2 A-LIVE** (user-run `$0`) — folds into LAUNCH-PREP's standalone smoke (chat "run a `$0` replay + show the judge council" → the pane opens/focuses).
- **The v1-scope-line** (pitch/early-access [monitor rec, fastest] vs self-serve) — PARALLEL, non-blocking; it only decides whether **IMPORT-1 + the provider picker** layer in AFTER LAUNCH-PREP. The user's last word: *"we need to do launch prep either ways right?"* (yes — LAUNCH-PREP is unconditional).
- **The Claude-council live demo** (now unblocked post-CHATBIND-2; provider-surface motivator) — POST-v1. Claude IS available (`build_judge_lm` `byo-claude`/`claude`/`claude-cli` → tool-less `ClaudeCliLM`; persist per-judge `model:"byo-claude"` + run in_process) but not UI-pickable (GAP B / S-BS-105). Memory `conversational-first-core-plugin-line`.
- **CHATBIND-1 voiced video** (ElevenLabs cut, owner-deferred) + the proof-capsule convention (doc + zyng video at each A-LIVE; honest-Δ). [[proof-capsule-convention]]

## Standing context for the monitor
- **The user runs the executor sessions + the paid/live runs** (pastes the kickoff; brings the plan-review + the return back). The monitor audits, gives the go, runs the close (fresh-critic for HARD-GATE), commits the close artifacts pathspec-only.
- **Prefs:** no autostart (`curl /health`, halt+ask if down); no push without explicit owner approval; LLM-cost-conscious (the user authorizes paid runs explicitly); **honest-Δ only** (an honest loss/non-result is a PASS, documented); **don't digress / launch ASAP** (the active directive — resist scope creep; park vision as specs).
- **Diagnose-before-edit + re-grep at driver-authoring (Phase-1a)** + **trust the executor's verbatim evidence** (the CHATBIND-1/2 executors both caught real flaws — the unreachable closure-default, the no-fetch-by-id reality, the ConfigTab gap). [[live-reassess-before-driver-lock]]
- **A-SAFE is the sacred invariant** for any chat-surface change: the deny-hook + allowlist (derived from `_TOOL_SPECS`) + the replay-only `$0` contract byte-identical; no paid knob; HARD-GATE → fresh-critic. [[conversational-authoring-surface-complete]]

## Pointers
- **Drivers:** `…phaseLAUNCH-PREP…` (READY, the next) · `…phaseCHATBIND-2…` (shipped) · `…phaseCHATBIND-1…` (shipped). `.devloop/prompts/index.json` (58 bundles).
- **Specs (parked post-v1):** `docs/specs/SPEC_EVAL_SCENARIOS.md` (the fluid multi-scenario; D-A working-frame-now, D-B FHIR-first) · `SPEC_PLUGIN_ARCHITECTURE.md` (OQ-1..3 resolved: Core = conversational shell + engine + ALL JUTE + BYOK + public plugins; Pro = locked vertical packs; the FE-plugin kind).
- **Closes:** `critique-bench-salvage-{CHATBIND-1,CHATBIND-2}-2026-06-09.md` + session logs alongside. `PROOF_bench-salvage_CHATBIND-1_2026-06-09.md`.
- **State:** `STREAM_bench-salvage.md` (First-move topped with the v1-launch focus + CHATBIND-2 close) + `streams.json` (current_phase = v1-launch + LAUNCH-PREP next).
- **Memory:** `conversational-first-core-plugin-line` (the v1-launch pivot + the CUT + the parked roadmap), `conversational-authoring-surface-complete` (the A-SAFE bound), `git-commit-pathspec-dirty-index`, `gtm-launch-and-journey-thesis` (open-core/BYO-key/no-us-hosted; install-friction = the named risk), `shell-no-prettier-handcompact-jsx` (the executor's note: no prettier config; edit shell JSX by hand).
