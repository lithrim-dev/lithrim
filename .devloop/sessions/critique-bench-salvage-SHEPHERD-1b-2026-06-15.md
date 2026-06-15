# Critique — bench-salvage phase SHEPHERD-1b (rail↔agent sync + one-step pacing)

> **Fresh adversarial critic. HARD GATE.** Read the spec + diff cold, verified every claim
> against the live tree + git. Read-only except this file.
> **Commit range:** `da2a0a8..HEAD` (5 commits: ec87e77, 34dda18, 35add13, 593395e, c729ac4).

## VERDICT: **PASS**

- **BLOCKING: 0**
- **NON-BLOCKING: 1**
- **OBSERVATION: 3**

A HARD GATE passes only with 0 BLOCKING findings. All 5 mandatory HARD-GATE verifications
(moat/A-SAFE byte-stability, additive+fail-closed-safe pacing hook, non-vacuous tests,
honest-Δ, scope+suite) PASS. The one NON-BLOCKING finding is a **pre-existing** prompt-honesty
seam that 1b did NOT introduce and that the PROOF capsule already discloses accurately.

---

## Real command outputs (verbatim)

**Guard trio (moat tripwire):**
```
PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare \
  python -m pytest tests/test_6bclean_seam_guard.py tests/test_6bclean_attestation.py -q
17 passed in 0.36s
```

**Full canonical suite:**
```
PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare \
  python -m pytest -q
2 failed, 542 passed, 4 skipped, 3 warnings in 68.28s
FAILED .../observation/tests/test_observation_pipeline.py::test_importing_observation_does_not_load_compliance_modules
FAILED .../observation/tests/test_observation_pipeline.py::test_default_run_pulls_no_heavy_deps
```
The 2 fails are the pre-existing order-dependent `sys.modules`-pollution flakes. In isolation
they pass (`pytest .../test_observation_pipeline.py -q` → `13 passed in 0.18s`). This cycle
touched only `loop.py` (prompt/hook), `app.jsx`, tests, and docs — zero overlap with the
observation/council import-graph the failing tests probe, so they are NOT a 1b regression.
(The S-BS-145 Vitest titlebar fail is the acknowledged pre-existing fail; not re-checked here.)

---

## HARD-GATE verification 1 — Moat / A-SAFE byte-stability  → **PASS (OBSERVATION on a path typo)**

- `git diff da2a0a8 HEAD -- apps/bff/agent/tools.py` → **empty.** tools.py byte-stable. ✔
- The driver/kickoff cites the moat at `runtime/council/...`; the live tree has them at
  `lithrim_bench/runtime/council/compliance_council.py` + `.../signals.py` (the in-repo package
  path). At the correct paths:
  `git diff da2a0a8 HEAD -- lithrim_bench/runtime/council/compliance_council.py lithrim_bench/runtime/council/signals.py`
  → **empty.** A broader `--stat -- 'lithrim_bench/runtime/council/'` over the range is also
  empty. Moat zero-diff confirmed. ✔  *(OBSERVATION-A: the path shorthand in the driver §5/§4 is
  inaccurate vs the live tree — harmless to the diff but worth correcting in the next driver.)*
- `_deny_non_lithrim` BODY is byte-identical: in the loop.py diff, the only `±` lines touching the
  deny hook are the comment block above it and `hooks={"PreToolUse": [HookMatcher(..., hooks=[_deny_non_lithrim])]}`
  → `hooks=[_deny_non_lithrim, _pace_one_step]` (loop.py:285). The function body
  (loop.py:203-228) does not appear as any `+`/`-` line. ✔
- A-SAFE surface unchanged: a grep of the loop.py `±` lines for
  `allowed_tools|permission_mode|bypassPermissions|setting_sources|skills=` returns ONLY the
  comment-block lines and the `hooks=` registration lines — `allowed_tools`,
  `permission_mode="bypassPermissions"`, `setting_sources=[]`, `skills=[]` (loop.py:282-288) are
  all context (unchanged). Only the `hooks=` line + the additive `_pace_one_step` closure changed. ✔
- Guard trio: **17 passed** (output above). ✔

## HARD-GATE verification 2 — Pacing hook is purely additive + fail-closed-SAFE  → **PASS**

- **Registration order, live-verified** (not just source): built the real options object and
  inspected `opts.hooks["PreToolUse"][0].hooks` → `['_deny_non_lithrim', '_pace_one_step']`.
  `_deny_non_lithrim` is FIRST; `_pace_one_step` is appended (loop.py:284-286). ✔
