# Spec-Adherence Critique — `bench-salvage` phase CE-PACK-6b-CLEAN

> Fresh-critic mode (HARD GATE). Worktree-isolated, adversarial-by-reproduction.

## Metadata

- **Stream:** bench-salvage
- **Phase:** CE-PACK-6b-CLEAN — clinical-clean the core council (the FROZEN-endgame finale of the generic-CE demarcation)
- **Driver bundle:** `bench-salvage-phaseCE-PACK-6b-CLEAN-clinical-clean-core-council-driver`
- **Commits audited:** `0cec6ac..df08ab3` (6 deliverables + session log) atop parent `1073fcc`; moat baseline `acc4973`
- **Spec(s) read against:** `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md` §0/§3/§4; `CLAUDE.md` taxonomy contract; `tests/_seam_freeze.py`
- **Critique mode:** `fresh-critic` (separate worktree-isolated session, not monitor-inline)
- **Date:** 2026-06-12
- **Reviewer:** critic session `af17916bd58f71969` (opus, `isolation: worktree`)

---

## Verdict

**NON-BLOCKING FINDINGS — [0 BLOCKING / 2 NON-BLOCKING / 0 OPEN-QUESTION]**

The FROZEN core council shed its last `build_prompt` / `safety_flags` / `_build_signature` clinical residue with the consensus/withstands **moat byte-frozen vs `acc4973`**, all three seam guards **reproduced non-vacuous** by real scratch-mutation, the seed relocation **output-neutral**, and the honesty re-scope (grep-empty NOT achieved, NOT claimed) **scrupulously documented**. The only caveats are an executor suite-count overstatement (corrected to 639/4 — still 0 new regressions) and an intentional historical-origin provenance string (D2-a, comment-guarded).

---

## 1. Surface fidelity

The cycle's "surface" is the authorized edit-set against the frozen files + the approved fork rulings.

| Plan ruling | Implementation | Match? | Severity |
|---|---|---|---|
| Fork 6 / D4: transcript branch → guard-marked `raise` | `compliance_council.py:2182` `raise ValueError("6b-CLEAN: …source_message-only")` (carries the `6b-CLEAN` sentinel) | exact | — |
| D4: delete `build_prompt` + import | `def build_prompt` gone; `from .safety_flags import get_flag_prompt_section` removed; core `safety_flags.py` deleted | exact | — |
| D3 / S-BS-129: genericize `_build_signature` ONLY | `judges_dspy.py` diff (vs parent) = 2 hunks both inside `_build_signature` (L173–194); I/O field names byte-stable | exact | — |
| Fork 2 = **D2-a**: keep `flag_source` literal frozen (no `_provenance` carve-out) | `flag_source` unchanged; `assert_clinical_ontology_seam_frozen` still byte-compares `_provenance`; comment-guarded as historical-origin in both `seed_ontology.py` + the relocated module | exact | — |
| Fork 3/4: retire `test_live_smoke.py` + `ab_harness.run_live` | both gone; `test_ab_harness` cost-refusal test removed | exact | — |
| D5: bounded guard authorization | `_SIGNATURE_GENERICIZE_SEAM = {"_build_signature"}`; `6b-CLEAN` deletion/raise markers; no blanket bypass | bounded | — |

**Findings:** No surface drift. Every authorized symbol change matches the monitor-approved plan exactly; no unauthorized line in either frozen file (V2 confirmed by `git diff 1073fcc HEAD`).

---

## 2. Behavioral fidelity

### Behavior 1: the moat (consensus/withstands MECHANISM) is byte-frozen

- **Spec assertion:** CLAUDE.md — "`_apply_consensus` + the consensus/withstands MECHANISM are byte-frozen vs `acc4973` (the moat is 0-delta)."
- **Test/verification:** full-body extraction at HEAD vs `git show acc4973:…compliance_council.py`.
- **Implementation:** `_apply_consensus` 28767 B / 547 L **byte-identical**; `extract_verdict_confidence` 1703 B / 40 L **byte-identical**.
- **Chain closes?** YES. Zero drift.

### Behavior 2: the freeze guard is non-vacuous in BOTH directions, all 3 guards

- **Spec assertion:** driver C4 — "an unauthorized deletion must still FAIL"; authorized edits must pass.
- **Test:** `tests/test_6bclean_seam_guard.py` (8 tests) + scratch-mutation reproduction.
- **Implementation:** all 3 guards **bite** on real scratch-mutation: (i) delete 15 L of `_apply_consensus` → `AssertionError: unauthorized DELETION … at base L1867-1881`; (ii) tamper `evaluate_dspy` → `consensus-seam symbol(s) drifted: ['evaluate_dspy']`; (iii) change `flag_source` in real `ontology.json` → `clinical_v1.json consensus/owner seam drifted`. Each restored.
- **Chain closes?** YES. The guards genuinely refuse unauthorized edits; the authorized deletion/signature/raise pass.

### Behavior 3: C1 — only the transcript path rerouted; source_message intact

- **Spec assertion:** monitor condition C1 — "`evaluate(context_kind=source_message)` must still route to `build_source_message_prompt`."
- **Test:** `tests/test_6bclean_reroute.py` + code trace.
- **Implementation:** `evaluate()` L2182 `if context_kind == CONTEXT_KIND_SOURCE_MESSAGE: build_source_message_prompt` (untouched); only the `else` (transcript) raises. `stages.py` reroutes ONLY the transcript default to `_default_authored_evaluator`. **0 live `build_prompt` callers** (all 11 remaining are doc-comments/docstrings).
- **Chain closes?** YES.

