# Spec-Adherence Critique — `bench-salvage` phase `SHEPHERD-1`

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `SHEPHERD-1` (the agent-led onboarding "shepherd" harness — plan + approval gates)
- **Driver bundle:** `bench-salvage-phaseSHEPHERD-1-agent-led-onboarding-harness-driver` v1
- **Commits audited:** `95c427e` → `224632d` (6 commits over parent `5b966ff`)
- **Spec(s)/driver read against:** `.devloop/prompts/bench-salvage_phaseSHEPHERD-1_agent-led-onboarding-harness-plan-gates_driver.md` (§2 W1–W5, §4 guardrails, §5 A1–A7); CRITIC.md; CRITIQUE_TEMPLATE.md
- **Critique mode:** `fresh-critic` (separate session, no prior implementation context)
- **Date:** 2026-06-15
- **Reviewer:** critic session (cold read; reconstructed diff via `git show`, re-ran both suites, broke + restored a scratch mapping, ran a parent-commit worktree)

---

## Verdict

**`NON-BLOCKING FINDINGS`** — 0 BLOCKING / 3 NON-BLOCKING / 1 OPEN-QUESTION

One sentence: SHEPHERD-1 is faithful, in-scope, and non-vacuous on every axis I could break — the moat/scope freeze is exact (council/signals/tools.py/registry zero-diff), the W1 rail derivation + W2 superset stanza + W3 save→advance + W4 entry all match the driver, both suites match the executor's claimed counts with the residual failures proven pre-existing at `5b966ff` — the only findings are a re-used seam ID (S-BS-146 collides with CONV-UX-1), the "N / 6"→"N / 5" denominator decision (documented, but the driver literal said "N / 6"), a harmless dead KB step-prompt, and the genuinely-unprovable-at-this-layer proactivity claim (correctly deferred to the monitor's A-LIVE re-drive).

---

## 1. Surface fidelity

| Driver definition | Implementation | Match? | Severity |
|---|---|---|---|
| W1 `deriveSteps` pure helper in `apps/shell/src/journey.js` | `journey.js:55` `export function deriveSteps(agentCfg, runs=[], activeAgent=null, runResult=null)` → `{steps, done, total}` | exact | — |
| W1 Domain done ⟺ ontology_ref | `journey.js:34-35` `case "Domain": return !!ep.ontology_ref` | exact | — |
| W1 Judges done ⟺ roster non-empty | `journey.js:36-37` `(ep.judges || []).length > 0` | exact | — |
| W1 Ground truth done ⟺ tools OR grounding_checks | `journey.js:38-39` `(ep.tools||[]).length>0 \|\| (ep.grounding_checks||[]).length>0` | exact | — |
| W1 KB optional, never `current`/blocking | `journey.js:24` `OPTIONAL=Set(["Knowledge base"])`; `:62` skipped when choosing current | exact | — |
| W1 Run done ⟺ ≥1 run for active agent | `journey.js:42-43` `(runs||[]).some(r=>r && r.agent===activeAgent)` | exact | — |
| W1 Review done ⟺ run opened (monitor decision: runResult non-null) | `journey.js:44-45` `case "Review": return runResult != null` | exact (distinct-beat option chosen, PROOF §"two decisions") | — |
| W1 `current` = first incomplete REQUIRED; literal `"current"` | `journey.js:60-68`; `panes.jsx` `"step " + s.state`; CSS `styles.css:254` `.step.current` | exact — literal is `"current"`, NOT `"active"` | — |
| W1 "N / 6" count | `journey.js:72-74` `total = required.length = 5` (KB excluded); `panes.jsx:78` renders `{count.done} / {count.total}` → **"N / 5"** | DEVIATION (denominator 5, not 6) | NON-BLOCKING |
| W2 shepherd-variant `_system_prompt` | `loop.py:133-134` `+ _SHEPHERD_STANZA`; `loop.py:142-169` the stanza | superset append; NOT a mode flag | — |
| W3 save→advance callback | `app.jsx` `onConfigSaved={refreshJourney}`; `panes.jsx` `captureSetup` fires `onConfigSaved?.()` | small callback on existing `onResult` | — |
| W4 shepherd entry chips | `panes.jsx` `data-testid="start-guided-setup"` + `"next-step-prompt"`; old 3 chips removed | exact | — |

