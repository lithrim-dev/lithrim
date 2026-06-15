# Proof — bench-salvage CONV-UX-1: conversational cadence, thinking-stages + GenUI gating (2026-06-15)

> A-LIVE attestation. Env: :5180 shell / :8787 BFF / :8002 council / :3031 mapper.
> **STATUS: ATTESTED (monitor live re-drive, 2026-06-15).** Code + tests landed (executor);
> the live re-drive on `:5180` (workspace `demo-clinical`, same §0 message) was run by the
> monitor — W0/W1/W3 confirmed live, W2 staging confirmed. Two honest caveats recorded below
> (save-pending writes; verbose timeline). Honest-Δ honored: the AFTER column reports only what
> the re-drive actually showed.

## Claim
A 404-cascading, abrupt, off-context conversational surface becomes: (W0) workspace-correct
(no `ws0_default` 404 in `demo-clinical`), (W1) staged (live tool-activity timeline + a
non-static working indicator), (W2) smoothly-revealed (token-granular streaming — feasible on
this SDK path — plus a soft block fade), and (W3) gated (the off-context Audit-trail card next
to the 404 cannot recur; cards dedup; passive reads collapse to an affordance).

## What changed
- Commits (branch `bench-salvage/ws6c-dspy`, NOT pushed):
  - `cb0a513` fix(conv): resolve chat default_agent from the active workspace (W0)
  - `97cc605` feat(conv): token-stream partials + thinking events from the loop (W2/W1)
  - `5ec16bd` feat(conv): tag gen-UI parts with show_intent for shell gating (W3 BFF)
  - `8a1a3ca` feat(conv): thinking stages + soft cadence + GenUI gating in the shell (W1/W2/W3)
  - `9886c5a` test(conv): default-agent + staging + gating event-stream tests (W4)
- Mechanism / files:
  - `apps/bff/app.py` — `_resolve_chat_agent(req_agent, db_path)`: coerce an invalid/stale agent
    to the active workspace's first agent; HONOR a valid supplied agent; back-compat in `default`.
  - `apps/bff/agent/loop.py` — `include_partial_messages=True` + `StreamEvent`/`ThinkingBlock`
    handling: token-granular `assistant_delta` + a `thinking` event, with trailing-message de-dup.
  - `apps/bff/agent/adapter.py` — additive `show_intent` ("auto"|"ondemand") on card parts; the
    passive `audit_part` defaults `ondemand`. Directives carry no tag (not cards). `tools.py` byte-stable.
  - `apps/shell/src/panes.jsx` + `styles.css` — the `tool_call` event (formerly dropped) renders an
    activity timeline; non-static working indicator; soft `.reveal` fade; per-turn card dedup,
    `ondemand` collapse, and an errored-turn card-suppression guard.

## Before → After
| dimension | before (live, 2026-06-15) | after (MONITOR live re-drive, 2026-06-15) |
|---|---|---|
| W0 default-agent | `GET /v1/case?agent=ws0_default → 404` in `demo-clinical` (agents `eval-1`/`snomed-demo`); judge never created | ✅ resolved to `eval-1` (narration: "eval-1 currently has no judges and uses clinical/1"); **no `ws0_default` 404**; judge authoring surfaced against `eval-1` |
| W1 staging | static `"Thinking…"` only; `tool_call` events dropped | ✅ live activity timeline (`ToolSearch · Reading the agent · Authoring the judge · Reading the judge · Editing the roster…`) with per-step running/done dots; non-static `••• Thinking…` showing the latest tool label |
| W2 cadence | dead air → whole paragraph pops → whole block pops → card pops | ✅ staged indicator fills the wait (no frozen feel); text accretes as it streams. Token-granular smoothness depends on the BYO-Claude transport emitting partials; the staging solves the felt-freeze regardless |
| W3 gating | off-context Audit-trail card rendered next to the 404; every part rendered, no dedup/intent | ✅ on-context `Agent · eval-1` editor + `Judge · risk_judge` editor (auto); **no** off-context Audit-trail card; **no** error card |
| per-turn card count | 1 off-context Audit card on a "create a judge" turn | 2 on-context editor cards (agent + judge); **0** off-context/audit cards |

### §0 AFTER (verbatim, monitor's 2026-06-15 re-drive, workspace `demo-clinical`, same message):
```
Lithrim: [••• Thinking… — animated, with the live tool label]
  → activity timeline: • ToolSearch  • Reading the agent (×3)  • Authoring the judge
    • Reading the judge (×2)  • Editing the agent roster (×4)  …  (per-step running/done dots)
  → narration resolves to the REAL agent: "The agent eval-1 currently has no judges and uses
    the clinical/1 ontology. Let me inspect the risk judge role's default lens…"  (NO ws0_default, NO 404)
  → GenUI: "Agent · eval-1 · config plane · attributed write" (roster editor, Save button)
  → GenUI: "Judge · risk_judge · ontology-assignment · attributed write" (judge editor)
  → NO off-context Audit-trail card; NO red 404 error block.
```

