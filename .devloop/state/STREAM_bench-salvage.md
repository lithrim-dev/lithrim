# STREAM: `bench-salvage` — Walking-Skeleton eval/calibration harness

> **Live monitor state.** 2026-05-30: pivoted from bottom-up "salvage the council in-process"
> to a **walking-skeleton product** — a domain-agnostic, tool-grounded eval/calibration harness
> for agentic-LLM outputs, built by **composing over the live verification stack** and thickening
> one vertical slice at a time. The harness grows INSIDE lithrim-bench.
>
> **Owner:** monitor · **Created:** 2026-05-30
> **North star:** a domain-agnostic, tool-grounded harness composed over `:8002 /v1/pipeline/evaluate`
> (council+structural+artifact, sync, inline) + `:3031` (JUTE copilot `/mappings/generate` + `/apply` +
> `/parse-hl7`) + pinecone KB (`:8002 /v1/kb/search`), with **SQLite as the configuration plane** and the
> **ontology as the domain definition**. Tool-grounding can flip verdicts (every flip logged); every
> correction is a **fine-tuning-ready record** for the future RLVR / data-lake north star. Paper:
> replicate current state on the harness, then strengthen via tool-grounded correction of
> confident-but-wrong judges (**S-BS-7** = the exhibit). `Agent` = the system under test.

## Authority docs

- `walking-skeleton-architecture` + `etlp-ecosystem-capability-map` (monitor memory) — the converged design + the live-endpoint map
- `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md` — why the FP is calibration not aggregation (S-BS-7 origin)
- `docs/HANDOFF_BENCH_SALVAGE_2026-05-29.md` — M1 close-out
- `docs/PAPER_OUTLINE.md` — locked one-claim guardrail (scribe = semantic-only by construction)
- `out/scribe_v1.live_pipeline_evaluate.bench_scribe_v1_inject_condition_1bd0f10dc7b5.json` — **WS-0 live baseline** (the captured live `/v1/pipeline/evaluate` result; grounding code is built offline against it)
- Live endpoints: `:8002` lithrim-backend (FastAPI, `COMPLIANCE_COUNCIL_VERSION=v2`), `:3031` etlp-mapper (Clojure JUTE)

---

## Milestone arc (walking-skeleton: build vertical, thicken incrementally)

| WS | Title | Composes / new code | Status |
|---|---|---|---|
| **WS-0** | One case end-to-end over live APIs | grade via live `:8002 /v1/pipeline/evaluate` (PROVEN) → persist (fs+SQLite) → **harness-side grounding** (S-BS-7 presence-check disproves MED FP) → composite + calibration-report | **done — closed 2026-05-30** (`9001a36..0859c8d`; NON-BLOCKING) |
| **WS-1** | SQLite config plane | Agent eval-profile {judges, council_config, ontology, tools, kb_bindings}; the **ontology data model** (flags+tiers+owners+questions+verification_contract); 4 slim-path collections doc-shim | **ready** (next) · WS-0 closed |
| **WS-2** | Generalize `:8002` | inject `council_config`/`ontology` into `PipelineRequest` (Optional, additive) → domain-agnostic grading | queued · WS-1 |
| **WS-3** | Tool-grounding generalized + mid-loop | JUTE contracts via `:3031 /generate`; pinecone query via `:8002 /v1/kb/search`; local vector (S-BS-5); grounding post-hoc → mid-loop | queued · WS-1 |
| **WS-4** | Eval-pack loop + LOCKED calibration gate | promote-to-eval + external SDK run + `/eval-runs/compare`; eval-pack = preregistered locked criteria incl. a **calibration gate**; NULL/regression parity | queued · WS-3 |
| **WS-5** | Frontend shell + one plugin UI | shell loads UI apps as plugins; first plugin = bring-data → graded+grounded case + calibration report | queued · WS-4 |
| **WS-6** | Compartmentalize-local | swap live `:8002` for in-process M1 council; local vector for pinecone; offline/licensed packaging; folds the old ~28-module analyze flow + Clojure server + desktop + packaging | queued · WS-5 |
| *(future)* | RLVR / data-lake | correction records → data lake → RL/fine-tuning flywheel (verification contracts = verifiable rewards) | north star |

---

## Current cycle

