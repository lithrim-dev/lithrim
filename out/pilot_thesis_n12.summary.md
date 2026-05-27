# Pilot — N=12 thesis-validation summary

_Generated 2026-05-27 18:31_ — 12 cases, 10 defects, 2 clean negatives.

## Headline
- **Silent-confident (council-layer):** 5/10 defects (50.0%)
- **Silent-confident (pipeline-layer):** 1/10 defects
- **Council verdict match (vs deterministic label):** 9/12
- **Artifact verdict match:** 8/12
- **All judge confidences == 1.0:** True
- **Mean per-judge confidence:** 1.0
- **Data-point checklist pass:** 12/12

## Per-case results
| Pick | Pack | Defect? | Compliance | Artifact | Structural | Expected | Unanim≈ | min/max conf | Silent (C/P) | Match | DataOK |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | scribe_v1 | defect | needs_review | WARN | PASS | needs_review/reject | ✓A | 1.00/1.00 | 1/0 | ✓ | ✓ |
| S2 | scribe_v1 | defect | reject | BLOCK | PASS | reject | ✓R | 1.00/1.00 | 0/0 | ✓ | ✓ |
| S3 | scribe_v1 | defect | approve | PASS | PASS | needs_review/reject | ✓A | 1.00/1.00 | 1/1 | ✗ | ✓ |
| S4 | scheduling_v1 | defect | reject | BLOCK | PASS | reject | ✓A | 1.00/1.00 | 1/0 | ✓ | ✓ |
| S5 | coding_v1 | defect | reject | BLOCK | PASS | needs_review/reject | ✓R | 1.00/1.00 | 0/0 | ✓ | ✓ |
| S6 | triage_v1 | defect | reject | BLOCK | PASS | reject | ✓R | 1.00/1.00 | 0/0 | ✓ | ✓ |
| S7 | hl7_adt_v1 | defect | needs_review | WARN | WARN | reject | ✓A | 1.00/1.00 | 1/0 | ✗ | ✓ |
| S8 | hl7_adt_v1 | defect | reject | BLOCK | BLOCK | reject | ✓A | 1.00/1.00 | 1/0 | ✓ | ✓ |
| M1 | scribe_v1 | multi | reject | BLOCK | PASS | reject | ✓R | 1.00/1.00 | 0/0 | ✓ | ✓ |
| M2 | scribe_v1 | multi | reject | BLOCK | PASS | reject | ✓R | 1.00/1.00 | 0/0 | ✓ | ✓ |
| C1 | scribe_v1 | clean | approve | PASS | PASS | approve | ✓A | 1.00/1.00 | 0/0 | ✓ | ✓ |
| C2 | hl7_adt_v1 | clean | reject | BLOCK | PASS | approve | split | 1.00/1.00 | 0/0 | ✗ | ✓ |

## Data-point checklist failures
- _All picks passed the data-point checklist._
