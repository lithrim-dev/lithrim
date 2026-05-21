# Lithrim Bench

Deterministically-labeled clinical-AI artifact verification benchmark generator.

This repo serves two purposes from one engine:

1. **Paper benchmark** — produces the synthetic, by-construction-labeled clinical artifact verification cases consumed by the Lithrim research paper (*A Deterministic Structural Floor Under LLM-as-Judge*). See `docs/PAPER_OUTLINE.md`.
2. **Lithrim Bench (developer product)** — the same engine, exposed to AI-agent developers signing up on Lithrim, so they can generate targeted golden cases for their own scribe / coding / triage / intake / scheduling agents and benchmark them. See `docs/LITHRIM_BENCH_PRODUCT_SPEC.md`.

## Core idea

The **Synthea-derived clinical encounter** is the single source of truth. Every modality — transcript, SOAP note, FHIR resource, HL7 v2 message, agent artifact — is a *projection* of that encounter. A defect is a typed mutation applied to a named projection, with `pre_value` / `post_value` recorded. **The label is true by construction.**

```
Synthea cohort (pinned)
  └─ EncounterSpec
       ├─→ TranscriptSynth   (dialogue grounded in encounter facts)
       ├─→ ArtifactSynth     (per agent: SOAP / ICD bundle / RiskAssessment / Patient+intake / Appointment)
       └─→ HL7Emitter        (simhospital pathway + post-emit mutator) [Phase 3]
                ↓
           DefectInjector  (typed library, modality-aware)
                ↓
           CasePackager → JSONL row {case_id, ground_truth, recipe, projections, expected_*}
                ↓
           Lint + OwnerMatrix gate (CI)
```

## Repo layout

```
lithrim-bench/
├── lithrim_bench/             # the engine library
│   ├── encounter_spec.py
│   ├── synthea_loader.py
│   ├── packager.py
│   ├── taxonomy.py
│   ├── injectors/
│   │   ├── base.py
│   │   └── wrong_dosage.py    # v1 reference injector
│   └── synthesizers/
│       ├── transcript.py
│       └── scribe_artifact.py
├── taxonomy/
│   └── taxonomy_snapshot.json # frozen snapshot of compliance_council.py taxonomy
├── scripts/
│   ├── snapshot_taxonomy.py             # refresh the snapshot from lithrim-backend
│   ├── lint_golden_against_taxonomy.py  # closes defect D1
│   ├── build_label_owner_matrix.py      # closes defect D3
│   └── generate_proof_case.py           # the v1 end-to-end demo
├── docs/
│   ├── PAPER_OUTLINE.md
│   ├── EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md
│   ├── ARCHITECTURE.md
│   └── LITHRIM_BENCH_PRODUCT_SPEC.md
├── data/
│   └── synthea_sample_data_csv_latest/  # NOT checked in (147MB); see MANIFEST.md
├── tests/
└── examples/
```

## Quick start

```bash
# 1. Point at the Synthea sample CSV cohort
ln -s ~/Workspace/github.com/synthea_sample_data_csv_latest data/synthea_sample_data_csv_latest

# 2. Install
pip install -e ".[dev]"

# 3. Generate the v1 end-to-end proof case (Synthea row → SOAP note → WRONG_DOSAGE → JSONL)
python scripts/generate_proof_case.py --out examples/proof_case.jsonl

# 4. Lint the existing lithrim-backend golden set against the snapshotted taxonomy
python scripts/lint_golden_against_taxonomy.py \
  --golden /Users/aregee/Workspace/github.com/lithrim-backend/demo_dataset/eval_golden.jsonl

# 5. Build the label → owner matrix
python scripts/build_label_owner_matrix.py \
  --golden /Users/aregee/Workspace/github.com/lithrim-backend/demo_dataset/eval_golden.jsonl \
  --out docs/label_owner_matrix.md

# 6. Refresh the taxonomy snapshot (when compliance_council.py changes upstream)
python scripts/snapshot_taxonomy.py --backend-path /Users/aregee/Workspace/github.com/lithrim-backend
```

## Phasing

| Phase | Scope | Cases | Status |
|---|---|---|---|
| 1 | Scribe + scheduling, top 8 defects, transcript + artifact only | ~400 | **in progress** (v0.1 = WRONG_DOSAGE proof) |
| 2 | + coding, triage, intake | ~1000 | not started |
| 3 | + HL7 modality via simhospital pathways + MessageProcessor mutator | ~1500 | not started |
| 4 | Lithrim Bench API surface (`POST /v1/bench/generate`) | n/a | not started |

## Why this repo is independent of `lithrim-backend`

The benchmark must be reproducible without the backend present. The contract surface is a single JSON snapshot of the council taxonomy (`taxonomy/taxonomy_snapshot.json`), refreshed by `scripts/snapshot_taxonomy.py`. Drift between this snapshot and the backend is caught by `scripts/lint_golden_against_taxonomy.py`, which can be run in CI on both sides.

## License

Apache-2.0.
