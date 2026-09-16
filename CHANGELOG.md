# Changelog

All notable changes to Lithrim are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
date-based pre-1.0 versions.

## [Unreleased]

### Fixed
- The model a judge is configured with is now the model that grades it. `lithrim configure
  --model openai/gpt-4.1-2025-04-14` wrote the string onto the judge record, but the council
  resolves a role's model from the per-role binding env, which was only written for a judge
  carrying a separate `provider` field — so the CLI's model never reached the council and every
  vote ran on the provider default. A `provider/model` string on the record is read as the
  binding it is, and `GET /v1/judges/{role}` reports the same pair the grade will use. Found in
  the paid OpenAI reproduction of v0.1.31: 90 cases graded on gpt-4o under a manifest naming
  gpt-4.1-2025-04-14 (Azure masked it, since the default deployment matched).
- A calibration round that makes the judge WORSE can no longer become the first pin. The gate
  compared only against a previously pinned score, so a first round pinned whatever it produced
  ("no pinned score to compare against") — including one whose own held-out graded fell
  (measured: 0.65 to 0.64 pinned, and the after round then scored below the before round). The
  round's own baseline, which the optimizer already writes beside the optimized score, is the
  comparison a first pin has; `force` still pins and the reason says so.
- The export verb reads the workspace the service is on, like every other verb — its corrections
  log and collections db defaulted to `default`, so an export could publish another workspace's
  rounds. With `--grade`, the export also refuses when the served models on its manifest are not
  the ones that answered the round it names.
- A paid calibration re-samples instead of replaying the judge cache. The grade path has set
  `LITHRIM_JUDGE_CACHE=0` since CACHE-TRAP-1; the optimize path set only the cache directory, so
  a second calibration could finish in seconds with the previous round's numbers — and the pin
  gate then decided on a replay. Both the service and the CLI now run the optimizer with the
  cache off.
- The CLI reads and writes the workspace the SERVICE is on. `--workspace-out` defaulted to
  `out/workspaces/default/out` whatever workspace was active, so after switching the service the
  CLI pinned demos into `default` and the next grade in the new workspace refused on a pin that
  did not belong to it. It resolves the active workspace from `GET /v1/workspaces` (or
  `--workspace`); an explicit `--workspace-out` still wins and an unreachable service falls back
  to `default`.
- An arm whose judge answered on a model other than the dated id it pins is refused instead of
  written out: `served_models_observed` was recorded and never compared. A deployment name or an
  operator attestation is still reported rather than accused, because neither is comparable to a
  served model id.

## [0.1.31] — 2026-09-15

The three critical findings from the v0.1.30 review, plus the job, provider and docs
follow-ups behind them.

### Changed
- **Breaking (API):** `POST /v1/cases/grade` refuses a PAID grade without `confirm: true`
  (422), the way `POST /v1/judges/{role}/optimize` always has. This includes `resume`, which
  runs on the original job's paid flags — the shell's Resume button billed with no cost dialog
  before. The $0 replay path (neither `live` nor `in_process`) spends nothing and needs no
  confirm. The shell sends the confirm from its in-DOM dialog and routes Resume through it;
  `lithrim grade` / `regrade` send it with `--confirm-cost`.

### Fixed
- A calibration round whose held-out set is not the one the pinned demos were scored on is now
  refused instead of pinned. The "no comparable score" branch pinned unconditionally, so a
  regressing round could reach the production judge by changing the subset it was scored on;
  `force` (`--force-pin`) still pins and the reason says so.
- Calibrating a corpus that carries its own split tags no longer strides across them. The
  stride ordered every labelled case by id and took every third as held-out, ignoring the split
  each case was imported with, so a labelled dataset's test rows could train the demos and
  decide the pin. The engine refuses such a corpus by name, the optimize route answers 422
  before any paid call, and the reviewer card no longer offers the stride.
- A resume refused by the duplicate-job 409 no longer leaves the job stuck reading `running`:
  the record is touched only after every refusal.
- A grade whose judge calls all fail the same auth/config way (401, 403, a missing deployment)
  stops after three such cases and fails with the provider's own message, keeping the graded
  rows for a resume, instead of grading the whole cohort into empty votes. A provider refusal
  (a content filter) stays a miss and never aborts. The judge's error text rides the row.
- `lithrim calibrate` runs on the provider binding and the key connected in the app, like a
  grade; it used to fall back to the role's default deployment and fail after the grade was
  already paid for.
- One poller per job in the shell: a second follower joins the first instead of doubling the
  polls and clobbering the progress chip, an agent switch stops the previous agent's pollers,
  and the reviewer card shares one poller per calibration across mounted cards. The cost dialog
  now closes when the service accepts the job instead of waiting out the whole run with Cancel
  disabled.
