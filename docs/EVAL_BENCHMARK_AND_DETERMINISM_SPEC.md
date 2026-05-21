# Eval Benchmark Fix + Determinism Protocol + Case Generation/Calibration Spec

**Date:** 2026-05-19
**Status:** draft for execution
**Scope:** make the eval trustworthy before any accuracy or worst-of claim is measured or published.

This spec is grounded in concrete defects found in the 2026-05-19 audit, not a generic plan. Each part cites the defect it closes.

## Defect register (what this spec fixes)

- **D1 mislabeled golden.** `demo_dataset/eval_golden.jsonl:58` expects `VALUE_MISMATCH`, a code not in `KNOWN_TAXONOMY_CODES` (`compliance_council.py:223`). The case can never match that flag. Class: golden labels reference codes the system cannot emit.
- **D2 verdict bistability.** `gold_data_integrity_doh_hba1c_value_mismatch_viol` at N=3 = 2 BLOCK / 1 WARN. Root cause: decisions are unanimous reject, but code-attribution is stochastic (judge sometimes attaches a code+evidence, sometimes bare reject); the aggregator routes those differently. Variance lives at the code-attribution layer, not the decision layer.
- **D3 declarative vs operational drift.** `_TIER1_OWNERS` (`compliance_council.py:187-194`) lists `source_message_judge` as co-owner of `WRONG_DOSAGE` / `MISSING_ALLERGY` / `FABRICATED_CONSENT`, but production runs only `["policy_judge","risk_judge","behavior_judge"]`. Ownership routing references a judge that does not run.
- **D4 silent partial coverage + empty rollup.** MPRS baseline runs (2026-05-04) submitted 8–17 cases against 14–23 expected; `result_summary` is `{}` in the run JSONs. The runner under-submits silently and computes no pack-level metric.
- **D5 model drift.** Reports span gpt-4o (2026-04-02), gpt-4.1 / gpt-4.1-mini (2026-05-03). Runs are not pinned to a model+version, so results are not comparable across dates.
- **D6 confidence-gate skip.** The transcript-only confidence gate (gpt-4o-mini) fast-pathed past the council (`skipped_council=True`) on clean-transcript/fabricated-artifact cases. A gate upstream of the measured component can silently change what is measured.
- **D7 critique-pass model sensitivity.** Drop-only critique works on gpt-4.1 (council purpose), fails on gpt-4.1-mini (same-model blindspot), and over-pruned one legitimate low-severity finding. Validated at N=1 (case-12 smoke).

---

# Part 1 — Benchmark fix

Goal: a small benchmark with correct, system-aligned labels and honest coverage, before any number is reported.

## 1.1 Golden case schema (formalize)

Every golden case is a JSON object with these required fields:

```
case_id                 stable unique id
pack                    scribe_v1 | coding_v1 | triage_v1 | intake_v1 | scheduler_v1
ground_truth_basis      "constructed"   (only constructed labels are admissible; see Part 3)
synthea_provenance      { synthea_version, module_set, seed, base_bundle_sha256 }
injection_recipe        { defect_type, params, mutated_field_or_span, pre_value, post_value }
                         (empty for clean/negative cases)
source_refs             transcript_id, audio_id (nullable), artifact refs
expected_compliance_verdict   scalar  ("reject"|"needs_review"|"approve")
                              OR set  (["reject","needs_review"]) + verdict_set_rationale
expected_safety_flags   list of taxonomy codes (MUST pass 1.2 contract)
expected_owner_map      { flag_code: owning_judge }  (filled by 1.3 reconciliation)
severity                critical|high|medium|low
clean_negative          bool   (true = no defect injected; used for false-positive measurement)
notes                   free text
```

`eval_golden.jsonl` is regenerated to this schema. The current 55–58 ad-hoc rows are migrated, not appended to.

## 1.2 Label–taxonomy contract (closes D1)

Add `scripts/lint_golden_against_taxonomy.py`:

- Load `KNOWN_TAXONOMY_CODES`, `TIER_1_NEVER_EVENTS`, `TIER_2_HIGH_RISK`, `TIER_3_MEDIUM` from `compliance_council.py` at runtime (import, do not copy-paste the lists).
- For every golden case: assert each `expected_safety_flags` code ∈ `KNOWN_TAXONOMY_CODES`. Unknown code = hard fail with the case_id and the offending code.
- Run it in CI and as a pre-eval gate. An eval run aborts if the pack fails the lint.

For each currently-failing case (starting with line 58 / `VALUE_MISMATCH`), choose one, explicitly, and record the decision in `eval_golden_annotations.md`:

- **Fix taxonomy:** add the code to the right tier + `_TIER1_OWNERS` + every `council_roles/*.txt` taxonomy section with a worked example (this is the b2 report's "option D" for `VALUE_MISMATCH`: add to `TIER_1_NEVER_EVENTS`, owner `behavior_judge`). Then the label stays.
- **Relabel:** if the defect is real but maps to an existing code, change the expected flag to the code the system can actually emit.
- **Exclude:** if neither holds, drop the case from the scored set and record why. Do not leave a guaranteed-miss in the benchmark.

## 1.3 Label → owner reconciliation (closes D3)

Add `scripts/build_label_owner_matrix.py`:

- For each expected flag in the benchmark, resolve the owning judge/tier from the live `_TIER1_OWNERS` and tier sets.
- Emit `demo_dataset/label_owner_matrix.md`: flag → tier → owning judge(s) → "owner runs in production? (Y/N)".
- Any flag whose only owner is `source_message_judge` (not in the running 3-judge config) is flagged. Resolve by either adding `source_message_judge` to the running config, reassigning ownership to a running judge, or excluding cases that depend on it. Record the decision.

This matrix is also the artifact Part 3 calibration consumes.

## 1.4 Set-valued expected verdicts (honest version)

Set-valued `expected_compliance_verdict` is allowed only for cases that are borderline **by clinical/spec definition**, with `verdict_set_rationale` citing the rule (e.g. DoH Abu Dhabi Data Integrity Standard §3).

Hard guardrail: a case is NOT made set-valued because the system is flaky on it. System flakiness is a determinism problem (Part 2), not a labeling decision. Mixing the two is how a real accuracy gap gets hidden. The lint enforces: `expected_compliance_verdict` is a set only if `verdict_set_rationale` is present and non-empty.

## 1.5 Coverage + rollup contract (closes D4)

`run_eval_pack.py` / the eval runner:

- Must submit `cases_expected == cases_submitted` or exit non-zero with the missing case_ids listed. No silent under-submission.
- Must populate `result_summary` with: `n`, `verdict_match_rate`, `flag_precision`, `flag_recall`, `flag_f1`, `false_block_rate` (clean_negative cases that got BLOCK/WARN), per-severity breakdown, `skipped_council_rate`.
- A run JSON with empty `result_summary` is treated as invalid and not citable.

## 1.6 Run pinning (closes D5)

Every run JSON records a `pinned` block: `{ llm_provider, judge_model, judge_model_version, mini_model, critique_purpose, council_judges (actual, from pipeline_run.council_config), prompts_git_sha, taxonomy_git_sha, dataset_sha256 }`. Two runs are comparable only if the `pinned` tuple matches. The runner refuses to diff/compare runs with mismatched pins unless `--allow-cross-pin` is passed (and then it labels the comparison as cross-pin in the output).

---

# Part 2 — Determinism protocol

Goal: stop reporting single-run verdicts. Measure and report distributions, and separate the two variance layers the audit found.

## 2.1 Replication

- Dev signal: N=5 fresh runs per case.
- Any reported/published number: N≥10 per case. Justification: at N=3 you already observed a 1/3 flip (D2); N=3 cannot estimate a flip rate. N≥10 gives a usable interval.
- Pin everything in 1.6. Where the provider exposes temperature/seed, pin them. Where it does not (most hosted judge APIs), residual variance is intrinsic and is exactly what you are measuring; state this in the run metadata, do not pretend it is controlled.

## 2.2 Three-layer agreement decomposition (operationalizes the b2 finding)

For each case, over the N runs, compute and report separately:

1. **Decision-layer agreement.** Per judge, approve/reject distribution. Metric: per-judge reject-rate over N, and cross-judge agreement (Fleiss' kappa on the approve/reject decision). In the hba1c case this layer was unanimous and stable; that must show up as kappa ≈ 1.
2. **Code-attribution agreement.** Conditioned on reject: does the judge attach a specific taxonomy code with grounded evidence, or a bare reject. Metric: code-attachment rate per judge over N, and agreement on *which* code. This is the layer that was unstable. It must be reported as its own number, not folded into the verdict.
3. **Aggregation sensitivity.** Holding judge outputs fixed per run, does the case verdict change as code-attribution varies under the current aggregator. Metric: `verdict_instability = 1 - (modal_verdict_count / N)`. A case with unanimous decisions but unstable verdict (hba1c) is the signature of aggregator sensitivity, and the report must make that explicit rather than blaming "LLM randomness".

## 2.3 Reported metrics (per pack)

- Per-case: verdict distribution over N, modal verdict, `verdict_instability`, decision-layer kappa, code-attribution rate.
- Pack-level: `verdict_match_rate` as mean over runs with a bootstrap 95% CI over the N runs, not a point estimate. `flag_precision/recall/F1` against constructed ground truth, with CI. `false_block_rate` (over-block on clean_negative) reported separately because clinical over-blocking has its own cost and the 2026-04-29 baseline already had an over-block miss. `instability_rate` = fraction of cases with `verdict_instability > 0`.

## 2.4 Reportability gate

A pack-level number is citable (deck, paper, diligence) only if all hold:

- benchmark passed the 1.2 lint and the 1.3 reconciliation,
- full coverage (1.5),
- N≥10 with the `pinned` tuple recorded,
- `instability_rate` is reported next to the accuracy number, never without it.

If a number cannot meet this, it is an internal signal, not a claim. This is the single rule that keeps the deck from getting ahead of the evidence.

---

# Part 3 — Eval case generation + calibration

Goal: generate cases where the label is true by construction, and calibrate the mapping between an injected defect and what the system is expected to emit, so the eval tests the system and not the labeling.

## 3.1 Generation pipeline

```
Synthea (pinned version + module_set + seed)
  -> base FHIR bundle  (source of truth; base_bundle_sha256 recorded)
  -> render base artifact (clean SOAP note / ICD coding / triage decision / etc.)
  -> defect injector: apply exactly one labeled defect (or a labeled multi-defect combo)
       fabricated_med | negated_finding_flipped | wrong_laterality | dosage_drift
       | upcoded_hcc | missing_identifier | value_mismatch | unsupported_claim
  -> case = { base, mutated artifact, injection_recipe, expected_verdict, expected_flags,
              grounding_span }   (schema in 1.1)
```

Because the defect is injected, the expected flag and the contradicting/absent source span are known exactly. This is what makes labels deterministic and the negative-audit-trail / faithfulness metric measurable (the injected span is the ground-truth grounding location).

Generate four case classes, recorded as a design matrix:

- **clean_negative** (no defect): the only way to measure `false_block_rate` / over-block. The audit shows you have almost none of these and an over-block miss already happened. This is the biggest current gap in case coverage.
- **single-defect**: one injected defect, for attribution precision.
- **multi-defect**: two+ defects, to test the worst-of rule actually takes the worst.
- **near-miss**: defect present but subtle (small numeric drift, single negation), for sensitivity and to probe the code-attribution instability deliberately.

Balance the matrix per pack and store it as `demo_dataset/<pack>_design_matrix.md`.

## 3.2 Two-stage calibration (this is the part that makes the eval trustworthy)

**Stage A — label/taxonomy calibration (before any system run).**
Labels are mechanically correct because they are injected. What is NOT automatic is the mapping "injected defect → taxonomy code the system should emit → judge/tier that owns it". Use the 1.3 `label_owner_matrix`:

- For each defect_type, assert there exists at least one running judge that can emit the expected code.
- Any defect_type with no running owner is a system gap. Either fix the taxonomy/ownership/prompt (option-D style) or exclude that defect_type from the scored set and log it as a known capability gap. Do not score the system on a defect it has no path to flag, and do not silently let it miss.
- Output: a frozen `defect_type -> expected_code -> owning_judge` table, version-pinned with the taxonomy SHA.

**Stage B — threshold/aggregator calibration (on a held-out split, never on test).**
- Split the benchmark: `calibration` / `test`. Tune nothing on `test`.
- On `calibration`, run N≥10 and use the three-layer decomposition to set aggregator routing thresholds and the confidence-gate behavior so that cases that are unambiguous **by construction** do not flip on code-attribution variance. The target is: unanimous-decision constructed cases should be verdict-stable; only genuinely borderline-by-spec cases should be set-valued.
- The confidence gate is evaluated in two configs every run: as-shipped, and forced-open. Report `skipped_council_rate` and the verdict delta between the two. This is the standing guard against the D6 class (a gate silently changing what is measured). If forced-open materially changes accuracy, the gate is part of the system under test and must be reported, not hidden upstream.
- Re-measure on `test`. Only `test` numbers, under the Part 2 reportability gate, are citable.

**Severity/borderline calibration.** Set-valued expected verdicts are decided by a written clinical/spec rule (the source standard), recorded in `verdict_set_rationale`, decided on `calibration`, frozen before `test`. Never widen an expected set after seeing test behavior. That is the exact failure mode (b2 "option A" applied wrongly) this guard exists to prevent.

## 3.3 Critique-pass handling (D7)

The drop-only critique pass is part of the system under test, not a fixed constant:

- Always run the eval in two arms: critique-off and critique-on (`purpose="council"`, the only one shown to work; `purpose="mini"` is documented insufficient).
- Report the delta: findings dropped (true unsupported vs legitimate over-pruned), verdict changes, and the over-prune rate (legitimate findings removed). The case-12 smoke showed it both correctly drops a bad flag and over-prunes a low-severity true finding; that tradeoff must be a measured number across the pack, not a single anecdote.

---

# Execution order (do not reorder)

1. Part 1.1–1.3: schema + `lint_golden_against_taxonomy.py` + `build_label_owner_matrix.py`. Fix or exclude every failing label. (Closes D1, D3.)
2. Part 1.5–1.6: coverage + rollup + pinning in the runner. (Closes D4, D5.)
3. Part 3.1–3.2 Stage A: stand up the Synthea+injection generator and the frozen defect→code→owner table; add clean_negative cases. (Closes the over-block measurement gap.)
4. Part 2: N≥10 replication + three-layer decomposition + reportability gate. (Operationalizes D2.)
5. Part 3.2 Stage B + 3.3: calibration split, confidence-gate dual-config, critique on/off arms. (Closes D6, D7.)
6. Only now: build the tuned-LLM-judge baseline (criteria injection + ensembling) and run the structural-vs-semantic worst-of comparison. Measuring before steps 1–5 produces noise.

# Acceptance

- `lint_golden_against_taxonomy.py` green on the full benchmark.
- `label_owner_matrix.md` has zero "owner does not run in production" rows in the scored set.
- Every scored pack run has full coverage, a populated `result_summary`, a `pinned` block, and an `instability_rate` reported beside accuracy.
- A documented `calibration`/`test` split; no tuning artifact references `test` case_ids.
- Clean_negative cases exist in every pack and `false_block_rate` is reported.
