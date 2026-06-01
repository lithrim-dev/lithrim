# Spec-Adherence Critique — `bench-salvage` phase `WS-6a`

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-6a` (backend baseline: curate + commit the pending `../lithrim-backend` WIP)
- **Driver bundle:** `bench-salvage-phaseWS-6a-backend-baseline-driver`
- **Commits audited:** `2f04a40` (C1 structural-verdict severity), `4b3e4e4` (C2 pipeline-grading D-E/D-J/D-K); docs/scaffold/scripts commits `379d1d3`/`a845809`/`493b533` are low-risk curation, not critiqued for behavioral fidelity.
- **Spec(s) read against:**
  - `../lithrim-backend/docs/PIPELINE_GRADING_AUDIT_2026-05-28.md` (the de-facto behavioral spec for C2: D-E §3 / D-J §5 / D-K §8 + the §"fix-log" rows; committed this cycle at `379d1d3`)
  - `../lithrim-backend/CLAUDE.md` (diagnose-before-edit gate + core invariants)
  - `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (strangle-not-fix framing; WS-6 step a)
- **Critique mode:** `inline` (monitor self-audit) — **NOT** fresh-critic
- **Date:** 2026-06-01
- **Reviewer:** monitor session (inline). **Independence caveat:** this session printed the kickoff, ruled on the Option-C plan-review, and ran `/devloop-audit` for WS-6a before this pass. The "read the spec before the session log" property is therefore FALSE (the session log was read during the prior audit). The user elected inline mode with this caveat acknowledged (HARD-GATE bundle; driver §Hardness permits inline for a curation cycle). Findings below were derived from a fresh read of the spec doc + the `git show` diffs this turn, and cross-checked against (not anchored on) the session log. A fresh-critic session remains available if stronger independence is wanted.

---

## Verdict

**`NON-BLOCKING FINDINGS`**

C1 and C2 faithfully implement the PIPELINE_GRADING_AUDIT D-E/D-J/D-K fixes; no BLOCKING drift and no out-of-scope intrusion. The findings are test-coverage asymmetries (the live v2 confidence leg and the council_error source/sink are not unit-tested, only the middle layer is) plus one partially-met sub-requirement (the spec asks to "pin/report `council_error_rate`"; this cycle ships only the enabling per-run flag) and two surfaced judgment calls. All are consistent with a curation cycle that commits diagnosed pre-existing WIP rather than authoring new behavior.

---

## 1. Surface fidelity

> Does the public API (function names, signatures, return shapes, error taxonomy, config keys) match the spec exactly?

This is a curation cycle: it designs no new endpoint or public function. It does change two **surfaced model shapes**, both spec-mandated.

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| §3 / fix #3 (PIPELINE_GRADING_AUDIT:421): "`JudgeVote.confidence` is now `Optional[float]=None`" | `models.py:37` `confidence: Optional[float] = None` (was `float = 0.0`) | exact | NON-BLOCKING (downstream impact, below) |
| §8 / fix #8 (PIPELINE_GRADING_AUDIT:426): "Surface a `council_error` flag" | `models.py:231` `PipelineProvenance.council_error: Optional[bool] = None`; `models.py:452` `AuditView.council_error: Optional[bool] = None` | additive, spec-mandated | matches |
| §5 / fix #7 (PIPELINE_GRADING_AUDIT:425): audit-view renders structural pass/fail correctly | `pipeline.py:388` `_extract_structural_checks` (shape unchanged, values corrected) | matches | matches |

**Findings:**

- `[NON-BLOCKING]` **`judge_votes[*].confidence` response contract widened `float` → `float | null`.** Spec PIPELINE_GRADING_AUDIT:185 / :421 require this exact change, so it is faithful, not drift. But it is a real response-shape change for any consumer of `/v1/pipeline/evaluate` or `/v1/pipeline/runs/{id}/audit-view`: a field that was always a float can now be `null` (e.g. Mistral `policy_judge` under v2). Any consumer that renders per-judge confidence must tolerate `null`. Concretely, the WS-5-BFF `ReportTab` judge-council view (`apps/shell/src/artifact.jsx`) and the bench harness composite reader should be checked. Disposition below.

---

## 2. Behavioral fidelity

> Pick 3 spec-claimed behaviors; trace spec assertion → test → implementation.

