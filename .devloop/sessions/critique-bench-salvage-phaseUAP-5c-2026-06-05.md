# Fresh-Critic Critique — `bench-salvage` phase `UAP-5c` (the full Domain→Judge→Flag→Run→Review journey, R11)

> **HARD-GATE fresh critic.** No prior implementation context. Spec + driver + diff read COLD; every
> executor claim re-verified from source. Critic ran read-only commands/tests + a non-vacuity revert in a
> scratch tree; wrote only this doc. Diff under review: `9cac025..9227b87` (7 commits a4e313d..9227b87).
> Parent `9cac025` (docs-only monitor commit) NOT reviewed. Date: 2026-06-05.

**VERDICT: NON-BLOCKING [0 BLOCKING / 1 NB / 1 OQ].**

All six load-bearing invariants the kickoff named HOLD, each verified from source (not from the session log):

- **A-SAFE (the crux): HOLDS** (CONFIRMED — I tried to reach a paid run, an un-audited write, and a gate bypass from all three new tools; every path is closed. The only `live=/in_process=` literal the agent can reach is the hardcoded `False,False` in `_run_eval_replay`; the two paid-capable ops — `eval_pack_run_endpoint` (`live`) and `put_agent_endpoint` (WRITE) — are wrapped by **no** tool/closure this cycle, the D-F SPLIT.).
- **A6 frozen 0-delta: HOLDS** (CONFIRMED — `git diff` over the council/seed set == 0 lines; all **10** named BFF ops are **byte-identical** parent→HEAD via AST extraction, incl. `get_judge_endpoint`; both `app.py` hunks are strictly inside `_build_tool_context`).
- **S-BS-82 fix correctness: HOLDS** (CONFIRMED — the `FieldInfo.split` crash reproduced verbatim against the real frozen endpoint; the fix is wrapper-only; the regression test is **NON-VACUOUS** — it drives the bound closure, which raises pre-fix).
- **S-BS-81 allowlist-bounds: HOLDS** (CONFIRMED — both the structural test and the `[agent]`-gated real-`ClaudeAgentOptions` test assert the exact `mcp__lithrim__*` set, no built-in, no wildcard, no paid knob across all 6 schemas).
- **Import-isolation: HOLDS** (CONFIRMED — `claude_agent_sdk` absent from `sys.modules` after `import app` on BOTH default python AND debuglithrim *with the extra installed* — proving lazy import, not mere absence).
- **BYO-Claude: HOLDS** (CONFIRMED — no `api_key` anywhere in `apps/bff/agent/`; `ClaudeAgentOptions`/`ClaudeSDKClient` built without a key).

---

## Re-run test counts (critic-run, hermetic, no service autostarted)

| Suite | Command | Result |
|---|---|---|
| Default python | `python3 -m pytest tests/ -q` | **293 passed, 12 skipped** |
| debuglithrim ([agent]) | `PYENV_VERSION=debuglithrim python -m pytest tests/test_uap5c_journey.py tests/test_uap5b_chat.py tests/test_ws5_bff.py lithrim_bench/runtime/council/tests/ -q` | **143 passed, 3 skipped** (3 live-Azure skips) |
| Shell Vitest | `cd apps/shell && npx vitest run` | **51 passed (11 files)** |
| ruff | `ruff check <changed .py>` | **All checks passed!** |

All four match the executor's claimed counts (session log §A7: 293/12, 143/3, 51) exactly. The 12 default skips are dspy/openai-absent + the two `[agent]`-gated tests; the 3 debuglithrim skips are live-Azure go-gated.

---

## Q1 — Surface fidelity (the 3 new SDK-MCP tools, schemas, adapter, loop)

**Match to driver §2 D2/D4/D5 + spec §13/§10: faithful.** CONFIRMED. No unauthorized surface drift.

