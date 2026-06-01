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
| **WS-1** | SQLite config plane | Agent eval-profile {judges, council_config, ontology, tools, kb_bindings}; the **ontology data model** (flags+tiers+owners+questions+verification_contract); 4 slim-path collections doc-shim | **done — closed 2026-05-30** (`6f4612f..0c73ff0`; NON-BLOCKING) |
| **WS-2** | Generalize `:8002` | inject `council_config`/`ontology` into `PipelineRequest` (Optional, additive) → domain-agnostic grading | **bench-side LANDED 2026-05-31** (`8b396d3..5ba1bec`, D0/D3/D4, PROCEED-WITH-CAVEATS); **backend D1/D2/D4 ⛔ HARD-GATE-paused** |
| **WS-3** | Tool-grounding generalized + mid-loop | **WS-3a:** promote the verification core (DSPy bench-gated JUTE generator + mutation/joint gate) into `lithrim_bench/verification/` + wire the bench-accepted contract into `harness/grounding` as the FLOOR (PASS→BLOCK). **WS-3b (deferred):** pinecone via `:8002 /v1/kb/search` + local vector (S-BS-5) + judge-calls-tool mid-loop into live `:8002` | **WS-3a done — closed 2026-06-01** (`59a3cba..d6fe96f`; audit CLEAN + fresh-critic NON-BLOCKING); prototyped on `spike/verification-toolbox` (66 offline tests). **WS-3b queued.** |
| **WS-4** | Eval-pack loop + LOCKED calibration gate | promote-to-eval + external SDK run + `/eval-runs/compare`; eval-pack = preregistered locked criteria incl. a **calibration gate**; NULL/regression parity. **Gates:** S-BS-13 (floor-apply replay) + S-BS-16 (floor inject-param validation) before any floor ships | **ready (WS-3a closing)** |
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
| **WS-1** — SQLite config plane + ontology data model | **✅ done — closed 2026-05-30** | Lifted the WS-0 hardcoded spine into two planes, zero new paid calls. New `harness/{ontology,config,collections}.py` + `data/ontology/clinical_v1.json` (23 flags / 16 questions / 1 verification_contract / severity_map) seeded byte-deterministically by `scripts/seed_ontology.py` (seed-not-import: light-import `safety_flags`, AST-parse tiers/owners; eval path reads only the JSON) + committed `data/config/agents/ws0_default.json` driving `scripts/run_eval.py` (canonical) with `run_ws0.py` as a thin shim over one grounding path. WS-0 critique **Q4.2 + Q4.3 CLOSED** (severity_map + extraction params as data); **Q4.1 recorded-only** (owner_roles in the correction record + ontology) → WS-4. **S-BS-6 ratified** (compose-over-live-v2 stored in the eval-profile); **S-BS-9 normalized** (shape contract + normalizer in picklist.py). 8 atomic commits `6f4612f..0c73ff0`. **Audit CLEAN; critique NON-BLOCKING** (`critique-bench-salvage-phaseWS-1-2026-05-30.md`); 99/99 tests green, ruff-clean. Session log `session-bench-salvage-phaseWS-1-2026-05-30.json`. |
| **WS-2** — generalize `:8002` config injection | **ready** (next) | WS-1 unblocks it. **PRE-CONDITION (WS-1 critique Q4.1):** reconcile the ontology flag-source — 4 flags (`FABRICATED_CONSENT_SCOPE`, `MALAFFI_CODE_PROPAGATION`, `MISSING_DUAL_CODING`, `WRONG_PATIENT_INFO`) are in the council `safety_flags.py` the ontology seeded from but **absent from `taxonomy/taxonomy_snapshot.json`** (the CLAUDE.md contract). Decide flag-source authority BEFORE the ontology drives live grading. Run `/devloop-expand-driver bench-salvage WS-2`. |
| **WS-3** — verification core promotion + structural floor (WS-3a) | **✅ done — closed 2026-06-01 (`59a3cba..d6fe96f` + close-out)** | Promoted the `spike/verification-toolbox` core into `lithrim_bench/verification/` (spec/etlp_client/tools/jute_gen/jute_dspy/mutation/router; `KbRagTool` class dropped) behind a `[verification]` extra (dspy/httpx), import-isolated (monitor-re-verified: dspy/httpx/pinecone/onnx absent from `sys.modules` on default deps). **Headline:** wired the structural FLOOR into `harness/grounding` via a sibling `_FLOOR_CONTRACT_TYPES` registry + `_run_floor` sub-path (Decision 2) — a bench-accepted contract injects a BLOCK the council missed and flips PASS→BLOCK (severity HIGH→weight 1.0 ≥ `block_at_or_above` 1.0), logged via `build_floor_correction` (inverse rollout, Decision 6) + surfaced in `composite()`. Backward-compat: clinical_v1 declares no floor → `ground()` additively identical (verdict + partitions unchanged, `floor_blocks==[]`, no floor HTTP via `_BoomHttp`). 3 by-construction packs homed (10/8/10, byte-deterministic regen — monitor-re-verified diff==0) + pinned clean Patient validator. **Audit CLEAN (7/7; A1/A3/A4/A5 monitor-re-verified: isolation `[]`, floor 5/5, packs diff==0, 164 passed/3 dspy-skipped); fresh-critic NON-BLOCKING** (`critique-bench-salvage-phaseWS-3-2026-06-01.md`; 0 BLOCKING / 6 NB / 3 OQ). New seams S-BS-13/14/15; Q4-3 → **S-BS-16** follow-up (touches the core invariant). Feeds `paper-1-copilot` §4/§6/§7 + settles S-P1-22. WS-3b (KB/RAG/ONNX + judge-calls-tool mid-loop) queued. |
| WS-4 … WS-6 | queued | see milestone arc + `TASK_PACK_bench-salvage.json`. |

