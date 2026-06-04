# Spec-Adherence Critique — `bench-salvage` phase `UAP-3`

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `UAP-3` (processing surface + run-history + the authored→flip wiring, R4+R6 / S-BS-63)
- **Driver bundle:** `bench-salvage-phaseUAP-3-processing-run-history-driver` (v1)
- **Commits audited:** `5959e28 812fade ddf32db 20ca6b9 b678be3 2a49411 8088d88 b3079d2` (range `82f822a..HEAD`)
- **Spec(s) read against:** `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` (§2A/§2B, §3.3 Stage-3, §4 BFF surface + gen-UI registry, §5 R4/R6, §6 invariants, §12 decisions, §13) · `docs/specs/SPEC_PRODUCT_SHELL.md` §10 (the ratified v1 BFF surface)
- **Critique mode:** `fresh-critic` (separate session)
- **Date:** 2026-06-04
- **Reviewer:** critic session (cold read; spec + diff before session log)

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The authored→flip wiring (S-BS-63) closes correctly and is proven causally — assigning a flag to a judge is what moves the verdict, the marker reaches the judge's prompt, and the other roles do not move; the frozen consensus seam is byte-0-delta; run-provenance persists on all three grade paths and round-trips; the new BFF surface is ratified in §10. Two additive surface deviations (an extra `verdict_flipped_by_stage` field on the `/v1/runs` row, and the grade seam landing as the pre-existing `semantic_stage=` rather than a `grade_inprocess(assignments=)` signature) are NON-BLOCKING and plan-reviewed/§10-adjacent. One real, already-tracked OPEN-QUESTION: authored in_process votes carry an empty per-judge `reason` in the audit/JudgeTab view (S-BS-66), inherited from the pre-existing DSPy seam — surface for the spec author against §2B `why.reasoning`.

---

## 1. Surface fidelity

> Does the public API match the spec/§10-ratified surface exactly?

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| SHELL §10:147 `GET /v1/runs?limit=` | `apps/bff/app.py:699` `list_runs_endpoint(limit: int = Query(50, ge=1, le=500))` | exact | — |
| SHELL §10:147 row `{run_id, verdict, gate_decision, agent, ts}` | `apps/bff/app.py:689` `_run_summary` → `{run_id, verdict, gate_decision, verdict_flipped_by_stage, agent, ts}` | **extra field** `verdict_flipped_by_stage` | NON-BLOCKING |
| SHELL §10:147 every `run_id` round-trips to `GET /v1/runs/{id}/audit` | `_run_summary.run_id = doc["pipeline_run_id"]`; `get_run_audit_endpoint` does `PIPELINE_RUNS.get(run_id)`; `PIPELINE_RUNS.id_field="pipeline_run_id"` (`collections.py:150`) | exact | — |
| SHELL §10:147 `POST /v1/eval-pack/run {pack_id, agents[], live?}` | `apps/bff/app.py:344` `EvalPackRunRequest{pack_id, agents=[DEFAULT_AGENT], live=False}` + `eval_pack_run_endpoint` | exact | — |
| SHELL §10:147 eval-pack returns "the frozen pack + the run ids", replay/live only | `app.py:377` returns `{"pack": pack, "run_ids": [...]}`; `evalpack.build_pack` carries no `in_process` (`evalpack.py:88`) | exact | — |
| SHELL §10:147 `POST /v1/run-eval` surfaces `pipeline_run_id` (S-BS-56) | `app.py:271` `record["pipeline_run_id"] = _pipeline_run_id(record)` reading `result.provenance.pipeline_run_id` | exact | — |
| SHELL §10:147 provenance persisted for **all three** paths (S-BS-52) | in_process via `SqliteProvenanceStore(db_path=collections_db)` (`run_eval.py:193`); replay+live via `_persist_run_provenance` (`run_eval.py:219`, the `if grade_path != "in_process"` block) | exact | — |
| SHELL §10:147 in-process grade built with authored judge assignments (S-BS-63); live `:8002` injection WS-2-gated | `run_eval.py:185-198` builds `build_authored_semantic_stage` on the in_process branch ONLY; live branch threads no assignments | exact | — |
| SPEC §4:192 / §4:186 gen-UI registry + `RunPanel` | `registry.js:31` `KNOWN_TOOLS` adds `"tool-run_panel"` (8→9); `RunPanel.jsx:166` `registerTool("tool-run_panel", RunPanel)` | exact | — |
| Driver A-2 `grade_inprocess(..., assignments=)` [seam option] | NO `grade.py` change; assignments → `build_authored_semantic_stage` → existing `semantic_stage=` param (`grade.py:133`, unchanged) | **seam (i), not the literal driver file** | NON-BLOCKING |
| Question-prompt surface `run_eval.run(..., assignments=, collections_db=)` | `run_eval.py:124-131` `run(agent, *, live, in_process, out_dir, ontology_path, assignments, collections_db)` | exact | — |
| Question-prompt surface `build_pack(..., collections_db=)` | `evalpack.py:91` `build_pack(pack_id, agents, *, live, out_dir, collections_db)` | exact | — |
| `bff.js` `getRuns()` | `bff.js:30` `getRuns(limit=50)` → `GET /v1/runs?limit=` | exact | — |

