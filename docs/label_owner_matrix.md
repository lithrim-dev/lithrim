# Label -> Owner Matrix

- Golden set: `/Users/aregee/Workspace/github.com/lithrim-backend/demo_dataset/eval_golden.jsonl`
- Taxonomy snapshot: `/Users/aregee/Workspace/github.com/lithrim-bench/taxonomy/taxonomy_snapshot.json`
- Production judges: ['behavior_judge', 'policy_judge', 'risk_judge']
- Declared but not running: ['source_message_judge']

| Flag | Tier | Declared owners | Production owners | Cases | Production owner runs? |
|---|---|---|---|---|---|
| `FABRICATED_CONSENT` | TIER_1 | ['behavior_judge', 'source_message_judge'] | ['behavior_judge'] | 1 | Y |
| `FABRICATED_HISTORY` | TIER_2 | (no Tier-1 entry) | (none) | 3 | Y |
| `HALLUCINATED_DETAIL` | TIER_2 | (no Tier-1 entry) | (none) | 3 | Y |
| `INCOMPLETE_DOCUMENTATION` | TIER_3 | (no Tier-1 entry) | (none) | 1 | Y |
| `MISSED_ESCALATION` | TIER_1 | ['behavior_judge', 'risk_judge'] | ['behavior_judge', 'risk_judge'] | 2 | Y |
| `PHI_DISCLOSURE_PRE_VERIFICATION` | TIER_1 | ['policy_judge'] | ['policy_judge'] | 5 | Y |
| `PHI_OVER_DISCLOSURE` | UNKNOWN | (no Tier-1 entry) | (none) | 1 | **N (code not in taxonomy)** |
| `SEVERITY_ESCALATION` | TIER_1 | ['behavior_judge', 'risk_judge'] | ['behavior_judge', 'risk_judge'] | 1 | Y |
| `UPCODING_RISK` | TIER_2 | (no Tier-1 entry) | (none) | 3 | Y |
| `VALUE_MISMATCH` | TIER_1 | ['behavior_judge'] | ['behavior_judge'] | 1 | Y |
| `WRONG_CATEGORY_CODE` | TIER_2 | (no Tier-1 entry) | (none) | 1 | Y |
| `WRONG_CODE` | TIER_2 | (no Tier-1 entry) | (none) | 1 | Y |
| `WRONG_DOSAGE` | TIER_1 | ['behavior_judge', 'risk_judge', 'source_message_judge'] | ['behavior_judge', 'risk_judge'] | 2 | Y |

OK: every Tier-1 flag in the golden set has at least one production owner.
