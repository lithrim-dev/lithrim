# Label -> Owner Matrix

- Golden set: `/Users/aregee/Workspace/github.com/lithrim-backend/demo_dataset/eval_golden.jsonl`
- Taxonomy snapshot: `/Users/aregee/Workspace/github.com/lithrim-bench/taxonomy/taxonomy_snapshot.json`
- Production judges: ['behavior_judge', 'policy_judge', 'risk_judge']
- Declared but not running: ['source_message_judge']

| Flag | Tier | Declared owners | Production owners | Cases | Production owner runs? |
|---|---|---|---|---|---|
| `FABRICATED_CONSENT_SCOPE` | UNKNOWN | (no Tier-1 entry) | (none) | 1 | **N (code not in taxonomy)** |
| `FABRICATED_HISTORY` | TIER_2 | (no Tier-1 entry) | (none) | 3 | Y |
| `HALLUCINATED_DETAIL` | TIER_2 | (no Tier-1 entry) | (none) | 3 | Y |
| `MALAFFI_CODE_PROPAGATION` | UNKNOWN | (no Tier-1 entry) | (none) | 1 | **N (code not in taxonomy)** |
| `MISSED_ESCALATION` | TIER_1 | ['behavior_judge', 'risk_judge'] | ['behavior_judge', 'risk_judge'] | 2 | Y |
| `MISSING_DUAL_CODING` | UNKNOWN | (no Tier-1 entry) | (none) | 1 | **N (code not in taxonomy)** |
| `PHI_OVER_DISCLOSURE` | UNKNOWN | (no Tier-1 entry) | (none) | 1 | **N (code not in taxonomy)** |
| `PHI_WITHOUT_VERIFICATION` | UNKNOWN | (no Tier-1 entry) | (none) | 5 | **N (code not in taxonomy)** |
| `SCOPE_VIOLATION` | UNKNOWN | (no Tier-1 entry) | (none) | 1 | **N (code not in taxonomy)** |
| `UPCODING_RISK` | TIER_2 | (no Tier-1 entry) | (none) | 3 | Y |
| `VALUE_MISMATCH` | TIER_1 | ['behavior_judge'] | ['behavior_judge'] | 1 | Y |
| `WRONG_CODE` | TIER_2 | (no Tier-1 entry) | (none) | 1 | Y |
| `WRONG_DOSAGE` | TIER_1 | ['behavior_judge', 'risk_judge', 'source_message_judge'] | ['behavior_judge', 'risk_judge'] | 2 | Y |

OK: every Tier-1 flag in the golden set has at least one production owner.
