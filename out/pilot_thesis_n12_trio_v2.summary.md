# Pilot N=12 — TRIO replication head-to-head

_Generated 2026-05-27 20:47_ — 12 cases, 10 defects, 2 clean negatives.

Trio: `gpt-4.1` + `Mistral-Large-3` + `Llama-4-Maverick-17B-128E-Instruct-FP8`
Compared against: prior gpt-4o × 3 council results in `out/pilot_thesis_n12.ndjson`

## Headline
- **Any-of-trio catches defect:** 10/10
- **All-three unanimously catch:** 7/10
- **False positives on clean negatives:** 1/2
- **Unanimous verdicts (any direction):** 4/12
- **Split verdicts (diversity present):** 8/12
- **Worst-of matches expected:** 9/12

## Per-model
| Model | Catches/Defects | FP/Cleans | Logprobs | Mean Conf | All Conf ≥0.999 | Conf<0.99 |
|---|---|---|---|---|---|---|
| gpt-4.1 | 9/10 | 1/2 | ✓ | 0.9163 | ✗ | 4 |
| Mistral-Large-3 | 9/10 | 0/2 | ✗ | — | — | — |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | 7/10 | 0/2 | ✓ | 0.997 | ✗ | 1 |

## Per-case head-to-head — OLD gpt-4o×3 council vs NEW trio
| Pick | Pack | Kind | Expected | OLD compliance | NEW worst-of | OLD catch | NEW catch | Improved? |
|---|---|---|---|---|---|---|---|---|
| S1 | scribe_v1 | defect | needs_review/reject | needs_review | needs_review | ✓ | ✓ | = |
| S2 | scribe_v1 | defect | reject | reject | needs_review | ✓ | ✓ | = |
| S3 | scribe_v1 | defect | needs_review/reject | approve | reject | ✗ (silent) | ✓ | ✓ (caught) |
| S4 | scheduling_v1 | defect | reject | reject | reject | ✓ | ✓ | = |
| S5 | coding_v1 | defect | needs_review/reject | reject | needs_review | ✓ | ✓ | = |
| S6 | triage_v1 | defect | reject | reject | reject | ✓ | ✓ | = |
| S7 | hl7_adt_v1 | defect | reject | needs_review | reject | ✓ | ✓ | = |
| S8 | hl7_adt_v1 | defect | reject | reject | needs_review | ✓ | ✓ | = |
| M1 | scribe_v1 | multi | reject | reject | reject | ✓ | ✓ | = |
| M2 | scribe_v1 | multi | reject | reject | reject | ✓ | ✓ | = |
| C1 | scribe_v1 | clean | approve | approve | needs_review | (approve ok) | FP | ✗ (regressed) |
| C2 | hl7_adt_v1 | clean | approve | reject | approve | FP (reject) | (approve ok) | ✓ (fixed) |

## Detailed per-model verdicts (NEW trio only)
| Pick | gpt-4.1 | Mistral-Large-3 | Llama-4-Maverick |
|---|---|---|---|
| S1 | needs_review @ 1.00 `[HALLUCINATED_DETAIL,MISSED_ALLERGY]` | needs_review `[FABRICATED_HISTORY]` | approve @ 0.99 |
| S2 | needs_review @ 0.56 `[WRONG_DOSAGE,MISSED_ALLERGY]` | needs_review `[WRONG_DOSAGE]` | needs_review @ 1.00 `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` |
| S3 | reject @ 1.00 `[FABRICATED_HISTORY,MISSED_ALLERGY]` | needs_review `[FABRICATED_HISTORY]` | needs_review @ 0.97 `[FABRICATED_HISTORY]` |
| S4 | needs_review @ 0.94 `[HALLUCINATED_DETAIL]` | reject `[STRUCTURAL_MALFORMED_DATE]` | reject @ 1.00 `[STRUCTURAL_MALFORMED_DATE]` |
| S5 | needs_review @ 1.00 `[FABRICATED_HISTORY,WRONG_CODE]` | needs_review `[WRONG_CODE]` | needs_review @ 1.00 `[WRONG_CODE]` |
| S6 | reject @ 1.00 `[HALLUCINATED_DETAIL]` | reject `[FABRICATED_HISTORY,MISSED_ESCALATION,VALUE_MISMATCH]` | reject @ 1.00 `[MISSED_ESCALATION,HALLUCINATED_DETAIL]` |
| S7 | approve @ 1.00 | reject `[STRUCTURAL_MALFORMED_DATE,STRUCTURAL_TRIGGER_EVENT_MISMATCH]` | approve @ 1.00 |
| S8 | needs_review @ 0.82 `[STRUCTURAL_TRIGGER_EVENT_MISMATCH]` | approve | approve @ 1.00 |
| M1 | reject @ 1.00 `[FABRICATED_HISTORY,HALLUCINATED_DETAIL,WRONG_DOSAGE,MISSED_ALLERGY]` | needs_review `[FABRICATED_HISTORY]` | needs_review @ 1.00 `[FABRICATED_HISTORY,WRONG_DOSAGE]` |
| M2 | reject @ 0.68 `[WRONG_DOSAGE,MISSED_ALLERGY,HALLUCINATED_DETAIL]` | needs_review `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` | needs_review @ 1.00 `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` |
| C1 | needs_review @ 1.00 `[MISSED_ALLERGY]` | approve | approve @ 1.00 |
| C2 | approve @ 1.00 | approve | approve @ 1.00 |

