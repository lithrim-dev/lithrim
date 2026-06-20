# CRITIQUE — bench-salvage phase FAUTH-4b (fresh cold critic)

> Persisted verbatim by the monitor from the cold-critic subagent's return (the `devloop-critic`
> agent has no Write tool by design). The critic RAN Gate 0 itself + independently reproduced the flip.
> In-repo range: `2eb2f18..efa0000`. External pack: `545aafc` (a fixture only).

verdict: **CLEAN** (one NON-BLOCKING note + one OPEN-QUESTION, neither blocks closure)

gate0: { suite: PASS, lint: PASS, types: N/A, tests_first: SINGLE-COMMIT but RED→GREEN empirically demonstrated }

## Gate 0 — deterministic (SUPREME), ran it myself
Command: `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare python -m pytest -q -p no:cacheprovider`, both legs from the SAME physical repo root (per S-BS-FAUTH4-1).
- HEAD `efa0000`: **38 failed, 700 passed, 26 skipped**
- Parent `2eb2f18`: **38 failed, 698 passed, 26 skipped**
- **Parent↔HEAD failure-set diff: IDENTICAL (38 == 38, 0 net new, 0 swap)** — `diff` exit 0. The +2 passes at HEAD are exactly the 2 new case-10 tests. The cycle touches NONE of the 38 failing files (intersection empty). The 38 are pre-existing external-pack working-tree drift.
- `tests/test_value_presence_floor.py` **8 passed** under pack=narrative; `tests/test_value_presence_case10.py` **2 passed** with the external fixture present.
- Ruff: **404 == 404** parent↔HEAD (pre-existing); the 3 touched files are ruff-clean.
- Tests-first: one commit (impl+tests). RED grounded empirically: HEAD's tests against PARENT's `floors.py` are RED (`KeyError: 'concept_in_artifact'` at `test_value_presence_floor.py:119` / `test_value_presence_case10.py:103`).

## The 4 questions
**Q1 — refinement correct + backward-compatible? CLEAN.** `match="all"` behaviorally byte-unchanged (`conforms = not missing`, `floors.py:315-318`; only the evidence `"match"` string differs, irrelevant to `conforms`). `match="any"` now concept co-presence (`concept_in_artifact = bool(re.search(value_regex, artifact))`, `floors.py:300`), replacing the old token-preservation `bool(present)`. FAUTH-4 suite stays GREEN; the A1 evidence-assertion change (`missing`→`concept_in_artifact`, `test_value_presence_floor.py:119-120`) is legitimate (RED on old code), not vacuity.

**Q2 — case-10 flip real + non-vacuous? CLEAN.** Fixture is the REAL case-10 (transcript records the refusal twice; SOAP has zero `want|refus|declin`). A2 (`test_value_presence_case10.py:191-209`) asserts `original=="PASS"`, `stage=="BLOCK"`, `composite=="reject"`, `DISSENT_ERASURE` injected — deterministic, no LLM/network; independently reproduced. Paraphrase robustness genuinely distinguishes new from old: source tokens `['refused','declining']`, artifact "declined" → OLD `present=[]`⇒False (false-block); NEW `re.search` hits⇒True.

**Q3 — MOAT / scope / honesty boundary. CLEAN.** The 4 moat files, `harness/grounding.py`, and `verification/spec.py` are 0-diff vs `2eb2f18`. Both `floor_executors()` equality snapshots byte-unperturbed + passing (value_presence stays narrative-pack-local). Scope = exactly the 3 declared files. External `545aafc` touched ONLY `healthcare/fixtures/case10_dissent_erasure.json` (+18); the foreign `ontology.json`/`taxonomy_snapshot.json` drift is uncommitted working-tree only, correctly NOT swept in. No governance claim: `DISSENT_ERASURE` absent from the healthcare snapshot (committed AND drifted) — an in-test rescore string only; productionization deferred to NARR-5-CRIT (stated in commit body + fixture `_provenance` + `test_value_presence_case10.py:12-23`).

**Q4 — honesty gap. CLEAN, one OPEN-QUESTION.** The "real case-10 APPROVE→BLOCK" claim is honestly bounded (pack=narrative + in-test ontology, NOT a governed healthcare grade; snapshot mint deferred). The paraphrase-brittleness limit is explicitly stated (`floors.py:226-228`: even concept mode is bounded by the pinned `value_regex` form set; SNOMED is the paraphrase-robust swap-in, FAUTH-3b).

## Findings
- **[NON-BLOCKING]** Tests-first: one commit (impl+tests), no separate RED `test(...)` commit. Mitigated — RED demonstrated empirically (HEAD tests vs parent floor → KeyError). Accept; note for the close. → for next cycles, commit the RED test first.
- **[OPEN-QUESTION → S-BS-FAUTH4b-1]** SPEC_CLINVERDICT_SELF_SERVE.md:123 specifies token-substring ("missing required token"); FAUTH-4b's `match=any`→concept co-presence is a paraphrase mitigation INSIDE the regex form set that the spec/driver did not pre-authorize (no FAUTH-4b driver on disk). Reasonable + honestly bounded; surface so the spec author can LOCK §123 to permit the two-mode (`all`=preservation / `any`=concept-co-presence) semantic. Not BLOCKING (more permissive; `match=all` untouched).

new seams: none new code-side. S-BS-FAUTH4-1 (worktree-baseline hygiene) respected. **S-BS-FAUTH4b-1** opened (spec §123 lock — DOC, owner).

## Bottom line
A tight, spec-faithful, moat-safe refinement. The pre-existing 38-failure baseline is byte-identical parent↔HEAD from the same physical root; the cycle touches none of those files; the new tests are demonstrably RED on the parent floor. `match="all"` value-preservation is behaviorally unchanged; `match="any"` correctly becomes concept co-presence; the real case-10 flip (PASS→floor-inject DISSENT_ERASURE→BLOCK/reject) reproduced deterministically + offline, with the paraphrase twin clearing under the new semantic and false-blocking under the old. Moat/grounding.py/spec.py/both snapshots 0-diff; external commit = fixture only; foreign drift not swept; DISSENT_ERASURE not minted into governance; honesty boundary stated. Hunted for a silently-weakened assertion, a vacuous proof, swept-in drift, an over-claim — all held. **CLEAN.**

---

## Monitor corroboration
- MOAT + grounding.py + spec.py 0-diff vs `2eb2f18` re-confirmed; failure-set diff parent↔HEAD IDENTICAL (38==38) independently captured.
- External commit `545aafc` = `healthcare/fixtures/case10_dissent_erasure.json` only; the foreign `ontology.json`/`taxonomy_snapshot.json` drift (the source of the 38 failures) left untouched.
- HARD-GATE (verdict-path) satisfied — independent cold critic ran Gate 0 + reproduced the flip + returned CLEAN.
- S-BS-FAUTH4b-1 logged (spec §123 two-mode lock, owner/doc).
