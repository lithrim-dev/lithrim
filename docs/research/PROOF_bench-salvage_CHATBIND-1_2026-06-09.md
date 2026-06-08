# Proof — bench-salvage CHATBIND-1: the conversational chat operates on the rail-selected agent (2026-06-09)

> A-LIVE attestation. Env: `:5180` shell / `:8787` BFF / `:8002` council (all health-checked first; no autostart). **$0** — the chat is replay/show-review only; no paid grading fired.

## Claim
After CHATBIND-1, the conversational chat loop operates on the **rail-selected (active) agent** by default — `get_agent` / `review_runs` target the selected case, **not** the hardcoded `ws0_default`. S-BS-103 closed. This is the unlock for the fully-chat-driven imported-case demo.

## What changed
- **Commits:** `574f98f` (feat) + `ef6e540` (test) — branch `bench-salvage/ws6c-dspy`, NOT pushed.
- **Mechanism / files:**
  - `apps/bff/agent/loop.py` — a net-new `_system_prompt(active_agent)` names the active agent + instructs default-targeting. The **only** `_build_options` change is the `system_prompt=` value; the A-SAFE deny-hook / `bypassPermissions` / isolation / allowlist / `max_turns` are byte-identical.
  - `apps/bff/app.py` — `_review_runs` scopes the run history to `req_agent` (filters on the `_run_summary` `agent_id→agent` projection; NON-VACUOUS — pre-fix a foreign agent's run leaks).

## Before → After
| dimension | before (the S-BS-103 bug, found live in DOGFOOD-1) | after (CHATBIND-1, attested here) |
|---|---|---|
| "which case am I evaluating?" | chat reported `ws0_default` regardless of the rail selection | chat reports the rail-selected `imported_scribe_scribe_diabetes_soap_clean_violation` |
| "review its runs" | listed runs unscoped (global history) | "1 run on record. Latest — `0343ca99`: verdict = BLOCK" (the active agent's run) |
| paid surface | (unchanged) | refused: "I can't fire a paid/live run — that's your cost-confirmed action in the UI" |

The delta IS the proof: the chat now follows the UI selection. Honest note below on what is *not* yet scoped.

## Evidence (grounded, not narrated)
- **Live chat** (rail case = `imported_scribe_scribe_diabetes_soap_clean_violation`), prompt: *"Which case am I evaluating right now? Show its config and review its runs."* → verbatim agent response (via `get_page_text`):
  > "You're evaluating `imported_scribe_scribe_diabetes_soap_clean_violation` — the current workspace agent (a clinical scribe case: diabetes SOAP note, 'clean violation' variant). … Config: Judges `risk_judge, policy_judge, faithfulness_judge` · Ontology `clinical/1` · Tools none. … Runs: 1 run on record. Latest — `0343ca99`: verdict = BLOCK. … Note: I can't fire a paid/live run — that's your cost-confirmed action in the UI."
- **Run id:** `0343ca99-c979-4874-abda-00e6ba354364` (the imported case's persisted run; BLOCK).
- **Screenshot:** the live chat naming the selected agent + its run (saved to disk during capture).
- **Reproduce ($0):** on `:5180` select the `imported_scribe` diabetes-violation case in the rail → chat "Which case am I evaluating right now? Show its config and review its runs."
- **Honest observation (not a CHATBIND-1 regression):** the agent-editor gen-UI card's "Config changes" pane renders the **global** governance audit (`GET /v1/audit`, all agents — hence `ws0_default` entries appear there), which CHATBIND-1 did not touch. The **run scoping** (`review_runs`) and the agent the chat *names* are correctly bound to the selected case; the card's audit pane being global is pre-existing and out of CHATBIND-1's scope.

## Journey impact
- **Launch-journey phase:** P3 Calibration — the conversational loop now operates on the case you actually selected.
- **De-risk gap addressed:** #1 SME-authorable bounded context (talk *to the case in front of you*).
- **Unblocks next:** the fully-chat-driven imported-case demo → the narrated walkthrough video (this capsule's second half).

## Video
- **Shipped (owner decision 2026-06-09): the `$0` offline silent + captioned cut.** `compose_lesson`, 5 segments (thesis → live demo → moat → architecture → GTM), `provider=offline`, 106.4s.
- Spec: [journeys/bench-salvage_CHATBIND-1.narrate.json](journeys/bench-salvage_CHATBIND-1.narrate.json) · video + captions: `out/zyng_narrate/chatbind1_capsule_preview.mp4` (+ `.srt`).
- The live-demo segment drives the **real** `:5180` chat (verified by a frame extract at the response moment — the agent-editor card rendered, scoped to the selected case). Honest framing note: the auto-scroll lands on the response card (which renders the **global** audit pane, hence `ws0_default` rows), so the prose hero ("You're evaluating `<case>`") sits just above the fold — a deferred framing polish (a scroll-to-prose step), **not** a correctness gap; the binding was attested directly via Chrome MCP + `get_page_text`.
- **Voice:** NOT voiced this pass — ElevenLabs (paid) declined by the owner; the captioned silent cut is the capsule. Re-render voiced anytime via `compose_lesson` `provider=elevenlabs` (needs `ELEVENLABS_API_KEY` in zyng's server env), `voice="narrator"`, `pronunciation="lithrim"`.
