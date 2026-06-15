# Proof — bench-salvage SHEPHERD-1b: the shepherd leads *cleanly* — one agent, one step per turn (2026-06-15)

> A-LIVE attestation env: :5180 shell / :8787 BFF (the live re-drive is the MONITOR's; the
> code/test-layer findings below are the executor's). $0 (no paid run).

## Claim

SHEPHERD-1 made the shepherd LEAD; SHEPHERD-1b makes it lead *cleanly*, closing the two seams it
left open:
- **S-BS-149** — the rail and the chat shepherd now operate on the SAME agent (no phantom
  `ws0_default` "0/5" while the shepherd drives a real agent).
- **S-BS-150** — one-step-and-wait is now mechanically enforced (a turn-scoped hook), not just a
  prose line; the shepherd proposes exactly one setup step per turn and stops.

## What changed

- Commits (branch `bench-salvage/ws6c-dspy`; not pushed):
  - `ec87e77` fix(shepherd): converge the rail onto the shepherd's resolved agent (W1, S-BS-149)
  - `34dda18` fix(shepherd): one-step-and-wait pacing — prompt + turn-scoped hook (W2, S-BS-150)
  - `35add13` test(shepherd): rail↔agent coercion + pacing-hook tests (W3)
  - `593395e` test(shepherd): track the foregrounded one-step wording (W2a follow-on)
- Mechanism / files:
  - **W1** `apps/shell/src/app.jsx:265-267` — a `useEffect([agents])` that mirrors the BFF
    `_resolve_chat_agent` contract (`apps/bff/app.py:1479-1483`) EXACTLY: `agents.length > 0 &&
    !agents.includes(activeAgent)` → `setActiveAgent(agents[0])`; a valid `activeAgent` (incl. a
    valid `?agent=` deep-link) is honored; empty `agents` is left unchanged. `setActiveAgent` only
    — it never bumps `sessionKey` (the sole `CenterPane` remount trigger at app.jsx:370), and is
    idempotent (once `activeAgent ∈ agents` the predicate is false, so no flip-flop). `journey.js`
    stays PURE.
  - **W2a** `apps/bff/agent/loop.py` `_SHEPHERD_STANZA` — the one-step rule is promoted to an
    imperative clause at the TOP of the stanza ("ONE STEP PER TURN, THEN STOP … propose EXACTLY ONE
    … config PROPOSAL … then STOP"), with reads + a $0 run explicitly free. SUPERSET preserved
    (base persona, HONESTY contract, active-agent naming, operator-degrade clause all intact).
  - **W2b** `apps/bff/agent/loop.py` `_build_options` — a turn-local counter closure + a SECOND
    `PreToolUse` hook `_pace_one_step` registered AFTER the byte-unchanged `_deny_non_lithrim` in
    the same matcher list. It caps the 7 step-proposing WRITE tools (`_STEP_PROPOSING_WRITES`
    frozenset) to 1/turn; the counter resets per turn because `_build_options(ctx)` is called fresh
    per turn (`_real_source`, loop.py:274). Fail-open for ITSELF (it can only ever ADD a deny).

## Before → After

| dimension | before | after |
|---|---|---|
| rail vs shepherd agent (non-default workspace) | DIVERGE — rail derives a phantom `ws0_default` ("0/5") while the shepherd resolves the workspace's first agent | CONVERGE — the shell coerces `activeAgent` to the same agent the shepherd resolves; the rail reflects that agent's real config |
| one-step pacing | prose-only (`Propose exactly ONE step at a time`, buried mid-stanza); nothing stopped the model chaining N proposals/turn | mechanical — the 2nd step-proposing write in a turn is denied by a `PreToolUse` hook; the deny prevents the audited write so no second card is fabricated |
| pacing rule prominence | one buried line | foregrounded imperative clause at the top of the stanza |

## Commit semantics — stated accurately (honesty-is-the-moat; clarification #1)

The authoring tools persist **immediately (audited)**, not as a pending card committed only on a
later human Save. Verified: `author_judge → _author_judge → put_judge_endpoint` (`apps/bff/app.py`)
calls `save_judge(jc, db_path=…, actor=…, audit_log=AuditLog(db_path=…), rationale=…)` at
**app.py:1018-1019** synchronously inside the request. So the "approval gate" is NOT a
"nothing-commits-until-Save" pending-commit gate. The honest gate is:
1. **the pacing cap** — exactly one config proposal per turn, so the human chooses to proceed step
   by step rather than a chained dump;
2. **re-editability** — every write is an audited config-plane edit that can be re-authored /
   reverted (e.g. `delete_judge` reverts to the default lens); and
3. **the immutable audit trail** — every write is an actor-attributed `AuditRecord`.
The pacing cap is correct regardless of immediate-vs-pending semantics; this capsule does not
overclaim a pending-commit gate. (The `_SHEPHERD_STANZA` line "the Save IS the approval gate"
refers to the editor card the human reviews; it is not a deferred DB commit — the persist is
immediate-and-audited.)

The W2b deny reason is phrased as graceful pacing, not an error — if surfaced it reads: *"One setup
step per turn: you've already proposed a step this turn. Surface that one card, ask the human to
review/save it and tell you to continue, then set up the next step on the following turn."* (No
"permission denied"/"blocked" wording — asserted by `test_pacing_hook_caps_step_proposing_writes_to_one_per_turn`.)

## Evidence (grounded, not narrated) — code/test layer

- **W1** `apps/shell/src/app.coerce.test.jsx` (5 tests, PASS): the BFF-contract replica
  (absent→`agents[0]`, present→honored, empty→unchanged) + the actual coercion effect from
  app.jsx:265-267 over synchronous props (absent→coerced, present→honored, empty→no-crash,
  idempotent with NO `sessionKey` bump). The full-App mount-effect integration assertion was NOT
  used: App's mount-effect chain hangs on dynamic-`import("./bff.js")` flush under jsdom (the
  click-driven `app.chat.test.jsx` is the only integration path that flushes) — so the effect's
  React semantics are exercised directly via a harness running app.jsx's verbatim predicate.
