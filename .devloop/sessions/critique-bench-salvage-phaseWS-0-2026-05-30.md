# Spec-Adherence Critique — `bench-salvage` phase `WS-0`

> Inline-mode critique (monitor self-audit), committed alongside close-out as
> `.devloop/sessions/critique-bench-salvage-phaseWS-0-2026-05-30.md`.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-0` (one case end-to-end over live APIs)
- **Driver bundle:** `bench-salvage-phaseWS-0-one-case-over-live-driver`
- **Commits audited:** `9001a36..0859c8d` (6 code/test commits; `9d2b721` = session-log commit, excluded)
- **Spec(s) read against:** `.devloop/prompts/bench-salvage_phaseWS-0_one_case_over_live_driver.md` §2 (deliverables) + §4 (scope) + §5 (acceptance); `.devloop/tasks/TASK_PACK_bench-salvage.json` task WS-0
- **Critique mode:** `inline` (monitor self-audit)
- **Date:** 2026-05-30
- **Reviewer:** monitor session

---

## Verdict

**NON-BLOCKING FINDINGS**

The WS-0 spine matches the driver's design intent: the three load-bearing behaviors (MED-FP suppression via the S-BS-7 presence-check, the versioned RLVR correction record, the S-BS-8 null-code skip-log) each trace spec → test → impl with a closing chain. All surface deviations are additive (extra defaulted kwargs, a realized-as-dict correction schema, a required `expected_block` kwarg on `calibration`) — none renames or breaks a contract, and each is sensible. Four spec-silent judgment calls are surfaced as OPEN-QUESTIONs for WS-1/WS-4, the most material being the calibration "correct" definition, which conflates per-judge votes with a case-level expectation and must be made role-aware *before* calibration becomes a gate in WS-4. Zero blocking drift; the cycle may close.

---

## 1. Surface fidelity

| Spec definition (driver §2) | Implementation | Match? | Severity |
|---|---|---|---|
| §2.1 `grade_live(case, *, env=".live_env")` | [grade.py:50](../../lithrim_bench/harness/grade.py#L50) `grade_live(case, *, env=DEFAULT_ENV, base_url="http://localhost:8002", timeout=180.0)` | + `base_url`, `timeout` (defaulted) | NON-BLOCKING |
| §2.1 `grade_replay(case, baseline_path)` | [grade.py:40](../../lithrim_bench/harness/grade.py#L40) exact | match | — |
| §2.2 `persist(case_id, record) -> None` | [persist.py](../../lithrim_bench/harness/persist.py) `persist(case_id, record, *, out_dir, db_path) -> dict` (+ `load()` helper) | returns `{sqlite,blob}` not `None`; extra `load` | NON-BLOCKING |
| §2.3 `VerificationContract` + `ground(result, case) -> GroundedResult` | [grounding.py:83](../../lithrim_bench/harness/grounding.py#L83) + [:165](../../lithrim_bench/harness/grounding.py#L165) | match (+`version` attr) | — |
| §2.4 `CorrectionRecord` schema + `emit(record)` | [correction.py:33](../../lithrim_bench/harness/correction.py#L33) `build_correction(...) -> dict` + [:83](../../lithrim_bench/harness/correction.py#L83) `emit` | schema realized as a versioned **dict** (`schema_version="ws0-correction/1"`), no class named `CorrectionRecord` | NON-BLOCKING |
| §2.5 `composite(grounded)` | [report.py:22](../../lithrim_bench/harness/report.py#L22) exact | match | — |
| §2.5 `calibration(result)` | [report.py:57](../../lithrim_bench/harness/report.py#L57) `calibration(result, *, expected_block, n_bins=10)` | required `expected_block` kwarg added | NON-BLOCKING |

**Findings:**

- `NON-BLOCKING` `grade_live`/`persist`/`calibration` carry additive kwargs and a richer return shape than the driver's loose signatures. All defaulted-or-justified; tests depend on `persist`'s `{sqlite,blob}` return ([test_ws0.py:121-124](../../tests/test_ws0.py#L113)) and `calibration`'s `expected_block` ([report.py:75](../../lithrim_bench/harness/report.py#L75)). No contract break.
- `NON-BLOCKING` The §2.4 "`CorrectionRecord`" is realized as a versioned dict from `build_correction`, not a named type. The version pin (`schema_version`) preserves the spec intent (a stable, downstream-consumable schema). For WS-1, consider promoting to a dataclass/Pydantic model when the ontology layer formalizes it.

No renames, no error-taxonomy drift, no broken return contract. 11 public symbols; 4 additive deviations, all documented here.

---

## 2. Behavioral fidelity

### Behavior 1: MED FP disproved + suppressed, true defect retained, verdict held

- **Spec assertion:** driver §5 A2 — "The MED FP (`MEDICATION_NOT_IN_TRANSCRIPT`) is disproved+suppressed by the presence-check; `FABRICATED_HISTORY` retained; composite verdict stays BLOCK/reject."
- **Test:** [test_ws0.py:48](../../tests/test_ws0.py#L48) `test_med_fp_suppressed_history_retained` — asserts `suppressed=={MEDICATION_NOT_IN_TRANSCRIPT}`, `matched_token=="zidovudine"`, `FABRICATED_HISTORY` in active, MED absent from active, `grounded.verdict=="BLOCK"`, `composite verdict=="reject"`.
- **Implementation:** [grounding.py:120](../../lithrim_bench/harness/grounding.py#L120) `MedPresenceCheck.check` (token from `active_medications`, span-corroborated) + [:165](../../lithrim_bench/harness/grounding.py#L165) `ground` (suppress + `_rescore`).
- **Chain closes?** **YES.** The test exercises the exact A2 claim; impl matches `zidovudine` from `patient_profile.active_medications`, corroborates against the judge's self-refuting span, suppresses, retains the HIGH `FABRICATED_HISTORY`, re-scores to BLOCK → composite `reject`.

### Behavior 2: versioned, RLVR-ready correction record

- **Spec assertion:** driver §2.4 / §5 A3 — "structured, versioned correction record … {rollout = judge prompt/output/confidence, tool call+result, corrected label, composite before/after, pinned ontology+contract version}."
- **Test:** [test_ws0.py:78](../../tests/test_ws0.py#L78) `test_correction_record_emitted` — one record; `schema_version`, `original_label`, `corrected_label=None`, `composite_before/after`, `ontology_version`, `contract_version`, `rollout` roles `=={policy_judge, faithfulness_judge}` each with confidence+model.
- **Implementation:** [correction.py:33](../../lithrim_bench/harness/correction.py#L33) `build_correction` (rollout filtered by `code in v["findings"]` — verified `findings` is a `list`, so this is true membership) + [:83](../../lithrim_bench/harness/correction.py#L83) append-only `emit`.
- **Chain closes?** **YES.** Rollout preserves each contributing judge's own confidence (raw-events shape — the calibration source and the RLVR substrate). `corrected_label=None` correctly encodes "this flag should not have fired."

### Behavior 3: S-BS-8 null-code findings skip-logged, never dropped

- **Spec assertion:** driver §5 diagnostic — "S-BS-8 null-code findings get skip+logged (surfaced in the report, not silently dropped)."
- **Test:** [test_ws0.py:68](../../tests/test_ws0.py#L68) `test_null_code_findings_skiplogged` — `len(ungrounded)==4`, all `code is None`, and **each is also in `active`**.
- **Implementation:** [grounding.py:184](../../lithrim_bench/harness/grounding.py#L184) — null-code findings appended to both `ungrounded` (reporting view) and `active` (still contributes to the verdict).
- **Chain closes?** **YES.** The "retained in active AND surfaced in ungrounded" invariant is asserted directly — null-code findings can't be silently lost.

All three chains close. No "asserts something nearby" gaps.

---

## 3. Out-of-scope intrusion

Diff (`git diff --stat d302f4c..9d2b721`) = 10 new files (`lithrim_bench/harness/{__init__,grade,persist,grounding,correction,report}.py`, `scripts/run_ws0.py`, `tests/test_ws0.py`, 2 vendored fixtures) + the session log. Cross-checked against driver §4:

- No `../lithrim-backend/` edits (compose-only held).
- No SQLite **config plane** / ontology table — `persist.py` is a doc-shim (`records(case_id PK, json TEXT, created_at)`); the one contract is hardcoded in `WS0_CONTRACTS` ([grounding.py:153](../../lithrim_bench/harness/grounding.py#L153)). WS-1 boundary held.
- No mid-loop / JUTE / pinecone grounding (WS-3 boundary held).
- Calibration is report-only ([report.py:57](../../lithrim_bench/harness/report.py#L57) returns a dict, never raises/gates) — WS-4 boundary held.
- No drive-by formatting: the repo-wide ruff debt (433 errors) is in files this cycle did not author; the 10 new files are ruff-clean.
- The additive helpers (`load`, `grade_live` `base_url`/`timeout`) live inside their own deliverable's module — not cross-cutting intrusion.

**No intrusion detected.**

---

## 4. Spec ambiguity surfaced (OPEN-QUESTIONs)

1. **`OPEN-QUESTION` — calibration "correct" definition conflates per-judge vote with a case-level expectation.** [report.py:75](../../lithrim_bench/harness/report.py#L75) computes `correct = (vote=="BLOCK") == expected_block` for **every** judge against the **single case-level** `expected_block`. So `risk_judge`'s confident PASS ("no HIPAA violations") is scored "incorrect" against a compliance-level expectation, even though a role-scoped PASS may be correct for that judge. Report-only here (harmless, small-N caveated). **But when calibration becomes a GATE in WS-4, the "correct" predicate must be role-aware or measured against the composite verdict, not per-judge vote vs case label** — otherwise a well-calibrated role-specialized council fails the gate for the wrong reason. Surface to the WS-4 spec author.

2. **`OPEN-QUESTION` — the severity→verdict re-score thresholds are a silent choice.** The driver said "re-score" without a mapping; [grounding.py:156](../../lithrim_bench/harness/grounding.py#L156) `_rescore` uses `weight>=0.5 → BLOCK` (HIGH=1.0, MEDIUM=0.5, LOW=0.2), so a lone MEDIUM finding blocks. This matches the live "worst-of" disposition but should be ratified — is MEDIUM-alone→BLOCK the intended harness composition, or should it be WARN? Lock in WS-1/WS-4.

3. **`OPEN-QUESTION` — med-name extraction algorithm is impl-defined.** The driver said "extract the med name from the finding/transcript"; [grounding.py:94](../../lithrim_bench/harness/grounding.py#L94) `_med_tokens` chose `active_medications` as the authoritative source + dosage/form/noise stripping + `len>=4` token floor. Conservative (never suppress on failed extraction) and correct for this case, but the heuristic is invisible to the spec. When this becomes an ontology verification_contract in WS-1, the extraction strategy should be an explicit, testable part of the contract definition (e.g., what happens with a 3-letter drug name, or a brand/generic mismatch).

4. **`OPEN-QUESTION` — reinforces S-BS-9 (already logged).** The `expected_compliance_verdict` shape divergence (string `'reject'` in `scribe_v1.jsonl` vs list `['needs_review','reject']` in `.n10.jsonl` for the same `case_id`) was worked around via source-pinning + shape-tolerance. The pack-shape inconsistency itself is for WS-1 pack hygiene to normalize; flagged here so the spec author treats it as a data-contract item, not just a runner workaround.

---

## Discipline self-check

- [ ] **Read the spec without reading the session log first** — **NOT fully met (known inline-mode limitation).** This critique ran in the same monitor session that performed the immediately-prior `/devloop-audit`, which read the session log. Inline mode forfeits the strict no-prior-context property (per CRITIC persona §"When the critic is triggered"). **Mitigation / evidence of genuine independent read:** the Q1/Q2/Q4 findings were derived by reading the implementation + driver directly, and this pass surfaced two findings **absent from the executor's session log** — the calibration role-conflation (Q4.1) and the `_rescore` threshold ambiguity (Q4.2) — which is the load-bearing signal that the critique did not merely ratify the log's self-report. WS-0 is a routine cycle (no spec/API-contract/launch touched), so inline mode is the sanctioned path; a fresh-critic session was not required.
- [x] **Each finding cites spec file:line AND impl file:line.**
- [x] **No code/spec/driver edits made during this pass.**

---

## Findings summary

| Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|
| 1 Surface fidelity | 0 | 2 | 0 |
| 2 Behavioral fidelity | 0 | 0 | 0 |
| 3 Out-of-scope intrusion | 0 | 0 | 0 |
| 4 Spec ambiguity surfaced | 0 | 0 | 4 |

**Verdict: NON-BLOCKING FINDINGS.** Cycle may proceed to `/devloop-close-phase`. Carry Q4.1 (calibration role-conflation) into the WS-4 calibration-gate spec and Q4.2/Q4.3 into the WS-1 ontology/contract spec; Q4.4 reinforces the already-logged S-BS-9.