**Findings:**

- `[NON-BLOCKING]` **`/v1/runs` row carries an extra `verdict_flipped_by_stage` field beyond the ratified §10 shape.** SHELL `§10:147` locks the row as `{run_id, verdict, gate_decision, agent, ts}` (5 fields); `apps/bff/app.py:689-697` `_run_summary` emits 6 (adds `verdict_flipped_by_stage`). Additive, harmless, and arguably more useful — but it is unratified against the same §10 edit (`8088d88`) the executor wrote, i.e. the shipped surface is wider than the surface they locked. Not consumed by the RunPanel UI or any §10-named consumer (`grep` of `apps/shell/src` + `tests/` finds it only in a `test_ws5_bff.py:427` fixture). Disposition: either drop the field or widen the §10 row line to 6 fields in a doc touch.
- `[NON-BLOCKING]` **The S-BS-63 grade seam landed as the pre-existing `semantic_stage=` param, not a new `grade_inprocess(assignments=)` signature.** Driver `§2 A-2` named `grade.py` and offered seam (i) [inject a `build_trio`-backed `semantic_stage`] vs (ii) [orchestrator reads assignments] as a plan-review decision. The impl picked seam (i): `grade.py` is **byte-untouched** (`git diff 82f822a..HEAD -- grade.py` = 0); the authored trio is assembled in `run_eval.py:189` and injected via the existing `semantic_stage=`. This is the more conservative choice (no edit adjacent to the frozen seam) and is spec-faithful — SPEC `§3.1.2 NET-NEW.3` and `§5 R4` mandate the behavior, not a `grade_inprocess(assignments=)` symbol. Recorded as a deviation-from-driver-literal that is a documented plan-review decision (session log `plan_review.deviations[0]`), not drift.

All other public symbols (`GET /v1/runs`, `POST /v1/eval-pack/run`, `pipeline_run_id`, `tool-run_panel`, `run_eval.run(assignments=, collections_db=)`, `build_pack(collections_db=)`, `getRuns()`) match the §10-ratified / question-prompt surface exactly.

---

## 2. Behavioral fidelity

### Behavior 1: the authored→flip — assigning a flag changes the in-process verdict, caused by the authoring not the case (MANDATORY pick (a))