- **Any single deny wins / additive-only argument.** The two hooks are orthogonal in the
  dangerous direction. `_pace_one_step` (loop.py:255-278) returns `{}` (allow) for everything
  except a 2nd+ tool whose name ∈ `_STEP_PROPOSING_WRITES`. Live-verified `_STEP_PROPOSING_WRITES ⊆
  {lithrim tool names}` (set-difference empty) — so pacing only ever further-restricts tools the
  deny hook ALREADY allows. It can never *grant* a non-lithrim tool, because returning `{}` is "no
  decision," and `_deny_non_lithrim` independently denies any name not starting with
  `mcp__lithrim__`. (Note: hook dispatch + deny-precedence is enforced CLI-side by the Claude Code
  hook engine, not in the Python SDK 0.2.90 — but the additive argument does not depend on
  ordering, only on the deny hook running independently, which it does as a registered matcher.) ✔
- **`except: return {}` fail-open is safe.** A malformed `input_data` reaching `_pace_one_step`
  fails open (abstains). The SAME malformed payload reaches `_deny_non_lithrim`, whose own
  `except: name = ""` (loop.py:215-216) yields `""`, which does not start with `mcp__lithrim__` →
  **deny**. So a malformed payload fails CLOSED at the deny hook; pacing's fail-open is irrelevant
  to the security bound. The "UNCOUNTED-but-dangerous tool through pacing" scenario is moot: the
  only tools pacing leaves uncounted are reads / `$0` runs / look-teach moves — and even an unknown
  tool name that slips pacing is still bounded by the deny hook. ✔
- **Turn-scoped counter genuinely resets per turn.** `_build_options` (loop.py:231) is a plain
  `def` — no `@lru_cache`/memoization anywhere. `pacing = {"writes": 0}` (loop.py:253) is created
  fresh inside each `_build_options` call. `_real_source` (loop.py:328) calls
  `opts = _build_options(ctx)` (loop.py:336) at the top of its body, and `_real_source` is a fresh
  async generator selected per `run_chat` invocation (loop.py:369 `src = source or _real_source`),
  i.e. once per `/v1/chat` turn. New turn → new `_real_source` call → new `_build_options` → new
  `pacing` dict. Reset by construction. ✔ The W2b test corroborates: a second `_build_options(ctx)`
  yields a hook whose 1st write is allowed again (test_uap5b_chat.py:387-389).

## HARD-GATE verification 3 — Tests are NON-VACUOUS  → **PASS**

- **W2b pacing test** (`test_pacing_hook_caps_step_proposing_writes_to_one_per_turn`,
  test_uap5b_chat.py:347-389). Against a no-op hook (`return {}` always) it WOULD FAIL: it asserts
  `_drive(pace, "author_judge") == {}` (1st allow) THEN `_drive(pace, "add_grounding_contract")`
  returns a `hookSpecificOutput` with `permissionDecision == "deny"` and reason containing "One
  setup step per turn" (a no-op hook returns `{}`, so this `["hookSpecificOutput"]` subscript would
  KeyError/AssertionError). It further asserts `get_agent`/`review_runs`/`run_eval` → `{}` (reads/
  $0 free) and a fresh `_build_options` re-allows the 1st write (reset). Non-vacuous. ✔
  `test_pacing_hook_fails_open_for_itself` asserts `pace(None,...)` and `pace({},...)` don't raise. ✔
