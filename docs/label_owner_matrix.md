# Label -> Owner Matrix

- Golden set: `out/scribe_v1.n10.jsonl`
- Taxonomy snapshot: `/Users/aregee/Workspace/github.com/lithrim-bench/taxonomy/taxonomy_snapshot.json`
- Production judges: ['behavior_judge', 'policy_judge', 'risk_judge']
- Declared but not running: ['source_message_judge']

| Flag | Tier | Declared owners | Production owners | Cases | Production owner runs? |
|---|---|---|---|---|---|
| `FABRICATED_HISTORY` | TIER_2 | (no Tier-1 entry) | (none) | 10 | Y |
| `HALLUCINATED_DETAIL` | TIER_2 | (no Tier-1 entry) | (none) | 13 | Y |
| `WRONG_DOSAGE` | TIER_1 | ['behavior_judge', 'risk_judge', 'source_message_judge'] | ['behavior_judge', 'risk_judge'] | 12 | Y |

OK: every Tier-1 flag in the golden set has at least one production owner.
