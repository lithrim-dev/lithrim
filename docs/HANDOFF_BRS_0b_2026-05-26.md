# Handoff — BRS-0b exec session, 2026-05-26 (paused at Phase 6, awaiting monitor close-out)

> **Cycle:** BRS-0b — Bench reporting fix + paper framing rewrite
> **Driver:** `lithrim-command-center/.lithrim/prompts/brs_0b_bench_reporting_fix_driver.md`
> **Companion BRS-0a output (read for context):** `docs/research/MEASUREMENT_AUDIT_2026-05-26.md` (commit `85901d8`)
> **Status:** ALL EXEC WORK COMPLETE. AWAITING MONITOR APPROVAL TO COMMIT.
> **Next action:** monitor reviews diffs + test output below → on approve, scoped `git add` + commit (no rebuild required).

---

## Status in one paragraph

BRS-0b execution complete through Phase 5 (ruff + pytest). All deliverables (a–i) landed per the approved plan. Tests pass 78/78 including the three new tests (i.1 parser, i.2 worst-of invariance, i.3 §7 snapshot). Belt-and-suspenders manual re-derivation via `analyze_runs.py` confirms §7 numbers are **byte-identical** to the pre-change baseline on all 4 packs. Paper §4.6 (new), §5.2 (rewrite), §7.1 (framing note), §7.3 (rewrite), §7b.8 (rewrite) all reflect validator-coverage-gap framing; S17 (scheduling 22→17, hl7 26→42 default) and S18 (scribe no longer "semantic-only by design") closures landed in §5.2. No commit yet — exec is stopped per Phase 6 discipline. **Monitor close-out is the gating step.**

---

## Deliverables — file inventory

### Code (1 file)

| File | Change | Lines |
|---|---|---|
| `lithrim_bench/backends/lithrim_pipeline.py` | `_STAGE_STATUS_NORMALIZE["not_applicable"] = "not_applicable"` (was `"PASS"`). Plus ruff cosmetic wraps on `sorted({...} - {""})` blocks in `_parse`. | +6 / -7 |

### Tests (3 files modified, 1 created, 1 fixture created)

| File | Change |
|---|---|
| `tests/test_lithrim_pipeline_parser.py` | Renamed `test_not_applicable_normalizes_to_pass` → `test_structural_not_applicable_preserved_through_backend_verdict`. Assertion updated to `structural_verdict == "not_applicable"` (was `"PASS"`). Docstring expanded. (i.1) |
| `tests/test_worst_of_backend.py` | Added `test_worst_of_rank_skips_structural_not_applicable_and_preserves_in_report` — locks the no-code-change invariant in `worst_of.py` against future regression. (i.2) |
| `tests/test_brs_0b_section_7_invariance.py` | **NEW.** Snapshot test re-deriving §7.1 pack_summary against `tests/fixtures/brs_0b_section7_snapshot.json`. Skips if `out/*.n10.ndjson` not present. Docstring includes regeneration command + monitor's "only when intentional" note. (i.3) |
| `tests/fixtures/brs_0b_section7_snapshot.json` | **NEW.** Pre-change baseline snapshot of `analyze_pack` output for 4 FHIR packs at `split=test`. Committed for the test to assert against. |

### Paper drafts (4 files)

