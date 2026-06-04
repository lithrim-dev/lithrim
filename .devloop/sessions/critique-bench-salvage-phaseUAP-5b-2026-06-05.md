# Fresh-Critic Critique — `bench-salvage` phase `UAP-5b` (the conversational shell, R11)

> **HARD-GATE fresh critic.** No prior implementation context. Spec + diff read COLD; every
> executor claim re-verified from source. Critic ran read-only commands/tests; wrote only this doc.
> Diff under review: `336c69a^..2944c55` (6 commits). Date: 2026-06-05.

**VERDICT: NON-BLOCKING [0 BLOCKING / 4 NB / 2 OQ].**

The two gate-deciders both hold:
- **A-SAFE-has-no-agent-paid-path: HOLDS** (CONFIRMED — I tried to break it five ways; the only `live=/in_process=` literal in the entire new surface is the hardcoded `False,False` in the chat binding, and the agent's tool allowlist is exactly the 3 in-process MCP tools).
- **A6 frozen 0-delta: HOLDS** (CONFIRMED — `wc -l == 0` over all frozen files; app.py has **zero deletion lines** → the existing op handlers are untouched).

---

## Q1 — Surface fidelity (the /v1/chat SSE route, the 3 SDK-MCP tools, the parts-adapter)

**Match to driver: faithful.** CONFIRMED.

- **Route:** `POST /v1/chat` returning a `StreamingResponse(media_type="text/event-stream")` — matches §2 D2 + the ratified §10 shape (`apps/bff/app.py:962`). `ChatRequest = {message, agent}` only.
- **3 tools (D-A):** `author_judge` / `get_judge` / `run_eval` — exactly the resolved CORE spine (`tools.py:130-154`; asserted by `test_core_tool_set_is_the_three_spine_tools`).
- **Adapter (D-D):** `author_judge`/`get_judge → tool-judge_editor`, `run_eval → tool-verdict_card` (`adapter.py:26-59`). Both target types pre-exist in `registry.js` KNOWN_TOOLS → no new card types.
- **SSE event schema (D-B):** `assistant_delta | tool_call | tool_result | error | done`, frames `data: <json>\n\n` (`loop.py:12-18, 107-109`) — matches the ratified §10 frame contract verbatim.

No unauthorized surface drift. The §10 ratification was done (not grown around — the S-BS-51 discipline held).

```
# registry.js UNCHANGED this phase; both adapter targets pre-exist:
$ git diff 336c69a^..2944c55 -- apps/shell/src/genui/registry.js   →  (empty)
$ grep -nE 'tool-verdict_card|tool-judge_editor' apps/shell/src/genui/registry.js
26:  "tool-verdict_card",
30:  "tool-judge_editor",
```

---

## Q2 — Behavioral fidelity (spec → test → impl for 3 claimed behaviors)

### (a) A-SAFE — the agent cannot fire a paid run [THE CRUX] — CONFIRMED

Traced spec (§13 "A-SAFE … `run_eval`'s schema carries NO `confirm`/`in_process`/`live`") → test
(`test_run_eval_handler_never_forwards_a_paid_knob`) → impl (`tools.py:111-125` + `app.py:944-948`).

- `RUN_EVAL_SCHEMA = {"agent": str}` — no paid key (`tools.py:40`). The negative test injects all three paid keys into the tool args and asserts the bound op sees `{agent: ..., extra: {}}` — i.e. the handler reads `args.get("agent")` and nothing else (`tools.py:114`).
- The bound `_run_eval_replay` hardcodes the $0 path: `RunEvalRequest(agent=agent, live=False, in_process=False)` (`app.py:947`). This is the ONLY `live=/in_process=` literal in the new surface.
- `ChatRequest` has no paid knob (`app.py:231-237`). The shell `chatStream` POSTs `{message, agent}` only (`bff.js`), asserted by the Vitest `toHaveBeenCalledWith({message, agent}, …)`.

```
$ grep -rnE 'in_process\s*=\s*True|live\s*=\s*True|"confirm"|"in_process"|"live"' apps/bff/agent/ apps/bff/app.py | grep -vE '#|"""|Cache-Control'
apps/bff/agent/tools.py:43:PAID_KEYS = ("confirm", "in_process", "live")    # ← the negative-test tuple ONLY
$ grep -n 'RunEvalRequest(' apps/bff/app.py
215:class RunEvalRequest(BaseModel):
947:            RunEvalRequest(agent=agent, live=False, in_process=False),   # ← the ONLY run binding; $0
```

**Break attempts (all failed → A-SAFE holds):**
1. *A tool forwarding a paid arg?* No — `run_eval_handler` reads only `agent`; injected paid keys are dropped (negative-tested).
2. *An injected key the handler honors?* No — `_run_eval_replay(agent)` has the only call site, paid flags hardcoded False.
3. *The SSE route passing a paid param?* No — `ChatRequest` has no paid field; `_build_tool_context` resolves `live/in_process=False` in the closure.
4. *`ctx.run_eval_replay` actually doing a paid run?* No — it constructs `RunEvalRequest(live=False, in_process=False)`.
5. *The agent escaping its tools to the shell/filesystem?* No — `allowed_tools = [mcp__lithrim__{author_judge,get_judge,run_eval}]` (`loop.py:49`). `permission_mode="bypassPermissions"` is **safe** precisely because no Bash/Read/Write/WebFetch tool is granted — the agent's entire action surface is the 3 gate/replay-bounded MCP tools. INFERRED-then-CONFIRMED via the allowlist grep.

The only paid path is the human's in-DOM `CostModal` → `onRunEval(true)` → the EXISTING TopBar live path. The agent's SSE loop has no code path to `setPaid` or `onRunEval` (`panes.jsx`: the bolt `icon-btn onClick={() => setPaid({open:true})}` is human-only; the `onEvent` handler only appends text/parts). The Vitest `opening the in-DOM cost modal …` asserts `onRunEval` is called with `true` only via the modal confirm.

### (b) The conversation IS the audit log — CONFIRMED

Spec (R0 / §13 "every tool-call that writes config goes through the EXISTING audited path") → test
(`test_author_judge_tool_makes_an_audited_write`) → impl. The `author_judge` tool calls the FROZEN
`put_judge_endpoint`, which persists with an actor-attributed `AuditLog` record (`app.py:591-625`). The
test writes via the tool, then `GET /v1/audit?target_type=judge` returns a record with the actor +
target. **Negative side:** `test_off_lens_assignment_is_surfaced_not_bypassed` asserts an off-lens
assignment 422s, emits NO card, and leaves the audit stream EMPTY → no silent un-audited write.

```
records = client.get("/v1/audit", params={"target_type": "judge"}).json()["records"]
assert records == []   # nothing persisted -> nothing audited (no silent bypass)
```

### (c) The parts-adapter reuses the EXISTING cards — CONFIRMED

`adapter.py` emits only `tool-judge_editor` / `tool-verdict_card`, both pre-existing (Q1). The flat-spread
`output` follows the S-BS-19 convention. `registry.js` is byte-unchanged this phase. Vitest renders the
streamed `tool-verdict_card` and asserts "REJECT" shows via the existing `renderTool` registry (no new
component).

---

## Q3 — Out-of-scope intrusion — NONE FOUND. CONFIRMED.

- **No wrapped BFF op modified.** `app.py` diff has **zero `-` lines** (additive-only). `run_eval_endpoint` / `put_judge_endpoint` / `get_judge_endpoint` / `optimize_judge_endpoint` / `_apply_consensus` untouched.
- **No new gen-UI card type.** `registry.js`/`index.js` unchanged; adapter maps to 2 existing cards.
- **The full from-scratch journey (UAP-5c) did NOT leak in.** Only the 3-tool spine is wired; UAP-5c is registered as a STUB in `index.json` + `TASK_PACK` + a driver-file placeholder (deferred-not-dropped).
- **Every changed file maps to a D0–D7 deliverable** (15 files: pyproject `[agent]`, 4 agent modules, app.py SSE route, 3 shell files, 2 tests, 2 specs, 3 devloop bookkeeping). No drive-by formatting/dep bumps beyond `[agent]`.

```
$ git diff 336c69a^..2944c55 -- apps/bff/app.py | grep -E '^-' | grep -v '^---'   →  (none)
$ git diff 336c69a^..2944c55 -- <frozen set> | wc -l   →  0
```

---

## Q4 — Spec ambiguity / judgment calls the spec was silent on

1. **[OQ] `permission_mode="bypassPermissions`."** The spec mandates the *outcome* (the agent cannot spend/relabel/bypass) but is silent on the SDK permission knob. The impl chose `bypassPermissions` and made it safe-by-construction by granting only the 3 bounded MCP tools. This is sound (no escape surface) but is an implicit trust on the allowlist staying minimal — see NB-1.

2. **[OQ] The BYO-Claude cost label semantics.** The spec doesn't define how to report the SDK's `total_cost_usd` for a subscription user. The impl labels it "subscription-equivalent estimate (BYO-Claude desktop — not a per-call charge)" (`loop.py:40`; fold-4 cost-honesty). A reasonable, on-thesis call; not spec-dictated.

---

## Independently-verified load-bearing invariants

### A-SAFE — HOLDS (CONFIRMED). See Q2(a) for the 5 break attempts.

### A6 FROZEN 0-DELTA — HOLDS (CONFIRMED)
```
$ git diff 336c69a^..2944c55 -- lithrim_bench/runtime/council/compliance_council.py \
    lithrim_bench/runtime/council/judges_dspy.py lithrim_bench/runtime/council/judge_metric.py \
    lithrim_bench/runtime/council/authored_stage.py data/ontology/clinical_v1.json \
    data/config/agents/ws0_default.json | wc -l
0
$ git diff 336c69a^..2944c55 -- apps/bff/app.py | grep -E '^-' | grep -v '^---'
(no output)   # app.py is ADDITIVE-ONLY; existing handlers untouched
```

### IMPORT-ISOLATION — HOLDS (CONFIRMED)
```
$ python3 -c "import lithrim_bench.runtime.council; import sys; print('claude_agent_sdk' in sys.modules)"
False
# Even WITH the [agent] extra installed (debuglithrim), the lazy import holds:
$ PYENV_VERSION=debuglithrim python -c "import sys; sys.path.insert(0,'apps/bff'); import agent; print('claude_agent_sdk' in sys.modules)"
False
$ PYENV_VERSION=debuglithrim python -c "import sys; sys.path.insert(0,'apps/bff'); import app;   print('claude_agent_sdk' in sys.modules)"
False
```
The SDK is pulled only inside `build_sdk_tools` / `_build_options` / `_real_source` / `run_chat`
(lazy `from claude_agent_sdk import …`), and `app.py`'s `from agent import …` is also lazy (inside the
route/builder). `test_agent_package_does_not_pull_the_sdk_at_import` asserts this in a fresh subprocess.

