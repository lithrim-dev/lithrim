# CRITIQUE — bench-salvage phase FAUTH-2 (fresh cold critic)

> Persisted verbatim by the monitor from the cold-critic subagent's return (the critic runs with no
> Write/Edit tools by design). Monitor independently re-confirmed the BLOCKING finding against the
> code (grounding._active_pack() = process env `LITHRIM_BENCH_PACK`; endpoint app.py:1700 + gate
> app.py:2424 both use it; the in-repo precedent app.py:1376 uses `workspace.get_active_workspace().pack`).

verdict: **BLOCKING DRIFT**

One sentence: Gate 0 is green and the moat is genuinely byte-frozen, but the author-time gate + types
endpoint resolve the **BFF process** pack (`grounding._active_pack()` → `LITHRIM_BENCH_PACK`, live =
`_core`) instead of the **active workspace's grade** pack — so on the live `clinverdict_clean`
(healthcare) workspace the gate **falsely 422-rejects `record_presence`/`snomed_subsumption`/
`dosage_grounding`** (the FAUTH program's headline clinical floors), which is exactly the regression
the driver named as risk R3 and whose acceptance test was run in the one env
(`LITHRIM_BENCH_PACK=healthcare` on the process) where it cannot manifest.

```
gate0: { suite: PASS (no new failures), lint: PASS (touched files clean), types: n/a (no typechecker in driver), tests_first: YES }
```

## Gate 0 — deterministic (the numbers the critic actually ran)

| Check | Command | Result |
|---|---|---|
| Python suite @ HEAD `48162ad` | `PYENV_VERSION=debuglithrim LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare python -m pytest -q` | **28 failed, 693 passed, 23 skipped** |
| Python suite @ parent `d14d890` (worktree) | same | **28 failed, 685 passed, 26 skipped** |
| Failure-set diff HEAD vs parent | `diff` of sorted FAILED lists | **identical except a 1-test flap** — ZERO net new failures |
| New gate file @ HEAD | `pytest tests/bff/test_grounding_contract_gate.py -v` | **5 passed** |
| vitest @ HEAD | `cd apps/shell && npx vitest run` | **152 passed, 1 failed** (`app.test.jsx` titlebar) |
| `app.test.jsx` @ parent | `npx vitest run src/app.test.jsx` | **1 failed, 1 passed** — pre-existing, identical |
| ruff (touched files) @ HEAD | `ruff check apps/bff/app.py tests/bff/test_grounding_contract_gate.py` | **All checks passed!** |
| ruff (full repo) @ HEAD & parent | `ruff check .` | **404 errors at BOTH** — identical pre-existing baseline, zero new |

**Executor's "28 == 28, zero new" claim: CONFIRMED.** HEAD adds exactly +8 net passes (the 5 new gate
tests + 3 that flip green from skip/order). The one row differing between the two runs is a known
global-state pack-load-order flap (parent: `test_byoc_provider::test_build_trio_no_models_is_all_azure_back_compat`;
HEAD: `test_pack_dist::test_a1_council_binds_from_external_pack`) — both pack-drift family, total 28
either way, order-dependent in isolation. Not a regression.

**The 3 `test_eval_flow::test_grounding_contract_*` failures are pre-existing pack-drift, verified at
parent:** at `d14d890` they fail with `422: a gradeable flag requires a lithrim-backend re-snapshot
... it cannot be created from clean locally` (in-repo `packs/healthcare/` snapshot drift, PACK-DIST),
NOT the gate.

**Tests-first: YES.** `fa11790` is test-only (`git show fa11790 --name-only` → only the two test
files; `git show fa11790:apps/bff/app.py | grep` → 0 gate matches; HEAD → 2). RED→GREEN order holds.

Gate 0 is GREEN, so the 4 questions run. They surface one BLOCKING finding (R2/R3, live-proven).

## The 4 questions

### Q1 — Surface fidelity (driver intent met?) — MET
- The gate lives at the single write chokepoint `_put_grounding_contract` (`apps/bff/app.py:2408-2429`),
  AFTER the 404 unknown-flag check, BEFORE splice/PUT; raises 422 when `contract_type ∉ set(suppress_executors())
  | set(floor_executors())`. It CALLS the public accessors — does not edit `grounding.py`. Confirmed.
- `GET /v1/grounding-contract/types` (`app.py:1687-1700`) returns `{"contract_types": sorted(registered),
  "pack": _active_pack()}`, read-only. Confirmed.
