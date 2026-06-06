# HANDOFF — `bench-salvage` post-UAP-5c-2 (the conversational tool set is COMPLETE)

> **Written by the monitor on cycle close (2026-06-05).** Load-bearing context for
> the next monitor session. Committed alongside the close-out commit.

---

## What just landed

- **Closed phase:** `UAP-5c-2` — complete the tool set (`run_eval_pack` batch + `assemble_agent` edit-one-facet) (commits `3578905..1ff7ea8`, parent `b2a8c92`, 6 atomic pathspec-only, **NOT pushed**)
- **Critique verdict:** **NON-BLOCKING [0 BLOCKING / 2 NB / 1 OQ]** — HARD-GATE genuinely-fresh-critic, agent `af82bf4b57ab6c3af` (`.devloop/sessions/critique-bench-salvage-phaseUAP-5c-2-2026-06-05.md`)
- **Audit verdict:** **CLEAN** (monitor 7-item, re-verified)
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseUAP-5c-2-2026-06-05.json`

The pre-authorized D-F split shipped in full → **the conversational surface is now the complete 8 tools** (`author_judge` / `get_judge` / `run_eval` / `get_agent` / `author_flag` / `review_runs` + `run_eval_pack` / `assemble_agent`). A-SAFE was re-proven safe-by-explicit-bound as the surface added its first paid-capable wrapper (`run_eval_pack`, `live=False` hardcoded — the fresh-critic proved the negative test non-vacuous by scratch-revert) and its first agent-reachable Agent WRITE (`assemble_agent`, edit-one-facet, `LENS_BY_ROLE`-guarded, audited). Green: default 299p/12s · debuglithrim 149p/3s · Vitest 51p/11f · ruff clean.

## What's next — a FORK (the tool set is feature-done; no driver authored yet)

There is **no UAP-5c-3** — the conversational authoring product surface is complete. The remaining work is *depth*, not more tools. Monitor's choice (with the user):

1. **S-BS-46/49 corpus-deepening** — a clean-negative cohort to counter the S-BS-76 over-fire = the path to a real *optimize WIN* (UAP-4 was an honest LOSS; the corpus is the lever). **Candidate lean** — it's the substantive product/research advance now that the surface is done. `/devloop-expand-driver bench-salvage <new-phase>` (author from the S-BS-46/49 seams + the UAP-4 finding).
2. **S-BS-74 live-correction demo** — engineer a case the authored trio over-fires → the gate corrects LIVE → the visceral S-BS-70 flip (for a pitch; polish on a proven mechanism).
3. **UAP-5a-assist** (R10 LLM author-assist, describe→draft) | **UAP-3b-3** (the LLM Ralph-Loop critique split).

**Plus an OWED user-run (not a cycle):** the **UAP-5c-2 A-LIVE `:5180`** — the first paid-capable wrapper, so the live attestation must confirm the agent stays replay-only (the way the UAP-5c A-LIVE confirmed A-SAFE held). `$0`, built driveable. (The older **UAP-5a A8** smoke is also still owed.)

## Open seams for `bench-salvage` (active)

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-84 | `assemble_agent` roster REMOVE has no owner↔emit / non-empty revalidation (ADD is guarded) | low | **open (UAP-5c-2; by-design, critic-endorsed LOW; OQ-1 + NB-1)** |
| S-BS-83 | `author_flag` is EDIT-ONLY (conversational flag CREATION stays a human act) | low | open (UAP-5c) |
| S-BS-80 | pre-existing TopBar "Run live" fires paid with NO in-DOM modal | low | open (pre-existing) |
| S-BS-74 | the live CORRECTION needs an engineered over-fire case (S-BS-70's visceral finale) | med | open |
| S-BS-76 | the authored DSPy demos over-fire (UAP-4 honest LOSS root) | med | open |
| S-BS-46/49 | corpus-deepening / clean-negative cohort for a real optimize win | med | open (carried) |
| S-BS-70 | the visceral live verdict-flip (mechanism proven offline + live-SAFE) | med | live-corrected-PENDING |

## Load-bearing context the next monitor MUST know

1. **The conversational product surface is COMPLETE — pivot from "add tools" to "deepen the eval."** UAP-1..5c-2 built the full UI-driven author→process loop (judges + flags + agents + runs + batch, all conversational, all audited). The next cycles are NOT more tools — they are the *substance* the tools operate on: a richer corpus (S-BS-46/49) so `optimize` can show a real win (UAP-4's honest LOSS was a calibration/corpus problem, not a tooling gap), and/or the visceral live-correction demo (S-BS-74). Don't reflexively author a "UAP-5c-3."

2. **A-SAFE is now the standing gate for any future conversational-tool change.** The pattern is locked: every tool wraps a FROZEN op via a `_build_tool_context` closure that passes Query/Header explicitly (the `fastapi-endpoint-as-plain-call-fieldinfo-trap` memory — S-BS-82); any paid-capable op is `live=False`-hardcoded with a non-vacuous `live=True`-dropped test; the allowlist-bounds + no-paid-knob tests must cover the full `_TOOL_SPECS`. If a future cycle adds a tool, it inherits this checklist.

3. **OQ-1 is a real spec-author decision (from the fresh-critic):** should `assemble_agent` REMOVE refuse emptying the roster / orphaning a gradeable flag's owner? Today it allows it (audited + reversible, not an A-SAFE hole, but the empty-roster case yields a *degraded* zero-judge verdict, not just "a narrower council"). It's filed LOW; resolve it when/if conversational agent-assembly graduates from edit-one-facet. The `CLAUDE.md` owner↔emit invariant is the relevant authority.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (the phase table + open-seams table + the First-move top block).
3. Read this handoff + the session log + critique for UAP-5c-2.
4. `git log --oneline -10` on `bench-salvage/ws6c-dspy` (nothing pushed).
5. Wait for user input. Don't autonomously start the next cycle — the fork is the monitor's call WITH the user.

## References
- Stream state: `.devloop/state/STREAM_bench-salvage.md` + `.devloop/state/streams.json` (`current_phase` + `cycle_state_note`)
- This cycle: session `session-bench-salvage-phaseUAP-5c-2-2026-06-05.json` · critique `critique-bench-salvage-phaseUAP-5c-2-2026-06-05.md` · driver `prompts/bench-salvage_phaseUAP-5c-2_complete-tool-set_driver.md`
- Spec (LOCKED): `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §13/R11 + `SPEC_PRODUCT_SHELL.md §10`
- Memory: `fastapi-endpoint-as-plain-call-fieldinfo-trap` · `browser-mcp-confirm-blocks-renderer` · `live-reassess-before-driver-lock` · `unified-authoring-product-frozen-journey` · `git-commit-pathspec-dirty-index`
