# Spec-Adherence Critique — `bench-salvage` phase `FAUTH-3` (+ `FAUTH-3a`)

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `FAUTH-3` (the ASSIST keystone, G2) `+ FAUTH-3a` (the reliability + empty-dict fixes)
- **Driver bundle:** `bench-salvage-phaseFAUTH-3-assist-prose-to-params-driver`
- **Commits audited (CODE range):** `457c4ae..1efd4b0` — `177e691, 11cace0, db3d88d, d66479e, 54679cb, c21816a, 69b2204, 1efd4b0` (HEAD `1d3c5d4` is a devloop-bookkeeping chore, not audited)
- **Spec(s) read against:** `docs/specs/SPEC_FLAG_AUTHORING_SELF_SERVE.md` §3 (SPINE INVARIANT), §4 (Assist step), §6 (G2)
- **Critique mode:** `fresh-critic` (separate session, no implementation context)
- **Date:** `2026-06-20`
- **Reviewer:** cold critic (independent re-derivation; monitor completed the cycle in-session after the executor subagent was sandbox-blocked twice — independence especially load-bearing here)

---

## Verdict

**`CLEAN`**

One sentence: Gate 0 is green (28==28, zero net new failures — the single differing row is the documented `test_pack_dist::test_a1` ↔ `test_byoc_provider` order-flap; FAUTH-3 files ruff-clean; ContractBuilder vitest 9/9), the spine invariant holds NON-VACUOUSLY both ways, `author_contract` is emit-only with a pure deterministic suggestion helper, the MOAT + `kb_context` retrieval + the FAUTH-2 gate are 0-diff, A-SAFE is unchanged (tool count 20, no PAID_KEY), and the two A-LIVE findings (default-fill + the empty-dict trap) are real RED→GREEN.

---

## 0. Deterministic gate (supreme — runs first)

| Check | Command (verbatim) | Result |
|---|---|---|
| Test suite @ HEAD `1efd4b0` | `env PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare python -m pytest -q` | **28 failed / 703 passed / 23 skipped** |
| Test suite @ parent `457c4ae` (worktree) | same, abs `LITHRIM_BENCH_PACKS_DIR` | **28 failed / 692 passed / 26 skipped** |
| Net-new failures (set diff) | `comm -23 head_fails parent_fails` | **0 net new** — 27 common; only-at-HEAD = `test_pack_dist::test_a1`, only-at-parent = `test_byoc_provider::test_build_trio_no_models_is_all_azure_back_compat` → the documented order-flap (28==28) |
| New FAUTH-3 tests | `pytest -q tests/bff/test_fauth3_assist.py tests/bff/test_contract_builder_part.py` | **13 passed** (the +11 pass delta vs parent = new coverage) |
| Linter (FAUTH-3 files) | `ruff check apps/bff/agent/{assist,tools,adapter,loop}.py tests/bff/test_fauth3_assist.py tests/bff/test_contract_builder_part.py` | **All checks passed** |
| Linter (repo-wide) | `ruff check .` | 404 errors at HEAD **and** identical 404 at parent `457c4ae` → PRE-EXISTING baseline, not regressed by this cycle |
| Type check | (no project type-checker configured — CLAUDE.md names pytest + ruff + vitest + npm build only) | n/a |
| UI (FAUTH-3 surface) | `cd apps/shell && npx vitest run src/genui/ContractBuilder.test.jsx` | **9 passed** |
| UI (full vitest) | `cd apps/shell && npx vitest run` | 1 failed / 154 passed — the 1 failure is `src/app.test.jsx` ("Shell" tab role), a file NOT in the FAUTH-3 diff (empty `git diff 457c4ae..1efd4b0 -- apps/shell/src/app.test.jsx apps/shell/src/app.jsx`); foreign-WIP / pre-existing, outside the audited range |

**Tests-first check:** YES — RED→GREEN demonstrated and re-proven in a worktree:
- `177e691` (test-only, 2 files) is RED at that commit: `ImportError: cannot import name 'assist'` (the helper module did not exist).
- `54679cb` (test-only) is RED at that commit: `KeyError: 'suggested_params'` (named-flag default-fill not yet implemented; fixed by `c21816a`).
- `69b2204` (test-only, 1 file) is RED at that commit: `KeyError: 'suggested_params'` on the empty-dict path (the `{}`→None normalization not yet present; fixed by `1efd4b0`).
All three `test(...)` commits precede their `fix`/`feat` commits.

**Gate verdict:** **GREEN — proceed to the 4 questions.** (The repo-wide 404 ruff baseline and the `app.test.jsx` vitest failure are both pre-existing/foreign to the audited range, not regressions of this cycle.)

