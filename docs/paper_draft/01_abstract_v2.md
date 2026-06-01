# §1 — Abstract (v2, reframed — validator-authoring lead, positioned vs the 2026 consensus)

> **Supersedes `01_abstract.md`** (the "structural floor" framing), per the `PAPER_OUTLINE.md`
> amendments of **2026-05-26** (reframe → the validator-authoring / generative-composition paper)
> and **2026-06-01** (the disclosed generator is the **DSPy bench-gated generator**; S-P1-22).
> The prior abstract is preserved verbatim for the audit trail. **Positioned against the 2026
> eval-market consensus** surfaced by the competitive scan (`.devloop` session 2026-06-01).
>
> **Working title (per the 2026-05-26 amendment):** *Closing the Validator-Authoring Bottleneck:
> Bench-Gated Generation of Conformance Validators and Their Composition with LLM-Judge Councils
> on a Clinical Artifact Benchmark.*
>
> **Target venue:** arXiv preprint first (priority date), then a workshop (NeurIPS/ICLR
> LLM-evaluation or SoLaR-style). The reproducible benchmark + harness + generator on GitHub is
> as much the artifact as the PDF.

---

**Working abstract (~270 words; final tightening pass after §6/§7 land).**

Evaluating LLM systems in regulated domains has converged, by 2026, on a consensus architecture: deterministic conformance checks, a semantic LLM-judge council, and human calibration of the judges. This consensus leaves two problems unaddressed. **First, the deterministic validators it depends on must be *authored* — and generating them from a specification with a single high-confidence model call is unreliable in a way the confidence score hides:** in our spike, single-call generation is accepted **0/3** by a multi-case oracle, shipping validators that self-report `confidence:high`/`partial` yet err on **9 of 10** cases. **Second, judges are calibrated against human-annotated sets, not labels true by construction.** We close the validator-authoring bottleneck with a **bench-gated generative pipeline** — a generate→test→refine loop gated by a multi-case, by-construction oracle, where the *gate*, not the model's self-reported confidence, is the load-bearing primitive — and evaluate it on a synthetic, deterministically-labeled clinical artifact benchmark (Synthea + programmatic defect injection; labels exact by construction; clean negatives for false-positive measurement). Our central claim is unchanged from the locked outline: **a semantic judge council is *categorically* blind to a class of specification-defined structural errors that more judge accuracy cannot fix, and a generated deterministic validator composed under a worst-of rule recovers that class.** On the HL7 ADT^A04 pack, a tuned 3-judge gpt-4.1 council catches **0/28** structural defects while certifying them at confidence **1.000** — *silent confident certification*, invisible at the API surface — whereas the generated conformance validator catches **28/28** (+100 pp). Across four semantic packs (N=10, 1380 council invocations) the council reaches **0.730** accuracy with a **5.73×** decision-vs-code-attribution gap. We position the contribution as **orthogonal to judge-noise reduction** (criteria-injection + ensembling) **and to reward-model scoring**, scope the structural recovery to *conformance* (semantic-equivalence judgment is characterized, not solved), and release the benchmark generator (`lithrim-bench`), the bench-gated generator, and the evaluation harness.

---

## What changed from `01_abstract.md` (and why)

| Lever | Old (`01_abstract.md`) | v2 (this) | Why |
|---|---|---|---|
| **Lead** | "a deterministic structural floor under LLM-as-judge" | **closing the validator-authoring bottleneck** (the generator is the contribution) | Per the 2026-05-26 amendment: the generator is the only genuinely non-obvious thing; the floor itself is engineering. |
| **Generator** | "validator generated via the etlp-mapper Jute copilot" (single call) | **DSPy bench-gated generator**; single-call copilot recast as the **baseline** | S-P1-22 (2026-06-01): single-call is confidently-wrong (0/3); the multi-case gate is what makes generation reliable. |
| **Positioning** | implicit (vs Lail & Markham tuned judge) | explicit **vs the 2026 consensus**: orthogonal to judge-calibration (LangSmith Align Evals, Langfuse) **and** to reward-model scoring (Composo) | The competitive scan: "deterministic + judges + human calibration" is now consensus best-practice; the *generation-reliability* + *by-construction* gaps are what remain novel. |
| **Silent-confident** | a motivating production run | a **measured failure mode** (confidence 1.000 on missed defects) elevated into the demonstration | §5_v2 makes it measurable, not anecdotal. |

## Discipline preserved (unchanged from `01_abstract.md` + `PAPER_OUTLINE.md` §1)

- **One claim:** *bounded recovery* of a specification-defined error class by worst-of composition. **Explicitly not claimed:** a deterministic system; that structural composition beats a tuned judge on *semantic* correctness; system-level verdict-propagation reliability (engineering, a limitations note). The locked claim is **not weakened** here — only its framing (generator-first) and positioning (vs the consensus) change.
- **Scope honesty (per the 2026-05-23 reframe):** the categorical claim is demonstrated on **HL7 conformance**; the four semantic packs are **baseline characterization**, not thesis validation; semantic-*equivalence* judgment is named as future work, not solved. The scheduling pack's apparent "+71 pp" is **orchestrator artifact_judge behavior, not a structural-axis win** — reported as such.
- **By-construction labels** are named in the abstract, not hidden — they are exactly what makes the labels exact and the false-positive / negative-audit-trail measurable *without* the human-annotation drift the consensus calibration loops carry.

## Citation provenance (every number traces to a CONFIRMED source)

| Claim | Source | Confidence |
|---|---|---|
| HL7: tuned-judge **0/28**, mapping 26 **8/28** (+28.6 pp), generated validator (mapping 93) **28/28** (+100 pp) | `01_abstract.md` provenance table → `out/hl7.C.worstof.analysis.json` (commit `d5b49f2`); `07_results.md` | CONFIRMED |
| 4 semantic packs **0.730** accuracy, **5.73×** gap (0.722 vs 0.126), behavior_judge 0.97 / 0.030 (829 votes) | `07_results.md` (N=10, size 50, held-out, 1380 invocations) | CONFIRMED |
| Silent confident: monoculture **5/10** unanimous-approve on defects, **36/36** votes @ confidence 1.000; trio → **0/10** + FP **2/2→0/2** | `05_section_5_silent_confident_certification_v2.md` | CONFIRMED |
| p1_exp_0: on 28 defects, **10 (35%)** unanimous-approve @ per-judge confidence 1.000; ≥1 judge approves on **25/28 (89%)** | `05_section_5_silent_confident_certification.md` → `out/p1_exp_0_council_confidence.summary.md` | CONFIRMED |
| Single-call generation **0/3** accepted; errs on **9/10** cases; DSPy bench-gated → ACCEPT | `PAPER_OUTLINE.md` amendment 2026-06-01 (S-P1-22) → **WS-3a spike** `experiments/dspy_council_smoke/REPORT_jute_dspy_generator.md` | **VERIFY against the primary spike report before camera-ready** (drafted from the committed outline amendment, not yet from the report itself) |

> **One number to firm before submission:** the **0/3 / 9-of-10** generation-reliability figures are drafted from the committed `PAPER_OUTLINE.md` amendment; pull the exact N + denominators from `REPORT_jute_dspy_generator.md` (the WS-3a primary) for §6. Everything else is CONFIRMED against `07_results.md` / `05_…v2.md`.
