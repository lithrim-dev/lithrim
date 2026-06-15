# Spec-Adherence Critique — `bench-salvage` phase `CONV-UX-1`

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `CONV-UX-1` (conversational cadence + thinking-stages + GenUI gating)
- **Driver bundle:** `bench-salvage-phaseCONV-UX-1-conv-cadence-thinking-genui-driver` (v1)
- **Commits audited:** `cb0a513` → `96c1517` (6 commits, parent `46414b7`)
- **Spec(s) read against:** the driver §2 deliverables (W0–W4) + §4 scope guardrails + §5 acceptance
- **Critique mode:** `fresh-critic` (separate session, no prior implementation context)
- **Date:** 2026-06-15
- **Reviewer:** critic session (cold read; reconstructed diff via `git show`; re-ran tests independently)

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The code+test layer of CONV-UX-1 is faithful, in-scope, and non-vacuous on every axis I could break. The moat is byte-frozen this cycle; W0/W1/W2/W3 logic is correct; the W2 spike claim is INDEPENDENTLY VERIFIED true (SDK exposes the cited symbols); the suite count is honest (534/2/4, the 2 failures pre-existing S-BS-96 import-isolation, proven not CONV-UX-1). Findings are minor: 1 pre-existing shell-suite failure outside CONV-UX-1's surface (must be acknowledged like the Python flakes), the S-BS-146 shared-part default, and `styles.css` being an unenumerated-but-necessary work surface. **Recommendation: PASS (non-blocking)** for the code layer — the A1–A4/A7 live acceptance remains the monitor's A-LIVE re-drive (correctly marked `PENDING-MONITOR-LIVE` in the session log).

---

## Claim-by-claim verification (the kickoff's 6 break-attempts)

### Claim 1 — Moat byte-frozen — **VERIFIED**

