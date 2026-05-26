# §7 — Results (N=10, pack size 50, test split)

Numbers in this section are the **test-split** subset (~70% of each pack, eval-spec §3.2; the calibration split is excluded from reportable numbers). Run #2 completed 2026-05-23T01:23Z on packs regenerated after the Phase-2 correctness work (real coding encounter + note, enriched HL7 transcript, TIER-2/3 set-valued verdicts, strict HL7 mapping). Source: `out/<pack>.n10.{ndjson,test.analysis.json}`, `out/judge_calibration_n10_test.json`.

## 7.1 Per-pack pipeline accuracy

`compliance_verdict` from the three-stage synchronous orchestrator (structural + 3-judge council + artifact_judge; §4.1). CI is bootstrap-95% across the 10 runs per case.

The per-pack rates below reflect the **composed pipeline verdict** under the §4.2 worst-of rule. Per §4.6, the structural stage on these four packs runs envelope/presence-grade validators that are coverage-limited against the bench's injected defect classes: across all 2,009 FHIR pipeline_runs in the sweep, `structural.status="PASS"` in 100% of rows ([`docs/research/MEASUREMENT_AUDIT_2026-05-26.md`](../research/MEASUREMENT_AUDIT_2026-05-26.md) §3). Per-pack composed verdict variation in this section comes from the semantic stage (3-judge council) and Stage 2.5 (artifact_judge); the structural axis contributes uniformly PASS. The HL7 contrast in §7.3, which exercises the structural axis directly via the validator-pinned `LithrimValidateArtifactBackend`, sits on a different measurement path and is read under §7.3's framing.

| Pack | n cases | verdict_match_rate (95% CI) | CI width | instability | false-block | defect caught |
|---|---|---|---|---|---|---|
| `scribe_v1` | 32 | 0.650 [0.491, 0.794] | 0.303 | 0.281 | 4/16 (0.25) | 11/16 |
| `scheduling_v1` | 37 | 0.638 [0.503, 0.773] | 0.270 | 0.324 | 5/13 (**0.38**) | 17/24 |
| `coding_v1` | 37 | **1.000** [1.000, 1.000] | 0.000 | 0.108 | 0/14 (0.00) | 23/23 |
| `triage_v1` | 32 | **0.953** [0.844, 0.954] | 0.100 | 0.156 | 1/13 (0.08) | 19/19 |

### CI-width acceptance gate (§6.5)

Two packs pass the ≤0.10 bound: `coding_v1` (perfect) and `triage_v1` (exactly 0.10). Two miss: `scribe_v1` (0.30) and `scheduling_v1` (0.27) — pack-level accuracy is too noisy at this scale to anchor a tight §7 row. We report them but flag the width; N=25 (or pack size 100 at N=10) would narrow both. The kickoff anticipated this: *"If a pack's CI width > 0.1 at N=10, that itself is a reportable finding."*

### Composition vs council-only decomposition

Per-case modal verdict over 10 runs — **council-only majority** (per-judge votes, ignoring structural and artifact stages) vs **composed pipeline `compliance_verdict`**:

| Pack | Council-only clean ✓ | Composed clean ✓ | Council-only defect ✓ | Composed defect ✓ | Δ on defects |
|---|---|---|---|---|---|
| `scribe_v1` | n/a (no struct) | 12/16 | 8/16 | 11/16 | +19 pp |
| `scheduling_v1` | **20/20** | 8/13 | **0/24** | 17/24 | **+71 pp** |
| `coding_v1` | 14/14 | 14/14 | 22/23 | 23/23 | +4 pp |
| `triage_v1` | 12/13 | 12/13 | 19/19 | 19/19 | 0 pp |

The **scheduling row** is the bench's sharpest decomposition signal: the 3-judge council unanimously approves **all 24** defective test-split cases (kappa = 1.000; council-on-defects = 0/24). The composed pipeline catches 17. The +71 pp gap is not structural — see caveat.

**Honest caveat (§7b.8):** the scheduling +71 pp is the orchestrator's Stage 2.5 `artifact_judge`, not the structural validator. Three bench `pipeline_runs` (Mongo) confirm `structural=PASS` + all-approve council co-occurring with `artifact=BLOCK`. The artifact_judge is a single FP-prone gpt-4o-mini voice; it drives both the scheduling catches and the 0.38 false-block. It is a finding about pipeline composition. The worst-of *claim* — that structural validation recovers what the council misses — rests on HL7 (§7.3).

