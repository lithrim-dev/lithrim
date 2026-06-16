# Critique — bench-salvage phase NARR-2 (HARD GATE, fresh cold critic)

**Cycle:** the JUTE per-scene extractor + the `ingest_cases` chat tool (the "eval anything" ingestion half).
**Commits:** `c88f733..e96efba` (5 commits; driver `c88f733`, then `e3ef8aa` test-red → `e4f9f68` feat extractor → `861b373` feat tool → `2f6732f` 16→17 count invariant → `e96efba` session log).
**Critic:** fresh cold session (no implementation context), `devloop-critic` subagent, 2026-06-16.
**Driver:** `.devloop/prompts/bench-salvage_phaseNARR-2_jute-extractor-ingest-tool_driver.md`

---

## VERDICT: PROCEED-WITH-CAVEATS

Faithful cycle; all four HARD-GATE invariants non-vacuously proven; MOAT byte-frozen; scope held; **Gate 0 introduces 0 new failures + 0 ruff delta**. The "caveats" are two honestly-declared seams (the D-C gradeable-corpus split + a live-only end-to-end path), both pre-disclosed by the executor and confirmed accurate. **No BLOCKING findings.**

## Gate 0 (supreme deterministic gate)

`LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare PYENV_VERSION=debuglithrim pytest -q`

| | HEAD `e96efba` | Base `cfe4b6d` | Delta |
|---|---|---|---|
| failed | 13 | 18 | **0 new** (HEAD ⊆ base; `comm -23 head base` empty) |
| passed | 568 | 549 | +19 |
| skipped | 5 | 7 | — |
| ruff | 398 (exit 0) | 398 (exit 0) | **0** |

- **Zero new failures.** All 13 HEAD failures are present at base and fail in isolation (`test_pack_dist`, `test_pack_layer1a`, `test_uap3b*`, `test_ws4a`, `runtime/council`, `runtime/observation` — subsystems this cycle never touched). The 5 base-only failures are openai-import order-pollution artifacts, not real fixes.
- **tests_first: YES** — RED commit `e3ef8aa` adds only tests+fixture; the extractor module/exports are absent → import-RED on collection. Test commit precedes both impl commits.
- New NARR-2 files in isolation: 11 passed / 1 skipped-live; ruff clean.

## The 4 HARD-GATE probes (all PASS, empirically non-vacuous)

