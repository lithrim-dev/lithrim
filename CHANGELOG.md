# Changelog

All notable changes to Lithrim are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
date-based pre-1.0 versions.

## [Unreleased]

## [0.1.27] — 2026-09-10

KPI contracts the floor proves before any judge, and OpenTelemetry traces as cases.

### Added
- KPI contracts (`kpi_threshold`, `field_in_set`): deterministic floors over a structured
  record's fields that prove a KPI before any judge runs; a breach injects the pinned flag
  with the expected and actual values named, unknown is never a violation; malformed pins
  are refused at author time (`docs/KPI_CONTRACTS.md`).
- OpenTelemetry trace exports (OTLP/JSON) as eval cases on the upload front door: one case
  per LLM span, the prompt as the transcript, the completion as the artifact, the span's
  attributes, resource, duration and status as the structured record the KPI floor checks.

## [0.1.26] — 2026-09-10

The RAGTruth loop from the shell: the six verbs reachable from the browser, one workspace
holding everything, the run-time quirks fixed. Acceptance: an uninvolved person on a fresh
compose stack, with the dataset files and their own key, reproduces the pilot table without a
terminal (`docs/reproduction/RAGTRUTH_LOOP_UI.md`).

### Added
- Load from the shell: `GET /v1/importers`, `POST /v1/cases/import` (the importer manifest's
  `adapter_module` / `files` / `splits` fields run the dataset adapter over uploaded files,
  labels kept, every case tagged with its split), a Load step in the rail, the import card.
- Grade jobs that survive a reload: `GET /v1/jobs?agent=`, interrupted-job reconciliation and
  resume (a restart no longer leaves a job that reads as running forever), `round` and
  `split` on the grade request, a retrying poller and restore-on-mount in the shell.
- The two-vocabulary scorecard per job: `GET /v1/jobs/{id}/scorecard?vocabulary=&compare=`
  (per-task response and span P/R/F1, per-code rows in the dataset's terms, the verdict rule
  both ways, a prior round beside it, the pinned demos in force); `scoring.table`.
- Calibrate from the shell on the calibration split (`split` on the optimize request), the
  out-of-sample check in the pin gate, the pinned demos on the judge read and the editor.
- Rounds: re-grade with the pinned demos, the `$0` replay labelled as not a measurement.
- Export from the shell: `POST /v1/export`, `GET /v1/exports`, `GET /v1/exports/{name}`;
  files under `<workspace out>/exports`; the exporter's `gold_from_blob`.
- The spend line: `GET /v1/spend?agent=&since=`; the status bar shows list-price spend.
- Workspaces: a first-run picker, `GET /v1/workspaces/{name}/resources`, a workspace card.
- `GET /v1/council/rules` and a card that describes how the council decides.
- A judge definition file prefills the reviewer builder; the providers section says where the
  key in force comes from; the contract version scheme is stated.
- `LITHRIM_JUDGE_CACHE_DIR`: dspy's disk cache scoped to the workspace (`<workspace out>/cache`).

### Changed
- Shared components lose their clinical copy (Reviewer verdict, Source/Response labels, a
  neutral sample criterion, "Terminology match (SNOMED)").
- README and SETUP no longer say `docker compose up --build`; the compose files pull the
  pinned published images. The setup-journey sentence lists every rail step.

### Fixed
- A judge read called directly by the chat tool no longer crashes on the dependency sentinel.

## [0.1.25] — 2026-09-10

The public cut of the RAGTruth pilot: the loop as a generic CLI, the dataset as an example.

### Added
- The `lithrim` CLI (`lithrim load | configure | grade | calibrate | regrade | export | score |
  spend | replay | run`): the product loop from a terminal against a running stack. A dataset
  enters through an adapter (`--adapter path/to/adapter.py`) and a `kind: importer` manifest;
  the reviewer through a judge definition file; the engine names no dataset. Every paid verb
  refuses without `--confirm-cost`.
- Importer manifests declare where an imported case keeps its source id, gold spans, task, and
  generating model (`source_id_path`, `gold_spans_path`, `task_path`, `generator_model_path`) and
  the dataset's training class names (`training_classes`); the engine falls back to the neutral
  top-level fields, so a corpus with no manifest still works (`docs/IMPORTERS.md`).
- `lithrim replay` / `make loop-demo`: one loop round at $0 from committed judge baselines,
  scored against human labels in both vocabularies; CI runs it on the RAGTruth sample.
- The cohort grade as a resumable background job: `POST /v1/cases/grade {background: true}`
  answers with a job id, `GET /v1/jobs/{id}` reports progress and the rows so far, the record
  persists under the workspace out dir, and `{resume: id}` grades only the cases without a
  verdict. The shell and the CLI poll it.
- The scorecard shows failed reviewer calls ("decided without that vote"), cache replays, and a
  per-reviewer Served block (model versions observed, mean latency, tokens); the Reviewers tab
  shows the served version, latency, and tokens per vote.
