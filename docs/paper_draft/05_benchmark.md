# §5 — Benchmark

## 5.1 Provenance and pinning

The bench is built on the **Synthea** synthetic patient cohort (Apache-2.0, publicly-distributed CSV release). All bench cases are derived from the [Synthea sample CSV release](https://synthea.mitre.org) pinned at the cohort manifest sha256 recorded in every pack's case rows. The synthesizers are deliberately **template-based, LLM-free** at v1 — both transcripts and structured artifacts are produced by deterministic Python templates that read an `EncounterSpec` (canonical pydantic model in `lithrim_bench/encounter_spec.py`, commit `bedbbfd`). The motivation is in [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md):

1. **Reproducibility.** A reviewer running `python scripts/generate_proof_case.py` gets byte-identical output to ours; no API keys, no `temperature`, no per-vendor drift.
2. **CI cost.** Lint and matrix scripts run on every change; LLM calls in the generation pipeline make CI slow and expensive.
3. **Honesty.** Synthetic transcripts are obviously synthetic at v1. That is correct: the bench tests the *verifier*, not benchmarking transcript naturalness. An LLM-backed synthesizer is a Phase 2 extension behind the same `synthesize_*` interface, opt-in.

The bench cohort and all generation logic are seeded; the cohort manifest, the seed, and the bench `git rev-parse HEAD` together pin a pack to byte-equality.

## 5.2 The five packs

The Phase 1 release covers five packs spanning the production agent surface:

| Pack | Agent type | Artifact type | Live structural validator | Injectors |
|---|---|---|---|---|
| `scribe_v1` | clinical scribe | `fhir_document_reference` (SOAP body) | none (semantic-only by design) | `WrongDosage`, `MissingAllergy`, `FabricatedHistory`, `ValueMismatch`, `HallucinatedDetail` |
| `scheduling_v1` | scheduling agent | `scheduling_action` | `scheduling-action/v1` (etlp mapping 22) | `PhiDisclosurePreVerification` |
| `coding_v1` | coding agent | `fhir_claim` | CARIN Claim Validator (etlp mapping 15) | `UpcodingRisk` |
| `triage_v1` | triage agent | `fhir_risk_assessment` | FHIR R4 RiskAssessment Validator (etlp mapping 19) | `MissedEscalation` |
| `hl7_adt_v1` | ADT^A04 emitter | `hl7_adt_a04` (raw HL7 v2 pipe-delimited text) | hl7-adt-a04-validator (etlp mapping 26) | 5 HL7-structural injectors |

`scribe_v1` is intentionally semantic-only — there is no widely-deployed SOAP-body structural validator that maps to the bench's defect classes, and a contrived validator would be circular evidence. This pack is the **negative control** for the categorical-blindness claim: a pack where the worst-of composition should approach the semantic-only baseline because the structural axis is degenerate.

`hl7_adt_v1` is the **positive control**: HL7 v2 conformance is the cleanest case of a public-spec, deterministically-checkable structural axis. The +28.6 pp worst-of gain on this pack ([`docs/HEADLINE_CONTRAST_2026-05-21.md`](../HEADLINE_CONTRAST_2026-05-21.md), commit `d5b49f2`) is the empirical center of gravity.

The three middle packs (`scheduling_v1`, `coding_v1`, `triage_v1`) are calibration territory: each carries one production-shipped structural validator with a published Jute template. The structural axis is real but partial. These packs test how the composition behaves at intermediate validator-coverage levels.

## 5.3 Deterministic-by-construction labels

Every bench case carries:

- `expected_compliance_verdict` — derived mechanically from the injection_recipe (clean → `approve`; tier-1 defect → `reject`; tier-2 → `needs_review`-or-`reject` per the taxonomy; tier-3 → `needs_review`).
- `expected_safety_flags` — a list of taxonomy codes, each ∈ `KNOWN_TAXONOMY_CODES` (lithrim-backend `compliance_council.py`). The lint script `scripts/lint_golden_against_taxonomy.py` enforces membership; any unknown code is a hard CI failure.
- `expected_artifact_verdict` — derived from the injection's structural projection (per the rule in §4.2).
- `expected_owner_map` — `{flag_code: [owning_judge, ...]}` produced by `scripts/build_label_owner_matrix.py` against the live `_TIER1_OWNERS` map. Any flag whose only owner is a judge not in the running 3-judge config is excluded from the scored set and logged.

The lint + label-owner pipeline closes defects D1 and D3 from the eval-spec's defect register ([`docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`](../EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md) §1.2, §1.3). The closure is committed on the bench side (commits `b0aa3fe`, `4eeffbc`) and on the lithrim-backend side (commits `2ca28e4`, `e94c49f`).

A pack regenerated from the same `(pack_name, size, seed, --mix)` tuple is byte-identical. The bench's reproducibility contract is enforced in `tests/test_determinism_harness.py` (74/74 tests passing as of commit `aff3aa9`).

## 5.4 The design matrix

Each pack at size N carries a slot plan, parameterized by `--mix clean=p1,single=p2,multi=p3`:

- **Clean negatives** (`p1`): no defect injected. The bench's primary measurement of `false_block_rate`. The audit ([`EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`](../EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md) §3.1) notes the original 55–58-case golden set had almost no clean negatives and an over-block miss had already happened in production. Clean negatives are non-optional.
- **Single-defect** (`p2`): one injector applied. The case is by construction defective at exactly the field/span the recipe names.
- **Multi-defect** (`p3`): two-or-more injectors applied. Tests that worst-of takes the *worst*, not an average.

Phase-2 packs (4-pack live calibration sweep used in §7) at size 8 use `clean=0.5, single=0.5, multi=0.0`. The N=10 sweep at size 50 (commit `4dd0909`, in-flight) uses the default `clean=0.4, single=0.5, multi=0.1`, giving 20 + 25 + 5 cases per pack for stratified analysis.

## 5.5 Calibration findings (Phase 2 items 1+2)

The calibration loop surfaced **two structural-validator binding errors** that would have biased §7 results if the diagnose-before-edit gate hadn't caught them:

1. **`coding_v1` synthesizer v2** omitted `provider.reference` and `insurance[].coverage.reference` on the FHIR Claim. The CARIN Claim Validator (etlp mapping 15) emitted `has_provider` + `has_insurance` failures on every clean case. The Phase 1 handoff doc misidentified the resolved mapping as 19 (it is 15); the Phase 2 kickoff doc named the missing fields as `provider.npi`, `total`, `insurance[]` — but `provider.npi` is not the validator's check (it wants `provider.reference`) and `total` is not enforced at all. The mapping-15 YAML template was the authoritative source. Bench commit `1ec493f` fixes the synthesizer; clean recall on `coding_v1` moves from 0/4 to 4/4.
2. **`triage_v1` synthesizer v2** omitted `code.coding[0]` (the SNOMED-CT system check) and `prediction[0].probabilityDecimal`. The FHIR R4 RiskAssessment Validator (mapping 19) emitted `has-condition-code` + `valid-probability` failures on every clean case. The kickoff doc named `prediction.probability` (correct concept, wrong FHIR R4 key — actual is `probabilityDecimal`), `prediction.period` (not enforced; what *is* enforced is top-level `occurrenceDateTime`, already present), and `prediction.rationale` (not enforced at all). Bench commit `1c68c55` fixes the synthesizer; clean recall on `triage_v1` moves from 0/4 to 4/4.

Both findings are documented in the commit messages and the v3 section of [`docs/JUDGE_CALIBRATION_2026-05-21.md`](../JUDGE_CALIBRATION_2026-05-21.md). The lesson the paper takes from this: **structural validator findings are the authoritative source for "what the validator requires"; secondary documentation drifts**. Future bench packs that bind to new validators should diagnose against the live finding-stream before adjusting the synthesizer.

## 5.6 What the benchmark deliberately does not include

- **LLM-generated transcripts** at v1. Phase 2 (post-paper) will add an LLM-backed synthesizer behind the same interface, opt-in.
- **Multilingual** cases. Out of scope for v1; the paper does not claim multilingual coverage.
- **Annotator-judged labels.** Every label is mechanical. A case where a label requires annotator judgment is excluded.
- **Real-world distributional realism.** Synthea is a simulator; the bench measures the *verifier*, not real-world clinical prevalence. This is named in §7b Threats to Validity.

## Word count

Approximately 1080 words. Under the 1500-word ceiling.

## Citation provenance

| Claim | Source |
|---|---|
| Synthea + Apache-2.0 | external |
| Five-pack inventory | bench `lithrim_bench/packs.py` @ commit `b259310` |
| Eleven injectors | bench `lithrim_bench/injectors/__init__.py` @ commit `0f03f04` |
| Lint + label-owner gates | bench `scripts/lint_golden_against_taxonomy.py` + `scripts/build_label_owner_matrix.py` @ commits `b0aa3fe`, `4eeffbc` |
| D1/D3 closure on backend | lithrim-backend commits `2ca28e4`, `e94c49f` |
| coding_v1 v3 fix (0/4 → 4/4) | bench commit `1ec493f` |
| triage_v1 v3 fix (0/4 → 4/4) | bench commit `1c68c55` |
| Determinism test passing | bench `tests/test_determinism_harness.py` @ commit `aff3aa9` |