- **Spec assertion:** SPEC `§5 R4` + the locked Decision 1 (`§12.1`): "A judge's refinement questions are *formed by assigning ontology flags to it*; the runtime prompt renders from the assignment." SHELL `§10:147`: "an authored judge re-votes with its authored lens." Acceptance `A1`: "the council votes reflect the authored lens (a verdict/finding change vs the default-config grade)."
- **Test:** `tests/test_uap3_grade.py:80` `test_authored_assignment_flips_the_in_process_verdict`. Unassigned stage (`assignments=None`) → `comp0["verdict"] != "reject"` AND every vote `!= "BLOCK"` (line 93-94). Assigned stage (`{"risk_judge": ["WRONG_DOSAGE"]}`) → `comp1["verdict"] == "reject"` (line 105), risk_judge `BLOCK` with `WRONG_DOSAGE` in findings (line 107-109), and **the other roles do not BLOCK** (line 110-112). Plus `tests/test_uap3_bff.py:150` proves the BFF threads the captured `assignments` kwarg.
- **Implementation:** `authored_stage.py:71-73` `build_trio(ontology=, assignments=, predictors=)` → each judge's `role_prompt = render_role_questions(ontology, role, assigned_flags=assigned)` (`judges_dspy.py:331`); the marker `"=== AUTHORED REFINEMENT (ontology assignment) ==="` is appended **only** when `assigned_flags` is truthy (`judge_assignment.py:72-73, 83-89`); `Judge.forward` feeds `role_key_questions=self.role_prompt` to the predictor (`judges_dspy.py:278`).
- **Chain closes?** **YES.** The test's injected predictor BLOCKs iff the marker is in `role_key_questions`; the marker is in the prompt iff an assignment is present; `build_trio` binds the assignment-rendered prompt as the judge's `role_prompt`; `Judge.forward` feeds that to the predictor. So the verdict flip is causally bound to the authoring reaching the judge's prompt — not to the case. The "other roles don't move" assertion (line 110-112) and the unassigned all-approve assertion (line 94) directly rule out the trivial-pass. **This is NOT a trivially-passing test.**
- **Note on the A4 parity scope:** the "unassigned grades byte-equivalently to the default lens" property is established at the **prompt-render** level — `judge_assignment.py:59` states the parity contract (`render_role_questions(ont, role)` is byte-equal to `load_role_prompt(role)` = the committed `council_roles/<role>.txt`), and the test asserts `cap["policy_judge"] == render_role_questions(ont, "policy_judge")` (`test_uap3_grade.py:134`). It is NOT separately asserted by running the legacy default-config council path (`grade_inprocess` with no `semantic_stage`) and diffing the grade. The render-level parity is the load-bearing one (the seam IS the prompt; the consensus math below is byte-frozen), so this is acceptable and arguably stronger (it pins exact text). Recorded as a precise scoping, not a finding.

### Behavior 2: run-history round-trip — a persisted run_id from `GET /v1/runs` resolves at `GET /v1/runs/{id}/audit` (MANDATORY pick (b))

- **Spec assertion:** SHELL `§10:147`: "`GET /v1/runs?limit=` … every `run_id` round-trips to `GET /v1/runs/{id}/audit`." Acceptance `A3`: "a listed `run_id` round-trips to `GET /v1/runs/{id}/audit` (no 404 for a persisted run)."
- **Test:** `tests/test_uap3_bff.py:105` `test_run_id_round_trips_to_audit` — posts `/v1/run-eval`, takes `pipeline_run_id` from the response, `GET /v1/runs/{rid}/audit` → 200, `body["run_id"] == rid`, `verdict == "BLOCK"`, `judges` is a list. Plus `test_runs_lists_the_persisted_replay_run:92` (empty → 1 row, `row["run_id"] == BASELINE_RUN_ID`) and `test_replay_run_id_is_idempotent_in_history:117` (3 runs → exactly 1 row).
- **Implementation:** persist keyed by `pipeline_run_id` (`run_eval.py:104-119` `_persist_run_provenance` → `PIPELINE_RUNS.insert`, `id_field="pipeline_run_id"`); list projects `run_id = doc["pipeline_run_id"]` (`app.py:692`); audit resolves `PIPELINE_RUNS.get(run_id)` (`app.py:730`). `insert` is `ON CONFLICT(id) DO UPDATE` (`collections.py:71-74`) — a genuine upsert.
- **Chain closes?** **YES.** The id the list emits is the same key the audit endpoint looks up; the upsert guarantees a persisted run is always retrievable; the idempotency test confirms a fixed-id replay yields one row, not a growing duplicate set. The 404 is correctly narrowed to "unknown / never-run id" (`app.py:732-735`; the stale "replay runs are not audited" copy was retired in `ddf32db`, with `test_ws5_bff.py:466` updated to assert `"not found"`).

