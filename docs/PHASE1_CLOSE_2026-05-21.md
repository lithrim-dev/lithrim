# Phase 1 close — 2026-05-21

8 of 8 priority defects shipped across 4 agent packs. The engine is feature-complete for the paper's §4 (Method) and §5 (Benchmark) sections; Phase 2 work is scale (more Synthea, more synth realism, more injector breadth), not new shape.

## Pack inventory

| Pack | Agent type | Injectors | Tier-1 / Tier-2 / Tier-3 | Anchor projection |
|---|---|---|---|---|
| `scribe_v1` | scribe | WRONG_DOSAGE, MISSING_ALLERGY, FABRICATED_HISTORY, VALUE_MISMATCH, HALLUCINATED_DETAIL | 3 / 2 / 0 | artifact_text (SOAP body) |
| `scheduling_v1` | scheduling | PHI_DISCLOSURE_PRE_VERIFICATION | 1 / 0 / 0 | transcript (verification turns) |
| `coding_v1` | coding | UPCODING_RISK | 0 / 1 / 0 | artifact_structured (FHIR Claim ICD) |
| `triage_v1` | triage | MISSED_ESCALATION | 1 / 0 / 0 | artifact_structured (FHIR RiskAssessment) |

8 injectors, 5 Tier-1, 3 Tier-2, 0 Tier-3. Three projection types exercised: `artifact_text`, `artifact_structured`, `transcript`. The composition is what the paper claims: the structural validator (etlp-mapper) tests `artifact_structured` blindspots that semantic judges cannot detect, while the semantic council exercises `artifact_text` and `transcript` cases.

## How to run

```bash
# all 4 packs at small N
for pack in scribe_v1 scheduling_v1 coding_v1 triage_v1; do
  python scripts/generate_pack.py --pack $pack --size 25 --seed 7
done

# scribe-pack with multi-defect cases (5 injectors -> good combinatorics)
python scripts/generate_pack.py --pack scribe_v1 --size 200 --seed 42 \
  --mix clean=0.35,single=0.50,multi=0.15
```

## Smoke result (size=25 per pack, seed=7)

| Pack | Clean | Single | Multi | Total |
|---|---|---|---|---|
| scribe_v1 | 10 | 12 | 3 | 25 |
| scheduling_v1 | 10 | 15 | 0 | 25 |
| coding_v1 | 10 | 15 | 0 | 25 |
| triage_v1 | 10 | 15 | 0 | 25 |

Multi-defect is only meaningful in `scribe_v1` (5 injectors); the single-injector packs downgrade multi → single automatically.

## Tests

35/35 passing across 9 test files:

- `test_taxonomy.py`, `test_packager.py`
- `test_wrong_dosage_injector.py`, `test_missing_allergy_injector.py`, `test_fabricated_history_injector.py`, `test_value_mismatch_injector.py`, `test_hallucinated_detail_injector.py`
- `test_scheduling_pack.py`, `test_coding_pack.py`, `test_triage_pack.py`

## Lint, owner-matrix, reconciliation state

- Backend's reconciled `eval_golden.jsonl`: 57 scored, 1 excluded, lint exits 0 against the snapshotted taxonomy. Closes D1 and D8.
- Owner matrix: every Tier-1 flag in the scored set has a production owner (post `source_message_judge` filtering).
- Snapshot SHA: per `taxonomy/taxonomy_snapshot.json`. Refresh via `scripts/snapshot_taxonomy.py` when backend taxonomy changes.

## Honest limitations going into Phase 2

1. **Synthea sample cohort is small.** Pack sizes saturate around 150–200 cases per pack before the cohort runs out of patients with the precondition data each injector needs. The Phase 2 lever is to pull a larger Synthea generation (deterministic seed pinned).

2. **`coding_v1` ICD-10 map covers 6 SNOMED codes.** Approximately 10–15% of Synthea patients hit these conditions. Expanding the map to 25–30 entries triples the pack ceiling.

3. **Triage scenarios are a 4-entry library**, paired with Synthea demographics by patient_id hash. The chief complaint is not derived from EncounterSpec content. Phase 2 can extend with urgent-care-warranted (not just ED-warranted) scenarios for verdict-class diversity.

4. **MISSING_ALLERGY in `scribe_v1` drops "Allergic disposition (finding)"** — Synthea's generic allergy label, not a drug allergy. Structurally correct but clinically less compelling than dropping "Penicillin allergy". Phase 2 fix: synthesize drug allergies into EncounterSpec when Synthea's source has only environmental ones.

5. **No CPT-level upcoding yet** (99213 → 99215). Framework ready; a `VisitLevelUpcodingInjector` variant is ~30 lines.

6. **HL7 modality not implemented (Phase 3).** The paper's main worst-of claim is most strongly demonstrated on HL7 ADT^A04 structural defects, which the etlp-mapper validates and the semantic judge cannot. Simhospital integration is the next major engine extension.

7. **Tuned-LLM-judge baseline (criteria injection + ensembling per arXiv 2604.13717) not yet built.** This is the paper §6 baseline; it's eval-system work, not bench-engine work, and lives separately.

## What the paper can claim from Phase 1

The paper's §4 (Method) and §5 (Benchmark) sections are now empirically anchorable:

- Method §4 can describe the worst-of composition + drop-only critique exactly as the production pipeline runs them (backend `compliance_council.py` + `artifact_evaluator.py`).
- Benchmark §5 can describe the generator: Synthea-pinned encounters, programmatic typed injection across 4 agent types and 8 defect classes, deterministic-by-construction labels with `pre_value`/`post_value` traceability in every `injection_recipe`, clean negatives as first-class output (not residue), and CI-enforced D1 + D8 lint guards.

The paper's §7 (Results) still requires phases 2-3 + the N=10 determinism harness. Engine is not the blocker for those; they're a separate runtime + analysis layer.

## Bench-as-product status (see LITHRIM_BENCH_PRODUCT_SPEC.md)

- Phase 4a (`/v1/bench/packs` JSONL download endpoint) is unblocked. The PackDefinition abstraction maps directly to the API: `POST /v1/bench/packs` body specifies `pack_name` + `size` + `seed` + `mix`; the response is a downloadable JSONL identical to what `generate_pack.py` produces today.
- Phase 4b (`/v1/bench/score` developer-output endpoint) is independent of the engine and requires backend integration. Not blocked by anything in this repo.

## Backlog for Phase 2 (priority order)

1. Pull a larger Synthea cohort (deterministic seed) to unblock pack sizes ≥ 500.
2. Expand `_icd10_map.py` to 25–30 conditions (3× coding pack ceiling).
3. `intake_v1` pack — currently no intake injector even though FABRICATED_CONSENT and PHI codes apply.
4. `VisitLevelUpcodingInjector` (CPT 99213 → 99215).
5. Drug-allergy enrichment for `scribe_v1` MISSING_ALLERGY clinical realism.
6. Urgent-care-warranted triage scenarios for verdict-class diversity.
7. LLM-backed transcript synthesizer (opt-in, parallel to the deterministic path).
