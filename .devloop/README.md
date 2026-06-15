# `.devloop/` — monitored-execution workflow

A monitor / executor / critic three-actor development workflow, scaffolded by
`devloop init`.

- `personas/` — the three roles. Read `MONITOR.md` to plan + audit, `EXECUTOR.md` to
  implement one driver, `CRITIC.md` to do a cold spec-adherence pass.
- `state/` — `streams.json` (registry) + `STREAM_<stream>.md` (live phase table + seams).
- `tasks/` — `TASK_PACK_<stream>.json` (the roadmap; you author the phases).
- `prompts/` — per-cycle driver bundles.
- `sessions/` — executor session logs + critiques + handoff briefs.
- `templates/` — DRIVER / CRITIQUE / SESSION_LOG starting points.

## Loop

Monitor authors a driver → user pastes the kickoff into a fresh session → executor
plan-reviews, implements, commits, logs, returns → monitor audits (7-item) + critiques
(4-question) + closes → next cycle. Monitor never implements; executor never plans
beyond its cycle; critic never edits.

Slash commands (`/devloop-status`, `-resume`, `-kickoff`, `-audit`, `-critique`,
`-close-phase`, `-expand-driver`, `-run`) live in `.claude/commands/`.

Autonomous mode (opt-in, `devloop init/update --with-autonomous`) adds native
subagents in `.claude/agents/` and `modules/autonomous.md`; `/devloop-run <stream>
<phase>` drives a cycle via subagents with Gate 0 + evidence capture, halting for
you before anything irreversible.
