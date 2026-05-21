# Architecture

## Engine spine

```
┌───────────────────────────────────────────────────────────────────────┐
│                       Synthea CSV cohort (pinned)                     │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │
                       lithrim_bench.synthea_loader
                                 │
                         ┌───────▼───────┐
                         │ EncounterSpec │   ← single source of truth
                         └───────┬───────┘
                                 │
        ┌────────────────────────┼────────────────────────────┐
        │                        │                            │
synthesizers.transcript   synthesizers.scribe_artifact   (synth.hl7  P3)
        │                        │                            │
        └───────────┬────────────┴────────────────┬───────────┘
                    │                             │
                    ▼                             ▼
            transcript: str            artifact: dict[str, Any]
                    │                             │
                    └──────────────┬──────────────┘
                                   │
                       ┌───────────▼───────────┐
                       │ injectors.<DefectName>│   ← typed, modality-aware
                       └───────────┬───────────┘
                                   │
                                   ▼
                       (transcript, artifact, recipe)
                                   │
                          lithrim_bench.packager
                                   │
                                   ▼
                       JSONL row (eval spec §1.1)
                                   │
                                   ▼
                       lint_golden_against_taxonomy
                       build_label_owner_matrix
```

## Module responsibilities

| Module | Responsibility | Stability |
|---|---|---|
| `encounter_spec` | Canonical Pydantic schema for a clinical encounter. Read by every synthesizer and injector. | Stable; widening is additive. |
| `synthea_loader` | Build EncounterSpec from Synthea CSV. Deterministic ordering. | Stable. Phase 2 will add observation/condition density. |
| `taxonomy` | Read-only handle over `taxonomy_snapshot.json`. Single coupling point to `lithrim-backend`. | Stable; never hand-edit the JSON. |
| `synthesizers.transcript` | Deterministic template-based transcript synth. v1 = no LLM. | v1; LLM-backed alternative in Phase 2. |
| `synthesizers.scribe_artifact` | FHIR DocumentReference + embedded SOAP body. | v1 scribe shape. New synthesizers per agent type in Phase 2. |
| `injectors.base` | `DefectInjector` ABC, `InjectionRecipe` dataclass. | Stable; new defect types subclass this. |
| `injectors.wrong_dosage` | v1 reference injector. WRONG_DOSAGE → SOAP PLAN section. | v1 reference. Pattern (locate-anchor / substitute / verify) replicates for every text-projection injector. |
| `packager` | Build a JSONL row that conforms to eval spec §1.1. Enforces defect D1/D3 in-process. | Stable; widening row fields is additive. |
| `scripts/snapshot_taxonomy` | Refresh `taxonomy_snapshot.json` from a `lithrim-backend` checkout. | Stable. |
| `scripts/lint_golden_against_taxonomy` | Closes D1. Run in CI. | Stable. |
| `scripts/build_label_owner_matrix` | Closes D3. Run in CI. | Stable. |
| `scripts/generate_proof_case` | v1 smoke: one clean + one injected case end-to-end. | Will be subsumed by `scripts/generate_pack.py` in Phase 2. |

## Why no LLM in v1

The synthesizers are deliberately template-based. Three reasons:

1. **Reproducibility for the paper.** A reviewer running `python scripts/generate_proof_case.py` should get byte-identical output to ours. No API keys, no `temperature`, no per-vendor drift.
2. **CI cost.** Lint and matrix scripts run on every change; LLM calls in the pipeline make CI slow and expensive.
3. **Honesty.** The transcripts are obviously synthetic at v1. That's correct: we're testing the *verifier*, not benchmarking transcript naturalness. Naturalness can come from an LLM-backed synthesizer in Phase 2, behind the same `synthesize_*` interface, opt-in.

## Phase progression

| Phase | New modules | Output |
|---|---|---|
| **1** (now) | `wrong_dosage`, more injectors (`missing_allergy`, `fabricated_history`, `value_mismatch`, `phi_pre_verification`, `hallucinated_detail`, `upcoding_risk`, `missed_escalation`) | ~400 scribe + scheduling cases |
| **2** | `synthesizers.coding_artifact`, `synthesizers.triage_artifact`, `synthesizers.intake_artifact`, `synthesizers.scheduling_artifact`; LLM-backed transcript synth (opt-in) | ~1000 cases across 5 agents |
| **3** | `hl7_emitter` (simhospital pathway YAML adapter), `hl7_mutator` (post-emit defect injection on HL7 text), structural-projection injectors | ~1500 cases, multi-modal |
| **4** | `lithrim_bench_api/` (FastAPI), org scoping, scoring endpoint, dashboard | Bench-as-a-product |
