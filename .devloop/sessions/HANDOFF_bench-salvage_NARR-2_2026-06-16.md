# HANDOFF — bench-salvage — NARR-2 closed → NARR-3 (2026-06-16)

> **For the next session.** The **narrative-eval wedge** ("eval anything" CE) ingestion half is built.
> NARR-2 (the JUTE extractor + the `ingest_cases` chat tool) is **closed PROCEED-WITH-CAVEATS** (HARD GATE,
> fresh cold critic + monitor audit CLEAN). Next is **NARR-3** (the deterministic floor executors).
> **Resume:** `/devloop-resume bench-salvage`, then read `docs/specs/SPEC_NARRATIVE_EVAL.md` + this doc.

---

## What just landed (NARR-2 — the JUTE extractor + the 17th SDK-MCP tool)

| Commit | What |
|---|---|
| `c88f733` | the NARR-2 driver + index registration |
| `e3ef8aa` | **test-RED** — `tests/verification/test_jute_extractor.py` + `tests/bff/test_ingest_cases_tool.py` + the StoryWorld fixture (genuinely RED: extractor module/exports absent → import error on collection) |
| `e4f9f68` | **`lithrim_bench/verification/jute_extractor.py`** — DSPy extractor (parallels `jute_dspy.py`) + the zero-null/`count==expected` structural invariant |
| `861b373` | **`ingest_cases`** (the 17th tool) — `apps/bff/agent/tools.py:545` handler + the bound `_ingest_cases` `app.py:1887` |
| `2f6732f` | the 16→17 `_TOOL_SPECS` count-invariant consequence-edits (5 existing A-SAFE-sweep tests) |
| `e96efba` | the NARR-2 session log |

**The proof:** an extraction that mis-joins returns `null` → the structural invariant scores it **0** and the
ingest tool pins **nothing**; a clean §4.2 template yields **5 admissible narrative cases** (`expected_safety_flags
⊆ the narrative tier union`, `injection_recipe is None`, the content-filtered scene survives). The `ingest_cases`
chat tool: drop JSON → generate `jute_transform` → live-gate `:3031` → present → on accept PIN (`persist_or_update`)
+ audited corpus write. **$0/offline default** (the live-convergence test A6 is `skipif LITHRIM_NARR_LIVE`).

**HARD-GATE verdict: PROCEED-WITH-CAVEATS.** All 4 probes non-vacuously PASS (the critic monkeypatched
`_CONTRACT_EXECUTORS` to confirm the A4 separation assertion actually bites; drove `score_extraction` to confirm
A1 rejects a mis-join). **MOAT byte-frozen** (`compliance_council`/`signals`/`judge_metric` + `_deny_non_lithrim`
at `loop.py:213` = 0 diff). Gate 0: **0 new failures, 0 ruff delta** (canonical env
`LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare PYENV_VERSION=debuglithrim`). Critique:
`.devloop/sessions/critique-bench-salvage-phaseNARR-2-2026-06-16.md`.

## Load-bearing corrections this cycle baked in (the driver's anchors drifted; the executor used the REAL lines)
1. The grade-time floor registry is **`_CONTRACT_EXECUTORS` in `lithrim_bench/harness/grounding.py:295`** (+ `_core_floor_executors()` + the pack merge), NOT the driver's guessed `_FLOOR_CONTRACT_TYPES`/`verification/grounding.py`. **NARR-3 attaches the floor executors HERE.**
2. The A-SAFE deny hook `_deny_non_lithrim` lives at **`apps/bff/agent/loop.py:213`**, not `tools.py`.
3. The bound-fn construction `_build_tool_context` is `app.py:1611`; the new `_ingest_cases` is bound at `app.py:1887` (right after `_put_grounding_contract` at `app.py:1842`); `ToolContext` is `app.py:2029`.

---

## What's next — NARR-3 (the deterministic floor executors + ATTACH-VALIDATORS)

