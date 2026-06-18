# Live dogfood: ClinVerdict through the Lithrim self-serve loop (2026-06-17)

> Drove the full **Agentic-Scribe → lithrim-sdk JSON → ingest (JUTE) → council → report** loop on the
> real BFF (`:8787`) + `:3031`, workspace `clinverdict` (pack=`healthcare`, external at
> `../lithrim-pack-healthcare`). Goal: surface the gaps that block a physician doing this self-serve.
> Companion: [`docs/specs/SPEC_CLINVERDICT_SELF_SERVE.md`](../specs/SPEC_CLINVERDICT_SELF_SERVE.md)
> (the static gap analysis — this is the *live* confirmation + new operational gaps).

## What was run
- Built a simulated **Agentic-Scribe push** (`/tmp/agentic_scribe_push.json`, 10 sessions, 30KB raw
  nested JSON — NOT the case envelope, so JUTE has to identify+transform it) from the 10 ClinVerdict cases.
- Drove `POST /v1/chat` (BYO-Claude, $0) → the agent called `ingest_cases` → JUTE transform on `:3031`
  → 10 cases pinned to the workspace corpus. **JUTE converged on the new clinical shape.**
- Set up was already done (3-judge healthcare council, Azure). Graded all 10 `in_process` (real Azure council).

## The headline result (honest-Δ, real)
The healthcare council, on a physician's adversarial suite it had never seen, **agreed with the
physician verdict on 8/10 cases**:

| case | physician | Lithrim council | agree | council findings |
|---|---|---|:--:|---|
| 01 neurology/HIV | reject | reject | ✓ | INCOMPLETE_DOCUMENTATION |
| 02 lumbar puncture | reject | **approve** | ✗ | — |
| 03 kidney injury | reject | reject | ✓ | INCOMPLETE_DOCUMENTATION |
| 04 blood cancer | reject | reject | ✓ | MEDICATION_NOT_IN_TRANSCRIPT, INCOMPLETE_DOCUMENTATION |
| 05 psychology | reject | reject | ✓ | FABRICATED_HISTORY, INCOMPLETE_DOCUMENTATION |
| 06 diabetes | reject | reject | ✓ | MEDICATION_NOT_IN_TRANSCRIPT, INCOMPLETE_DOCUMENTATION |
| 07 pediatrics/food | reject | reject | ✓ | MISSED_ESCALATION, PROXY_MISATTRIBUTION, INCOMPLETE_DOCUMENTATION |
| 08 all-negative | approve | approve | ✓ | — |
| 09 pediatrics/seizure | reject | reject | ✓ | PROXY_MISATTRIBUTION, INCOMPLETE_DOCUMENTATION |
| 10 splinter/vaccine refusal | reject | **approve** | ✗ | — |

**The 2 misses are the point, not noise.** Both (case 02 lumbar omission, case 10 vaccine-refusal
*dissent erasure*) are the subtle medico-legal omissions ClinVerdict was built to expose — exactly where
the **physician meta-verdict** (META-VERDICT-1) + a **dissent/completeness floor** (NARR-FLOOR-1) would
close the loop. Note `PROXY_MISATTRIBUTION` fired on cases 07 + 09, matching the physician's own tags.

⚠️ **Caveat that IS a gap:** the verdicts are real because the agent grades from `out/clinverdict_v1.jsonl`
(a hand-run extractor file, transcripts intact) — **not** from the JUTE-ingested corpus (see gap #1/#6).

## Gap log (surfaced live; ~14)

### Blocking — the ingest→grade loop is not closed
1. **Transcript silently dropped on ingest (HIGH).** JUTE's generated transform set `context="{}"` for
   **all 10** ingested cases — the SOAP survived, the transcript (the grading reference) was lost, and
   nothing flagged it. A grade off this corpus would be against an empty transcript. This is the exact
   silent-degradation ClinVerdict warns about, occurring *inside* the ingest. *(out/workspaces/clinverdict/out/ingested_cases.jsonl)*
2. **Ingest writes one corpus; grading reads another (HIGH).** `ingest_cases` pins to
   `ingested_cases.jsonl`; `run_eval` grades the agent's `dataset.source`
   (`out/clinverdict_v1.jsonl` here). The ingested corpus is *pinned but not registered gradeable* — the
   code comment names it: "the gradeable-corpus registration … is the NARR-2→NARR-4 bridge (flagged as a
   seam)" (`app.py:2188`). The loop only worked because the source was pointed at a hand-extracted file.
3. **No `case_id` selector on `run-eval` (HIGH).** `RunEvalRequest` = `{agent, live, in_process}` only.
   To grade a different case you must `PUT /v1/agent` with `dataset.case_id` changed. *(app.py:309)*
4. **No batch-grade-the-corpus path (HIGH).** `eval-pack` batches *agents*, not cases. "Evaluate all
   10" required a manual loop: repoint agent → grade, ×10. *(app.py:741)*
5. **`/v1/corpus` returns the wrong corpus (MED).** It returns the *correction* corpus
   (`read_corpus()`, empty), not the ingested cases — so the 10 ingested cases have no listing endpoint. *(app.py:729)*

### Blocking — pack/workspace wiring
6. **A workspace pinned to an external pack doesn't record where it lives (HIGH).** `packs_dir` was
   `null`; the grade subprocess crashed `FileNotFoundError: pack 'healthcare' not found via entry points,
   LITHRIM_BENCH_PACKS_DIR, or …/packs`. The UI lists `healthcare` (the BFF env can see it) and lets you
   pin it, but the workspace never captures `packs_dir`, so grading is dead-on-arrival. **Unblocked by
   hand-setting `packs_dir` in `out/workspaces/clinverdict/workspace.json`** — which is what
   create-workspace should have done. *(pack.py:133, _grade_via_subprocess app.py:517)*