| File | Section | Change |
|---|---|---|
| `docs/paper_draft/04_method.md` | §4.6 added | New "Validator coverage and its decomposition from the worst-of rule" subsection (~180 words). Cites BRS-0a §1.3 verbatim with anchor link per monitor note 3. Names mapping 18 envelope-only pattern. |
| `docs/paper_draft/05_benchmark.md` | §5.2 rewritten | Pack table now has 6 columns (added "Validator scope"). S17 closure: scheduling row corrected to `fhir_appointment` + mapping 17; hl7 row clarifies mapping 42 default + 26/93 as direct-backend references. S18 closure: "semantic-only by design" framing removed from scribe row; explicit acknowledgment scribe is no longer a clean negative control. Injector lists verified against `lithrim_bench/injectors/__init__.py:16-42` per monitor note 4. |
| `docs/paper_draft/07_results.md` | §7.1 framing note + §7.3 rewrite | §7.1 gains a one-paragraph framing note ahead of the table (validator-coverage caveat citing §4.6 + BRS-0a §3). §7.3 headline-contrast paragraph rewritten as "validator-coverage ceiling under explicit registration." **Numbers in both tables unchanged.** |
| `docs/paper_draft/07b_threats_to_validity.md` | §7b.8 rewritten | Heading expanded to "...and the structural axis is contractually blind." Body incorporates BRS-0a §2.2 verbatim citation of **278 fhir_appointment BLOCK verdicts** (per monitor note 2). Names artifact_judge as sole detector; explicit mapping 17 envelope-only blindness. |

---

## Test output — verbatim

```
============================== 78 passed in 0.48s ==============================
```

The three new tests specifically:

```
tests/test_lithrim_pipeline_parser.py::test_structural_not_applicable_preserved_through_backend_verdict PASSED
tests/test_worst_of_backend.py::test_worst_of_rank_skips_structural_not_applicable_and_preserves_in_report PASSED
tests/test_brs_0b_section_7_invariance.py::test_section_7_pack_summary_invariance_against_brs_0b_baseline PASSED
```

Pre-change state (verified before the code change landed, per monitor discipline): (i.1) FAILED as expected (locked the new contract); (i.2) PASSED (confirms no `worst_of.py` change needed); (i.3) PASSED (baseline self-consistent).

---

## §7 numerical invariance — belt-and-suspenders verification

Ran `python3 scripts/analyze_runs.py --runs out/<pack>.n10.ndjson --pack out/<pack>.n10.jsonl --split test` post-change on all 4 packs and diffed against the pre-change baseline snapshot. Result:

```
scribe_v1: BYTE-IDENTICAL to baseline ✓
scheduling_v1: BYTE-IDENTICAL to baseline ✓
coding_v1: BYTE-IDENTICAL to baseline ✓
triage_v1: BYTE-IDENTICAL to baseline ✓
TOTAL DIFFS: 0
```

Acceptance criterion #2 ("Existing NDJSON re-analyzes cleanly; §7 numeric values unchanged") satisfied. HALT condition (a) not triggered.

---

## ruff status

```
4 files reformatted (cosmetic only — docstring blank-line, sorted({...}-{""}) wraps)
All checks passed!
```

The 4 reformatted files: `lithrim_bench/backends/lithrim_pipeline.py`, `tests/test_lithrim_pipeline_parser.py`, `tests/test_worst_of_backend.py`, `tests/test_brs_0b_section_7_invariance.py`. No semantic change.

---

## Monitor notes — all applied

| # | Note | Status |
|---|---|---|
| 1 | (i.3) snapshot test docstring with "regenerate ONLY when section 7 numbers intentionally change" | ✓ docstring includes verbatim regeneration command + the discipline note |
| 2 | §7b.8 "278" number must be lifted verbatim from MEASUREMENT_AUDIT §2.2 | ✓ verified at write time; §2.2 says *"CONFIRMED across 278 BLOCKs in 22-23 window (verdict-BLOCK count = artifact-BLOCK count = 278)"*; cited explicitly |
| 3 | §4.6 anchor link to MEASUREMENT_AUDIT §1.3 | ✓ added: `(../research/MEASUREMENT_AUDIT_2026-05-26.md#13-what-the-validators-actually-check-phase-2--ask-2)` |
| 4 | §5.2 injector list spot-check against `lithrim_bench/injectors/__init__.py` | ✓ all 5 packs verified: scribe (WrongDosage/MissingAllergy/FabricatedHistory/ValueMismatch/HallucinatedDetail), scheduling (PhiDisclosurePreVerification), coding (UpcodingRisk), triage (MissedEscalation), hl7 (5 HL7-structural injectors named) — match exact contents of `SCRIBE_INJECTORS` / `SCHEDULING_INJECTORS` / `CODING_INJECTORS` / `TRIAGE_INJECTORS` / `HL7_ADT_INJECTORS` lists |
| 5 | Manual `analyze_runs.py` re-derivation before commit | ✓ ran on all 4 packs; diff vs baseline: 0 changes |

