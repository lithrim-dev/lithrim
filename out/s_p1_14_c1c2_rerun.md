# S-P1-14 reverification — C1 + C2 after NKA propagation patch
Backend patch: lithrim-backend `e8147d8` (`feat(council-roles): propagate NKA exception to risk_judge + policy_judge`)

## Per-case delta

| pick | verdict before → after | verdict_lifted? | judges that changed | findings before → after |
|---|---|---|---|---|
| **C1** | ? → PASS | ✗ | (no changes) | (no changes) |
| **C2** | ? → WARN | ✗ | (no changes) | (no changes) |

## Raw judge votes after patch

### C1 (`bench_scribe_v1_clean_negative_943a942d3519`)
- Expected: `approve`
- Actual: `PASS`
- pipeline_run_id: `None`
- Judge votes:
  - `risk_judge` (gpt-4.1): `PASS` conf=1.0 codes=[]
  - `policy_judge` (Mistral-Large-3): `PASS` conf=0.0 codes=[]
  - `faithfulness_judge` (Llama-4-Maverick-17B-128E-Instruct-FP8): `PASS` conf=1.0 codes=[]

### C2 (`bench_hl7_adt_v1_clean_negative_9eff0d8ab203`)
- Expected: `approve`
- Actual: `WARN`
- pipeline_run_id: `None`
- Judge votes:
  - `risk_judge` (gpt-4.1): `PASS` conf=1.0 codes=[]
  - `policy_judge` (Mistral-Large-3): `PASS` conf=0.0 codes=[]
  - `faithfulness_judge` (Llama-4-Maverick-17B-128E-Instruct-FP8): `PASS` conf=1.0 codes=[]