**Findings:**

- `[NON-BLOCKING]` **"N / 6" → "N / 5" count denominator.** Driver §2 W1 says verbatim *"compute the 'N / 6' from completed."* The implementation excludes the optional KB step from the denominator (`journey.js:72-74`, `total = required.length = 5`), so the rail reads **"N / 5"**, not "N / 6". This is a *defensible* reading of the same §2 W1 bullet that says KB "never blocks progress" and "never counts toward the denominator" (`journey.js:62` comment), and it is openly tested (`journey.test.jsx:18,62,81,102` assert `1 / 5` / `0 / 5` and that the literal `"4 / 6"` is *gone*). So it is a documented, tested judgment call — not hidden drift. But the driver's literal said "6", so I flag it for the spec author to lock. **Disposition:** accept "N / 5" (the optional-step-excluded count is the more honest plan metric) OR update the driver text. NON-BLOCKING. Note the stale "N / 6" wording survives in two comments (`journey.js:18,73` reference "4 / 6"/"N / 6") while the code yields N/5 — cosmetic doc lag.

No other surface drift. All public symbols (`deriveSteps`, `nextStep`, the `LeftRail`/`CenterPane` props, `_SHEPHERD_STANZA`) match the driver's intent.

---

## 2. Behavioral fidelity

### Behavior 1: W1 rail derivation maps live state → plan (non-vacuous)

- **Driver assertion:** §5 A1 *"an empty eval shows Domain `active` + the rest `todo` + a correct 'N/6'; an agent with judges shows Judges `done`."*
- **Test:** `journey.test.jsx:12-91` — the full ladder (empty→Domain current; +ontology→Domain done/Judges current; +judges→Judges done; +tools|checks→Ground truth done; KB done-but-never-current; run-for-this-agent only; Review distinct beat; `nextStep` null when complete) + `:98-105` the rail renders `1 / 5` not `4 / 6`.
- **Implementation:** `journey.js:32-77` `isDone` + `deriveSteps`; `app.jsx` `deriveSteps(agentCfg, runs, activeAgent, runResult)`.
- **Chain closes?** **YES.** I PROVED non-vacuity: scratch-edited `journey.js:37` `case "Judges": return true` → `npx vitest run src/journey.test.jsx` = **5 failed / 7 passed** (the empty-agent, ontology, +judges, KB, and save→advance cases all flip), then restored byte-identical (`git status` clean). The test genuinely exercises the mapping.

### Behavior 2: W2 shepherd stanza is a SUPERSET (back-compat) + bounded

- **Driver assertion:** §2 W2 *"Keep it a BOUNDED prompt change… default behavior must stay back-compatible for non-onboarding chats"*; §5 A2.
- **Test:** `tests/test_shepherd.py:46-60` asserts the base persona (`"You are Lithrim's setup assistant"`), the HONESTY contract (`"HONESTY IS THE PRODUCT"`, `"A manufactured win is a product FAILURE"`), the active-agent naming (`` `eval-7` ``, `"Operate on"`) all survive, and the stanza is *appended after* both; `:63-72` proves per-call naming is non-vacuous (`agent_alpha` present / `agent_beta` absent and vice-versa).
- **Implementation:** `loop.py:133-134` appends `_SHEPHERD_STANZA` to the existing `_system_prompt` body; the persona head + HONESTY block + active-agent naming live ABOVE the append point (untouched). `_build_options` (`loop.py:206`) and `_deny_non_lithrim` (`loop.py:178`) are OUTSIDE every diff hunk — byte-identical.
- **Chain closes?** **YES.** I independently ran `_system_prompt('eval-7')` in `debuglithrim` and confirmed all back-compat literals are present and the stanza is ordered after persona + honesty. No `ChatRequest`/`ToolContext` widening (the only "ChatRequest/ToolContext" string in the diff is inside the new *comment* at `loop.py:139`). No mode flag. The last clause (`loop.py:168-169` *"If setup is already COMPLETE… drop back to the reactive operator posture"*) degrades it. Back-compat test is non-vacuous: absent the append, the `SHEPHERD THE ONBOARDING` assertions (`test_shepherd.py:59-60,71-72`) fail.

### Behavior 3: W3 approval-gate save→advance (Save → re-derive → step flips done)