### PYDANTIC-SETTINGS NON-REGRESSION — HOLDS (CONFIRMED)
```
$ PYENV_VERSION=debuglithrim python -c "import pydantic_settings; print(pydantic_settings.__version__)"
2.14.1
$ PYENV_VERSION=debuglithrim python -m pytest lithrim_bench/runtime/council/tests/ tests/test_ws5_bff.py -q
128 passed, 3 skipped   # 3 skips = live-Azure (LITHRIM_LLM_PROVIDER unset) — expected
```
The transitive 2.1→2.14 bump the `[agent]` extra pulls does NOT regress the council/BFF suites.

### TESTS GREEN — CONFIRMED (actual counts)
```
$ PYENV_VERSION=debuglithrim python -m pytest tests/test_uap5b_chat.py -q
8 passed, 1 warning            # (the stub-source loop test runs here; it skips on default py — see below)
$ python3 -m pytest tests/ -q
287 passed, 11 skipped         # skips: dspy/openai not installed + 1 [agent]-extra skip (test_uap5b_chat:173) — all expected on default deps
$ cd apps/shell && npx vitest run src/panes.chat.test.jsx
2 passed (1 file)
```
`claude_agent_sdk == 0.2.90` under debuglithrim (within the `>=0.2.90,<0.3` cap).

