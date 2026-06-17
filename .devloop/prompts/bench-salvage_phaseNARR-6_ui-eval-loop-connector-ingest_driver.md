# Driver — `bench-salvage` phase `NARR-6`: the UI-driven StoryWorld eval loop — connector + real-field batch ingest (P1a+P1b)

> **Authored by the monitor from a code-scan reassessment (run `wf_d493ca05-d40`, 4 readers + synthesis, confidence HIGH) + owner decisions (2026-06-17). Every load-bearing anchor re-grepped DIRECTLY afterward.**
>
> **Bundle ID:** `bench-salvage-phaseNARR-6-ui-eval-loop-connector-ingest-driver`
> **Version:** v1 · **Authored:** 2026-06-17 · **Re-verified:** 2026-06-17 (vs HEAD `65a3d68`)
> **Hardness:** **HARD GATE** (new BFF endpoints + a secret/PII path + a real-data extractor + a shell form; the MOAT is read-only — fresh-critic at close). **$0** — no paid council in this cycle.

---

## KICKOFF (paste into a fresh executor session)
```
You are the EXECUTOR for the .devloop/ cycle: bench-salvage phase NARR-6
(the UI-driven StoryWorld eval loop — connector config + real-field batch ingest; P1a+P1b; $0).

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseNARR-6_ui-eval-loop-connector-ingest_driver.md  (this doc)
  3. .devloop/sessions/HANDOFF_bench-salvage_NARR-5_2026-06-17.md
  4. docs/research/PROOF_narrative_live_council_2026-06-17.md  (the live-grade context)
  5. apps/bff/app.py:1887-2032  (_ingest_cases — the generate->:3031-gate->PIN->corpus-upsert->audit machinery to REUSE per session) + :2005-2013 (KbRagTool reads keys from env — the secret pattern) + :743-772 (workspace endpoints)
  6. lithrim_bench/verification/etlp_client.py:48-150  (EtlpJuteClient — clone for the StoryWorld HTTP client; base_url + key)
  7. lithrim_bench/verification/jute_extractor.py  (_to_envelope:63, score_extraction, best_of_n_extractor — the auto-generate path)
  8. lithrim_bench/harness/grade.py:22-38  (.live_env loader pattern — mirror for .connector_env) + lithrim_bench/picklist.py:101-145 (the D1 bridge: ingested cases are ALREADY gradeable by case_id)
  9. apps/shell/src/app.jsx:13-103  (WorkspaceSwitcher form pattern to mirror for the connector form) + apps/shell/src/bff.js (the BFF client)
 10. phi_redaction in core (grep: lithrim_bench/runtime/council/ + the observation agents — the kept-as-generic PII/PHI redaction to reuse at ingest)

Canonical env:
  LITHRIM_BENCH_PACK=narrative LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare PYENV_VERSION=debuglithrim
  Regression: LITHRIM_BENCH_PACK=healthcare ... ; UI: cd apps/shell && npx vitest run
Services are UP (curl /health; NEVER autostart). $0 cycle — do NOT grade the paid council.
The REAL StoryWorld API (owner-provided): base https://storyworld-api-uae.salmonocean-32935a91.uaenorth.azurecontainerapps.io ; header x-api-key ; list /api/admin/sessions?limit&offset -> {items,total} (841) ; detail /api/admin/sessions/<id>. The KEY is owner-supplied at runtime — NEVER hardcode/commit it.

Post your plan-review per EXECUTOR.md. Do not write code until I say "go".

Bundle ID: bench-salvage-phaseNARR-6-ui-eval-loop-connector-ingest-driver
```

---

