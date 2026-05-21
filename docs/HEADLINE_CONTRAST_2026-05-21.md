# Headline contrast — measurable on demand

**Date:** 2026-05-21
**Status:** demonstrable in the harness; awaiting real-backend numbers for the paper's §7 Results.

This doc records the empirical setup of the paper's main claim now that the bench engine + determinism harness + tuned-judge baseline + worst-of composition all exist.

## The claim (precise form, per PAPER_OUTLINE.md §1)

> A semantic LLM-as-judge is categorically blind to a class of specification-defined structural errors, and this blindness does not close with more judge accuracy because the judge is reasoning about meaning, not validating structure. Composing a deterministic structural validator with a semantic judge council under a worst-of rule recovers that error class.

The claim has two parts:

1. **Categorical blindness:** more semantic-judge accuracy does not close the structural gap. To test: hold the structural class fixed, increase semantic-judge tuning, and observe whether the gap closes.
2. **Compositional recovery:** worst-of with a structural validator restores the recall the semantic side cannot produce. To test: hold the semantic-judge tuning fixed, add the structural validator, and observe whether the gap closes.

## Setup

- **Pack:** `out/hl7_adt_v1.jsonl` — 30 cases, seed=7 (12 clean negatives, 11 single-defect, 3 multi-defect; 18 of 30 cases carry at least one structural defect).
- **Determinism protocol:** N=10 per case (eval spec §2.1).
- **Backends:**
  - `mock` — label-leaky baseline. Defeats verdict_match_rate by construction; useful only as a control.
  - `tuned-mock` — `TunedMockBackend(ensemble_size=3, per_member_semantic_accuracy=0.85)`. Pinned to the literature anchor (Lail & Markham, RewardBench 2 mid-80s). **Structural-blind by contract**: emits `structural_verdict = None` regardless of input. This is the simulation of the paper's "tuned semantic judge."
  - `structural-only` — `MockBackend(structural_drift_rate=0, decision/flag flip → 1)`. The validator with no semantic opinion.
  - `worst-of` — `WorstOfBackend(tuned-mock, structural-only)`. The composition.

## Result (one-shot, seed=7, N=10)

| Backend | verdict_match_rate (95% CI) | structural_recall | mean_decision_layer_kappa |
|---|---|---|---|
| basic mock (label-leaky control) | 1.000 (1.00–1.00) | 0.000 | 1.000 |
| **tuned-mock alone** | **0.400 (0.23–0.60)** | **n/a (blind)** | 0.687 |
| structural-only validator | 0.400 (0.23–0.60) | **1.000** | 1.000 |
| **worst-of(tuned-mock, structural)** | **1.000 (1.00–1.00)** | **1.000** | 0.687 |

## Interpretation

The 60-pp gap between tuned-mock alone (0.40) and worst-of (1.00) is the paper's headline. On a pack where 60% of cases (18 of 30) are structural defects, a tuned semantic ensemble at the published mid-80s accuracy ceiling cannot exceed 0.40 verdict_match because the structural class is **outside its measurement axis**. Composition with a deterministic structural validator recovers exactly that 60%.

The CI on tuned-mock and structural-only is identical (0.23–0.60) because both are limited by the *same* 12/30 clean-case ceiling. The structural validator alone covers the structural cases but has no opinion on the clean ones (it correctly says PASS). The tuned ensemble alone covers the clean ones (correctly approves them) and is blind to the structural ones (incorrectly approves them too). Together — and *only* together — they cover both.

Per-member κ stays at 0.687 across the tuned and worst-of rows because κ measures intra-ensemble agreement on the *semantic* axis; the structural axis is deterministic so it doesn't degrade κ.

## What the paper can claim from this

§4 (Method): the worst-of rule is `WorstOfBackend(semantic, structural)`. Two-line definition, ten-line implementation, mirrors backend's production rule.

§6 (Experiment design): the four-way comparison above is reproducible by anyone with the bench checkout. Three CLI invocations + an analysis call:

```
python scripts/generate_pack.py --pack hl7_adt_v1 --size 30 --seed 7
python scripts/run_determinism.py --pack-path out/hl7_adt_v1.jsonl --n 10 --backend tuned-mock
python scripts/run_determinism.py --pack-path out/hl7_adt_v1.jsonl --n 10 --backend worst-of --worst-of-semantic tuned-mock
python scripts/analyze_runs.py --runs out/*.runs.ndjson --pack out/hl7_adt_v1.jsonl
```

§7 (Results): the table above, with mock backends, is the *illustrative* version. The paper's actual Results row requires:

1. Running tuned-mock against the bench, but with `per_member_semantic_accuracy` calibrated against the LIVE LLM ensemble's accuracy on a held-out calibration split — so the mock's parameters are anchored, not assumed.
2. Running the real LLM ensemble against the bench (`--backend http --worst-of-semantic http`) for verification.
3. Running the real structural validator (etlp-mapper) against the bench (`--backend etlp-structural --worst-of-structural etlp`) for verification.

When (2) and (3) run and produce numbers consistent with the simulation, the paper's §7 numbers are honest.

## What still needs to happen

- **Calibrate per-member accuracy.** Run the live council on a 50-case calibration split, measure per-judge accuracy. Plug into `TunedMockBackend`. Then re-run the four-way comparison; the gap should be of the same shape as the illustrative numbers above.
- **Live-stack smoke.** Boot lithrim-backend + etlp-mapper, run `--backend worst-of --worst-of-semantic http --worst-of-structural etlp`. Verifies HTTP contracts. The harness is contract-ready; only the live services need to come up.
- **Pack scale.** Generate 200+ HL7 cases (the sample cohort has enough patients). Bigger N tightens the CI on the headline contrast; current N=30 produces wide CIs because the design matrix is small.

## Why this matters now

Before the tuned-judge baseline existed, the paper's "more accuracy doesn't close the structural gap" claim was rhetorical. With `TunedMockBackend`, it is **testable on the same pack, the same protocol, the same analysis** as every other backend. Wire a real LLM into `LithrimHttpBackend` later; the harness doesn't care which side of the worst-of is real and which is simulated. The composition rule itself is identical in either case.