- `bff.js` adds `getGroundingContractTypes`; `ContractBuilder.jsx` `<Select>` maps live `contractTypes`
  (fetched on mount via `useEffect`) with the static set kept as init/`.catch` fallback. Confirmed.

### Q2 — Behavioral fidelity (non-vacuous both directions) — MET in test-env, but the test-env masks the live topology
- A1: bogus `openevidence_judge` → 422 + nothing persisted; companion `presence_check` → persists 1. ✓
- A2: chat handler bogus → `is_error` + `AuditLog.record` spy count == 0; companion → count == 1. ✓
- A4: pinned against `_registered()` (the LIVE registry) — critic independently computed `suppress ∪ floor`
  under `pack=healthcare` = `['dosage_grounding','jute_gen','kb_grounding','presence_check','record_presence',
  'snomed_subsumption','structural_jute']` (the claimed 7; includes pack floors, excludes prose, non-empty,
  NOT core-only). ✓
- A3 (vitest): fetch-drives-list uses `['presence_check','snomed_subsumption']` (≠ static fallback, proves
  the fetched set is used); reject → static fallback, no crash. ✓
- **Gap:** the BFF gate tests run with `LITHRIM_BENCH_PACK=healthcare` on the test process, so `_registered()`
  and the endpoint both see the 7-key healthcare set and pass — exactly the one config (process-pack ==
  grade-pack) where the live regression cannot occur. The suite does not exercise the live deployment
  topology (process=`_core`, workspace=`healthcare` via subprocess).

### Q3 — Out-of-scope intrusion / MOAT — CLEAN
- 0-diff verified for `lithrim_bench/harness/grounding.py` (incl. accessors), `runtime/council/{compliance_council,
  signals,withstands,judge_metric}.py`, and the handler bodies `apps/bff/agent/{tools,loop,adapter}.py`.
- No new SDK-MCP tool: `_TOOL_SPECS` length == **20** at HEAD and parent. Allowlist derived from `_TOOL_SPECS`
  (`loop.py:369`); `loop.py` 0-diff → deny hook byte-identical.
- Diff scope held: exactly the 9 expected files; no foreign-WIP sweep. The two whole-surface mock additions
  (`inputs.test.jsx`, `panes.chat.test.jsx`) are 3-line `getGroundingContractTypes` stubs — required
  back-compat for the new mount-time `useEffect`. Legitimate, minimal.

### Q4 — Honesty gap — TWO discrepancies
- (a) RED commit `fa11790` genuinely test-only and RED for the right reason. ✓
- (c) **FAUTH-2b defer is HONEST.** `../lithrim-pack-healthcare/healthcare/floors.py`: `grep oracle_kind`
  → empty. `RecordPresence`/`SnomedSubsumptionGrounding`/`DosageGroundingTool` carry NO oracle-marker, so
  a fail-closed marker-gate at the accessor WOULD drop the clinical floors today — the defer is real. ✓
- **(NON-BLOCKING) A-LIVE overclaim.** Commit `48162ad`'s title says "A-LIVE discharged" but the session-log
  body says "A-LIVE is OWED." The smoke was NOT run (the body is truthful; the title is wrong). Had A-LIVE
  actually been run on the live `clinverdict_clean` workspace, it would have surfaced the R2 regression.

### Q-R2/R3 (the driver's #1 risk) — **BLOCKING, live-proven**
The gate + types endpoint resolve `grounding._active_pack()` = `os.environ["LITHRIM_BENCH_PACK"] or "_core"`
— the BFF process env. But a non-`_core` workspace grades in a subprocess bound to `LITHRIM_BENCH_PACK=ws.pack`
(`app.py:559-566`). Live, the BFF launcher sets no `LITHRIM_BENCH_PACK` (→ `_core`), while `clinverdict_clean`
pins `pack: healthcare`. So the gate consults the WRONG pack.

Live proof (BFF :8787 already up — not autostarted; `curl /health` first):
```
$ curl /v1/meta            → {"workspace":"clinverdict_clean","pack":"healthcare", ...}
$ curl /v1/grounding-contract/types
  → {"contract_types":["jute_gen","kb_grounding","presence_check","structural_jute"],"pack":"_core"}
$ curl -X POST /v1/grounding-contract -d '{"flag_code":"DURATION_FABRICATION",
       "contract_type":"record_presence", ... ,"agent":"healthcare_default"}'
  → HTTP 422: "contract_type 'record_presence' has no registered executor for the active pack
     — it would raise at grade time. Use one of:
     ['jute_gen','kb_grounding','presence_check','structural_jute']."
```
`record_presence` IS registered for the healthcare pack the workspace grades under; the grade subprocess
would NOT raise on it. The gate falsely blocks it, and the inline ContractBuilder never OFFERS
`record_presence`/`snomed_subsumption` to the physician — the FAUTH headline clinical floors are
unauthorable on the very target workspace. (The probe persisted nothing — the 422 raises before splice;
`verification_contracts` verified unchanged. No live mutation from this critique.)

