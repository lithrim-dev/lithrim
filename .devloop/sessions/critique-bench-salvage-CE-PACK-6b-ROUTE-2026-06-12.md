# Inline critique — bench-salvage CE-PACK-6b-ROUTE (authored path = only in-process grade)

**Date:** 2026-06-12 · **Mode:** inline (Routine, non-frozen; subagent-executed) · **Verdict:** CLEAN
**Commits:** 2b1f43d (reroute) · 113c156 (guard test + ws0 note) · c6ecd30 (docs) — on `5d576dc`.
**Cold-read basis:** the driver §2/§5 + `git diff 5d576dc HEAD` + monitor re-runs (the guard test + the full suite).

## 7-item audit — CLEAN
3 commits · scope = `scripts/run_eval.py` + `tests/test_uap3_grade.py` (the D4 guard) + `tests/fixtures/ws0/README.md` (the light re-pin note) + 2 docs — **no frozen council, no pipeline/ab_harness/test_consensus** (grep-confirmed) · monitor re-ran the suite (628 passed, 0-new vs baseline; the 2 fails = pre-existing S-BS-96 guards) + ruff clean · foreign files (`app.jsx`, `journeys/*`, the demo HANDOFF) untouched · the D0 HALT-gate was honored (measured 0-new breakage; proceeded) · session log present; no seams opened.

## The 4 questions
- **Q1 Surface fidelity — PASS.** `run_eval.py:256-273`: when `not (assignments or models or roles)`, sets the full-lens default `{role: sorted(pack_lenses()[role]) for role in pack_production_judges() if role in lenses}` and builds the authored stage; `semantic_stage` is never `None` on the in-process path. The "back-compat default council" docstrings corrected.
- **Q2 Behavioral fidelity — PASS.**
  1. **`build_prompt` off the product path:** the new guard `test_no_assignment_in_process_path_builds_authored_stage_not_default_council` ($0, stubbed seams) pins that a no-assignment in-process run builds an authored stage, not `None`. Monitor re-ran it green.
  2. **Authored path unchanged:** standalone + neutral_default + uap3_grade green — only the DEFAULT routing changed, not the authored mechanism.
  3. **No regression:** D0 measured 0-new because no test drives `run_eval`'s no-assignment dispatch and asserts the legacy default-council verdict (the in-process tests mock `run()`, or construct `build_authored_semantic_stage` directly with explicit assignments). Monitor confirmed 628 passed / 0-new.
- **Q3 Out-of-scope intrusion — NONE.** `build_prompt` NOT deleted (correctly left for 6b-CLEAN); the pipeline/ab_harness/consensus entrypoints untouched; the ws0_default baseline NOT regenerated (a README note instead of a fragile/paid live re-pin — the right call).
- **Q4 Judgment calls — surfaced.** The default-assignment choice (full pack lens vs `assignments=None`) decided as full-lens with evidence (driver-recommended; 0-new under it; `test_uap3_grade`'s unassigned-marker semantics untouched because that test constructs the stage directly, not via `run_eval`).

## Disposition
CLEAN. The in-process product grade is now **authored-path-only** — `build_prompt` is dead code on the product path (UI-authored prompts are the single live prompt source; the OQ-1 product concern is solved). `build_prompt` stays physically present, reached only by the out-of-scope `stages.py`/`ab_harness`/consensus-unit-test, and is **deleted in 6b-CLEAN** (the FROZEN HARD-GATE) along with `safety_flags.py` + the `_build_signature` clinical residue (S-BS-129). No new seams.
