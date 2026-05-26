# P1-EXP-0: Council confidence on silent-confident HL7 defects

**Source:** `out/p1_exp_0_council_confidence.ndjson` (N=1)
**Pack:** `out/hl7_adt_v1.jsonl` (40 cases: 12 clean + 28 defect; all defects expect `reject`)
**Validator:** mapping 93 (strict HL7 ADT^A04, Jute Copilot output)

## Counts

- Total rows in NDJSON: **40**
- Error rows: **0**
- Clean negative cases: **12**
- Defect-bearing cases: **28**
- **Council-silent subset** (defect + council unanimous-approve — the §5 measurement): **10 / 28** (35%)
- Pipeline-silent subset (council-silent AND pipeline gate=approve — driver §2 D3 literal filter, audit only): **0 / 28**

## §5 subset-definition deviation (logged for audit)

The driver's literal filter requires `compliance_verdict == 'approve'` — but `compliance_verdict` is the pipeline gate AFTER structural composition (the §6 solution). Filtering the §5 failure-mode population through its own solution yields 0 by construction, regardless of council calibration. Per PAPER_FRAMING_DECISIONS_2026-05-26.md A1, §5 is a council-layer statement ("the council silently and confidently certifies spec-violating clinical artifacts"), so the right filter drops the pipeline-gate clause and keeps only the council-unanimous-approve condition on defect-bearing rows. User-approved deviation 2026-05-27 (option A in the halt+surface).

## Council agreement breakdown on the 28 defects

- unanimous_approve: **10**
- split: **15**
- unanimous_reject: **3**
- other: **0**

## Structural verdict on the 28 defects (mapping 93)

- WARN: **21**
- BLOCK: **7**

## What the pipeline gate did with the council-silent subset

On the council-silent subset — defects every judge approved at this confidence — the composed pipeline gate (worst-of with mapping 93) was driven by the structural side to the following dispositions:

- `compliance_verdict=needs_review`: **10**

Structural verdict on the same subset:
- `structural_verdict=WARN`: **10**

## Per-judge confidence on the council-silent subset

| Judge | n | mean | median | p25 | p75 | min | max | modal bucket |
|---|---|---|---|---|---|---|---|---|
| policy_judge | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9-1.0 |
| risk_judge | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9-1.0 |
| behavior_judge | 10 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9-1.0 |

### Histograms (0.1-wide buckets)

**policy_judge**
  `0.9-1.0` ██████████ (10)

**risk_judge**
  `0.9-1.0` ██████████ (10)

**behavior_judge**
  `0.9-1.0` ██████████ (10)

## §5 headline (draft, plug into paper_draft/05_section_5_…)

> On the 10 HL7 ADT^A04 defects (35% of 28) that the live council unanimously approved, per-judge mean confidence was {policy: 1.000, risk: 1.000, behavior: 1.000}; the histogram is concentrated in policy in 0.9-1.0, risk in 0.9-1.0, behavior in 0.9-1.0. The generated HL7 ADT^A04 conformance validator (Jute Copilot mapping 93) flagged every one of those silent cases: `structural_verdict=BLOCK` on 0, `WARN` on 10, 0 silent.
