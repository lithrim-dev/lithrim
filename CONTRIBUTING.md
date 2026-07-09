# Contributing to Lithrim

Thanks for considering a contribution. Lithrim is a developer evaluation
harness; the bar for changes is correctness and honesty, not breadth.

## The one rule that matters

**No manufactured wins.** This project's value is that it tells you where it
*doesn't* work. Don't tune a demo to look better than the mechanism is — if a
result is a loss, we report the loss. PRs that overstate a capability (in code,
docs, or sample data) will be asked to add the honest caveat.

## Development setup

Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # pytest + ruff — lint + a clean collect + a subset of the suite
                               # (the FULL suite needs the extras table below)
```

The base install (`pydantic`, `pandas`) is enough to run the **$0 offline demo**:

```bash
make demo        # council votes -> grounding floor flips PASS->BLOCK -> audit
```

Optional extras unlock more of the stack — install only what you need:

| Extra | Adds | Unlocks |
|---|---|---|
| `dev` | pytest, ruff | run the suite + lint |
| `council` | openai, tenacity, pydantic-settings | the in-process council (real LLM grading) |
| `bff` | fastapi, uvicorn, httpx | the shell BFF API (`apps/bff`) |
| `agent` | claude-agent-sdk | the conversational chat loop |
| `verification` | dspy, httpx | the JUTE validator generator + live connectors |
| `observation` | openai, tenacity | KPI observation agents |
| `pg` | psycopg, yoyo-migrations | Postgres-backed provenance |

The suite is designed to pass **without any model key** — LLM-dependent tests use
mocks/replay, and clinical pack tests skip when the (separately distributed)
healthcare pack isn't present. To run the **full** suite credential-free, install the
non-credential extras (this is what CI does):

```bash
pip install -e ".[dev,council,verification,bff,agent]"
pytest -q        # 1000+ tests, green, no API key (key-needing tests skip)
```

A minimal `.[dev]` install runs the offline demo, the linter, and a large subset; a
handful of tests need an optional package (`dspy`, `fastapi`, …) and skip-or-fail
without it, so install the extras above before relying on a full local run.

## Before you open a PR

```bash
ruff check .     # lint (make lint)
pytest -q        # the suite (make test) — must be green credential-free
make demo        # the offline demo still runs
```

- Keep diffs focused; match the surrounding style. The shell JSX is hand-compact
  (no prettier) — format your touched lines by hand.
- Tests-first for behavior changes: add the failing test, then the fix.
- Don't commit secrets, local paths, or run artifacts. `.env*`, `*.sqlite`,
  `out/`, and `node_modules/` are gitignored — keep it that way.

## Adding a synthetic sample case

Sample cases are **true by construction** — the label is justified by how the
case was built, not by a downstream judge. A new case must:

1. use only safety-flag codes present in its pack's `taxonomy_snapshot.json`,
2. carry an `injection_recipe` (defect type + the field/span mutated + pre/post
   values) **or** be a clean negative (`injection_recipe: null`,
   `expected_safety_flags: []`),
3. pass `scripts/lint_golden_against_taxonomy.py`.

See [`CLAUDE.md`](CLAUDE.md) for the full invariant. Never load **real** patient
data — all bundled clinical-shaped data is synthetic (Synthea).

## Adding a checker / judge or a connector

Judges are authored by assigning an ontology and a role prompt; connectors are
manifest entries (MCP transport) plus an executor. See
[`docs/specs/SPEC_TOOL_CONNECTORS.md`](docs/specs/SPEC_TOOL_CONNECTORS.md) and the
`packs/_core` / `packs/support_ticket_qa` packs as worked examples.

## Reporting an over-claim

If a doc or output promises more than the code proves, that's a bug. Open an
issue (there's an "over-claim" template) — we'd rather fix the claim than keep it.
