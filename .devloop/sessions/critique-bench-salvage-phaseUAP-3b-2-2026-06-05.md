# Spec-Adherence Critique — `bench-salvage` phase `UAP-3b-2`

> Fresh-critic session (HARD GATE). Cold read; default-skeptical; every load-bearing
> claim independently re-run, not trusted from the executor's session log.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `UAP-3b-2` (complete the moat — S-BS-72 provenance blob + GroundingCheck entities + the LIVE attestation)
- **Driver bundle:** `bench-salvage-phaseUAP-3b-2-groundingcheck-entity-llm-critique-driver`
- **Commits audited:** `8a159c0..HEAD` = `662a1c0`, `74215bf`, `af584cc`, `f3f0932`, `24318a7` (5 commits)
- **Spec(s) read against:** `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §2A (:60-74), §2B (:82-115); `docs/specs/SPEC_PRODUCT_SHELL.md` §10; driver §2/§3/§5
- **Critique mode:** `fresh-critic` (separate session)
- **Date:** 2026-06-05
- **Reviewer:** critic session (cold)

---

## Verdict

**`NON-BLOCKING FINDINGS`**

One sentence: The deterministic moat's operational + audit layers landed cleanly and additively (S-BS-72 above the frozen seam, byte-identical; GroundingChecks read-only-additive for `clinical_v1`; frozen seam wc-l == 0), and the LIVE attestation is **HONEST** — Run A's 3×withstand ruling and Run B's genuine non-firing are both verified directly from the persisted blob, the prize tier was correctly halt-to-surfaced (not manufactured), so the cycle is safe to close as PROCEED-WITH-CAVEATS.

---

## 1. Surface fidelity

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| §2A: GroundingCheck = first-class INDEPENDENT entity declared in the eval profile (:63) | `config.py:64` `EvalProfile.grounding_checks: tuple[str,...] = ()` + `agent_from_dict`/`agent_to_dict` round-trip | exact (additive default-empty) | — |
| §2B: critique ruling `why` = `{signals_weighed:[ontology_rules,validator_outputs], decision, what_failed}` (:102) | `withstands.py:59 to_audit_why()` → `{signals_weighed, decision, what_failed}`; embedded as `{role, **why}` (`run_eval.py:166`) | exact | — |
| §2B: `actor.type` includes `grounding_check`; action `run\|suppress\|...` (:88-89) | `grounding_check.py:67/91` `Actor(type="grounding_check")`, action `suppress`/`floor_block`/`run` | exact | — |
| §2B: processing audit = the full chain incl. the critique's withstands-decisions (:107) | `run_eval._embed_withstands_in_blob` → blob `withstands_decisions`; BFF `_run_audit_report` `withstands` projection (`apps/bff/app.py:727`) | exact | — |
| §13: locus = BOTH — independent GroundingChecks post-consensus, gate pre-consensus (:268) | GroundingCheck audit appended after `ground()`/`composite()` (`run_eval.py:351-358`); gate stays pre-consensus | exact | — |
| Driver §2 B/D2: S-BS-72 ABOVE the frozen seam, returned dict byte-identical | `_embed_withstands_in_blob` patches only the persisted blob (`PIPELINE_RUNS.get→insert`); never touches `result`/`_apply_consensus`/`PipelineProvenance` | exact | — |
| SPEC_PRODUCT_SHELL §10: new read field ratified | `+1` UAP-3b-2 bullet documenting the `withstands` array (no new endpoint) | exact (in-scope A2) | — |
| SPEC_UNIFIED §2A (LOCKED): GroundingCheck entity definition | `+1` append-only `*(Impl status …)*` parenthetical; original line verbatim-preserved | additive impl-note on a locked spec | NON-BLOCKING |

**Findings:**

- `[NON-BLOCKING]` The LOCKED `SPEC_UNIFIED_AUTHORING_PRODUCT.md` §2A gains a 1-line append-only impl-status parenthetical (`8a159c0..HEAD` word-diff confirms: the normative GroundingCheck definition is preserved verbatim; only a green-highlighted `*(Impl status, UAP-3b-2 2026-06-05: … light surface landed …)*` was appended). It changes **no** normative content (entity contract, withstands-gate, R0–R9 all untouched) and mirrors the spec's own §13 precedent that additive notes "do not alter the lock." Logged at plan-review (`APPROVED-AT-PLAN`). A strict reading would prefer impl-status to live in the STREAM/session log rather than the locked spec body, but it is disclosed, benign, and reduces drift between the spec and reality. **Disposition: accept.**
- `[NON-BLOCKING]` The 1-line BFF `withstands` projection in `_run_audit_report` is beyond the driver's literal file list but is REQUIRED for A2's `/v1/runs/{id}/audit` leg, was flagged at plan-review (`APPROVED-AT-PLAN`), folded into D2, and ratified in SPEC_PRODUCT_SHELL §10. **Disposition: accept (logged decision, not drift).**

All other public symbols match spec exactly. No renamed/removed/incompatible surface.

---

## 2. Behavioral fidelity

### Behavior 1: S-BS-72 — the withstands ruling lands in the run-PROVENANCE blob, ABOVE the frozen seam, returned dict byte-identical

- **Spec assertion:** §2B:107 "the processing audit = the full chain incl. … the critique's withstands-decisions"; driver §2-B/D2 "ABOVE the frozen `_apply_consensus` … the returned `result` dict stays byte-identical (A3)."
- **Test:** `tests/test_uap3b2_provenance.py::test_S_BS_72_provenance_blob_carries_withstands_ruling` — runs the REAL `grade_inprocess` (injected per-role predictors, no Azure) with an injected `SqliteProvenanceStore`; asserts the blob has NO `withstands_decisions` *before* the embed, then after the embed reads back `{role, signals_weighed:{ontology_rules,validator_outputs}, decision:'corrected', what_failed}` and `pipeline_run_id` preserved. I re-ran it (debuglithrim): **PASS**.
- **Implementation:** `_embed_withstands_in_blob` (`run_eval.py:127-170`): `in_process and run_id and sink` guard → `PIPELINE_RUNS.get(run_id)` → set `blob["withstands_decisions"]` → `PIPELINE_RUNS.insert(blob)`. Structurally it touches ONLY the persisted blob.
- **Chain closes?** **YES.** Independently verified the three crux sub-claims:
  - (i) Patches only the persisted blob. `grade_inprocess` returns `result.model_dump(mode="json")` (`grade.py:170`) — a freshly-serialized dict, a *distinct object* from the `PipelineProvenance` the backend saves internally. `_embed_withstands_in_blob` never receives `result`, never touches `_apply_consensus` or the `PipelineProvenance` model (both 0-delta this cycle). Byte-identity of the returned dict is guaranteed by construction.
  - (ii) FK preserved. `collections.py:73` upsert = `ON CONFLICT(id) DO UPDATE SET fk=excluded.fk, json=…`; the re-inserted full doc carries `org_id` (the fk), so the fk re-derives to the same value. Confirmed in the live blob (`pipeline_run_id` + `org_id` intact).
  - (iii) Real round-trip. The test goes through the genuine `grade_inprocess` + an injected store, not a mock.
- **Note:** The test calls `_embed_withstands_in_blob` directly rather than via `run()`. So the *unit* of the embed + the real grade-save path is covered, but the full `run()` wiring (does `run()` pass the right args, in order, with `collections_db`) is only exercised by the LIVE Run A — which I verified independently below (the blob carries the 3-judge ruling). Net: the chain closes across the unit test + the live run together.

### Behavior 2: A6 — GroundingChecks run + audited at the post-consensus locus; `ground()`/`composite()` additively identical for `clinical_v1`

- **Spec assertion:** §2A:63 "GroundingCheck … executed per evaluation alongside the LLM judges … promoted to a config-plane-authored, standalone entity"; driver §2-D3 "`ground()`/`composite()` ADDITIVELY IDENTICAL for the floor-less `clinical_v1`."
- **Test:** `tests/test_uap3b2_grounding_check.py` (5 tests, default deps, $0). `test_ground_and_composite_additively_identical` snapshots `(suppressed, active, floor_blocks, grounded.verdict, composite.verdict)` before/after `audit_grounding_checks(...)` and asserts `before == after`; `test_undeclared_profile_emits_nothing` pins the default-`()`→`[]` no-op; `test_eval_profile_grounding_checks_roundtrips` pins the additive serialization. I re-ran: **5 PASS**.
- **Implementation:** `grounding_check.py::audit_grounding_checks(declared, grounded, …)` is a **pure reader** over `GroundedResult.suppressed`/`floor_blocks` — it takes `grounded` as input and never calls `ground()`. Empty `declared` short-circuits to `[]` (`:55`). `run_eval.py:355` calls it AFTER `ground()`/`composite()` and only appends to `audit_log`.
- **Chain closes?** **YES.** Independently verified: `harness/grounding.py` and `harness/report.py` (composite) are **0-delta** this cycle (`git diff 8a159c0..HEAD … | wc -l == 0`), so `ground()`/`composite()` control flow is provably unchanged. `EvalProfile.grounding_checks` defaults `()` and `agent_to_dict` only emits the key when non-empty, so every committed agent (incl. the frozen `ws0_default.json`, also 0-delta) serializes byte-identically. The audit is a strictly-additive projection.
- **Note:** None. This is the cleanest of the three.

### Behavior 3: §2A invariant — "the gate cannot relabel a by-construction case"

- **Spec assertion:** §2A:73-74 "The critique can down-rank or correct a judge's reasoning but cannot relabel a by-construction case."
- **Test:** `tests/test_uap3b2_provenance.py::test_gate_cannot_relabel_true_case` — risk_judge raises `WRONG_DOSAGE` (its OWN in-lens Tier-1 code) → the gate withstands it, decision stays `reject`, the finding is kept. I re-ran: **PASS**.
- **Implementation:** `withstands.py:144-164` (0-delta, REUSED): an out-of-lens code is rejected ONLY when no owning judge corroborates it; a validator-disproved code is suppressed only on a deterministic disprove. An in-lens true finding falls through to `kept` (`:166`).
- **Chain closes?** **YES.** Re-pinned by the guard test; the gate logic is unchanged this cycle. The LIVE Run A corroborates it on the real trio (below): `WRONG_DOSAGE` survived the on-by-default gate → verdict stayed BLOCK (S-BS-73 holds).
- **Note:** None.

**Findings:**

- `[OPEN-QUESTION]` Cross-locus PresenceCheck coexistence (pre-existing, not this cycle). On LIVE Run A the **pre-consensus gate** ruled faithfulness_judge's `MEDICATION_NOT_IN_TRANSCRIPT` **withstand** (verified in the blob), while the **post-consensus `ground()`** disproved the same code (the `corrections` array shows `PresenceCheck` matched "zidovudine", `composite_before/after: BLOCK`). The same contract on the same code resolved differently at the two loci. This stems from `signals.py` (0-delta this cycle) building the per-judge validator signal from the seam finding's own `evidence_spans`+case shape, which can differ from what `ground()` reconstructs post-consensus. It changes **no** acceptance claim (both outcomes are honestly reported; the gate code is unchanged), and it is inherited UAP-3b behavior — but the spec (§2A/§13 locus=BOTH) does not reconcile *why* an independent post-consensus GroundingCheck may disprove a code its judge-attached pre-consensus signal admitted. Surface to the spec author; out of this cycle's scope to fix.

---

## 3. Out-of-scope intrusion

Driver §2 deliverables: D1 (live attestation — recorded run, no code), D2 (S-BS-72 provenance embed), D3 (GroundingCheck entities), D4 (tests), D5 (docs + UAP-3b-3 split stub).

`git diff 8a159c0..HEAD --name-only` (10 files):

```
lithrim_bench/harness/grounding_check.py            <- D3 (new)
lithrim_bench/harness/config.py                     <- D3 (EvalProfile.grounding_checks)
scripts/run_eval.py                                 <- D2 + D3 wiring
apps/bff/app.py                                      <- D2 (1-line withstands projection; logged A2)
tests/test_uap3b2_provenance.py                     <- D4
tests/test_uap3b2_grounding_check.py                <- D4
docs/specs/SPEC_PRODUCT_SHELL.md                     <- D5 (§10 ratify, +1)
docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md         <- D5 (§2A impl-note, +1)
.devloop/prompts/...UAP-3b-3...driver.md             <- D5 (split stub)
.devloop/sessions/session-...UAP-3b-2-2026-06-05.json <- session log
```

**Findings:**

- All 10 diffed files map to a D1–D5 deliverable (or the session log). **No drive-by refactor, no formatting pass, no dep bump.**
- I independently re-verified the FROZEN set is untouched (driver §4): `compliance_council._apply_consensus` + `judges_dspy` + `judge_metric` + `council_roles/` + `data/ontology/clinical_v1.json` + `data/config/agents/ws0_default.json` → `git diff … | wc -l == 0`. I additionally confirmed the REUSE-not-rewrite claim: `withstands.py`, `signals.py`, `authored_stage.py`, `grounding.py`, `report.py`, `audit.py` are **all 0-delta** — the cycle composes over them, never edits them.
- `git status --porcelain` shows ONLY the three expected foreign untracked files (`.claude/`, `KICKOFF_CRITIC_…WS-6c…md`, `REPORT_fhir_agentbench_…md`) — NOT swept into any commit (pathspec-only discipline held). **No intrusion detected.**

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: `created_at` re-stamp on the post-save patch (S-BS-68-adjacent)

- **Spec text (or absence):** the spec/driver are silent on the doc-shim's upsert re-stamping `created_at`. Driver D-C named it as a known risk.
- **Implementation decided:** `_embed_withstands_in_blob` re-inserts the full doc; `collections.py:67/73-74` upsert re-stamps `created_at`. The docstring (`run_eval.py:139-145`) discloses it as "benign here (a 2nd write to the SAME row, same `run` call, ms apart → newest-first ordering unchanged; the provenance's own payload timestamp is preserved)" and explicitly defers the S-BS-68 first-write-wins fix.
- **Alternatives that would also be spec-compliant:** the orchestrator-seam approach (D-C option a) would thread the sink into the provenance build pre-save and avoid the re-stamp entirely.
- **Question for spec author:** is a same-`run` `created_at` re-stamp acceptable for the provenance tier's RLVR/lake semantics, or must first-write-wins be enforced before the blob tier is treated as immutable source-of-truth?
- **Recommended resolution:** accept for this cycle (disclosed, matches the D-C lock-in); fold the first-write-wins fix into the S-BS-68 blob-tier pass.

### Ambiguity 2: GroundingCheck declaration values = flag codes vs contract refs

- **Spec text (or absence):** §2A:63 says "promoted to a config-plane-authored, standalone entity" but does not pin the *declaration unit*.
- **Implementation decided:** `EvalProfile.grounding_checks` is `tuple[str,...]` of **flag codes** matched against `grounded.suppressed[].finding.code` / `floor_blocks` (`grounding_check.py:57-62/86`).
- **Alternatives that would also be spec-compliant:** declaring by `contract_type`/`version`, or by a structured `{code, contract}` ref.
- **Question for spec author:** is "flag code" the right declaration key, or should a GroundingCheck reference the contract (so two checks on the same code can be distinguished)?
- **Recommended resolution:** accept (the light surface, D-D); revisit when the config-plane CRUD UI lands.

**Findings:**

- `[OPEN-QUESTION]` `created_at` re-stamp semantics for the provenance tier (Ambiguity 1).
- `[OPEN-QUESTION]` GroundingCheck declaration unit = flag code (Ambiguity 2).
- `[OPEN-QUESTION]` Cross-locus PresenceCheck disprove asymmetry (carried from §2, behavioral findings).

---

## Independently-verified load-bearing checks (the HARD-GATE crux)

**A4 frozen-seam 0-delta (BLOCKING if non-zero):**
```
git diff 8a159c0..HEAD -- compliance_council.py judges_dspy.py judge_metric.py council_roles/ \
  data/ontology/clinical_v1.json data/config/agents/ws0_default.json | wc -l
