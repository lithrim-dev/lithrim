# Holdout Hygiene Policy

**Status: DRAFT v1, 2026-07-04, for owner review.**
**Program: REL-OPS-1 O6 (SPEC_RELIABILITY_PROGRAM.md).**

This document writes down the tune/certify separation that already exists in the code
(DEMO-PIN-1 and the frozen held-out split), so the guarantee is auditable rather than
tribal. Every mechanism claim below cites the committed file that implements it.

## 1. Why this policy exists

Judge optimization (few-shot demo compilation) and judge certification (the honest
held-out delta, calibration reports, external validation) must never read the same
rows in the same role. A judge tuned on the rows that later certify it produces a
manufactured win. The reliability program's standing rule applies: a number is
published only when the mechanism that protects it exists.

## 2. The existing mechanism (evidence)

### 2.1 The split field is the role marker

Every calibration-corpus row carries a `split` field with exactly two grading roles:

- `"calibration"`: the trainset, eligible for optimization.
- `"test"`: the held-out set, eligible only for measurement.

`load_corpus` documents and filters on this field
(`lithrim_bench/runtime/council/judge_optimize.py:53-66`).

### 2.2 The optimization entry point separates the roles

`run_optimize` (`lithrim_bench/runtime/council/judge_optimize.py:362`) is the single
paid optimization entry point (wrapped by `scripts/optimize_judge.py` and the BFF
`POST /v1/judges/{role}/optimize`, `apps/bff/app.py:3167`). It:

- trains only on `split == "calibration"` rows
  (`lithrim_bench/runtime/council/judge_optimize.py:405`),
- measures the baseline and the compiled program only on `split == "test"` rows
  (`judge_optimize.py:406`, `judge_optimize.py:420`, `judge_optimize.py:436`),
- reports the delta win-or-loss; the accept gate is never loosened
  (`judge_optimize.py` docstring at `378-380`).

### 2.3 The held-out split is frozen

Growing the corpus may only grow the trainset:

- The corpus widening generator pins every new row to the `calibration` split, so the
  `test` split stays byte-stable across widenings
  (`../lithrim-pack-healthcare/scripts/generate_judge_calib.py:100-101` and `:282`).
- The pack repo pins this with a dedicated regression test:
  `../lithrim-pack-healthcare/tests/test_uap4_corpus_superset.py:79-83`
  (`test_held_out_test_split_is_frozen`), plus the leak assertion at `:75` (a new row
  in the `test` split fails the suite).
- The council-side test asserts the `test` split is frozen at the v1 30 cases and that
  widening changed only the trainset
  (`lithrim_bench/runtime/council/tests/test_judge_optimize.py:57-73`).

### 2.4 DEMO-PIN-1: tuned artifacts are pinned and signature-visible

The output of optimization (compiled few-shot demos) is a grade-affecting artifact, so
it is treated like config, not like a side effect:

- `run_optimize` persists the compiled demos to
  `compiled_demos_<tag>.json` under the workspace out-dir
  (`lithrim_bench/runtime/council/judge_optimize.py:466`).
- The next grade in that workspace loads them (`scripts/run_eval.py:451`,
  `lithrim_bench/runtime/council/judge_optimize.py:337`,
  `lithrim_bench/runtime/council/judges_dspy.py:695`,
  `lithrim_bench/runtime/council/sampling.py:301`).
- SIGNATURE-1 folds the demo file digests into the grade signature
  (`lithrim_bench/harness/replay.py:62` `demo_digests`, `:117` `grade_signature`;
  wired at `scripts/run_eval.py:382`), and the freshness guard
  (`lithrim_bench/harness/replay.py:157` `is_fresh`) refuses to serve a pre-tuning
  verdict as fresh after the demos change.

Together: what tuned the judge is recorded, hashed, and cannot silently leak into a
certification replay.

## 3. The policy

### 3.1 Corpora that may TUNE (judge optimization)

- `judge_calib_v1.jsonl` rows with `split == "calibration"`
  (`../lithrim-pack-healthcare/examples/judge_calib_v1.jsonl`). This is currently the
  ONLY tune-eligible surface. Optimization consumes it exclusively through
  `run_optimize`'s calibration filter (`judge_optimize.py:405`).