- **W2a** `tests/test_uap5b_chat.py::test_system_prompt_foregrounds_the_one_step_and_wait_rule` +
  `::test_system_prompt_stays_a_superset_back_compat` (PASS), plus the updated
  `tests/test_shepherd.py` (4 PASS) tracking the foregrounded wording.
- **W2b** `tests/test_uap5b_chat.py::test_pacing_hook_caps_step_proposing_writes_to_one_per_turn`
  (1st write allow, 2nd same-turn deny w/ graceful reason, reads + $0 run never counted, fresh
  `_build_options` resets) + `::test_pacing_hook_fails_open_for_itself` (PASS). Asserts the matcher
  is `["_deny_non_lithrim", "_pace_one_step"]` (deny first + additive).
- **Moat/A-SAFE tripwire (PASS):** guard trio 17 passed; `apps/bff/agent/tools.py` byte-stable
  (empty diff vs `da2a0a8`); `_deny_non_lithrim` body + everything up to `def _build_options`
  byte-identical; `compliance_council.py`/`signals.py` zero-diff; the `_build_options` A-SAFE
  surface (`allowed_tools`/`permission_mode`/`setting_sources`/`skills`/`max_turns`/
  `include_partial_messages`) byte-unchanged — only the `hooks=` line gained `_pace_one_step` and
  the additive closure.
- **Suite:** canonical `pytest` = **2 failed | 542 passed | 4 skipped**; the 2 fails are the
  pre-existing order-dependent `test_observation_pipeline.py` `sys.modules`-pollution flakes
  (CONFIRMED identical at parent `da2a0a8`: the full suite there also fails the same 2 — and both
  pass in isolation). Vitest = **1 failed | 110 passed (111)**; the 1 fail is the acknowledged
  S-BS-145 `app.test.jsx` titlebar test (`ModeSwitch` commented out at app.jsx:109), identical at
  parent.
- Reproduce (code/test): `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare
  LITHRIM_BENCH_PACK=healthcare python -m pytest tests/test_uap5b_chat.py tests/test_shepherd.py` ;
  `cd apps/shell && npx vitest run src/app.coerce.test.jsx`.

## Before → After (A-LIVE :5180 re-drive) — **PENDING-MONITOR-LIVE**

The driver assigns the live re-drive to the monitor. To fill on the live pass:
- **A1 LIVE:** open a non-default workspace whose agents exclude `ws0_default`; confirm the rail and
  the shepherd name the SAME agent and the rail shows that agent's real step state (not "0/5").
- **A2 LIVE:** give a multi-step ask; confirm exactly ONE save-pending card lands per turn.
- **A3 LIVE (the SHEPHERD-1 deferred beat):** after the human acts on a proposed config, the rail
  ticks a step to `done` — the beat held back in SHEPHERD-1 because of S-BS-149.

## Journey impact

- Launch-journey phase: **P1 Install / P2 Verify** — onboarding is now coherent (the rail and the
  chat agree) and well-paced (one step at a time).
- De-risk gap: **#1 SME-authorable bounded context** — a cleaner, less overwhelming guided author
  loop.
- Unblocks: the SHEPHERD-1 deferred "watch the rail tick to done" demo beat (now reproducible with
  S-BS-149 closed).

## Video

- PENDING-MONITOR-LIVE (optional per A6 — a tight re-capture of the deferred save→advance beat is the
  payoff if cheap). Spec to author at live pass: `journeys/bench-salvage_SHEPHERD-1b.narrate.json` →
  `out/zyng_narrate/`.
