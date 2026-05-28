# P1-FHIR-CONFORMANCE-MINI harness results


- Backend: `http://localhost:8002`  agent: `none`
- Validator: etlp-mapper mapping 41 (`fhir-patient-validator-strict`, profile `us-core-patient`)
- Cases run: **3**
- All three gates: **1/3**
- Verdict match: 2/3 | Flags match: 2/3 | No structural FP: 3/3

## Per-case

| pick | verdict | flags | structural | overall | notes |
|------|---------|-------|------------|---------|-------|
| A_CLEAN | ✗ BLOCK | ✓ 0/0 | ✓ 0 findings, status=PASS | **FAIL** | got reject |
| B_STRUCT_STRIP_IDENTIFIER | ✓ BLOCK | ✗ 0/1 | ✓ 2 findings, status=WARN | **FAIL** | missed: STRUCTURAL_MISSING_REQUIRED_FIELD |
| C_SEM_GENDER_MISMATCH | ✓ BLOCK | ✓ 1/1 | ✓ 0 findings, status=PASS | **PASS** | via VALUE_MISMATCH:substitute:FABRICATED_HISTORY |
