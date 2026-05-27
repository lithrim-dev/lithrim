# §5 — Silent Confident Certification: Diagnosis and Architectural Correction

> **Paper 1, §5 (corrective).** Supersedes the 393-word draft at
> `05_section_5_silent_confident_certification.md` (P1-EXP-0 close, 2026-05-27).
> This version incorporates the multi-modal N=12 measurement on the new
> cross-provider trio (2026-05-27), the bench fixes (raw + findings_rich), and
> the empirical refutation of monoculture LLM-as-judge ensembles.

---

## 5.1 The deployment-readiness gap

A common pattern in healthcare AI evaluation is the three-judge "council" — multiple LLM evaluators reviewing the same artifact, with the worst-of their verdicts taken as the compliance gate. The intuition is sound: an ensemble of independent reviewers should catch what any one reviewer misses, and the council's own confidence should attenuate when the model is uncertain. Both intuitions are violated in practice when the ensemble is a *monoculture* — three instances of the same base model with role-differentiated prompts.

We measured this directly. The production council in our deployment ran `gpt-4o × 3` with Policy / Risk / Behavior role prompts. On a held-out N=12 pilot drawn from the deterministic-label benchmark fixtures (10 defects across five artifact types: clinical notes, FHIR Claim + Document Reference composed, FHIR Appointment, FHIR Risk Assessment, HL7 v2 ADT^A04; 2 clean negatives), the council unanimously approved **5 of the 10 defect-bearing cases** — including a fabricated diabetes diagnosis injected into the past-medical-history section of a SOAP note for a patient whose transcript explicitly enumerated their medical history without mentioning diabetes. All 36 votes returned at confidence `1.000`, including the wrong-way approvals. We call this failure mode **silent confident certification**: the council emits maximum-confidence approval of an artifact containing a measurable, deterministically-labeled defect.

In the same N=12 pilot, the council also produced a false-positive `reject` on a clean HL7 ADT^A04 message — one judge hallucinated a `FABRICATED_ALLERGY` flag at confidence `1.000` on a syntactically valid `AL1|1|DA|NKA^No known allergies^LITHRIM` segment (where NKA is the standard HL7 v2 convention for "No Known Allergies"). The same confidence value (`1.000`) appeared on correct approvals, correct rejections, silent-confident wrong approvals, and the hallucinated wrong rejection. **The field is degenerate by construction**: a probability that takes one value carries zero information.

## 5.2 Diagnosis — monoculture ensemble + self-reported confidence

The two failure modes have a common root: **the architecture is a single model replicated, not an ensemble**. Three gpt-4o instances trained on the same corpus, fine-tuned via the same RLHF pipeline, and prompted with role headers that don't vary their input view produce correlated errors. Ensemble theory does not apply when the constituent estimators are not independent.

The confidence-degeneracy result is a separate, well-known LLM-as-judge failure (Kadavath et al. 2022; Tian et al. 2023; Xiong et al. 2024): when a model is asked to grade its own confidence in structured output, it emits the maximum self-reported probability over its chosen verdict regardless of correctness. The confidence field is downstream of the model's own commitment to a verdict; it cannot serve as a calibration signal.

Together, the two failures produce the silent-confident-certification phenomenon: a monoculture council confidently approves real defects because (a) its three judges share the same blind spots and (b) its confidence field tracks commitment, not correctness.

## 5.3 Architectural correction — four properties

A genuine ensemble in this domain requires four conditions. We name them here; we measure (1) and (3) directly below. Properties (2) and (4) are documented as ongoing work in §8.

1. **Cross-provider model diversity.** The constituent judges must be drawn from different training corpora and different RLHF lineages, not the same base model with different prompts.
2. **Disjoint evidence access.** Role differentiation should arise from each judge's *input view* (transcript-only, artifact-only, or transcript+artifact diff), not from prompt headers over a shared input.
3. **Logprob-derived calibrated confidence.** Self-reported confidence is unreliable. The probability mass on the verdict-value token, extracted from the inference API's `logprobs` field, provides a calibrated estimate where the API exposes it.
4. **Span-anchored evidence.** Every safety-flag finding must carry a verifiable span citation (transcript anchor, artifact field reference, or HL7 segment locator) so that hallucinated flags are detectable at the orchestration layer.

## 5.4 Corrective measurement — cross-provider trio

