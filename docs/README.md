# Docs index

The tracked documentation for Lithrim. Start with the repo-root
[`README.md`](../README.md) (what this is, quickstart, intended use and limits) and
[`SETUP.md`](../SETUP.md) (the hands-on Docker path to a first grade).

## In this directory

| Doc | What it covers |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The components, engine, packs/plugins, judge council, grounding floor, BFF, UI, JUTE mapper, run trail, and how they connect. |
| [`CAPABILITY_CARD.md`](CAPABILITY_CARD.md) | The honest capability card: what the deterministic floor verifies, what it does not, how it abstains, and what it depends on. |
| [`EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`](EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md) | The determinism spec the engine implements: the defect register (D1–D7) and the by-construction case-generation protocol. |
| [`JUTE_MAPPER_ADDON.md`](JUTE_MAPPER_ADDON.md) | The bundled ingest mapper for arbitrary agent-trace JSON: what needs it, what doesn't, and how to run core-only. |
| [`ONTOLOGY_FLAG_LIFECYCLE.md`](ONTOLOGY_FLAG_LIFECYCLE.md) | Flag classes (reference vs gradeable) and the lifecycle rules that keep labels true by construction. |
| [`POLICY_HOLDOUT_HYGIENE.md`](POLICY_HOLDOUT_HYGIENE.md) | The tune/certify separation: why a judge is never certified on the rows it was optimized on. |
| [`specs/SPEC_TOOL_CONNECTORS.md`](specs/SPEC_TOOL_CONNECTORS.md) | The tool / MCP connector plane: declaring a connector, transports, secrets, reference connectors. |

## At the repo root

| Doc | What it covers |
|---|---|
| [`REPRODUCING.md`](../REPRODUCING.md) | Re-running the published study (Zenodo DOI + OSF prereg) from this repo. |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Dev setup, optional extras, test/lint expectations. |
| [`SECURITY.md`](../SECURITY.md) | Reporting a vulnerability (GitHub private reporting), secret handling. |
| [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | Contributor Covenant 2.1. |
| [`CHANGELOG.md`](../CHANGELOG.md) | Release notes. |