---

## Pre-existing working-tree state (NOT BRS-0b deliverables)

Surfaced for monitor awareness — these were in the working tree before BRS-0b started and **must be excluded from the BRS-0b commit**:

| File | Origin | Disposition |
|---|---|---|
| `docs/PAPER_OUTLINE.md` (modified) | Earlier in same conversation session (2026-05-26 reframe + amendment paragraphs added before BRS-0b kicked off) | Exclude from BRS-0b commit; commit separately under its own change story |
| `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` (new) | Same conversation session | Exclude from BRS-0b commit; commit separately |
| `docs/label_owner_matrix.md` (modified) | Pre-existing local regeneration pointing to `out/scribe_v1.n10.jsonl` instead of the lithrim-backend golden set. Not touched in BRS-0b. | Exclude from BRS-0b commit; either commit separately or revert |

The BRS-0b commit is scoped to exactly the 9 deliverable files listed above.

---

## One pre-existing finding surfaced for monitor (out of scope, no action)

`triage_v1`'s CI in `out/triage_v1.n10.test.analysis.json` is `[0.8938, 0.9938]`, but `docs/paper_draft/07_results.md` §7.1 table currently states `[0.844, 0.954]`. The JSON file is authoritative; paper text drifted before BRS-0b. **Not touched in this cycle** (out of scope; the driver's (f) instruction said "Numbers unchanged"). Candidate fix-up for BRS-6 (paper amendment) alongside the framework rewrite. Logged here so future cycles don't rediscover it.

---

## What the next session does (in order)

1. **Read this handoff first.** It is paste-ready context for a fresh exec session.
2. **Verify state on local environment.** Run:
   - `python3 -m pytest tests/ -v` — must show 78 passed (or 77 passed + 1 skipped if `out/` is gitignored on this checkout)
   - `python3 -m ruff check lithrim_bench/ tests/` — must show "All checks passed!"
3. **If monitor has approved:** execute the scoped commit (full command below).
4. **If monitor has not yet approved:** stop and wait.
5. **After BRS-0b commit closes:** decide next cycle from the BRS arc. See "Next cycle candidates" below.

### Scoped commit command (paste-ready, monitor must approve first)