- `examples/ragtruth/`: the RAGTruth adapter, the detector judge definition, and the pilot's
  experiment arms (paper prompt, ensembles, an experimental Azure fine-tune client) as measured
  records; `docs/reproduction/RAGTRUTH_LOOP.md` runs the loop from the published images.

### Changed
- Judge optimize (UI and API) pins compiled demos into the workspace only through a held-out
  gate: the optimizer's files are staged, a set whose held-out score is below the pinned set's is
  not pinned (`force_pin` overrides, recorded), and the response carries `pin`. The editor says
  pinned / not pinned instead of promising a later binding step.
- The capability card records the boundaries measured on RAGTruth: ensembles negative on a
  two-code task, a fine-tuned small model as a cost trade (not a training platform), offsets as
  importer metadata rather than an engine span type.
- Positioning: Lithrim is described as an expert reviewer agent (judges raise signals,
  signals trigger grounding checks, each case is cleared / flagged / escalated with evidence).
  `make demo` now reports what backed its verdict (`floor_backstopped`) instead of
  attributing a judge-only rescore to the floor.
- The report pane and the inline verdict card title a graded case by the reviewer's decision
  when the record carries one: Flagged (a check contradicted the artifact), Cleared (a check
  confirmed it or disproved the judges' signal), or Needs a person (nothing proven either way),
  with the reason and evidence under the title. Records from an earlier server render as before.
- Fact-check rows print what the check found (reason, missing and present values), and the
  passes a check recorded render as "Confirmed by a fact-check" so an escalated case shows what
  was verified. The section heading says "confirmed the result" when the reviewers had already
  blocked, and "changed the result" only when the pre-floor verdict differs from the final one.

### Fixed
- The Reviewers tab read only the in-session run and said "No run yet" for a case with a
  stored run while the Report tab showed it. Both tabs now hydrate the same persisted record.
- The batch scorecard (Run eval / Grade all) tallied engine verdicts, so five BLOCKs read
  "5 flagged" while the report pane called four of them "Needs a person". The grade matrix and
  scorecard rows now carry the review block, and the card's tally, row words and narrative
  count by it ("1 flagged · 4 need a person · 0 cleared"); rows without one keep the verdict
  wording.
- Dependencies: `litellm` is capped `<1.97` on every extra that imports it. litellm 1.97+
  imports `typing.NotRequired` (Python 3.11+) on its import path while declaring
  `>=3.10`, which broke the assistant probe and the BYO-Claude judge path on Python 3.10
  (CI and the `python:3.10-slim` BFF image at v0.1.21). Last good is 1.96.2.
- The global Azure council branch sent `logprobs` to every deployment; a MaaS deployment
  (Mistral) rejects the parameter and the judge died into a silent empty WARN. It now applies
  the same deployment-granular gate as the per-role branch (confidence-dark, never a dead judge).

### Added
- `review_state()` in the engine and `composite()["review"]`: the cleared / flagged / escalated
  decision is computed once and rides every graded record (the queue script imports it; its
  output is pinned byte-stable). Floor rows carry their evidence, and the persisted `grounded`
  block carries `floor_passes` and `coverage` for parity with the composite.
- `value_grounding` core floor: a value the artifact states must be present in the source;
  a violation on a structured record source, a named lead on prose (measured on RAGTruth).
- `GroundedResult.floor_passes` + `composite()["floor_passes"]`: a satisfied floor is recorded
  as evidence, and a PASS it examined counts as floor-backstopped.
- The neutral `_core` pack binds `value_grounding` (floor) and `source_grounding` (suppress)
  contracts, all in-process.
- `make queue` (`scripts/queue_demo.py`): five public RAGTruth cases (MIT, human-labeled)
  worked into cleared / flagged / escalated at $0, with committed judge baselines
  (`samples/ragtruth/`, `scripts/ragtruth_cases.py`).

## [0.1.0-ce] — Unreleased

First public Community Edition release.

### Added
- The deterministic **grounding floor** + in-process **council**, with
  by-construction labeling and an audit spine.
- `make demo` — a $0, offline, no-key, no-pack replay that shows the floor flip a
  council `PASS` to `BLOCK` on a neutral fabricated-claim case.
- Neutral open packs: `_core` (generic content review) and `support_ticket_qa`
  (both `tier: core`), plus the plugin / connector (MCP) interface.
- A synthetic clinical sample pack (`clinical_scribe`, `tier: core`) — a by-construction
  teaser of the ambient-scribe note-review domain (missing allergy, wrong dosage, fabricated
  history, negation reversal, diagnosis upcoding, + a clean negative). Synthetic, not the
  curated Pro `healthcare` pack.
- BYOK single-provider live grading (OpenAI / Azure OpenAI).
- Release scaffolding: an honest README with an explicit limits section,
  `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, a credential-free CI
  workflow, and issue / PR templates.

### Notes
- The full clinical `healthcare` domain pack is **distributed separately**; a
  fresh clone is clinical-free and boots on the neutral `_core` pack.
- **Not a medical device, not clinically validated** — see the README "Intended
  use & safety" note. All bundled sample data is synthetic (Synthea).