- **W1 coercion test** (`app.coerce.test.jsx`). **Judged skeptically.** The executor's flagged
  deviation (React harness + BFF-contract replica because jsdom can't flush the App mount-effect's
  dynamic-`import("./bff.js")` chain) is **acceptable, not vacuous**, for three verified reasons:
  (1) The harness `useEffect` body (app.coerce.test.jsx:35) is **byte-identical** to the real
  app.jsx coercion (app.jsx:266): both are
  `if (agents.length > 0 && !agents.includes(activeAgent)) setActiveAgent(agents[0]);` (confirmed
  via grep — same string at both sites). It is a verbatim copy, not a behavioral re-implementation
  that could drift in logic. (2) The dynamic-import obstacle is real: `refreshAgents` (app.jsx:247)
  does `const { listAgents } = await import("./bff.js")`, and the App mount fires a chain of such
  imports — so a full-App jsdom mount genuinely can't flush the effect synchronously. (3) The
  harness's `sessionKey`-untouched invariant maps to a REAL mechanism: `CenterPane key={sessionKey}`
  (app.jsx:382) is the sole remount trigger, bumped only by `setSessionKey` (S-BS-89 "New
  evaluation"); the coercion uses `setActiveAgent` only, so the "no chat-remount loop" assertion is
  not a strawman. The replica `resolveAgent` (lines 20-24) additionally pins the BFF contract
  (absent→`agents[0]` / present→honored / empty→unchanged) so a future BFF drift is catchable.
  **Residual risk (OBSERVATION-B):** the harness copy could silently drift from app.jsx:266 if
  someone edits the app and forgets the test — a `key={sessionKey}`-style structural guard or
  importing the effect would be stronger, but for a one-line effect this is standard and the test
  is non-vacuous. ✔
- **W2a prompt test.** `test_system_prompt_foregrounds_the_one_step_and_wait_rule`
  (test_uap5b_chat.py:312-323) asserts the NEW wording: `"ONE STEP PER TURN"`, `"EXACTLY ONE"` +
  `"config PROPOSAL"`, `"then STOP"`, `"do NOT chain multiple"` (case-folded), and
  `"Reading the live state is FREE"`. `test_system_prompt_stays_a_superset_back_compat`
  (test_uap5b_chat.py:326-337) asserts the 4 SUPERSET markers: base persona
  (`"Lithrim's setup assistant"`), honesty contract (`"HONESTY IS THE PRODUCT"`), active-agent
  naming (`` "`eval-1`" ``), operator-degrade clause (`"drop back to the"` + `"reactive operator
  posture"`). Both the new wording AND all 4 back-compat markers are asserted. ✔ `test_shepherd.py`
  was additionally updated (5-line diff) to track the foregrounded `"ONE STEP PER TURN"` /
  `"EXACTLY ONE"` / `"then STOP"` wording (replacing the stale `"ONE step at a time"`). ✔

## HARD-GATE verification 4 — Honest-Δ (commercial moat)  → **PASS, one NON-BLOCKING seam**

- **A1/A2/A3 are correctly scoped.** The PROOF capsule
  (`docs/research/PROOF_bench-salvage_SHEPHERD-1b_2026-06-15.md`) splits cleanly: the "Evidence
  (grounded, not narrated) — code/test layer" section (lines 70-100) covers A1/A2 at the code/test
  layer; the live A1/A2/A3 beats are under a heading literally titled
  **"(A-LIVE :5180 re-drive) — PENDING-MONITOR-LIVE"** (lines 102-109) with the items to fill on the
  live pass. **No live win is claimed that wasn't captured.** The video is also "PENDING-MONITOR-LIVE"
  (lines 120-124). Honest. ✔

- **The prompt "never auto-commit … the Save IS the approval gate" seam.** → **FINDING 1
  (NON-BLOCKING).**
  - The stanza line `"PROPOSE, never auto-commit: surface the editor card for the human to Save (the
    Save IS the approval gate)"` is at **loop.py:171**.
  - The authoring path commits IMMEDIATELY (audited), not pending-on-Save:
    `author_judge → put_judge_endpoint` calls `save_judge(jc, db_path=…, actor=…,
    audit_log=AuditLog(db_path=db_path), rationale=rationale)` synchronously inside the request
    (verified at **apps/bff/app.py:1018-1019**). There is no deferred-DB-commit gate.
  - **1b did NOT introduce this line.** In `git diff da2a0a8 HEAD -- apps/bff/agent/loop.py` the
    line appears only as a **context (unchanged) line** — grepping the `±` lines for it returns
    nothing. `git log -S "the Save IS"` attributes it to `fdb141e` (the parent SHEPHERD-1 cycle's
    proactive-shepherd commit), and `git merge-base --is-ancestor fdb141e da2a0a8` → true (it
    pre-exists this cycle's base). It was preserved verbatim as part of the W2a SUPERSET. ✔
  - **Is the capsule's gate description accurate?** YES. The capsule has a dedicated section
    "Commit semantics — stated accurately (honesty-is-the-moat; clarification #1)" (lines 48-63)
    that states the persist is "immediate (audited)" at "app.py:1018-1019", explicitly says the
    "approval gate" is NOT a "nothing-commits-until-Save" pending-commit gate, re-frames the real
    gate as (1) the pacing cap + (2) re-editability + (3) the immutable audit trail, and states
    "this capsule does not overclaim a pending-commit gate." The capsule does NOT inherit the
    prompt's looser phrasing — it corrects it. ✔
  - **Verdict:** the prompt line at loop.py:171 is a **pre-existing honesty seam** — "the Save IS
    the approval gate" overstates the mechanism (the editor-card Save is a UX review affordance, not
    a transactional commit gate; the write already persisted). It is NOT a 1b regression and the
    capsule already discloses the true semantics. Worth filing for a future prompt-wording cycle so
    the system prompt itself matches the capsule's honest framing.
  - **Proposed seam:** **S-BS-151 (LOW)** — "shepherd stanza overstates the Save as an approval
    *gate*; the authoring tools persist immediately-and-audited (app.py:1018-1019). Reword
    loop.py:171 so the prompt's framing matches the capsule's honest 3-part gate (pacing cap +
    re-editability + audit trail). Pre-existing from SHEPHERD-1 (`fdb141e`); preserved by the 1b
    SUPERSET; not a 1b regression." Severity LOW: it does not cause a manufactured win (no run-time
    fabrication), and the human-facing capsule is already accurate; it is a prompt-prose honesty
    tidy, not a correctness or safety defect.

