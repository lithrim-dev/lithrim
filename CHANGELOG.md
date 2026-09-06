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

### Fixed
- The global Azure council branch sent `logprobs` to every deployment; a MaaS deployment
  (Mistral) rejects the parameter and the judge died into a silent empty WARN. It now applies
  the same deployment-granular gate as the per-role branch (confidence-dark, never a dead judge).

### Added
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