| Cycle | Status | Note |
|---|---|---|
| **M1** — salvaged council + sync orchestrator in-process | **done 2026-05-30** | case-1 `reject==reject` (1/1); `FABRICATED_HISTORY` caught; `MEDICATION_NOT_IN_TRANSCRIPT` CONFIRMED FP. Persisted-judge-reasoning enabler landed. 82 tests green. Now a **WS-6 input** (the compartmentalize-local target), not the spine. Artifacts: `out/scribe_v1.local{,.guardfix}.ndjson`; handoff `docs/HANDOFF_BENCH_SALVAGE_2026-05-29.md`. |
| **COUNCIL-EVIDENCE-GATE** — R3(d) consensus fix | **⛔ halted / re-scoped 2026-05-30** | Pre-check P0 ($0.10) FALSIFIED the fix: the MED FP is findings-first + fully-evidenced (SPEC §2b false — NDJSON projection artifact); root cause = judge calibration, not aggregation. Re-routed to **S-BS-7** (the WS-0 grounding worked example). Records: `REPORT_r3d_precheck_falsification_2026-05-30.md`, `r3d_precheck_P0_raw_evidence_2026-05-30.ndjson`, `.devloop/sessions/{session,critique}-…COUNCIL-EVIDENCE-GATE-2026-05-30.{json,md}`. Closed commit `b54e92a`. |
| **WS-0** — one case over live APIs | **✅ done — closed 2026-05-30** | Spine landed end-to-end on the one M1 scribe case, entirely OFFLINE against the captured baseline (zero new paid calls). New `lithrim_bench/harness/` pkg (grade/persist/grounding/correction/report) + `scripts/run_ws0.py` + `tests/test_ws0.py`; 6 atomic commits `9001a36..0859c8d` (+ session-log `9d2b721`). **S-BS-7 exhibit works:** the med presence-check disproves+suppresses the confident `MEDICATION_NOT_IN_TRANSCRIPT` FP (zidovudine is verbatim in transcript; judge cites that very line as proof of absence), retains `FABRICATED_HISTORY`, holds composite verdict at `reject`, emits one versioned RLVR correction record. S-BS-8 (4 null-code findings) skip-logged not dropped. Calibration report-only (ECE 0.5, small-N caveat). **Audit CLEAN; critique NON-BLOCKING** (`critique-bench-salvage-phaseWS-0-2026-05-30.md`); 89/89 tests green, new code ruff-clean. Session log `session-bench-salvage-phaseWS-0-2026-05-30.json`. |
| **WS-1** — SQLite config plane + ontology data model | **ready** (next) | WS-0 unblocks it. Run `/devloop-expand-driver bench-salvage WS-1`. Fold in the 3 WS-0 critique open-questions (calibration role-conflation → WS-4 note; `_rescore` thresholds + med-extraction heuristic → encode in the ontology contract) and normalize S-BS-9 pack shapes. |
| WS-2 … WS-6 | queued | see milestone arc + `TASK_PACK_bench-salvage.json`. |

---