### A-LIVE is SKIP (owed, USER-RUN) — CORRECT (CONFIRMED)
No service autostarted; no `:5180`/`:8787` attestation fired by the executor (per R3 / no-autostart). The
loop is built DRIVEABLE: the paid gate is the in-DOM `CostModal` (NOT `window.confirm`), Chrome-MCP-
driveable per `browser-mcp-confirm-blocks-renderer`. This is the correct posture, not a gap. The A-LIVE
attestation is the monitor's to schedule at close (→ owed; track as the close-blocking user-run, S-BS-79).

### BYO-CLAUDE GUARDRAIL — HOLDS (CONFIRMED)
```
$ grep -rniE 'api_key|anthropic_api_key|sk-ant|bearer|ANTHROPIC_' apps/bff/agent/ apps/bff/app.py apps/shell/src/{bff.js,panes.jsx,components/CostModal.jsx}
(no output)   # no API-key path; local-CLI / desktop BYO-Claude only
```
`_build_options`/`_real_source` pass no `api_key` to `ClaudeAgentOptions`/`ClaudeSDKClient` — the SDK
inherits the local `claude` CLI / desktop auth. No hosted/multi-tenant key path → the licensing guardrail
holds. (D0's `ANTHROPIC_API_KEY`-unset proof is asserted in the spec; the code carries no key requirement.)

### ruff — CONFIRMED clean
```
$ python3 -m ruff check apps/bff/agent/ apps/bff/app.py tests/test_uap5b_chat.py
All checks passed!
```

---

## Findings

- **[NON-BLOCKING] NB-1 — `bypassPermissions` is safe-by-allowlist, not safe-by-mode.** The A-SAFE guarantee leans on `allowed_tools` staying exactly the 3 bounded MCP tools (`loop.py:49`). If a future cycle (UAP-5c) adds a tool that wraps a paid/destructive op, or widens the allowlist to a built-in (Bash/Write), `bypassPermissions` would auto-approve it. Recommend UAP-5c carry an explicit test that the allowlist contains no built-in tools and no paid-capable wrapper. CONFIRMED (mechanism); HYPOTHESIS (future risk). Not blocking this cycle.

  ```
  loop.py:49  allowed = [f"mcp__lithrim__{name}" for _, name, *_ in _TOOL_SPECS]
  loop.py:53  permission_mode="bypassPermissions",  # safe ONLY while _TOOL_SPECS stays gate/replay-bounded
  ```

- **[NON-BLOCKING] NB-2 — `author_judge` tool hardcodes `validator_refs=[]` and `model=""`.** The tool can assign a flag lens but cannot bind a model or attach validators through the conversation (`app.py:927`). This is a reasonable spine-scoping call (the spec's CORE is "the audited assignment write"), but it means a conversationally-authored judge is model-unbound until a click-path PUT binds one. INFERRED. Flag for UAP-5c's tool-surface expansion; not a spec violation (the spine is explicitly minimal).

- **[NON-BLOCKING] NB-3 — the verdict-card `agreement`/`confidence` projection is best-effort.** `verdict_part` (`adapter.py:31-59`) computes agreement off `votes[0]` and averages confidences, defaulting to "—" when the replay record has no council votes (the WS-0 replay path). Cosmetic for the demo card; the load-bearing field (`verdict`) is projected correctly (test asserts "REJECT"). CONFIRMED. Non-blocking.

- **[NON-BLOCKING] NB-4 — default-vs-debuglithrim test-count nuance (not a defect).** On default `python3`, `test_uap5b_chat.py` reports the stub-loop test as 1 skip (`needs the [agent] extra`); under debuglithrim it runs → 8 passed. The driver's "uap5b" count is therefore 8 (debuglithrim) / 7+1skip (default). Both are green; noting so the close doesn't read the skip as a failure. CONFIRMED.

- **[OPEN-QUESTION] OQ-A — the BYO-Claude D0 proof is asserted, not re-runnable by the critic.** The spec + session log claim a trivial `ClaudeSDKClient` + one `@tool` ran with `ANTHROPIC_API_KEY` unset. I confirmed `claude_agent_sdk==0.2.90` is importable under debuglithrim and that the code carries no API-key path, but the live D0 run itself is not a CI artifact (correctly — it's BYO-Claude/desktop). This folds into the A-LIVE user-run attestation. Not blocking (the import-isolation + no-key-path are independently verified); the live confirmation rides A-LIVE.

- **[OPEN-QUESTION] OQ-B — `permission_mode` / cost-label are executor judgment calls the spec was silent on.** See Q4. Both are sound; recording so the close ratifies them rather than treating them as drift.

---

## Bottom line

Spine + 3-tool CORE built faithfully to the driver and the LOCKED §13/R11 + §10 contract. The two
gate-deciders — **A-SAFE (no agent-initiated paid path)** and **A6 (frozen 0-delta)** — both hold under
adversarial verification. Import-isolation, the pydantic-settings non-regression, the BYO-Claude
no-API-key guardrail, ruff, and all four test suites are green. No out-of-scope intrusion; UAP-5c
correctly deferred as a stub. The A-LIVE `:5180` conversational attestation is owed + USER-RUN (built
driveable via the in-DOM CostModal) — that is the correct no-autostart posture, the close-blocking item to
schedule. Findings are all NON-BLOCKING or OPEN-QUESTION.

**VERDICT: NON-BLOCKING [0 BLOCKING / 4 NB / 2 OQ].**