→ 0
```
**PASS.** (Note: the session log's A4 evidence cites `git diff acc4973 HEAD`, where `acc4973` is the **UAP-3b** parent — one cycle wider than the UAP-3b-2 parent `8a159c0`. The wc-l is 0 over BOTH ranges, so the claim holds; the citation is merely imprecise. The in-repo guard `test_frozen_seam_zero_delta` also bases on `acc4973` — wider-but-still-0, acceptable.)

**Suites re-run (not trusted from the log):**
- `PYENV_VERSION=debuglithrim pytest tests/ -q` → **282 passed, 0 failed** (matches log; includes the gated S-BS-72 integration).
- default-deps `pytest tests/ -q` → **270 passed, 10 skipped** (matches log).
- `import lithrim_bench` leaks **NONE** of dspy/openai/httpx/fastapi (verified via `sys.modules`).
- `tests/test_uap3b2_provenance.py` → 4 PASS; `tests/test_uap3b2_grounding_check.py` → 5 PASS.
- ruff on all 6 changed files → **All checks passed!**
- Vitest (`apps/shell`) → **45 passed (10 files)** (matches log).

**S-BS-72 above the frozen seam + byte-identical:** **YES.** The patch touches only the persisted blob (`PIPELINE_RUNS.get→insert`), never `result` / `_apply_consensus` / `PipelineProvenance` (all 0-delta); fk preserved by the full-doc re-insert; the test round-trips through the real `grade_inprocess`. The claim is honest.

**A6 additively-identical for `clinical_v1`:** **YES.** `audit_grounding_checks` is a pure reader over `GroundedResult`; `grounding.py`/`report.py` are 0-delta; default-`()` profile emits nothing; the additive-identity test passes. The claim is honest.

**The LIVE-attestation HONESTY (verified from the persisted blob + `/tmp/run{A,B}.json`, not the log):**
- **Run A** (`uap5a_flip_demo`, rid `087a59f8…`, real paid trio): I read `withstands_decisions` straight from `out/config/bench_collections.sqlite` → **all 3 judges `decision=withstand`, `what_failed=[]`** — the log's A1 claim is verbatim-true. Verdict **BLOCK**; `WRONG_DOSAGE` (the genuine by-construction defect) survived → **S-BS-73 holds** (the on-by-default gate ADMITS a legitimate finding; it does not break a true one). Run A is honestly labeled **SAFE-direction (D2 + S-BS-73 validation)** and is NOT misrepresented as "the moat correcting live" — the log explicitly halt-to-surfaces the prize tier. **(a) → YES, honest.**
- **Run B** (`ws0_default`, risk_judge assigned `[MEDICATION_NOT_IN_TRANSCRIPT]`, rid `2275720c…`): I read the council votes + the blob ruling directly → **risk_judge PASS (raised NOTHING)** despite the assignment; faithfulness raised only in-lens `FABRICATED_HISTORY`+`INCOMPLETE_DOCUMENTATION`; gate = all 3 withstand. This is a **GENUINE non-firing**, not a cover: the well-calibrated DSPy trio simply did not over-fire the presence-checkable code, and (per `signals.py:effective_lens` = base+assignments) the assignment puts the code IN-lens so it can't be forced out-of-lens by authoring anyway. The UAP-5a non-convergence lesson recurs exactly as the driver §0 pre-authorized. **(b) → GENUINE halt-to-surface.**
- **S-BS-74 + S-BS-70 disposition:** S-BS-74 ("the authored DSPy trio does not reproduce the prompt-council MED FP → no live validator-disprove correction") is a principled, CONFIRMED-evidence finding (Run B is its proof). Leaving S-BS-70 at "live-corrected-attestation-PENDING" (rather than claiming the moat fully attested) is the correct, honest disposition — the visceral live *correction* is still owed; the offline A2 stands as the mechanism proof and D2 renders the ruling live. **(c) → principled.**
- **Verdict on the live attestation: HONEST.** A manufactured flip would be a FAIL; none was manufactured. PASS-honest (Run A) + HALT-TO-SURFACE (Run B), both verified from disk.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 2 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 1 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 2 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (if any)

No BLOCKING findings.

NON-BLOCKING / OPEN-QUESTION dispositions:

1. **SPEC_UNIFIED §2A impl-note on a locked spec** → accept as-is (disclosed, additive, §13 precedent). Optionally migrate future impl-status to the STREAM file.
2. **BFF 1-line `withstands` projection** → accept (logged A2, ratified in §10).
3. **`created_at` re-stamp (S-BS-68-adjacent)** → fold first-write-wins into the S-BS-68 blob-tier pass.
4. **Cross-locus PresenceCheck disprove asymmetry** → spec-author note (§2A/§13 locus reconciliation); pre-existing, not this cycle.
5. **GroundingCheck declaration unit (flag code)** → revisit at the config-plane CRUD UI follow-on.
6. **S-BS-74** → monitor decides: a dedicated live-correction demo cycle (construct a case the AUTHORED trio genuinely over-fires) vs accept the offline-mechanism + live-safe proof.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec (SPEC_UNIFIED §2A/§2B) + driver BEFORE the executor's session log; read the session log LAST per the task order.
- [x] Read the diff via `git diff 8a159c0..HEAD` against commits; re-ran every load-bearing check (A4 wc-l, all suites, ruff, Vitest, the two live blobs) myself.
- [x] Each finding cites both spec §/file:line and implementation file:line.
- [x] Did NOT edit any code, spec, or driver (only this critique file).
- [x] Did NOT confer with monitor or executor; formed the verdict independently. No paid LLM calls were made.

---

## Appendix: commits audited

```
24318a7 docs(bench-salvage): UAP-3b-2 executor session log (PROCEED-WITH-CAVEATS)
f3f0932 docs(spec): S-BS-72 closed + the GroundingCheck-entity surface + the LLM-critique split (UAP-3b-3 stub)
af584cc test(uap-3b-2): S-BS-72 provenance ruling + GroundingCheck entity + ground() additive-identical + frozen 0-delta
74215bf feat(run-eval): embed the withstands ruling in the run-blob (S-BS-72) + wire the post-consensus GroundingCheck audit
662a1c0 feat(grounding): GroundingChecks as first-class config-authored entities (UAP-3b A6)
```

## Appendix: files changed

```
.devloop/prompts/bench-salvage_phaseUAP-3b-3_llm-ralph-loop-critique_driver.md |  89 ++++++
.devloop/sessions/session-bench-salvage-phaseUAP-3b-2-2026-06-05.json          | 144 +++++++
apps/bff/app.py                                                                |   3 +
docs/specs/SPEC_PRODUCT_SHELL.md                                               |   1 +
docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md                                   |   2 +-
lithrim_bench/harness/config.py                                               |  31 +++-
lithrim_bench/harness/grounding_check.py                                       | 109 ++++++++
scripts/run_eval.py                                                            |  66 +++++-
tests/test_uap3b2_grounding_check.py                                           | 130 ++++++++
tests/test_uap3b2_provenance.py                                               | 188 +++++++++++
10 files changed, 750 insertions(+), 13 deletions(-)
```