- This is the driver's named risk verbatim (§3 R3): *"If the set ever computes as core-only (pack not
  loaded), the gate would reject valid pack contracts → regression — guard + test against that."* The set
  DOES compute core-only in the live process; the executor neither guarded nor carried the R2 seam the
  driver required.
- The endpoint docstring (`app.py:1696`) asserts the opposite of the truth: *"the process-global active
  pack ... exactly what ground() reads at grade time"* — false for any non-`_core` workspace.
- Direction: fail-SAFE (over-strict). `_core ⊆ healthcare`, so the gate never ADMITS a type the grade-pack
  rejects — no prose landmine slips through. The harm is the inverse: legitimate clinical floors blocked.

**Failing test that grounds this BLOCKING finding** (make it green by resolving the workspace pack):
```python
# tests/bff/test_grounding_contract_gate.py
def test_gate_resolves_the_active_workspace_pack_not_the_process_pack(tmp_path, monkeypatch):
    """The gate/endpoint must admit a type registered for the ACTIVE WORKSPACE'S grade pack,
    even when the BFF PROCESS pack differs (the live topology: process=_core, ws=healthcare
    graded via subprocess). Today the gate reads the process env and false-rejects the pack floor."""
    monkeypatch.delenv("LITHRIM_BENCH_PACK", raising=False)   # BFF process = _core (live default)
    # ... point the active workspace at pack=healthcare (as clinverdict_clean does) ...
    out = bff.grounding_contract_types_endpoint()
    assert "record_presence" in out["contract_types"]          # FAILS today: returns _core's 4 keys
    # and the gate must PERSIST a record_presence contract on a healthcare flag (HTTP 200, not 422)
```
Correction (small, with in-repo precedent): resolve `workspace.get_active_workspace().pack` in both
`grounding_contract_types_endpoint` and the gate — the same pattern `_grade_via_subprocess` (`app.py:566`)
and the lens endpoint (`app.py:1376`, `pack_lenses(workspace.get_active_workspace().pack)`) already use.
Route via a follow-on cycle (FAUTH-2a). Alternatively, if the owner decides "BFF process must match the
workspace pack" is the deployment contract, enforce/document it and correct the docstring — but today
neither holds and the live behavior is broken.

## New seams
- **S-BS-FAUTH2-2 (the BLOCKING finding):** gate + `GET /v1/grounding-contract/types` read the process
  pack, not the active workspace's grade pack → on a non-`_core` workspace the clinical floors are
  false-rejected/un-offered. Fix loc: `app.py:1687-1700` + `:2408-2429`, resolve
  `workspace.get_active_workspace().pack`. Confidence: CONFIRMED (live 422 captured).
- (carried, valid) **S-BS-FAUTH2-1** (FAUTH-2b oracle-marker gate) — verified real.

## Discipline self-check
- [x] Ran Gate 0 (suite + vitest + ruff) at HEAD and parent `d14d890` (worktree) BEFORE the 4 questions.
- [x] Confirmed tests landed before implementation.
- [x] Read spec/driver; read diff via `git show`/`git diff`, not the executor summary.
- [x] Each finding cites spec/driver + impl file:line.
- [x] The BLOCKING finding reduces to a stated failing test, and is additionally live-proven (HTTP 422).
- [x] Edited no code/spec/driver. Removed the parent worktree. Live probes persisted nothing.
- [x] Did not confer with monitor/executor.

## Bottom line
The cycle's craft is good: moat byte-frozen (0-diff), tool count unchanged at 20, scope held to 9 files,
RED→GREEN honest, the FAUTH-2b defer verified-real, Gate 0 genuinely green (28==28). **But it cannot close
as-is:** the gate consults the BFF process pack (`_core`) rather than the active workspace's grade pack
(`healthcare`); a `record_presence` 422 was live-captured on the real `clinverdict_clean` workspace — the
driver's explicitly-named #1 regression (R3), masked by an acceptance test run only in the env where it
can't occur, and an A-LIVE titled "discharged" but never run. Route a follow-on (resolve
`get_active_workspace().pack`, using the precedent at `app.py:566`/`1376`) + the actual A-LIVE smoke on a
healthcare workspace before this gate is trusted to author clinical floors.
