# Fresh-Critic Critique — bench-salvage phase ONB-0 (conversational memory)

**VERDICT: NON-BLOCKING [0 BLOCKING / 2 NB / 1 OQ]**

Range reviewed: `e8c52e1..34efd72` (6 commits). HARD-GATE, fresh critic, no prior context.
All five claims (C1–C5) verified adversarially — scratch-reverts proved the two load-bearing
A-SAFE negatives genuinely guard their property. The single remaining gate (A1/A-LIVE) is a
USER-RUN, correctly deferred and marked SKIP by the executor (it is unscheduleable by the
executor — the agent can never fire a paid run). Tree restored byte-identical after probes;
HEAD unmoved.

---

## C1 — D-A: SDK signature + by-construction no-re-execution proof (THE load-bearing claim) — CONFIRMED

**Evidence (installed SDK):**
```
VERSION 0.2.90
SIG (self, prompt: str | collections.abc.AsyncIterable[dict[str, typing.Any]], session_id: str = 'default') -> None
FILE .../debuglithrim/lib/python3.10/site-packages/claude_agent_sdk/client.py
```
The executor's claim (v0.2.90, `query(str | AsyncIterable[dict])`) is exact.

**Evidence (the str path in the SDK — what `query(str)` actually sends):**
```python
if isinstance(prompt, str):
    message = {
        "type": "user",
        "message": {"role": "user", "content": prompt},
        "parent_tool_use_id": None,
        "session_id": session_id,
    }
    await self._transport.write(json.dumps(message) + "\n")
```
A `str` prompt is wrapped in a single **user** message. There is no code path by which a string
can become a `tool_use` block or an assistant-role turn. Tool invocation in this SDK happens only
when the *model* emits a tool_use block in its response — never from the request content.

**Evidence (the fold returns a plain str, passed straight to query):**
`apps/bff/agent/loop.py:71` `_fold_history(message, history) -> str` builds `"\n".join(lines)`
from `[speaker] content` text lines (reads only `turn.get("content")`/`turn.get("role")`).
`apps/bff/agent/loop.py:109` `await client.query(_fold_history(message, history))` — the SAME
`query(str)` call shape as the pre-cycle `await client.query(message)`. The str is the only
thing that changes; the call shape is identical.

**Evidence (native seed / session_resume NOT used):**
```
$ grep -rn "session_resume|resume|import_session|AsyncIterable|fork" apps/bff/agent/loop.py apps/bff/app.py
(no matches)
```
`ClaudeAgentOptions` exposes `resume`, `continue_conversation`, `fork_session`, `session_id`,
`session_store` — NONE are set by `_build_options` (unchanged from pre-cycle). The
`AsyncIterable[dict]` seed path is not used.

**Finding:** The no-re-execution guarantee is genuinely **by construction**: history → `str` →
user-message-only → cannot carry a tool_use block → cannot re-invoke a tool or re-spend. The
preamble's "do not re-run" sentence is correctly characterized (in code + commit body + spec) as
belt-and-suspenders, NOT the proof. I tried to find any path where threaded history re-fires a
tool or hits a paid call: none exists. Defense-in-depth: `ChatTurn(extra="forbid")` +
`model_dump()` means even the dict reaching the fold is `{role, content}` only; and `_fold_history`
would ignore extra keys regardless. **CONFIRMED.**

---

## C2 — A6 frozen 0-delta — CONFIRMED

**Evidence (frozen set diff is EMPTY):**
```
$ git diff e8c52e1..34efd72 --stat -- apps/bff/agent/tools.py apps/bff/agent/adapter.py 'lithrim_bench/runtime/council/' data/
(empty)
```
The 8-tool surface (`tools.py`/`adapter.py`), the entire `runtime/council/` tree (which is where
`judge_metric`, `_apply_consensus`, `signals`, `withstands`, the per-judge seam live — confirmed
via grep), and all committed seeds under `data/` are byte-identical.

