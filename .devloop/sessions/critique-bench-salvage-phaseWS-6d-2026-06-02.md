# Critique — `bench-salvage` WS-6d (ROUTINE, inline + risk-driven deep verification)

**Verdict:** NON-BLOCKING → CLOSE.
**Mode:** inline critique by the monitor (ROUTINE: a new store impl behind an existing injected seam; the consensus IP + grade-record shape frozen; nothing reads the rows yet). **Escalated to a deep verification** because the cycle carried a **git history rewrite around the locked `PAPER_OUTLINE.md`** — that is a genuine high-risk event you don't eyeball-trust, so the monitor re-ran the load-bearing gate and audited the rewrite from source.
**Commit span:** bench `f898790..c6a35db` (4 commits) on parent `f7b9a2d` (the monitor's S-BS-38 commit), branch `bench-salvage/ws6c-dspy`, not pushed.

## The two cruxes

### 1. The history rewrite is clean (no paper-file contamination, no lost work)

The executor's first commit (pathspec-less `git commit`) swept in 3 staged paper-stream files (`docs/PAPER_OUTLINE.md` + 2 `docs/research/*`) that a concurrent session had left in the index. With monitor+user go, the executor soft-reset to `f7b9a2d` and rebuilt all 3 commits from the **exact original per-file blobs**, then re-staged the paper files. **Monitor re-verified from source:**
- `git diff f7b9a2d..HEAD --stat` = **exactly 9 files: the 8 executor files + the session log; ZERO paper files.**
- `f7b9a2d` intact (STREAM-only, 1 insertion) — untouched by the reset.
- The 3 paper files are **restored + re-staged** intact (`M`/`A`, 221 lines) in the index, in **no** WS-6d commit — yours to commit on the paper stream.
- Backend untouched (`mvp-ready @ 6720c70`, clean).

New tree = old tree minus exactly the 3 paper files. The decontamination did precisely what was promised. Lesson recorded as the `git-commit-pathspec-dirty-index` memory (concurrent `.devloop` sessions leave foreign files staged → always `git commit -- <your-files>`).

### 2. A3 (the frozen-contract gate) is PRINCIPLED, not gamed

A3 is the load-bearing claim — *the grade record is byte-identical with persistence on vs off* — and a strip-then-compare test is exactly where signal can hide. The monitor scrutinized `test_a3_grade_record_byte_identical_persistence_on_vs_off` and confirmed three controls make it real:
1. **NoOp-vs-NoOp control** (`strip(r_noop)==strip(r_noop2)`) proves `_NONDET = {pipeline_run_id, timestamp, duration_ms}` is *exactly* the run-to-run nondeterminism — the on-vs-off equality is not an over-strip artifact.
2. **`r_sqlite != r_noop`** on the raw dicts proves the runs are real executions, not memoised.
3. **side-effect assertions** (1 row written + `find_by_id` non-None) prove the Sqlite path *actually persisted* — so it is on-vs-off, not off-vs-off.
Any persistence-induced mutation of a non-stripped field fails the equality. **A3 ran AND PASSED on `debuglithrim` (6 passed)** — monitor re-ran it.

## Per-gate (monitor re-verified)

| Gate | Verdict | Evidence |
|---|---|---|
| A1 round-trip | PASS | `got == {**model_dump, agent_id}` — full fidelity, no schema drift |
| A2 eval-isolation | PASS | distinct `pipeline_run_id` → 2 rows; same id → upsert (last-write-wins) |
| A3 frozen contract | PASS | 6 passed on `debuglithrim`; test principled (3 controls above) |
| A4 Mongo retired | PASS | `MongoProvenance` → **0 hits** in `runtime/` (alias deleted; default → NoOp) |
| A5 default install | PASS | **205 passed / 8 skipped** default deps; new code ruff-clean; no new dep |
| A6 scope held | PASS | 8 files + session log; no paper files; backend untouched; no §10/consensus/grade-seam-signature change |

## The 4 questions

1. **Surface fidelity** — `SqliteProvenanceStore` (`save`/`find_by_id`) matches the backend Protocol template + the approved plan: opt-in (default `NoOp`), lazy import (the cycle fix), standalone `PIPELINE_RUNS`, fail-soft fire-and-forget.
2. **Behavioral fidelity** — the **blob tier** (S-BS-38) verbatim: full `provenance.model_dump(mode="json")` → `PIPELINE_RUNS`; `kb_retrievals` as the 4-field summary; no projection columns (S-BS-4 held). Eval-isolation rides `pipeline_run_id` uniqueness (the `::eval::` mechanism has no bench analogue — no `store_report` in the primitive).
3. **Out-of-scope intrusion** — none. The optional `test_grade_wire.py` docstring nit the monitor offered was taken (6 lines, in-scope).
4. **Spec ambiguity** — none new; the §7 "missing eval-collection indexes" was correctly scoped out (doc-shim-minimal, no consumer/query for them).

## Disposition

Audit CLEAN; rewrite verified clean; A3 principled + passing. **CLOSE** WS-6d — the in-process grade path is now Mongo-free (the first ship-path payment). Carryforward:
- **S-BS-39** (low) — `debuglithrim` *full* suite has 12 pre-existing reds (10× `test_ws5_bff` TestClient-version + 2× OBS isolation tests that are default-deps-only by design). Structurally not WS-6d (different subsystems); the env-analogue of S-BS-24, not a regression gate.
- **The 3 staged paper files** are the user's to commit on the paper stream (intact, decontaminated).
- S-BS-34 (ruff exclude) + S-BS-38 (persistence projection + S3/ADLS, future) carry forward.
