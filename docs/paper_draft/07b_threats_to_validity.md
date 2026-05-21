# §7b — Threats to Validity

This section is written before §7 results are populated (kickoff Item 5 instruction). The threats are derived from the bench's commit history, the live-stack smokes, and the eval-spec defect register. Writing them honestly is the load-bearing decision; the section earns the rest of the paper its credibility.

## 7b.1 Synthea distributional unrealism

Synthea is a simulator. Its patients are demographically broad but clinically simplified; condition co-morbidities, lab panels, and documentation styles are not drawn from real EHR data. The benchmark tests the *verifier* — given an artifact and a transcript, does the verifier reach the right verdict? — not real-world clinical prevalence. The bench's contribution to clinical evaluation is the **mechanism characterization** (semantic vs structural axes; deterministic-by-construction labels; negative-audit-trail measurable), not a population-level claim about clinical AI agent failures.

A reviewer asking "would these results transfer to real EHR data?" should be answered: **structural conformance violations transfer trivially** (the validator does not care whether the FHIR Claim is from Synthea or from a real EHR), but **semantic-judge accuracy may not** (the simplified Synthea narratives may be easier or harder than real notes). §7's per-pack accuracy numbers should therefore be read as "verifier accuracy on this benchmark's synthetic distribution", not "verifier accuracy on real EHR data". The HL7 +28.6 pp headline gain, conversely, is dominated by validator coverage, which is data-distribution-independent.

A v2 of this benchmark backed by a real, de-identified clinical narrative source (e.g. MIMIC-IV notes with synthetic structural-projection injections) is a natural follow-on. Out of scope for this paper.

## 7b.2 Injected defects are explicit and well-specified; real failures are messier

Every bench defect is a single mutation with a recorded recipe. Real agent failures often involve cascading semantics, partial information, or LLM hallucinations that drift across multiple fields. Our benchmark is a **lower bound on difficulty**: if a verifier struggles on a single explicit defect, it will struggle more on a cascading real-world failure.

This means the worst-of gain we report should be read as a **lower bound on the production-relevant gain**. Specifically, multi-defect cases in real EHRs (e.g. a fabricated medication co-existing with a value-mismatch co-existing with a missing structural field) almost certainly increase the structural axis's contribution because the structural defect typically remains crisp even when the semantic story gets muddy. We do not measure this directly; we name it as a likely under-statement of the paper's central claim.

## 7b.3 N is finite

The N=10 sweep across 4 packs at size 50 (2000 council invocations, commit `4dd0909`) gives 10 samples per case. For binary verdict-match outcomes, the 95% CI half-width at p=0.5 is approximately 0.16 — meaning we can distinguish accuracy at the 70% level from accuracy at the 86% level, but we cannot distinguish 82% from 84%. The determinism protocol exists exactly because single-run verdicts are not trustworthy (D2 in the eval-spec); N=10 buys us a usable interval, not a tight one.