**Evidence (app.py confined to the chat surface):**
```
$ git diff ... -- apps/bff/app.py | grep -E "^@@|^\+class |^\-class "
@@ -57,12 +57,12 @@ import json          (Literal + ConfigDict imports only)
@@ -228,12 +228,26 @@ class OptimizeRequest(BaseModel):
+class ChatTurn(BaseModel):
@@ -1087,8 +1101,11 @@ async def chat_endpoint(
```
Exactly three hunks: the import line, the `ChatTurn` insert + `ChatRequest.history` extension, and
`chat_endpoint`. No wrapped BFF op (`put_agent_endpoint`/`eval_pack_run_endpoint`/
`run_eval_endpoint`/`get_*_endpoint`) is touched. `grep -nE "judge_metric|_apply_consensus|seam"`
over the app.py/loop.py diffs returns nothing.

**Evidence (chat_endpoint adds only the thread):**
```python
history = [t.model_dump() for t in req.history]
...
async for event in run_chat(req.message, ctx, history=history):
```
The actor/ctx build, the lazy SDK import, the SSE wrapper, and the StreamingResponse headers are
all unchanged.

**Evidence (tool set stays exactly 8 — non-vacuous, exact set-equality):**
`tests/test_uap5b_chat.py:253` asserts `names == {author_judge, get_judge, run_eval, get_agent,
author_flag, review_runs, run_eval_pack, assemble_agent}` (8). Passes (see C4). **CONFIRMED.**

---

## C3 — A-SAFE tests are NON-VACUOUS — CONFIRMED (both load-bearing negatives proved via scratch-revert)

### (a) No-re-execution negative — `test_replaying_history_triggers_no_new_audited_write` — load-bearing

The test drives `run_chat(..., history=<describes a prior author_judge>, source=_benign_stub)` and
asserts `GET /v1/audit` count is unchanged (real BFF op over a tmp config DB — NOT mocked). It
guards that `run_chat`'s own body does not iterate history into tool executions.