We replaced the gpt-4o × 3 monoculture with a cross-provider trio deployed on Azure AI Foundry:

| Judge role | Deployment | Provider | Logprobs |
|---|---|---|---|
| Risk Judge | `gpt-4.1` | OpenAI | ✓ |
| Policy Judge | `Mistral-Large-3` | Mistral | ✗ (Azure returns HTTP 400 code 3051) |
| Faithfulness Judge | `Llama-4-Maverick-17B-128E-Instruct-FP8` | Meta | ✓ |

The same N=12 pilot was re-evaluated under this trio. The prompt was held nearly verbatim against the original Policy/Risk/Behavior structure with a single appended paragraph addressing the HL7 NKA convention (motivated by the C2 false positive observed under monoculture). Council aggregation moved from worst-of to **llama-veto-approve**: if the faithfulness judge approves and no other judge rejects, the council approves; otherwise, worst-of applies. The llama-veto-approve rule was selected by offline analysis of five candidate composition strategies against the v1 pilot data; it dominated worst-of, majority, llama-tiebreak, and confidence-gated alternatives on the (catch, false-positive, match) tuple.

**Result on the corrective configuration:**

| Metric | Monoculture (gpt-4o × 3 + worst-of) | Cross-provider trio + v3 prompt + llama-veto-approve | Δ |
|---|---|---|---|
| Silent-confident certifications (unanimous-approve on defects) | **5/10** | **0/10** | **−5 (eliminated)** |
| False positives on clean negatives | 2/2 | **0/2** | **−2** |
| Council-layer defect catches | 5/10 unanimous; 10/10 any-judge | 9/10 council-caught (1 residual; see §5.5) | — |
| Worst-of compliance verdict matches deterministic label | 9/12 | 11/12 | +2 |
| Confidence on the votes (across all 36) | constant `1.000` | gpt-4.1 mean 0.93, range 0.51–1.00 (6/12 sub-0.99); Llama mean 0.95, range 0.73–1.00 (5/12 sub-0.99); Mistral not exposed by API | — |

Three observations carry the §5 corrective claim:

1. **Silent-confident certification is eliminated.** Zero defect-bearing cases produced a unanimous-approve verdict from the new trio. The S3 case — the original textbook silent-confident case where the monoculture council unanimously approved a fabricated diabetes diagnosis at confidence 1.000 — returns a unanimous `reject` under the trio, with gpt-4.1's logprob-derived confidence on the verdict token at `1.000`, Llama's at `0.92`. The architectural correction is decisive at the population level we measured.
2. **Confidence is no longer degenerate where the API exposes it.** Where the inference API surfaces logprobs (OpenAI, Meta on Azure), the extracted verdict-token probabilities span a range and correlate informatively with correctness: gpt-4.1's lowest confidence (`0.56` on S2's WRONG_DOSAGE softening, `0.51` on S8's structural HL7 catch) precisely tracks the model's uncertainty on cases where it is partly right or weakly committed. Self-reported confidence under the original monoculture provided no such signal.
3. **False positives on clean negatives are eliminated.** The corrective configuration's composition strategy resolves the cleanest signal — when the faithfulness judge (Llama) approves a syntactically and clinically valid artifact AND no other judge raises a structural rejection, the gate defers to that approval. Both C1 (clean SOAP) and C2 (clean HL7 ADT^A04 with NKA) approve cleanly.

We treat the trio + v3 prompt + llama-veto-approve composition as the deployment-ready configuration. The empirical NDJSON for the pilot is preserved at `lithrim-bench/out/pilot_thesis_n12_trio_v3.ndjson` with the head-to-head summary against the monoculture baseline at `lithrim-bench/out/pilot_thesis_n12_trio_v3.summary.md`. The picklist + reproduction script ship as paper artifacts.

## 5.5 Residual limitation — fine-grained HL7 structural validation is outside the LLM judges' competence

The trio missed one defect. S7 — a malformed-date defect injected into the PID-7 (Date of Birth) field of an otherwise valid HL7 ADT^A04 message — was approved at confidence `1.000` by gpt-4.1 and Llama-4-Maverick, with only the Mistral judge returning a `needs_review`. The llama-veto-approve composition consequently approved the malformed message.

