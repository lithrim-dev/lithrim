# Judge calibration (live council, gpt-4.1)

- packs scanned: 4
- total rows: 32
- ensemble accuracy (majority vote): **0.8125**
- mean ensemble size observed: 3.00

## Per-judge

| judge | n | accuracy | recall (reject) | precision (reject) | false_block_rate | flag_attach |
|---|---|---|---|---|---|---|
| `behavior_judge` | 32 | 0.844 | 0.6875 | 1.0 | 0.0 | 0.0909 |
| `policy_judge` | 32 | 0.781 | 0.6875 | 0.8462 | 0.125 | 0.3636 |
| `risk_judge` | 32 | 0.781 | 0.625 | 0.9091 | 0.0625 | 0.2 |

## TunedMockBackend calibration

- mean per-member accuracy across judges: **0.802**
- mean per-member flag attachment rate: **0.218**

Suggested TunedMockBackend invocation:

```
TunedMockBackend(ensemble_size=3, per_member_semantic_accuracy=0.802, per_member_flag_attachment_rate=0.218)
```
