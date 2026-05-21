# Judge calibration (live council, gpt-4.1)

- packs scanned: 4
- total rows: 2000
- ensemble accuracy (majority vote): **0.76**
- mean ensemble size observed: 3.00

## Per-judge

| judge | n | accuracy | recall (reject) | precision (reject) | false_block_rate | flag_attach |
|---|---|---|---|---|---|---|
| `behavior_judge` | 2000 | 0.760 | 0.6458 | 0.9349 | 0.0675 | 0.2026 |
| `policy_judge` | 2000 | 0.730 | 0.6333 | 0.8837 | 0.125 | 0.1855 |
| `risk_judge` | 2000 | 0.745 | 0.6233 | 0.928 | 0.0725 | 0.1578 |

## TunedMockBackend calibration

- mean per-member accuracy across judges: **0.745**
- mean per-member flag attachment rate: **0.182**

Suggested TunedMockBackend invocation:

```
TunedMockBackend(ensemble_size=3, per_member_semantic_accuracy=0.745, per_member_flag_attachment_rate=0.182)
```