```bash
git add lithrim_bench/backends/lithrim_pipeline.py \
        tests/test_lithrim_pipeline_parser.py \
        tests/test_worst_of_backend.py \
        tests/test_brs_0b_section_7_invariance.py \
        tests/fixtures/brs_0b_section7_snapshot.json \
        docs/paper_draft/04_method.md \
        docs/paper_draft/05_benchmark.md \
        docs/paper_draft/07_results.md \
        docs/paper_draft/07b_threats_to_validity.md

git commit -m "$(cat <<'EOF'
fix(bench): not_applicable distinct + paper framing (BRS-0b)

(1) Preserves stage_results.structural.status="not_applicable" as a
distinct value through the bench's reporting chain (was: collapsed
to "PASS" by _STAGE_STATUS_NORMALIZE in lithrim_pipeline.py:30-34).
Existing section 7 numbers unchanged (BRS-0a confirmed zero
not_applicable rows in the n10 sweep); the fix is hygiene for
future runs with absent profiles or stricter validators.

(2) Section 5.2 pack-validator rows corrected per BRS-0a audit
section 1.1 (commit 85901d8): scheduling_v1 actual binding is
fhir_appointment / mapping 17 (envelope-only Lithrim FHIR R4
Appointment Validator), not scheduling_action / mapping 22.
hl7_adt_v1 default profile resolves to mapping 42 (Lenient); the
"deployed" (mapping 26) and "strict" (mapping 93) references are
direct-backend artifacts used by the section 7.3 worst-of
composition, NOT the active profile.

(3) Section 4 adds a 4.6 "Validator coverage" subsection;
section 7.1/7.3/7b.8 framing rewritten from stock-config-vs-
production to validator-coverage-vs-validator-existence. Scribe
"semantic-only by design" framing removed (S18 resolution per
monitor 2026-05-26).

Tests added: parser preserves not_applicable; WorstOfBackend
rank-skips not_applicable while preserving it in the reporting
field; section 7 pack_summary snapshot regression guard
(byte-identical to pre-change baseline on all 4 packs).

No section 7 numeric change. No new LLM call. No backend code
touched.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Next cycle candidates (read BRS-0a §5 for full reframe context)

The BRS arc is 7 cycles; BRS-0a closed (audit), BRS-0b closes here (this cycle). Remaining:

| Cycle | Original scope | Reframed scope (post-BRS-0a) | Estimated effort |
|---|---|---|---|
| **BRS-1** | provenance observability — `silent_confident_certification` boolean + `verdict_flipped_by_stage` string on PipelineProvenance | **expand** to also persist validator template id + checks-run-count + checks-failed-count (validator-template-pin). Closes the validator-coverage observability gap that BRS-0a surfaced. | ~1–1.5 days |
| **BRS-3** | Variant B critique pass — structural findings as immutable critique context | **deprecation candidate** — zero structural findings on FHIR packs at current validator coverage; nothing for critique to defend. Either cancel or rescope to HL7-only after profile registration | cancel or 1 day |
| **BRS-4** | artifact_judge per-artifact-type opt-out | **rescope** to "improve artifact_judge precision via critique pass" — opt-out target is `fhir_appointment` not `scheduling_confirmation`; opt-out costs all 278 BLOCKs in the sweep; precision fix is cheaper and net-positive | ~1–2 days |
| **BRS-6** | re-run packs and amend Paper 1 §7 | **broader paper amendment** — §4 + §5 + §7 framing now lives in BRS-0b; BRS-6 picks up the framework-paper reframe (Paper 1 → Jute Copilot paper per 2026-05-26 amendment in `docs/PAPER_OUTLINE.md`) + the 1-day council-confidence experiment | ~4–5 days post the 1-day experiment |

**Recommended next:** BRS-1 (cheap, observability foundation that BRS-6 builds on), then BRS-6 (paper). BRS-3 cancel (or defer until validator templates upgrade). BRS-4 worth queuing but not urgent.

The **framework-paper reframe** (Paper 1 = Jute Copilot paper, full mechanism disclosure) is captured in `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` (pre-existing in working tree). BRS-6 will execute against that decision when it kicks off.

---

## Single biggest risk going forward

**The pre-existing working-tree state must not bleed into the BRS-0b commit.** The scoped `git add` command above is explicit; verifying `git status --short` after staging shows ONLY the 9 BRS-0b deliverable files (3 of those will be in the "untracked" → "added" path: `tests/test_brs_0b_section_7_invariance.py`, `tests/fixtures/brs_0b_section7_snapshot.json`) is the safety net. If the staged tree includes `docs/PAPER_OUTLINE.md` or `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` or `docs/label_owner_matrix.md`, **stop and unstage** before committing.

---

## Audit-trail discipline preserved

- All BRS-0b causal claims have evidence (file:line cites, jq output, MEASUREMENT_AUDIT §-numbered cites) per `lithrim-backend/CLAUDE.md` diagnose-before-edit gate.
- The 2026-05-22 + 2026-05-23 + 2026-05-26 reframe notes on `docs/PAPER_OUTLINE.md` are preserved verbatim (not modified by BRS-0b).
- The BRS-0a output (`docs/research/MEASUREMENT_AUDIT_2026-05-26.md`, commit `85901d8`) is the load-bearing source for §4.6 + §5.2 + §7.1 + §7.3 + §7b.8 rewrites; every paper edit cites it with §-number.
- No lithrim-backend code touched, no LLM call, no service started, no profile registered.
