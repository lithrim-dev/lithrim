# Critique — bench-salvage NARR-6 (UI-driven StoryWorld eval loop — connector config P1a + real-field batch ingest P1b)

> **HARD GATE — fresh cold critic** (no implementation context; agent `a1a5e0c5af249bc97`). Mandate: Gate 0 (both envs + vitest) → the load-bearing **secret-hygiene + PII-redaction** checks → 4 spec-fidelity questions → moat-freeze. Edited nothing; scratch worktrees removed; `.active` left as found (`storyworld_`).
>
> **Verdict: CLEAN.** Gate 0 green both envs + vitest (0-new); tests-first non-vacuous; the two load-bearing properties hold non-vacuously; the moat is byte-frozen (incl. `_ingest_cases` byte-identical, `workspace.py` + `phi_redaction.py` 0-diff); scope clean; the green bar is honestly scoped ($0/offline, the live half disclosed). One NON-BLOCKING OPEN-QUESTION (bare given-name) + 3 confirmed low/medium seams.

Date: 2026-06-17 · Cycle: `14fdc7a..b0435b9` (4 commits, test-red-first; moat baseline `65a3d68` already 0-diff) · Monitor 7-item audit: CLEAN.

---

## Gate 0 — supreme, re-run cold
- **Targeted (pack=narrative):** A1–A5 → **5 passed** (`test_connector_config.py` ×2, `test_storyworld_ingest.py` ×2, `test_narrative_batch_ingest_bridge.py` ×1). Full narrative suite: HEAD 105 fail / parent 106 fail → **0 NEW** (strict subset; the failures are clinical/council tests run under the wrong pack — env-misfit, identical at parent).
- **Regression (pack=healthcare full):** HEAD 8 fail / 589 pass == parent 8 fail / 589 pass → **0 NEW** (HEAD's set ⊆ parent's; one parent failure resolved at HEAD). The `.active` caveat (S-BS-NARR6-1) was discharged by comparing parent vs HEAD with the SAME on-disk `.active=storyworld_`; the critic's own runs used `tmp_path` workspaces (real `.active` untouched).
- **vitest:** 1 fail / 133 pass == parent → 0-new (the 1 = pre-existing S-BS-145 `app.test.jsx`, reproduces byte-for-byte at parent; the new ConnectorForm is JSX-only, adds 0 vitest tests).
- **Tests-first:** `0f6b31b test(...)` lands FIRST; checked out → A1–A5 FAIL `assert 404 == 200` (endpoints absent) → RED→GREEN non-vacuous. (`StoryWorldAdminClient` landed in the RED commit so the monkeypatch target exists — EXECUTOR-sanctioned, confirmed non-vacuous via 404 not AttributeError.)
- **Lint:** ruff clean on the 6 cycle `.py`.

## The load-bearing adversarial checks
**Secret hygiene — PASS.** `.connector_env` + `connector.json` are under the gitignored `out/` tree (`git check-ignore` confirms; `git ls-files` empty). The config endpoint writes the key ONLY to `ws.dir/.connector_env` (`STORYWORLD_API_KEY=…`); the response returns `{connector_id, base_url, status, last_tested}`, the `connector.json` sidecar persists `{connector_id, base_url, last_tested}`, the `AuditRecord.after` is `{base_url, last_tested}` — **never the key** anywhere. A1 asserts the secret absent from the response, the sidecar, and ALL `*.sqlite` (bytes-membership), present only in `.connector_env`; A2 (401) asserts the key is NOT written. No real Azure key in the diff (placeholders only). The shell `ingestStoryworld` does not send the key.

**PII redaction — PASS (+ 1 OPEN-QUESTION).** The endpoint (`_prepare_storyworld_session`) structurally never reads `child_name`/`age`/`reader_note` into any record AND runs `redact_text` over the scene body+title; `PHI_PATTERNS` is 0-diff (no clinical-residue extension). A3 is non-vacuous — the fixture genuinely carries `child_name:"Noor Al-Mansoori"`, `age:9`, and an inline `jane.doe@example.com`+phone in `reader_note`; A3 asserts the full name, the `age`/`child_name` keys, and the inline email all absent from the emitted case. **OPEN-QUESTION (NON-BLOCKING) → `S-BS-NARR6-4`:** the child's bare *first name* ("Noor") appears inline in the narrative `clean_text` and survives (`redact_text` catches only patterned PII, not bare given names; A3 asserts only the *full* name). Spec-consistent (owner §8.1 specified key-drop + body-redact; entity-level name redaction would corrupt the graded narrative) — an OPEN-QUESTION for the spec author of the eventual export / paid-council path, not a NARR-6 blocker (the floor reads provenance, not names).

