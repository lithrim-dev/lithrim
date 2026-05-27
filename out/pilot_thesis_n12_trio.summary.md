# Pilot N=12 — TRIO replication head-to-head

_Generated 2026-05-27 20:33_ — 12 cases, 10 defects, 2 clean negatives.

Trio: `gpt-4.1` + `Mistral-Large-3` + `Llama-4-Maverick-17B-128E-Instruct-FP8`
Compared against: prior gpt-4o × 3 council results in `out/pilot_thesis_n12.ndjson`

## Headline
- **Any-of-trio catches defect:** 10/10
- **All-three unanimously catch:** 10/10
- **False positives on clean negatives:** 2/2
- **Unanimous verdicts (any direction):** 6/12
- **Split verdicts (diversity present):** 6/12
- **Worst-of matches expected:** 9/12

## Per-model
| Model | Catches/Defects | FP/Cleans | Logprobs | Mean Conf | All Conf ≥0.999 | Conf<0.99 |
|---|---|---|---|---|---|---|
| gpt-4.1 | 10/10 | 2/2 | ✓ | 0.9304 | ✗ | 6 |
| Mistral-Large-3 | 10/10 | 2/2 | ✗ | — | — | — |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | 10/10 | 1/2 | ✓ | 0.9497 | ✗ | 5 |

## Per-case head-to-head — OLD gpt-4o×3 council vs NEW trio
| Pick | Pack | Kind | Expected | OLD compliance | NEW worst-of | OLD catch | NEW catch | Improved? |
|---|---|---|---|---|---|---|---|---|
| S1 | scribe_v1 | defect | needs_review/reject | needs_review | needs_review | ✓ | ✓ | = |
| S2 | scribe_v1 | defect | reject | reject | reject | ✓ | ✓ | = |
| S3 | scribe_v1 | defect | needs_review/reject | approve | reject | ✗ (silent) | ✓ | ✓ (caught) |
| S4 | scheduling_v1 | defect | reject | reject | reject | ✓ | ✓ | = |
| S5 | coding_v1 | defect | needs_review/reject | reject | reject | ✓ | ✓ | = |
| S6 | triage_v1 | defect | reject | reject | reject | ✓ | ✓ | = |
| S7 | hl7_adt_v1 | defect | reject | needs_review | needs_review | ✓ | ✓ | = |
| S8 | hl7_adt_v1 | defect | reject | reject | reject | ✓ | ✓ | = |
| M1 | scribe_v1 | multi | reject | reject | reject | ✓ | ✓ | = |
| M2 | scribe_v1 | multi | reject | reject | reject | ✓ | ✓ | = |
| C1 | scribe_v1 | clean | approve | approve | needs_review | (approve ok) | FP | ✗ (regressed) |
| C2 | hl7_adt_v1 | clean | approve | reject | needs_review | FP (reject) | FP | — |

## Detailed per-model verdicts (NEW trio only)
| Pick | gpt-4.1 | Mistral-Large-3 | Llama-4-Maverick |
|---|---|---|---|
| S1 | needs_review @ 0.96 `[HALLUCINATED_DETAIL]` | needs_review `[FABRICATED_HISTORY,HALLUCINATED_DETAIL,INCOMPLETE_DOCUMENTATION]` | needs_review @ 1.00 `[FABRICATED_HISTORY,HALLUCINATED_DETAIL]` |
| S2 | reject @ 0.99 `[WRONG_DOSAGE,VALUE_MISMATCH]` | reject `[WRONG_DOSAGE,VALUE_MISMATCH,INCOMPLETE_DOCUMENTATION]` | needs_review @ 1.00 `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` |
| S3 | reject @ 1.00 `[FABRICATED_HISTORY,FABRICATED_ALLERGY]` | reject `[FABRICATED_HISTORY,INCOMPLETE_DOCUMENTATION,VALUE_MISMATCH]` | reject @ 0.88 `[FABRICATED_HISTORY,FABRICATED_ALLERGY]` |
| S4 | needs_review @ 0.78 `[STRUCTURAL_MALFORMED_DATE]` | reject `[VALUE_MISMATCH,STRUCTURAL_MALFORMED_DATE]` | reject @ 1.00 `[STRUCTURAL_MALFORMED_DATE,VALUE_MISMATCH]` |
| S5 | reject @ 0.78 `[VALUE_MISMATCH]` | reject `[WRONG_CODE,VALUE_MISMATCH,STRUCTURAL_MALFORMED_DATE]` | reject @ 0.88 `[WRONG_CODE,HALLUCINATED_DETAIL,FABRICATED_HISTORY]` |
| S6 | reject @ 1.00 `[VALUE_MISMATCH,HALLUCINATED_DETAIL]` | reject `[HALLUCINATED_DETAIL,VALUE_MISMATCH,MISSED_ESCALATION,INCOMPLETE_DOCUMENTATION]` | reject @ 1.00 `[HALLUCINATED_DETAIL,WRONG_CODE,VALUE_MISMATCH]` |
| S7 | needs_review @ 0.94 `[FABRICATED_ALLERGY,STRUCTURAL_MALFORMED_DATE]` | needs_review `[STRUCTURAL_MALFORMED_DATE,VALUE_MISMATCH,FABRICATED_ALLERGY]` | needs_review @ 0.82 `[FABRICATED_ALLERGY,STRUCTURAL_MALFORMED_DATE]` |
| S8 | needs_review @ 0.99 `[FABRICATED_ALLERGY,HALLUCINATED_DETAIL]` | needs_review `[FABRICATED_HISTORY,STRUCTURAL_TRIGGER_EVENT_MISMATCH,STRUCTURAL_MALFORMED_DATE]` | reject @ 0.95 `[STRUCTURAL_TRIGGER_EVENT_MISMATCH,FABRICATED_ALLERGY]` |
| M1 | reject @ 1.00 `[FABRICATED_HISTORY,HALLUCINATED_DETAIL,WRONG_DOSAGE]` | needs_review `[HALLUCINATED_DETAIL,WRONG_DOSAGE,VALUE_MISMATCH]` | needs_review @ 1.00 `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` |
| M2 | reject @ 1.00 `[FABRICATED_HISTORY,WRONG_DOSAGE]` | reject `[FABRICATED_HISTORY,WRONG_DOSAGE,INCOMPLETE_DOCUMENTATION,VALUE_MISMATCH]` | needs_review @ 1.00 `[HALLUCINATED_DETAIL,WRONG_DOSAGE]` |
| C1 | needs_review @ 0.73 `[HALLUCINATED_DETAIL]` | needs_review `[VALUE_MISMATCH,FABRICATED_HISTORY]` | approve @ 1.00 |
| C2 | needs_review @ 1.00 `[FABRICATED_ALLERGY]` | needs_review `[STRUCTURAL_MALFORMED_DATE,VALUE_MISMATCH,FABRICATED_ALLERGY]` | needs_review @ 0.87 `[FABRICATED_ALLERGY,STRUCTURAL_MALFORMED_DATE]` |

