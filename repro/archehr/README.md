# ArchEHR-QA initial experiment

Status: **offline preparation and scoring are implemented; real model/council runs are not**.
This is an isolated experiment adapter, not a new native Lithrim benchmark pack or an RL pipeline.
See [ASSESSMENT.md](ASSESSMENT.md) for the assessment and [CODEX_KICKOFF.md](CODEX_KICKOFF.md)
for a paste-ready continuation prompt.

## What is ready

- Gold-free normalized inputs and baseline/revision prompt packets.
- Strict case/answer coverage, citation-ID, duplicate and output-shape checks.
- Real Lithrim `ValueGroundingTool` diagnostics over the **cited text**, with prose-safe abstention.
- Unlabeled, experiment-prefixed Lithrim council input rows; no fabricated gold flags.
- Submission JSON/ZIP export and a hash-pinned official Subtask 4 scorer wrapper.
- Input/prediction/prompt/code hashes and overwrite refusal for each output directory.
- A neutral synthetic smoke fixture that deliberately exposes the numeric check's blind spot.

**Not ready:** approved dataset access, verification of the restricted release's XML layout,
model/endpoint/budget selection, authored council criteria, live council feedback, automated model
generation/revision, paired statistical comparison, or leaderboard submission. The current revision
packets contain deterministic diagnostics only. They must not be called the full council+floor arm.

## Run the free smoke

From the repo root, using the existing Python environment with Lithrim's base dependencies:

```bash
python3 -m repro.archehr.run smoke --out out/archehr-smoke-new
```

Choose a **new** output directory for each run. The command writes:

```text
prepared/inputs.json                  frozen, gold-free normalized inputs
prepared/prompts.jsonl                one baseline prompt packet per case
prepared/empty_submission_template.json   schema template, NOT a model baseline
review/feedback.json                  integrity checks + native numeric diagnostics
review/revision_prompts.jsonl         one-revision prompt packets
review/council_inputs.jsonl           unlabeled rows for later real council review
export/submission.json
export/submission.zip                 one member: submission.json
manifest.json                         synthetic-plumbing label, zero model calls
```

The first synthetic answer says delivery takes 12 days but cites a sentence about 12 items.
Numeric membership passes; semantic support remains `null`. Another answer reverses a negation.
The supplied hand-authored prediction is deliberately incorrect. **No improvement is claimed.**

## Official scorer, locally