---

## Open seams

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-1 | v1 pure-legacy vs findings-first | medium | **resolved** — findings-first w/ validated spans (pre-check P0) |
| S-BS-2 | v2 over-fire family (FABRICATED_CONSENT / INCOMPLETE_DOCUMENTATION / …) | medium | **open — CONFIRMED on live v2 by the WS-0 smoke test** (over-fires on the scribe note); ADDITIONAL grounding targets → WS-3 |
| S-BS-3 | blast radius of authoritative findings | high | **superseded/moot** — the aggregation fix it guarded doesn't land |
| S-BS-4 | SQLite shape (doc-shim vs relational) | medium | **resolved (WS-1)** — doc-shim applied (4 collections + config plane); rationale recorded in `collections.py`/`config.py` docstrings |
| S-BS-5 | local vector stub; sqlite-vec blocked | medium | open → WS-3 (numpy over rag receipts; or `:8002 /v1/kb/search`) |
| S-BS-6 | v1-vs-v2 as the canonical baseline | medium | **resolved/ratified (WS-1)** — compose-over-live-v2 stored in `ws0_default.eval_profile.council_config.disposition` (STORED only; injection = WS-2). Harness baseline is live-v2 + grounding cleans the over-fire. |
| S-BS-7 | MED FP is judge-calibration, not aggregation | **high** | **HYPOTHESIS confirmed (WS-0)** — the presence-check disproves+suppresses the live MED FP end-to-end (the WS-0 worked example landed). Generalize from one hardcoded contract to the ontology's verification_contract layer in WS-1; mid-loop (judge-calls-tool) in WS-3. |
| S-BS-8 | live `/v1/pipeline/evaluate` returns structural/artifact findings with **null taxonomy code** (4 in the WS-0 baseline; S-P1-16 generalization) | medium | **handled in WS-0** (skip-logged into the `ungrounded` bucket, retained in active, surfaced in report — never dropped). Upstream code-backfill in `lithrim-backend artifact_evaluator` remains out of harness scope. |
| S-BS-9 | same `case_id` carries divergent `expected_compliance_verdict` shape across pack files (string `'reject'` in `scribe_v1.jsonl` vs accept-set list `['needs_review','reject']` in `scribe_v1.n10.jsonl`) | low | **resolved (WS-1)** — code-level shape contract + `normalize_expected_verdict`/`expected_block`/`load_case` in `picklist.py`; collision order documented + deterministic (PACK_FILES n10-first, consumers pin via `load_case`). Residual (Q4.3): bare `resolve_case_fixtures` still n10-first by default → future pack-hygiene note. |
| S-BS-12 | S-BS-10 lint is **one-directional** — `gradeable_flags_outside_snapshot` (`seed_ontology.py:160`) catches "runtime tiers a flag the snapshot hasn't blessed" but NOT the reverse: a snapshot code the runtime stops tiering silently becomes `gradeable=false` with no lint. Per `CLAUDE.md` (snapshot = contract-of-record) the reverse is arguably the more dangerous divergence | medium | **open — opened WS-2 bench-side fresh-critic Q4.1; CONFIRMED.** Inert today (19==19). Recommend: lock the source-of-truth direction + a **bidirectional** lint (snapshot-code-not-gradeable ⇒ FAIL or explicit allowlist). Carry into the WS-2 backend driver or a small follow-up. Fix loc: `scripts/seed_ontology.py:152-160`. |
| S-BS-11 | `build_prompt` is hardcoded clinical prose, not templated from the taxonomy — truly domain-agnostic *prompting* (injected ontology generating the prompt) is a large rewrite of safety-critical prose | medium | **open — opened WS-2 D2 checkpoint; CONFIRMED.** `build_prompt:517-622` embeds HIPAA/FABRICATED_CONSENT/category-code rules as English; only taxonomy ref is "one of the codes from the SAFETY FLAG TAXONOMY below" — no tier-list templating. **WS-2 D2 scope LOCKED to the tractable seam:** instance-resolvable tier/owner/known-code LOOKUP (Surface A) + model selection (Surface B) + additive-block-only prompt threading; full prose rewrite deferred to **S-BS-11** (future cycle). Fix loc: `../lithrim-backend/app/services/compliance_council.py build_prompt:517 / build_source_message_prompt:1036`. |
| S-BS-10 | ontology flag-source fork — 4 flags (`FABRICATED_CONSENT_SCOPE`, `MALAFFI_CODE_PROPAGATION`, `MISSING_DUAL_CODING`, `WRONG_PATIENT_INFO`) seeded from council `safety_flags.py` are **absent from `taxonomy/taxonomy_snapshot.json`** (the CLAUDE.md contract-of-record) | medium | **DECIDED 2026-05-31 (user) = Option A: snapshot-authoritative + lint gate.** Diagnosis CONFIRMED: the 4 are *defined-but-untiered* in the backend itself (defined in `safety_flags.py:132/414/444/473`, absent from `compliance_council.py` TIER_1/2/3 + `_TIER1_OWNERS`) — already inert in grading. **Resolution (WS-2 deliverable-0, harness-only):** ontology gradeable set = the 19 tiered snapshot codes; `seed_ontology.py` cross-checks every seeded flag against `taxonomy_snapshot.json` and partitions **gradeable (in-snapshot, tier+owner)** vs **reference (out-of-snapshot, `tier=null, gradeable=false`)**; grounding/`_rescore` use gradeable-only; `safety_flags.py` stays a prose source for in-snapshot codes only. Lint FAILS if a *gradeable* flag is outside the snapshot. Rejected: backfill (Option B — needs a backend tier/owner clinical decision, separate cycle) and snapshot-as-prose-source (Option C — bigger schema change, noted as eventual cleanup to drop the `safety_flags.py` coupling entirely). |
| S-BS-13 | `run_eval` passes `http_client=None` → a declared floor uses the LIVE `:3031` path even under `--replay` (no offline floor-apply replay) | medium | **open → WS-4 (gate).** CONFIRMED (WS-3a). Inert today (clinical_v1 declares no floor) + the *test* path injects a fake client, so A3 holds. WS-4's eval-pack loop MUST add a floor-apply replay capture before any domain ships a floor contract. Fix loc: `scripts/run_eval.py run()`. |
| S-BS-14 | Floor declared without the `[verification]` extra raises ImportError at apply-time, not config-load | low | **open.** CONFIRMED (WS-3a). Cosmetic/DX — no early "install lithrim-bench[verification]" message. Fix loc: `grounding.py _run_floor` or ontology-load validation. |
| S-BS-15 | `_CONTRACT_EXECUTORS` is now the SUPPRESS-only registry but keeps its generic name (floor types live in the sibling `_FLOOR_CONTRACT_TYPES`) | low | **open.** Naming clarity only; rename to `_SUPPRESS_EXECUTORS` explicitly deferred this cycle (not worth the churn). Fix loc: `grounding.py`. |
| S-BS-16 | Floor-injected flag bypasses the gradeable/owner partition + severity validation — injected into `active` AFTER the per-finding loop (`grounding.py:355-365`), so `inject_flag_code`/`inject_severity` are read raw with no check that the code is a declared gradeable flag (owner per invariant #4) or the severity a key in `severity_map.weights` | **medium** | **open → follow-up cycle (WS-3b/WS-4), GATE before any floor-declaring ontology ships.** Fresh-critic Q4-3; touches the `CLAUDE.md` core invariant ("labels true by construction; never silently scored"). Inert for the shipped clinical ontology (no floor). A misconfigured floor could BLOCK on an ownerless code, or silently never fire on a typo'd severity (`weight_of`→0.0). Recommend: validate `inject_flag_code` ∈ `ontology.gradeable_flags()` + `inject_severity` ∈ `severity_map.weights` at ontology-load, raising loudly. Fix loc: `grounding.py:355-365` / ontology-load. |

---

## First move (next monitor action)

**WS-3a close-approved 2026-06-01 (audit CLEAN + fresh-critic NON-BLOCKING).** The 5 atomic commits are staged in the working tree, **gated on user sign-off** (HARD GATE — close precedes commit).

1. **✅ WS-3a LANDED 2026-06-01** (`59a3cba..d6fe96f` — 5 atomic D0-D4 + monitor close-out commit; hashes recorded in `session-bench-salvage-phaseWS-3-2026-06-01.json`). **Next monitor action = choose the next cycle (item 2 below); do NOT autostart.**
2. **Next cycle (monitor's choice — do NOT autostart):**
   - **WS-3b** — KB/RAG/ONNX stack (S-BS-5 local vector + pinecone via `:8002 /v1/kb/search`) + judge-calls-tool MID-LOOP into the live council. The mid-loop half waits on WS-2's paused backend `council_config`/`ontology` injection; the KB half does not. Natural home for the **S-BS-16** floor inject-param validation (small, touches the core invariant) + the S-BS-15 rename + S-BS-14 DX fix + the stale `tools.py` spike comments / dangling `TOOL_KB_RAG`.
   - **WS-4** — eval-pack loop + LOCKED calibration gate. **Gated** on S-BS-13 (floor-apply replay capture) + S-BS-16 (inject-param validation) BEFORE any floor-declaring ontology ships. Also picks role-aware-vs-eligible-raiser ownership (WS-1 Q4.2: `_TIER1_OWNERS`-only = 8/23 flags).
3. **WS-2 backend half (separately gated, unrelated to WS-3):** still blocked on (a) user lands/stashes the in-flight `../lithrim-backend/` WIP (8 files) and (b) user sign-off on the every-`:8002`-caller blast radius; backend commits need their OWN fresh-critic pass. Carry S-BS-12 (bidirectional lint) into that driver.
4. **Paper feed:** WS-3a now settles `paper-1-copilot` **S-P1-22** (§2/§4 reframe) — the DSPy bench-gated generator is the disclosed mechanism for §4/§6/§7. Resolve S-P1-22 once the commits land.
5. **Carry WS-1 Q4.3:** `resolve_case_fixtures` n10-first default → future pack-hygiene note.

---

## References

- Persona: `.devloop/personas/MONITOR.md`
- Task pack: `.devloop/tasks/TASK_PACK_bench-salvage.json` (M1 + COUNCIL-EVIDENCE-GATE history; WS-0..WS-6)
- Memory: `walking-skeleton-architecture`, `etlp-ecosystem-capability-map`
- Live baseline: `out/scribe_v1.live_pipeline_evaluate.bench_scribe_v1_inject_condition_1bd0f10dc7b5.json`
- Falsification (S-BS-7 origin): `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md`
- Paired publication stream: `.devloop/state/STREAM_paper-1-copilot.md`
