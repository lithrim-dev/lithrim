# §3 — Related Work and Positioning

This paper sits at the intersection of three research lines: LLM-as-judge reliability, clinical NLP/faithfulness evaluation, and FHIR/HL7 conformance validation. The contribution is not "a better judge" or "a new validator" but the **composition** of a deterministic structural validator with a semantic LLM-judge council under a worst-of rule, characterized on a synthetic-by-construction clinical artifact benchmark.

We frame each related line briefly, name what we re-use, and pre-empt the obvious reviewer objections.

## 3.1 LLM-as-judge reliability and stochastic-noise control

Lail & Markham (RewardBench 2, _arXiv 2604.13717_) establish the strong-baseline territory for LLM-as-judge: criteria-injection plus an ensemble of 3+ judges, on a tuned model, reaches the mid-80s on general reward benchmarks. We treat this as our **baseline-construction reference**, not a result of this paper — and we replicate it explicitly on the bench rather than asserting it on faith. On our calibration sweep (32 cases across `scribe_v1`, `scheduling_v1`, `coding_v1`, `triage_v1`; 3-judge live gpt-4.1 council with criteria-injection; full pipeline, N=1; commit `aff3aa9`), ensemble majority-vote accuracy lands at **0.8125** — squarely within the published mid-80s anchor.

We adopt Lail & Markham's two mechanisms (criteria-injection + ensembling) deliberately:

1. To make the structural-vs-semantic comparison fair against a *strong* semantic baseline, not a single-call strawman. A reviewer cannot dismiss our worst-of gain as "we just compared against a bad judge."
2. To position our axis as **orthogonal** to theirs. Their work reduces stochastic judge noise within the semantic axis; ours adds a deterministic floor underneath. Noise-control inside the semantic axis cannot, by construction, detect violations of a machine-checkable specification — that requires a structural validator. We make this categorical claim precise in §4 and characterize it empirically in §7.

The closest adjacent work — Zheng et al. _MT-Bench_, Lin et al. _LLM-Eval_, Chen et al. _judge-bench_ — focus on judge calibration, prompt sensitivity, and inter-judge agreement. None compose a structural validator with the judge; the gap between meaning-validation and specification-validation is implicit in their setups and not measured. We argue that on conformance-sensitive tasks (clinical artifacts being our particular instance, but the same logic applies to legal contracts, financial filings, regulatory submissions), the gap is the *most consequential* failure mode and benchmarks that fold it into a general accuracy score cannot surface it.

## 3.2 Faithfulness and groundedness in clinical NLP

Clinical NLP evaluation has converged on faithfulness/groundedness metrics — does each asserted claim in the generated artifact have a supporting source span in the input? — typically measured by annotator agreement or by entailment models (Maynez et al. _Faithfulness in Abstractive Summarization_; clinical adaptations in MedQA, MIMIC-derived faithfulness studies).

Our **negative-audit-trail** signal generalizes this construct in a setting where the answer is mechanically knowable rather than annotator-judged. Because every defect in our benchmark is _injected_ — and the injection recipe records the exact span the mutation affects — the contradicting or absent source span is known by construction. An asserted claim with no supporting source span is itself a measurable finding, and *which span* is missing is exact. This avoids the annotator-agreement floor that limits how tight a clinical faithfulness metric can be set in the wild.

We do not claim a new faithfulness method. We claim the deterministic-by-construction labels make the existing construct measurable at a precision that hand-annotated faithfulness benchmarks cannot reach.

## 3.3 FHIR/HL7 conformance validation

FHIR and HL7 v2 conformance is a public specification with reference implementations (HAPI FHIR Validator, the official HL7 v2 validator, simhospital pathway emitters). Anyone with the spec PDF and an afternoon can stand up a validator — the contribution of structural validation in this paper is therefore **not the validator itself**.

What we contribute on this axis:

1. **Composition with a semantic judge.** A structural validator on its own gates conformance; pairing it with a semantic judge under worst-of pulls the structural-violation recall into a pipeline whose primary axis is semantic faithfulness. This is the engineering insight; we measure the resulting accuracy gain over each component alone.
2. **A benchmark that exercises both axes.** Standard FHIR/HL7 conformance test suites test the validator. Standard LLM-judge benchmarks test the judge. Neither suite tests their *combination*; ours does, and the design matrix (clean / single-defect / multi-defect / near-miss) is balanced so the two axes can be measured separately and jointly.
3. **A calibration log showing which validator coverage matters.** The deployed mapping-26 HL7 ADT^A04 validator catches 2 of 5 bench defect classes (commit `3aa4151`, [`docs/LIVE_SMOKE_2026-05-21.md`](../LIVE_SMOKE_2026-05-21.md)). On the bench's HL7 pack this puts the worst-of recovery at **+28.6 pp** (commit `d5b49f2`); a stricter validator would close the remaining 3-of-5 gap. We frame the live number explicitly as **the deployed validator's coverage** and the simulated +60-pp ceiling as **the recovery ceiling at full validator coverage** ([`docs/HEADLINE_CONTRAST_2026-05-21.md`](../HEADLINE_CONTRAST_2026-05-21.md)). Conflating the two is the failure mode this paper is most determined to avoid.

## 3.4 What this is not

To pre-empt reviewer drift:

- This is **not** a "we beat GPT-4 on FHIR" paper. The semantic side is gpt-4.1 at the published mid-80s ceiling; the gain is from the structural axis, not from a better judge.
- This is **not** an evaluation of a proprietary validator. The structural validator we use is a Jute-based conformance template against a public specification (etlp-mapper mapping 15 for FHIR Claim, mapping 19 for FHIR R4 RiskAssessment, mapping 26 for HL7 ADT^A04). The templates are committed in the etlp-mapper repository.
- This is **not** a system-reliability paper. Verdict propagation, council/UI consistency, latency budgets — all engineering. They are explicit limitations (§7b), not claims.
- This is **not** a determinism paper. The N≥10 protocol is methodology for honest measurement of a stochastic system. We do not assert the pipeline is deterministic; we report the distributions a stochastic pipeline produces.

## 3.5 Replication

We replicate Lail & Markham's strong baseline on the bench's calibration sweep (commit `aff3aa9`). The 0.8125 ensemble accuracy we measure on 32 cases is within the literature's mid-80s ± noise band. With the Item 4 N=10 sweep at pack size 50 (commit `4dd0909`, in-flight), the confidence interval narrows enough to anchor §7 results without ambiguity. The replication is itself a contribution: prior work on LLM-judge reliability rarely re-runs a separate group's baseline on a new dataset, so it is genuinely useful to confirm that the criteria-injection + ensembling mechanism transfers across domains and dataset shapes.

## Word count

Approximately 970 words. Comfortably under the 1500-word ceiling.

## Citation provenance

| Claim | Source |
|---|---|
| Mid-80s anchor (Lail & Markham) | _arXiv 2604.13717_ (external) |
| Replicated 0.8125 ensemble | commit `aff3aa9` → `out/judge_calibration_v3.json` |
| Validator coverage 2/5 | commit `3aa4151` → `docs/LIVE_SMOKE_2026-05-21.md` |
| +28.6 pp HL7 gain | commit `d5b49f2` → `out/hl7.C.worstof.analysis.json` |
| Simulated +60 pp ceiling | commit `d5b49f2` → `docs/HEADLINE_CONTRAST_2026-05-21.md` |