## Open seams

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-1 | v1 pure-legacy vs findings-first | medium | **resolved** — findings-first w/ validated spans (pre-check P0) |
| S-BS-2 | v2 over-fire family (FABRICATED_CONSENT / INCOMPLETE_DOCUMENTATION / …) | medium | **open — CONFIRMED on live v2 by the WS-0 smoke test** (over-fires on the scribe note); ADDITIONAL grounding targets → WS-3 |
| S-BS-3 | blast radius of authoritative findings | high | **superseded/moot** — the aggregation fix it guarded doesn't land |
| S-BS-4 | SQLite shape (doc-shim vs relational) | medium | **DECIDED = document shim** → applied in WS-1 |
| S-BS-5 | local vector stub; sqlite-vec blocked | medium | open → WS-3 (numpy over rag receipts; or `:8002 /v1/kb/search`) |
| S-BS-6 | v1-vs-v2 as the canonical baseline | medium | **disposition recorded (WS-0), ratify in WS-1** — live = v2 (over-fires confirmed). Monitor lean adopted as the harness-baseline default: **compose-over-live-v2 + let grounding clean the over-fire**. WS-1 ratifies it in the SQLite config (Agent eval-profile council_config). |
| S-BS-7 | MED FP is judge-calibration, not aggregation | **high** | **HYPOTHESIS confirmed (WS-0)** — the presence-check disproves+suppresses the live MED FP end-to-end (the WS-0 worked example landed). Generalize from one hardcoded contract to the ontology's verification_contract layer in WS-1; mid-loop (judge-calls-tool) in WS-3. |
| S-BS-8 | live `/v1/pipeline/evaluate` returns structural/artifact findings with **null taxonomy code** (4 in the WS-0 baseline; S-P1-16 generalization) | medium | **handled in WS-0** (skip-logged into the `ungrounded` bucket, retained in active, surfaced in report — never dropped). Upstream code-backfill in `lithrim-backend artifact_evaluator` remains out of harness scope. |
| S-BS-9 | same `case_id` carries divergent `expected_compliance_verdict` shape across pack files (string `'reject'` in `scribe_v1.jsonl` vs accept-set list `['needs_review','reject']` in `scribe_v1.n10.jsonl`) | low | **opened WS-0; CONFIRMED.** Worked around this cycle (runner pins driver-cited source + `expected_block()` shape-tolerant). Underlying pack-shape inconsistency → **normalize in WS-1** pack hygiene. Fix loc: pack generation + `lithrim_bench/picklist.py` resolution order. |

---

## First move (next monitor action)

**WS-0 is closed (audit CLEAN, critique NON-BLOCKING). The walking-skeleton spine is proven end-to-end on the one case.** WS-1 is now unblocked and is the top of the queue.

1. **PRIORITY-0: expand the WS-1 driver.** `/devloop-expand-driver bench-salvage WS-1`. Deliverables (per `TASK_PACK_bench-salvage.json` WS-1): SQLite **config plane** (Agent eval-profile {judges, council_config, ontology, tools, kb_bindings}) so the WS-0 run is driven from config not hardcoded args; the **ontology data model** unifying `SafetyFlagDefinition` (`safety_flags.py:37`) + `TIER_1/2/3` (`compliance_council.py:176/201/212`) + `_TIER1_OWNERS:232` + freetext KEY QUESTIONS, **plus a per-question `verification_contract`**; 4 slim-path doc-shim collections (S-BS-4). Re-grep all anchors at authoring.
2. **Promote the WS-0 hardcoded contract into the ontology.** The `MedPresenceCheck` (currently in `grounding.WS0_CONTRACTS`, `ontology_version="ws0-hardcoded/0"`) becomes the ontology's **first verification_contract** — and per the WS-0 critique Q4.3, the **med-extraction strategy must be an explicit, testable part of the contract** (3-letter names, brand/generic), not a buried heuristic.
3. **Carry the 3 WS-0 critique open-questions:** (Q4.1) the calibration "correct" predicate conflates per-judge vote with a **case-level** expectation — **must be role-aware (or composite-based) BEFORE WS-4 makes it a gate**; note it in the WS-4 calibration-gate spec now so it isn't forgotten. (Q4.2) ratify the `_rescore` severity→verdict thresholds (lone MEDIUM→BLOCK). (Q4.3) the med-extraction heuristic, above.
4. **Ratify S-BS-6 in WS-1:** adopt compose-over-live-v2 as the harness baseline in the Agent eval-profile council_config; let grounding clean the over-fire (S-BS-2 flags → WS-3 grounding targets).
5. **Normalize S-BS-9** as part of WS-1 pack hygiene (single `expected_compliance_verdict` shape across pack files; or a documented shape contract the runner reads).
6. Do NOT start WS-2+ until WS-1 lands the config plane + ontology driving the WS-0 vertical.

---

## References

- Persona: `.devloop/personas/MONITOR.md`
- Task pack: `.devloop/tasks/TASK_PACK_bench-salvage.json` (M1 + COUNCIL-EVIDENCE-GATE history; WS-0..WS-6)
- Memory: `walking-skeleton-architecture`, `etlp-ecosystem-capability-map`
- Live baseline: `out/scribe_v1.live_pipeline_evaluate.bench_scribe_v1_inject_condition_1bd0f10dc7b5.json`
- Falsification (S-BS-7 origin): `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md`
- Paired publication stream: `.devloop/state/STREAM_paper-1-copilot.md`