### 3.2 Corpora that may only CERTIFY

- `judge_calib_v1.jsonl` rows with `split == "test"`: the frozen held-out set. They
  produce the honest before/after delta and nothing else.
- The provider-drift canary golden set and its pinned baseline
  (`scripts/canary_judges.py`, `lithrim_bench/canary.py`): certify-only by
  construction; it exists to detect drift against a pinned verdict table and must
  never feed optimization.
- External physician-curated suites (the clinverdict corpus family,
  `../lithrim-pack-healthcare/clinverdict/examples/`): external validation. Tuning on
  them would destroy their evidentiary value as an independent check.
- Any customer acceptance corpus, by default. A corpus is certify-only unless it
  carries an explicit `calibration` split.

### 3.3 How a corpus (or case) moves between roles

- A new case enters as `calibration` (tune) by default; the widening generator
  enforces this (`generate_judge_calib.py:282`).
- The `test` split of a corpus version is FROZEN. Individual rows are never
  reassigned between splits. Enlarging the held-out set means minting a new,
  versioned corpus with a new frozen `test` split, cut BEFORE any optimization run
  reads the new version.
- One-way door: a row that has ever been tune-eligible in a corpus version may never
  become certify-eligible in a later version of the same corpus. The reverse
  (certify to tune) is likewise forbidden within a corpus version; it can only happen
  by minting a new version and re-freezing a new held-out split that excludes the row.
- External suites never move to the tune role. Period.

### 3.4 What a violation looks like, and where it is caught

| Violation | Caught by |
| --- | --- |
| A `test` row's split flips to `calibration` (or its membership changes) | `../lithrim-pack-healthcare/tests/test_uap4_corpus_superset.py:79-83`; `lithrim_bench/runtime/council/tests/test_judge_optimize.py:57-73` |
| A widening row lands in the `test` split | `test_uap4_corpus_superset.py:75` |
| An optimize run is pointed at a certify-only corpus (no `calibration` rows) | Refused at the entry point before any paid call (`lithrim_bench/runtime/council/judge_optimize.py:388-398`), pinned by `lithrim_bench/runtime/council/tests/test_judge_optimize.py:218` (`test_run_optimize_refuses_certify_only_corpus`) |
| Tuned demos silently change a verdict served as a fresh replay | SIGNATURE-1 freshness guard: demo digests are in the grade signature (`lithrim_bench/harness/replay.py:62`, `:117`, `:157`) |
| Optimization measured on rows it trained on | Structural: train and held-out are disjoint split filters in the same function (`judge_optimize.py:405-406`); the frozen-split tests keep the sets stable |

## 4. Enforcement status

- **SHIPPED (pre-existing):** the split filters in `run_optimize`, the frozen
  held-out pins (council + pack repo tests), the widening-pins-to-calibration
  generator rule, and the SIGNATURE-1 demo-digest freshness guard.
- **SHIPPED (this wave, tests-first):** the entry-point refusal of a certify-only
  corpus. `run_optimize` now raises `ValueError` before `import dspy` and before any
  LM construction when the corpus carries zero `calibration` rows
  (`judge_optimize.py:388-398`); the RED test was written first and is now GREEN
  (`tests/test_judge_optimize.py:218`).
- **NOT ENFORCED (honest gaps, stated rather than faked):**
  - Near-duplicate leakage. Nothing detects a calibration row whose content is a
    copy or trivial mutation of a `test` row. The split freeze is by `case_id`
    membership, not by content similarity.
  - Cross-corpus leakage. Nothing detects the same underlying case appearing in the
    tune corpus and in an external certify-only suite.
  - Human process. The one-way-door rule in 3.3 for future corpus versions is policy,
    not code; a new corpus version with a polluted held-out split would pass the
    current pins (they freeze v1 membership, not future versions).

  Building content-similarity or cross-corpus checks requires new machinery
  (deduplication over case content) and is deliberately not claimed here.