### Behavior 1: D-J — audit-view derives structural `passed` from `status`, `detail` from `message`

- **Spec assertion:** PIPELINE_GRADING_AUDIT:257 "the denormaliser reads `c.get("passed")` while the persisted check dicts use the key `status` ... It would make the UI's structural panel look uniformly failed"; fix #7 (:425) "now derives `passed` from `status` and `detail` from `message` ... with the legacy `passed`/`detail` keys kept as fallback."
- **Test:** `tests/routes/test_audit_view_surface_fixes.py` `test_structural_check_passed_derived_from_status` (status `pass`/`fail` → `passed` True/False; `message` → `detail`) and `test_structural_check_legacy_passed_detail_keys_still_honored` (legacy keys fallback).
- **Implementation:** `pipeline.py:388` `_extract_structural_checks` derives `passed` from `status` with `bool(c.get("passed"))` fallback; `detail` from `message` with `detail` fallback.
- **Chain closes?** **YES.** Both the new behavior and the back-compat path are asserted at the same surface the bug lived on.

### Behavior 2: D-E — per-judge `confidence` None preserved, not coerced to 0.0

- **Spec assertion:** PIPELINE_GRADING_AUDIT:185 "The `JudgeVote` surface coerces `None or 0.0 → 0.0` (`stages.py:590`; same coercion in `pipeline/models.py:69`)"; fix #3 (:421) "Stopped coercing `None`→`0.0` at the `JudgeVote` layer (`stages.py:_judge_votes_from_models`, `models.py:_coerce_legacy_judge_votes`)."
- **Test:** `test_audit_view_surface_fixes.py` `test_judge_vote_missing_confidence_stays_none` (model default) + `test_coerce_legacy_judge_votes_preserves_none_and_real_zero` (None stays None; genuine 0.0 stays 0.0; 0.93 preserved). These exercise the **`_coerce_legacy_judge_votes`** leg and the model default.
- **Implementation:** `models.py:37` (Optional default), `models.py:69` `_coerce_legacy_judge_votes` (numeric-only coercion), **`stages.py:585` `_judge_votes_from_models`** (numeric-only coercion).
- **Chain closes?** **PARTIAL.** The spec names *both* fixed sites, but no test exercises **`stages.py:_judge_votes_from_models`** (the LIVE v2 grading path). It is the symmetric twin of the tested legacy path, and the post-cycle e2e observed `policy_judge` `confidence=null` live on `/v1/pipeline/evaluate` (session log `post_cycle_e2e_validation.surfaces_confirmed_live.D-E_confidence_None`), so it is e2e-covered, not unit-covered. Finding below.

### Behavior 3: D-K — council error surfaces a flag so WARN-on-error is not counted as graded

- **Spec assertion:** PIPELINE_GRADING_AUDIT:379 (D-K) + fix #8 (:426) "The council intermittently errors (429/timeout → WARN fallback, empty `judge_votes`), after which the verdict silently rests on the single artifact_judge. Surface a `council_error` flag **and pin/report `council_error_rate`**; do not let a WARN-on-error masquerade as a graded WARN."
- **Test:** `tests/services/pipeline/test_council_error_flag.py` — three tests on the **orchestrator**: `council_error` True when `semantic_meta` flags it, False on normal grade, None when semantic skipped. All inject a pre-set `semantic_meta` and assert `result.provenance.council_error`.
- **Implementation:** the flag is *set* in `stages.py:806` (except-branch `council_error: True`) and `stages.py:860` (success-branch `consensus.get("reason") == "insufficient_valid_models"`); *computed* in `orchestrator.py:325` (None when `semantic.status == "not_applicable"`); *rendered* in `pipeline.py:1047` `_denormalise_audit_view` (reads `doc.get("council_error")`).
- **Chain closes?** **PARTIAL.** The orchestrator pass-through is well-tested, but the **source** (`stages.py:806`/`:860` derivation, including the `insufficient_valid_models` branch) and the **sink** (`pipeline.py:1047` AuditView rendering) are not unit-tested. The e2e observed `council_error=True` under a transient rate-limit (the except-branch), but the success-branch `insufficient_valid_models` derivation is neither unit-tested nor e2e-confirmed. Findings below.

**Findings:**