---

## 1. Surface fidelity

The FAUTH-3 "public surface" is the conversational `author_contract` tool schema + the `contract_builder_part` emit shape + the `ContractBuilder` props + the pure `assist.suggest_presence_check_params` helper.

| Spec/driver definition | Implementation | Match? | Severity |
|---|---|---|---|
| R4 — EXTEND `author_contract`, additive optional knobs, NO new tool, NO PAID_KEY | `AUTHOR_CONTRACT_SCHEMA = {flag_code, suggested_params:dict, source_hint:str, question:str}` (`tools.py:147-152`); tool count **20**; `author_contract` count **1**; `PAID_KEYS=('confirm','in_process','live')` absent from all `_TOOL_SPECS` | MATCH | — |
| R1 (c) — deterministic skeleton helper supplies correct KEYS; agent fills VALUES | `assist.suggest_presence_check_params(flag_code, source_hint)` returns EXACTLY `{med_source, dosage_regex, token_min_len, noise_tokens}` (`assist.py:31-45`) | MATCH | — |
| PresenceCheck param contract (`grounding.py:119-144`) | the four keys are exactly PresenceCheck's; both required keys (`med_source`, `dosage_regex`) non-empty | MATCH | — |
| FAUTH-1 back-compat — un-suggested path is byte-identical `{agent, flag_code}` | `contract_builder_part` adds `suggested_params`/`question` to `output` ONLY when truthy (`adapter.py:104-110`); no-flag card stays `{agent:'ws0_default', flag_code:''}` (test `test_author_contract_no_flag_stays_empty`) | MATCH | — |
| ContractBuilder props — accept `suggested_params` + `question`, seed `paramsText`, Save unchanged | `ContractBuilder.jsx:54` adds `suggested_params, question: seedQuestion`; `paramsText` seeds from `JSON.stringify(suggested_params, null, 2)` else the inert default (`:72-76`); Save path untouched | MATCH | — |

**Findings:** No surface drift detected. All public symbols match the driver's R1/R4 resolutions and the PresenceCheck param contract exactly.

---

## 2. Behavioral fidelity

### Behavior 1: THE SPINE INVARIANT — the assist writes NOTHING; only an explicit Save writes (non-vacuous both ways)

- **Spec assertion:** SPEC §3 (`SPEC_FLAG_AUTHORING_SELF_SERVE.md:74-79`) — "An assist source … is AUTHORING-TIME ONLY and MUST NOT be bound to a `verification_contract`. The only thing `ground()` runs at grade time is a pinned DETERMINISTIC contract …"; §3 point 3 (`:96-99`) — assists are read-only by construction, no write path into the ontology or `ground()`.
- **Test:** `tests/bff/test_fauth3_assist.py:97-142` `test_spine_guard_assist_sequence_writes_nothing_explicit_save_does` — drives `kb_context` then `author_contract(suggested_params=…)` over a `ToolContext` where EVERY bound op except `put_grounding_contract` RAISES and `put_grounding_contract` is a spy over a `store` list; asserts `store == []` and `save_spy.calls == 0` after the assist; then calls `put_grounding_contract` explicitly and asserts `save_spy.calls == 1` and `len(store) == 1`.
- **Implementation:** `author_contract_handler` (`tools.py:611-647`) calls `ctx.emit(contract_builder_part(...))` and `_text(...)` only — no bound write op. Verified by independent trace (empty-dict named-flag call → no `_forbidden` raised → part carries the 4 PresenceCheck keys).
- **Chain closes?** YES. The guard is non-vacuous BOTH ways: the assist sequence provably writes nothing, and the explicit `put_grounding_contract` provably DOES write (so the "writes nothing" half is not a vacuous no-op).

### Behavior 2: the prose→params suggestion is deterministic (no LLM, no network)

- **Spec assertion / driver A4:** the suggestion returns exactly `{med_source, dosage_regex, token_min_len, noise_tokens}`; same input → same output; no network, no LLM.
- **Test:** `tests/bff/test_fauth3_assist.py:31-45` asserts `a == b` (determinism), `set(a) == {the four keys}`, types, and `source_hint` threading.
- **Implementation:** `assist.py` imports ONLY `from __future__ import annotations` (grep for openai/dspy/httpx/requests/urllib/socket/anthropic/azure → none). The defaults `dosage_regex`/`token_min_len`/`noise_tokens` are byte-exact clones of the canonical seeded presence_check in `tests/fixtures/_core/ontology._core_house.json` (verified: `\b\d+(?:\.\d+)?\s*(?:%|x)\b`, `4`, `["the","and","that"]`).
- **Chain closes?** YES. The helper is provably pure.

