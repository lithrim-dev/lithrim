# STREAM — `brs-arc` (Bench Reporting Series)

> **Live monitor state for the BRS arc.** Updated on every cycle close.
> Companion to `.devloop/personas/MONITOR.md`.
>
> **Stream owner:** monitor
> **Created:** 2026-05-26 (post BRS-0a close)
> **North star:** close measurement + observability gaps surfaced by BRS-0a so the paper claims are auditable end-to-end.

## Authority docs

- `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` — the spec the engine implements (D1–D7 acceptance)
- `docs/PAPER_OUTLINE.md` — locked paper outline (with 2026-05-22, 2026-05-23, 2026-05-26 reframe notes)
- `docs/research/MEASUREMENT_AUDIT_2026-05-26.md` — BRS-0a output, load-bearing for BRS-0b through BRS-6
- `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` — D1–D9 + A1–A6 amendments (Paper 1 = Jute Copilot paper)
- `docs/HANDOFF_BRS_0b_2026-05-26.md` — most recent cycle close handoff
- `.devloop/tasks/TASK_PACK_brs-arc.json` — machine-readable task list

---

## Current phase table

| Cycle | Title | Status | Closing commit | Critique |
|---|---|---|---|---|
| **BRS-0a** | Bench measurement audit — validator coverage framing | **done — closed 2026-05-26** | `85901d8` | inline (no critique-doc committed) |
| **BRS-0b** | Bench reporting fix + paper framing rewrite | **done — closed 2026-05-26** | `956e07c` | inline (no critique-doc committed) |
| **BRS-1** | Provenance observability — `silent_confident_certification` boolean + `verdict_flipped_by_stage` string + validator-template-pin (template id + checks-run-count + checks-failed-count) | **ready — recommended next** | — | — |
| **BRS-3** | Variant B critique pass — structural findings as immutable critique context | **deprecation candidate** — zero structural findings on FHIR packs at current validator coverage; either cancel or rescope HL7-only post profile registration | — | — |
| **BRS-4** | artifact_judge per-artifact-type opt-out | **rescope candidate** — opt-out target is `fhir_appointment` not `scheduling_confirmation`; better path is "improve artifact_judge precision via critique pass" | — | — |
| **BRS-6** | Paper amendment (now Paper 1 = Jute Copilot paper per A1–A6) + 1-day council-confidence experiment | **blocked on BRS-1** (BRS-1's observability fields make BRS-6 §5 measurement auditable) | — | — |

---

## BRS-0a close summary (2026-05-26)

**Verdict:** PROCEED (audit shipped; surfaced validator-coverage gap framing).

| Metric | Result |
|---|---|
| Closing commit | `85901d8` (`docs(research): bench measurement audit -- validator coverage framing (BRS-0a)`) |
| Critique mode | inline (no separate critique-doc) |
| Output artifact | `docs/research/MEASUREMENT_AUDIT_2026-05-26.md` |

**Findings dispositioned:** §1.3 (validator coverage decomposition), §2.2 (278 fhir_appointment BLOCKs all attributable to artifact_judge), §3 (mapping 17/22/26/42/93 reconciliation) carried into BRS-0b as paper-section rewrites.

---

## BRS-0b close summary (2026-05-26)

**Verdict:** PROCEED (reporting fix + paper framing landed; §7 byte-identical).

| Metric | Result |
|---|---|
| Closing commit | `956e07c` (`fix(bench): not_applicable distinct + paper framing (BRS-0b)`) |
| Tests | 78/78 pass; 3 new tests (i.1 parser, i.2 worst-of invariance, i.3 §7 snapshot) |
| §7 invariance | byte-identical to baseline on all 4 packs (scribe/scheduling/coding/triage) |
| Critique mode | inline (no separate critique-doc committed) |
| Scope held | yes — `docs/PAPER_OUTLINE.md`, `docs/label_owner_matrix.md`, `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` correctly excluded from BRS-0b commit per HANDOFF |

**Handoff brief:** [`docs/HANDOFF_BRS_0b_2026-05-26.md`](../../docs/HANDOFF_BRS_0b_2026-05-26.md) — preserved verbatim; this scaffold reads from it.

---

## Open seams

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-BRS-1 | `triage_v1` CI in JSON (`[0.8938, 0.9938]`) vs paper §7.1 (`[0.844, 0.954]`) — paper text drifted before BRS-0b | low | `docs/paper_draft/07_results.md` §7.1 | BRS-0b | open (deferred to BRS-6) |
| S-BRS-2 | Pre-existing working-tree drift: `docs/PAPER_OUTLINE.md` (2026-05-26 amendment) + `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` (new) + `docs/label_owner_matrix.md` (modified) not yet committed | low | working tree | BRS-0b | open — needs separate doc-commit cycle |
| S-BRS-3 | The S17/S18 closures (scheduling mapping reconciliation + scribe "semantic-only by design" framing removal) live in BRS-0b paper rewrites; bench taxonomy + injector list spot-checked but no automated guard prevents future regression | medium | `tests/` (no test covers paper-vs-injector consistency) | BRS-0b | open — candidate guard in BRS-1 |

---

## Next candidates (monitor's queue)

1. **BRS-1 — Provenance observability (recommended next).** Add `silent_confident_certification: bool`, `verdict_flipped_by_stage: str`, `validator_template_id: str`, `checks_run_count: int`, `checks_failed_count: int` to PipelineProvenance. ~1–1.5 days. **Cheap, observability foundation that BRS-6 §5 measurement builds on.**
2. **S-BRS-2 commit cycle.** The three working-tree doc files surfaced in the BRS-0b handoff need their own doc-only commit (or a revert decision for `label_owner_matrix.md`). ~30 min. Do this before BRS-1 to clean the working tree.
3. **BRS-6 paper amendment.** Blocked on BRS-1 (BRS-6 §5 measurement needs BRS-1's observability fields). ~4–5 days post the 1-day council-confidence experiment.
4. **BRS-3 cancel or rescope decision.** Pure planning, ~30 min reading + decision.
5. **BRS-4 rescope decision.** Pure planning, ~30 min.

---

## First move (next monitor action)

When the next monitor session resumes this stream:

1. Decide whether to clean S-BRS-2 (working-tree drift) first as a tiny doc-commit cycle, or fold it into BRS-1's commit story.
2. Draft `.devloop/prompts/brs-arc_phaseBRS-1_provenance_observability_driver.md` per the template. The 2026-05-21 BRS-1 driver in `lithrim-command-center/.lithrim/prompts/brs_01_provenance_observability_exec_driver.md` is the working reference — re-grep against current code (per MONITOR §Phase 1a) and **expand** it to also persist `validator_template_id`, `checks_run_count`, `checks_failed_count` per the BRS-0a reframed scope.
3. Once driver is ready, `/devloop-kickoff brs-arc BRS-1` and paste into a fresh exec session.

---

## References

- Persona: `.devloop/personas/MONITOR.md`
- Task pack: `.devloop/tasks/TASK_PACK_brs-arc.json`
- BRS-0a output: `docs/research/MEASUREMENT_AUDIT_2026-05-26.md`
- BRS-0b handoff: `docs/HANDOFF_BRS_0b_2026-05-26.md`
- Paper framing amendments: `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md`
- Prior driver bundles (in lithrim-command-center): `lithrim-command-center/.lithrim/prompts/brs_*_driver.md` (these are the historical drivers for BRS-0a/0b/1 — the BRS-1 one is a starting point, not a final draft)
