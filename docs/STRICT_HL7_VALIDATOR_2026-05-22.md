# Stricter HL7 ADT^A04 validator — Phase 2 Item 6

**Date:** 2026-05-22
**Status:** generated, validated, registered as etlp-mapper mapping **93**.

Closes the HL7 structural-coverage gap documented in
`HEADLINE_CONTRAST_2026-05-21.md`: the deployed validator (mapping 26)
caught 2 of 5 bench defect classes; the stricter validator catches
all 5.

## How it was generated

Per the kickoff Item 6 plan, the stricter mapping was generated via
the **etlp-mapper Jute Copilot** (`POST /mappings/generate`), not
hand-written — the request is reproducible in
`scripts/_gen_strict_hl7_mapping.py`.

- **Mode:** extend (`existing_template` = mapping 26's YAML), so the
  copilot built on the 16 working presence checks rather than from
  scratch.
- **Scope:** common, widespread, standard HL7 v2.x ADT^A04
  conformance — not site-specific customization. (Real health-system
  deployments customize heavily; the copilot exists for that. For the
  paper we deliberately stay on the common standard.)
- **Result:** `confidence: partial`, compiled clean, 2 retries. The
  generated template is committed at
  `validators/hl7_adt_a04_strict.yaml` and registered as mapping 93.

## What it adds over mapping 26

Mapping 26 is **presence-only** — every check tests that a field
exists. It cannot catch a field that is present but malformed. The
strict validator keeps all 16 presence checks and adds 3
format/value-set checks:

| New check | Field | Rule |
|---|---|---|
| `dob-format-valid` | PID-7 | date of birth must be a valid 8-digit YYYYMMDD value |
| `gender-value-valid` | PID-8 | administrative gender must be in HL7 Table 0001 `{A,F,M,N,O,U}` |
| `trigger-event-consistent` | EVN-1 | EVN event type code must equal the MSH-9 trigger event |

Total: 19 checks (16 presence + 3 format/value/consistency).

## Coverage measurement (bench HL7 pack, 40 cases, N=1)

| Validator | Clean PASS | Defects caught | Classes at 100% |
|---|---|---|---|
| mapping 26 (deployed, presence-only) | 12/12 | **8/28** (28.6%) | 2/5 |
| mapping 93 (strict, this work) | 12/12 | **28/28** (100%) | **5/5** |

Per defect class with mapping 93:

```
malformed_date          11/11
missing_segment          4/4
invalid_field_format     2/2
missing_required_field   4/4
trigger_event_mismatch   7/7
```

## Headline contrast, updated

| System | Defects caught | Clean correct |
|---|---|---|
| tuned-mock alone (semantic, structural-blind) | 0/28 | 12/12 |
| structural-only — mapping 26 (deployed) | 8/28 (28.6%) | 12/12 |
| structural-only — mapping 93 (strict) | **28/28 (100%)** | 12/12 |
| worst-of(tuned-mock, mapping 93) | **28/28 (100%)** | 12/12 |

The composition gain with the strict validator is **+100 pp** of
structural-defect catch over the tuned-semantic baseline (0/28 →
28/28). `HEADLINE_CONTRAST_2026-05-21.md` projected a simulated
"+60 pp ceiling at full validator coverage"; the strict validator
empirically realizes — and exceeds — that ceiling, because all five
bench defect classes are deterministically checkable HL7 v2
conformance rules.

The paper should report both numbers with explicit framing:
- **deployed-validator coverage** (mapping 26): +28.6 pp — what a
  field-presence validator delivers today.
- **full-conformance coverage** (mapping 93): +100 pp — what a
  standard-scope conformance validator delivers. No longer a
  simulation; measured against a real Jute validator.

## Injector bug found and fixed (diagnose-before-edit)

While validating mapping 93, the `trigger_event_mismatch` class read
0/7 even though the new `trigger-event-consistent` check was correct.
Evidence: a parsed trigger-mismatch message showed MSH-9 still
`ADT^A04` and MSH-10 carrying the injected `ADT^A99`.

`Hl7TriggerEventMismatchInjector` wrote `msh[9]`, but in the
pipe-split MSH field list MSH-9 sits at **index 8** (MSH-1 is the
field separator itself, offsetting the list by one). The injector
was corrupting MSH-10 (message control id) and leaving the trigger
event intact — so the "trigger event mismatch" class never injected
a mismatch. This is why *neither* mapping 26 *nor* mapping 93 caught
it before the fix. Fixed to write `msh[8]`; regression test added
(`test_trigger_event_mismatch_injector_corrupts_msh9_not_msh10`).
After the fix, trigger_event_mismatch reads 7/7.

## Reproduction

```bash
# 1. Generate the stricter template via the copilot
python scripts/_gen_strict_hl7_mapping.py        # writes out/strict_hl7_adt_a04.yaml

# 2. Register it (idempotent — creates a new mapping id each call)
#    POST /mappings {title, content:{tags,yaml,test_data}}  -> mapping 93

# 3. Measure coverage
python scripts/run_determinism.py --pack-path out/hl7_adt_v1.jsonl --n 1 \
    --backend lithrim-validate-artifact --etlp-mapping-id 93 \
    --out out/hl7.strict.struct.ndjson

# 4. Worst-of contrast
python scripts/run_determinism.py --pack-path out/hl7_adt_v1.jsonl --n 1 \
    --backend worst-of --worst-of-semantic tuned-mock \
    --tuned-per-member-accuracy 0.802 --tuned-flag-attachment-rate 0.218 \
    --worst-of-structural lithrim-validate-artifact --etlp-mapping-id 93 \
    --out out/hl7.strict.worstof.ndjson
```

The committed template `validators/hl7_adt_a04_strict.yaml` is the
frozen artifact; step 1 regenerates it (copilot output is not
byte-deterministic, so the committed copy is the reference).
