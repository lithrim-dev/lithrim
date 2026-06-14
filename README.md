# Lithrim Bench

Deterministically-labeled clinical-AI artifact verification benchmark generator.

This repo serves two purposes from one engine:

1. **Paper benchmark** — produces the synthetic, by-construction-labeled clinical artifact verification cases consumed by the Lithrim research paper (*A Deterministic Structural Floor Under LLM-as-Judge*). See `docs/PAPER_OUTLINE.md`.
2. **Lithrim Bench (developer product)** — the same engine, exposed to AI-agent developers signing up on Lithrim, so they can generate targeted golden cases for their own scribe / coding / triage / intake / scheduling agents and benchmark them. See `docs/LITHRIM_BENCH_PRODUCT_SPEC.md`.

## Open-core: this repo is the OSS Core — domain packs load from OUTSIDE it (PACK-DIST-1)

**This repo is the genuinely domain-agnostic CE / OSS core.** It ships NO clinical content. The
engine (council orchestration, the grounding-floor mechanism, the SQLite config plane, `run_eval`,
the eval-pack gate, all of JUTE, BYOK) + a neutral default pack (`packs/_core/`) + a non-clinical
sample pack (`packs/support_ticket_qa/`) are everything the core needs to boot and grade standalone.

A **domain** is a *pack* — a manifest (`pack.json`) bundling an ontology + taxonomy + council role
prompts + grounding floors + dataset generators. The full **clinical `healthcare` pack is Pro and
distributed separately** in its own repo (`../lithrim-pack-healthcare`), NOT in these OSS bits
(SPEC_PLUGIN_ARCHITECTURE OQ-3). The core loads it from outside via the pack-discovery seam
(`lithrim_bench/harness/pack.py`), which resolves a pack id in order:

1. an installed **entry point** in the `lithrim_bench.packs` group (the idiomatic pip path);
2. **`LITHRIM_BENCH_PACKS_DIR`** — `os.pathsep`-joined external dirs (the dev / airgap path);
3. the in-repo `packs/` (the CE sample packs + fixtures).

```bash
# THE canonical dev / CI invocation — load the external healthcare pack AND pin it active:
LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare python -m pytest
# …or pip-install it (registers the entry point):
pip install -e ../lithrim-pack-healthcare && LITHRIM_BENCH_PACK=healthcare …
```

> **Both env vars are load-bearing.** `LITHRIM_BENCH_PACKS_DIR` alone (without `LITHRIM_BENCH_PACK`)
> only makes the pack *discoverable* — the active pack stays on the neutral `_core` default, so the
> frozen council binds `_core`'s taxonomy codes at import and the 12 healthcare test modules fail
> collection with `PackConsistencyError` (clinical codes not in the active council). That is
> fail-closed-correct, not a bug: pin `LITHRIM_BENCH_PACK=healthcare` to grade through the clinical pack.

With no pack on the path the core stays on the neutral `_core` default and grades fine — a Pro pack
the operator can't reach is **absent**, not stubbed (fail-closed). To add your own domain, write a
pack repo with a `pack.json` + the entry point and point the env var at it — **zero engine edits**.

> **The rest of this README documents the engine through the *clinical* lens** (the paper's domain).
> Those specifics now live in the `healthcare` pack; read them as "what a fully-built domain pack
> looks like," not as content shipped in this repo.

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

> **Want to run the conversational eval _product_** (the 3-pane shell + the in-process
> council + the grounding floor, BYO Azure/Claude key, no `lithrim-backend`/Mongo)?
> See [`docs/QUICKSTART.md`](docs/QUICKSTART.md). The steps below are the _engine_
> (Synthea → labeled cases).

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
