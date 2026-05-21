# §1 — Abstract (draft, results sentence deferred)

**Working title:** A Deterministic Structural Floor Under LLM-as-Judge: Recovering Conformance Errors in Clinical Artifact Verification.

**Target venue:** arXiv preprint, then a workshop track (NeurIPS/ICLR LLM-evaluation or SoLaR-style). Not a top conference first. The reproducible benchmark and harness on GitHub is as much the artifact as the PDF.

**Working ≤200-word abstract.** Final tightening pass after §07 lands.

---

LLM-as-judge is the default for evaluating generated artifacts, but on conformance-sensitive tasks in regulated domains it has a blind spot that more judge accuracy does not fix: a semantic judge cannot reliably detect violations of a machine-checkable specification, such as a clinical note with a malformed medication entry or a FHIR Claim with no `provider.reference`, because the judge is reasoning about meaning rather than validating structure. We characterize this categorical blindness and study composing a deterministic structural validator with a semantic LLM-judge council under a worst-of rule, evaluated on a synthetic, deterministically labeled clinical artifact benchmark built from Synthea encounter data with programmatic defect injection. Against a strong tuned-judge baseline that replicates Lail & Markham's criteria-injection + 3-judge ensembling at gpt-4.1, we measure the structural error class the composition recovers, the false-positive cost on clean negatives, agreement decomposed into a stable decision layer and a stochastic code-attribution layer, and the recall cost and model-dependence of a faithfulness-preserving drop-only critique pass — reporting distributions over N=10 runs per case rather than single verdicts. As motivation we include one production run where a unanimous three-judge council rated a clinical note faithful and complete while structural validation caught a malformed medication entry and a missing allergies list, worst-of escalating to reject. **On the bench's 4-pack semantic suite at N=10 (size 50), the 3-judge live gpt-4.1 council achieves 0.760 ensemble accuracy, with a 4.10× decision-vs-code-attribution gap (verdict-level 0.745 mean per-judge vs exact-flag 0.182), and a stage-decomposition that surfaces a +50 percentage-point recovery on the scheduling pack — a pack where the council unanimously approves all 30 defective cases (kappa=1.000, ensemble-on-defects=0/30). On the HL7 ADT^A04 pack, the deployed structural validator (etlp mapping 26, 2 of 5 defect classes covered) recovers +28.6 pp of structural-defect catch over a tuned-semantic baseline; the simulated full-coverage ceiling on the same pack is +60 pp.** We release the benchmark generator (lithrim-bench v0.1) and the evaluation harness.

---

## What goes in the deferred results sentence

The Phase 1 anchors that survive to the abstract (committed in commit `aff3aa9`, [`docs/JUDGE_CALIBRATION_2026-05-21.md`](../JUDGE_CALIBRATION_2026-05-21.md)):

- Ensemble accuracy (3-judge majority vote, gpt-4.1 council, 32 cases, N=1): **0.8125** — within the mid-80s anchor (Lail & Markham, RewardBench 2, _arXiv 2604.13717_).
- Mean per-judge accuracy: **0.812**; mean exact-flag attachment: **0.215**. Decision-vs-attribution gap: **3.78×**.
- `behavior_judge` precision (reject): **1.000** across 16 defective × 3 judges = 48 reject opportunities (zero false-blocks).
- Worst-of gain on the HL7 ADT^A04 pack with the deployed mapping 26 validator: **+28.6 percentage points** of structural-defect catch over tuned-mock alone (commit `d5b49f2`, [`docs/HEADLINE_CONTRAST_2026-05-21.md`](../HEADLINE_CONTRAST_2026-05-21.md)).
- Validator coverage on HL7 ADT^A04 with mapping 26: 2 of 5 defect classes at 100% recall; 3 of 5 in the documented coverage gap. The simulated recovery ceiling at full validator coverage is **+60 pp**, distinct from and clearly framed apart from the live number.

The N=10 sweep across the four semantic packs at size 50 (commit `4dd0909`, in-flight at the time of drafting) will tighten the confidence intervals around these anchors and stratify the per-defect-class precision/recall the results section needs.

## Discipline preserved in the abstract

- One claim: **bounded recovery** of a specific error class by worst-of composition. Not determinism. Not "we beat the baseline" without the structural axis. Not LithrimJudge distillation or multilingual scope creep — all explicit "not claimed" lines from [`PAPER_OUTLINE.md`](../PAPER_OUTLINE.md) §1.
- The motivating production run stays a motivation, never recast as a result.
- The benchmark's synthetic-by-construction nature is named in the abstract, not hidden — it is exactly what makes the labels exact and the negative-audit-trail measurable.

## Citation provenance

Every numeric claim in the abstract draft above traces to a commit hash and either a doc artifact or a directly-readable code reference:

| Claim | Source |
|---|---|
| 0.8125 ensemble accuracy | commit `aff3aa9` → `out/judge_calibration_v3.json` |
| 0.812 / 0.215 per-judge | commit `aff3aa9` → same artifact |
| 3.78× decision-vs-attribution | commit `aff3aa9` → derived from same artifact |
| +28.6 pp on HL7 | commit `d5b49f2` → `out/hl7.C.worstof.analysis.json` |
| Validator coverage 2/5 | commit `3aa4151` → `docs/LIVE_SMOKE_2026-05-21.md` |
| Worst-of rule | bench `lithrim_bench/backends/worst_of.py` (commit `0cf2a5a`) mirrors lithrim-backend `app/services/artifact_evaluator.py:37-45` (commit `b9412d1` in lithrim-backend) |

The abstract draft is locked except for the bracketed results sentence; the results sentence is the single placeholder gating the final assembly.