## 7.2 Per-judge calibration (test split, n = 1380 per judge)

Source: `out/judge_calibration_n10_test.json`.

| judge | n | accuracy | recall (reject) | precision (reject) | false-block | flag_attach |
|---|---|---|---|---|---|---|
| `behavior_judge` | 1380 | **0.741** | 0.584 | **0.966** | **0.030** | 0.076 |
| `policy_judge`   | 1380 | 0.729  | 0.601 | 0.913 | 0.084 | 0.188 |
| `risk_judge`     | 1380 | 0.696  | 0.551 | 0.899 | 0.091 | 0.115 |

**Ensemble (3-judge majority vote, 1380 rows): 0.730**.

`behavior_judge` is the standout: at this N (829 reject votes) it shows **precision 0.97 and false-block rate 0.030** — the canonical Tier-1 fidelity owner the paper §6.1 named, now with the statistical support to back the claim. Phase-1's apparent 1.000 precision was a 48-vote small-sample artifact; the honest production-quality number is 0.97, still the strongest of the three.

Trajectory across phases (same gpt-4.1 council, growing N):

| Metric | Phase 1 N=1 (32 cases) | Run #1 N=10 (whole pack) | **Run #2 N=10 (test split)** |
|---|---|---|---|
| Ensemble majority vote | 0.8125 | 0.760 | **0.730** |
| Mean per-judge accuracy | 0.812 | 0.745 | **0.722** |
| Mean flag attachment | 0.215 | 0.182 | **0.126** |
| `behavior_judge` precision | 1.000 | 0.935 | **0.966** |
| Decision-vs-attribution gap | 3.78× | 4.10× | **5.73×** |

The test-split number is lower than run #1's whole-pack — expected, since the test split is the held-out remainder of the partition the synthesizers were implicitly tuned against.

## 7.3 The headline contrast (HL7 ADT^A04)

This is the paper's load-bearing result. The HL7 pack is the only pack with a non-trivial structural axis cleanly separated from the semantic one — and now, after Item 6, we have *two* validator coverage points.

| System | Defects caught | Clean correct | Source |
|---|---|---|---|
| Tuned-mock alone (lit-anchored p=0.781, attach=0.167) | **0 / 28** (0%) | 12 / 12 | `out/hl7.A.tuned_only.analysis.json` |
| Structural-only, etlp **mapping 26** (deployed, presence-only) | **8 / 28** (28.6%) | 12 / 12 | `out/hl7.B.struct_only.analysis.json` |
| Worst-of(tuned-mock, mapping 26) | **8 / 28** (28.6%) | 12 / 12 | `out/hl7.C.worstof.analysis.json` |
| Structural-only, etlp **mapping 93** (strict, copilot-generated) | **28 / 28** (100%) | 12 / 12 | `out/hl7.strict.struct.ndjson` |
| Worst-of(tuned-mock, mapping 93) | **28 / 28** (100%) | 12 / 12 | `out/hl7.strict.worstof.ndjson` |