**Findings:** No behavioral drift. The three load-bearing behaviors all demonstrated by reproduction.

---

## 3. Out-of-scope intrusion

Driver deliverables (D1–D7) + monitor conditions (C1–C4). `git diff 1073fcc HEAD --stat` = 23 files, all mapping to a deliverable/condition:

- D1: `stages.py`, `authored_stage.py`, `ab_harness.py` (Fork 4); D2-a: `safety_flags_seed.py` (rename+strip), `seed_ontology.py`; D3: `judges_dspy.py`; D4: `compliance_council.py`, `__init__.py`; D5: `_seam_freeze.py` + `test_6bclean_seam_guard.py`; D6/C3: `test_uap3_grade.py`, `pipeline/models.py`, `backends/local_pipeline.py`, `scripts/run_eval.py`, `test_consensus.py`, retire `test_live_smoke.py`/`test_ab_harness.py`; attestation `test_6bclean_attestation.py` + reroute `test_6bclean_reroute.py`; D7 `SPEC…`, `CLAUDE.md`, `test_standalone_ce.py`.

**Findings:** No intrusion. Foreign files (`apps/shell/src/app.jsx`, `journeys/*`, the live-demo HANDOFF) **untouched** across all 7 commits. Every commit pathspec-scoped.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: A1 "grep → empty" is unachievable this cycle (Fork 1)

- **Spec text:** driver headline `grep -riE 'hipaa|clinical|…' lithrim_bench/runtime/council/` → empty, **vs** SPEC §4 deferring `build_source_message_prompt`.
- **Implementation decided:** re-scoped A1 to "the 3 named residues removed; remaining residue enumerated + pinned by `test_6bclean_attestation.py`"; opened CE-PACK-6c. `compliance_council.py` still carries the **live** `build_source_message_prompt` branch (140 needles → fewer, not zero).
- **Resolution:** ACCEPTED at plan-review (monitor). The close does NOT claim grep-clean (SPEC + attestation docstring both say so explicitly). Non-vacuous: a scratch needle in unlisted `llm_provider.py` → attestation FAILS.

### Ambiguity 2: SPEC §4 "delete safety_flags outright" vs driver D2 "relocate"

- **Implementation decided:** RELOCATE (D2-a) — `seed_ontology.py` + `test_ws2.py` import the seed, so an outright delete would break the seed path. The §4 note missed the live importer.
- **Resolution:** driver D2 correct; logged as a SPEC discrepancy for the §4 author.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 2 | 0 |

**Total BLOCKING: 0** → cycle MAY close.

### NON-BLOCKING dispositions

1. **Suite-count overstatement (advisory).** Executor handback claimed **642 passed / 2 failed**; critic verified **639 / 4 / 3**. The 2 extra failures (`test_byoc_provider::…all_azure_back_compat` — unset `AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3`; `test_uap3_grade::…builds_authored_stage_not_default_council` — missing gitignored `out/scribe_v1.jsonl`) are **PRE-EXISTING** (reproduced at parent `1073fcc`) → still **0 new regressions**. Executor env (Azure vars + fixture present) inflated the count. **Disposition:** the close-doc cites **639/4-with-4-pre-existing**, not 642/2. Honesty-is-the-moat. ruff: parent 455 → HEAD 452 (−3 from the deletion), 0-new.
2. **`flag_source` literal names a deleted path (LOW).** Intentional + comment-guarded per D2-a (historical authoring origin). **Disposition:** fold the path-string refresh into the pre-existing **S-BS-113** re-seed (do NOT full-re-seed — sweeps the `fidelity` owner_roles addition); do NOT open a standalone seam.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Verified the diff via `git show`/`git diff` against commits, not the executor's summary
- [x] Re-ran the suite + ruff independently in an isolated worktree
- [x] Reproduced guard non-vacuity by scratch-mutation (restored each)
- [x] Did NOT edit any code, spec, or driver in the user's tree
- [x] Did NOT confer before writing the verdict

## Appendix: commits audited

```
df08ab3 docs(devloop): session log — CE-PACK-6b-CLEAN executor return
5118738 docs(ce): 6b-CLEAN done — core council prompt-builder is clinical-clean (re-scoped A1); open the 6c seam (D7)
42f70e4 refactor(council): delete build_prompt + the evaluate transcript branch + the orphaned safety_flags.py (D4)
10585c5 refactor(council): genericize _build_signature — domain-agnostic scaffold (D3, S-BS-129)
5513917 test(seam): authorize the build_prompt deletion + the _build_signature genericization; non-vacuity both directions (D5, C4)
1ed34e0 refactor(pack): relocate the safety-flag seed into the healthcare pack; seed_ontology reads it (D2-a)
0cec6ac refactor(pipeline): reroute the transcript stage to the authored council; retire the ab_harness control arm (D1, Fork 4)
```

## Appendix: suite observed

`639 passed, 4 failed, 3 skipped` (debuglithrim full run). 4 failures ALL pre-existing at parent `1073fcc`: the 2 S-BS-96 observation import-isolation guards (pass in isolation) + the unset-Azure-env + the missing-gitignored-fixture. The 3 new test files (`test_6bclean_seam_guard` 8 + `test_6bclean_reroute` 4 + `test_6bclean_attestation` 3) all pass.
