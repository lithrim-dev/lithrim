# Critique — bench-salvage SHEPHERD-1c (HARD GATE)

**Verdict: PASS — 0 BLOCKING.** Fresh-critic fan-out of 4 independent lenses (moat byte-stability,
S-BS-154 correctness, S-BS-153 correctness + honest-Δ, test non-vacuity), each re-reading the tree and
re-running the suites. Implementation committed `a003863` (parent `132f24c` driver).

## Per-lens verdicts

| Lens | Verdict | Blocking |
|---|---|---|
| MOAT + byte-stability | PASS | 0 |
| S-BS-154 correctness (offer/gate pack resolution) | PASS | 0 |
| S-BS-153 correctness + honest-Δ | PASS | 0 |
| Test non-vacuity + hygiene | PASS | 0 |

## What the critics independently confirmed

- **Moat / frozen set 0-diff vs `132f24c`** (`git diff … | wc -l` = 0): `compliance_council.py`,
  `signals.py`, `judge_metric.py` (incl. the module-global `LENS_BY_ROLE` at :64, byte-imported by the
  byte-frozen `signals.py:40` as the withstands-gate default `lens_by_role` @ :85/100/132),
  `apps/bff/agent/tools.py`, `apps/bff/agent/loop.py` (incl. `_deny_non_lithrim` at :203, still **first**
  in the `PreToolUse` hook list), and `journey.js` (deriveSteps/isDone). W1 added a **separate** BFF-side
  `_active_lens_by_role()` resolver instead of mutating the frozen global — the moat scope-check value
  cannot shift.
- **W1 confined to `app.py`, no council re-entry:** `_active_lens_by_role()` lazy-imports ONLY
  `harness.pack` + `harness.workspace`; `pack_lenses()` reads the snapshot JSON directly (acyclic,
  stdlib-only). All offer/gate authority paths (`_judge_summary` offered lens; `_validate_judge_assignment`
  owner↔emit lens + 404 role guard; GET `/v1/judges` role enumeration + per-role 404 guard) resolve to the
  **active workspace** pack consistently — no path still uses the process-global `LENS_BY_ROLE` as the
  offer/gate authority. Snapshot defense-in-depth (owner↔emit THEN snapshot) retained. No off-by-one (an
  unknown role 404s, not 500).
- **S-BS-153 W2:** roster-add is **idempotent** (append only if absent; `rostered:false` on repeat),
  **active-agent-only** (mutates only the named agent; the global JudgeConfig store is not conflated with
  the per-agent roster — two-store split confirmed at the persistence layer), **audited** (goes through
  `put_agent_endpoint` → `save_agent` with `AuditLog`, writing an agent-targeted edit/author `AuditRecord`),
  and **lens-edit-safe** (a re-edit is a no-op append, never a strip).
- **honest-Δ — non-vacuous in BOTH directions** by controlled revert: reverting W1 (resolver→boot-pack
  global) fails exactly `test_offer_tracks_active_workspace_not_the_boot_global`; disabling W2 fails exactly
  the 3 S-BS-153 roster tests; reverting the JudgeEditor agent-pass fails exactly the new JudgeEditor test;
  reverting `bff.js` fails the "with agent" client test. No test asserts a constant or stubs the thing under
  test. Network-free (FastAPI TestClient + tmp SQLite + monkeypatched `get_active_workspace`; shell stubs
  fetch / vi.mocks bff.js). Runnable in `debuglithrim`.
- **Suites green on cleared bytecode** (monitor re-ran): BFF `tests/test_shepherd1c_judge.py` 10/10; shell
  `journey + JudgeEditor + bff` .test.jsx 29/29.

## Non-blocking (carried as seams / notes — none block close)

- **S-BS-155 (low, NEW follow-on)** — W1 scope: the DELETE-judge guard (`app.py:1104`), optimize guard
  (`:1136`), and `_assemble_agent` add_judge guard (`:1757`) still read the **process-global**
  `LENS_BY_ROLE`, not `_active_lens_by_role()`. **Correct today** (healthcare `production_judges` == the
  `_core` trio — same role NAMES; those guards do role-membership, not code-membership). A future Pro pack
  with a **different role set** would 404 a valid active-pack role at those three endpoints. Executor
  disclosed this transparently; deliberately out of the driver's 3-touch-point W1 scope. Clean follow-on:
  fold them onto `_active_lens_by_role` for full consistency.
- **S-BS-156 (low/med, PRE-EXISTING, NEW)** — `tests/test_flag_crud.py::{test_delete_guard_404_unknown,
  test_delete_guard_refuses_gradeable_in_snapshot}` fail at HEAD `132f24c` **independent of this change**
  (`PackConsistencyError`: the discovered external healthcare pack declares taxonomy codes the frozen
  council's `KNOWN_TAXONOMY_CODES` does not carry — a council↔pack snapshot drift in this local env). Verified
  by stashing all SHEPHERD-1c changes (fails identically). Out of scope; flag for separate triage (likely a
  `scripts/snapshot_taxonomy.py` re-snapshot of the external pack, not a code fix).
- **Partial-vacuity (acceptable):** 5 healthcare-direction BFF tests pass even with W1 reverted because
  `tests/conftest.py` pins `LITHRIM_BENCH_PACK=healthcare` (boot global already == healthcare lens). The
  load-bearing W1 guard is the single `test_offer_tracks_active_workspace_not_the_boot_global` (active
  workspace flipped to `_core`). Could be strengthened by parametrizing the boot pack.
- **W2 atomicity note:** the roster-add is a read-modify-write (get_agent → mutate → put_agent) with no
  transaction spanning judge-save + roster-add. Benign for the single-actor BFF; matches the existing
  `_assemble_agent` pattern exactly.

## PROCESS HAZARD (recorded — affected verification, not the deliverable)

The review fan-out ran on the **shared real working tree**, and two critics performed in-place revert
experiments to prove non-vacuity, causing spurious mid-run failures on the same tree; a concurrent .devloop
session also left foreign `.devloop/{README,personas/*,templates/*,modules/}` changes in the tree. The
critics restored the deliverable (0 residual `REVERT-EXPERIMENT` markers). **Monitor independently
re-verified before commit:** frozen set 0-diff, no revert markers, delivered W1/W2 logic present
(`_active_lens_by_role` returns `pack_lenses(get_active_workspace().pack)`; W2 guard = `if agent:`), cleared
bytecode, re-ran both suites green, and committed **pathspec-only** (8 files; the foreign `.devloop/*`
changes were NOT swept in — `git show --stat a003863` lists only the 8). Lesson: future review fan-outs that
need reverts should use isolated worktrees, not the shared tree.
