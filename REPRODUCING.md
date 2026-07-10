# Reproducing the study

This repo carries everything needed to re-run the configuration-controlled study behind
the technical report *A grounded evaluation architecture for clinical scribes: a
configuration-controlled study of LLM judges and a deterministic grounding floor*.

- **Report + data (Zenodo):** version DOI [10.5281/zenodo.21270268](https://doi.org/10.5281/zenodo.21270268),
  concept DOI [10.5281/zenodo.21270267](https://doi.org/10.5281/zenodo.21270267) (resolves to the latest version)
- **Preregistration (OSF):** [10.17605/OSF.IO/2ZU4H](https://doi.org/10.17605/OSF.IO/2ZU4H)
  (the F10 corrected-rerun prediction; v2 will be deposited under the same concept DOI)

## What the study was

Five judge configurations x two evidence arms x 54 cases = **540 graded evaluations**, all
over an **identical deterministic grounding floor** (same floor ontology cloned into every
workspace, by construction):

| Workspace | Configuration | Judges |
|---|---|---|
| `stream-a-single` | Single generalist, self-consistency k=8, t=1.0 | 1 |
| `stream-b-ensemble` | Multi-model ensemble, same instruction, k=1, t=0.0 | 6 |
| `stream-c-same` | Specialist council (risk/policy/faithfulness lenses), one model | 3 |
| `stream-c-mixed` | Specialist council, mixed models | 3 |
| `baseline-scalar-reward` | Commercial scalar-reward baseline (vendor not named in the published report, pending vendor notice) | 1 |

The two arms differ only in the floor ontology: **armT** (transcript-only) vs **armR**
(record-informed: `grading_context_fields: ["patient_profile"]` exposes the clinical
record to grading). Everything else is held identical.

The corpus is 54 cases per workspace: the 44-case synthetic bidirectional corpus (22
upcode positives + 22 clean-generalization negatives, built over MTS-Dialog) plus 10
physician-curated cases (withheld here; see the 44-vs-54 boundary below).

## Repo file map (vs the Zenodo bundle)

| This repo | Zenodo bundle (v1) | Notes |
|---|---|---|
| `repro/corpus/cv_bidirectional_44_bundle.jsonl` | `data/corpus_bidirectional_44.jsonl` | **Byte-identical.** Sanitization applied here (a personal attribution in the rationale strings became "per the physician collaborator's ratified directional rule", 38 rows) matches the deposited copy exactly. |
| `repro/corpus/upcoded_positives.jsonl` | (rows 1-22 of the bundle) | The 22-row upcode split, same sanitization (19 rows touched). |
| `repro/corpus/clean_generalization_negatives.jsonl` | (rows 23-44 of the bundle) | The 22-row clean-generalization split, same sanitization (19 rows touched). |
| `repro/ontology_armR.json` | `data/graded_ontology_armR.json` | **Identical content** (verified by deep-equal). One facility name in a `fact_preservation` check is generalized to "a state psychiatric facility", matching the deposit. |
| `repro/ontology_armT.json` | *(absent from the v1 deposit; queued for v2)* | The transcript-only reference floor. Differs from armR only by the **absence** of `grading_context_fields`; same facility-name generalization applied. |
| `repro/role_binds.json` | *(absent from the v1 deposit; queued for v2)* | The per-role provider/model bind record (recovered from the deposited per-configuration scorecards + the pre-study bind readout). |
| `repro/setup_streams.py`, `repro/cohort_runner.py`, `repro/consolidate.py` | *(absent from the v1 deposit; queued for v2)* | Parameterized ports of the study orchestration scripts (the originals hardcoded a machine-local scratch dir and a second stack on port 18787). |
| *(not in repo)* | `data/consolidated_arm{T,R}.json`, `data/typing_report_*.json`, `data/suppression_ledger_*.json`, `data/optimize_*.json` | The study **outputs**. Get them from Zenodo; your rerun regenerates equivalents via `consolidate.py`. |

## The 44-vs-54 boundary

The **ten physician-curated cases (ClinVerdict) are not in this repo** pending written
attribution consent; the curator appears in the published record as "the physician
collaborator". Consequences for reproduction:

- Fully reproducible from this repo alone: all **bidirectional-corpus metrics** (upcode
  catch rates, clean-generalization false-positive rates, the floor-flip ledger, floor
  suppression behavior, upcode typing) since they derive from the 44 tracked cases.
- Affected without the withheld cases: the **per-configuration scorecard totals** (n=54
  counts of matches/misses/over-flags include the 10 physician cases) and the
  **reliability/K-sweep metrics** computed over the whole corpus. Expect n=44 equivalents.
- The physician cases were graded with the dated deployment `gpt-5.5-2026-04-23`
  (recorded in `repro/role_binds.json`).

`setup_streams.py` asserts 44 cases per workspace by default; if you hold the withheld
file, point `LITHRIM_REPRO_PHYSICIAN_CASES` at it and the assertion becomes 54.

## Prerequisites

1. A running Lithrim stack (BFF on `:8787` by default): see `SETUP.md` / `make up`.
2. **Provider keys**, connected in the UI (Providers) or via `POST /v1/provider/config`:
   - **Azure OpenAI** (deployments for `gpt-4.1` and `gpt-5.4`),
   - **Anthropic** (`claude-opus-4-8`, `claude-sonnet-5`),
   - an **OpenAI-compatible endpoint** serving `Llama-4-Maverick-17B-128E-Instruct-FP8`
     and `Mistral-Large-3` (ensemble members; optional if you drop those two roles),
   - the **commercial scalar-reward baseline is optional**; the published report does not
     name its vendor pending vendor notice, and this repo's provider plane is generic
     product integration. Skip `baseline-scalar-reward` if you don't hold a key for that
     class of product.
3. The SNOMED floor tooling: a Hermes SNOMED jar + db under `snomed/` (see
   `snomed/README.md`). The floor contracts call it as an MCP tool (`hermes_snomed`).

## Cost note

A full rerun is **~540 paid grades** (54 cases x 5 configurations x 2 arms), plus k=8
self-consistency sampling on `stream-a-single`. Budget accordingly; there are no paid
calls in `setup_streams.py` (authoring only) or `consolidate.py` ($0 replays).

## Run sequence

Everything below defaults to `LITHRIM_REPRO_BASE=http://localhost:8787` and writes
outputs to `LITHRIM_REPRO_OUT=./out/repro`.

### 0. Dry-run (offline, free)

```bash
python repro/setup_streams.py --dry-run
```

Prints the full plan (workspaces, judges, lenses, corpus) without any HTTP call.

### 1. Workspace setup (authoring, free)

```bash
# transcript-only arm (armT is the default ontology)
python repro/setup_streams.py
# record-informed arm: rerun the whole sequence on a second stack or a fresh set of
# workspaces with:
LITHRIM_REPRO_ONTOLOGY=repro/ontology_armR.json python repro/setup_streams.py
```

Creates the 5 workspaces, clones the identical floor ontology into each, authors the
`hermes_snomed` tool, ingests the corpus, authors the stream judges, and pins each roster.

### 2. Bind models to roles (free; re-probes before writing)

Each judge role gets a `{provider, model}` bind, reusing the provider key you already
stored. The full study record is `repro/role_binds.json`. Example sequence (run with the
target workspace active; switch via `POST /v1/workspace {"name": ...}`):

```bash
# stream-a-single
curl -sX POST localhost:8787/v1/roles/bind -H 'Content-Type: application/json' \
  -d '{"role": "single_generalist", "provider": "azure", "model": "gpt-4.1"}'

# stream-b-ensemble (repeat per role; a per-role "endpoint"/"api_version" override is
# supported so two judges on the same provider can hit different deployments)
curl -sX POST localhost:8787/v1/roles/bind -H 'Content-Type: application/json' \
  -d '{"role": "ens_gpt41", "provider": "azure", "model": "gpt-4.1"}'
curl -sX POST localhost:8787/v1/roles/bind -H 'Content-Type: application/json' \
  -d '{"role": "ens_gpt5", "provider": "azure", "model": "gpt-5.4"}'
curl -sX POST localhost:8787/v1/roles/bind -H 'Content-Type: application/json' \
  -d '{"role": "ens_opus", "provider": "anthropic", "model": "claude-opus-4-8"}'
curl -sX POST localhost:8787/v1/roles/bind -H 'Content-Type: application/json' \
  -d '{"role": "ens_sonnet", "provider": "anthropic", "model": "claude-sonnet-5"}'
curl -sX POST localhost:8787/v1/roles/bind -H 'Content-Type: application/json' \
  -d '{"role": "ens_llama", "provider": "openai_compatible", "model": "Llama-4-Maverick-17B-128E-Instruct-FP8"}'
curl -sX POST localhost:8787/v1/roles/bind -H 'Content-Type: application/json' \
  -d '{"role": "ens_mistral", "provider": "openai_compatible", "model": "Mistral-Large-3"}'

# stream-c-same: cs_risk / cs_policy / cs_faith all -> azure gpt-4.1
# stream-c-mixed: cm_risk -> anthropic claude-opus-4-8, cm_policy -> azure gpt-4.1,
#                 cm_faith -> azure gpt-5.4
```

Note on naming: the setup script authors the published role and workspace names directly
(`single_generalist`, the six `ens_*` members, `cs_*`/`cm_*`, `scalar_reward_baseline`).
`repro/role_binds.json` carries the authoritative role-to-model map.

### 3. Grade the cohort (PAID)

```bash
python repro/cohort_runner.py
```

Sequential, per-case resilient; progress in `$LITHRIM_REPRO_OUT/progress.log`, sentinel
file `COHORT_DONE` on completion.

### 4. Consolidate ($0)

```bash
python repro/consolidate.py
```

Writes `$LITHRIM_REPRO_OUT/consolidated.json`: per-stream scorecards
(replay-from-provenance), reliability metrics, the stream-a K-sweep, and the floor-flip
ledger (council `verdict` vs post-floor `grounded_verdict` per case). Compare against the
Zenodo `data/consolidated_arm{T,R}.json`.

## Single stack vs the study's two stacks

The study ran its five workspaces on a **second, isolated validate stack on `:18787`**
purely to keep the research runs away from a demo stack; that is an operational choice,
not a requirement. A single default stack on `:8787` reproduces the study; to mirror the
original isolation, bring up a second compose project and set
`LITHRIM_REPRO_BASE=http://localhost:18787`.

## Determinism caveats

- Judge verdicts are LLM outputs: expect run-to-run variation, especially on
  `stream-a-single` (t=1.0, k=8). The published reliability card quantifies this.
- The floor is deterministic given the same SNOMED edition; terminology results are
  edition-dependent (the report states the edition used).
- Known corpus artifact (report F10): most clean-generalization notes contain exam/vitals
  content absent from their transcripts. The preregistered scrub + rerun (OSF DOI above)
  will be deposited as v2 under the same concept DOI.
