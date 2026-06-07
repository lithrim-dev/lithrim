# Fresh-critic critique — `bench-salvage` BYOC-1 (BYO-Claude as a first-class tool-less provider)

> **Mode:** HARD-GATE → genuinely-fresh critic (Agent `a6b5fbc4bd9b33e42`, cold context, no implementation bias) + monitor 7-item audit.
> **Date:** 2026-06-07 · **Verdict: NON-BLOCKING** (fresh-critic [0 BLOCKING / 2 NB / 1 OQ]; monitor audit CLEAN).
> **Disposition:** BYOC-1 closes **PROCEED-WITH-CAVEATS** (the executor's verdict stands; caveats = the owed USER-RUN A-LIVE S-BS-94 + the green-bar correction below).

## Monitor 7-item audit (independent re-run)
1. **Commits exist / tree clean** — `5c54aaf 0624eed ccb01c0 6f0bbc9 1fd4482 c05d8b3` on `bench-salvage/ws6c-dspy` (parent `c4d33ab`, not pushed); working tree clean except the 3 pre-existing foreign untracked files. ✓
2. **Files match driver** — 12 files: D1 `byo_claude_lm.py` (new) · D2 `judges_dspy.py` · D3 `authored_stage.py`/`run_eval.py`/`app.py`/`tools.py` · D4 `test_byoc_provider.py` (new) · guard reconciliation `_seam_freeze.py` (new)/`test_uap3b_withstands.py`/`test_uap3b2_provenance.py` · D5 design note + session log. ✓
3. **Tests** — targeted 25/25 (byoc + both guards incl. `MOAT_EXHIBIT` + `gate_cannot_relabel`); canonical `pytest -q` debuglithrim **448 passed / 2 failed / 3 skipped** (see NB-1). ruff clean on changed files. ✓ (with the NB-1 correction)
4. **Scope held** — BFF/journey/`bff.js`/genui 0-touch where required; `compliance_council.py` (`_apply_consensus`) byte-frozen; only `build_judge_lm`/`build_trio` changed in `judges_dspy.py`. ✓
5. **User prefs** — no autostart, no pushes, pathspec-only (the moat-guard commit `1fd4482` touches ONLY the 3 test files), foreign files never swept, A-LIVE left USER-RUN (cost-conscious). ✓
6. **Session log** — well-formed; S-BS-94/95 opened, S-BS-92 closed, the guard CITATION-DRIFT documented as an approved deviation. ✓
7. **Deviations justified** — D-D="Both" + D-F="offline now / live USER-RUN" + the per-symbol-freeze guard fix — all user-approved at plan-review. ✓

## Fresh-critic — load-bearing checks (all PASS, independently reproduced)
- **Consensus seam byte-frozen (the moat):** the critic's own AST extraction — 13 top-level symbols, none added/removed, all 11 non-binder symbols byte-identical to `acc4973` (`EvidenceSpan, Finding, Judge, _build_signature, _get, _norm_decision, _raw_response_for, _span_to_dict, _validate_findings, default_taxonomy_context, evaluate_dspy`); even module-level `_ROLE_DEPLOYMENT` + `V2_ROLES` byte-identical; only `build_judge_lm`/`build_trio` differ. `compliance_council.py`/`judge_metric.py`/seeds/`council_roles` diffs empty.
- **Frozen-seam guard NON-VACUOUS:** scratch-perturbing a seam body → `consensus-seam symbol(s) drifted: ['_validate_findings']`; scratch-adding a top-level symbol → symbol-SET assertion fired. Reverted.
- **A-SAFE tool-less NON-VACUOUS:** dropping `--tools ""` and appending `--dangerously-skip-permissions` each made the A-SAFE tests FAIL; the prompt rides stdin, never argv. Reverted.
- **A6 Azure behavioral identity:** `build_judge_lm("risk_judge")` → `dspy.LM` `azure/...` (the selector-pop doesn't perturb Azure).
- **Import-isolation:** plain `python3` (genuinely no dspy/openai) imports `byo_claude_lm` without pulling `dspy`/`litellm`.
- **No-faked-confidence:** `extract_verdict_confidence` (the real ported fn) → `None`; seam dict carries `None`, never a synthesized float.
- **Composition flip is consensus-driven, not hardcoded:** the critic's independent 3-config repro through the real `evaluate_dspy` — verdict tracks the Claude seat exactly (approve→reject→approve).

## Findings
- **NB-1 (green-bar correction — monitor records the honest number).** The session log claims "debuglithrim 339 / default 302, 0 failed." Those are `pytest tests/` (subdir-only). The canonical `pytest -q` (pyproject `testpaths` = `tests` + `runtime/council/tests` + `runtime/observation/tests`) is **448 passed / 2 failed / 3 skipped** (debuglithrim). **The 2 failures are PRE-EXISTING and BYOC-1-INDEPENDENT** — `test_observation_pipeline.py::{test_importing_observation_does_not_load_compliance_modules, test_default_run_pulls_no_heavy_deps}`; they fail identically at parent `c4d33ab` (436/2) and baseline `acc4973` (369/2); BYOC-1 touched none of the observation tests (monitor-confirmed: `git diff --name-only c4d33ab HEAD` has no observation/isolation file) and adds +12 passing with the SAME 2 failures. **A5/A7 = PASS for BYOC-1 (no new failure); the absolute suite is not all-green.** → S-BS-96.
- **NB-2 (order-fragile isolation tests).** Those 2 are `assert "X" not in sys.modules` checks that fail under full collection once any earlier test imports dspy/openai/litellm (BYOC-1's `test_byoc_provider.py` is now one such importer, but the failures pre-date it). Fix = run them in a subprocess. → folded into S-BS-96.
- **OQ-1 → RESOLVED by the monitor.** `authored_stage.py` appears in the driver §4 frozen list, yet D3 modified it. This is NOT drift: the user-approved plan-review deviation D-D="Both" explicitly authorized the per-judge `model` threading through `build_trio`/`run_eval`/`authored_stage`/BFF/`tools`. The change is additive (one `models: dict|None=None` param; the withstands-gate + `_apply_consensus` call untouched; ~10 lines) and the `run_eval` gate widens `if assignments:` → `if assignments or models:`. **Monitor accepts** (surfaced + approved ≠ silent scope creep; the §4 frozen text was overridden by the documented D-D approval).

## Disposition
NON-BLOCKING. **S-BS-92 CLOSED** (mechanism: BYO-Claude is a first-class tool-less council provider). Opened **S-BS-94** (med — the conv-UI 1-Claude-2-Azure paid A-LIVE owed, USER-RUN), **S-BS-95** (low — the global switch wires only the DSPy judge path, not `llm_provider.py`), **S-BS-96** (low — the 2 pre-existing order-fragile observation-isolation tests + the devloop green-bar should run canonical `pytest -q`, not the `tests/` subset). No proof capsule this cycle (the headline composition A-LIVE is the owed USER-RUN S-BS-94; produce the honest capsule then). Next cycle: **CRUD-from-clean** (the 3rd user objective).
