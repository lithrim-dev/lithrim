# Proof — bench-salvage SHEPHERD-1b: the shepherd leads *cleanly* — one agent, one step per turn (2026-06-15)

> A-LIVE attestation env: :5181 shell (a stale shell held :5180; Vite fell back to :5181) /
> :8787 BFF (re-drive on the monitor's pass, 2026-06-15; the code/test-layer findings below are
> the executor's). $0 (no paid run; all writes were $0 audited config-plane edits + BYO-Claude chat).

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

## A-LIVE :5181 re-drive (monitor, 2026-06-15) — honest-Δ, NOT all wins

Driven via Claude-in-Chrome on the `demo-clinical` workspace (agents `eval-1` + `snomed-demo`;
**no `ws0_default`** — the exact non-default workspace S-BS-149 diverged in). $0 throughout.

- **A1 — CONFIRMED LIVE ✓.** On landing, the rail showed a coherent **"1 / 5", Domain ✓, Judges =
  NOW** for `eval-1` — i.e. it derived `eval-1`'s real config, NOT a phantom `ws0_default` "0/5".
  Asked *"which agent am I setting up?"*, the shepherd read live state and surfaced an
  **`Agent · eval-1`** editor card. Rail's active agent **and** the shepherd's resolved agent both =
  `eval-1`. **They converge** — the S-BS-149 fix holds. (Bonus, both CONFIRMED live: the A-SAFE deny
  hook fired *gracefully* when the model tried a stray `ToolSearch` — *"ToolSearch doesn't apply to
  the Lithrim tools… let me read the live state first (free)"* — and the CONV-UX-1 activity timeline
  rendered the tool steps.)
- **A2 — CONFIRMED LIVE ✓.** Single message asked for **two** config steps ("set up my judges AND
  add the ground-truth grounding contract … configure both now"). The shepherd verbalized the
  pacing exactly — *"…**one config step per turn** … the natural order is Judges → Ground truth …
  So I'll lead with judges now, then propose the grounding contract on the next turn once you've
  saved"* — and surfaced **one** config write (the roster), deferring ground-truth. Free reads
  (`get_agent`/`get_judge`) flowed unthrottled, as designed. The S-BS-150 fix holds (and W2b is
  unit-test-proven as the mechanical backstop).
- **A3 — DID NOT REPRODUCE LIVE ✗ (honest loss; the deferred demo beat).** Saving the
  `Agent · eval-1` roster committed (audited: card showed *"saved ✓ as rahul@lithrim.dev"*), but the
  rail **stayed "1 / 5, Judges NOW"** — it did not tick. Ground truth via the shell's own
  `getAgent('eval-1')` post-save: **`eval_profile.judges: []`** (`ontology_ref:"clinical/1"`,
  `tools:[]`). The rail derivation is **CORRECT** (faithfully reflects empty `judges`); the failure
  is upstream. A second attempt (assigning the `risk_judge` lens via the JudgeEditor) returned a
  **422: `assigned flags outside taxonomy snapshot … ['INTERNAL_INCONSISTENCY']`**. So neither live
  authoring surface flips the rail's Judges step. **CONFIRMED** these are PRE-EXISTING gaps, not 1b
  regressions (1b changed only the W1 coercion + the W2 pacing; it never touched SHEPHERD-1's W3
  save→advance wiring, the field model, or the admissibility gate — SHEPHERD-1's own close already
  recorded "W3 save→advance proven at the mechanism/test layer, live Save not driven"). The
  rail-advance MECHANISM stays unit-test-proven (the W3 derivation test: an agentCfg with non-empty
  `judges` → Judges `done`); the live break is localized to the authoring write + lens admissibility.

### Two new seams filed (SHEPHERD-1c scope; neither blocks 1b)
- **S-BS-153 (med)** — rail↔authoring **field-mapping gap**: the `Agent · eval-1` roster Save commits
  (audited) but leaves `eval_profile.judges` (the rail's `Judges` predicate source, `journey.js`
  `isDone`) empty — it writes a roster/`council_config`-shaped field the rail does not read. So the
  live save→advance (SHEPHERD-1 W3) never ticks Judges. CONFIRMED via `getAgent` ground truth.
- **S-BS-154 (med)** — JudgeEditor **lens options ⊄ pack taxonomy snapshot**: the `risk_judge` card
  offers lens codes (`INTERNAL_INCONSISTENCY`, `UNSUPPORTED_ASSERTION`) that the demo-clinical
  admissibility gate rejects (`422 assigned flags outside taxonomy snapshot`), so a judge can't be
  authored via the offered lenses in this pack. CONFIRMED via the 422.

**Verdict:** the two seams SHEPHERD-1b targeted — S-BS-149 + S-BS-150 — are CLOSED and live-confirmed
(A1, A2). The deferred "rail ticks to done" beat (A3) is an **honest loss** that the live drive
surfaced two real, pre-existing causes for. Per the honesty-is-the-moat thesis ("a manufactured win
is a FAIL"), this loss is reported as the proof point it is, not hidden.

## Journey impact

- Launch-journey phase: **P1 Install / P2 Verify** — onboarding is now coherent (the rail and the
  chat agree) and well-paced (one step at a time).
- De-risk gap: **#1 SME-authorable bounded context** — a cleaner, less overwhelming guided author
  loop (agent + rail now agree; one step per turn).
- Still BLOCKED (honest): the SHEPHERD-1 deferred "watch the rail tick to done" demo beat does NOT
  yet reproduce — S-BS-149 was necessary but not sufficient; S-BS-153 (authoring writes the field
  the rail reads) + S-BS-154 (admissible lenses) are the remaining preconditions → SHEPHERD-1c.

## Video

- NOT captured. The intended payoff was a tight re-capture of the save→advance beat, but A3 did not
  reproduce live (S-BS-153/154), so there is no honest "rail ticks to done" beat to film yet. A clean
  capture is deferred to SHEPHERD-1c once 153/154 land. (A1 + A2 are demonstrable live now, but a
  video is OPTIONAL per A6 and not worth the spend without the A3 payoff.)
