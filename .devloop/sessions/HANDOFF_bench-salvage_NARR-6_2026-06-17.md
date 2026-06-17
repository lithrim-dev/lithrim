# HANDOFF — bench-salvage — NARR-6 closed → NARR-7 (2026-06-17)

> **For the next session.** The UI-driven StoryWorld eval loop now has its **connect + pull + ingest** half.
> **NARR-6 (P1a connector config + P1b real-field batch ingest) is CLOSED CLEAN** (HARD GATE; fresh cold
> critic CLEAN + monitor audit CLEAN; secret hygiene + PII redaction both pass non-vacuously; moat byte-frozen).
> Next is **NARR-7 = P1c (`grade_floor_only`) + P1d (the corpus Findings view)** — the **visible payoff**
> ("see it over there" lands here). **Resume:** `/devloop-resume bench-salvage`, then read this + the NARR-6 driver/critique.

---

## What just landed (NARR-6, $0)
| Commit | What |
|---|---|
| `0f6b31b` | test-RED — A1–A5 (`test_connector_config.py`, `test_storyworld_ingest.py`, `test_narrative_batch_ingest_bridge.py` + a redacted real-shape fixture + `StoryWorldAdminClient`); 5×404 at parent |
| `b58e859` | **P1a+P1b BFF** — `POST /v1/connector/config` + `POST /v1/connector/storyworld/ingest` (reuses the frozen `_ingest_cases`) |
| `b95cd80` | **P1a UI** — `ConnectorForm` (mirrors `WorkspaceSwitcher`) + `bff.js` `testConnector`/`ingestStoryworld` |
| `b0435b9` | the NARR-6 session log |

**The loop so far:** in the shell, enter the StoryWorld base URL + key → Test → pull a batch → per-session the real-field extraction (`enhanced_scenes` dict-or-list → per-scene case, `enhancement_status`→`source`, `finish_reason` join, `session_id`) runs through the **frozen** `_ingest_cases` → cases land in `ws.out_dir/ingested_cases.jsonl`, **PII-redacted** (`child_name`/`age` key-dropped + `redact_text` body), gradeable by `case_id` via the **D1 bridge**. The key lives ONLY in the gitignored `.connector_env`. **MOAT byte-frozen** (incl. `_ingest_cases` byte-identical, `workspace.py` 0-diff). Gate 0: A1–A5 5/5, 0-new both envs + vitest.

## The architectural win NARR-7 leans on (re-confirmed)
`ground()` runs the floor decls over the **CASE ROW independent of the council** (grounding.py:645-668). So **P1c `grade_floor_only`** is a small helper: build a synthetic `{findings:[], verdict:PASS, provenance:{pipeline_run_id}}` and feed it through the EXISTING `ground()` + `composite()` → the SILENT_DEGRADATION/BRACKET_LEAK floor BLOCKs appear at **$0, no council, moat untouched**. The narrative case row already carries top-level `finish_reason`+`source` (what `SilentDegradationTool` reads), and the NARR-6 extraction puts them there.

## What's next — NARR-7 (P1c + P1d — the visible payoff)
- **P1c (small):** `grade_floor_only(case, ontology)` (slot beside `grade_replay/live/inprocess` in `lithrim_bench/harness/grade.py`) → synthetic result through `ground()`+`composite()`; route via `POST /v1/run-eval?floor_only=true` (a new `RunEvalRequest` field, dispatch in `run_eval.run` before any backend). Persists `$0` provenance. Demonstrable: `floor_block_count>0` on an ingested SILENT_DEGRADATION case with zero council spend. **MOAT READ-ONLY** (`ground()`/`composite()`/`floors.py` are read, never edited).
- **P1d (medium):** `GET /v1/corpus/findings` — reads `ws.ingested_cases.jsonl`, runs the P1c $0 floor-only grade per case, aggregates `{SILENT_DEGRADATION, BRACKET_LEAK}` incidence by story/mode/lang + a flagged-case list; a new **6th Findings tab** in `ArtifactPane` (`artifact.jsx:535-547`, mirror the `CorpusTab` self-fetch pattern at `:348`) rendering the incidence grid + list, drilling into the EXISTING `ReportTab` on row-click ($0 read-only — per the owner decision, no silent paid re-grade). New `bff.js getCorpusFindings()`. **This closes the loop fully self-serve in the shell** — and reproduces the proven 11/841 sweep in-UI at $0.
- Risk to carry: `GET /v1/corpus/findings` re-runs the $0 floor per case on each call (~841 at full scale) — fine at $0/deterministic, but add a `limit`/pagination param to avoid a slow first paint (pre-compute is P3). The incidence grid needs story/mode/lang as case metadata — the NARR-6 transform should populate them (verify/extend in P1d).

## After NARR-7 (deferred)
- **P2a (PAID):** the multi-model council over the corpus, behind the existing CostModal (per-batch confirm), surfaced alongside the $0 floor verdict (floor keeps deterministic precedence). **Folds in the over-fire fix** — the council needs RICH reader-choice/emotion context in the extraction (the `PERSONALIZATION_MISS` over-fire from the live real-session grade) — and the NARR-5 seams (`S-BS-NARR4-1` real LENGTH_VIOLATION catch, `S-BS-97` per-judge model provenance).
- **P3:** generalize → `kind:importer`, multi-connector "eval anything"; pre-compute the corpus aggregate.

## Open seams (NARR-6)
- **`S-BS-NARR6-3`** (medium, owner-driven) — the auto-generated `jute_transform` + the live `:3031` apply-gate + the real StoryWorld pull are MOCKED in the green bar; the live owner pull is the unproven half / the manual attestation. A live pull with the owner's key is the demonstration (capture as a proof note).
- **`S-BS-NARR6-4`** (low, spec-author) — the child's bare given-name survives inline in the graded `clean_text` (can't strip the protagonist's name without corrupting the narrative); decide handling before any data export / the paid-council path.
- **`S-BS-NARR6-1`** (low, pre-existing) — `test_ws5_bff` is sensitive to the `.active` pointer; a fixture should override `get_active_workspace`. **The active workspace is currently `storyworld_` (narrative) — reset to `demo-clinical`/`default` for a clean clinical test env** (or the live pull stays on `storyworld_`).
- **`S-BS-NARR6-2`** (low) — `session_id` enriched post-`_ingest_cases`; acceptable.
- Carried: the NARR-5 seams (→ P2a).

## Standing prefs (unchanged)
Services UP this session (curl /health; never autostart) · no push without owner approval (branch `bench-salvage/ws6c-dspy`, **NOT pushed**) · pathspec-only atomic commits · tests-first (RED before code) · canonical env `LITHRIM_BENCH_PACK=healthcare …` for the green bar (`pack=narrative` for the targeted) · diagnose-before-edit · honest-Δ / $0-first, PAID deliberate + owner-go'd · MOAT byte-frozen · secrets only in gitignored `.connector_env`/`.live_env` · PII redact-at-ingest.

## First move (next session)
1. Read this + `docs/research/PROOF_narrative_live_council_2026-06-17.md` + the NARR-6 critique + the NARR-6 driver §0 (the P1c/P1d spec).
2. `/devloop-expand-driver bench-salvage NARR-7` (P1c+P1d; re-grep `grade.py` + `run_eval.run` dispatch + `grounding.py:645-668` + `artifact.jsx:535-547`/`CorpusTab:348`; the $0 floor-only path + the corpus aggregate + the 6th tab).
3. Optionally: the owner-driven LIVE pull (NARR-6 `S-BS-NARR6-3`) with the real key — drop the connector form in the shell, pull a batch, confirm cases ingest live; capture as a proof note.
