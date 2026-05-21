# §6 — Experiment Design

## 6.1 Systems compared

The bench supports the following backends through a unified `BackendClient` interface (`lithrim_bench/backends/base.py`). Each backend can be slotted into the determinism harness identically:

| Backend | Role | Implementation |
|---|---|---|
| `mock` | label-leaky control | `MockBackend` — reads expected labels; used to verify analysis plumbing. Never reported as a result. |
| `tuned-mock` | strong semantic baseline | `TunedMockBackend(ensemble_size=3, per_member_semantic_accuracy=p, per_member_flag_attachment_rate=r)` — Lail & Markham-style ensemble simulation. Structural-blind by contract. |
| `lithrim-validate-artifact` | structural-only via live Lithrim middleware | `LithrimValidateArtifactBackend` — POSTs to `/v1/validate-artifact`; routes through the live artifact-profile system to the correct etlp mapping. |
| `etlp-structural` | structural-only via direct etlp-mapper client | `EtlpStructuralBackend` — bypasses Lithrim middleware; useful when measuring validator behavior in isolation. |
| `lithrim-pipeline` | live full pipeline (semantic + structural) | `LithrimPipelineBackend` — POSTs to `/v1/pipeline/evaluate`; returns the production worst-of verdict plus all per-judge votes. The production system under test. |
| `worst-of` | meta-backend composition | `WorstOfBackend(semantic, structural)` — pairs any (semantic, structural) backends under the §4.2 rule. |

The experiment-grid for §7 results pairs each pack with three configurations:

1. **Tuned-mock alone** (literature-anchored simulation of "strong semantic judge").
2. **Live structural validator alone** (zero semantic).
3. **Worst-of (tuned-mock + live structural)** (the composition).

A live-council fourth configuration is also reported on a subset of packs to verify the simulation matches reality. On the bench's 32-case calibration sweep (commit `aff3aa9`), the live-council ensemble achieves accuracy 0.8125 — within the tuned-mock-anchored simulation band — confirming the simulation is calibrated.

## 6.2 The N≥10 protocol

Every reportable number in §7 is averaged over N=10 runs per case (eval-spec §2.1). Dev-signal sweeps use N=5; calibration sweeps use N=1 (acknowledged as scoping signal, not reportable). N=3 is explicitly insufficient: the audit observed a 1/3 flip in the `hba1c_value_mismatch` case under the live council, and N=3 cannot estimate a flip rate (eval-spec §2.1, defect D2).

The N=10 sweep at pack size 50 across the four semantic packs (`scribe_v1`, `scheduling_v1`, `coding_v1`, `triage_v1`) is in flight at the time of drafting (commit `4dd0909`); expected completion ~8 hours from launch ([`docs/N10_SWEEP_FOLLOWUP_2026-05-21.md`](../N10_SWEEP_FOLLOWUP_2026-05-21.md)). Acceptance: 4 NDJSON files with 500 rows each, `verdict_match_rate_ci95` width ≤ 0.1 per pack, `instability_rate` reported per pack.

Where the LLM provider exposes temperature/seed, we pin them. Where it does not (the production Azure gpt-4.1 endpoint exposes neither), residual variance is intrinsic to the system under test and is what we are measuring. We state this in run metadata; we do not pretend it is controlled.

## 6.3 The three-layer agreement decomposition

For each case over N=10 runs, we compute and report three separate agreement layers per the eval-spec §2.2:

1. **Decision-layer agreement.** Per-judge `approve`/`reject` decision distribution and cross-judge Fleiss' kappa. Stable, high kappa here means the judges agree on the *outcome*, even if they disagree on the taxonomy code.
2. **Code-attribution agreement.** Conditioned on `reject`: does the judge attach a specific taxonomy code with grounded evidence, or a bare `reject`? We report per-judge code-attachment rate over N and agreement on _which_ code. The Phase 1 calibration sweep already showed an order-of-magnitude gap here — 0.812 verdict-level accuracy versus 0.215 exact-flag attachment, a **3.78× decision-vs-attribution gap** (commit `aff3aa9`).
3. **Aggregation sensitivity.** Holding judge outputs fixed per run, does the case verdict change as code-attribution varies under the current aggregator? Metric: `verdict_instability = 1 - (modal_verdict_count / N)`. A case with unanimous decisions but unstable verdict is the signature of aggregator sensitivity, surfaced explicitly rather than blamed on "LLM randomness".

