# Proof — bench-salvage ONB-0: the chat loop now remembers across turns (S-BS-87) — 2026-06-06

> A-LIVE attestation capsule (per `.devloop/templates/PROOF_CAPSULE_TEMPLATE.md`).
> **Status: ATTESTED — A-LIVE PASS 2026-06-06 (memory coherent + the floor live, same run, on the post-ASAFE-1 loop). S-BS-87 CLOSED.**
> Env: `:5180` shell · `:8787` BFF (persistent) · BYO-Claude (`ANTHROPIC_API_KEY` unset). $0.

## Claim
`POST /v1/chat` was **stateless per message** — the agent re-read live config each turn but
carried no conversational thread, so it forgot the user's stated domain and what it just
wrote (the S-BS-87 *"no config writes this session"* failure). ONB-0 makes the loop
**memory-coherent** via a client-replayed `history` array, replayed as **context only** — and
proves, by construction, that replay re-executes no tool and re-spends nothing.

## What changed
- **Commits** (`bench-salvage/ws6c-dspy`, not pushed): `1c1519c` ChatRequest.history + endpoint
  threading · `e7e6192` loop replays history into the fresh `ClaudeSDKClient` · `f260aea` shell
  composer passes prior turns as history · `60a0542` A-SAFE/threading/back-compat tests ·
  `6bb8d92` docs · `34efd72` session log.
- **Mechanism:** `ChatRequest` gains `history: list[ChatTurn]` (default `[]` → back-compatible);
  `_real_source` folds prior turns into a **transcript preamble** on the *same* `client.query(str)`
  call (`agent/loop.py:_fold_history`). The new message is foregrounded last; a guard line
  ("context only — don't re-run a tool") is belt-and-suspenders, **not** the proof.

## Before → After
| dimension | before | after |
|---|---|---|
| `/v1/chat` request | `{message, agent}` (stateless) | `+ history: [{role, content}]` (client-replayed) |
| cross-turn recall | none — re-orients from config each turn | remembers stated domain + prior turns |
| "what we just did" | *"no config writes this session"* (wrong) | reports the actual audited write |
| paid/tool re-fire on replay | n/a | **impossible** — a `str` carries no `tool_use` (by construction) |

## Evidence (grounded, not narrated)
- **Offline gates — both GREEN:**
  - 7-item mechanical audit: **CLEAN** (6 real commits; scope = D1–D6; A6 0-delta; session log valid).
  - HARD-GATE fresh critic (`adedbe687`): **NON-BLOCKING [0 / 2 NB / 1 OQ]**. Critique:
    `.devloop/sessions/critique-bench-salvage-phaseONB-0-2026-06-06.md`.
- **C1 by-construction no-re-execution:** SDK `claude-agent-sdk 0.2.90`,
  `query(str | AsyncIterable[dict])`; the `str` path wraps the prompt in a single **user** message
  → cannot carry a `tool_use` block. Native dict-seed + `resume`/`session_id` NOT used.
- **A6 0-delta:** `git diff e8c52e1..34efd72` over `tools.py`/`adapter.py`/`runtime/council/`/`data/`
  is empty; `app.py` confined to 3 hunks (imports · `ChatTurn`+`history` · `chat_endpoint`); tool set
  stays exactly **8**.
- **A-SAFE non-vacuity (scratch-revert proven):** `extra="forbid"→"ignore"` ⇒ the smuggled-paid-knob
  test FAILS; injecting a re-execution into `run_chat` ⇒ the no-new-audit test FAILS (`assert 1 == 0`).
- **Suites:** onb0+uap5b **17 passed**; +uap5c **29**; import-isolation **2** (default) / **1**
  (debuglithrim); Vitest **4 passed**; ruff clean. (`tests/test_onb0_memory.py` collects **8** tests.)
- **Reproduce (offline, $0):** `PYENV_VERSION=debuglithrim python -m pytest tests/test_onb0_memory.py tests/test_uap5b_chat.py -q`

### A-LIVE — PASS (2026-06-06, monitor-driven on the FIXED post-ASAFE-1 loop, $0 BYO-Claude)
A 6-turn conversation against the auto-reloaded `:8787` loop (`scripts/_onb0_alive_capture.py`).
Evidence: `docs/research/RUN_onb0_alive_2026-06-06.json`. **Verdict: PASS** (all three checks True).
- [x] **A1a domain recall** — turn 5, unprompted: *"You said what you care about most is catching wrong-dosage mistakes."*
- [x] **A1b action recall** — turn 6: *"Config writes this session: one — Assign WRONG_DOSAGE → risk_judge, actor monitor@onb0-alive"* (NOT "no config writes"). S-BS-87 does not recur.
- [x] **A4 no-re-execution** — risk_judge audit `before=17 → after=18, delta=1`: exactly one record despite turns 3–6 carrying the write in history.
- [x] **Floor live, SAME RUN (post-ASAFE-1):** the canary's `Read`/`Bash` were denied (`floor_denied=True`), and the agent's built-ins (`ToolSearch`/`AskUserQuestion`) were refused at the tool layer throughout — it completed the journey on `mcp__lithrim__*` tools alone. **Memory + the enforced floor in one coherent run.** (The agent's "tool loader rejecting me" confusion = S-BS-91, low; it recovered.)
- Capsule video: `out/zyng_narrate/onb0_memory_verified_narrated.mp4` (the old `onb0_memory_narrated.mp4` stays INVALIDATED — it narrated "the safety floor held" pre-fix).

## Journey impact
- **De-risk gap:** **#1 — SME-authorable bounded context** (`PLATFORM_THESIS_bounded_context.md` §4-5).
  Cross-turn memory is the **single load-bearing prerequisite** (`SPEC_ONBOARDING_JOURNEY` §2A) for a
  guided, multi-turn authoring/teaching conversation — without it, the SME on-ramp is impossible.
- **Launch journey:** unblocks the teaching on-ramp (the top-of-funnel that makes the bounded context
  SME-ownable) → **SPEC_ONBOARDING_JOURNEY Phases 1-4**.
- **Unblocks next:** Phase 1 (teaching brain: `mode` + curriculum + capability sheet).

## Video
- Spec: `journeys/bench-salvage_ONB-0.narrate.json` (mode 2 capture→narrate) → render:
  `out/zyng_narrate/onb0_memory_narrated.mp4` (+ `.srt`). **PENDING** — rendered after the A-LIVE
  (from the silent capture, or a card-based capsule from the before→after + audit evidence).
