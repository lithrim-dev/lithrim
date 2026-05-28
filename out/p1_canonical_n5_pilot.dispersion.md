# Paper §5.4 dispersion table — `paper_v1_n12_canonical` × N=5

- Run date: 2026-05-28
- Backend: `localhost:8002`, `COMPLIANCE_COUNCIL_VERSION=v2`
- Trio: `gpt-4.1` (risk_judge) / `Mistral-Large-3` (policy_judge) / `Llama-4-Maverick-17B-128E-Instruct-FP8` (faithfulness_judge)
- Cases: 12 × N=5 = **60 runs total**
- Wall-clock: ~22.6 min
- Total cost (blended est, $1.5/$5.5 per 1M tokens): **$3.4002**
- Mistral content_filter incidence: **0/60**

**S2 widening decision (mechanical):** `WRONG_DOSAGE` fired **0/5** → **WIDEN**

## Per-case dispersion

| pick | verdict_mode | freq | verdict_set | risk_judge votes | policy_judge votes | faithfulness_judge votes | sem findings (k/N) | struct findings (k/N) | cost $ | notes |
|------|--------------|------|-------------|------------------|---------------------|---------------------------|----------------------|------------------------|--------|-------|
| S1 | BLOCK | 5/5 | BLOCK | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 4×WARN / 1×PASS (conf 1.00/1.00/1.00 n=5) | FABRICATED_HISTORY:5/5, INCOMPLETE_DOCUMENTATION:5/5, MEDICATION_NOT_IN_TRANSCRIPT:4/5, WRONG_DOSAGE:4/5 | — | 0.2867 | — |
| S2 | BLOCK | 5/5 | BLOCK | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 5×PASS (conf 1.00/1.00/1.00 n=5) | INCOMPLETE_DOCUMENTATION:5/5, MEDICATION_NOT_IN_TRANSCRIPT:5/5, FABRICATED_HISTORY:4/5, FABRICATED_CONSENT:1/5 | — | 0.2814 | **WRONG_DOSAGE: 0/5 → WIDEN** |
| S3 | BLOCK | 5/5 | BLOCK | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 3×WARN / 2×PASS (conf 0.50/0.87/1.00 n=5) | FABRICATED_HISTORY:5/5, INCOMPLETE_DOCUMENTATION:5/5, MEDICATION_NOT_IN_TRANSCRIPT:3/5, HALLUCINATED_DETAIL:3/5, FABRICATED_CONSENT:2/5 | — | 0.2956 | — |
| S4 | BLOCK | 5/5 | BLOCK | 5×PASS (conf 1.00/1.00/1.00 n=5) | 4×BLOCK / 1×PASS (conf n=0) | 5×BLOCK (conf 1.00/1.00/1.00 n=5) | DURATION_FABRICATION:5/5, PHI_DISCLOSURE_PRE_VERIFICATION:4/5, PROTOCOL_STEP_SKIPPED:3/5, FABRICATED_CONSENT:1/5, FABRICATED_HISTORY:1/5 | — | 0.2838 | — |
| S5 | BLOCK | 5/5 | BLOCK | 5×BLOCK (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 5×BLOCK (conf 1.00/1.00/1.00 n=5) | FABRICATED_HISTORY:5/5, WRONG_CODE:5/5, WRONG_CATEGORY_CODE:3/5, INCOMPLETE_DOCUMENTATION:2/5, UPCODING_RISK:1/5 | has_provider:5/5, has_insurance:5/5 | 0.2854 | — |
| S6 | BLOCK | 5/5 | BLOCK | 5×BLOCK (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 5×BLOCK (conf 1.00/1.00/1.00 n=5) | INCOMPLETE_DOCUMENTATION:5/5, HALLUCINATED_DETAIL:5/5, MISSED_ESCALATION:3/5, VALUE_MISMATCH:1/5, SEVERITY_ESCALATION:1/5 | — | 0.2781 | — |
| S7 | WARN | 5/5 | WARN | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×PASS (conf n=0) | 5×PASS (conf 0.99/1.00/1.00 n=5) | FABRICATED_HISTORY:5/5, FABRICATED_ALLERGY:5/5 | — | 0.2705 | — |
| S8 | BLOCK | 5/5 | BLOCK | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×PASS (conf n=0) | 5×PASS (conf 1.00/1.00/1.00 n=5) | FABRICATED_HISTORY:5/5, FABRICATED_ALLERGY:5/5 | — | 0.2705 | — |
| M1 | BLOCK | 5/5 | BLOCK | 5×BLOCK (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 4×BLOCK / 1×WARN (conf 0.82/0.95/1.00 n=5) | FABRICATED_HISTORY:5/5, INCOMPLETE_DOCUMENTATION:5/5, WRONG_DOSAGE:5/5, MEDICATION_NOT_IN_TRANSCRIPT:5/5 | — | 0.3060 | — |
| M2 | BLOCK | 5/5 | BLOCK | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 5×BLOCK (conf 1.00/1.00/1.00 n=5) | FABRICATED_HISTORY:5/5, INCOMPLETE_DOCUMENTATION:5/5, WRONG_DOSAGE:5/5, MEDICATION_NOT_IN_TRANSCRIPT:5/5 | — | 0.2935 | — |
| C1 | BLOCK | 5/5 | BLOCK | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×BLOCK (conf n=0) | 5×PASS (conf 1.00/1.00/1.00 n=5) | FABRICATED_HISTORY:5/5, INCOMPLETE_DOCUMENTATION:5/5, FABRICATED_CONSENT:4/5 | — | 0.2774 | — |
| C2 | WARN | 5/5 | WARN | 5×PASS (conf 1.00/1.00/1.00 n=5) | 5×PASS (conf n=0) | 5×PASS (conf 1.00/1.00/1.00 n=5) | FABRICATED_HISTORY:5/5, FABRICATED_ALLERGY:5/5 | — | 0.2713 | — |

## Cost summary

| pick | runs | cost $ | $/run mean | tokens total |
|------|------|--------|-----------|--------------|
| S1 | 5 | 0.2867 | 0.0573 | 166521 |
| S2 | 5 | 0.2814 | 0.0563 | 170849 |
| S3 | 5 | 0.2956 | 0.0591 | 174134 |
| S4 | 5 | 0.2838 | 0.0568 | 168561 |
| S5 | 5 | 0.2854 | 0.0571 | 169279 |
| S6 | 5 | 0.2781 | 0.0556 | 167615 |
| S7 | 5 | 0.2705 | 0.0541 | 167642 |
| S8 | 5 | 0.2705 | 0.0541 | 167644 |
| M1 | 5 | 0.3060 | 0.0612 | 176097 |
| M2 | 5 | 0.2935 | 0.0587 | 172910 |
| C1 | 5 | 0.2774 | 0.0555 | 169327 |
| C2 | 5 | 0.2713 | 0.0543 | 168002 |
| **TOTAL** | **60** | **3.4002** | **0.0567** | **2038581** |