### Behavior 3: the frozen-seam invariant (MANDATORY pick (c))

- **Spec assertion:** SPEC `§6:223`: "Frozen consensus seam. Authoring lives strictly ABOVE the per-judge seam; `compliance_council._apply_consensus` stays byte-frozen (the whole DSPy track's A1)." SPEC `§2A:73-74`: "All of this lives above the frozen consensus seam … the NET-NEW is the orchestration." Acceptance `A2`: `git diff` over `compliance_council.py` (esp. `_apply_consensus`) + the per-judge seam dict = 0 lines.
- **Test:** acceptance check (not a pytest) — `git diff 82f822a..HEAD -- compliance_council.py judges_dspy.py judge_metric.py clinical_v1.json data/config/agents council_roles | wc -l`.
- **Implementation:** `authored_stage.py:64` `consensus = council._apply_consensus(results, gate_mode=gate_mode)` — only **CALLS** it; reuses `run_semantic(request, council_evaluate=_evaluator)` (`authored_stage.py:67-69`) for the consensus→StageResult mapping, so no orchestrator edit.
- **Chain closes?** **YES — independently re-run by this critic: result = 0 lines.** Additionally confirmed `lithrim_bench/runtime/pipeline/stages.py` and `orchestrator.py` are untouched (`git diff --name-only` empty), and the ONLY file changed under `runtime/council/` + `runtime/pipeline/` is the new `authored_stage.py`. `authored_stage.py` adds no orchestrator/`stages.py` edit and only calls `_apply_consensus`. The per-judge seam dict shape (`{model, decision, confidence, findings, errors}`, `judges_dspy.py:286-292`) is byte-shape-identical to the prompt-council `models` rows, so `_run_council_and_map` maps it unchanged. The A1/A2 invariant holds exactly as the spec requires.

**Findings:**

- No behavioral drift. All three mandatory chains close. The authored→flip is causally tied to the authoring (not the case), the run-history round-trip resolves by construction, and the frozen seam is byte-0-delta (critic-re-run).

---

## 3. Out-of-scope intrusion

> The diff against the driver §2 deliverables list + the NOT-in-scope list + the frozen-seam check.

Driver §2 deliverables (verbatim, abbreviated): **A** S-BS-63 assignments threading (`run_eval.py`, `grade.py`, `app.py`); **B** run ids + history + replay-provenance (`app.py`, `run_eval.py`, `grade.py`); **C** eval-pack batch (`app.py` over `evalpack.build_pack`); **D** RunPanel UI (`RunPanel.jsx`, `registry.js`, `panes.jsx`, `bff.js`); **E** tests (`tests/test_uap3_*.py`, `RunPanel.test.jsx`); **F** docs (`SPEC_PRODUCT_SHELL.md §10`).

`git diff --stat 82f822a..HEAD` — 18 files:

