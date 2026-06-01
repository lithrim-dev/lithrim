# Verification packs — by-construction structural-validator oracles (WS-3)

These are the **acceptance oracles for the structural floor** (`lithrim_bench/verification`):
a candidate JUTE validator is *bench-accepted* only if it PASSes every clean / control /
semantic case and BLOCKs every labeled structural defect (0 FP, 0 ERR). The field-typed
`injection_recipes` entry **is** the label, consistent with `CLAUDE.md` §"Core invariant:
labels are true by construction".

| pack | count | domain | build script |
|---|---|---|---|
| `fhir_patient_v1.jsonl` | 10 | FHIR R4 US-Core Patient | `scripts/build_fhir_patient_pack.py` |
| `fhir_observation_v1.jsonl` | 8 | FHIR R4 Observation | `scripts/build_fhir_observation_pack.py` |
| `transaction_v1.jsonl` | 10 | payment transactions (non-clinical) | `scripts/build_transaction_pack.py` |

Each build script is byte-deterministic (fixed `GENERATED_AT`, `case_id = sha256(content)`);
re-running over-writes the pack with an identical file (`re-run + diff == 0`). The Patient
pack is derived from the committed `out/fhir_patient_mini.jsonl`; the other two synthesize
their resources inline.

## NOT the council golden set — a different oracle shape

These rows carry `expected_structural_verdict` (PASS/BLOCK for a structural *validator*),
**not** the council-eval contract of `examples/*.jsonl` (`expected_safety_flags` keyed to
`taxonomy/taxonomy_snapshot.json`). They carry their own field-typed by-construction
discipline. Therefore **`scripts/lint_golden_against_taxonomy.py` does not apply to these
packs** — do not run it against them or "fix" them to satisfy it.

## Live mapping-id provenance (etlp-mapper `:3031`)

The spike persisted the bench-accepted validators as live mappings during cross-domain
demonstration. The ids are **narrative provenance only** — IDs reseed and are not
reproducible from this repo; the reproducible artifacts are the packs + the pinned
validator (`validators/fhir_us_core_patient_validator.generated.jute`, the clean,
bench-accepted US-Core Patient validator used as the offline structural floor).

| mapping id | resource | note |
|---|---|---|
| 101 | Patient | the clean bench-accepted validator; pinned at `validators/fhir_us_core_patient_validator.generated.jute` |
| 102 | Observation | cross-domain cold run (0 human interventions) |
| **103** | Transaction | **retained on purpose** — ships the known **buggy first-char-only timestamp check**: the oracle-completeness evidence (the pack accepted it because it had no adversarial malformed-timestamp case). This is the §7 "Threats to Validity" finding that motivates `verification/mutation.py`. No buggy artifact is used as a floor validator. |
