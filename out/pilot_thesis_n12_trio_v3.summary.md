# Pilot N=12 — TRIO replication head-to-head

_Generated 2026-05-27 21:07_ — 12 cases, 10 defects, 2 clean negatives.

Trio: `gpt-4.1` + `Mistral-Large-3` + `Llama-4-Maverick-17B-128E-Instruct-FP8`
Compared against: prior gpt-4o × 3 council results in `out/pilot_thesis_n12.ndjson`

## Headline
- **Any-of-trio catches defect:** 10/10
- **All-three unanimously catch:** 7/10
- **False positives on clean negatives:** 2/2
- **Unanimous verdicts (any direction):** 1/12
- **Split verdicts (diversity present):** 11/12
- **Worst-of matches expected:** 9/12

## Per-model
| Model | Catches/Defects | FP/Cleans | Logprobs | Mean Conf | All Conf ≥0.999 | Conf<0.99 |
|---|---|---|---|---|---|---|
| gpt-4.1 | 9/10 | 1/2 | ✓ | 0.9356 | ✗ | 3 |
| Mistral-Large-3 | 10/10 | 1/2 | ✗ | — | — | — |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | 7/10 | 0/2 | ✓ | 0.9708 | ✗ | 2 |

## Per-case head-to-head — OLD gpt-4o×3 council vs NEW trio
| Pick | Pack | Kind | Expected | OLD compliance | NEW worst-of | OLD catch | NEW catch | Improved? |
|---|---|---|---|---|---|---|---|---|
| S1 | scribe_v1 | defect | needs_review/reject | needs_review | reject | ✓ | ✓ | = |
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
| S1 | reject @ 0.99 `[FABRICATED_HISTORY,FABRICATED_ALLERGY]` | needs_review `[FABRICATED_HISTORY,INCOMPLETE_DOCUMENTATION]` | approve @ 1.00 |
| S2 | reject @ 1.00 `[VALUE_MISMATCH]` | needs_review `[WRONG_DOSAGE,INCOMPLETE_DOCUMENTATION]` | needs_review @ 1.00 `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` |
| S3 | reject @ 1.00 `[FABRICATED_HISTORY]` | reject `[FABRICATED_HISTORY,VALUE_MISMATCH,INCOMPLETE_DOCUMENTATION]` | needs_review @ 0.92 `[FABRICATED_HISTORY,HALLUCINATED_DETAIL]` |
| S4 | reject @ 0.82 `[STRUCTURAL_MALFORMED_DATE]` | needs_review `[VALUE_MISMATCH,STRUCTURAL_MALFORMED_DATE]` | reject @ 1.00 `[STRUCTURAL_MALFORMED_DATE,VALUE_MISMATCH]` |
| S5 | reject @ 1.00 `[HALLUCINATED_DETAIL,WRONG_CODE]` | needs_review `[WRONG_CODE,VALUE_MISMATCH]` | needs_review @ 1.00 `[WRONG_CODE]` |
| S6 | reject @ 1.00 `[HALLUCINATED_DETAIL,VALUE_MISMATCH]` | reject `[HALLUCINATED_DETAIL,VALUE_MISMATCH,MISSED_ESCALATION,INCOMPLETE_DOCUMENTATION]` | reject @ 1.00 `[HALLUCINATED_DETAIL,WRONG_CODE,VALUE_MISMATCH]` |
| S7 | approve @ 1.00 | needs_review `[STRUCTURAL_MALFORMED_DATE,VALUE_MISMATCH]` | approve @ 1.00 |
| S8 | reject @ 0.51 `[STRUCTURAL_TRIGGER_EVENT_MISMATCH]` | needs_review `[STRUCTURAL_TRIGGER_EVENT_MISMATCH,VALUE_MISMATCH]` | approve @ 1.00 |
| M1 | reject @ 1.00 `[FABRICATED_HISTORY,HALLUCINATED_DETAIL,WRONG_DOSAGE,VALUE_MISMATCH]` | needs_review `[VALUE_MISMATCH,HALLUCINATED_DETAIL]` | needs_review @ 1.00 `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` |
| M2 | reject @ 1.00 `[HALLUCINATED_DETAIL,WRONG_DOSAGE,FABRICATED_HISTORY,FABRICATED_ALLERGY]` | reject `[FABRICATED_HISTORY,WRONG_DOSAGE,INCOMPLETE_DOCUMENTATION,VALUE_MISMATCH]` | needs_review @ 1.00 `[WRONG_DOSAGE,HALLUCINATED_DETAIL]` |
| C1 | needs_review @ 0.90 `[VALUE_MISMATCH]` | approve | approve @ 1.00 |
| C2 | approve @ 1.00 | needs_review `[STRUCTURAL_MALFORMED_DATE,VALUE_MISMATCH]` | approve @ 0.73 |