- `[NON-BLOCKING]` **D-E live leg untested.** `stages.py:585` `_judge_votes_from_models` (the v2 path) has no unit test; only `_coerce_legacy_judge_votes` and the model default are asserted (`test_audit_view_surface_fixes.py`). Mitigated by the live e2e. Spec: PIPELINE_GRADING_AUDIT:421. Impl: `stages.py:585`.
- `[NON-BLOCKING]` **D-K source + sink untested.** The `council_error` derivation in `stages.py:806`/`:860` and the AuditView rendering in `pipeline.py:1047` are uncovered; only `orchestrator.py:354` pass-through is tested (`test_council_error_flag.py`). The `insufficient_valid_models` success-branch is the weakest leg (no unit + no e2e). Spec: PIPELINE_GRADING_AUDIT:426. Impl: `stages.py:860`, `pipeline.py:1047`.
- `[NON-BLOCKING]` **`council_error_rate` not implemented (flag-only).** Fix #8 (PIPELINE_GRADING_AUDIT:426) asks to "Surface a `council_error` flag **and pin/report `council_error_rate`**." This cycle ships the per-run flag (the enabling primitive) but not the rate rollup; the C2 message says rollups "*can* compute `council_error_rate`." Partial satisfaction of the requirement. Disposition below (likely belongs in the eval-pack layer, WS-4b, not the backend).

---

## 3. Out-of-scope intrusion

> Anything in the diff not in the driver's deliverables list.

Driver §2 deliverables: D0 triage manifest, D1 tests-green-before-commit, D2 gitignore transients, D3 resolve stray docs, D4 atomic per-concern commits, D5 session log.

`git show` of C1 (`2f04a40`) and C2 (`4b3e4e4`) confirms every hunk is a D-E/D-J/D-K or `_check_severity` change with an inline rationale. No drive-by refactor, no formatting pass (the three ruff nits were preserved as-authored per §4 "no drive-by reformatting", logged as S-WS6A-4, confirming no reformatting sweep), no dependency change.

**Findings:**

- **All diffed code maps to deliverables. No intrusion detected.** The one structural note (not intrusion): C2 bundles three audit fixes (D-E + D-J + D-K) into one commit. This is the approved Option-C grouping (the files `pipeline.py`/`models.py`/`stages.py` straddle the fixes, and D-E + D-J share `test_audit_view_surface_fixes.py`, making strict per-fix atomicity impossible without hunk-surgery). Documented in `plan_review.deviations[0]`. Per-concern (the concern being "the 2026-05-28 audit's surface/provenance fixes"), not per-fix.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: `_check_severity` severity vocabulary + silent fallback on an unrecognized value

- **Spec text (or absence):** the audit doc and `CLAUDE.md` do not define the validator-template severity vocabulary that C1 consumes; C1 is an extension of `43b20f6` (P0-1), itself not vocabulary-specified.
- **Implementation decided:** `artifact_evaluator.py` `_CHECK_SEVERITY_MAP` = {critical, high → high; medium, moderate → medium; low → low}; an out-of-vocabulary or non-string severity falls back to the legacy `"required"`-in-message heuristic (`_check_severity`, asserted by `test_unrecognized_severity_falls_back_to_heuristic`).
- **Alternatives that would also be compliant:** raise/log loudly on an unrecognized severity (fail-closed) rather than silently falling back.
- **Question for spec author:** is {critical, high, medium, moderate, low} the canonical validator-severity set, and should an unrecognized value warn rather than silently fall back?
- **Recommended resolution:** accept for now (fail-safe: a typo cannot silently *downgrade* a `required` failure, since fallback re-applies the heuristic). Note the symmetry with bench seam **S-BS-16** (which argues floor-injected severities should be validated loudly against `severity_map`); the same loud-validation argument applies to the validator side here. Surface to the WS-4b / S-BS-16 owner.

### Ambiguity 2: `council_error = None` vs `False` when the semantic stage did not run

- **Spec text (or absence):** fix #8 distinguishes error-WARN from graded-WARN but is silent on the structural-only / `context_kind=none` case where no council runs.
- **Implementation decided:** `orchestrator.py:325` sets `council_error = None` (not `False`) when `semantic.status == "not_applicable"`; locked by `test_council_error_none_when_semantic_skipped`.
- **Alternatives:** `False` ("no error occurred") would also be defensible.
- **Question for spec author:** is `None` ("no council verdict to assess") the intended encoding for a skipped semantic stage, versus `False`?
- **Recommended resolution:** accept (None reads as "not applicable", which a `council_error_rate` rollup should exclude from the denominator anyway); record so the eval-layer rollup treats `None` as excluded, not as a clean grade.