- A round name compares only within its own split, so a calibration round never sits beside a
  test round as a before/after. The shell asks for a comparison only for the after round.
- The reviewer editor's fact-check list offers only the checks the ACTIVE pack can run: the
  static list offered `dosage_grounding` (a clinical floor that ships with the healthcare pack)
  on the neutral `_core` pack, so a reviewer could reference a check nothing would execute.
- The export format picker offers only the formats the importer declares (a dataset with no
  training prompt module cannot write the chat one), instead of sending the human into a 422.
- Both compose files pass `LITHRIM_ALLOWED_ORIGINS`, `LITHRIM_OPTIMIZE_TIMEOUT_S` and
  `LITHRIM_GRADE_TIMEOUT_S` through, so the documented knobs work from a compose `.env`.
- Docs: the stale "held out on the test split" lines, the RAGTruth citation (Wu et al.
  everywhere), the Azure deployment model string with the OpenAI form beside it, the curls the
  no-clone reproduction needs, the release the compose file pins, and the README's "pulls".

### Security
- The chat export loads only the training prompt module the importer manifest declares; the
  route used to import whatever path the request named.
- Both ingest routes refuse a blob over `LITHRIM_INGEST_MAX_MB` (default 64) with the two sizes
  and the knob, instead of reading an unbounded paste into memory.

## [0.1.30] — 2026-09-11

Calibrate as a background job, so a pilot-scale calibration runs from the shell.

### Fixed
- A calibration at the pilot's scale (315 training, 135 dev cases) no longer dies with a 500:
  the optimizer ran inside the request with a hardcoded ten-minute limit. Calibrate now runs as
  a background job on the grade-job pattern (202 with a job id, the record under the
  workspace's jobs with kind `optimize`, the role and the full result block, a list filter by
  kind, restart reconciliation, a 409 for a second calibration of the same role), and the judge
  editor starts it, polls it, finds it again after a reload, and shows the service's reason on
  failure. The limit is `LITHRIM_OPTIMIZE_TIMEOUT_S` (default four hours); a timeout is a failed
  calibration with nothing pinned (504 on the synchronous path). The per-case grade limit is
  `LITHRIM_GRADE_TIMEOUT_S` (default 600).

### Added
- ⌘K "Grade the test split", the before round, available after a reload (it was only on the
  import card right after a load, which left "Grade all cases" as the only way back).

## [0.1.29] — 2026-09-10

Held-out hygiene for the pin gate, and the training export from the shell.

### Fixed
- The pin gate no longer reads the test cut. The calibration corpus (the RAGTruth adapter's and
  the shell's split calibrate) is the calibration split alone, with a deterministic,
  source-disjoint 30% `dev` slice the gate scores on; the test cut stays untouched until the
  after round. `run_optimize` and `scripts/optimize_judge.py` take the held-out split
  (`heldout_split` / `--heldout-split`, default `test`).
- A pinned score is compared only on the same held-out set. The score sidecar records the
  held-out identity (split, size, digest of the case ids) and the manifest names the split; a
  set pinned before this change (scored on the test cut) or a changed dev slice is not
  comparable, so the round is refused with that reason rather than pinned (re-scoring the
  pinned set would be a paid round); `force` pins it deliberately and says so.
- The chat (azure-chat) export no longer crashes on a structured prose source (every RAGTruth QA
  row); a row the training prompt still cannot fill is refused by name.

### Added
- Grade the calibration split from the shell (import card, `⌘K`), a paid round of its own that
  a training export draws on.
- The export control picks a format (generic, paper, azure-chat) and says which split it
  exports from; the training formats only from a calibration-split round.
- The importer manifest's `training_prompt_module` names the prompt a chat training row is
  written with, so the shell's azure-chat export needs no path.

## [0.1.28] — 2026-09-10

Fixes from the v0.1.27 published-image test.

### Fixed
- A malformed KPI pin (empty field, unknown op, missing or non-numeric bound, `min > max`,
  empty or non-list `allowed`, unknown mode or target) is now refused when authored, as the
  docs said; v0.1.27 accepted it and skipped it at grade time, so the KPI never ran. The spec
  holds the one rule the author gate and the grade share.
- KPI contracts stack per flag, one per field, and never displace a flag's other checks; a new
  version of the same KPI replaces its predecessor. Other contracts stay one per flag.
- An upload through the attach button ticks the rail's Load step without a reload.
- The scorecard read no longer says the floor's blocks were defects "the reviewers missed"; the
  count includes blocks a reviewer also raised.

### Added
- ⌘K "Add a check or KPI contract" opens the contract builder without the assistant.

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
