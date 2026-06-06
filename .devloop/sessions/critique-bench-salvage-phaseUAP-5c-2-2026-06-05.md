# Fresh-Critic Critique — `bench-salvage` phase `UAP-5c-2` (complete the conversational tool set → 8: `run_eval_pack` batch + `assemble_agent` edit-one-facet, R11)

> **HARD-GATE fresh critic.** No prior implementation context. Spec + driver + diff read COLD; every
> executor claim re-verified from source. Critic ran read-only commands/tests + a non-vacuity revert in a
> scratch tree (restored clean) + three adversarial probe scripts; wrote only this doc. Diff under review:
> `b2a8c92..1ff7ea8` (6 commits 3578905..1ff7ea8). Parent `b2a8c92` (docs-only commit) NOT reviewed.
> Date: 2026-06-05.

**VERDICT: NON-BLOCKING [0 BLOCKING / 2 NB / 1 OQ].**

This cycle re-introduces the FIRST agent-reachable wrapper over a PAID-CAPABLE op (`run_eval_pack` over
`eval_pack_run_endpoint`'s `live` knob) and the FIRST agent-reachable Agent WRITE (`assemble_agent`), so
A-SAFE is the gate-decider again. Every load-bearing invariant the kickoff named HOLDS, each verified from
source (not from the session log):

- **A-SAFE (the crux): HOLDS** (CONFIRMED — I tried to reach a paid run, an un-audited write, and a gate
  bypass from all 8 tools; every path is closed. The two run-capable closures BOTH hardcode `live=False`
  (and `_run_eval_replay` also `in_process=False`); no tool schema across all 8 carries a paid knob; the
  `assemble_agent` ADD path refuses an unknown role and its WRITE is audited; the Review leg is pure-read
  `tool-audit_log`, never `tool-run_panel`).
- **The `live=False` hardcode is NON-VACUOUS** (CONFIRMED — I reverted `live=False`→`live=True` in a scratch
  copy of `_run_eval_pack` and the negative test FAILED with `assert True is False`; restored clean).
- **A6 frozen 0-delta: HOLDS** (CONFIRMED — `git diff` over the council/seam/seed set == 0 lines;
  `put_agent_endpoint` (28 lines) AND `eval_pack_run_endpoint` (29 lines) AND `EvalPackRunRequest` are
  **byte-identical** parent→HEAD via name-extraction; both `app.py` hunks are strictly inside
  `_build_tool_context`).
- **S-BS-84 (the disclosed seam): HONESTLY CHARACTERIZED, genuinely LOW** (CONFIRMED — the ADD path IS
  `LENS_BY_ROLE`-guarded (unknown role → 404, roster untouched); the REMOVE path IS un-revalidated (I
  drained the roster to `[]`, which persisted); but every emptying write is still AUDITED, REMOVE can only
  narrow an existing roster (never fabricate/relabel), and the worst case is a degraded-but-traceable
  verdict, not an A-SAFE escape).
- **Import-isolation: HOLDS** (CONFIRMED — `claude_agent_sdk` absent from `sys.modules` after `import app`
  on BOTH default python AND debuglithrim *with the extra installed* — proving lazy import, not mere
  absence).
- **BYO-Claude: HOLDS** (CONFIRMED — no `api_key` anywhere in `_build_options`; no `ANTHROPIC_API_KEY`
  reference; `ClaudeAgentOptions` built without a key).

---

## Re-run test counts (critic-run, hermetic, no service autostarted)

| Suite | Command | Result |
|---|---|---|
| Default python | `python3 -m pytest tests/ -q` | **299 passed, 12 skipped** |
| debuglithrim ([agent]) | `PYENV_VERSION=debuglithrim python -m pytest tests/test_uap5c_journey.py tests/test_uap5b_chat.py tests/test_ws5_bff.py lithrim_bench/runtime/council/tests/ -q` | **149 passed, 3 skipped** (3 live-Azure skips) |
| Shell Vitest | `cd apps/shell && npx vitest run` | **51 passed (11 files)** |
| ruff | `python3 -m ruff check <6 changed .py>` | **All checks passed!** |

All four match the executor's claimed counts (session log diagnostic_stats: 299p/12s, 149p/3s, 51p) exactly.
The 12 default skips are dspy/openai-absent + the two `[agent]`-gated tests; the 3 debuglithrim skips are
live-Azure go-gated. Critically, the `[agent]`-gated `test_build_options_carries_exactly_the_bounded_allowlist_under_bypass`
RAN (not skipped) under debuglithrim, because `claude_agent_sdk` IS installed there — binding the 8-tool
allowlist claim to the real `ClaudeAgentOptions`.

---

## Q1 — Surface fidelity (the 2 new SDK-MCP tools, schemas, adapter, loop)

**Match to driver §2 D1/D2/D3/D4 + spec §13/§10: faithful.** CONFIRMED. No unauthorized surface drift.

- **Tool set (D-A = ship BOTH):** `_TOOL_SPECS` grows 6→8 = the UAP-5c set + `{run_eval_pack, assemble_agent}`
  (`tools.py:325-340`; asserted by `test_tool_set_is_the_uap5c_journey_set` (now 8) + `test_uap5c2_split_tools_grow_the_set_to_eight_with_no_paid_knob`).
  The D-F run_eval_pack-alone fallback did NOT trigger — `assemble_agent` stayed edit-one-facet (verified
  below), so shipping both is in-scope per driver §4 + §0/§2.
- **Schemas (SDK-free, paid-knob-free):** `RUN_EVAL_PACK_SCHEMA={"pack_id":str,"agents":list}` (NO
  `live`/`confirm`/`in_process`); `ASSEMBLE_AGENT_SCHEMA={"name":str,"add_judge":str,"remove_judge":str,"rationale":str}`
  (a DELTA, never a full Agent dict) (`tools.py:51-63`). I enumerated all 8 schemas — `paid_offenders=[]` for
  every one.
- **Adapter (D-B):** `run_eval_pack→tool-audit_log` (`audit_part`, the batch's newest run id), `assemble_agent→tool-agent_editor`
  (`agent_part`, self-fetches the updated `GET /v1/agent`) (`adapter.py:22-30,58-63`). Both targets pre-exist
  in `registry.js` `KNOWN_TOOLS:28-29`; the registry is **byte-unchanged** this cycle (absent from the diff)
  → no new card types (A4). The Review/batch leg is pure-read `tool-audit_log` — NOT `tool-run_panel` (whose
  paid Run is `window.confirm`-gated, S-BS-80).
- **Loop (D4):** `_SYSTEM_PROMPT` names both new tools, states `run_eval_pack` is `$0` REPLAY and a live batch
  is the human's, and adds "an unknown judge role" to the surfaced-error list (`loop.py:33-34,38-39,46-50`).
  `allowed` auto-extends from `_TOOL_SPECS` (`loop.py:61`); `max_turns` stays 12 (`loop.py:67`).

**One surface nuance (NB-1, below):** the `ASSEMBLE_AGENT_SCHEMA` types `add_judge`/`remove_judge` as `str`,
but the closure `_assemble_agent` defaults them to `None` and the handler reads `args.get(...)` (so an
omitted facet is `None`, not `""`). Behaviour is correct (the `if not add_judge and not remove_judge` 400s
on neither); the schema-vs-closure default mismatch is cosmetic.

---

## Q2 — Behavioral fidelity (spec assertion → test → implementation), 3 load-bearing chains

### Chain 1 — A-SAFE: `run_eval_pack` cannot fire a paid batch (the THE crux)

- **Spec/driver assertion:** driver §5 A-SAFE + spec §10 (UAP-5c-2): "its schema carries NO `live`/`confirm`/`in_process`
  and the bound closure HARDCODES `EvalPackRunRequest(..., live=False)` — injecting `live=True` into the tool
  args is **DROPPED** (negative-tested)."
- **Test:** `test_run_eval_pack_drops_an_injected_live_knob` (`test_uap5c_journey.py:208-229`) monkeypatches
  `bff.eval_pack_run_endpoint` with a spy, calls the handler with `{...,"live":True,"confirm":True,"in_process":True}`,
  asserts `captured["live"] is False`. Plus `test_run_eval_pack_handler_never_forwards_a_paid_knob:232-251`
  (handler-drop mirror: `seen == {"pack_id":"p","agents":[AGENT],"extra":{}}`).
- **Impl:** `_run_eval_pack` (`app.py:1004-1013`) → `EvalPackRunRequest(pack_id=pack_id, agents=agents, live=False)`;
  handler call site is `ctx.run_eval_pack(pack_id=pack_id, agents=agents)` (`tools.py:231`) — only two args,
  physically cannot forward a paid key.
- **CHAIN CLOSES + NON-VACUOUS.** The `env` fixture binds the REAL `_run_eval_pack` closure (`test:92`
  `bff._build_tool_context(...)`), and `_run_eval_pack` references `eval_pack_run_endpoint` as a module-global
  resolved at call time — so the monkeypatch genuinely flows through. **Critic non-vacuity proof:** reverting
  `live=False`→`live=True` in a scratch `app.py` makes the test FAIL (`assert True is False` at `:229`);
  restored clean (empty `git diff --stat`). This is the single most load-bearing test of the cycle and it
  catches the regression.

### Chain 2 — `assemble_agent` is an AUDITED, edit-one-facet Agent WRITE

- **Spec/driver assertion:** driver §5 A2/A3 + spec §13: "the audited `PUT /v1/agent`, `target_type=agent`";
  "edit-one-facet = the judges roster … never a full dict from the model"; "an unknown role 404s — never
  fabricate a judge."
- **Test:** `test_assemble_agent_roster_edit_is_an_audited_agent_write` (`:248-264`): removes `faithfulness_judge`,
  asserts `tool-agent_editor` emitted, `GET /v1/audit?target_type=agent` shows an `actor.id=='test-sme'` /
  `target.type=='agent'` record, and `faithfulness_judge not in ag["eval_profile"]["judges"]` (the delta
  applied). Plus `test_assemble_agent_unknown_judge_is_surfaced_not_bypassed:267-279` (unknown role → `is_error`,
  no card, `GET /v1/audit?target_type=agent == []`).
- **Impl:** `_assemble_agent` (`app.py:1016-1043`) loads the current dict via the FROZEN `get_agent_endpoint`
  (404 on unknown agent), edits ONLY `current["eval_profile"]["judges"]`, guards ADD with `if add_judge not in
  LENS_BY_ROLE: raise 404`, and PUTs the merged dict through the FROZEN audited `put_agent_endpoint` (passing
  `rationale`/`default_actor`/`x_actor` explicitly — the S-BS-82 rule). The model supplies only the delta.
- **CHAIN CLOSES.** I independently confirmed `agent_to_dict` nests `judges` under `eval_profile`
  (`config.py:123`) and `agent_from_dict` reads it back (`:97,102`), so the load→edit-one-facet→put round-trip
  is faithful. **Independent probe:** ADD `fabricated_judge` → `HTTPException 404 "unknown judge role
  'fabricated_judge'"`, roster untouched. The write goes through `put_agent_endpoint`'s `agent_from_dict`
  422-gate (byte-identical to parent). No full-dict path exists — the over-engineering trap the driver §4
  forbids is avoided.

### Chain 3 — A-SAFE structural: the 8-tool allowlist is exactly `mcp__lithrim__*`, no built-in, no paid knob

- **Spec/driver assertion:** driver §5 A-SAFE + spec §10: "the allowlist stays exactly the `mcp__lithrim__*`
  set (now 8) with no built-in"; "NO tool schema carries a paid knob."
- **Test:** `test_allowlist_is_bounded_to_mcp_lithrim_tools_no_builtins:161-170` + `test_no_tool_schema_carries_a_paid_knob:173-178`
  (both iterate `_TOOL_SPECS`, auto-covering the 2 new tools) + `test_uap5c2_split_tools_grow_the_set_to_eight_with_no_paid_knob:200-207`
  (asserts `len==8` + the 2 new schemas paid-knob-free) + the `[agent]`-gated `test_build_options_carries_exactly_the_bounded_allowlist_under_bypass:181-191`
  (the REAL `ClaudeAgentOptions`: exact list, `bypassPermissions`, `isdisjoint(BUILTIN_TOOLS)`).
- **Impl:** `loop._build_options:61` `allowed = [f"mcp__lithrim__{name}" for _, name, *_ in _TOOL_SPECS]`;
  `permission_mode="bypassPermissions"` (`:65`).
- **CHAIN CLOSES.** **Independent derivation:** the 8-tool allowlist is exactly `[mcp__lithrim__{author_judge,
  get_judge, run_eval, get_agent, author_flag, review_runs, run_eval_pack, assemble_agent}]` — all prefixed,
  no wildcard, disjoint from `{Bash,Read,Write,Edit,WebFetch,WebSearch,Glob,Grep,NotebookEdit,Task,MultiEdit}`.
  The `[agent]`-gated test RAN (not skipped) under debuglithrim, binding the structural claim to the real SDK
  options. `bypassPermissions` is safe precisely because the allowlist is bounded and no schema carries a paid
  knob.

---

## Q3 — Out-of-scope intrusion

**None.** CONFIRMED. The full `git diff b2a8c92..1ff7ea8 --name-only` is exactly 9 files, all in driver §2:

| File | Driver deliverable |
|---|---|
| `apps/bff/agent/tools.py` | D1/D2 (schemas + handlers + `_TOOL_SPECS`) |
| `apps/bff/app.py` | D1/D2 (`_run_eval_pack` + `_assemble_agent` closures, both inside `_build_tool_context`) |
| `apps/bff/agent/adapter.py` | D3 (adapter docstring updates; reuses `audit_part`/`agent_part`) |
| `apps/bff/agent/loop.py` | D4 (`_SYSTEM_PROMPT` + auto-extend allowlist) |
| `tests/test_uap5c_journey.py` | D5 (6 new A-SAFE/journey tests) |
| `tests/test_uap5b_chat.py` | D5 (the tool-set assertion grows to 8) |
| `docs/specs/SPEC_PRODUCT_SHELL.md` | D6 (§10 ratification note — additive) |
| `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` | D6 (§13 ratification note — additive) |
| `.devloop/sessions/session-bench-salvage-phaseUAP-5c-2-2026-06-05.json` | D6 (session log) |

No drive-by refactors, no formatting passes, no dependency bumps. The spec notes are accurate to the impl
(they state `live=False` hardcoded, edit-one-facet, `LENS_BY_ROLE` guard, byte-identical ops, no new card
types) — ratification, not contract-weakening. The foreign untracked files (`.claude/`, `KICKOFF_CRITIC_*`,
`REPORT_fhir_*`) were NOT swept into the diff (absent from the name-only list) — the
`git-commit-pathspec-dirty-index` discipline held.

---

## Q4 — Spec ambiguity surfaced (OPEN-QUESTIONS for the spec author)

- **OQ-1 (carried from S-BS-84, restated for the spec author):** Should an `assemble_agent` roster edit refuse
  a write that (a) empties the roster, or (b) orphans the owner of a gradeable flag? The spec §13 says
  edit-one-facet "add/remove ONE known v2 judge … never fabricate a judge" but is silent on a write-time
  owner↔emit / non-empty revalidation on REMOVE. The impl currently allows both (verified below). This is
  LOW (audited, reversible, no A-SAFE breach) but it makes an implicit decision — "a roster edit may degrade
  gradeability, the audit trail is the safety net" — that becomes canon unless the spec author locks or
  corrects it. (Analogous to S-BS-83's owner-authoring boundary.)

---

## Independently-verified load-bearing invariants (verbatim evidence)

### A-SAFE — no tool reaches a paid run / un-audited write / gate bypass — HOLDS (CONFIRMED)

Every endpoint call inside `_build_tool_context` (the only agent-reachable surface), critic-greped:

```
953:    def _run_eval_replay(agent: str) -> dict:
954:            RunEvalRequest(agent=agent, live=False, in_process=False),   # hardcoded $0
...
1010:            EvalPackRunRequest(pack_id=pack_id, agents=agents, live=False)  # hardcoded $0
```

Schema enumeration over all 8 tools (critic-run):

```
author_judge:   paid_offenders=[]      get_agent:      paid_offenders=[]
get_judge:      paid_offenders=[]      author_flag:    paid_offenders=[]
run_eval:       paid_offenders=[]      review_runs:    paid_offenders=[]
run_eval_pack:  schema_keys=['pack_id','agents']         paid_offenders=[]
assemble_agent: schema_keys=['name','add_judge','remove_judge','rationale'] paid_offenders=[]
```

The two run-capable closures BOTH hardcode the $0 path; every other closure is a read or an audited
config-plane write (`put_judge`, `put_ontology`, `put_agent`) — none is a paid `:8002` call. The Review/batch
leg renders `tool-audit_log` (pure-read), never `tool-run_panel`. **No path from any tool to a paid run, an
un-audited write, or a gate bypass.**

### The `live=False` hardcode is NON-VACUOUS — CONFIRMED

```
=== BASELINE === 2 passed (test_run_eval_pack_drops_an_injected_live_knob + the handler mirror)
=== MUTATION: live=False -> live=True (1 site in _run_eval_pack) ===
=== Re-run under mutation ===
E       assert True is False
tests/test_uap5c_journey.py:229: AssertionError
FAILED tests/test_uap5c_journey.py::test_run_eval_pack_drops_an_injected_live_knob
=== RESTORE === (empty git diff --stat = restored clean)
```

The monkeypatch on `bff.eval_pack_run_endpoint` flows through the REAL `_run_eval_pack` closure (bound by the
`env` fixture), and the spy captures the real `req.live`. Reverting the hardcode makes the assertion fail. The
test catches the regression — it is NOT asserting something always-true.

### A6 frozen 0-delta — HOLDS (CONFIRMED)

```
git diff b2a8c92 1ff7ea8 --stat -- compliance_council.py judges_dspy.py judge_metric.py
   authored_stage.py data/ontology/clinical_v1.json data/config/agents/ws0_default.json
   => (empty)

put_agent_endpoint   (name-extracted, 28 lines each rev): BYTE-IDENTICAL
eval_pack_run_endpoint (name-extracted, 29 lines each rev): BYTE-IDENTICAL
EvalPackRunRequest model:                                   BYTE-IDENTICAL

app.py diff hunk headers (ALL inside the closure):
  @@ -1000,6 +1000,52 @@ def _build_tool_context(
  @@ -1007,6 +1053,8 @@ def _build_tool_context(
```

The council/seam/seed set is 0-delta; both wrapped ops (and the request model) are byte-identical parent→HEAD;
all 48 new app.py lines are strictly inside `_build_tool_context`. The new code is a DRIVER OVER the frozen
ops, never a modification of them.

### S-BS-84 (the disclosed seam) — HONESTLY CHARACTERIZED, genuinely LOW (CONFIRMED) — independent severity call

Three-leg probe (critic-run):

```
(a) ADD unknown role  -> GUARDED: HTTPException 404 "unknown judge role 'fabricated_judge'
                          (known: ['faithfulness_judge','policy_judge','risk_judge'])"  [roster untouched]
(b) REMOVE all three  -> risk_judge gone -> policy_judge gone -> faithfulness_judge gone
                          FINAL roster: []  <- EMPTY ROSTER PERSISTED
(c) the emptying writes -> agent audit records: 3  (each REMOVE is still AUDITED + attributed)
(d) $0 replay on the empty-roster agent -> ran OK, verdict='reject' (does NOT crash)
```

**Independent severity: LOW is defensible and the executor's characterization is honest.** The seam is real
and exactly as disclosed: ADD is `LENS_BY_ROLE`-guarded (the only path that could fabricate/widen authority);
REMOVE is un-revalidated and can empty the roster. But it is NOT an A-SAFE escape:
1. Every write — including the emptying ones — is AUDITED with an attributed actor, so the change is fully
   traceable and reversible (the conversation-IS-the-audit-log invariant holds).
2. REMOVE can only NARROW an existing roster; it cannot inject a non-existent judge, relabel a case, or
   bypass a gate. There is no paid run, no un-audited write, no fabrication.

**One refinement (NB-2, below):** the executor's stated impact says the orphan case is "a NARROWER council,
not a wrong verdict." My probe shows the terminal EMPTY-roster case still emits a `reject` verdict from zero
judges — a degraded/meaningless verdict, not merely "narrower." Still LOW (audited, reversible, no fabrication),
but "not a wrong verdict" is optimistic for the empty-roster edge; the honest framing is "a degraded-but-traceable
verdict at grade time."

### Import-isolation — HOLDS (CONFIRMED)

```
claude_agent_sdk in sys.modules (default python, after import app):       False
claude_agent_sdk INSTALLED in debuglithrim:                                True
claude_agent_sdk in sys.modules (debuglithrim, after import app):          False
```

Absent from `sys.modules` after `import app` on BOTH default deps AND debuglithrim (where the `[agent]` extra
IS installed) — proving a genuine lazy import inside `loop._build_options` (`from claude_agent_sdk import ...`
at `loop.py:57`, function-scoped), not mere environmental absence.

### BYO-Claude — HOLDS (CONFIRMED)

`loop._build_options` (`loop.py:56-67`) constructs `ClaudeAgentOptions(... allowed_tools=allowed,
permission_mode="bypassPermissions", max_turns=12)` with NO `api_key` argument and NO `ANTHROPIC_API_KEY`
reference anywhere in `apps/bff/agent/`. The provider is the local Claude CLI/desktop auth.

---

## Findings

- **NB-1 (NON-BLOCKING, cosmetic).** `ASSEMBLE_AGENT_SCHEMA` types `add_judge`/`remove_judge` as `str`, but the
  closure/handler default them to `None` and branch on `if not add_judge`. Behaviour is correct; the
  schema-default-vs-closure-default mismatch is cosmetic and harmless. (`tools.py:56-63` vs `app.py:1017,1026-1028`.)
  Sub-note: removing a judge NOT in the roster is a no-op that still fires an audited PUT (a change-free audit
  record). Harmless; within the S-BS-84 umbrella.

- **NB-2 (NON-BLOCKING, framing).** The S-BS-84 impact text ("a NARROWER council, not a wrong verdict")
  understates the EMPTY-roster terminal case, which my probe shows still emits a `reject` verdict from zero
  judges (a degraded verdict, not merely narrower). The severity (LOW) is unchanged and correct; only the
  prose is slightly optimistic. Recommend the spec author note OQ-1 when deciding whether REMOVE should warn
  on emptying/orphaning. (`session-...json` seams_opened[0].impact vs the probe in §S-BS-84 above.)

- **OQ-1 (OPEN-QUESTION).** See Q4 — should `assemble_agent` REMOVE refuse an empty/owner-orphaning roster?
  The spec is silent; the impl allows it (audited). For the spec author to lock or correct.

---

## Discipline self-check

- [x] Read the spec/driver/persona cold (CRITIC.md, the UAP-5c-2 driver, the UAP-5c parent driver) before reading the executor's session log.
- [x] Reconstructed the diff via `git diff`/`git show` against the commits, not the executor's prose.
- [x] Each finding cites both a spec/driver locus and an implementation file:line.
- [x] Did NOT edit any code, spec, or driver. The one scratch mutation (non-vacuity revert) was made on a temp copy and restored; `git diff --stat` confirms the tree is clean.
- [x] Did NOT confer with the monitor or executor before writing the verdict.

---

## Bottom line

**NON-BLOCKING — the cycle may close.** The pre-authorized D-F split landed in full (both tools, NOT the
run_eval_pack-alone fallback), and `assemble_agent` stayed genuinely edit-one-facet (load→modify-one-roster→put,
never a full dict from the model) — so shipping both is in-scope, not over-reach. A-SAFE is re-proven
safe-by-explicit-bound as the surface widened to 8: `run_eval_pack`'s schema carries no paid knob and the
closure hardcodes `live=False` (the negative test is NON-VACUOUS — a reverted hardcode fails it);
`assemble_agent`'s ADD path is `LENS_BY_ROLE`-guarded and its WRITE is audited (`target_type=agent`); the
8-tool allowlist is exactly the `mcp__lithrim__*` set with no built-in (bound to the real `ClaudeAgentOptions`
under `bypassPermissions`); the Review leg is pure-read. A6 holds to the byte (council/seam/seeds 0-delta;
`put_agent_endpoint` + `eval_pack_run_endpoint` + `EvalPackRunRequest` byte-identical; all new code inside
`_build_tool_context`). Import-isolation + BYO-Claude re-confirmed. Green bar matches the executor's claims
exactly (299/12, 149/3, 51, ruff clean). Scope is clean (9 files, all in §2; no foreign sweep). S-BS-84 is a
genuine, honestly-disclosed, LOW config-correctness seam (the REMOVE path can empty/orphan the roster) — every
such write is still audited and only narrows authority, so it is a correctness-nuisance, not an A-SAFE escape;
2 NB framing/cosmetic notes + 1 OQ for the spec author. The A-LIVE `:5180` slice is correctly OWED under the
no-autostart rule (not a failure); the UAP-5c A-LIVE was attested first (b2a8c92), so this does not compound on
an un-attested surface.