### Behavior 3: FAUTH-3a — a NAMED flag default-fills the deterministic skeleton even when the SDK passes `{}`

- **Spec/driver:** A-LIVE finding — the live agent did NOT reliably pass `source_hint`/`suggested_params`, and the SDK-MCP layer passes `{}` (not None) for an omitted dict param, yielding the inert card. The fix: default-fill the deterministic skeleton for a named flag, treating `{}` as no-suggestion.
- **Test:** `test_author_contract_default_fills_skeleton_for_named_flag` (`:215-230`) and `test_author_contract_empty_suggested_params_still_default_fills` (`:233-248`). The latter was RED at `69b2204` (`KeyError: 'suggested_params'`) and GREEN at `1efd4b0`.
- **Implementation:** `tools.py:633-637` — `_raw = args.get('suggested_params'); suggested = _raw if (isinstance(_raw, dict) and _raw) else None; … if suggested is None and flag_code: suggested = suggest_presence_check_params(...)`. The `and _raw` truthiness check is exactly the `{}`→None normalization.
- **Chain closes?** YES. The `{}` empty-dict trap is reproduced deterministically and fixed; the no-flag case is preserved (`test_author_contract_no_flag_stays_empty`).

**Note on a relaxed existing test (Q2 sharper question — was a test bent to mirror the code?):** `tests/bff/test_contract_builder_part.py` was changed (in test-commit `54679cb`) from asserting the output is EXACTLY `{agent, flag_code}` to asserting the keys plus `set(o["suggested_params"]) == {the four PresenceCheck keys}`. This is NOT a weakening-to-pass: it is the direct, intended consequence of the FAUTH-3a behavior change (a named flag now default-fills), and the new assertion STRENGTHENS the contract (it demands the correct keys, not the inert default). The companion no-flag case is tightened to assert `"suggested_params" not in output`. Legitimate.

**Findings:** No behavioral drift. All three spine-critical chains close; the one relaxed assertion is a correct, strengthened consequence of the spec'd behavior change.

---

## 3. Out-of-scope intrusion

Driver deliverables (§2): (1) `tests/bff/test_fauth3_assist.py` NEW, (2) `ContractBuilder.test.jsx` EXTEND, (3) `tools.py` extend + helper, (4) `adapter.py` `contract_builder_part`, (5) `ContractBuilder.jsx`, (6) `loop.py` prompt.

`git diff 457c4ae..1efd4b0 --name-status`:

```
M  apps/bff/agent/adapter.py
A  apps/bff/agent/assist.py
M  apps/bff/agent/loop.py
M  apps/bff/agent/tools.py
M  apps/shell/src/genui/ContractBuilder.jsx
M  apps/shell/src/genui/ContractBuilder.test.jsx
M  tests/bff/test_contract_builder_part.py
A  tests/bff/test_fauth3_assist.py
```

- `assist.py` (NEW) maps to deliverable 3 (the helper, authorized as "or a small `assist` module").
- `test_contract_builder_part.py` is not in the explicit numbered list but its change is a forced consequence of the FAUTH-3a default-fill (deliverable 3) — it would otherwise go RED; updating it in the test commit is correct, not intrusion.
- `loop.py` diff is exclusively `_SYSTEM_PROMPT` string lines (verified: every changed line is a quoted prompt-string line; no callback/deny-hook/code change).

**Findings:** All diffed files map to deliverables (or are forced consequences thereof). No drive-by refactor, no formatting pass (no prettier — `ContractBuilder.jsx` edits are hand-compact, ~13 lines), no dependency bump, no foreign-WIP sweep. No intrusion detected.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: the default `med_source` chart path (R3, partial)

- **Spec text / driver R3:** the param KEYS are fixed; for VALUES, clone the canonical seed if one exists, else curated sane defaults; `med_source` → "the canonical chart path, e.g. `patient_profile.active_medications`".
- **Implementation decided:** `assist.py:28` `_DEFAULT_MED_SOURCE = "patient_record.medications"` — a generic default, NOT the seed's `med_source` (`source_facts.referenced_terms`) and not the driver's example string. The docstring honestly flags it as "a generic chart-path default the agent overrides via `source_hint`."
- **Alternatives also spec-compliant:** the seed's `source_facts.referenced_terms`, or the driver's `patient_profile.active_medications`, or `transcript.text` (the A-LIVE value).
- **Question for spec author:** should the un-hinted `med_source` default to a canonical seeded path (so a human who Saves without editing gets a working floor), or stay generic-needs-confirm? The three proven values (`dosage_regex`/`token_min_len`/`noise_tokens`) ARE cloned byte-exact; only `med_source` is a curated guess.
- **Recommended resolution:** accept — this is exactly the disclosed seam `S-BS-FAUTH3-1` (generic `med_source` the human confirms for non-transcript checks); the human's edit+Save is the spine backstop. NON-BLOCKING / OPEN-QUESTION.