The public scorer is not vendored into tracked source. This setup placed the exact upstream file at
`out/archehr-upstream/scoring_subtask_4.py`. On a fresh checkout, obtain the file from
[this pinned organizer revision](https://github.com/soni-sarvesh/archehr-qa-2026/blob/344b67e2f9c5d3c9510a77eb8bfd00b89f505b5b/evaluation/scoring_subtask_4.py)
and save it outside tracked source. The wrapper refuses any other bytes:

```text
SHA256 947357e3f22868d5869d90632fcb9e7203d2688118f35d4e3e2941271752d250
```

Only NumPy is imported beyond the standard library by this scorer; it is present in the assessed
host environment. No large NLP model/scoring dependency installation is needed for Subtask 4.

```bash
python3 -m repro.archehr.official \
  --scorer out/archehr-upstream/scoring_subtask_4.py \
  --inputs repro/archehr/fixtures/inputs.json \
  --submission repro/archehr/fixtures/prediction.json \
  --key repro/archehr/fixtures/key.json \
  --out out/archehr-score-new
```

Expected synthetic result: **0 F1**, labeled `synthetic_plumbing_not_benchmark`. The wrapper executes
the official CLI, not a rewritten approximation. It requires exact case and sentence-ID coverage,
rejects duplicates, and does not expose the upstream case-filter option. It preserves the official
micro/macro precision, recall and F1 on the 0–100 scale; `overall_score` is micro-F1.

A local official-scorer result is **not** a leaderboard entry. Authentic benchmark comparability
also requires the correct release, cohort, access rights and evaluation conditions.

## Bring authorized data, without gold leakage

The dataset is credentialed, not an unrestricted download. Obtain the correct 2026 Subtask 4 release
through the [organizers' data instructions](https://archehr-qa.github.io/#data). Do not copy actual
records into tracked fixtures, prompts, commits, public reports, or an unapproved model endpoint.
Use a private controlled directory for input/key/output; even feedback and prompts contain source text.

`fixtures/inputs.json` defines the adapter's normalized schema. It allows only task inputs:
case ID, patient question, clinician question, numbered source sentences, and the supplied numbered
answer sentences. Extra fields, including annotations/citations/relevance, are rejected. For this
task the answer is supplied input; the answer-to-evidence links are the withheld target.

If the release has supplied-answer XML, the strict importer supports:

```bash
python3 -m repro.archehr.import_xml \
  --xml /private/path/task4-input.xml \
  --name archehr-qa-2026 --release EXACT_RELEASE --split development \
  --out /private/path/prepared-run-001
```

Expected XML fields: `case@id`, `patient_narrative`, `clinician_question`,
`note_excerpt_sentences/sentence@id`, `answer_sentences/sentence@id`.
This layout is based on [a 2026 participant's input parser](https://github.com/mo-arvan/archehr-qa-2026-uic-aihealth4all/blob/main/src/task.py),
**not verified against an authorized organizer file in this setup**. Unexpected structure fails
closed. It does not silently strip annotations, reconstruct answers from keys, or support older
release schemas by guessing. In particular, a development release without supplied answer sentences
needs an explicitly reviewed data-preparation step; never add a key-reading fallback to inference.

Alternatively prepare already-normalized input:

```bash
python3 -m repro.archehr.run prepare \
  --inputs /private/path/inputs.json --out /private/path/prepared-run-001
```

Input allowlists prevent accidental field leakage, not gold manually pasted into a text field,
prior model training contamination or an operator consulting held-out labels. Those need protocol
review. A `heldout` metadata label alone does not enforce a train/test split.

## First real file-driven loop

1. Freeze the development cohort, model revision, prompts and per-case call/token limits.
   Obtain explicit endpoint/data-use and budget approval. The experiment commands never call a model.
2. Feed each baseline packet's `system` and `input` to the chosen model. Capture raw outputs,
   resolved model/provider IDs, sampling settings, tokens, cost, latency and errors. Aggregate the
   per-case objects into a submission JSON list; never silently drop failed cases.
3. Produce feedback and revision packets:

   ```bash
   python3 -m repro.archehr.run review \
     --inputs /private/path/prepared-run-001/inputs.json \
     --submission /private/path/baseline.json --out /private/path/review-run-001
   ```

   Invalid submissions still get structural feedback and revision packets, but exit nonzero and
   cannot be exported/scored. Malformed objects are not echoed into model prompts. All-empty link
   lists are valid abstention, not proof of correctness; report their count with recall.
4. For the full hypothesis, add actual recorded council feedback in a separately implemented,
   tested adapter. The prepared council rows assess the supplied answer against proposed cited text;
   the base model still receives the full source when revising. A council verdict is not a gold link
   label. Never reuse `EvidencePresence` to clear arbitrary support/contradiction findings.
5. Ask the **same model** for one revision with the selected arm's feedback. Save every output.
   Score baseline and revised predictions only after they are frozen, using the separate scorer
   command with the correct key and **the same** normalized inputs. Gold never returns as feedback.
6. Export each valid run with `python3 -m repro.archehr.run export --inputs INPUTS
   --submission PREDICTIONS --out NEW_DIRECTORY`. ZIP packaging does not upload anything.

For development scoring, inspecting mistakes is allowed, but those cases can no longer provide a
held-out improvement claim. Keep a genuinely untouched cohort and preregister the final comparison.

## Running Lithrim at localhost:5180

The assessment verified API health and UI HTTP 200. It created `archehr-initial` on the neutral
`_core` pack, **empty and not activated**. The original active workspace remained `demo-day`.
No existing agents, cases, bindings or ontologies were edited, and no services were restarted.

Before live integration, deliberately select the new workspace and create an experiment-only agent.
Switching is global in the current BFF; do not switch while another task is using it. Use native JSONL
ingest preview/commit for the prepared `council_inputs.jsonl`, then grade only explicit experiment
case IDs after cost approval. Empty-citation cases have no supporting source and may not pass the
native ingest preflight; handle them explicitly as abstentions, not fabricated evidence. Native
`PASS/BLOCK/WARN` and ArchEHR link F1 must remain separate report fields.

## Verification

```bash
ARCHEHR_SCORER_PATH=out/archehr-upstream/scoring_subtask_4.py \
  python3 -m pytest tests/test_archehr_experiment.py tests/test_archehr_import.py \
  tests/test_archehr_lithrim_feedback.py tests/test_archehr_official.py -q
```

Without `ARCHEHR_SCORER_PATH`, only the upstream integration test skips; ordinary tests are offline.
No core engine, taxonomy, consensus function, service code, or existing study corpus was changed.
