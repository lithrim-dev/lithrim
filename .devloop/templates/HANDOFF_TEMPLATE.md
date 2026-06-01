# HANDOFF — `<stream>` phase `<N>` → phase `<N+1>` kickoff

> **Written by the monitor on cycle close.** Load-bearing context for
> the next monitor session that takes over after a compaction or
> after-hours break. Committed alongside the close-out commit.
>
> **Path:** `.devloop/sessions/HANDOFF_<stream>_phase<N+1>_kickoff_YYYY-MM-DD.md`

---

## What just landed

- **Closed phase:** `<N>` — `<title>` (commits `<sha>..<sha>`)
- **Critique verdict:** `<CLEAN | NON-BLOCKING | BLOCKING>` (`<critique-md-path>`)
- **Audit verdict:** `<CLEAN | DRIFT>` (per `.devloop/state/STREAM_<stream>.md`)
- **Session log:** `<session-log-path>`

## What's next

- **Next phase:** `<N+1>` — `<title>`
- **Driver bundle:** `<bundle-id>` (`<status: stub | ready>`)
- **Driver path:** `.devloop/prompts/<stream>_phase<N+1>_<scope>_driver.md`
- **Blocked by:** `<none | phase <M> | seam S-<id>>`

## Open seams for `<stream>`

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-`<X>` | `<title>` | `<sev>` | `<loc>` | phase `<n>` | `<open|resolved>` |

## Load-bearing context the next monitor MUST know

1. `<one paragraph: a non-obvious decision made in this cycle that
   shapes the next one>`
2. `<one paragraph: a known landmine the next monitor might step on>`
3. `<one paragraph: anything the user said in this cycle that ought
   to persist as a preference>`

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_<stream>.md` (especially the phase table
   and open seams).
3. Read this handoff doc.
4. Read the most recent session log: `<session-log-path>`.
5. Run `git log --oneline -10` in the target repo(s) to see commit timeline.
6. Wait for user input. Don't autonomously start the next cycle.

## References

- Stream state: `.devloop/state/STREAM_<stream>.md`
- Prior cycle session log: `<path>`
- Prior cycle critique: `<path>`
- Roadmap context: `<repo-root>/<roadmap-or-spec-file>`