1. **A4 trust-model separation — PASS.** Real registry is `lithrim_bench/harness/grounding.py:295` `_CONTRACT_EXECUTORS` (+ `_core_floor_executors()` + pack merge) — NOT the driver's guessed `_FLOOR_CONTRACT_TYPES`/`verification/grounding.py`; the executor's correction is right. The extractor exports a generator, not a `VerificationTool`, and is absent from all 4 grade-time registries. Non-vacuity proven empirically: monkeypatching `_CONTRACT_EXECUTORS["jute_transform"]=object` fires the A4 assertion. The §12 `JuteExtractorTool`/`spec.py` entry was correctly NOT built (plan-review D-B).
2. **MOAT 0-diff — PASS.** `git diff cfe4b6d --` over `compliance_council.py`/`signals.py`/`judge_metric.py` empty; the A-SAFE deny hook `_deny_non_lithrim` lives at `apps/bff/agent/loop.py:213` (driver said tools.py — executor's correction right) and `loop.py` diff is empty. Seam-guard tests pass.
3. **A1 structural invariant is real — PASS.** `score_extraction` (`jute_extractor.py:103`) returns `accepted=False, graded=0.0, cases=[]` on a mis-join / short array / non-compile; `accepted=True, graded=1.0, 5 cases` on a clean extraction. Driven directly: `MISJOIN: accepted=False nulls=5 graded=0.0 cases=0`. Asserts each branch (not `assert True`); RED was genuine.
4. **Error paths pin NOTHING — PASS.** The bound `_ingest_cases` (`app.py:1887`) raises on JSON-parse-fail / non-convergence / apply-time invariant-fail **strictly before** `persist_or_update` (PIN) / corpus-write / `AuditLog.record`. The handler (`tools.py:545`) surfaces a structured error, emits no corpus part. `test_ingest_pins_nothing_on_invariant_fail` asserts `is_error` + "nothing pinned" + `ctx.parts == []`.

## The 4 spec-fidelity questions

1. **Surface fidelity — MATCH.** `JuteExtractorSignature`, `score_extraction(... *, expected_count)`, `extraction_feedback_from`, `make_extraction_metric`, `build_extractor_generator`, `best_of_n_extractor`, `INGEST_CASES_SCHEMA`, `ToolContext.ingest_cases`, the 17th `_TOOL_SPECS` entry — all per driver §2. The `JuteExtractorTool`/`spec.py` omission is the one authorized omission (D-B; A4 even asserts its absence).
2. **Behavioral fidelity (tests assert SPEC) — YES.** A1↔§4.2 mis-join, A2↔§4.1 envelope + §4.3 admissibility (asserts `expected_safety_flags ⊆ narrative tier union` from the real snapshot, `injection_recipe is None`, content-filtered scene survives), A3-neg↔§6 "nothing pinned on failure". A5 sweep got stricter (non-vacuous over all 17). No test bent to mirror code.
3. **Out-of-scope intrusion — NONE.** Production code touches only the 4 §2 files. The 5 "extra" test files are mandatory 16→17 consequence edits (count invariants + `ToolContext(... ingest_cases=_noop)` stubs), isolated in `2f6732f`. No shell JSX, no `packs/healthcare/`, no `packs/narrative/` snapshot/ontology edit, no re-snapshot.
4. **Honesty gaps — NONE.** No manufactured win, no vacuous test (A1/A4 proven to bite). Limitations declared as seams. Live A6 honestly `skipif`-guarded, reported as diagnostic, not claimed passed.

## Findings

1. **OBSERVATION** — the suite is order-non-deterministic (openai-import pollution flips ~5 unrelated tests between runs). Pre-existing, environmental. Future hygiene cycle (a conftest import-isolation guard), not a blocker.
2. **NON-BLOCKING** — the bound `_ingest_cases` gating-order (pin/upsert/audit strictly after acceptance) is verified by code-read + the handler-level A3-neg test, but **no automated test drives the real `_ingest_cases` with a mock client returning a mis-join to assert `persist_or_update` was NOT called**. = the executor's declared seam **S-BS-NARR2-2**. Proposed coverage: inject a fake `EtlpJuteClient` whose `test_template` returns a short/null array, assert `RuntimeError` + `persist_or_update`/`AuditLog.record` call-count == 0. Logic correct on read; coverage gap, not a defect.
3. **OBSERVATION** — the ingested corpus is written to `ws.out_dir / "ingested_cases.jsonl"` (`app.py:1964`), which **nothing reads** (`load_case` resolves via the agent dataset/source, `app.py:540`). Cases are pinned + audited + on-disk but **not yet gradeable through the picklist** = declared seam **S-BS-NARR2-1** (D-C split). The §6 P0 exit ("present + PIN + emit + audit") is genuinely met; "gradeable end-to-end" correctly NOT claimed.

## Caveat confirmations

- **"13 failures all pre-existing"** — CONFIRMED (`comm` HEAD vs base: zero HEAD-only; all 13 at base, fail in isolation).
- **3 driver citation drifts** — ALL CONFIRMED ACCURATE + correctly applied: deny hook `loop.py:213` (byte-frozen); `_put_grounding_contract` `app.py:1842` with `_ingest_cases` bound at `app.py:1887` inside `_build_tool_context` (`app.py:1611`) → `ToolContext` `app.py:2029`; registry `_CONTRACT_EXECUTORS` `harness/grounding.py:295`. Drift caught, not propagated. No FieldInfo trap (bound fn calls `EtlpJuteClient`/`workspace`/`AuditLog` directly).
- **Seam S-BS-NARR2-1 (D-C split)** — HONEST (declared in the session log + code comments `app.py:1960-1961`). P0 exit met; gradeable picklist registration correctly deferred to the NARR-2→NARR-4 bridge.

---

*This file was authored by the monitor from the cold critic's structured return (the critic subagent has no Write tool by design). Verdict and evidence are the critic's; the monitor filed it verbatim-in-substance.*