- **Tool set (D-A):** `_TOOL_SPECS` = `{author_judge, get_judge, run_eval, get_agent, author_flag, review_runs}` — the UAP-5b spine + the 3 journey tools (`tools.py` `_TOOL_SPECS`; asserted by `test_tool_set_is_the_uap5c_journey_set`). The heavy `assemble_agent`/`run_eval_pack` legs are absent — the D-F SPLIT (pre-authorized, driver §3/§4; session log plan_review row 4).
- **Schemas (SDK-free, paid-knob-free):** `GET_AGENT_SCHEMA={"name":str}`, `AUTHOR_FLAG_SCHEMA={"flag_code":str,"tier":str,"gradeable":bool,"rationale":str}`, `REVIEW_RUNS_SCHEMA={"limit":int}` (`tools.py`). None carries a `PAID_KEYS` member.
- **Adapter (D-B/D-D):** `get_agent→tool-agent_editor` (`{agent}`), `author_flag→tool-flag_editor` (`{agent}`), `review_runs→tool-audit_log` (`{runId}`) (`adapter.py` `agent_part`/`flag_part`/`audit_part`). All three targets pre-exist in `registry.js` `KNOWN_TOOLS`; the registry is **byte-unchanged** this cycle → no new card types (A4).
- **Loop (D5):** `_SYSTEM_PROMPT` names all six tools + the explicit Domain→Judge→Flag→Run→Review order + the "NEVER fire a paid run / surface errors plainly" invariant; `max_turns` 8→12 (`loop.py`; plan_review row 2). The §10 + §13 ratification was done in-band (S-BS-51 ratify-don't-grow discipline held).

```
$ git diff 9cac025 9227b87 -- apps/shell/src/genui/registry.js   →  (empty)   # A4: no new card type
$ sed -n '23,33p' apps/shell/src/genui/registry.js
  "tool-flag_editor",  …  "tool-agent_editor",  "tool-audit_log",  "tool-judge_editor",  "tool-run_panel",
```

**Disposition (not a defect):** the Review leg renders `tool-audit_log` rather than `tool-run_panel`. The driver D-D offered either. The executor's verify-first gate (plan_review row 1) found `RunPanel.jsx:57 if (m.paid && !window.confirm(COST_CONFIRM)) return;` — a `window.confirm`-gated paid Run (S-BS-80) — and chose the pure-read `tool-audit_log` so the Review leg adds **no** agent-adjacent paid surface. This *strengthens* A-SAFE; a correct judgment call, ratified in §10.

---

## Q2 — Behavioral fidelity (spec → test → impl for the load-bearing behaviors)

### (a) A-SAFE — no agent path to a paid run [THE CRUX] — CONFIRMED

Traced spec (§13 "A-SAFE … no tool can fire a paid run"; driver A-SAFE §5:179) → tests (`test_no_tool_schema_carries_a_paid_knob`, `test_build_options_carries_exactly_the_bounded_allowlist_under_bypass`, `test_author_flag_unknown_flag_is_surfaced_not_bypassed`) → impl (`tools.py` schemas + `app.py` `_run_eval_replay`/`_author_flag`/`_review_runs`).

**Break attempts (all failed):**

1. *A new tool wraps a paid-capable op?* **No.** `grep` across `apps/bff/agent/` + the closures for `eval_pack_run_endpoint` / `EvalPackRunRequest` / `put_agent_endpoint` → **empty**. The two paid-capable ops are not reachable from any tool. The SPLIT (D-F) means there is literally no paid-capable wrapper this cycle.
2. *The agent sets `live`/`in_process` through `run_eval`?* **No.** `RUN_EVAL_SCHEMA={"agent":str}` (no paid key); `_run_eval_replay` is the only binding and hardcodes the $0 path:
   ```
   app.py:952  def _run_eval_replay(agent: str) -> dict:
   app.py:954      RunEvalRequest(agent=agent, live=False, in_process=False),   # ← the ONLY run binding; $0
   ```
3. *A paid knob hides in a NEW schema?* **No.** `test_no_tool_schema_carries_a_paid_knob` iterates **all** `_TOOL_SPECS` and asserts `PAID_KEYS ∩ schema == []`. I re-ran it: PASSED. (The UAP-5b critique NB-1 — "the no-paid-knob test only checked `RUN_EVAL_SCHEMA`" — is now closed: it is generalized across all 6 tools.)
4. *The agent escapes its tools to the shell/FS via `bypassPermissions`?* **No.** `_build_options` (`loop.py:57`) derives `allowed=[f"mcp__lithrim__{name}" for _,name,*_ in _TOOL_SPECS]` — purely the bounded set, no built-in, no wildcard. The `[agent]`-gated test asserts `list(opts.allowed_tools)==expected` against the real `ClaudeAgentOptions` AND `set(allowed).isdisjoint(BUILTIN_TOOLS)`. I re-ran it under debuglithrim (extra installed, so it does NOT skip): PASSED.
5. *`review_runs` mutates or spends?* **No.** Both legs are pure reads: `list_runs_endpoint` (`PIPELINE_RUNS.list_all`) + `get_run_audit_endpoint` (`PIPELINE_RUNS.get`); the closure only reads + threads the latest `run_id` to the card.

```
$ grep -rn "eval_pack_run_endpoint|EvalPackRunRequest|put_agent_endpoint" apps/bff/agent/ + the closures
   →  (no match)   # no agent-reachable paid-capable op this cycle
```

### (b) A2 — the conversation IS the audit log (R0); no un-audited write — CONFIRMED, non-vacuous

Traced spec (§2B "every authoring action → an immutable AuditRecord"; driver A2 §5:175) → test (`test_full_journey_…_is_audited`: `{"ontology","judge"} <= targets`) → impl (`put_ontology_endpoint` always emits an `AuditRecord`, `app.py:742-751`; `author_flag` writes only through it).

I drove `author_flag` + `author_judge` against a tmp config DB and read `GET /v1/audit` directly — **two** actor-attributed records appear:
```
('test-sme', 'edit',   'ontology', 'uap5c_test')
('test-sme', 'author', 'judge',    'risk_judge')
=> {ontology, judge} ⊆ targets : True
```
The negative path is real too: `test_author_flag_unknown_flag_is_surfaced_not_bypassed` — an unknown flag → 404 surfaced, **no card emitted** (`ctx.parts == []`), **nothing persisted** (`GET /v1/audit?target_type=ontology` → `[]`). I re-ran it: PASSED. No silent un-audited write.

### (c) author_flag cannot bypass the snapshot author-gate — CONFIRMED

Traced spec (CLAUDE.md core invariant "never silently score a flag the contract-of-record has not blessed"; driver A3 §5:176) → impl (`_validate_ontology`, `app.py:691-711`). `put_ontology_endpoint` calls `_validate_ontology(ontology)` **before** any write (`app.py:734`). Check 2 (`app.py:704-710`) rejects a `gradeable` flag outside `taxonomy_snapshot.json` with 422. `author_flag` re-PUTs the **whole** ontology, so the entire body is re-validated on every edit — a `gradeable=true` flip outside the snapshot 422s and is surfaced by `author_flag_handler` ("The ontology was NOT changed (the snapshot/structural gate held)"). The agent cannot relabel/re-grade past the gate.

### (d) S-BS-82 — the bound get_judge fix + the test that actually catches it — CONFIRMED

The kickoff's sharpest probe: *does the regression test exercise the BOUND closure (catches) or only the TestClient (would NOT, because the router resolves `Query(None)→None`)?*

- **The bug is real.** `get_judge_endpoint:559` `assigned_flags: str | None = Query(None,…)`; `:580` `if assigned_flags is not None`; `:581` `assigned_flags.split(",")`. Called as a plain function (no router), `assigned_flags` is a `Query` FieldInfo → `is not None` → `.split` raises. I reproduced it against the **real frozen endpoint**:
  ```
  PRE-FIX  get_judge_endpoint("risk_judge", agent="t", db_path=d, workdir=wd)   [assigned_flags omitted]
     → AttributeError: 'Query' object has no attribute 'split'
  POST-FIX get_judge_endpoint("risk_judge", agent="t", assigned_flags=None, db_path=d, workdir=wd)
     → dict (assigned_flags=[])
  ```
- **The fix is wrapper-only.** `_get_judge` (`app.py:948-950`) now passes `assigned_flags=None` explicitly; `get_judge_endpoint` is byte-identical (A6). The binding rule is recorded as a comment (`app.py:943-947`).
- **The test catches it.** `test_get_judge_tool_returns_a_summary_not_a_fieldinfo_crash` (`test_uap5b_chat.py:170-181`) calls **`ctx.get_judge(role="risk_judge")`** at line 180 — the *raw bound closure*, the exact live path — not just the TestClient. Since the bound closure pre-fix used the crashing call shape, the test is **NON-VACUOUS**: the line-180 assertion would raise `AttributeError` against reverted-fix code. (I confirmed line 116 `get_judge_handler` also routes through `ctx.get_judge`, so even the handler arm exercises the closure.) This is precisely the test the offline UAP-5b 8/8 missed.

---

## Q3 — Out-of-scope intrusion

**None.** The diff touches exactly 11 files, all in driver §2 deliverables or §2 D7 (docs/session):

```
.devloop/sessions/session-bench-salvage-phaseUAP-5c-2026-06-05.json   (D7)
apps/bff/agent/{__init__,adapter,loop,tools}.py                        (D2/D4/D5)
apps/bff/app.py                                                        (D1 + D2 closures)
apps/shell/src/panes.chat.test.jsx                                     (D6 Vitest)
docs/specs/SPEC_PRODUCT_SHELL.md  +  SPEC_UNIFIED_AUTHORING_PRODUCT.md  (D7)
tests/test_uap5b_chat.py  +  tests/test_uap5c_journey.py              (D6)
```

- **Frozen set untouched:** `grep` over the touched files for `compliance_council|judges_dspy|judge_metric|authored_stage|withstands|signals|clinical_v1|ws0_default|taxonomy_snapshot` → **NONE**.
- **`app.py` is closure-local:** the only deletion line is the old `_get_judge` call (the S-BS-82 fix, the one allowed touch); the additions are `_get_agent`/`_author_flag`/`_review_runs` + the three `ToolContext` kwargs — all inside `_build_tool_context`. No op handler line touched. No drive-by formatting / dep bump.

The two spec edits are *required* by D7 (ratify the grown set into §10/§13), not intrusion.

---

## Q4 — Spec ambiguity surfaced / judgment calls

**OQ-1 (for the spec author) — `author_flag` is EDIT-ONLY; "the full journey from scratch" creates judges from scratch but only *edits* pre-existing flags.** The driver's title is "…from-scratch," and §2 D2 describes `author_flag` over `PUT /v1/ontology` without specifying create-vs-edit. The executor (plan_review row 3, user-approved) worded the tool "EDIT AN EXISTING flag's tier/gradeable … does NOT create a flag or invent owners," and `_author_flag` raises 404 on an unknown flag (`app.py`). This is the **correct safety posture** — creating a gradeable flag needs `owner_roles` + a snapshot refresh, which must stay a deliberate human act (CLAUDE.md owner↔emit invariant), and an agent fabricating `owner_roles` would be exactly the kind of un-blessed scoring the repo exists to prevent. It is tracked as **S-BS-83** (session log). Surfaced so the spec author can decide whether the "from-scratch" vision eventually wants a *separate* create-flag tool that authors (not fabricates) owners — not a defect this cycle.

**NB-1 (carried, unchanged) — NB-2 model-bind + NB-3 verdict-projection deferred.** `author_judge` stays model-unbound (`model=""` at the UAP-5b binding); `verdict_part` agreement/confidence still default to `"—"` on replay. Both are orthogonal to the journey, were explicitly deferred at plan-review (rows 5), and are not required by any UAP-5c acceptance criterion. Carried forward; non-blocking.

---

## Independently-verified load-bearing invariants (verbatim evidence)

### A-SAFE — HOLDS (CONFIRMED)
```
# (1) no agent-reachable paid-capable op (the D-F SPLIT):
$ grep -rn "eval_pack_run_endpoint|EvalPackRunRequest|put_agent_endpoint" apps/bff/agent/  →  (empty)
# (2) the only run binding hardcodes $0:
app.py:954   RunEvalRequest(agent=agent, live=False, in_process=False)
# (3) no paid knob in ANY schema (re-ran): test_no_tool_schema_carries_a_paid_knob  PASSED
# (4) the runtime allowlist is the bounded set, bypassPermissions safe:
loop.py:57   allowed = [f"mcp__lithrim__{name}" for _, name, *_ in _TOOL_SPECS]
loop.py:61   permission_mode="bypassPermissions"   # safe iff allowed stays bounded — asserted
# (5) writes go only through the audited+validated PUT:
app.py:734   _validate_ontology(ontology)     # 422 before any write (snapshot gate)
app.py:742   AuditLog(db_path=db_path).record(AuditRecord(actor=actor, action="edit", target=ontology, …))
```

### A6 frozen 0-delta — HOLDS (CONFIRMED)
```
$ git diff 9cac025 9227b87 --stat -- council/{compliance_council,judges_dspy,judge_metric,authored_stage}.py \
      data/ontology/clinical_v1.json data/config/agents/ws0_default.json   →  (empty)
# AST byte-identity of all 10 named BFF ops, parent vs HEAD:
get_judge_endpoint        IDENTICAL (4aa4ff8f76 == 4aa4ff8f76)
put_judge_endpoint        IDENTICAL      run_eval_endpoint         IDENTICAL
put_ontology_endpoint     IDENTICAL      put_agent_endpoint        IDENTICAL
get_agent_endpoint        IDENTICAL      eval_pack_run_endpoint    IDENTICAL
list_runs_endpoint        IDENTICAL      get_run_audit_endpoint    IDENTICAL
get_audit_endpoint        IDENTICAL
# app.py deletion lines (only the old _get_judge call, inside the closure):
$ git diff … apps/bff/app.py | grep '^-' | grep -v '^---'  →  only "-        return get_judge_endpoint(role, agent=req_agent, db_path=db_path, workdir=workdir)"
```

### S-BS-82 — fix correct + test non-vacuous — HOLDS (CONFIRMED)
```
# reproduced against the REAL frozen endpoint:
PRE-FIX   get_judge_endpoint(role, agent=…, db_path=…, workdir=…)  → AttributeError: 'Query' object has no attribute 'split'
POST-FIX  get_judge_endpoint(role, agent=…, assigned_flags=None, …) → dict
# the regression test drives the bound closure (the live path), not just the TestClient:
test_uap5b_chat.py:180   summary = ctx.get_judge(role="risk_judge")   # raises pre-fix → NON-VACUOUS
$ pytest …::test_get_judge_tool_returns_a_summary_not_a_fieldinfo_crash   PASSED
```

### S-BS-81 — allowlist-bounds + no-paid-knob — HOLDS (CONFIRMED)
```
$ pytest …::test_allowlist_is_bounded_to_mcp_lithrim_tools_no_builtins              PASSED
$ pytest …::test_no_tool_schema_carries_a_paid_knob                                 PASSED
$ pytest …::test_build_options_carries_exactly_the_bounded_allowlist_under_bypass   PASSED  ([agent], NOT skipped)
# the [agent]-gated test binds the structural claim to the real ClaudeAgentOptions:
test_uap5c_journey.py   assert list(opts.allowed_tools) == [f"mcp__lithrim__{n}" …]
                        assert opts.permission_mode == "bypassPermissions"
                        assert set(opts.allowed_tools).isdisjoint(BUILTIN_TOOLS)   # Bash/Read/Write/Edit/WebFetch/…
```

### Import-isolation — HOLDS (CONFIRMED)
```
default python   : claude_agent_sdk in sys.modules after import app  →  False
debuglithrim     : claude_agent_sdk INSTALLED                        →  True
debuglithrim     : claude_agent_sdk in sys.modules after import app  →  False   # lazy, not mere absence
```

### BYO-Claude — HOLDS (CONFIRMED)
```
$ grep -rn "api_key" apps/bff/agent/   →  (no match)
loop.py:58   ClaudeAgentOptions(mcp_servers=…, allowed_tools=…, permission_mode=…, system_prompt=…, max_turns=…)  # no api_key
loop.py:72   async with ClaudeSDKClient(options=opts) as client:   # no api_key; local-CLI/desktop auth
```

---

## Findings

| # | Severity | Finding |
|---|---|---|
| OQ-1 | OPEN-QUESTION | `author_flag` is EDIT-ONLY (tier/gradeable of an existing flag); conversational flag *creation* + `owner_roles` authoring stays a human act (S-BS-83). Correct safety posture; surfaced so the spec author can decide whether the "from-scratch" vision later wants a separate owner-authoring create-flag tool. Not a defect this cycle (user-approved at plan-review; not required by any UAP-5c acceptance criterion). |
| NB-1 | NON-BLOCKING | NB-2 model-bind (`author_judge` stays `model=""`) + NB-3 verdict-projection (replay agreement/confidence default `"—"`) carried, deferred at plan-review; orthogonal to the journey; not required by any A-criterion. |

**Legitimately deferred (NOT findings — the driver did not require them this cycle):** the `assemble_agent` (PUT /v1/agent WRITE) + `run_eval_pack` (eval-pack batch) split → UAP-5c-2 (driver §3/§4 D-F, pre-authorized). **A-LIVE** (the `:5180` user-run full-journey attestation) is **OWED** under the no-autostart rule, not a failure — the executor correctly built it driveable (pure-read Review leg, no `window.confirm` on the chat surface) and left the user-run for the monitor to schedule. The executor's note that "the eval-pack/live-hardcoded sub-assertion is N/A this cycle" is **correct**: with no paid-capable wrapper, there is nothing to hardcode-test — the SPLIT removes the obligation, it doesn't skip it.

---

## Bottom line

**NON-BLOCKING [0 BLOCKING / 1 NB / 1 OQ].** This is a clean, right-sized growth of a proven spine. The action surface widened (three new SDK-MCP tools, one of them an audited WRITE, under `permission_mode="bypassPermissions"`), and the safety boundary is re-proven **safe-by-explicit-bound**, not safe-by-current-allowlist: the allowlist test now binds to the real `ClaudeAgentOptions`, the no-paid-knob assertion is generalized across all six schemas, the one audited write goes only through the snapshot-validated + always-audited `PUT /v1/ontology`, and the two paid-capable ops are wrapped by nothing at all (the SPLIT). Both carried seams are genuinely closed: S-BS-82's fix is wrapper-only with a non-vacuous closure-driving regression test (I reverted it in a scratch tree and the test's load-bearing line raises), and S-BS-81 is asserted exactly as the NB-1 ask specified. A6 holds to the byte across all 10 ops. Green bar reproduced (293/12, 143/3, 51, ruff clean). The only owed item is the BLOCKING-but-USER-RUN A-LIVE `:5180` attestation, which is the monitor's to schedule — built driveable, no service autostarted. Cycle closes.

---

## Discipline self-check

- [x] Read the spec + driver cold; read the diff via `git diff`/`git show` BEFORE the executor's session log.
- [x] Re-verified every claim from source; reproduced the S-BS-82 crash + proved the test non-vacuous via a scratch-tree revert.
- [x] Each finding cites spec/driver + implementation file:line.
- [x] Did NOT edit any code, spec, driver, or test; wrote only this critique doc.
- [x] Did NOT confer with monitor or executor before the verdict; the session log was read last (to cross-check, not anchor) — its claims matched independent re-verification.