```
.devloop/sessions/session-bench-salvage-phaseUAP-3-2026-06-04.json | 187   (E/F — session log; docs-only)
apps/bff/app.py                                    |  99   (A/B/C deliverables)
apps/shell/src/bff.js                              |  15   (D deliverable)
apps/shell/src/bff.test.jsx                        |   2   (coupled: runEval body +in_process)
apps/shell/src/genui/RunPanel.jsx                  | 167   (D deliverable, new)
apps/shell/src/genui/RunPanel.test.jsx             |  84   (E deliverable, new)
apps/shell/src/genui/index.js                      |   2   (D materialization — barrel import for registration)
apps/shell/src/genui/registry.js                   |   4   (D deliverable)
apps/shell/src/genui/registry.test.jsx             |   9   (coupled: KNOWN_TOOLS 8→9)
apps/shell/src/panes.jsx                           |   1   (D deliverable — CenterPane mount)
docs/specs/SPEC_PRODUCT_SHELL.md                   |   1   (F deliverable — §10 ratify)
lithrim_bench/harness/collections.py               |  23   (B materialization — list_all backs GET /v1/runs)
lithrim_bench/harness/evalpack.py                  |  14   (C materialization — build_pack collections_db + run_id)
lithrim_bench/runtime/council/authored_stage.py    |  97   (A materialization — the seam-(i) stage builder, new)
scripts/run_eval.py                                |  85   (A/B deliverables)
tests/test_uap3_bff.py                             | 179   (E deliverable, new)
tests/test_uap3_grade.py                           | 134   (E deliverable, new)
tests/test_ws5_bff.py                              |   6   (coupled: 404-copy change)
```

**Frozen-seam check (MANDATORY, critic-re-run):** `git diff 82f822a..HEAD -- compliance_council.py judges_dspy.py judge_metric.py clinical_v1.json data/config/agents council_roles | wc -l` → **0**. PASS.

**`authored_stage.py` discipline (MANDATORY):** only **CALLS** `_apply_consensus` (`authored_stage.py:64`); adds **no** orchestrator / `stages.py` edit (`git diff --name-only` of both = empty). Confirmed.

**NOT-in-scope list — independently verified absent:**
- Withstands-gate / GroundingChecks / Ralph-Loop critique (UAP-3b): no `harness/grounding.py` change in the diff; `authored_stage.py` adds no signals bus. **Absent.**
- Optimize / calibration in-UI (R5/UAP-4): no `judge_optimize` touch; no `POST /v1/judges/{role}/optimize` route. **Absent.**
- Floor/KB ship from a committed ontology (S-BS-13/16/41): clinical_v1.json byte-0-delta; no floor wired. **Absent.**
- Authoring-assist describe→card (UAP-5a/R10): no LLM-draft path; no `POST /v1/author/{kind}`. **Absent.**
- JudgeEditor shell mount (S-BS-62): `panes.jsx` adds only `tool-run_panel`, not `tool-judge_editor`. **Absent.**
- Re-snapshotting ontology `owner_roles` (S-BS-59): no taxonomy/ontology owner edit. **Absent.**

**Findings:**

- `[NON-BLOCKING]` **Three files are materializations of named deliverables rather than literal driver file-names**, all in-scope: `authored_stage.py:1` (the seam-(i) stage builder — materializes driver A-2 "council-CONSTRUCTION above the frozen seam"; the cleaner alternative to editing `grade.py`); `collections.py:81` `DocShimCollection.list_all` (materializes driver B-4 "list persisted runs from … `PIPELINE_RUNS`" — keeps the SQL out of the BFF); `genui/index.js:12,24` barrel import/export of `RunPanel` (materializes driver D-7 "register `tool-run_panel`" — the side-effect import is how registration happens). Each is the minimal substrate for a named deliverable, not a drive-by. The executor pre-declared these in plan-review (`session log plan_review.deviations[6]`) so the critic would not read them as intrusion; this critic concurs on the merits.
- `[NON-BLOCKING]` **Three coupled EXISTING test files updated to track behavior changes** (the kickoff-flagged set): `test_ws5_bff.py:466` (404 copy `"replay"`→`"not found"`, tracking the retired copy in `ddf32db`); `registry.test.jsx` (`KNOWN_TOOLS` 8→9, the registry count); `bff.test.jsx:40` (the `runEval` body gains `in_process: false`, tracking the `bff.js` signature). All three are faithful assertion-updates that follow their source edits — not new scope. (`session log plan_review.deviations[5]`.)
- `[NON-BLOCKING]` **The RunPanel is mounted inside the frozen journey's center-pane flow** (`panes.jsx:172`, `renderTool({type:"tool-run_panel", ...})` injected into the "Everything checks out… Running all 2,400" message block). SPEC `§8:243` lists "Journey rework" as a non-goal. The mount is a single additive line that renders the new processing tool (the R4 deliverable D-8 explicitly requires mounting `tool-run_panel` in `CenterPane`), not a rework of the journey script/copy/flow. In-scope, but noted because the chosen mount point is the journey surface; a more neutral mount (a dedicated processing view) may be preferable as the shell grows. Disposition: accept; revisit at shell-IA pass.

