# Changelog

All notable changes to Lithrim are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
date-based pre-1.0 versions.

## [Unreleased]

### Changed
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
