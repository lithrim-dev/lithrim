# Handoff — `bench-salvage` → next session (2026-06-16, HONEST-1)

> **HONEST-1 (open-core MVP Phase 0) CLOSED CLEAN** — executed INLINE (monitor-driven executor)
> + a HARD-GATE fresh-critic **subagent** (`a565a146`, CLEAR-TO-CLOSE [0 BLOCKING / 1 NB / 1 OQ]).
> The grade path no longer fabricates a `0.0/WARN` accuracy on UNLABELED data — the honesty-thesis
> contradiction that would have shipped on the exact surface a new BYO user sees first.

## What landed (branch `bench-salvage/ws6c-dspy`, LOCAL — NOT pushed)

**Build `bdd24c0..b436471`** (5 commits, test-red-first, pathspec-only):
- **W1/W2 (`6feb103`):** `calibration_check` derives `label_status` ∈ {labeled|unlabeled|partial} from
  `expected_compliance_verdict` presence. Unlabeled → `verdict_match_rate`/`ece` = `None`, `status`
  `"unlabeled"`, an honest caveat — **NO fabricated 0.0/WARN, NO manufactured 1.0/PASS** (honest-Δ both
  ways). The labeled path is **byte-equivalent** (the 30 existing `test_ws4a`+`test_ws5_bff` calibration
  assertions unchanged) and a labeled MISMATCH still reports a genuine WARN. `calibration()` gained
  `labeled=` (default True, byte-identical); `run_eval` threads it so the stored BLOB is honest too.
- **W3/W4/W5 + H-D6 (`e2dc71b`):** the Report Calibration block WITHHOLDS accuracy/ECE on unlabeled
  ("verdict & grounding shown; accuracy & calibration withheld"); the CaseTab reads an unlabeled case as
  "unknown ground truth" not a clean negative; `GET /v1/case` emits a `labeled` flag (`_case_labeled` —
  the serializer coerced `expected_safety_flags`→`[]`, so a presence signal was required; H-D6, approved
  at plan-review).
- **S-BS-165 fix (`b436471`):** dropped a stray `f`-string prefix (ruff F541) the critic flagged — touched
  files now ruff-clean.
- **MOAT byte-frozen:** `compliance_council.py` / `signals.py` / `judge_metric.py` / `judges_dspy.py` =
  0 diff; `grade.py composite()` untouched. Diff confined to `report.py` / `run_eval.py` / `app.py` /
  `artifact.jsx` + the 3 test files.

## Verification — CLEAN
- **Gate 0 (env exported), 0-new:** pytest **563p / 2 pre-existing S-BS-96 / 4 skip**; vitest **124p / 1
  pre-existing S-BS-145** — the critic confirmed BOTH pre-existing in isolation (not on faith).
- **Tests-first + non-vacuous:** `bdd24c0` precedes the fixes; the critic proved RED-on-revert (report.py →
  A1-A3 RED; artifact.jsx → A4/A5 RED), tree restored.
- **Monitor 7-item audit CLEAN + HARD-GATE fresh-critic CLEAR-TO-CLOSE.**

## Open seams (none block)
- **S-BS-165 (low) — CLOSED in-cycle** (`b436471`): ruff F541 in the new BFF test.
- **S-BS-166 (low, OQ):** A3's partial-batch fixture uses `ece=0.0`; a production unlabeled rec carries
  `ece=None` (W2). Add an end-to-end partial-batch test with a real `ece=None` record to pin the
  `if ece is not None and n` pooling guard. Spec-author call; fold into BYO-INGEST or a cleanup.
- Carried: S-BS-96 (2 observation guards), S-BS-145 (vitest titlebar), S-BS-155/157/158/159/160/161 (low).

## Next move — BYO-INGEST (Phase 1, the front door)
`/devloop-expand-driver bench-salvage BYO-INGEST`. The 4 blockers from [[byo-data-ingestion-cliff]]:
1. `POST /v1/case` + a writable case store (the agent's `dataset.source`/`case_id` can point at it).
2. A **note+FHIR → `{transcript, artifacts[], patient_profile}` adapter** (bounded v1: DocumentReference +
   plain note; reuse the base64 decode at `app.py:_artifact_note`; **punt** reference-resolution; do NOT use
   JUTE for a trivial decode per `[[jute-for-data-transformations]]`).
3. **Bind-on-ingest** — a new agent binds to the ingested `case_id`, NOT cloned from the pack fixture
   (`bff.js createAgent` clones today; `_pack_agent_template` `app.py:667-711`).
4. An `ingest_case` SDK-MCP tool (the 16th; first that touches DATA — respect the A-SAFE deny-default +
   the FieldInfo trap, `[[fastapi-endpoint-as-plain-call-fieldinfo-trap]]`).

**HONEST-1 was its precondition** — now that the unlabeled path is honest, ingestion can ship without the
Review pane lying on a new user's first run. Per [[lithrim-doubledown-decision]]: Phase 2 = floor-in-`_core`,
Phase 3 = author-the-floor; **the real falsifier is getting ONE scribe-vendor on real data once 0-2 land** —
that's outside-the-machine work the agent loop can't do.

Resume: `/devloop-resume bench-salvage`; authoritative state in `streams.json current_phase` + the STREAM
First-move + this handoff + the HONEST-1 critique/session-log. Memory `[[lithrim-doubledown-decision]]`,
`[[byo-data-ingestion-cliff]]`, `[[bench-test-env-pack-export]]`.