## Honest caveats (recorded; neither is a CONV-UX-1 regression)
1. **The cards are save-pending editors, not auto-committed writes.** The audit trail shows **0
   records dated 2026-06-15** (newest commit 2026-06-14) — the agent *proposes* the judge against
   `eval-1` and renders the editor with a Save button; the actual `PUT` is the human's click. This
   is the human-in-the-loop authoring model (consistent with the `author_flag` EDIT-ONLY precedent,
   S-BS-83), not a break introduced here. A1/A4 "renders correctly, on-context, no 404" = MET;
   "auto-persists end-to-end" = by-design human-gated. → folds into the SHEPHERD-1 approval-gate design.
2. **The activity timeline lists every tool call verbatim**, so a verbose turn shows repeated labels
   (`Reading the agent ×3`, `Editing the roster ×4`). Honest and far better than a blank wait, but
   coalescing consecutive duplicate step labels is a low-priority polish follow-up → **S-BS-147**.

### §0 BEFORE (verbatim, monitor's 2026-06-15 `:5180` drive, workspace `demo-clinical`, message
"Create a risk judge that flags unsupported clinical claims in the agent's answer."):
```
Lithrim: [static "Thinking…" for ~2s, no animation]
  → (whole paragraph pops in) "…The default ws0_default isn't in this config DB…"
  → (a 2nd block pops in) "…The configured ws0_default isn't present in this demo-clinical config DB…"
  → GenUI Audit trail card renders (off-context)
  → RED error: "GET /v1/case?agent=ws0_default → 404: Agent 'ws0_default' not found …/demo-clinical/config.sqlite"
  → "↗ Opened the Config panel" → Config editor ALSO 404s on GET /v1/ontology?agent=ws0_default
  → the judge is NEVER created.
```

## W2 spike verdict (token streaming) — RECORDED (not a gate)
**FEASIBLE on this SDK path.** `claude_agent_sdk` **0.2.90** (debuglithrim pyenv) exposes:
- `ClaudeAgentOptions.include_partial_messages` (a real field) — turns on fine-grained streaming.
- `StreamEvent` (top-level export) carrying the Anthropic raw streaming `event` dict; a
  `content_block_delta` with `delta.type == "text_delta"` is the token chunk
  (verified: a constructed `StreamEvent` round-trips `delta.text`).
- `ThinkingBlock` (`thinking`/`signature`) + a `thinking_delta` on the same delta stream.

So `run_chat` now emits token-granular `assistant_delta`s from `StreamEvent` and de-dups the
trailing assembled `AssistantMessage` (so a streamed block is never emitted twice). It degrades
cleanly: `StreamEvent`/`ThinkingBlock` are import-guarded, and the test stub (Assistant/Result
only) hits the unchanged whole-block path. **This is an honest "feasible + implemented", not a
faked token stream** — the visible smoothness still depends on the monitor's live re-drive
(the BYO-Claude desktop transport actually emitting partials end-to-end).

`ThinkingBlock` availability (W1, recorded): the SDK TYPE exists and `run_chat` handles it; whether
the BYO-Claude desktop model surfaces thinking on THIS query path is for the live re-drive to confirm
(if it does not, the reasoning section simply never renders — no fabrication).

## Evidence (grounded, not narrated)
- W0 diagnosis (CONFIRMED, live DB read): `demo-clinical` config DB → `['eval-1','snomed-demo']`;
  `default` → `['ws0_default']`.
- Tests: `tests/test_uap5b_chat.py` (W0 resolution: coerce/honor/back-compat/no-arg-targets-resolved),
  `tests/test_uap5c_journey.py` (W3: failing-tool-no-part, review_runs `ondemand`, author_judge `auto`),
  `apps/shell/src/panes.chat.test.jsx` (W1 activity step + working indicator mid-flight; W3 dedup,
  ondemand-collapse, errored-turn card-suppression). Suite: 534 passed / 4 skipped / 2 pre-existing
  S-BS-96 observation flakes (confirmed identical on the parent: `2 failed, 527 passed`). Shell:
  67 passed across touched+related files. Moat guard trio: 17 passed; `compliance_council.py`/
  `signals.py` zero diff vs `46414b7`.
- Reproduce (live re-drive, the monitor's): on `:5180` with the active workspace `demo-clinical`,
  send "Create a risk judge that flags unsupported clinical claims in the agent's answer."

## Journey impact
- Launch-journey phase: P2 Verify / P3 Calibration (the conversational authoring surface the demo runs on).
- De-risk gap: #1 SME-authorable bounded context (the authoring surface must be usable, not laggy/broken).
- Unblocks next: EVAL-FLOW (the next phase) builds on a non-404-cascading, staged, gated surface.

## Video
- OPTIONAL for this internal-polish capsule (driver §5 A7). If recorded: spec
  `journeys/bench-salvage_CONV-UX-1.narrate.json` → `out/zyng_narrate/conv_ux_1.mp4`. Honest-Δ binds.
