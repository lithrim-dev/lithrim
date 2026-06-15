# Module: autonomous (opt-in)

> Runs the devloop cycle with **native subagents** instead of manual paste
> handoffs, and captures evidence automatically. Disabled by default; enable with
> `devloop init --with-autonomous` (or `devloop update --with-autonomous`). Built
> on the tests-first / Gate 0 contract — that deterministic gate is what makes
> unattended operation safe.

## What it adds

- `.claude/agents/devloop-executor.md` + `.claude/agents/devloop-critic.md` —
  native subagent versions of the personas, spawned via the Task tool.
- `/devloop-run <stream> <phase>` — the orchestrator command. One invocation runs
  a whole cycle: spawn executor → spawn critic → Gate 0 → evidence capture →
  stage → report, halting for you only at the irreversible step.

## The loop `/devloop-run` drives

1. Confirm a driver exists for `<stream> <phase>` (author it first with the
   monitor / `/devloop-expand-driver` if not). The driver is the standing
   plan-approval — there is no per-cycle human plan-review in autonomous mode.
2. Spawn the **devloop-executor** subagent with that driver. It writes tests
   first (RED), implements to GREEN, commits atomically, returns structured.
3. Spawn the **devloop-critic** subagent cold. It runs **Gate 0** (re-run the
   suite/lint/types). RED ⇒ stop and escalate. GREEN ⇒ the 4 fidelity questions.
4. On a clean close, capture evidence (below).
5. Stage close-out artifacts and **halt for your approval** before anything
   irreversible. Report back.

## The autonomy boundary (the load-bearing decision)

| Automatic (deterministic + reversible) | Human-gated (irreversible / outward-facing) |
|---|---|
| plan (driver) → tests → implement → **commit** | `git push`, tag |
| Gate 0 (run suite/lint/types) | deploy, `npm publish` |
| spec-fidelity critique | merging on a green the critic only rubber-stamped |
| evidence capture, summary, stage | the final "ship it" |

Commits are automatic because they are local and reversible, and the driver is
the pre-approval. Anything that leaves the machine stays your call — the loop
runs to *staged + recorded + summarized*, then pings you for one tap.

**Caveat — keep yourself in the loop on fidelity.** Gate 0 catches *functional*
regressions deterministically. The critic is still an LLM-judge for *spec
intent* — do not auto-merge on a green it merely rubber-stamped. Read its
findings before approving the irreversible step.

## Evidence capture (Zyng MCP)

On a clean close the orchestrator produces a proof artifact:

- **App demo present** → call the Zyng MCP: `capture_clips` drives the running
  app headless (Playwright) and screen-records the feature into a raw clip +
  timeline; `publish` uploads the clips + a composition spec and returns a
  managed, narrated MP4. (See `zyng-mcp`; `capture_clips` needs no key,
  `publish` spends credits.)
- **No app** (library / refactor) → fall back to a written proof doc + test-output
  screenshots.

Honest-Δ only: a loss is recorded as a loss, never dressed up as a win. (If the
`proof-capsule` module is also enabled, this capture step *is* the proof capsule.)

### Wiring the Zyng MCP

Add the recorder as an MCP server the orchestrator session can reach (project
`.mcp.json` or your Claude config), e.g.:

```json
{ "mcpServers": { "zyng": { "command": "python", "args": ["-m", "zyng_mcp"] } } }
```

Then `capture_clips` / `publish` are available to `/devloop-run`. Recording an
app that needs login uses a saved session — never type credentials into the run.

## Dispatch from anywhere

`/devloop-run` is the entry point. To trigger it remotely:

- **Phone, zero infra:** open the project on claude.ai/code (mobile) and run
  `/devloop-run <stream> <phase>`.
- **Hands-free / recurring:** wrap it in a scheduled cloud routine (`/schedule`).
- **Text-a-command:** a thin bot → `claude -p "/devloop-run ..."` headless (Agent
  SDK), replying with the summary + MP4 link.

## Why it's a module, not core

The base workflow is deliberately human-in-the-loop (paste kickoffs, owner-gated
commits). Autonomous mode trades that for native-subagent orchestration, which
is only responsible because Gate 0 is deterministic. Enable it on streams whose
acceptance is genuinely test-gated; keep the manual flow where a human plan-review
per cycle still earns its cost.