### UX / persistence
7. **"Refresh poof — everything is gone" (HIGH, user-reported).** On browser reload the UI loses all
   state (ingested cases, active case, chat) though the workspace + corpus survive on disk — the shell
   doesn't rehydrate the active workspace on load.
8. **Ingest is chat-only; no upload (MED).** The 30KB scribe JSON had to be pasted into the chat message;
   no drop-zone/file-picker (the spec's NARR-8-UPLOAD-1).

### Fidelity / observability
9. **`context_kind` hardcoded `narrative_scene` (MED).** All 10 clinical cases carry the StoryWorld
   template's context_kind — the extractor doesn't set a per-domain kind.
10. **Requested carry-through fields dropped (MED).** `scribe_output.model` / `finish_reason` came through
    as `None` for all 10 despite explicit extraction_rules.
11. **SOAP silently reshaped into a FHIR DocumentReference (LOW-MED).** The note got wrapped as a
    `DocumentReference` attachment; content survives (the `_artifact_note` decoder handles it) but it's an
    unrequested transformation.
12. **No USD cost for council grades (MED).** ~10 paid Azure grades ran with no in-product $ meter (only
    the BYO-Claude *chat* subprocess shows a cost). The user spends with no surfaced number. (TRACE-1/OBS-COST-1.)
13. **Per-judge confidence sometimes `None` (LOW-MED).** `policy_judge` returned `confidence=None` on
    several cases → ECE caveated "small N." (S-BS-97.)
14. **Run history doesn't surface `case_id` (LOW-MED).** `/v1/runs` rows show PASS/BLOCK/WARN (stage
    verdicts) but not which case; case_id renders as `?`.

## What this confirms vs the spec
The static spec ([`SPEC_CLINVERDICT_SELF_SERVE.md`](../specs/SPEC_CLINVERDICT_SELF_SERVE.md)) predicted
the *authoring/meta-verdict/label* gaps. The live run **adds the operational ones the static read could
not see**: the ingest→grade bridge being unwired (#2), the transcript-drop (#1), the external-pack
`packs_dir` crash (#6), no case selector / no corpus batch (#3/#4), and the refresh-state-loss (#7).
The **NARR-2→NARR-4 "gradeable-corpus bridge"** is the single highest-leverage fix: it closes 1–5 at once.

## Changes I made (workspace config only, gitignored, reversible)
- `out/workspaces/clinverdict/workspace.json`: `packs_dir: null → "../lithrim-pack-healthcare"` (the
  create-workspace omission; keep it — it's the correct value).
- `healthcare_default.dataset.case_id` was repointed per-case during the batch (now `clinverdict_10`).
- Corpus now holds 10 JUTE-ingested cases (transcript-dropped, see #1).

## Artifacts
- Simulated push: `/tmp/agentic_scribe_push.json` · batch verdicts: `/tmp/batch_results.json` ·
  run ids persisted to `GET /v1/runs` (12 runs).

## Resolution — the ingest→grade loop (landed 2026-06-18)
The critical defect (#1) and the loop gaps (#2–5) are **fixed, tested, and proven live** (not committed).

**Phase 1 — the silent transcript-drop (#1).** `_to_envelope` is now domain-agnostic (carries an
explicit `context`/`transcript`; narrative `ctx_bits` fallback unchanged), and `score_extraction` gained
an envelope-level invariant that **rejects** a transform with empty `context` — so a lossy transform
fails the gate instead of pinning silently. Tests: [tests/verification/test_ingest_context_fidelity.py](../../tests/verification/test_ingest_context_fidelity.py)
(RED→GREEN, 6). Live: re-ingest regenerated the transform → case 01 now carries the full transcript
(`context` len 1810).

**Phase 2 — close the loop (#2–5).** `GET /v1/cases` lists the ingested corpus (with a `has_context`
fidelity signal); `POST /v1/run-eval {case_id}` grades a specific case via the shared `_grade_case`
helper (override threaded to the subprocess via `--case-id`); `POST /v1/cases/grade` batch-grades the
corpus into a cohort `{matrix, summary}`. Tests: [tests/bff/test_corpus_grade_loop.py](../../tests/bff/test_corpus_grade_loop.py)
(6). Live: `/v1/cases` → 10 rows (case 01 `ctx=Y`, stale ones `ctx=N`); `/v1/cases/grade` subset →
`{n:2, graded:2, verdicts:{approve:1,reject:1}}`.

**Phase 3 — NARR-9 (#6), self-describing packs_dir (landed 2026-06-18).** `create_workspace` now
captures the external pack's location (`_resolve_external_packs_dir`, `workspace.py`) so a workspace
pinned to an externally-distributed pack grades regardless of the BFF's ambient env — no more
dead-on-arrival. Tests: [tests/test_workspace_packs_dir.py](../../tests/test_workspace_packs_dir.py) (5,
RED→GREEN). Live: a fresh `pack=healthcare` workspace via `POST /v1/workspaces` now records
`packs_dir: …/lithrim-pack-healthcare` instead of `null`.

**Still open:** #7 (refresh-rehydration — the "poof"); #9–14 (context_kind default, carry-through fields,
FHIR-wrap, USD cost, run-id case_id). The 9 pre-fix corpus cases still read `ctx=N` — re-ingest to refresh them through the new gate.
Regression: all touched files green in isolation; the only suite failures are pre-existing (the external
healthcare-pack ontology drift `23→25`, confirmed by a stash test, + suite test-order fragility).