This decomposition was load-bearing for the [`hba1c` bistability finding](../EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md): the decision layer was unanimous, the code-attribution was stochastic, and the aggregator's verdict-routing turned that stochasticity into a 1/3 verdict flip. Folding all three into one "accuracy" number would hide the actual failure mode.

## 6.4 Reported metrics

Per-case (reported in `out/<pack>.n10.analysis.json`):
- verdict distribution over N
- modal verdict
- `verdict_instability`
- decision-layer kappa
- code-attribution rate

Pack-level (reported in `docs/paper_draft/07_results.md` once Item 4 lands):
- `verdict_match_rate` (mean over N runs, bootstrap 95% CI)
- per-defect-class precision / recall / F1 against constructed ground truth (CI from bootstrap)
- `false_block_rate` on clean negatives (reported separately because over-block has its own cost — the 2026-04-29 baseline already had an over-block miss)
- `instability_rate` (fraction of cases with `verdict_instability > 0`)
- `flag_attachment_rate_mean` (per-judge and pooled)
- `skipped_council_rate` (the confidence-gate audit metric, see §6.6)

## 6.5 Reportability gate

Per eval-spec §2.4, a pack-level number is citable in the paper only if **all** hold:

- pack passed the §1.2 taxonomy lint and §1.3 owner-reconciliation
- full coverage (`cases_expected == cases_submitted`)
- N≥10 with the `pinned` block recorded (LLM provider/model/version, prompts SHA, taxonomy SHA, dataset SHA)
- `instability_rate` is reported next to the accuracy number, never without it

If a number cannot meet this gate, it is an internal signal, not a paper claim. This is the single rule that keeps the paper from getting ahead of the evidence. The early-Phase-1 numbers ("clean recall 4/4 at N=1") in [`docs/JUDGE_CALIBRATION_2026-05-21.md`](../JUDGE_CALIBRATION_2026-05-21.md) are explicitly internal signal — they direct synthesizer calibration; they do not appear in §7.

## 6.6 The confidence-gate dual-config

The transcript-only confidence gate (gpt-4o-mini fast-path) fast-pathed past the council on clean-transcript/fabricated-artifact cases in the 2026-04-29 baseline (eval-spec defect D6). A gate upstream of the measured component can silently change what is measured.

§7 reports every pack in two configurations: **as-shipped** (gate enabled) and **forced-open** (gate disabled, `gate_mode=False` on `LithrimPipelineBackend`). We report `skipped_council_rate` and the verdict delta between the two. If forced-open materially changes accuracy, the gate is part of the system under test and must be reported, not hidden upstream.

## 6.7 Critique-pass on/off arms

Per eval-spec defect D7 and §3.3, the drop-only critique pass is part of the system under test, not a fixed constant. §7 runs the eval in two arms: critique-off and critique-on, `purpose="council"` only (the documented-working configuration). The reported delta includes:

- findings dropped (true unsupported vs legitimate over-pruned)
- verdict changes
- over-prune rate (legitimate findings removed)

The case-12 smoke showed the critique pass both correctly drops a bad flag and over-prunes a low-severity true finding; §7 reports this trade-off as a measured pack-level number, not an anecdote.

## 6.8 Calibration / test split

A calibration / test split is documented before §7 numbers are taken. Aggregator thresholds, confidence-gate behavior, and any tunable composition parameter are set on `calibration` only; `test` is held out. Set-valued `expected_compliance_verdict` is decided on `calibration` per a written clinical/spec rule (recorded in `verdict_set_rationale`) and frozen before `test` — system flakiness does NOT make a case set-valued (eval-spec §1.4). The `test` cases are the only ones whose numbers appear in §7.

## Word count

Approximately 1110 words. Under the 1500-word ceiling.

## Citation provenance

| Claim | Source |
|---|---|
| Backend interface | bench `lithrim_bench/backends/base.py` @ commit `bedbbfd` |
| WorstOfBackend implementation | bench `lithrim_bench/backends/worst_of.py` @ commit `0cf2a5a` |
| LithrimPipelineBackend | bench `lithrim_bench/backends/lithrim_pipeline.py` @ commit `e862ec6` |
| N=10 protocol | bench `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` §2.1 |
| Three-layer decomposition | bench `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` §2.2 |
| 3.78× decision-vs-attribution gap | commit `aff3aa9` → `out/judge_calibration_v3.json` |
| Reportability gate | bench `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` §2.4 |
| Confidence-gate audit | bench `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` defect D6 |
| Critique-pass two-arm protocol | bench `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` §3.3 |
| N=10 sweep launch | bench commit `4dd0909` → `docs/N10_SWEEP_FOLLOWUP_2026-05-21.md` |
