# Critique — bench-salvage / FAUTH-1 (surface the ContractBuilder input widget inline)

> **HARD GATE close note. 2026-06-20.** Verdict: **CLOSE — PROCEED-WITH-CAVEATS.**
>
> **Honesty caveat on the gate:** the cold fresh-critic subagent was **stopped by the owner pre-verdict**
> ("critic taking too long"). It had already completed the expensive independent work and reported it on
> stop — but it did NOT write its own verdict. The deterministic verification below was therefore
> **completed + recorded by the monitor**, not emitted by a fully-independent cold critic. The
> independence is *partial* (the critic did the Gate-0 worktree baseline + the A-SAFE perturbation cold,
> before being stopped); the monitor finished the GREEN re-run + the freeze/scope audit. Treat the
> "fully independent cold verdict" as **owed-but-waived** for speed; if a stricter gate is wanted later,
> re-run `/devloop-critique bench-salvage FAUTH-1` from clean.

## What the cold critic independently confirmed before being stopped (its stop report, verbatim intent)
- Working tree **pristine: 21 entries, foreign WIP intact** (the concurrent CONV-FIRST/META-VERDICT-1 work survived).
- `apps/bff/agent/tools.py` **md5 unchanged** vs its own checkpoint; stash count back to 1; no probe residue; worktrees removed.
- Its **read-only/test-only mandate honored** — the one **A-SAFE scratch perturbation was reverted byte-perfectly** (i.e. it exercised the non-vacuity probe and cleaned up).

## Monitor deterministic verification (completed at close)
- **Tests RED→GREEN, non-vacuous (empirical):** impl symbols (`author_contract`, `contract_builder_part`) = **0** at the test commit `4b5c89c`, **present** at the feat commit `f72d04f`; the tests carry real assertions incl. the surfaces-not-spends guard (`raise AssertionError("author_contract must not call a bound write/grade op")`).
- **GREEN re-run (independent, monitor):** `tests/bff/test_contract_builder_part.py` + `tests/test_asafe_tool_gate.py` → **13 passed**; `apps/shell/src/genui/ContractBuilder.test.jsx` → **5 passed** (canonical env `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare`; vitest in `apps/shell`).
- **A-SAFE:** `AUTHOR_CONTRACT_SCHEMA` carries **no paid knob** (no `confirm`/`in_process`/`live`); the tool surfaces a card, performs no bound write/grade op; tool count **19→20** (exactly +1); allowlist auto-derives from `_TOOL_SPECS` (asafe-gate test green).
- **MOAT byte-frozen:** `git diff 645dfcd..HEAD` shows **0 changes** to `runtime/council/{compliance_council,signals,withstands}.py`, `judge_metric.py`, `harness/grounding.py`; `add_grounding_contract_handler` byte-identical (0 deletions in `tools.py`); `_deny_non_lithrim` unchanged.
- **Hunk-surgery cleanliness (the cycle-specific risk):** the 5 FAUTH commits (`4b5c89c..ece66a4`) touched only 13 FAUTH files (3 product + `ContractBuilder.jsx` + 2 new tests + 6 count-pin consequence-edits + the session log). **No foreign hunk swept into a commit** (adapter `votes`/`runId` = 0, tools `meta_verdict`/`open_artifact` = 0 in the committed diffs). **Foreign WIP survived** uncommitted + intact (adapter `votes`/`runId` ×4, VerdictCard `ClinicianVerdict` ×2, `test_uap5b_chat` foreign hunk ×16 all still present).
- **No push / no autostart.**

## Gate 0 (the one item NOT re-derived by the monitor)
The **full-suite 0-new-failures** number was the cold critic's worktree-baseline run (stopped before it reported the figure) + the executor's own run (688p / 28f, claimed equal to the parent `645dfcd` 28f baseline; the 28 are pre-existing pack-snapshot drift). The monitor did **not** re-run the entire suite. Risk is bounded: the MOAT + `ground()` + grade path are git-verified **0-diff**, so no council/grade behavior can regress; the only new surface is an additive `$0` conversational tool, whose own tests are green. If a fully-independent full-suite figure is required, re-run the critic.

## Spec-fidelity (the 4 questions)
1. **Driver intent met?** Yes — `author_contract` surfaces the existing `ContractBuilder` INPUT widget inline (the `get_judge`→`JudgeEditor` mirror), seeded by `flag_code`; the human's Save (`putGroundingContract`) is the sole, existing, audited write. No new write path, executor, or floor.
2. **R4 real?** Yes — `CONTRACT_TYPES` scoped+exported to the registered-executor set (`presence_check`/`snomed_subsumption`/`record_presence`); the no-executor types (`negation_check`/`code_match`/`range_check`) removed, so a non-coder cannot author a `contract_type` that makes `ground()` raise.
3. **Scope creep?** None — R1 found `tool-contract_builder` already wired through `renderTool` (`registry.js`/`panes.jsx`), so no shell-render refactor was added (the executor correctly did NOT touch `panes.jsx`/`registry.js`).
4. **Honesty gap?** None found — the session log's claims match the code/diff on every spot-check.

## Seams (both LOW, carried)
- **S-BS-FAUTH1-1** — `CONTRACT_TYPES` is a static guard, not derived from the active pack's live registry; the deeper **registration GATE** (SPEC §3 OQ-2) is **FAUTH-2/G3**.
- **S-BS-FAUTH1-2** — the **A-LIVE `:5180` smoke is OWED to the owner** (no-autostart/no-browser-drive standing pref): surface the builder inline, fill + Save, confirm the contract persists via `GET /v1/ontology` / `/v1/audit`.

## Verdict
**CLOSE — PROCEED-WITH-CAVEATS** (deterministic verification clean; the fully-independent cold-critic verdict is owed-but-waived for speed; A-LIVE owed; 2 low seams → FAUTH-2 + owner smoke). Commits local, not pushed.