**Scratch-revert (injected the FORBIDDEN re-execution into `run_chat`):**
```python
for _t in history or []:
    if _t.get("role") == "assistant" and "author_judge" in (_t.get("content") or ""):
        ctx.author_judge(role="risk_judge", assigned_flags=[], rationale="replayed")
```
**Result — test FAILED:**
```
>       assert after == before
E       assert 1 == 0
tests/test_onb0_memory.py:227: AssertionError
```
The audit count went 0→1 through the real audit endpoint. File restored (`git checkout --`),
tree confirmed clean. **Genuinely load-bearing** for the "run_chat does not replay writes"
property. (Caveat NB-1 below: the stub-source design means this test alone does not exercise the
`_real_source` fold-to-str path — that property is covered separately by C1's structural proof +
`test_fold_history_is_plain_text...`. The two together are sufficient; the audit test is not the
sole guard of the by-construction proof, and the executor's own evidence text says so.)

### (b) `ChatTurn(extra="forbid")` rejection — `test_chat_turn_rejects_a_smuggled_paid_knob` — load-bearing

**Scratch-revert** (`extra="forbid"` → `extra="ignore"` in app.py). **Result — test FAILED:**
```
>           with pytest.raises(ValidationError):
E           Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
tests/test_onb0_memory.py:104: Failed
```
With `extra="ignore"`, a smuggled `{confirm:True}`/`{live:True}`/`{in_process:True}`/`{agent:x}`
is silently accepted — exactly the smuggling the test forbids. File restored, tree clean.
**Genuinely load-bearing.** (The companion `test_chat_turn_role_is_constrained` still passed under
the revert — correct: `Literal` enforcement is independent of `extra`.)

### (c) Back-compat + fold-is-text units — present and passing

`test_chat_request_history_defaults_empty_back_compatible` (history defaults `[]`),
`test_back_compat_no_history_still_yields_done` (no-history still yields the `done` event),
`test_fold_history_empty_returns_the_bare_message` (no history → the bare message str),
`test_fold_history_is_plain_text_with_the_current_ask_last` (str, `"tool_use" not in folded`,
current ask last, empty turn dropped). All genuine assertions on real behavior.

**Finding: CONFIRMED non-vacuous.**

---

## C4 — Independently RE-RUN suites (REAL numbers)

| Suite | Command | Result |
|---|---|---|
| onb0 + uap5b | `PYENV_VERSION=debuglithrim pytest tests/test_onb0_memory.py tests/test_uap5b_chat.py -q` | **17 passed** |
| onb0 alone | `PYENV_VERSION=debuglithrim pytest tests/test_onb0_memory.py -q` | **8 passed** |
| onb0 + uap5b + uap5c | `... tests/test_uap5c_journey.py` | **29 passed** |
| import-isolation + 8-tool (default 3.12.8) | `pytest ...test_agent_package_does_not_pull_the_sdk_at_import ...test_tool_set_is_the_uap5c_journey_set` | **2 passed** |
| import-isolation (debuglithrim) | same, debuglithrim | **1 passed** |
| Vitest | `cd apps/shell && npx vitest run src/panes.chat.test.jsx` | **4 passed** (node_modules present) |
| ruff | `ruff check apps/bff/app.py apps/bff/agent/loop.py tests/test_onb0_memory.py` | **All checks passed!** |

All green. The "29 passed" matches the session log. NB-2: the session log's `diagnostic_stats`
and commit-4 body state `test_onb0_memory.py` has **"10 tests"**; it collects **8** (verified by
`--collect-only` and a standalone run). Cosmetic count inaccuracy, not a coverage gap — the 8
tests cover every claimed property.

---

## C5 — Scope: no Phase-1/2 leak — CONFIRMED

**Evidence:**
```
$ git diff ... -- apps/ | grep -inE "\bmode\b|curriculum|capabilit|session_id|teach|operate" | grep -vE "model_dump|model_config"
119:+    # ... (The Phase-1 `mode` field is NOT here.)
```
The only `mode` hit is the comment asserting `mode` is OUT. No `curriculum`/`capabilities`/server
`session_id`/`teach`/`operate` functional code. No new gen-UI card-type file (registry/genui/card
files absent from the diff name list). `ChatRequest` = `{message, agent, history}` only;
`history: list[ChatTurn] = []` is back-compatible (an old `{message, agent}` client validates —
`test_chat_request_history_defaults_empty_back_compatible` passes). **CONFIRMED.**

---

## Safety attestation

- Two scratch-reverts performed (app.py `extra=`, loop.py `run_chat`), each on ONE committed file,
  each restored via `git checkout -- <exact path>`. `git status --short` confirmed clean before
  and after each.
- Final tree: only the pre-existing uncommitted `.devloop/` monitor files + `.claude/` +
  research/template untracked files (none touched by me — a concurrent monitor session owns
  `.devloop/personas/MONITOR.md` etc.). HEAD unmoved at `34efd72`.
- No `git add`/`commit`/`push`/`stash`/`reset`/`clean`/`checkout .`; no source modified as a "fix".

---

## Findings ledger

**BLOCKING (0):** none.

**NON-BLOCKING (2):**
- **NB-1 (test-design observation, not a defect):** `test_replaying_history_triggers_no_new_audited_write`
  uses a stub source, so it guards `run_chat`'s no-iterate-history-into-writes property but does NOT
  itself exercise the `_real_source` fold-to-str path. That path's safety is established structurally
  (C1: SDK `query(str)` → user-message-only) + by `test_fold_history_is_plain_text...`. The
  combination is sufficient and the executor's evidence is honest about it ("offline proxy … the
  live ≥6-turn run asserts GET /v1/audit shows exactly one record"). No change required; the live
  A-LIVE one-record assertion (sharpening 2) is the right end-to-end closer.
- **NB-2 (doc accuracy):** session log `diagnostic_stats.test_counts` + commit-4 body say
  `test_onb0_memory.py` has "10 tests"; it has **8**. Cosmetic; correct at close.

**OPEN QUESTIONS (1):**
- **OQ-1 (gate ownership — by design):** A1/A-LIVE (the ≥6-turn live coherence + the
  one-audit-record no-re-execution check on `:5180`) is USER-RUN and remains owed (executor marked
  it SKIP, correctly — the executor cannot fire it). This is the actual decider for "memory coherence
  in practice." It is built-driveable (no new `window.confirm`; paid gate = the in-DOM CostModal,
  unchanged → Chrome-MCP-driveable). The monitor must schedule it (persistent BFF) + the proof
  capsule before `/devloop-close-phase`. Not blocking the code gate; blocking the phase-close.

---

## Diagnostic (not gates)
- Replay mechanism shipped: **transcript-preamble fold** (`_fold_history`), not the native seed —
  verified the native `AsyncIterable[dict]`/`resume`/`fork_session` paths are unused.
- No-re-execution proof: **by construction** (str → user-message-only), re-derived from SDK source.
- History cap: **NONE** (replay all; empty-content turns dropped). Text-only content.