- `git diff 46414b7 HEAD -- lithrim_bench/runtime/council/compliance_council.py lithrim_bench/runtime/council/signals.py lithrim_bench/verification/tools.py apps/bff/agent/tools.py` → **EMPTY** (all four byte-identical across the cycle). The brief listed a non-existent `runtime/council/...` path; the real path is `lithrim_bench/runtime/council/compliance_council.py` — confirmed frozen. `apps/bff/agent/tools.py` (the brief's 3rd "moat" file) is the agent tools file and is ALSO byte-stable this cycle (the S-BS-146 constraint that forced the W3 tag onto `adapter.py` instead).
- No `consensus`/`withstand`/`verdict_confidence` line appears in the cycle diff (`grep` over the diff → empty).
- Guard trio `tests/test_6bclean_seam_guard.py` + `tests/test_6bclean_attestation.py`: **17 passed in 0.29s**. NON-VACUOUS by construction — the suite includes self-synthesized tamper cases (`test_unauthorized_deletion_of_consensus_still_fails`, `test_unauthorized_edit_to_evaluate_dspy_still_fails`, `test_changing_flag_source_provenance_would_trip_the_guard`) that PASS only because the guard raises on tampering. The `acc4973` baseline diff is large (expected — `acc4973` predates the 6b-CLEAN deletions already in the parent `46414b7`); the cycle-relevant freeze is the empty `46414b7..HEAD` diff, which holds.

### Claim 2 — W0 correctness + non-vacuity — **VERIFIED (reproduced)**

`_resolve_chat_agent` (`apps/bff/app.py:1457`):
- (a) valid supplied agent honored: `if req_agent in names: return req_agent` (line 1479) — multi-agent targeting preserved.
- (b) invalid coerced: `if names: return names[0]` (line 1482). `list_agents` (`lithrim_bench/harness/config.py:281`) does `ORDER BY name`, so `names[0]` is deterministic (`eval-1` < `snomed-demo`).
- (c) back-compat: a `default` workspace holding `ws0_default` resolves the literal to itself (branch (a)).
- Last-resort `return req_agent` (no agents on disk) lets the loop surface an honest 404 rather than crash; DB-read failure also returns `req_agent` (chat never broken by a DB error).
- **Non-vacuity REPRODUCED:** I reverted the helper body to `return req_agent` in a scratch copy → `test_resolve_chat_agent_coerces_an_invalid_agent_to_the_workspace_agent` + `test_a_no_agent_arg_handler_targets_the_resolved_agent` FAILED (2 failed, 2 passed — the honor/back-compat tests correctly still pass under identity). Restored byte-clean.

### Claim 3 — W1/W2 loop logic — **VERIFIED (SDK independently inspected)**

`apps/bff/agent/loop.py` (commit `97cc605`):
- **De-dup is real:** `streamed_text`/`streamed_thinking` flags set on a `StreamEvent` text_delta/thinking_delta; the trailing assembled `AssistantMessage`'s `TextBlock`/`ThinkingBlock` is emitted only `if not streamed_*`. `ToolUseBlock` is NEVER streamed (it only appears in the assembled message), so tool calls are never double-emitted. Flags reset after each assembled message (multi-turn safe). → No double text.
- **Clean degradation:** `try: from claude_agent_sdk import StreamEvent, ThinkingBlock / except ImportError: StreamEvent = ThinkingBlock = ()`. An empty tuple is falsy (`if StreamEvent and ...` skips the partial branch) and `isinstance(x, ())` is always False, so an older SDK / the test stub hits the unchanged whole-block path. The stub source (yields only Assistant/Result) is exercised by `tests/test_uap5b_chat.py` — **12 passed**.
- **W2 spike claim INDEPENDENTLY VERIFIED (no executor word taken, no paid call):** `PYENV_VERSION=debuglithrim python -c "import claude_agent_sdk"` →
  - version `0.2.90`
  - `StreamEvent`: True (fields `uuid, session_id, event, parent_tool_use_id` — `event` is the raw Anthropic dict the code reads via `(msg.event or {}).get("delta")`)
  - `ThinkingBlock`: True (fields `thinking, signature` — code reads `block.thinking`)
  - `ClaudeAgentOptions.include_partial_messages`: True
  The shapes match the code exactly. The spike is HONEST, not faked.

### Claim 4 — W3 gating — **VERIFIED (with one NON-BLOCKING note)**

`apps/bff/agent/adapter.py` (commit `5ec16bd`):
- `show_intent` is additive (`_part` adds the key; shell ignores unknown keys → flat-spread-safe). `audit_part` defaults `ondemand` (line 79 — the live offender), the four editor/verdict factories default `auto`. Directives (`open_artifact_part`, `propose_live_run_part`) DELIBERATELY omit the tag and keep their bare `{type,state,output}` shape (preserves the CHATBIND-2 exact-equality tests).
- **Error suppression is real and pre-existing-correct:** every `*_handler` in `tools.py` does `res = ctx.<call>()` inside a `try`, `return _error(...)` in the `except`, and `ctx.emit(part)` only AFTER (audited all 16 emit sites; ordering verified). Because `tools.py` is byte-stable, the W3 "audit every handler" deliverable was satisfied by the EXISTING structure — correctly, the executor did not need to touch it.
- **Shell dedups + renders ondemand compactly:** `panes.jsx` per-turn `seen` Set (one card per type), `show_intent === "ondemand"` → `<details className="ondemand">` "Show … ▸". The shell test `panes.chat.test.jsx` exercises all three (dedup→1, ondemand collapse, error-guard) — **19 passed**.
- **Outcome (structurally sound):** a "create a judge" turn → `author_judge` emits `judge_part` (`auto`, primary inline card); the incidental `review_runs` audit read is `ondemand` (collapsed). With W0 the `get_agent` no longer 404s, and the error-guard suppresses any card on a failed turn. The §0 live cascade (Audit-card-next-to-404) cannot recur.
- **S-BS-146 (NON-BLOCKING):** `agent_part`/`judge_part` are shared by a write caller (`assemble_agent`/`author_judge`, want `auto`) and a passive read caller (`get_agent`/`get_judge`, want `ondemand`), but the byte-stable-`tools.py` constraint precludes per-caller intent, so both default `auto`. A passive `get_agent` orientation read therefore still renders a full card. This is HONESTLY disclosed in the `5ec16bd` commit body and does NOT undermine the §0 outcome (the live off-context card was the Audit-trail, which IS `ondemand`). A bounded follow-up seam, not drift.

### Claim 5 — Tests non-vacuous + suite honest — **VERIFIED (reproduced)**

- Full canonical suite (`PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=/Users/aregee/Workspace/github.com/lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare python -m pytest -q`): **534 passed, 2 failed, 4 skipped in 67.78s** — matches the executor's claim exactly.
- The 2 failures (`test_observation_pipeline.py::test_importing_observation_does_not_load_compliance_modules` + `::test_default_run_pulls_no_heavy_deps`) **PASS in isolation** (`2 passed in 0.01s`) → S-BS-96 import-isolation pollution, collection-order, NOT CONV-UX-1. Proven further: the CONV-UX-1 Python tests import no council/compliance module (`grep` → none), and the 2 fail even in a run that DESELECTS the CONV-UX-1 tests alongside them.
- **+7 new Python tests** (4 W0 in `test_uap5b_chat.py`, 3 W3 in `test_uap5c_journey.py`) + 6 new shell tests in `panes.chat.test.jsx` (a pre-existing file, +109 lines).
- **Non-vacuity REPRODUCED on two tests:**
  - reverted `audit_part` default `ondemand`→`auto` → `test_w3_review_runs_part_is_tagged_ondemand` + `test_w3_author_judge_part_is_tagged_auto` FAILED. Restored.
  - disabled the shell dedup (`if (false && seen.has(...))`) → `dedups two same-type cards within a turn to ONE` FAILED with "expected 2 to be 1". Restored.

### Claim 6 — Scope held — **VERIFIED (with one NON-BLOCKING note)**

- `git diff 46414b7 HEAD --stat`: 10 files. Mapping: `app.py`→W0; `loop.py`→W1/W2; `adapter.py`→W3; `panes.jsx`→W1/W2/W3 shell; `styles.css`→W1/W2 CSS; `panes.chat.test.jsx`+`test_uap5b_chat.py`+`test_uap5c_journey.py`→W4; session-log JSON + `PROOF_*.md`→A7. All map to deliverables.
- **`genui/registry.js` UNTOUCHED** — no new GenUI component types (W3 gates the existing catalog). ✓
- **No re-theme:** `styles.css` is a single +40-line additive block (new `.activity`/`.working`/`.reveal`/`.reasoning`/`.ondemand`) using existing CSS variables; zero existing rules modified; `prefers-reduced-motion` honored.
- **No prettier reformat:** the panes.jsx deletions are the old render-map JSX re-nested inside a new IIFE that introduces per-turn `seen`/`inFlight`/`running` locals (a genuine feature change). Unrelated sections (LeftRail, SETUP_PARTS) untouched; hand-compact one-liners preserved. `ruff check` on all touched Python → "All checks passed!".
- **NON-BLOCKING note:** `styles.css` was not enumerated by name in the driver §2 starting-point file list (the driver named `panes.jsx`/`bff.js`/`registry.js`), but it is the necessary implementation surface for W1/W2's visual affordances and is documented in the `8a1a3ca` commit body. In-scope-but-unenumerated, not a drive-by.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity (W0–W3 symbols) | 0 | 0 | 0 |
| 2 | Behavioral fidelity (de-dup, error-guard, spike) | 0 | 1 (S-BS-146) | 1 (multi-text-block de-dup) |
| 3 | Out-of-scope intrusion | 0 | 1 (`styles.css` unenumerated) | 0 |
| 4 | Suite honesty | 0 | 1 (pre-existing shell failure) | 0 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Findings detail

### NON-BLOCKING 1 — S-BS-146 shared-part default (`adapter.py:66,73`)
`agent_part`/`judge_part` default `auto` for both write and passive-read callers because the moat-scope byte-stable-`tools.py` constraint precludes per-caller intent. A passive `get_agent`/`get_judge` orientation read still renders a full card. Honestly disclosed in `5ec16bd`; does NOT break the §0 outcome (the live offender, `audit_part`/`review_runs`, IS `ondemand`). **Disposition:** log as the existing S-BS-146 seam; revisit if/when `tools.py` re-opens.

### NON-BLOCKING 2 — pre-existing shell-suite failure outside CONV-UX-1
`apps/shell/src/app.test.jsx` "renders the titlebar with the mode-switch…" FAILS (the `Shell`/`Journey` `tab` role is not in `<App>` — it lives in a parent like `main.jsx`; consistent with the `shell-journey-chrome-parity` memory). **PROVEN pre-existing:** I reverted `panes.jsx` + `styles.css` (the only CONV-UX-1 shell files) to parent `46414b7` and re-ran — the test failed IDENTICALLY. NOT a CONV-UX-1 regression. The full shell vitest run is **1 failed | 90 passed**, all 6 new CONV-UX-1 shell tests green. **Disposition:** the close-out should acknowledge this the same way the 2 Python S-BS-96 flakes are acknowledged (A6 covered only the Python suite; the JS suite carries this one pre-existing red). Recommend a tracking seam.

### NON-BLOCKING 3 — `styles.css` not in the driver's enumerated file list (§3, scope)
In-scope-but-unenumerated; additive-only; documented in `8a1a3ca`. **Disposition:** accept as-is.

### OPEN-QUESTION 1 — single-boolean de-dup vs a multi-text-block message
`streamed_text` is one boolean per assembled message. If a single `AssistantMessage` ever carried one text block that streamed AND a second text block that did NOT stream (with `include_partial_messages=True`), the flag would suppress the second. With streaming on, all text should stream, so this is theoretical; tool-use interleaving is handled separately (never streamed). **Question for the spec author:** is the SDK guaranteed to stream ALL text blocks of a turn when `include_partial_messages=True`? If not, the de-dup wants per-block tracking. **Recommended resolution:** accept (low risk on the current SDK); note for a future hardening if a multi-text-block turn is ever observed dropping text.

---

## Required actions

No BLOCKING findings → no required correction to close.

Recommended dispositions:
1. Acknowledge NON-BLOCKING 2 (pre-existing `app.test.jsx` failure) in the close-out alongside the S-BS-96 Python flakes; open a tracking seam (shell chrome-parity).
2. Log NON-BLOCKING 1 against the existing S-BS-146.
3. The A1–A4/A7 live acceptance (`PENDING-MONITOR-LIVE` in the session log) is the monitor's A-LIVE re-drive — the honest-Δ bound on the PROOF stub's AFTER column must hold.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the driver + persona + template; read the diff via `git show` against the commits (not the executor's prose).
- [x] Re-ran every test myself; reproduced 3 non-vacuity proofs (W0 identity revert, W3 audit_part default revert, shell dedup disable) and restored each byte-clean.
- [x] Independently inspected the Claude Agent SDK (no executor word taken; no paid call).
- [x] Each finding cites file:line + the specific evidence + reproduction status.
- [x] Did NOT edit/commit any tracked file (all scratch edits reverted; `git diff HEAD` empty; temp backups removed). Did NOT drive the browser. Read the session log only at the end (to cross-check, not anchor).

---

## Appendix: commits audited

```
96c1517 docs(conv): PROOF capsule stub + session log — cadence before→after (A7)
9886c5a test(conv): default-agent resolution + staging + gating event-stream tests (W4)
8a1a3ca feat(conv): thinking stages + soft cadence + GenUI gating in the shell (W1/W2/W3)
5ec16bd feat(conv): tag gen-UI parts with show_intent for shell gating (W3 BFF)
97cc605 feat(conv): token-stream partials + thinking events from the loop (W2/W1)
cb0a513 fix(conv): resolve chat default_agent from the active workspace (W0)
```

## Appendix: files changed

```
.devloop/sessions/session-...CONV-UX-1-2026-06-15.json | 151 +
apps/bff/agent/adapter.py                              |  71 +-
apps/bff/agent/loop.py                                 |  48 +-
apps/bff/app.py                                        |  34 +-
apps/shell/src/panes.chat.test.jsx                     | 109 +
apps/shell/src/panes.jsx                               | 172 +-
apps/shell/src/styles.css                              |  40 +
docs/research/PROOF_bench-salvage_CONV-UX-1_2026-06-15.md | 95 +
tests/test_uap5b_chat.py                               |  65 +
tests/test_uap5c_journey.py                            |  37 +
10 files changed, 766 insertions(+), 56 deletions(-)
```
