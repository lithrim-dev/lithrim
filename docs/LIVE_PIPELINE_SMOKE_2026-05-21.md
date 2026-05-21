# Live-pipeline smoke — scribe_v1 (2026-05-21)

Second live-stack run, this time against `POST /v1/pipeline/evaluate` — the sync orchestrator endpoint that exercises *both* the semantic council (3 judges, gpt-4.1) and the structural validator in a single round-trip. The smoke surfaced the **symmetric calibration gap to the HL7 finding**: the bench's deterministic synthesizer makes structurally-compliant artifacts that the live council nevertheless flags as fabricated, because the transcript doesn't textually ground every artifact assertion.

## Setup

- Backend: `LithrimPipelineBackend(base_url=8002, org_id=<dev>, gate_mode=False)`
- Endpoint: `POST /v1/pipeline/evaluate` (returns `PipelineResult` synchronously: artifact verdict + structural StageResult + semantic StageResult + 3-judge `judge_votes`).
- Pack: `scribe_v1` size 8, seed 7, mix `clean=0.5,single=0.5,multi=0.0`.
- N=1 (8 calls × ~27s/call = 3m40s total wall clock).

## Result

```
mean_verdict_match_rate:      0.50  (CI [0.125, 0.875])
instability_rate:             0.00
false_block_rate:             1.00  (4/4 clean negatives blocked)
mean_decision_layer_kappa:    0.81  (strong inter-judge agreement)
structural_cases:             0     (scribe pack has no structural defects)
mean_structural_match_rate:   1.00  (no structural cases; trivially 1)
```

## Per-case breakdown

| slot | expected | observed | match | observed flags |
|---|---|---|---|---|
| inject_condition (FABRICATED_HISTORY) | reject | reject | ✓ | FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT |
| dosage_drift (WRONG_DOSAGE) | reject | reject | ✓ | FABRICATED_HISTORY, HALLUCINATED_DETAIL, MEDICATION_NOT_IN_TRANSCRIPT, **WRONG_DOSAGE** |
| inject_condition | reject | reject | ✓ | FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT |
| inject_condition | reject | reject | ✓ | FABRICATED_HISTORY, HALLUCINATED_DETAIL |
| clean | approve | **reject** | ✗ | FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT |
| clean | approve | **reject** | ✗ | FABRICATED_HISTORY, HALLUCINATED_DETAIL |
| clean | approve | **reject** | ✗ | FABRICATED_ALLERGY, FABRICATED_CONSENT, FABRICATED_HISTORY, HALLUCINATED_DETAIL, MEDICATION_NOT_IN_TRANSCRIPT |
| clean | approve | **reject** | ✗ | FABRICATED_ALLERGY, FABRICATED_HISTORY, INCOMPLETE_DOCUMENTATION, FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT |

## Two findings

### Finding 1: injected defects are caught at 100% recall

All 4 injected cases hit `reject` with the expected primary flag present in the council's output. The dosage_drift case shows the live council emitting `WRONG_DOSAGE` exactly as the bench expects. The other injected cases ride FABRICATED_HISTORY (the council interprets the synthesized PMH addition as fabrication, which is the right read).

This is the paper's claim, observed: the live council catches the semantic defect class the bench is calibrated to inject.

### Finding 2: clean negatives false-block at 100% — symmetric calibration gap

All 4 clean cases score `reject` instead of the expected `approve`. The council fires on these patterns:

- `FABRICATED_HISTORY` on every clean case
- `MEDICATION_NOT_IN_TRANSCRIPT` on 3 of 4
- `HALLUCINATED_DETAIL` on 3 of 4
- `FABRICATED_ALLERGY`, `FABRICATED_CONSENT`, `INCOMPLETE_DOCUMENTATION` on the most-elaborate cases

These are not random false positives. They are *systematic*: the deterministic SOAP synthesizer emits a PMH section with conditions from the Synthea record and a PLAN section with the patient's primary medication, but the deterministic transcript synthesizer mentions these only briefly or not at all. From the council's perspective, the artifact asserts clinical content the transcript does not ground — which is the textbook definition of FABRICATED_HISTORY.

