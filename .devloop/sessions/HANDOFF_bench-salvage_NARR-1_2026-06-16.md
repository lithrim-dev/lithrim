# HANDOFF — bench-salvage — NARR-1 closed → NARR-2 (2026-06-16)

> **For the next session.** The **narrative-eval wedge** ("eval anything" CE) is underway.
> NARR-1 (the `narrative` domain pack) is **closed**. Next is **NARR-2** (the JUTE per-scene
> extractor + the chat ingest tool). **Resume:** `/devloop-resume bench-salvage`, then read
> `docs/specs/SPEC_NARRATIVE_EVAL.md` + this doc.

---

## What just landed (NARR-1 — the narrative pack, data-only)

| Commit | What |
|---|---|
| `df64f2f` | `SPEC_NARRATIVE_EVAL.md` — the wedge spec (+ the narrative-eval handoff; XFORM-1 retired) |
| `935a36c` | the NARR-1 driver + index registration |
| `08cc25c` | **`packs/narrative/`** — pack.json + taxonomy_snapshot.json + ontology.json + 3 council_roles + a clean-negative StoryWorld fixture |
| `c1e5997` | **`tests/test_narrative_pack.py`** — snapshot-consistency lint + standalone-grade |

**The proof (all $0/offline, `debuglithrim`):** a real StoryWorld scene grades to a verdict under
`LITHRIM_BENCH_PACK=narrative` with the healthcare pack UNLOADED and `:8002` DOWN — clean→`approve`,
`BRACKET_LEAK`→`reject` (the move is the AUTHORING) — with **0 `packs/healthcare/` reads** and the
narrative judge prompts carrying **0 clinical needles**. Acceptance A1–A6 GREEN; the consistency
gate is **non-vacuous** (3 malformed-snapshot perturbations each caught); pack-neighbor regression
59p/30-skip; ruff clean. **DATA-ONLY** — `git diff` = `packs/narrative/**` + `tests/**`, zero
engine/BFF/shell.

**Two corrections this cycle baked in (honesty):**
1. The grounding run `wf_8715f73a-0ec` **refuted the "clinical-taxonomy wall"** that the prior
   narrative-eval handoff (B5) + memory `conversational-first-core-plugin-line` implied: admissibility
   is **pack-bound** (`harness/admissibility.py:43-57`), not clinical-locked. `support_ticket_qa` is the
   non-clinical precedent. So a narrative pack grades today with zero engine edits.
2. A workspace/pack-surface fan-out found the **workspace/pack-selection UI already exists** (the shell
   `WorkspaceSwitcher` pack dropdown `app.jsx:82-89` ← `GET /v1/packs` `app.py:775` ← `POST
   /v1/workspaces {pack}` `app.py:760`; grade binds `LITHRIM_BENCH_PACK=ws.pack` `app.py:353`). So the
   spec's "+ UI hook" was already built → NARR-1 shrank to pure pack data.

## The narrative taxonomy (the contract-of-record — `packs/narrative/taxonomy_snapshot.json`)
11 codes; `production_judges` = the core deployable trio (PACK-2c — no new deployable judge):
- **TIER_1**: `BRACKET_LEAK` (→policy), `SILENT_DEGRADATION` (→risk).
- **TIER_2**: `BODY_CONTRADICTION`, `LENGTH_VIOLATION`, `POV_VIOLATION`, `LANGUAGE_DRIFT`, `MODE_INAPPROPRIATE`, `TONE_INFIDELITY`.
- **TIER_3**: `CLICHE_OVERUSE`, `REPETITION`, `PERSONALIZATION_MISS`.
The floor-layer codes ship as gradeable **judge** flags; their **deterministic executors are NARR-3**.

---

## What's next — NARR-2 (the JUTE extractor + the chat ingest tool)

Per `SPEC_NARRATIVE_EVAL` §8 cycle 2 + §12 (the rebuild list). **The retired XFORM-1 folds in here.**
Build:
1. A **`JuteExtractor`** (DSPy signature + an EXTRACTION metric) reusing the `jute_dspy` loop
   (`lithrim_bench/verification/jute_dspy.py`: `score_template`:130, `make_bench_metric`:200,
   `render_dsl_excerpt`:279 [the runtime-notes/builtin gap], `build_generator`:333, `best_of_n`:421) +
   `EtlpJuteClient` (`etlp_client.py:48-164`: `test_template`, `apply_mapping`, `persist_or_update`).
   New: `JuteExtractorSignature` (`extraction_rules`, `sample_input`, `prior_template`, `prior_feedback`
   → `jute_transform`); an extraction metric with a **hard structural output-invariant**
   (zero-null / `count==expected` — a mis-join returns `null`, not an error); `JuteExtractorTool`.
2. The **`ingest_cases`** SDK-MCP tool (the 17th; `apps/bff/app.py` `_build_tool_context`:1595-1910,
   `_TOOL_SPECS`:603-744): drop JSON → generate `jute_transform` → live-gate on `:3031` → present
   the extracted cases → on accept, pin (`persist_or_update`) + upsert the workspace corpus
   (cases load via `picklist.load_case`; no ingest tool exists yet — `app.py:109,539-541`).
   **A-SAFE checklist applies** (deny-default; the FieldInfo trap if wrapping an endpoint — memory
   `fastapi-endpoint-as-plain-call-fieldinfo-trap`).
3. The **reference template is the proven per-scene normalizer** (`SPEC_NARRATIVE_EVAL` §4.2,
   committed verbatim) — the loop should regenerate it (does `jute_dspy` converge on a transformer?),
   live-gate, pin. `:3031` is up (no autostart; curl first).

**Hardness for NARR-2:** likely HARD-GATE (it touches the verification plane + adds a chat tool with a
live-service dependency; the extractor must NOT wire into any grade-time floor — trust-model separation).

## Open seams / notes
- **NARR-1 snapshot is the contract** — if the SME (user) wants codes moved/renamed/re-tiered, it's a
  cheap pack-data edit (`packs/narrative/taxonomy_snapshot.json` + `ontology.json` + the consistency test).
- The `bridge→scene` offset (Bridge-A Q&A → the Ranger scene) lives in the importer (NARR-2 decision).
- Memory to update opportunistically: `conversational-first-core-plugin-line` still says nothing wrong
  (it already affirms domain-agnosticism), but a `narrative-eval-wedge` project memory would help future
  resumes (MEMORY.md is over its size budget — keep any new index line short).
- Standing prefs unchanged: no autostart · no push without owner approval (branch `bench-salvage/ws6c-dspy`,
  NOT pushed) · pathspec-only · honest-Δ · BYO-key/$0 first.

## First move (next session)
1. Read this doc + `docs/specs/SPEC_NARRATIVE_EVAL.md` (§8 NARR-2 + §12 rebuild list).
2. `/devloop-expand-driver bench-salvage NARR-2` (author the NARR-2 driver from the spec).
3. Confirm `:3031` is live (`curl`) before any extractor live-gate; keep the extractor off the grade-time floor.
