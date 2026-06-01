# `.devloop/` — monitored-execution workflow

> Drop-in scaffold for the monitor / executor / critic three-actor
> development workflow. See repo-root or
> `~/Workspace/github.com/lithrim-backend/docs/dev-workflow/README.md`
> for the full system overview.

## Layout

```
.devloop/
├── README.md              this file
├── personas/
│   ├── MONITOR.md         persistent session role (planner + auditor)
│   ├── EXECUTOR.md        fresh-session-per-cycle role (implementer)
│   └── CRITIC.md          fresh-session-per-HARD-GATE role (independent reviewer)
├── state/
│   ├── streams.json       index of all streams in this repo
│   └── STREAM_<name>.md   per-stream live state (phase table + open seams)
├── tasks/
│   └── TASK_PACK_<stream>.json    machine-readable task list
├── prompts/
│   ├── index.json                 registered bundle metadata
│   ├── KICKOFF_MONITOR.md         paste-ready: take over the monitor role
│   ├── KICKOFF_EXECUTOR.md        paste-ready: take over an executor cycle
│   ├── KICKOFF_CRITIC.md          paste-ready: take over a critic pass
│   └── <stream>_phase<N>_<scope>_driver.md   per-cycle driver bundles
├── sessions/
│   ├── session-<stream>-phase<N>-YYYY-MM-DD.json    executor session log
│   ├── critique-<stream>-phase<N>-YYYY-MM-DD.md     spec-adherence critique
│   └── HANDOFF_<stream>_phase<N>_kickoff_YYYY-MM-DD.md
├── seams/
│   └── SEAM_S-<id>_<title>_YYYY-MM-DD.md            optional per-seam doc
├── templates/
│   ├── DRIVER_TEMPLATE.md
│   ├── CRITIQUE_TEMPLATE.md
│   ├── SESSION_LOG_TEMPLATE.json
│   └── HANDOFF_TEMPLATE.md
├── spikes/                 throwaway exploration code
└── bin/
    └── devloop             CLI helper (optional; see bin/README.md)
```

## How to start a session

### Monitor (planner + auditor)

```bash
# In a fresh Claude Code session in this repo:
#   Paste the contents of .devloop/prompts/KICKOFF_MONITOR.md
```

### Executor (implementer, one cycle)

```bash
# In a fresh Claude Code session in this repo:
#   Paste the contents of .devloop/prompts/KICKOFF_EXECUTOR.md
#   with <STREAM>, <N>, <SCOPE> substituted for the cycle target.
```

Or invoke `/devloop-kickoff <stream> <phase>` (global slash command, if
installed) to print a pre-filled kickoff.

### Critic (independent reviewer, HARD GATE only)

```bash
# In a fresh Claude Code session in this repo:
#   Paste the contents of .devloop/prompts/KICKOFF_CRITIC.md
#   with the spec paths + commit range + stream + phase substituted.
```

## Slash commands (globally installed)

| Command | Purpose |
|---|---|
| `/devloop-status` | Dashboard of all streams + open seams + recent activity |
| `/devloop-resume` | Compact resume: last cycle, open seams, recommended next |
| `/devloop-kickoff <stream> <phase>` | Print paste-ready executor kickoff |
| `/devloop-audit <stream> <phase>` | Mechanical 7-item audit of latest cycle |
| `/devloop-critique <stream> <phase>` | Run the inline 4-question critique |
| `/devloop-close-phase <stream> <phase>` | Audit + critique + close out |
| `/devloop-expand-driver <stream> <phase>` | Re-grep + flesh out a stub driver |

## Conventions

1. **Diagnose-before-edit gate.** Every root-cause claim needs an
   evidence block above it. Tagged CONFIRMED / INFERRED / HYPOTHESIS.
   See `personas/MONITOR.md` and `personas/EXECUTOR.md`.

2. **File:line citation discipline.** Driver authoring re-greps every
   citation against current code. See `personas/MONITOR.md` §Phase 1a.

3. **Plan-review checkpoint.** Executor never writes code without
   posting a plan and getting user approval.

4. **Scope guardrails.** Every driver has an explicit "NOT in scope".

5. **Atomic commits per logical unit.** No bundled
   architecture + feature + docs commits.

6. **Per-repo atomic commits across multi-repo work.** Each repo gets
   its own focused commit. Monitor never cross-commits.

7. **Owner-gated:** no autostart, no auto-commit, no push, no publish
   without explicit user approval.

## Adapting the scaffold

The example files (`STREAM_EXAMPLE.md`, `TASK_PACK_EXAMPLE.json`, the
`EXAMPLE-stream` entry in `streams.json` and `prompts/index.json`) are
templates to copy and rename. Delete them once you have at least one
real stream defined.