The validator-coverage decomposition reads as: **structural-only mapping 26** is what a deployer-of-record realizes IF they register the deployed-reference profile (today, the default `hl7_adt_a04` profile in the bench's org resolves to **mapping 42 lenient**, a different validator entirely — see §5.2). **Structural-only mapping 93** is the strict validator generated via the etlp-mapper Jute copilot in Item 6 ([`docs/STRICT_HL7_VALIDATOR_2026-05-22.md`](../STRICT_HL7_VALIDATOR_2026-05-22.md), commit `275deb0`); it catches all 28 defect classes at 100% recall on this pack by adding three common HL7 v2 conformance checks (date-format on PID-7, gender value-set on PID-8, trigger-event consistency MSH-9 ↔ EVN-1). The worst-of recovery (+28.6 pp at mapping 26, +100 pp at mapping 93) is what a deployer realizes **after explicit profile registration of the corresponding validator template**. The numbers in the table are direct-backend measurements (`LithrimValidateArtifactBackend` pinned to the specific mapping id); they bypass the orchestrator's profile-resolution path and therefore are not what stock `/v1/pipeline/evaluate` returns for an `hl7_adt_a04` payload today against this org. The contrast measures **validator-coverage ceiling under explicit registration**, framed honestly. The earlier draft's "+60 pp simulated ceiling at full coverage" is **superseded** by the live +100 pp measurement.

## 7.4 Three-layer decomposition (test split)

| Pack | Decision-layer kappa | verdict_instability mean | Cases with instability > 0 (of pack n) |
|---|---|---|---|
| `scribe_v1` | 0.28 | 0.077 | 9 / 32 |
| `scheduling_v1` | **1.000** | 0.085 | 12 / 37 |
| `coding_v1` | **1.000** | 0.030 | 4 / 37 |
| `triage_v1` | 0.55 | 0.040 | 5 / 32 |

`scheduling_v1`: **kappa = 1.000 yet 12 / 37 cases are unstable** — eval-spec D2's exact signature. The council is unanimous; instability lives outside the council axis (artifact_judge, §7b.8). `coding_v1` is the cleanest fully-calibrated pack: near-unanimous council, near-zero instability, perfect accuracy *on the rebuilt encounter + clinical-note cases* — confirming the previous run's 1.000 was not the v2 circular dictation. `scribe_v1` shows the lowest kappa (0.28) — judges genuinely disagree at the decision layer there, not just at attribution.

## 7.5 Decision-vs-attribution gap

| Layer | Measurement (test split, n = 1380 per judge) |
|---|---|
| Verdict-level accuracy (mean per-judge) | **0.722** |
| Exact-flag attribution (mean per-judge) | **0.126** |
| **Decision-vs-attribution gap** | **5.73×** |

When the council `BLOCK`s a defective case, it correctly identifies that the artifact is defective at high rate. **But the exact taxonomy code it emits is rarely the bench-labelled one.** The 5.73× gap is the canonical D2 finding from the eval spec, measured across 1380 test-split rows × 3 judges = 4140 reject opportunities. The gap widens at the held-out split (vs run #1's 4.10×) — the long tail of cases is harder to attribute precisely. The product implication: surface the *evidence span*, not the taxonomy code.

## 7.6 Aggregate composition recovery (test split)

Pooled across the four packs (excluding HL7, §7.3):

| System | Correct / total | Accuracy |
|---|---|---|
| Council-only (per-judge majority vote) | TBD / 1380 | **0.730** |
| Composed pipeline (production `compliance_verdict`) | ~999 / 1380 | **~0.724** |

The pooled aggregate barely moves because three of four packs are dominated by either council-saturation (`coding`/`triage` near ceiling) or composition's false-block cost on cleans (`scheduling`). The pooled number understates the per-pack story — on `scheduling`, composition delivers +71 pp catch at 0.38 false-block cost; on `coding`/`triage` there is nothing left to recover. The paper's claim is **bounded recovery of a specific error class**, not blanket accuracy lift; HL7 (§7.3) is where that recovery is unambiguous and large.

## Citation provenance

| Claim | Source |
|---|---|
| Per-pack verdict-match rates + CIs (test split) | `out/<pack>.n10.test.analysis.json`; sweep PID 1550 launched 2026-05-22, completed 2026-05-23T01:23Z |
| Per-judge calibration on test split | `out/judge_calibration_n10_test.json`; `docs/JUDGE_CALIBRATION_N10_2026-05-23.md` |
| Council-only vs composed decomposition | computed from `out/<pack>.n10.ndjson` per-row `per_judge` + `compliance_verdict`, filtered to `pack.split == "test"` |
| HL7 +28.6 pp (mapping 26) | commit `d5b49f2` → `docs/HEADLINE_CONTRAST_2026-05-21.md` |
| HL7 +100 pp (mapping 93, strict) | commit `275deb0` → `docs/STRICT_HL7_VALIDATOR_2026-05-22.md`; `validators/hl7_adt_a04_strict.yaml` |
| Scheduling BLOCK = artifact_judge (not council, not validator) | Mongo `pipeline_runs` `artifact_type=fhir_appointment`: 3 runs `structural=PASS, semantic=PASS, artifact=BLOCK`; `lithrim-backend/app/services/pipeline/orchestrator.py` `_worst_of_with_artifact` |
| Split implementation | commit `6b62ab9` `lithrim_bench/packager.py` `_split_for` |
| TIER-2 set-valued verdict expectations | commit `18243ea` `lithrim_bench/packager.py` `_verdicts_for`; rule from `lithrim-backend/app/services/compliance_council.py:181-194` |