## 0. Context + the owner decisions (read first)
The owner wants the "eval anything" loop **fully self-serve in the shell**: connect the StoryWorld admin API → pull a batch → ingest → ($0 floor) grade → see a corpus findings view. A $0 curl sweep already PROVED the deterministic floor finds **11 SILENT_DEGRADATION sessions in 841** (incl. **4 the app's own `enhancement_status: success` masked** — caught only by the `finish_reason: content_filter` join). This is the productization of that.

**This is split:** **NARR-6 = P1a+P1b** (connector config + real-field batch ingest — the visible connect+pull half). **NARR-7 = P1c+P1d** (the `grade_floor_only` $0 path + the corpus Findings view — the payoff). **Deferred:** P2a (the PAID council over the corpus, behind the CostModal), P2b (`kind:tool` declaration + agent-callable ingest), P3 (`kind:importer` generalization). *(This supersedes the earlier "NARR-6 = polished walkthrough/video" framing — the walkthrough/video + the NARR-5 seams fold into the eventual demo phase.)*

**OWNER DECISIONS (2026-06-17 — bake in, do not relitigate):**
1. **PII → REDACT AT INGEST.** Strip/redact `child_name` + `age` (reuse the kept-as-generic `phi_redaction` core mechanism) BEFORE anything is written to `ingested_cases.jsonl`. The eval-case keeps only `clean_text` + provenance — **no PII ever on disk**.
2. **Secret → `.connector_env` on disk.** Write the `x-api-key` to a gitignored `out/workspaces/<name>/.connector_env`, loaded like `.live_env` (grade.py:22). **Never** SQLite/manifest/git. Persist only `base_url`+`last_tested` to the workspace.
3. **Transform → AUTO-GENERATE (DSPy).** Use `best_of_n_extractor` to auto-generate the real-field `jute_transform`, live-gated on `:3031`, **then PIN it** (generate-at-authoring → live-gate → pin → deterministic apply; the existing `_ingest_cases` flow). Apply-time stays deterministic; the `:3031` apply-gate makes a mis-join fail CLEAN (null→reject, nothing pinned).

**The over-fire lesson (from the live real-session grade):** the council's `PERSONALIZATION_MISS` over-fires on thin context — so the council needs RICH reader-choice/emotion context in the transform. **NARR-6 is FLOOR-ONLY ($0); the floor does NOT depend on rich context** (it reads `enhancement_status`/`finish_reason`/`clean_text`), so this doesn't bite NARR-6. It is a hard **P2a requirement** (carry the rich context for when the paid council runs).

---

## 1. Deliverables (P1a + P1b; $0)

**P1a — the connector config (BFF + shell; small).**
- `POST /v1/connector/config` (NEW, `apps/bff/app.py`): body `{connector_id:"storyworld_admin", base_url, x_api_key}`. **Validate** with a read-only Test (GET `/api/admin/sessions?limit=1` with the key → surface a clean 200/401/404/timeout, NEVER fabricate). **Write the key** to `out/workspaces/<active>/.connector_env` (gitignored; mirror the grade.py:22 `.live_env` parser). **Persist** only `base_url`+`last_tested` to the workspace record. The key is read FROM `.connector_env`/env at ingest time, never returned.
- Shell connector form (`apps/shell/src/`, mirror the `WorkspaceSwitcher` form app.jsx:13-103 + a `bff.js` method): base URL + masked key + **Test connection** button. Hand-compact JSX, NO prettier.

**P1b — the real-field batch ingest (BFF + verification; medium).**
- A **StoryWorld HTTP client** (`lithrim_bench/verification/`, clone `EtlpJuteClient` etlp_client.py:48): `list_sessions(limit, offset)` + `get_session(id)`, base_url + key from `.connector_env`/env, injectable for tests.
- `POST /v1/connector/storyworld/ingest` (NEW): body `{limit, offset?, agent?}`. Paginate `/api/admin/sessions`, fetch each detail, and per session run the **EXISTING `_ingest_cases` machinery** (app.py:1887) with a real-field `extraction_rules` — map `metadata.enhanced_scenes` **[dict-or-list, per node]** → **one case per scene**, projecting `enhancement_status`→`source` (`success`→`enhanced`, else `baseline`) and joining `metadata.llm_calls.finish_reason` by `scene_node_id`, so each emitted case carries the **top-level `finish_reason`+`source`** that `SilentDegradationTool` reads (floors.py). **REDACT** `child_name`/`age` (phi_redaction) before writing. Add explicit `session_id` to the envelope (avoid `resource.id` collisions). Union all into `ws.out_dir/ingested_cases.jsonl` (the D1 bridge already grades these by `case_id`). One `AuditRecord` per batch. Return `{count, sessions, cases, errors_trapped}` (structured errors: 401/404/timeout/mis-join — never fabricate).

---

## 2. Tests-first (RED before code; all $0/offline — mock the StoryWorld client + `:3031`)
- **A1 (P1a):** `POST /v1/connector/config` with a mocked Test → writes `.connector_env` (key present, gitignored path), persists `base_url` only, key NOT in the response/SQLite. RED at parent (endpoint 404).
- **A2 (P1a):** a failing Test (mock 401) → surfaces the auth error, does NOT write the key. Non-vacuity.
- **A3 (P1b):** the real-field extraction on a FIXTURE real session (use a cached `out/storyworld_real/sessions/*.json` shape, or a trimmed redacted fixture) → N scenes → N §4.1 cases with correct `source`/`finish_reason` per scene (the `choice_2` fallback → `source:baseline,finish:content_filter`); **PII redacted** (no `child_name`/`age` in the emitted case); `session_id` present. RED at parent.
- **A4 (P1b):** the ingested cases are gradeable through the **D1 bridge** — `load_case(case_id)` resolves a batch-ingested case from `ingested_cases.jsonl` (mirror the NARR-5 D1 test). Confirms the loop reaches the grade path.
- **A5 (P1b, mis-join fails clean):** a malformed/mis-joined extraction → the `:3031` apply-gate (`score_extraction`) rejects → **nothing pinned** (count 0), no bad provenance.
- Mock the StoryWorld client + `EtlpJuteClient`/`:3031` so all tests are $0/offline (mirror `tests/bff/test_ingest_cases_bound.py`).

## 3. Plan-review risks
- **R1 — the real host is the owner's Azure URL, NOT `:3000`.** Use the owner-provided base; the connector form takes it. The live ingest needs the owner's key in `.connector_env` (the executor uses a MOCK client for tests; a live pull is a manual owner step, not in the green bar).
- **R2 — PII redaction entry point:** locate the exact `phi_redaction` callable in core (it's the kept-as-generic CE-PACK-6c mechanism). Redact `child_name`/`age` (and any reader free-text) before the case is written. Assert in A3 that the emitted case has no PII.
- **R3 — the auto-generated transform:** generate via `best_of_n_extractor` against a real sample, live-gate on `:3031`, PIN. For the OFFLINE tests, pin a transform fixture (don't call `:3031` in the green bar). The dict-or-list `enhanced_scenes` shape must be handled (real data varies).
- **R4 — secret hygiene:** the key never enters SQLite/manifest/git/the response/logs. Confirm `.connector_env` is gitignored (the `out/` tree is). Don't echo the key.
- **R5 — MOAT + core read-only:** `git diff 65a3d68 HEAD --` EMPTY for council four + `harness/grounding.py` + `verification/{spec,tools}.py` + `apps/bff/agent/tools.py`. P1b REUSES `_ingest_cases` (does not edit it) + clones `EtlpJuteClient` (new file). No re-snapshot.

## 4. Scope guards / NOT in scope
- **No** paid council (that's P2a/NARR-7+); **no** `grade_floor_only` or the Findings view (NARR-7 = P1c+P1d); **no** `kind:tool`/`kind:importer` declaration (P2b/P3); **no** moat/core edit; **no** healthcare touch.

## 5. Exit
- A1–A5 GREEN (`pack=narrative`); canonical regression (`pack=healthcare`) 0-new vs `65a3d68`; vitest 0-new; ruff clean; moat 0-diff; RED→GREEN with parent-RED pasted.
- **Demonstrable (live, owner-driven):** in the shell, enter the StoryWorld base URL + key → Test passes → pull a batch (e.g. limit=50) → N cases land in `ingested_cases.jsonl`, **PII-redacted**, gradeable by `case_id` via the D1 bridge. (The $0 floor-grade + the Findings view that make the SILENT_DEGRADATION incidence VISIBLE are NARR-7.)
- **HARD GATE:** fresh cold critic confirms — the key never persists outside `.connector_env`, PII is redacted before disk, the extraction maps real fields correctly + fails clean on mis-join, and the moat/core are 0-diff.
