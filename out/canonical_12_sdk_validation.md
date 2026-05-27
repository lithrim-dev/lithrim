# Canonical N=12 SDK validation


- Backend: `http://localhost:8002`  agent: `69e8eed80774d8129275bb4a`
- Cases run: **12**
- All three gates: **3/12**
- Verdict match: 9/12 | Flags match: 5/12 | No structural FP: 11/12

## Per-case

| pick | verdict | flags | structural | overall | notes |
|------|---------|-------|------------|---------|-------|
| S1 | ✓ BLOCK | ✗ 0/1 | ✓ 0 findings | **FAIL** | missed: HALLUCINATED_DETAIL |
| S2 | ✓ BLOCK | ✓ 1/1 | ✓ 0 findings | **PASS** | — |
| S3 | ✓ BLOCK | ✓ 1/1 | ✓ 0 findings | **PASS** | — |
| S4 | ✓ BLOCK | ✓ 1/1 | ✓ 0 findings | **PASS** | — |
| S5 | ✓ BLOCK | ✗ 0/1 | ✗ 2 findings | **FAIL** | missed: UPCODING_RISK / structural FP: has_provider,has_insurance |
| S6 | ✓ BLOCK | ✗ 0/1 | ✓ 0 findings | **FAIL** | missed: MISSED_ESCALATION |
| S7 | ✗ WARN | ✗ 0/1 | ✓ 0 findings | **FAIL** | got needs_review / missed: STRUCTURAL_MALFORMED_DATE |
| S8 | ✓ BLOCK | ✗ 0/1 | ✓ 1 findings | **FAIL** | missed: STRUCTURAL_TRIGGER_EVENT_MISMATCH |
| M1 | ✓ BLOCK | ✗ 1/2 | ✓ 0 findings | **FAIL** | missed: WRONG_DOSAGE |
| M2 | ✓ BLOCK | ✗ 1/2 | ✓ 0 findings | **FAIL** | missed: HALLUCINATED_DETAIL |
| C1 | ✗ BLOCK | ✓ 0/0 | ✓ 0 findings | **FAIL** | got reject |
| C2 | ✗ BLOCK | ✓ 0/0 | ✓ 0 findings | **FAIL** | got reject |