- **Driver assertion:** §2 W3 *"on the human's Save (the existing audited write), the rail re-derives → the step flips to `done`… No server-side session state"*; §5 A3.
- **Test:** `panes.shepherd.test.jsx:64-77` mounts a proposed JudgeEditor card, clicks the real **Save judge** button, asserts `onConfigSaved` fires (the rail re-derive trigger); `journey.test.jsx:115-123` proves the re-derive flips Judges `current`→`done` and `done` increments by 1.
- **Implementation:** `panes.jsx` `captureSetup = (key) => (result) => { setSetup(...); onConfigSaved?.() }` (rides the editors' existing `onResult`); `app.jsx` `onConfigSaved={refreshJourney}`; `refreshJourney` (`app.jsx`) re-fetches `getAgent(activeAgent)` + `getRuns()` (offline-safe) and re-derives. No server-side store (confirmed — only React state + the two existing GET endpoints).
- **Chain closes?** **YES.** The frozen editor card components are untouched (the callback rides their existing emit, not their internals — `panes.jsx` comment + the zero-diff on the card files). `registry.js` `KNOWN_TOOLS` zero-diff (no new card type).

**Findings:**

- `[NON-BLOCKING]` **Proactivity is prompt-instructed, not mechanically enforced, and unprovable at the code/test layer.** The stanza (`loop.py:142-169`) is a genuine, well-formed lead-the-journey instruction (read live state via `get_agent`/`review_runs` → find first incomplete → open with guidance → propose ONE step → degrade when complete) and is *not* cosmetic — it materially changes the agent's instructions, and W4 primes the opening message (`"Help me set up my first evaluation from scratch"`). BUT: `run_chat`/`_run_streaming` (`loop.py:227,276`) drive the loop from a *user* `message` — there is **no unsolicited opening turn** (consistent with the §4 "no server-side session state" guardrail + S-BS-87 history-replay). So whether the agent actually LEADS is a runtime property of the model honoring the system prompt, which the test layer (correctly) only asserts at the prompt-construction level (`test_shepherd.py`). The executor honestly marks A2's live-lead `PENDING-MONITOR-LIVE` and the PROOF AFTER as owed. **Disposition:** this is the monitor's A-LIVE re-drive gate, not a code-layer block. My code-level read: a fresh/empty eval whose first message is the W4 "Start guided setup" fill will *plausibly* make a well-behaved model lead — the instruction is clear and the live state read is in the agent's existing toolset. NON-BLOCKING; the live re-drive is the real test.

---

## 3. Out-of-scope intrusion

Driver §2 deliverables: W1 (rail derivation — `data.jsx`/`panes.jsx`/`journey.js`), W2 (`loop.py` stanza), W3 (save→advance callback), W4 (empty-state entry — `panes.jsx`), W5 (tests), A7 (PROOF + session log).

`git diff 5b966ff HEAD --stat` (9 files):

```
.devloop/sessions/session-...SHEPHERD-1-2026-06-15.json | 141 ++   (A7)
apps/bff/agent/loop.py                                   |  38 ++   (W2)
apps/shell/src/app.jsx                                   |  33 ++   (W1 fetch + W3 wiring)
apps/shell/src/journey.js                                |  84 ++   (W1 NEW)
apps/shell/src/journey.test.jsx                          | 124 ++   (W5)
apps/shell/src/panes.jsx                                 |  65 ++   (W1 rail + W3 + W4)
apps/shell/src/panes.shepherd.test.jsx                   |  78 ++   (W5)
docs/research/PROOF_...SHEPHERD-1_2026-06-15.md          |  91 ++   (A7)
tests/test_shepherd.py                                   |  72 ++   (W5)
9 files changed, 705 insertions(+), 21 deletions(-)
```

- **Moat freeze EXACT:** `git diff 5b966ff HEAD -- lithrim_bench/runtime/council/compliance_council.py lithrim_bench/runtime/council/signals.py apps/bff/agent/tools.py` = **EMPTY** (reproduced). `apps/shell/src/genui/registry.js` `KNOWN_TOOLS` = **zero-diff** (no new card type). The frozen editor card components = byte-untouched (W3 rides `onResult`).
- **No re-theme / no prettier:** `styles.css` / `theme.css` / `journey.css` = **zero-diff**. The two modified shell files churn 33 + 65 surgical lines (no whole-file reformat).
- **`data.jsx` claimed-but-untouched:** the task brief listed `data.jsx` (W1 "step model"), but the executor put the step model in the NEW `journey.js` and left `data.jsx`'s `STEPS` template intact (read-only import). This is a *narrower* footprint than the brief implied — not an intrusion. Noted for the record; the executor's session-log file count ("7 code") + the actual 9-with-artifacts both reconcile.

**Findings:**

- `[NON-BLOCKING]` **Dead KB step-prompt in `STEP_PROMPTS`.** `panes.jsx` `STEP_PROMPTS` includes a `"Knowledge base"` entry, but by the W1 design KB is never `current` (`journey.js:24,62`), so `nextStepName` is never `"Knowledge base"` and the `"Next: Knowledge base"` chip can never render. Harmless (the `STEP_PROMPTS[nextStepName]` guard `panes.jsx` simply never hits it), but it is dead config. **Disposition:** accept or trim in a follow-up. NON-BLOCKING.

All diffed files map to deliverables. No drive-by refactors, dependency bumps, or formatting passes detected.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: the Review-step done-signal (Run-dup vs distinct beat)

- **Driver text:** §2 W1 *"Review done ⟺ a run exists/has been opened"* (ambiguous: "exists" = Run-dup; "opened" = distinct beat). §5 A1 doesn't disambiguate.
- **Implementation decided:** Review done ⟺ `runResult` non-null (the distinct-beat option) — `journey.js:44-45`; tested `journey.test.jsx:73-82`.
- **Question for spec author:** lock Review = `runResult`-non-null (distinct beat) as canon? (The executor records this as a monitor-preferred decision in the PROOF "two decisions used".)
- **Recommended resolution:** ACCEPT — the distinct-beat reading is the better plan UX (Review isn't a Run duplicate).

**Findings:**

- `[OPEN-QUESTION]` Review-step signal — surfaced above; recommend ACCEPT.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 1 (N/5 vs N/6) | 0 |
| 2 | Behavioral fidelity | 0 | 1 (proactivity is prompt-only; live-deferred) | 0 |
| 3 | Out-of-scope intrusion | 0 | 1 (dead KB step-prompt) | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 1 (Review signal) |

**Total BLOCKING: 0** → cycle MAY close.

Plus one **honesty/bookkeeping finding** (CRITIC §"honesty check", does not map to a template question):

- `[NON-BLOCKING — HONESTY]` **Seam-ID collision: S-BS-146 re-used.** The SHEPHERD-1 session log (`session-...SHEPHERD-1-2026-06-15.json:124`) opens **S-BS-146** for "app.chat.test.jsx getMeta-mock → 2 unhandled rejections." But **S-BS-146 was already assigned in CONV-UX-1** to the "shared-part `auto` default" seam (`adapter.py:66,73`) — confirmed in both `session-...CONV-UX-1-2026-06-15.json:134,172` AND the CONV-UX-1 fresh-critic critique (`critique-bench-salvage-CONV-UX-1-2026-06-15.md:60,96-97,116`). S-BS-147 is ALSO taken (CONV-UX-1 "coalesce duplicate timeline labels"). The new getMeta-mock seam should be re-numbered to the next free id — **S-BS-148**. The seam itself is correctly characterized (CONFIRMED pre-existing, low severity, one-line mock fix) — only the ID is wrong. **Disposition:** monitor renumbers to S-BS-148 in close-out.

---

## Required actions

No BLOCKING findings — none required to close.

NON-BLOCKING / OPEN-QUESTION dispositions for the monitor:

1. **Seam-ID collision (S-BS-146):** renumber the getMeta-mock seam to **S-BS-148** in the stream state during close-out. *(monitor)*
2. **"N / 6" → "N / 5":** confirm the count denominator with the spec author; if "N / 5" is accepted, scrub the stale "4 / 6"/"N / 6" wording in `journey.js:18,73` comments. *(spec author / follow-up)*
3. **Dead KB `STEP_PROMPTS` entry:** trim in a follow-up or accept as inert. *(accept)*
4. **Review-step signal:** lock the distinct-beat reading as canon. *(spec author — recommend ACCEPT)*
5. **Proactivity:** the A-LIVE re-drive (A2/A4) is the real test of lead-the-journey + the PROOF AFTER — proceed with the monitor's `:5180` re-drive. *(monitor)*

---

## Suite re-run (independently reproduced)

- **Python:** `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=…/lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare python -m pytest -q` → **538 passed, 2 failed, 4 skipped** (matches the executor's claim). The 2 failures are `lithrim_bench/runtime/observation/tests/test_observation_pipeline.py::{test_importing_observation_does_not_load_compliance_modules, test_default_run_pulls_no_heavy_deps}` — the **S-BS-96 import-isolation order-flakes**: the observation module is **zero-diff** in this cycle, and both **PASS in isolation** (`2 passed in 0.01s`). NOT SHEPHERD-1.
- `tests/test_shepherd.py` → **4 passed**. Moat guard trio (`test_6bclean_seam_guard.py` + `test_6bclean_attestation.py`) → **17 passed**, and the trio is non-vacuous in both directions by construction (`test_unauthorized_deletion_of_consensus_still_fails`, `test_unauthorized_edit_to_evaluate_dspy_still_fails`).
- **Shell Vitest (HEAD):** `npx vitest run` → **1 failed | 105 passed (106), 2 errors**. The new files `journey.test.jsx` + `panes.shepherd.test.jsx` = **15 passed (15)** (matches "+15 new").
- **Shell Vitest (parent `5b966ff`, run in a throwaway worktree):** **1 failed | 90 passed (91), 2 errors** — the SAME failure (`app.test.jsx > … renders the titlebar with the mode-switch …`, the S-BS-145 titlebar test) and the SAME 2 errors (the `getMeta` mock gap, `app.jsx:145`, originating in `panes.chat.test.jsx` + `app.chat.test.jsx`, both untouched by this diff). **Delta = exactly +15 passing; the residual 1-fail/2-errors are proven pre-existing.** Worktree removed; main tree clean at `224632d`.

---

## Critic discipline self-check

- [x] Read the driver/spec without reading the executor's session log first (session log read last, only to cross-check the seam ID + counts)
- [x] Read the diff via `git show`/`git diff` against commits, not the executor's prose summary
- [x] Each finding cites file:line (driver §/quote + impl file:line)
- [x] Did NOT edit any code, spec, or driver (the one scratch mutation to `journey.js` for non-vacuity was restored byte-identical; `git status` clean — verified)
- [x] Did NOT drive the browser (the monitor runs the live re-drive); did NOT confer with monitor or executor

**Overall recommendation: PASS (non-blocking).** 0 BLOCKING. The code/test layer is faithful, in-scope, non-vacuous, and the moat is byte-frozen. The A1–A4/A7 live acceptance (does the shepherd actually LEAD end-to-end + the PROOF AFTER) remains the monitor's A-LIVE re-drive, correctly deferred. Renumber the S-BS-146 collision to S-BS-148 at close.

---

## Appendix: commits audited

```
224632d docs(shepherd): PROOF capsule + session log — onboarding before->after (A7)
725b2e7 test(shepherd): rail derivation + shepherd-prompt + save-advance tests (W5)
f89e8d9 feat(shepherd): shepherd-aware empty-state entry (W4)
1c9f01b feat(shepherd): approval-gate save->advance loop (W3)
fdb141e feat(shepherd): proactive plan-aware shepherd system-prompt mode (W2)
95c427e feat(shepherd): derive the setup-journey rail from live config state (W1)
```

## Appendix: files changed

```
.devloop/sessions/session-...SHEPHERD-1-2026-06-15.json | 141 +++
apps/bff/agent/loop.py                                   |  38 +-
apps/shell/src/app.jsx                                   |  33 +-
apps/shell/src/journey.js                                |  84 +++ (NEW)
apps/shell/src/journey.test.jsx                          | 124 +++ (NEW)
apps/shell/src/panes.jsx                                 |  65 +-
apps/shell/src/panes.shepherd.test.jsx                   |  78 +++ (NEW)
docs/research/PROOF_...SHEPHERD-1_2026-06-15.md          |  91 +++ (NEW)
tests/test_shepherd.py                                   |  72 +++ (NEW)
9 files changed, 705 insertions(+), 21 deletions(-)
```