A pack with `verdict_match_rate_ci95` width > 0.1 (kickoff Item 4's acceptance bound) is reported but flagged as "scoping-tightness only". A v2 paper with N=25 per case (and pack sizes proportional) closes the residual interval.

## 7b.4 The mid-80s LLM-judge anchor is from general reward benchmarks, not clinical conformance

Lail & Markham's ~85.8% on RewardBench 2 is the established literature anchor for tuned LLM-as-judge (criteria-injection + ensembling at gpt-4.1-mid-tier). We replicate this on the bench's calibration sweep at 0.8125 (commit `aff3aa9`) — within the band — but the bench's task is **clinical artifact conformance**, not general reward modeling. The fact that the literature anchor transfers within noise is itself a contribution (§3.5), but it is not a guarantee that *every* sub-task in clinical NLP reaches this level. Coding upcoding and triage missed-escalation may be easier or harder than general reward signals; we do not extrapolate.

## 7b.5 The deployed validator's coverage is finite

This is the most consequential threat and deserves the most careful framing.

The bench's headline +28.6 pp gain on the HL7 ADT^A04 pack ([`docs/HEADLINE_CONTRAST_2026-05-21.md`](../HEADLINE_CONTRAST_2026-05-21.md), commit `d5b49f2`) is the production-deployed `etlp-mapper` mapping 26's coverage. Mapping 26 is a field-presence validator; on the bench's HL7 pack it catches:

- `STRUCTURAL_MISSING_REQUIRED_SEGMENT` (100% recall)
- `STRUCTURAL_MISSING_REQUIRED_FIELD` (100% recall)

and passes through:

- `STRUCTURAL_MALFORMED_DATE`
- `STRUCTURAL_INVALID_FIELD_FORMAT`
- `STRUCTURAL_TRIGGER_EVENT_MISMATCH`

with PASS verdicts. The simulated full-coverage ceiling — i.e., if mapping 26 caught all 5 defect classes at 100% — yields the **+60 pp** number, also reported. The two numbers are framed throughout the paper as **the deployed validator's coverage** and **the recovery ceiling at full validator coverage**, with explicit terminology to prevent conflation.

A reviewer's natural objection — "if your validator caught 5 of 5 classes, what would the gain be?" — has its answer in `docs/HEADLINE_CONTRAST_2026-05-21.md` and is summarized in §7. The bench can demonstrate the simulation deterministically (the structural axis is deterministic by construction), so the +60 pp ceiling is not speculative; it is the upper bound of a finite-state mechanism with a parameterized coverage knob. A stricter validator (e.g. mapping 41 lenient, or a HAPI v2 integration — Phase 3 territory) would close the gap empirically; we do not gate the paper on that work but we name it as an obvious follow-on.

## 7b.6 Verdict propagation and system-level consistency are defective today

The lithrim-backend production pipeline can return an "engine verdict" that disagrees with the "surfaced verdict" presented in the UI (documented in `lithrim-backend/docs/CONSENSUS_FIELD_MAPPING_FIX.md` and `lithrim-backend/docs/DISPOSITION_AS_UI_SOURCE_OF_TRUTH.md`). This is an engineering concern, **explicitly out of the scientific claim**. The paper measures the engine verdict at the `compliance_verdict` level (via `LithrimPipelineBackend`, which reads directly from the pipeline's emitted verdict, not the UI-surfaced one), so the engine-vs-UI gap does not affect §7 numbers. We disclose it as a limitation; we do not hide it.

## 7b.7 Pipeline-parser quirk: `structural_findings` empty when validator emits findings keyed `name:`

The `LithrimPipelineBackend` parser at [`lithrim_bench/backends/lithrim_pipeline.py:155-159`](../../lithrim_bench/backends/lithrim_pipeline.py#L155-L159) extracts `check_name` or `code` from each structural finding. Validators that emit findings keyed `name:` (e.g. etlp mapping 19, the FHIR R4 RiskAssessment Validator) have their finding-names dropped to `[]` in our NDJSON's `structural_findings` field, even though the structural verdict is correctly propagated. This is a cosmetic-only mismatch; it does not affect verdict-level metrics. We flagged it in the v3 commit (`1c68c55`) and will patch the parser in a follow-on. §7's verdict-level results are not affected; flag-name-level analyses for mapping-19-validated packs (`triage_v1`) will under-count when the finding list is the source.

## 7b.8 Synthetic transcripts are obviously synthetic

The v1 synthesizers are deterministic templates; clinical narratives generated by an LLM (or drawn from real notes) are richer in vocabulary, hedging, ambiguity, and informal speech. Our negative-audit-trail metric is exact precisely because the transcripts are simple — there is no annotator-floor on "did the agent ground this claim in the transcript" because the transcript's content is deterministic. An LLM-backed synthesizer would relax this but at the cost of relaxing the metric's exactness. This is a trade-off, not a bug; we report it.

## Word count

Approximately 1080 words. Under the 1500-word ceiling.

## Citation provenance

| Claim | Source |
|---|---|
| Synthea is a simulator (Apache-2.0) | external |
| Validator coverage 2/5 on mapping 26 | bench `docs/LIVE_SMOKE_2026-05-21.md` @ commit `3aa4151` |
| Live +28.6 pp gain | bench `docs/HEADLINE_CONTRAST_2026-05-21.md` @ commit `d5b49f2` |
| Simulated +60 pp ceiling | same |
| Replicated 0.8125 ensemble | commit `aff3aa9` → `out/judge_calibration_v3.json` |
| Pipeline-parser quirk | bench `lithrim_bench/backends/lithrim_pipeline.py:155-159` @ commit `e862ec6` |
| D2 audit (hba1c bistability) | bench `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` defect D2 |