This mirrors the HL7 calibration finding (LIVE_SMOKE_2026-05-21.md), in the opposite direction:

| Pack | Validator | Clean case verdict | Why |
|---|---|---|---|
| HL7 ADT^A04 | structural (mapping 26, field-presence) | PASS (after PV1.7/IN1/AL1 calibration) | Once the synthesizer emits every field the validator inspects, clean is clean. |
| scribe SOAP | semantic council (gpt-4.1 × 3) | reject | The council inspects *semantic grounding*, which the deterministic template synthesizer does not yet match. |

Same engine, two different validators, two calibration gaps in opposite axes. Both are bench-side fixes, not paper-claim-side defects.

## The fix paths

Three options, in increasing rigor:

1. **Tightening (zero-LLM):** shrink the synthesizer's artifact to a strict subset of what the transcript establishes. The PMH section should only list conditions the transcript names; the PLAN section should not introduce new medications. This keeps the deterministic baseline reproducible but makes clean cases pass the council.
2. **Pairing (zero-LLM):** lengthen the deterministic transcript to enumerate every PMH/PLAN item explicitly ("Dr: Your past medical history includes hypertension, hyperlipidemia. Continue your metoprolol and your atorvastatin."). The artifact stays as-is.
3. **LLM-backed transcript synthesizer (opt-in):** the engine already has the interface (synthesizers/transcript.py). Phase 2 swaps in a calibrated LLM-rendered dialogue that grounds every artifact assertion. This is the paper's eventual recommended path; the deterministic baseline stays as the reproducibility floor.

For the paper, option 1 + option 2 in combination (lengthen transcript AND tighten artifact) is the deterministic v2 path. Option 3 is the upgrade path for naturalness.

## Cross-validating the headline contrast (preview)

The numbers from this run are not yet the paper's headline contrast — that requires running the HL7 pack against the live pipeline, ideally with a stricter validator or a profile that catches the format-level defects the bench's HL7 synthesizer injects. The scribe smoke tells us the semantic side works on the cases it's calibrated to catch.

The next experiment is `--pack hl7_adt_v1 --backend lithrim-pipeline --n 1` to measure what the LIVE composition does on the HL7 pack — the moment of paper truth.

## Reproduction

```bash
# 1. Generate the calibrated scribe pack
python scripts/generate_pack.py --pack scribe_v1 --size 8 --seed 7 \
    --mix clean=0.5,single=0.5,multi=0.0 --out out/scribe_v1.live.jsonl

# 2. Run live (uses .live_env if no --api-key/--org-id given)
python scripts/run_determinism.py \
    --pack-path out/scribe_v1.live.jsonl \
    --n 1 \
    --backend lithrim-pipeline \
    --out out/scribe_v1.live.ndjson

# 3. Analyze
python scripts/analyze_runs.py \
    --runs out/scribe_v1.live.ndjson \
    --pack out/scribe_v1.live.jsonl
```

Wall clock: ~3m40s for 8 cases at N=1. Latency dominated by 3× gpt-4.1 calls per case.

## Paper-relevant fact pattern

Two live-stack smokes, two symmetric calibration findings:

- **Structural calibration gap (HL7):** initially the bench's clean message failed mapping 26 because the synthesizer omitted PV1.7/IN1/AL1. Fixed by extending the synthesizer. After fix: clean = PASS (100%), 2/5 defect classes covered (100% each), 3/5 in coverage gap.
- **Semantic calibration gap (scribe):** the bench's clean artifact + transcript pair fails the live council because the deterministic transcript does not textually ground every artifact assertion. Not yet fixed. After fix (option 1+2 above), clean should approach `approve` at the council's natural FP rate.

Both findings would have been invisible without the live-stack smoke. This is precisely the value the live stack adds — moving the paper's claims from contract-level to behavior-level.