No intrusion that exceeds the driver's deliverables. All 18 files map to a deliverable, a deliverable's materialization, or a coupled assertion-update.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: S-BS-63 closed for in_process-only — the live `:8002` assignment-injection narrowing

- **Spec text:** SHELL `§10:147` (ratified this cycle): "The in-process grade is built with the agent's **authored judge assignments** (S-BS-63) … (live `:8002` per-judge assignment-injection stays WS-2-backend-gated)." Driver `§2 A-1` had said thread into "the in_process **(and live)** grade."
- **Implementation decided:** `run_eval.py:185-198` builds `build_authored_semantic_stage` on the in_process branch ONLY; the live branch (`run_eval.py:200-211`) threads no assignments. The docstring (`run_eval.py:147-150`) states the live narrowing explicitly.
- **Alternatives that would also be spec-compliant:** thread assignments into `grade_live` too (would require the WS-2 backend per-judge injection, which is HARD-GATE-paused).
- **Question for spec author:** is S-BS-63 legitimately *closed* (not merely deferred) when only the in_process path re-votes with the authored lens? The driver said "(and live)"; the ratified §10 + the executor narrowed live OUT and opened **S-BS-64** for it.
- **Recommended resolution:** **accept** — the narrowing is ratified into SHELL §10 (the authoritative surface) and is consistent with SPEC `§8:245` (no new backend endpoints; compose over `:8002`/`:3031`). The live leg is correctly a *tracked open seam* (S-BS-64), not a silent gap. This is a legitimate close-for-in_process with the live half explicitly seamed.

### Ambiguity 2: replay-provenance idempotency on a fixed `pipeline_run_id`

