# Inline critique — bench-salvage PACK-CLEANUP (corpus-path-portability)

**Date:** 2026-06-11 · **Mode:** inline (Routine cycle) · **Verdict:** CLEAN
**Commits:** c5ace29 (D1 loader) · 93f4451 (D2 corpora + pre_widen) · 14d3aac (D3 track proof_case)
**Cold-read basis:** driver §2–§5 + `git diff 13a6cb9..14d3aac` + independent re-run of A2/A3.

---

## Q1 — Surface fidelity

The public surface this cycle touches is (a) the `SyntheaProvenance.cohort_path` *representation* and (b) the committed-corpus contract. Both match intent:

- `_repo_relative(p) -> str` added to `lithrim_bench/encounter_spec.py` (the agreed home, ratified in plan-review over the driver's original picklist suggestion). Both loaders call it. Signature matches the plan.
- `cohort_path` is now a repo-relative POSIX string (`data/synthea_sample_data_csv_latest`) in every committed corpus; absolute fallback preserved for out-of-tree cohorts.
- **One surface deviation from the driver text, APPROVED-mid-cycle and CONFIRMED:** the helper uses `os.path.abspath` (no symlink-follow), NOT the driver-prescribed `.resolve()`. Monitor independently verified `data/synthea_sample_data_csv_latest` is a symlink to `/Users/aregee/Workspace/github.com/synthea_sample_data_csv_latest` (outside the repo) — `.resolve()` would follow it, escape `REPO_ROOT`, and force the absolute fallback, defeating the fix. The driver's `build_fhir_mini_pack.py:84` precedent never hit this because it operates on a real dir. This is a correct diagnose-before-edit correction, documented in the D1 commit body + the helper docstring. No drift — a driver-text correction.

## Q2 — Behavioral fidelity (3 spec-claimed behaviors traced)

1. **"Determinism guard now portable" (A2).** Spec: `test_committed_corpus_matches_a_fresh_generator_run` should pass off-canonical. Trace: D1 makes a fresh loader run emit the relative string → D2 normalized committed to the same → monitor re-ran `tests/test_uap4_corpus_superset.py` = 6/6 green (incl. the byte-identical-rows compare against the lockstep-normalized pre_widen fixture). Chain holds.
2. **"Only `cohort_path` changed" (A4).** Spec: every non-path field byte-identical. Trace: monitor independently grepped the 166-line `judge_calib` diff (the largest) → **0** changed lines that aren't `cohort_path`; the 179/179 balanced insert/delete across D2 corroborates pure line-for-line replacement. Holds.
3. **"proof_case readable on a fresh checkout" (A3).** Spec: un-ignore + track → the 3 readers green. Trace: `.gitignore` block removed, `examples/proof_case.jsonl` tracked, `git check-ignore` empty; monitor re-ran the 3 reader modules = 22 green. Holds.

## Q3 — Out-of-scope intrusion

None. `git diff --name-only 13a6cb9..14d3aac` = exactly the 12 deliverable files. No council file, no `backends/`/`runtime/pipeline/` docstring touched (the dropped scrub stayed dropped). The pre-existing `ruff format --check` "would reformat" hunks were correctly left untouched (parent `13a6cb9` already non-compliant; the hunks don't intersect the executor's added lines) — per §4 no-drive-by. Foreign staged demo files (app.jsx, journeys/*) untouched.

## Q4 — Spec ambiguity surfaced

- **The symlink/`resolve` assumption** (Q1) — the driver assumed the `.resolve()` precedent transferred; it didn't, because the data dir is a symlink. Surfaced + corrected in-cycle. No open question remains.
- **S-BS-126** (low, opened): `tests/fixtures/ws0/case.bench_scribe_v1_inject_condition_1bd0f10dc7b5.jsonl` still carries an absolute `cohort_path`. Executor confirmed (via `git grep`) it's never dereferenced as a filesystem path — inert captured pipeline-evaluate payload — and A1's grep is `examples/`-scoped, so leaving it is in-bounds. A future fixture-portability sweep could close it; not load-bearing.

---

**Disposition:** CLEAN. Close S-BS-117 + S-BS-119; open S-BS-126 (low). PACK-2c remains deferred/untouched.