**Findings:**

- `[OPEN-QUESTION]` Severity vocabulary + silent-fallback policy (Ambiguity 1). Ties to S-BS-16.
- `[OPEN-QUESTION]` `council_error` None-vs-False for skipped semantic (Ambiguity 2). Affects how the future `council_error_rate` denominator is computed.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 1 | 0 |
| 2 | Behavioral fidelity | 0 | 3 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 2 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (dispositions)

No BLOCKING findings; nothing halts closure. NON-BLOCKING / OPEN-QUESTION dispositions:

1. **D-E live leg + D-K source/sink untested (Q2).** Disposition: **log as a seam** for a backend test-health follow-up (natural alongside S-WS6A-5, "the backend suite is not a green gate"). A small unit-test cycle should cover `stages.py:_judge_votes_from_models` confidence-None, `stages.py` `council_error` derivation (both branches), and `pipeline.py:_denormalise_audit_view` council_error rendering. Not WS-6a's job (curation, not authoring).
2. **`council_error_rate` not implemented (Q2).** Disposition: **carry to WS-4b** (the eval-pack / calibration-gate layer is the natural home for an error-rate rollup; the per-run flag this cycle ships is its prerequisite). Reconcile with Ambiguity 2 (None excluded from the denominator).
3. **`judge_votes[*].confidence` nullable downstream impact (Q1).** Disposition: **check WS-5-BFF `ReportTab` / `artifact.jsx` and the bench harness composite reader** tolerate `null` per-judge confidence before the shell renders live council data. Log as a seam if either assumes a float.
4. **Severity vocabulary + silent fallback (Q4, Ambiguity 1).** Disposition: **route to the S-BS-16 owner** (symmetric loud-validation argument); accept as-is for this cycle.
5. **`council_error` None-vs-False (Q4, Ambiguity 2).** Disposition: **accept**; record for the `council_error_rate` denominator design.

---

## Critic discipline self-check (inline mode)

- [ ] Read the spec without reading the executor's session log first — **FALSE.** The session log was read during the prior `/devloop-audit` this session. User elected inline mode with this caveat acknowledged. Spec doc + diffs were re-read fresh this turn; the session log was used only to cross-check (the findings here are net-new vs the session log's S-WS6A-1..5, which are test-rot/suite-health/ruff, not spec fidelity).
- [x] Read the diff via `git show` against commits (`2f04a40`, `4b3e4e4`), not via the executor's summary.
- [x] Each finding cites both spec file:line and implementation file:line.
- [x] Did NOT edit any code, spec, or driver during this pass.
- [N/A] "Did NOT confer with monitor/executor" — inline mode is the monitor; the contamination is the prior plan-review + audit, disclosed above.

**Net:** the load-bearing independence property is partially forfeited (inline, post-audit). The user accepted this for a curation cycle. For a contract-design HARD-GATE this would warrant a fresh-critic re-run; here the curation framing + the CLEAN mechanical audit make the residual risk low.

---

## Appendix: commits audited

```
2f04a40 fix(structural-verdict): prefer validator-declared check severity over the "required" heuristic
4b3e4e4 fix(pipeline-grading): audit-view surface + council_error provenance (PIPELINE_GRADING_AUDIT_2026-05-28 D-E/D-J/D-K)
```

## Appendix: files changed (code commits only)

```
app/services/artifact_evaluator.py                 |  35 +-   (C1)
tests/services/test_artifact_evaluator_severity.py |  49 ++   (C1)
app/routes/pipeline.py                             |  20 +-   (C2 D-J + D-K sink)
app/services/pipeline/models.py                    |  19 +-   (C2 D-E + D-K shape)
app/services/pipeline/stages.py                    |  16 +-   (C2 D-E + D-K source)
app/services/pipeline/orchestrator.py              |  10 +    (C2 D-K compute)
tests/routes/test_audit_view_surface_fixes.py      |  72 ++   (C2 D-E + D-J)
tests/services/pipeline/test_council_error_flag.py |  92 ++   (C2 D-K orchestrator)
```