### Ambiguity 2: server-side param-KEY validation deferred (driver §3 explicit deferral)

- **Spec text:** §3 — "Server-side param-KEY validation at write time → out (the seam stays; grade-time KeyError is the backstop)."
- **Implementation decided:** no write-time validation; a wrong `med_source`/missing key surfaces only as a grade-time `KeyError` in `PresenceCheck`. Consistent with the deferral.
- **Question for spec author:** none — this is an explicit, accepted deferral. NON-ISSUE.

**Findings:** One OPEN-QUESTION (the `med_source` default), already captured as seam `S-BS-FAUTH3-1`; not BLOCKING.

---

## Summary of findings

| # | Gate / Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 0 | Deterministic gate (tests/lint) | 0 | — | — |
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 1 (`med_source` default = seam S-BS-FAUTH3-1) |

**Gate 0 GREEN** → cycle may close on the deterministic axis.
**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (if any)

None blocking. For the record:

1. **Finding:** the un-hinted `med_source` default (`patient_record.medications`) is a curated guess, not the canonical seed path.
   **Proposed disposition:** accept as-is; already logged as seam `S-BS-FAUTH3-1`. The human edit+Save is the spine backstop; a future per-flag default map is the noted fix. Optional: spec author may lock the canonical default in a later cycle.

2. **Observation (NOT a FAUTH-3 finding):** the full vitest run shows 1 failure in `src/app.test.jsx` (a "Shell" tab role query). This file is NOT in the FAUTH-3 diff (untouched in `457c4ae..1efd4b0`) and the working tree carried foreign edits at session start. It is pre-existing/foreign and does not gate this cycle, but the monitor should confirm `app.test.jsx` green on a clean tree before any cycle that DOES touch the shell chrome.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Ran Gate 0 (suite + lint + vitest) from a clean checkout / worktree, recorded verbatim, BEFORE the questions
- [x] Confirmed each `test(...)` commit precedes the implementation it covers (RED re-proven in a worktree for all three)
- [x] Read the spec (§3/§4/§6) cold
- [x] Read the diff via `git diff`/`git show` against the commits, not via the executor's summary
- [x] Each finding cites both spec file:line and implementation file:line
- [x] No BLOCKING findings (none needed reduction to a failing test)
- [x] Did NOT edit any code, spec, or driver (only wrote this critique doc, per CRITIC.md)
- [x] Did NOT confer with monitor or executor before forming the verdict (read the session log only after Gate 0 + the 4 questions, to cross-check — its claims matched my independent run, incl. both A-LIVE findings)

No audit drift.

---

## Appendix: commits audited

```
1efd4b0 fix(bff): FAUTH-3a — treat empty-dict suggested_params as no-suggestion (default-fill)
69b2204 test(fauth): FAUTH-3a — empty-dict suggested_params must still default-fill — red
c21816a fix(bff): FAUTH-3a — author_contract default-fills the deterministic presence_check skeleton
54679cb test(fauth): FAUTH-3a default-fill the presence_check skeleton for a named flag — red
d66479e fix(bff): steer the FAUTH-3 assist to the deterministic source_hint path (correct keys)
db3d88d feat(shell): ContractBuilder pre-fills from suggested_params, editable, Save unchanged (FAUTH-3)
11cace0 feat(bff): author_contract suggests presence_check params (emit-only) — the kb_context-cite assist (FAUTH-3)
177e691 test(fauth): FAUTH-3 assist prose→params — spine guard + suggestion shape — red
```

## Appendix: files changed

```
 apps/bff/agent/adapter.py                     |  27 ++-
 apps/bff/agent/assist.py                      |  45 +++++
 apps/bff/agent/loop.py                        |  15 +-
 apps/bff/agent/tools.py                       |  50 ++++-
 apps/shell/src/genui/ContractBuilder.jsx      |  13 +-
 apps/shell/src/genui/ContractBuilder.test.jsx |  26 +++
 tests/bff/test_contract_builder_part.py       |  12 +-
 tests/bff/test_fauth3_assist.py               | 273 ++++++++++++++++++++++++++
 8 files changed, 436 insertions(+), 25 deletions(-)
```