- **Spec text (absence):** SPEC `§2B:115` requires audit records be "immutable + append-only"; SHELL `§10:147` says replay "appears in run-history and is auditable" but is silent on what happens when the **same** deterministic replay is re-run (the baseline carries a fixed `pipeline_run_id`).
- **Implementation decided:** `run_eval.py:104-119` `_persist_run_provenance` upserts on `pipeline_run_id` (via `collections.py:71-74` `ON CONFLICT(id) DO UPDATE`); deterministic replay reuses the baseline's fixed id, so re-running yields ONE row per baseline (`test_uap3_bff.py:117` proves it). Note: the upsert sets `created_at=excluded.created_at`, so a re-run also **re-stamps** `created_at`, moving the row to the top of the newest-first list.
- **Alternatives that would also be spec-compliant:** append-per-invocation (a fresh surrogate run id each replay → an append-only history of identical runs); or keying on a content hash + invocation timestamp.
- **Question for spec author:** is "one immutable row per deterministic replay baseline" the intended audit semantics, or should each invocation be an append-only event (even for byte-identical replays)? The `§2B:115` "append-only" language and the upsert-overwrite are in mild tension for the replay case (re-running mutates `created_at` of an existing row rather than appending).
- **Recommended resolution:** **accept for run-history** (the projection/index tier — one row per addressable run is the natural shape and matches `persistence-blob-projection-architecture`); flag for the spec author whether the *immutable blob/event* tier (the RLVR substrate) should instead append-per-invocation. Low-stakes for replay (byte-identical), but worth an explicit line in §2B so the contract is locked. (Matches the executor's stated "by design" disposition, `session log diagnostic_stats.run_history_replay_rows`.)

### Ambiguity 3: authored in_process per-judge `reason`/`model` in the realized council view

- **Spec text:** SPEC `§2B:99`: "**judge raise** → `{ taxonomy_code, decision, reasoning, evidence_spans[], confidence|null }` (the per-judge seam — already emitted)." The audit report is to answer "why" per-judge.
- **Implementation decided:** on the authored path, `_run_audit_report` (`app.py:701`) and `_council_view` (`app.py:285`) project `reason = v.get("reason")`; `_judge_votes_from_models` builds `reason = m.get("summary") or m.get("rationale") or ""` (`stages.py:599`). The DSPy `Judge.forward` seam dict (`judges_dspy.py:286-292`) carries neither `summary` nor `rationale`, so authored in_process votes get `reason = ""`. The injected-evaluator branch also sets `_model_lookup = {}` (`stages.py:747`, per the session log), so `model` is the role name rather than a deployment id.
- **Alternatives that would also be spec-compliant:** have the DSPy `Judge.forward` emit a `summary`/`rationale` (out of scope this cycle — `judges_dspy.py` is frozen); or have `authored_stage`'s `_evaluator` populate a reason from the DSPy rationale field.
- **Question for spec author:** does the §2B per-judge `why.reasoning` requirement need to hold on the in_process / authored-DSPy path, or is votes+findings+confidence sufficient there (reasoning being a prompt-council-only enrichment)?
- **Recommended resolution:** **accept as a tracked OPEN-QUESTION**, NOT a regression of this cycle. This is a **pre-existing property of the DSPy in_process arm** (the seam dict has carried no `summary`/`rationale` since before UAP-3; `judges_dspy.py` is byte-0-delta here). The authored stage *inherits* it by reusing `Judge.forward` exactly; it does not *cause* it. The executor self-reported it as **S-BS-66** (CONFIRMED) with the same evidence this critic derived independently. The default prompt-council path is unaffected (its `models` rows carry a rationale, e.g. the fixture baseline's `risk_judge.reason` is fully populated). Surface to the spec author so the §2B `why.reasoning` contract is explicit for the DSPy path; address in UAP-3b or a `judges_dspy` enrichment cycle, not here.

**Findings:**

- `[OPEN-QUESTION]` S-BS-63 closed for in_process-only with the live leg seamed as S-BS-64 — confirm the close semantics (recommend accept; it is ratified in §10 and the live half is tracked, not silent).
- `[OPEN-QUESTION]` Replay-provenance upserts one row per fixed baseline id (and re-stamps `created_at`) — confirm this against the §2B "append-only" language for the immutable/RLVR tier (recommend accept for the run-history projection; lock the blob-tier semantics in §2B).
- `[OPEN-QUESTION]` Authored in_process votes carry an empty per-judge `reason` (and a role-name `model`) in the §2B audit/JudgeTab view (S-BS-66) — a pre-existing DSPy-seam property inherited, not caused, by this cycle; confirm whether §2B `why.reasoning` must hold on the DSPy path.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 2 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 3 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 3 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (if any)

No BLOCKING findings — no required corrections to close.

NON-BLOCKING / OPEN-QUESTION dispositions (none gate closure):

1. **Finding (Q1):** `/v1/runs` row carries extra `verdict_flipped_by_stage` beyond the §10 row shape.
   **Proposed disposition:** widen the SHELL `§10:147` row line to 6 fields in a doc touch, OR drop the field from `_run_summary`. Log as a seam if not done in close-out. (Spec author / monitor; trivial.)
2. **Finding (Q1):** grade seam landed as `semantic_stage=` (no `grade_inprocess(assignments=)`).
   **Proposed disposition:** accept as-is — documented plan-review Decision 1 (seam (i)); the conservative, frozen-seam-respecting choice. No action.
3. **Finding (Q3):** three deliverable materializations + three coupled test updates.
   **Proposed disposition:** accept as-is — all in-scope, pre-declared in plan-review, faithful. No action.
4. **Finding (Q3):** RunPanel mounted in the frozen-journey center-pane flow.
   **Proposed disposition:** accept; revisit the mount point at a shell-IA pass as the processing surface matures. No action this cycle.
5. **Finding (Q4):** S-BS-63 in_process-only close (S-BS-64 live), replay idempotency vs §2B append-only, authored-path empty `reason` (S-BS-66).
   **Proposed disposition:** spec author confirms the three semantics; S-BS-64/S-BS-66 already opened and tracked. The A8 `:5180` visual smoke (incl. the real paid in_process authored-flip) remains **OWED** at close — flagged by the executor, not a critique finding (mechanical-audit territory), but the monitor should ensure it lands before declaring the visceral authored-flip demonstrable.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec without reading executor's session log first (spec + driver + full diff + tests read; session log read LAST, as cross-check only)
- [x] Read the diff via `git show` against each of the 8 commits, not via the executor's summary
- [x] Each finding cites both spec file:line and implementation file:line
- [x] Did NOT edit any code, spec, or driver (only this critique .md written)
- [x] Did NOT confer with monitor or executor before writing the verdict
- [x] Re-ran the load-bearing checks independently: frozen-seam `wc -l` = 0; `stages.py`/`orchestrator.py`/`compliance_council.py` untouched; `authored_stage.py` module-level imports = stdlib-only; UAP-3 pytest 9 passed (debuglithrim); Vitest 23 passed

Cross-check note: my independent Q4 finding on the empty authored-path `reason`/`model` matches the executor's self-reported **S-BS-66** (same evidence, `stages.py:747` + the DSPy forward seam). The session log's PROCEED-WITH-CAVEATS self-assessment is consistent with this critique; no contradiction surfaced between the executor's claims and the cold read.

---

## Appendix: commits audited

```
b3079d2 docs(bench-salvage): session log for UAP-3 (processing + run-history + authored→flip)
8088d88 docs(spec): ratify /v1/runs + /v1/eval-pack/run in SHELL §10 (S-BS-51)
2a49411 test(uap-3): authored→flip + run-history + eval-pack + RunPanel
b678be3 feat(shell): RunPanel gen-UI (tool-run_panel) + run-history (R4)
20ca6b9 feat(bff): POST /v1/eval-pack/run batch processing (R6)
ddf32db feat(harness): persist replay + live provenance for auditability (S-BS-52)
812fade feat(bff): surface pipeline_run_id + GET /v1/runs run-history (S-BS-56)
5959e28 feat(harness): thread authored judge assignments into the in-process grade (S-BS-63)
```

## Appendix: files changed

```
.devloop/sessions/session-bench-salvage-phaseUAP-3-2026-06-04.json | 187 +++++
apps/bff/app.py                                    |  99 ++++++++++-
apps/shell/src/bff.js                              |  15 +-
apps/shell/src/bff.test.jsx                        |   2 +-
apps/shell/src/genui/RunPanel.jsx                  | 167 ++++++++++++++++++
apps/shell/src/genui/RunPanel.test.jsx             |  84 +++++++++
apps/shell/src/genui/index.js                      |   2 +
apps/shell/src/genui/registry.js                   |   4 +-
apps/shell/src/genui/registry.test.jsx             |   9 +-
apps/shell/src/panes.jsx                           |   1 +
docs/specs/SPEC_PRODUCT_SHELL.md                   |   1 +
lithrim_bench/harness/collections.py               |  23 +++
lithrim_bench/harness/evalpack.py                  |  14 +-
lithrim_bench/runtime/council/authored_stage.py    |  97 +++++++++++
scripts/run_eval.py                                |  85 +++++++++-
tests/test_uap3_bff.py                             | 179 ++++++++++++++++++++
tests/test_uap3_grade.py                           | 134 ++++++++++++++
tests/test_ws5_bff.py                              |   6 +-
18 files changed, 1086 insertions(+), 23 deletions(-)
```
