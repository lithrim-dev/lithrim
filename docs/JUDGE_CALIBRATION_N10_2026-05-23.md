# Judge calibration (live council, gpt-4.1)

- packs scanned: 4
- split: test
- total rows: 1380
- ensemble accuracy (majority vote): **0.7304**
- mean ensemble size observed: 3.00

## Per-judge

| judge | n | accuracy | recall (reject) | precision (reject) | false_block_rate | flag_attach |
|---|---|---|---|---|---|---|
| `behavior_judge` | 1380 | 0.741 | 0.5841 | 0.9657 | 0.0304 | 0.0762 |
| `policy_judge` | 1380 | 0.729 | 0.6012 | 0.913 | 0.0839 | 0.1876 |
| `risk_judge` | 1380 | 0.696 | 0.5512 | 0.8986 | 0.0911 | 0.115 |

## TunedMockBackend calibration

- mean per-member accuracy across judges: **0.722**
- mean per-member flag attachment rate: **0.126**

Suggested TunedMockBackend invocation:

```
TunedMockBackend(ensemble_size=3, per_member_semantic_accuracy=0.722, per_member_flag_attachment_rate=0.126)
```