## The 4 spec-fidelity questions
1. **Surface — match.** Both endpoints additive; `StoryWorldAdminClient` clones `EtlpJuteClient` (injectable, lazy-httpx, `test_connection` never raises); `_prepare_storyworld_session` maps `source`/`finish_reason`/`session_id` + handles dict-OR-list `enhanced_scenes` (`_scenes_to_list`); `_ingest_cases` **byte-identical** + REUSED via `ctx.ingest_cases`; `workspace.py` 0-diff (sidecar, not a dataclass field).
2. **Behavioral — tests assert the spec.** A3's content_filter fallback → `source:baseline` + `finish_reason:content_filter` (the exact `SilentDegradationTool` signature, floors.py:169-192; `_to_envelope` surfaces both top-level). A4 drives the REAL ingest endpoint → corpus → `load_case` (the D1 bridge) → `grade_inprocess` verdict ($0 predictors). A5 mis-join → `count==0`, `errors_trapped>=1`, score-spy `>=1` (gate ran), persist-spy `==0`, corpus empty.
3. **Out-of-scope — none.** 10 files, +1193/-0. No `grade_floor_only`/Findings view (NARR-7), no paid council/CostModal, no `kind:tool`/`kind:importer`, no healthcare touch, no snapshot regen, no `jute_extractor.py`/`_ingest_cases`/`workspace.py` edit. `app.py` = 3 hunks, pure additions.
4. **Honesty — HONESTLY SCOPED.** The green bar proves the BFF logic only (field projection + PII drop+redact + envelope + `_ingest_cases` reuse + mis-join-fails-clean) with the StoryWorld client / `best_of_n_extractor` / `score_extraction` / `:3031` all MOCKED ($0/offline per the driver). No test fabricates a live result. The live transform-convergence + real pull are explicitly carried as `S-BS-NARR6-3` (the owner-driven manual half), not overclaimed.

## Moat-freeze — 0-DIFF (asserted)
`git diff 65a3d68 HEAD --` EMPTY across council four + `harness/grounding.py` + `verification/{spec,tools}.py` + `apps/bff/agent/tools.py`; `_ingest_cases` byte-identical; `workspace.py` + `phi_redaction.py` + `jute_extractor.py` 0-diff. No re-snapshot.

## Seams (open)
- **`S-BS-NARR6-3`** (medium, **NARR-6/7 owner-driven**) — the auto-generated `jute_transform` + the live `:3031` apply-gate over real-shape data + the real StoryWorld pull are MOCKED in the green bar ($0 driver-mandate); the live owner pull is the unproven half / the demonstrable manual attestation. The honest demarcation.
- **`S-BS-NARR6-4`** (low, NEW — spec-author, export/council path) — the child's bare given-name survives inline in the graded `clean_text` (can't be stripped without corrupting the narrative). Decide handling for the eventual data-export / paid-council surface.
- **`S-BS-NARR6-1`** (low, pre-existing) — `test_ws5_bff` is sensitive to the on-disk `.active` pointer (a narrative-pack `.active` makes the grade subprocess inherit pack=narrative without `snomed_subsumption`). Fails at parent too; a fixture should override `get_active_workspace`. A test-hygiene cycle.
- **`S-BS-NARR6-2`** (low) — `session_id` is enriched by the endpoint post-`_ingest_cases` (the frozen `_to_envelope` drops it). Acceptable; the batch endpoint is the only real-field producer.

## Disposition
The NARR-6 contract (P1a+P1b) is met; Gate 0 green both envs; the secret + PII properties hold non-vacuously; the moat is byte-frozen; scope is clean; the green bar is honest. **Cycle closes CLEAN.** NARR-7 (P1c `grade_floor_only` + P1d the Findings view — the visible payoff) is next; the live owner pull (`S-BS-NARR6-3`) is the manual demonstration. The bare-name OPEN-QUESTION (`S-BS-NARR6-4`) is for the spec author before any data export.
