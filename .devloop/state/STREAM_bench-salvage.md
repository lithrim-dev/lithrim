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
| **WS-0** | One case end-to-end over live APIs | grade via live `:8002 /v1/pipeline/evaluate` (PROVEN) → persist (fs+SQLite) → **harness-side grounding** (S-BS-7 presence-check disproves MED FP) → composite + calibration-report | **READY** (next) |
| **WS-1** | SQLite config plane | Agent eval-profile {judges, council_config, ontology, tools, kb_bindings}; the **ontology data model** (flags+tiers+owners+questions+verification_contract); 4 slim-path collections doc-shim | queued · WS-0 |
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
| **WS-0** — one case over live APIs | **ready** | Grading seam **PROVEN LIVE 2026-05-30** (HTTP 200, ~40s; baseline saved). Build persist + harness-side grounding OFFLINE against the saved baseline (zero new paid calls). Driver: `bench-salvage-phaseWS-0-one-case-over-live-driver` (**stub** — run `/devloop-expand-driver bench-salvage WS-0`). |
| WS-1 … WS-6 | queued | see milestone arc + `TASK_PACK_bench-salvage.json`. |

---

## Open seams

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-1 | v1 pure-legacy vs findings-first | medium | **resolved** — findings-first w/ validated spans (pre-check P0) |
| S-BS-2 | v2 over-fire family (FABRICATED_CONSENT / INCOMPLETE_DOCUMENTATION / …) | medium | **open — CONFIRMED on live v2 by the WS-0 smoke test** (over-fires on the scribe note); ADDITIONAL grounding targets → WS-3 |
| S-BS-3 | blast radius of authoritative findings | high | **superseded/moot** — the aggregation fix it guarded doesn't land |
| S-BS-4 | SQLite shape (doc-shim vs relational) | medium | **DECIDED = document shim** → applied in WS-1 |
| S-BS-5 | local vector stub; sqlite-vec blocked | medium | open → WS-3 (numpy over rag receipts; or `:8002 /v1/kb/search`) |
| S-BS-6 | v1-vs-v2 as the canonical baseline | medium | open — **WS-0 confirms live = v2 (over-fires)**; decide harness baseline in WS-0/WS-1; lean compose-over-live-v2 + grounding cleans the over-fire |
| S-BS-7 | MED FP is judge-calibration, not aggregation | **high** | open — **WS-0 worked example** (presence-check disproves it); reproduces on the LIVE path |
| S-BS-8 | live `/v1/pipeline/evaluate` returns structural/artifact findings with **null taxonomy code** (4 in the WS-0 baseline; S-P1-16 generalization) | medium | open — harness finding→contract lookup keys on code; handle (skip+log, surface in report) in WS-0/WS-2 |

---

## First move (next monitor action)

**WS-0 is ready and the grading seam is proven live.** The remaining new code is **persist + harness-side grounding**, both buildable+testable OFFLINE against the captured baseline (`out/scribe_v1.live_pipeline_evaluate.<case>.json`) — **zero new paid calls.**

1. **PRIORITY-0: expand the WS-0 driver.** `/devloop-expand-driver bench-salvage WS-0`. Re-grep the live contract anchors at authoring: `PipelineRequest` (`../lithrim-backend/app/services/pipeline/models.py:237`, `org_id` required), the route (`app/routes/pipeline.py:66`), auth = `X-API-Key` (`.live_env`: `LITHRIM_API_KEY`/`LITHRIM_ORG_ID`). Driver §2 deliverables: persist (fs blob + SQLite doc-shim), harness-side grounding (S-BS-7 presence-check), structured+versioned correction record (RLVR-ready), composite report, calibration **report-only** (reliability + ECE). Lock the "no backend change in WS-0" guardrail (config injection = WS-2).
2. **PRIORITY-0: the grounding step is offline.** It reads the saved baseline → runs the presence-check contract on `MEDICATION_NOT_IN_TRANSCRIPT` → disproves (zidovudine IS in transcript) → suppress + re-score; emits the correction record. The S-BS-8 null-code findings get skip+logged (surfaced in the report, not silently dropped).
3. **Decide S-BS-6 in WS-0/WS-1:** harness baseline v1 vs live-v2. Monitor lean = compose-over-live-v2 (prod-real + more FP exhibits for the paper) and let grounding clean the over-fire.
4. **Calibration is step-1 (report-only) here**; the LOCKED calibration gate (Avenridge-style standing) is WS-4. Capturing per-rollout confidence in the correction record (the raw-events shape) is what makes both the calibration report and the RLVR north star possible — do not drop it.
5. Do NOT start WS-1+ until WS-0 lands the vertical end-to-end on the one case.

---

## References

- Persona: `.devloop/personas/MONITOR.md`
- Task pack: `.devloop/tasks/TASK_PACK_bench-salvage.json` (M1 + COUNCIL-EVIDENCE-GATE history; WS-0..WS-6)
- Memory: `walking-skeleton-architecture`, `etlp-ecosystem-capability-map`
- Live baseline: `out/scribe_v1.live_pipeline_evaluate.bench_scribe_v1_inject_condition_1bd0f10dc7b5.json`
- Falsification (S-BS-7 origin): `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md`
- Paired publication stream: `.devloop/state/STREAM_paper-1-copilot.md`