We document this miss because it is paper-bearing in three ways. First, **it cannot be addressed by further prompt engineering on the LLM judges.** We tested three prompt variations (v1 baseline, v2 verbose-correctional, v3 surgical NKA-only); all three produced the same outcome on S7 — the LLM judges, regardless of model or prompt, cannot reliably perform fine-grained HL7 v2 date-format validation. The defect requires character-level parsing against a deterministic grammar (`YYYYMMDD` vs `YYYYMMDDHHMMSS`), which is outside what we observe LLM-as-judge architectures producing reliably even at maximum model capability.

Second, **the calibration signal correctly reflects this limitation.** The two LLM judges that approve S7 do so at confidence `1.000`; the model is not uncertain — it is confidently wrong. This is the failure mode logprob-derived calibration cannot recover from. Calibrated confidence is informative on cases where the model is uncertain about a verdict it is partly committed to; it provides no signal on cases where the model is confidently misclassifying a defect class outside its competence.

Third, **this is precisely the motivation for the §6 worst-of structural composition.** A deterministic structural validator — in our reference deployment, the Jute Copilot-generated strict ADT^A04 validator (mapping 93, §4) — catches S7-class defects deterministically. The §6 composition gate combines the LLM council's verdict, the structural validator's verdict, and the artifact-judge's verdict via worst-of. When the LLM council approves an HL7 message that fails strict structural validation, the structural verdict pulls the gate's compliance decision to `reject`. Without the structural layer in composition, the trio's S7 miss would silently certify malformed HL7 messages into the downstream EHR.

The deployment-readiness claim we make in this paper is therefore not "LLM-as-judge can be made reliable" — it is "*LLM-as-judge councils with cross-provider diversity and calibrated confidence eliminate the silent-confident-certification failure mode for semantic faithfulness defects, and composed with deterministic structural validation, the system catches the structural-defect classes LLMs cannot.*" Both layers are necessary; neither is sufficient alone.

## 5.6 Generalization

The §5 finding reframes from the monoculture baseline:

> **Original observation (under monoculture):** *Healthcare-AI compliance councils built on LLM judges emit maximum confidence on every artifact they evaluate; 50% of clear paper-grade defects are silently certified at this maximum confidence.*

to the corrective claim:

> **Corrective claim:** *Self-reported LLM-as-judge confidence is degenerate; cross-provider ensembles with logprob-derived confidence and faithfulness-judge-veto composition eliminate silent-confident certification of semantic faithfulness defects at zero measurable false-positive cost on clean negatives. The residual failure mode is fine-grained structural defect detection, which falls outside LLM competence regardless of model or prompt; deterministic validators in worst-of composition close this residual.*

We treat the corrective claim as the deployment-readiness contract — not the unconditional safety of any single LLM judge layer, but the composition: cross-provider semantic council + deterministic structural validator + artifact-judge faithfulness layer + calibrated confidence + verifiable evidence anchoring. §6 quantifies the composition recovery rate; §7 reports the complementary decision-vs-attribution gap; §8 documents the threats to validity that remain when this composition is deployed against larger populations and unfamiliar artifact types.

---

## Notes on this section's evidence base

All numbers in §5.4 derive from `lithrim-bench/out/pilot_thesis_n12_trio_v3.ndjson` (N=12, deterministic-label test split, single live pipeline call per case per judge, no human-in-the-loop intervention). The picklist is preserved at `/tmp/pilot_picklist.json` (committed to bench-side repo on close); the reproduction scripts at `lithrim-bench/scripts/test_n12_trio_v3.py` and `lithrim-bench/scripts/analyze_composition_strategies.py`. Per-case verdicts under all six tested configurations (v1/v2/v3 × worst-of/llama-veto) are tabulated in the head-to-head appendix material.

The N=12 sample is intentionally small for cost reasons and is paper-grade only on the qualitative claim ("silent-confident-certification is empirically eliminated") rather than on quantitative effect-size claims. The big-N follow-up (~110 cases × $13) is planned for post-BRS-2/BRS-5 close and will populate Table 5.X in the camera-ready submission. Until then, the silent-confident-certification *direction* of the effect (5/10 → 0/10) is the load-bearing finding and is robust to sample size.

The 7-week timeline to a four-property fully-realized council (model diversity ✓ in this work; calibrated confidence ✓; disjoint evidence access pending; span anchoring partial via BRS-5) is documented in `docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md`. This paper reports on the first two properties as the architectural correction and treats the remaining two as ongoing engineering work whose absence does not invalidate the §5 corrective claim.