Per `SPEC_NARRATIVE_EVAL` §4.3 (`floor`-layer codes) + §8 cycle 3 + `SPEC_GROUNDING_TOOL_LAYER.md`. **This is where
the narrative grading gets its anti-circularity floor** — the machine-checkable codes from the enhancement prompt's
own shipped contract:
- **`SILENT_DEGRADATION`** (provenance) — `finish_reason != stop` yet the run reported `completed` / silently fell
  back to `source: baseline`. **The day-one proof point** (the user's real session: 1 of 5 gpt-5 calls hit
  `content_filter`, fell back to baseline, the PDF looked finished). The fixture `storyworld_session.json` already
  carries the content-filtered scene — NARR-3 makes the floor catch it deterministically.
- **`BRACKET_LEAK`** (det.) — the output contains `[…]` (the authoring marker leaked).
- **`LENGTH_VIOLATION`** (det.) — not 3–4 sentences.
- (then `POV_VIOLATION` / `LANGUAGE_DRIFT` / `CLICHE_OVERUSE` / `REPETITION` as the lens widens.)

**Build:** the floor executors as `_CONTRACT_EXECUTORS` entries (`harness/grounding.py:295` — the REAL registry,
corrected above) + the ATTACH hook so a narrative flag's `verification_contract` runs them at grade time. Mirror the
existing executors (`presence_check`, `kb_grounding`, `structural_jute`, `jute_gen`) + `_core_floor_executors()`.
**Trust-model boundary (carried from NARR-2):** these floor executors CAN flip a verdict (that's the point — they're
the floor); the **NARR-2 `jute_transform` extractor stays OUT of this registry** (ingestion ≠ grounding).

**Likely HARD-GATE** (it touches the grade-time floor + the withstands-gate path — the moat-adjacent plane). The
floor executors are deterministic, so tests are crisp (pass/violation pairs on crafted scenes).

## Open seams (NARR-2, all NON-BLOCKING — candidates for NARR-3/NARR-4 or a quick follow-on)
- **`S-BS-NARR2-1`** (medium) — the **D-C split**: ingested cases are pinned + audited + written to
  `ws.out_dir/ingested_cases.jsonl` (`app.py:1964`) but **nothing reads that file** — `load_case` resolves via the
  agent dataset/source (`app.py:540`), so the cases are not yet gradeable through the picklist. This is the
  NARR-2→NARR-4 bridge. The P0 exit ("present + PIN + emit + audit") is met; do NOT overclaim "gradeable end-to-end."
- **`S-BS-NARR2-2`** (low) — the bound `_ingest_cases` mis-join→no-pin ORDERING is code-read + handler-unit verified
  but lacks an automated test driving the REAL bound fn with a mock `EtlpJuteClient` (assert `persist_or_update` /
  `AuditLog.record` call-count == 0 on a short/null apply). A 10-min test; do it in NARR-3 or as a hygiene follow-on.
- **`S-BS-NARR2-3`** (low) — `bridge→scene` offset is a no-op stub (P1; the reader's Bridge-A Q&A → the Ranger scene
  lookup feeds `PERSONALIZATION_MISS` later).
- **Pre-existing OBSERVATION** (not this cycle) — the suite is order-non-deterministic via openai-import pollution
  (~5 unrelated tests flip between runs); always run Gate 0 with the canonical env. A future conftest
  import-isolation hygiene cycle would settle it.

## Standing prefs (unchanged)
No autostart (`:3031` is up — `curl /mappings`, never start it) · no push without owner approval (branch
`bench-salvage/ws6c-dspy`, **NOT pushed**) · pathspec-only atomic commits · tests-first (RED before code) ·
`PYENV_VERSION=debuglithrim` for council/dspy deps + `LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare` for the
full green bar · diagnose-before-edit · honest-Δ / BYO-key $0 first · MOAT byte-frozen (guard-trio tripwire).

## First move (next session)
1. Read this doc + `docs/specs/SPEC_NARRATIVE_EVAL.md` (§4.3 + §5 + §8 NARR-3) + `docs/specs/SPEC_GROUNDING_TOOL_LAYER.md`.
2. Read the REAL floor registry: `lithrim_bench/harness/grounding.py:295` (`_CONTRACT_EXECUTORS` + `_core_floor_executors`) and an existing executor to mirror.
3. `/devloop-expand-driver bench-salvage NARR-3` (author the driver from the spec; re-grep every anchor — the §12 anchors drifted once already).
4. Optionally first close S-BS-NARR2-2 (the 10-min mis-join no-pin test) to harden NARR-2's error path.