## HARD-GATE verification 5 — Scope + suite  → **PASS**

- `git diff da2a0a8 HEAD --stat` is **exactly the 7 expected files**: the session log,
  `apps/bff/agent/loop.py`, `apps/shell/src/app.coerce.test.jsx`, `apps/shell/src/app.jsx`,
  `docs/research/PROOF_bench-salvage_SHEPHERD-1b_2026-06-15.md`, `tests/test_shepherd.py`,
  `tests/test_uap5b_chat.py`. No stray edits. ✔
- **No prettier reformat:** `app.jsx` numstat = `12 0` (12 added, 0 deleted — a pure additive
  block at app.jsx:257-267, no reformat sweep). The hand-compact-JSX / no-prettier guardrail held. ✔
- **No new GenUI card types:** grep of the added lines for `cardType|card_type|GenUI|kind:` →
  empty. ✔
- **Suite:** `2 failed, 542 passed, 4 skipped` — only the pre-existing observation-pipeline flakes
  (pass in isolation: 13 passed). ✔

---

## Findings ledger

| # | Severity | Finding | Cite |
|---|---|---|---|
| 1 | NON-BLOCKING | Shepherd stanza calls the editor-card Save an "approval gate," but `author_judge`→`put_judge_endpoint`→`save_judge(audit_log=…)` persists immediately-and-audited. Pre-existing from SHEPHERD-1 (`fdb141e`, ancestor of `da2a0a8`); preserved verbatim by the 1b SUPERSET; the capsule discloses the true semantics. Propose **S-BS-151 (LOW)**. | loop.py:171 / apps/bff/app.py:1018-1019 / PROOF lines 48-63 |
| A | OBSERVATION | Driver §4/§5 cite the moat at `runtime/council/...`; the live tree path is `lithrim_bench/runtime/council/...`. Path shorthand only — moat zero-diff verified at the correct path. Correct in the next driver. | driver §4-§5 vs `lithrim_bench/runtime/council/` |
| B | OBSERVATION | The W1 coerce test's harness `useEffect` is a byte-identical *copy* of app.jsx:266, not an import of the real effect; a future app.jsx edit could silently desync it. Acceptable for a one-line effect (and the BFF-contract replica + sessionKey invariant add real coverage), but a structural import/guard would be stronger. | app.coerce.test.jsx:35 vs app.jsx:266 |
| C | OBSERVATION | SDK 0.2.90 dispatches PreToolUse hooks CLI-side, so deny-precedence is enforced by the Claude Code hook engine, not the Python SDK. The additive-safety argument does NOT depend on ordering — only on the deny hook running independently (it does, as a registered matcher) and on `_STEP_PROPOSING_WRITES ⊆ lithrim tools` (verified). Noted so the safety claim isn't read as an in-SDK ordering guarantee. | loop.py:284-286 |

---

## Discipline self-check

- [x] Read the spec (driver) + CRITIC.md before reading the executor's session log.
- [x] Read the diff via `git diff`/`git show` against the commits, not the executor's prose.
- [x] Each finding cites spec/contract file:line AND implementation file:line.
- [x] Did NOT edit any code, spec, or driver — read-only except this critique file.
- [x] Independently re-ran the guard trio + canonical suite + the isolation check; did not take
      counts from the executor's report.

**Overall: PASS** (0 BLOCKING). The moat + A-SAFE surface are byte-frozen, the pacing hook is
purely additive and fail-closed-safe via the independent deny hook, the W1/W2a/W2b tests are
non-vacuous, the honest-Δ is intact (live beats correctly marked PENDING-MONITOR-LIVE), and the
diff is scoped to the 7 expected files. The single NON-BLOCKING seam (S-BS-151) is a pre-existing
prompt-prose honesty tidy, not a 1b regression.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
