# CRITIQUE — bench-salvage phase FAUTH-2a (fresh cold critic)

> Persisted verbatim by the monitor from the cold-critic subagent's return (the critic has no
> Write/Edit tools by design). Commits: parent (FAUTH-2 HEAD) `48162ad` → HEAD `0f91a1c`
> (`210ccce` test → `6ca1187` grounding → `0f91a1c` bff).

verdict: **NON-BLOCKING FINDINGS** (the original BLOCKING finding S-BS-FAUTH2-2 is fixed; Gate 0 could
not be run by the critic — runner denied — so deterministic supremacy is *attested-not-reproduced*;
see the one NON-BLOCKING caveat)

```
gate0: { suite: COULD-NOT-RUN (runner denied — Bash/python/pytest/curl/vitest/ruff all denied this session),
         lint: COULD-NOT-RUN, types: n/a, tests_first: YES (git: 210ccce test-only, precedes 6ca1187/0f91a1c) }
```

## Runner status
The critic's Bash tool was fully denied this session for everything except git read-ops/grep/file-reads
(`python -c`, `pytest`, `curl` all permission-denied — the same flapping outage that blocked both
FAUTH-2a executors). Per the kickoff fallback, the critic did NOT re-run the suite and did NOT restate
the monitor's 28/695/23 numbers as confirmed; it verified everything statically checkable from git +
source (most of the cycle's load-bearing claims).

## Gate 0 — verified vs could-not-run
| Check | Result |
|---|---|
| Python suite @ HEAD & parent | **COULD NOT RUN** (pytest denied). Monitor claims 28==28 (HEAD 28f/695p/23s). Arithmetic internally plausible (+2 net passes = the 2 new tests); the `test_pack_dist::test_a1` ⇄ `test_byoc_provider::test_build_trio` order-flap is corroborated by the FAUTH-2 critique. Not independently reproduced. |
| Tests-first | **YES, git-verified** — `210ccce test` → `6ca1187 grounding` → `0f91a1c bff`; `git show --stat 210ccce` = 1 file (test only). |
| RED-at-parent, right reason | **VERIFIED via git** — `48162ad:app.py:1687-1700` calls `suppress_executors()` no-arg → process env; the new test sets process=`_core` + ws=`healthcare`, so at parent the endpoint returns `_core`'s 4 keys → `assert "record_presence" in …` fails (the exact bug). `test_accessors_optional_pack_arg_is_additive` is also RED at parent (`suppress_executors("healthcare")` → TypeError, no param existed). |

## The 4 questions
### Q1 — driver intent met — MET
- Endpoint (`app.py:1706-1708`) + gate (`app.py:2433-2434`) now resolve `workspace.get_active_workspace().pack`
  and pass it to `suppress_executors(...)`/`floor_executors(...)`; endpoint returns `"pack": ws_pack`.
- The false docstring is corrected (`48162ad:app.py:1695-1696` "process-global active pack … exactly what
  ground() reads" → HEAD `app.py:1697-1702` resolves the active workspace's grade pack per-request).
- Mirrors `_active_lens_by_role`/S-BS-154 (`app.py:1361-1376`) exactly (lazy import, BFF-confined).
  `Workspace(name=,pack=)` is a valid dataclass (`workspace.py:68-73`) → the test monkeypatch is sound.

### Q2 — the BLOCKING bug is fixed, non-vacuous — MET (deterministically by inspection); the LIVE re-proof is OWED on the critic's side
- `test_gate_resolves_the_active_workspace_pack_not_the_process_pack` (`tests/bff/test_grounding_contract_gate.py:282-330`)
  asserts both directions ((a) endpoint includes `record_presence`/`snomed_subsumption`, `pack=="healthcare"`
  under process=`_core`; (b) the gate PERSISTS a `record_presence` contract = 200, not 422; prose still 422).
  GREEN by construction (code traced; could not execute).
- A4 (`:107-134`) is now order-INDEPENDENT (monkeypatches `get_active_workspace→healthcare`, pins
  `_registered("healthcare")`) — the correct test-side remedy for the mutable-workspace-global the fix introduced.
- **LIVE check NOT performed by the critic** (`curl` denied) — could not mirror the original critic's 422→200.

### Q3 — MOAT / scope — CLEAN
- Diff = **exactly 3 files** (`app.py`, `grounding.py`, the gate test); no foreign-WIP sweep (session-start
  dirty tree left uncommitted; each commit `--stat` touches only its scoped file).
- `grounding.py` diff = **exactly the additive `pack=` param** (3 signatures + 3 one-line `pack or _active_pack()`
  bodies + docstrings); no logic/mechanism change.
- **0-diff moat:** `compliance_council.py` (holds `_apply_consensus`), `withstands.py`, `judge_metric.py`,
  `signals.py` are NONE in the diff → byte-identical; `signals.py:183` still reads `suppress_executors()`
  **no-arg**. Every accessor caller except the two BFF sites is no-arg (`signals.py:183`, `grounding.py:503/543/597-598`,
  `floor_contract_types` forwards its own optional param at `:402`).
- **No new SDK-MCP tool** (`agent/{tools,loop,adapter}.py` not in diff → count 20, allowlist + deny hook 0-diff).
- No shell file in diff → vitest baseline unchanged.

### Q4 — honesty gap — ONE NON-BLOCKING discrepancy
- The freeze relaxation is EXACTLY the optional param (no smuggled change). Commit subjects/scope/session-log all match git.
- **NON-BLOCKING — A-LIVE attested-by-monitor, not independently reproduced (this critic).** The session log's
  live claim (BFF pid 53262, `ps eww` no `LITHRIM_BENCH_PACK` → process=`_core`; endpoint returned the healthcare
  7-key set after hot-reload; result requires both edits else 500) is internally sound, but the critic could not
  verify it (`curl`/`ps` denied). The gate POST-200 was not exercised live (monitor avoided workspace residue) —
  covered by the deterministic test. Not BLOCKING, but R3's "A-LIVE for real" + an independent live confirmation
  (the one thing the original critic did — the 422) was not mirrored.

## New seams
- **None opened by the code.** The environment seam `S-BS-FAUTH2a-2` (executor-subagent sandbox deny) **recurred
  for the critic** — Gate-0 could not be run cold. Genuine PROCESS GAP: a HARD-GATE cycle whose "deterministic
  gate is supreme" was closed by the monitor without an independent runner and critiqued without one. The Gate-0
  supremacy is, for this cycle, **un-exercised by any independent party** — OWED until a healthy-runner re-run.

## Discipline self-check
- [x] Attempted Gate 0 first; runner denied → marked COULD-NOT-RUN, inferred no numbers.
- [x] Tests-first git-verified; read diff via git not the summary; read session log last.
- [x] Findings cite file:line; no BLOCKING asserted on judgment alone; edited nothing; conferred with no one.
- [ ] **Did NOT run suite/lint/live-curl cold** — runner denied. The "deterministic gate, run independently"
      property is NOT satisfied this turn; the verdict is bounded by that.

## Bottom line
On **static** evidence this is a CLEAN fix of S-BS-FAUTH2-2: both call sites resolve the workspace pack (the
S-BS-154 precedent), the false docstring is corrected, `grounding.py` is purely the additive optional `pack=`
(no-arg byte-identical), the moat (`_apply_consensus`/`withstands`/`judge_metric`/`signals.py:183`) is 0-diff,
tool count 20, scope exactly 3 files, tests-first/RED-at-parent git-verified. Returned **NON-BLOCKING rather
than CLEAN** for one honest reason: the critic could not run Gate 0 or the independent live re-proof (Bash
denied), so deterministic-supremacy + A-LIVE rest on the monitor's attestation — and the monitor is the party
whose claims the critic was spawned to verify. The code-level verification is as strong as possible without a
runner; **an independent Gate-0 run + live re-proof is OWED**, to be discharged by a critic/owner with a working
runner before this gate is treated as fully independently closed.
