All claims confirmed against source. The key facts are now grounded:

- Parked bench council is byte-identical line count (2733) to backend but **differs** (`diff` exit 1) — stale mirror, confirming the WS-6b map's "snapshot drift" risk.
- DSPy smoke ledger has 28 rows across the documented modes (v2_critique=4, v3_grounded=12, v4_toolbox=8, plus 4 untagged).
- `council_dspy.py:17-21` carries the verbatim "DELIBERATE SIMPLIFICATION ... None of that is reproduced" docstring proving the consensus IP was deliberately dropped.
- `council_v2.py:4-6` is the cross-provider trio mirroring backend JUDGES_V2.

I have everything I need. Writing the recomposition plan now.

---

# WS-6b RECOMPOSITION / PORT PLAN — Bench-Salvage WS-6 Consolidation Track

**Doc role:** the WS-6b port/recomposition plan artifact. Reconciles the strangler-fig topology (`docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md`) with the read-only subsystem audit. Every architectural claim is tagged CONFIRMED (verified against source this session) / INFERRED (sound deduction from the maps) / HYPOTHESIS (needs a decision or probe).

**Baseline pins (CONFIRMED this session):** `lithrim-backend` @ `mvp-ready` / `493b533` (clean); `lithrim-bench` @ `main` / `b065f14` (WS-5d); DSPy prototype in worktree `agent-adefc36309f77ed1b` (throwaway, reference-only — `council_dspy.py:3` "This is a throwaway").

**Frame inherited from topology spec (do not relitigate here):** strangler-fig not de-Mongo retrofit (§Decision); sequencing **(B)** — BFF re-points from live `:8002` to in-process per-capability (§Sequencing); **PORT-not-rewrite** the validated council IP (§WS-6c); Mongo retired from the product path (§Topology DB row); ETLP stays a `:3031` JVM sidecar (§ETLP Services); **frozen-contract rule** — WS-6c+ swaps implementation behind `run_eval.run` / `report.composite` / §10 BFF, never the signature.

**S-BS-24 caveat honored throughout:** the backend test suite is RED pre-existing (e.g. `tests/test_council_evidence_extraction.py:12` imports the renamed `RetrievalMatch` and fails at collection — CONFIRMED in the WS-3b map). Green-backend is **NOT** a gate for any WS-6 phase. The bench's own offline tests + the by-construction packs are the regression gate.

---

## 1. END STATE — the single clean Python-Layer service

**One clean FastAPI Python-Layer process** (the topology's middle layer, `SPEC_PRODUCT_SERVICE_TOPOLOGY.md:30`) that *is* the bench backend and *is* the shell's BFF. No Mongo, no Celery, no LangGraph. Diagram-in-prose, outer-to-inner:

```
                         UI Platform (Tauri/React shell, WS-5)
                                      │  BFF = Python-Layer API (§10 v1 contract, frozen)
                                      ▼
┌───────────────────────────── PYTHON LAYER (one process) ─────────────────────────────┐
│                                                                                        │
│  HARNESS GRADE→GROUND→RLVR LOOP  (already built: scripts/run_eval.py:101-152)          │
│    grade ── in-process call ──▶ RECOMPOSED AGENTIC PIPELINE (was LangGraph)            │
│      │        (today: grade_live POSTs :8002 /v1/pipeline/evaluate, grade.py:40-127)   │
│      │                                                                                  │
│      ▼                                                                                  │
│   ground() ─ ontology-driven suppress registry + structural FLOOR (grounding.py)       │
│      │        via VERIFICATION TOOLBOX (verification/tools.py + router.py compose_verdict)│
│      ▼                                                                                  │
│   composite + calibration (report.py, report-only) ──▶ RLVR records                    │
│      │        build_correction / build_floor_correction → corpus-row/1                 │
│      ▼        (correction.py, corpus.py — append-only NDJSON lake)                      │
│   REPOSITORY INTERFACE (was MongoProvenanceStore Protocol, provenance.py:25)           │
│                                                                                         │
│  RECOMPOSED AGENTIC PIPELINE (was app/workflows/*.py LangGraph):                        │
│    straight-line async fn: retrieve → safety-prescreen → confidence-gate →             │
│      [skip?] COUNCIL → evidence → (persist via repo)                                    │
│    ├─ COUNCIL = PORTED consensus IP (Tier-1/2/3 + ownership + NKA + llama-veto)         │
│    │            wrapping DSPy-REBUILT per-judge modules (judges/taxonomy prompts)       │
│    ├─ deterministic tools: failure_clustering, evidence_extraction, compliance_guard    │
│    │            (pure fns, no I/O — port verbatim)                                      │
│    └─ KB: hipaa_retrieval recomposed behind a kb_rag VerificationTool                   │
│                                                                                         │
│  SALVAGED ENABLING INFRA (port-as-is):                                                  │
│    llm_provider.get_sync/async_openai_client (Azure cross-provider factory)             │
│    config subset (LITHRIM_LLM_PROVIDER + 5 Azure deployment ids + COUNCIL_VERSION)      │
└────────────────────────────────────────────────────────────────────────────────────────┘
        │ HTTP :3031 (structural validation — the ONE remaining outbound)
        ▼
   ETLP-mapper (Clojure JVM sidecar) — JUTE validator + connectors  [unchanged]

   Persistence: SQLite (desktop/BYOK) ↔ PG/Aurora (VPC) behind the repository interface.
   Pinecone + ONNX models: the kb_rag retrieval backend (deferred WS-3b infra tier).
```

**What is new vs the live `:8002` backend (CONFIRMED from maps):** (a) the two LangGraph `StateGraph`s (`compliance_workflow.py:10`, `observation_workflow.py:4`) collapse to plain async functions; (b) `ComplianceCouncil.evaluate`'s 3-judge fan-out is rebuilt as DSPy modules but its `_apply_consensus` (`compliance_council.py:1853`) is **ported verbatim**; (c) every Mongo write (`compliance_workflow.py:1414-1435`, `observation_workflow.py:858`, `provenance.py:60`) routes through the repository interface to SQLite/PG; (d) Celery drivers (`compliance_tasks.py:111`, `observation_tasks.py:172`) are replaced by the in-process harness loop (`run_eval.py:101-152`).

---

## 2. SALVAGE — port-as-is enabling infra

The topology's "necessary enabling infra" maps exactly to the infra map's `salvage-port-asis` set.

| Asset | Source (CONFIRMED) | Why port-as-is |
|---|---|---|
| **Azure cross-provider adapter + client factory** | `app/services/llm_provider.py:1-148` | Infra-pure: grep for mongo/motor/celery/fastapi/redis/boto/pinecone/httpx imports returns nothing (EXIT=1 in map); imports only `openai` SDK + `app.config`. `get_sync/async_openai_client(purpose)` return `(client, model)` (`:97-118`, `:121-142`). `_resolve_model` maps purpose→deployment (`:38-80`). Module-scope `(kind,provider,purpose)` cache (`:35`), `reset_clients` for test flips (`:145`). Carries its own unit test `tests/services/test_llm_provider.py`. |
| **Config schema SUBSET** | `app/config.py` — `LITHRIM_LLM_PROVIDER:81`, 5 Azure deployment ids (`:82-86`, `:216-217`), `OPENAI_API_KEY:76`, `COMPLIANCE_COUNCIL_VERSION:211` | Port only these fields. **Do NOT drag** S3/Pinecone/LiveKit/HIPAA/Celery/playground fields (app-specific). Fix legacy naming: `APP_NAME='Velto Backend'`, DB name `'velto'` (`config.py:12,17`) — cosmetic but confuses a fresh host. |
| **ProvenanceStore interface (the persistence TEMPLATE, not the Mongo impl)** | `app/services/pipeline/provenance.py:25` Protocol (save/find_by_id/find_compliance_report_by_run_id); injected into `PipelineOrchestrator` (`orchestrator.py:201/217`) | The *Protocol shape* is salvage; the *MongoProvenanceStore impl* (`provenance.py:37`) is replaced. This is the exact repository abstraction WS-6d wants — already proven with an in-memory test double. |

**Tie to bench (CONFIRMED):** `config.py:208` cites `lithrim-bench docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md`; `config.py:213` pins bench commit `ffdd3f2`; `compliance_council.py:390` says its v2 trio is "Ported from lithrim-bench scripts/test_n12_trio_v3.py". The factory is already the seam the bench's `council_v2.py` plugs into (`council_v2.py:36` `pred.set_lm(lms[role])` binds each judge to its Azure deployment).

**Risk (INFERRED, infra map):** v2 reaches Mistral-Large-3 + Llama-4-Maverick by Azure deployment-id substitution on the `AzureOpenAI` SDK (`llm_provider.py:44-63`) — a documented-smoke assumption (comment `:44-46`, "2026-05-27 200 OK"), not a guaranteed SDK contract. v2 purposes `mistral_judge`/`meta_judge` HARD-require `LITHRIM_LLM_PROVIDER=azure` (`_resolve_model` raises on openai-direct, `:76-79`) — an openai-direct host silently degrades to the v1 monoculture trio.

---

## 3. REBUILD-ON-DSPY — per-judge prompts + taxonomy as DSPy-optimizable modules

**What gets rebuilt (the agents map's `recompose`/`rebuild` surface, the council map's *(a)+(c)*):** the per-judge LLM prompt-and-parse, scored by the bench by-construction packs. **Proven prior art exists** — this is not a blank slate.

**Prior art #1 — the DSPy council prototype (CONFIRMED this session):**
- `council_v2.py:4-6,23,28,36` — cross-provider trio (`risk_judge`=gpt-4.1, `policy_judge`=Mistral-Large-3, `faithfulness_judge`=Llama-4-Maverick), each bound to its own deployment via one Azure adapter, per-judge try/except so one provider failure is recorded-not-fatal. Mirrors backend `JUDGES_V2` (`compliance_council.py:472-497`).
- `council_dspy.py` — 3 `dspy.Predict` judges over `_JudgeSignature` (findings-first decision/violations/confidence/reason).
- **The ledger proving it works (CONFIRMED — 28 rows, `v2_runs.ndjson`):** modes `v3_grounded`=12, `v4_toolbox`=8, `v2_critique`=4. `smoke_result_v3_grounded.json:24-85` shows `clean_negative` council=reject → grounded=**APPROVE** (correct flip, recipe agrees); `inject_condition` stays reject with `ungrounded=['Diabetes mellitus type 2 (disorder)']` matching the injected post_value. `run_smoke_v4_toolbox.py` shows the prototype already consuming the *promoted* Router+compose_verdict.

**Prior art #2 — the verification toolbox's DSPy generator (CONFIRMED, WS-3a):**
- `verification/jute_dspy.py:130-217,333-418` — `score_template`/`bench_accept` is the metric (0 FP, 0 ERR, every structural defect BLOCKED); `make_bench_metric` gates optimizer demos on hard-accept; `build_generator` runs a seeded generate→test→refine loop scored against live `:3031`. This makes **the bench the acceptance oracle for tool authoring** — the exact pattern judge-prompt optimization follows.

**The rebuild map (INFERRED, agents + council maps):**
| Backend prompt-and-parse | → DSPy module | Scored by |
|---|---|---|
| `compliance_council.build_prompt` (`:517-788`) + 5 role prompts (`council_roles/*.txt`) + 23 flag defs (`safety_flags.py:37`, `get_flag_prompt_section :621`) | per-judge DSPy Signature + optimizer-owned prompt text | by-construction packs (`data/ontology/clinical_v1.json` 24 flags, recipe = label) |
| `run_confidence_gate` (`compliance_workflow.py:627`) gpt-4o-mini gate | a cheap DSPy gate signature | gate-can-only-approve invariant (see §5) |
| 4 LLM extractors: `intent_quality` hallucination-vs-KB, `safety` PII/HIPAA/PCI (`safety_agent/agent.py` 3 LLM calls :402/480/537), `sentiment` | DSPy extractor modules (removes ~600 lines of bespoke JSON-repair, agents map) | actual_flags multi-source union (memory `reference_eval_actual_flags_multisource`) |

**Do NOT DSPy-rebuild:** the tier/owner/veto math (that's §5). DSPy owns *prompt text + judge fan-out*; the *consensus arithmetic* stays ported. This is the hybrid resolved in §6.

---

## 4. RECOMPOSE-IN-PROCESS — LangGraph workflows + agents, and what changes when Mongo/Celery/web drop

**The LangGraph removability is CONFIRMED this session** (the strongest verified claim in this plan):
- Only import is `from langgraph.graph import END, StateGraph` (`compliance_workflow.py:10`, `observation_workflow.py:4`).
- API surface across both files: `add_node`×16, `add_conditional_edges`×14, `add_edge`×3, `set_entry_point`×2, `compile`×2, `ainvoke`×2 — **nothing else** (verified via `grep -hoE`).
- Graph-runtime features (`checkpointer|MemorySaver|SqliteSaver|interrupt(|Command(|add_messages`) across all of `app/`: **0 hits** (verified `wc -l` = 0).

**The recompose (INFERRED, workflow map's `disposition_rationale`):**
- Conditional edges → `if/await`. Error sink (`handle_error`, `compliance_workflow.py:1514`; single sink routing) → `try/except`. The near-linear chain `retrieve → prescreen → gate → [skip?] council → evidence → store` becomes one async function. The one fan-out (`run_parallel_analyses` `asyncio.gather`, `observation_workflow.py:570`) stays as-is. The single conditional skip (`_should_skip_council` `:851`) becomes one `if`.
- The threaded `ComplianceState` (32-field TypedDict, `:35-81`) and `ObservationState` (`:38-91`) stay as the in-memory field contract the DSPy pipeline must emit (verdict/confidence/consensus/final_verdict/guard_override/evidence_spans/failure_*).

**Agents (INFERRED, agents map):** the 6 KPI agents are plain async classes already (no Mongo/Azure/LangGraph imports — all coupling funnels through services). Recompose hoists them out of per-call re-instantiation (the workflow re-instantiates fresh at `observation_workflow.py:333/391/447/481/503/537/613` — a known cost the map flags). **Drop the dead `evaluation_agent`** (zero references, agents map). **Park the LiveKit `simulation_agent`** — it's a real-time voice sim, not a pipeline node; keep as a stable in-process service if live-call ingest is needed, otherwise out-of-scope for WS-6.

**Exactly what changes when Mongo/Celery/web scaffolding drops:**
| Dropped (infra map `drop-legacy`) | Replacement |
|---|---|
| `app/database.py` Motor singleton (`:18-22`); all `compliance_report.update_one`/`audit_item`/`low_confidence_queue` writes (`compliance_workflow.py:1414-1559`); `conversation_item.find_one` (`observation_workflow.py:355`) | repository interface → SQLite/PG (WS-6d). Council itself writes **nothing** (CONFIRMED 0 Mongo hits) — only the workflow's `store_report` did. |
| `app/celery_app.py` (Redis-bound); `compliance_tasks.py:111`, `observation_tasks.py:172` drivers | in-process harness loop (`run_eval.py:101-152`) calls the async pipeline directly |
| `app/tasks/_compat.py::run_async` asyncio/gevent shim (`:46-61`, consumed by ~9 tasks) | **deleted** — in-process host `await`s coroutines directly (infra map: "drop with Celery") |
| `app/main.py` FastAPI+CORS+30 routers+Mongo index bootstrap; `app/rate_limit.py` (Redis slowapi); `app/auth/*` (Mongo+FastAPI JWT/API-key) | the Python-Layer's own thin FastAPI surface (the §10 BFF contract); auth re-scoped to desktop/BYOK + VPC (not Mongo `api_keys` lookup) |

**Behavior-preservation contracts that MUST survive the recompose (INFERRED, workflow map `risks`):**
1. **Two-phase disposition** is load-bearing: preliminary in `run_council` (`:957`, no evidence) then recomputed in `extract_evidence` (`:1211`, with `evidence_spans` for soft-escalation). Preserve the ordering.
2. **Fatal vs non-fatal errors:** `check_hipaa_compliance` (`:746-751`) and `evaluate_artifacts` (`:1005-1009`) intentionally swallow errors ("optional"). The recompose must preserve which failures are fatal.
3. **Council concurrency:** keep the `COMPLIANCE_COUNCIL_MAX_CONCURRENT_LLM` semaphore (`compliance_council.py:57-60`) to avoid Azure rate-limit storms.
4. **Eval isolation:** `store_report` appends `::eval::<eval_run_id>` to `context_hash` (`:1371-1372`) for fresh per-eval upserts; persisted `kb_retrievals` is a 4-field summary, NOT the in-memory shape (memory `reference_pipeline_run_persistence_shape`). The repo impl must keep this.

---

## 5. PRESERVE-AS-IP — PORT not rewrite (the consensus IP the DSPy smoke deliberately dropped)

This is the heart of the topology spec's "losing the validated calibration/NKA/prompt IP is the chief risk" (`SPEC_PRODUCT_SERVICE_TOPOLOGY.md:65`). **CONFIRMED this session** that the DSPy prototype deliberately dropped it: `council_dspy.py:17-21` reads verbatim *"DELIBERATE SIMPLIFICATION: consensus here is plain WORST-OF ... The real `_apply_consensus` is evidence- and tier-based (Tier-1 never-events reject on a single owning judge, Tier-2 needs 2+ judges, PHI false-positive reclassification, ownership gating, a v2 llama-veto path, etc.). None of that is reproduced."*

**Port verbatim as a pure-Python module (CONFIRMED Mongo-free — 0 DB hits in `compliance_council.py`):**

| IP block | Source (CONFIRMED anchors) | Contract |
|---|---|---|
| `_apply_consensus` | `compliance_council.py:1853` (→ :2398) | per-judge findings collection + dedup; Tier-1 one-strike (owner OR ≥2 evidence-judges); Tier-2 needs 2+; PHI-FP suppression; per-pillar worst-of combine; majority + None-tolerant confidence; ALWAYS-applied artifact-BLOCK override |
| `_compose_council_verdict_v2` (llama-veto) | `compliance_council.py:1812` | if `faithfulness_judge`(Llama)==approve AND no other rejects → approve, else worst-of; gated OFF when `tier1_triggered` non-empty (safety floor) |
| `_worst_of_verdicts` | `compliance_council.py:1799` | strictest-wins floor (reject>needs_review>approve) |
| Tier/owner/pillar TABLES | `TIER_1_NEVER_EVENTS:176`, `TIER_2_HIGH_RISK`, `TIER_3_MEDIUM`, `KNOWN_TAXONOMY_CODES:279`, `_TIER1_OWNERS:232`, ARTIFACT/CONVERSATION/DUAL_PILLAR codes (`:288-326`) | these MUST travel WITH the consensus engine |
| NKA exception | `council_roles/faithfulness_judge.txt:1`, `risk_judge.txt:38`, `policy_judge.txt:1` + `compliance_council.py:1357` v2 NKA paragraph | HL7 AL1 "NKA/NKDA = no-known-allergies, do NOT flag FABRICATED_ALLERGY" |
| Defensive recompute (workflow-side) | `_recompute_consensus_from_council` (`compliance_workflow.py:2206`), `_recompute_final_verdict` (`:2281`) | **CRITICAL CONTRACT**: must mirror `_apply_consensus` exactly incl. BRS-3 None-confidence tolerance for Mistral. Port council + recompute *in lockstep*. |
| Confidence-gate safety policy | P0-3 artifact-guard (`:767-780`), FAST PATH (`:782-827`), hidden regex protocol checks (`:722-765`) | artifacts ALWAYS go to council; gate can ONLY approve; the regex checks (tool-call-without-identity, reschedule-without-preauth, clinical-ambiguity) live *inside the node* — easy to miss |

**Critical IP-port traps (INFERRED, council map `risks`):**
- **Tables are split across TWO files.** Tiers+owners+pillars live in `compliance_council.py`; flag prompt-text + FailureType live in `app/models/safety_flags.py`. A port that grabs only the file *named like* a taxonomy source (`safety_flags.py`) **silently loses Tier-1 owner-gating and pillar routing**. (Note: `app/services/safety_flags.py` does **not** exist — the real path is `app/models/`.)
- **Do NOT port from the bench mirror.** `lithrim_bench/runtime/council/compliance_council.py` is byte-identical *line count* (2733, CONFIRMED) but `diff` confirms it **DIFFERS** from backend (CONFIRMED exit=1 this session), and `taxonomy_snapshot.json` pins `source_commit ba84608` (CONFIRMED) vs backend `493b533`. The bench mirror is a **frozen WS-6 seed, stale**, not the SSOT. **Port from `lithrim-backend` @ `493b533`.**
- **v1 vs v2 diverges sharply at runtime** via `settings.COMPLIANCE_COUNCIL_VERSION`: logprob confidence override, llama-veto branch (`:2348`), None-tolerant averaging. `extract_verdict_confidence` returns None for Mistral by design and must NEVER be coerced to 1.0 (`:402-405`). Porting only one version, or hardcoding v2, changes verdicts.
- **`source_message_judge` is declared-but-not-running** (snapshot) yet still appears in several `_TIER1_OWNERS` sets (`:233-241`) and has a live prompt file. A naive port could re-activate a judge the production trio excludes. (Matches CLAUDE.md core invariant #4.)
- **Determinism seeding:** eval-mode uses per-(case,judge) SHA-256 seeds (`_eval_seed:63`); live uses constant seed=42; Arabic parse-fail retry switches to seed=43+frequency_penalty=0.5 (`:107-112`, memory `project_council_arabic_timeout`). A DSPy reimpl that ignores seeding breaks the harness's verdict-reproducibility signal.

---

## 6. HOW IT ALL TIES IN — one coherent narrative + the hybrid resolution

The user's brief — *"recompose the langraph based agentic workflows ... once we have rebuilt the council and taxonomy etc over here based on the work we did with dspying, tools etc, they all tie in"* — describes a flywheel that already has three of its four quadrants built in `lithrim-bench` (the bench-substrate map's `already-in-bench` disposition). WS-6 supplies the fourth.

**The narrative (CONFIRMED prior art in brackets):**
1. **The DSPy council prototype** proved the loop: council → critique → tool-grounded re-derivation produces *correct* verdict flips on by-construction cases [`smoke_result_v3_grounded.json:24-85` clean-negative reject→APPROVE; `v2_runs.ndjson` 28 rows]. It *motivated and seeded* the toolbox.
2. **The verification toolbox (WS-3a FLOOR)** extracted the prototype's hard-wired determinism contract into a promoted package: `InRowTool` (record-presence), `StructuralJute`/`JuteGen` (the structural FLOOR over `:3031`), and `Router.compose_verdict` (the false-negative guardrail — a flag is *never cleared by silence*, `router.py:55-109`; `conforms=None` never clears, `spec.py:5-15`). `run_smoke_v4_toolbox.py` shows the prototype re-consuming this promoted package.
3. **The harness grade→ground→RLVR loop** is the live spine [`run_eval.py:101-152`]: `grade` composes over the pipeline, `ground` runs the suppress registry (the **S-BS-7 zidovudine** confident-FP disproof, `grounding.py`) + the structural floor (PASS→BLOCK), then emits `build_correction`/`build_floor_correction` records projected to `corpus-row/1` — the append-only **data-lake north star** (`corpus.py:54-87`, `rollout_ref` sha256 back to the full per-judge rollout) that feeds an RLVR/fine-tuning flywheel. Verification-contract = the verifiable reward.
4. **This recomposed agentic layer (WS-6) closes the loop**: today `grade_live` reaches *out* to live `:8002` (`grade.py:119-126`); after WS-6c the same `grade` seam calls the **in-process** recomposed pipeline. The agentic workflows, the ported council, and the DSPy judges become the *thing being graded and ground* — inside the same process as the harness that grades them.

**The apparent tension — PORT-not-rewrite (council) vs rebuild-on-DSPy (judges) — resolves into ONE hybrid layered module:**

```
  Council.forward(context_payload):
    ┌─ REBUILD-ON-DSPY ──────────────────────────────────────────────┐
    │  N DSPy judge modules (council_v2.py pattern) fan out over the   │
    │  identical sanitized payload → each emits                        │
    │  {decision, findings[taxonomy_code+evidence_spans], confidence}  │
    │  ← prompt text + flag defs are DSPy-optimizable, scored by packs │
    └────────────────────────────────────────────────────────────────┘
                          │  per_judge list (EXACT shape pred.per_judge already produces)
                          ▼
    ┌─ PORT-NOT-REWRITE ─────────────────────────────────────────────┐
    │  _apply_consensus + Tier-1/2/3 + _TIER1_OWNERS + PHI-FP +        │
    │  worst-of pillar combine + artifact-BLOCK + llama-veto + NKA     │
    │  ← pure Python, ported verbatim from compliance_council.py       │
    │    :176-356 (tables) + :1798-2398 (consensus+veto)               │
    └────────────────────────────────────────────────────────────────┘
                          │
                          ▼  verdict dict (zero LLM/Mongo dep)
```

The seam is clean because the ported `_apply_consensus` takes *exactly* the `{decision, findings, confidence, evidence_spans}` per-judge dict shape that `council_v2.py`'s `pred.per_judge` already produces (council map: "takes a list of per-judge ... dicts ... and returns a verdict dict with zero LLM/Mongo dependency"). **DSPy owns the prompts; the tier math stays ported as the safety floor.** Optimizing a judge prompt can never weaken a Tier-1 never-event rule because the rule lives *below* the DSPy layer.

**The `taxonomy_snapshot.json` contract is the bench↔council coupling point** (CLAUDE.md: "the only coupling point to lithrim-backend"). It already encodes `KNOWN_TAXONOMY_CODES`, `tier1_owners`, `production_judges`, `declared_but_not_running=[source_message_judge]` — the owner-resident-judge invariant the harness lints against (CLAUDE.md invariant #4). **Re-snapshot via `scripts/snapshot_taxonomy.py --backend-path …` against `493b533` before the port** (current snapshot is stale at `ba84608`, CONFIRMED).

---

## 7. DEPENDENCY-ORDERED PHASES — mapped onto WS-6c..6e + NEW sub-phases

The topology spec defines WS-6c (port council) / WS-6d (persistence swap) / WS-6e (ETLP packaging). The agentic scope the user added (recompose LangGraph workflows + agents) requires **two new sub-phases**. Proposed insertion preserving the frozen-contract rule:

| Phase | Scope | Gates / gated-by | Dev-time `:8002` dependency during strangle |
|---|---|---|---|
| **WS-6b** *(this doc)* | Recomposition plan. Re-snapshot taxonomy @ `493b533`. **Decide the open questions in §8.** | Gated-by 6a (clean tree, done). Gates everything below. | — |
| **WS-6c** | **PORT v2 council Mongo-free** into `lithrim_bench/runtime/council/` (extends M1 v1→v2). PORT `_apply_consensus`+tables+veto+NKA verbatim (§5); re-derive from `493b533`, NOT the stale parked mirror. Wire the SALVAGED `llm_provider` factory + config subset (§2). | Gated-by 6b. Gates 6c-DSPy + 6d. **Frozen behind `run_eval.run`.** | Council now in-process; BFF re-points council capability off `:8002`. KB still hits `:8002`-kb path. |
| **WS-6c-DSPy** *(NEW)* | **Rebuild per-judge prompts + taxonomy as DSPy modules** (§3), wrapping the ported consensus (the §6 hybrid). Score via by-construction packs; reuse `jute_dspy` bench-accept metric pattern. Promote `council_v2.py` from worktree-reference to package. | Gated-by 6c (needs the ported consensus to wrap). Soft-gates the calibration story. | none new |
| **WS-6c-AGENTIC** *(NEW)* | **Recompose the LangGraph workflows** (§4): `compliance_workflow` + `observation_workflow` → straight-line async fns; preserve the 4 behavior contracts + the gate safety policy. **Recompose the 6 KPI agents** in-process (hoist instantiation); drop dead `evaluation_agent`; park LiveKit sim. | Gated-by 6c (the inner council it invokes must exist in-process first). Can run parallel with 6c-DSPy. | etlp-mapper `:3031` (structural, permanent sidecar). `evaluate_artifacts` keeps `:3031`. |
| **WS-6d** | **Persistence swap** — implement the repository interface (template = `ProvenanceStore` Protocol, §2) over SQLite(desktop)/PG(VPC). Carve `compliance_report` out of the provenance store (`provenance.py:119` leak). Add the missing eval-collection indexes. Route eval.py-equivalent `pipeline_runs` reads through `find_by_id`. **Mongo out.** | Gated-by 6c-AGENTIC (the recomposed pipeline is what writes through the repo). | **`:8002` fully strangled for council+persistence.** |
| **WS-6d-KB** *(NEW, optional / WS-3b-aligned)* | **Rebuild KB retrieval behind a `kb_rag` VerificationTool** (WS-3b map). `hipaa_retrieval` recomposed as a library behind the bench `kb_rag` slot (`spec.py:31` dangling constant); implement the missing `KbRagTool` (currently only in the worktree). Fix the stale `RetrievalMatch` import. | Gated-by 6c. Independent of 6d. Inherits Pinecone+Mongo+~1GB ONNX infra cost. | Pinecone (SaaS) + ONNX (local) as the retrieval backend. |
| **WS-6e** | **ETLP JVM sidecar packaging** — uberjar + JRE bundling (the packaging long pole, `SPEC_PRODUCT_SERVICE_TOPOLOGY.md:66`). Coordinate with shell WS-5e. | Independent of council track; can start anytime. | `:3031` becomes the bundled sidecar. |

**What gates what (summary):** 6b → 6c → {6c-DSPy ∥ 6c-AGENTIC} → 6d; 6d-KB hangs off 6c; 6e is orthogonal. The **frozen-contract rule** keeps all of this parallel-safe with WS-5 shell work — every phase swaps implementation behind `run_eval.run` / `report.composite` / the §10 BFF, never the signature (`SPEC_PRODUCT_SERVICE_TOPOLOGY.md:52`).

**What stays a dev-time `:8002` dependency through the strangle (CONFIRMED, grade.py:119-126):** `grade_live` POSTing `:8002 /v1/pipeline/evaluate` remains the *replay-baseline producer* until WS-6c-AGENTIC lands the in-process pipeline. The `grade_replay` path (`grade.py:40-127`, same `PipelineResult` shape, $0) means downstream stages are path-agnostic — the strangle is invisible to ground/report/RLVR.

---

## 8. RISKS + OPEN QUESTIONS (decide at WS-6b plan-review)

**Architectural risks:**
1. **LangGraph in-process vs compose-over-live (the central WS-6 tension).** Today the bench composes OVER live `:8002` (`grade.py`); WS-6c-AGENTIC pulls the LangGraph pipeline *in-process*. The recompose itself is low-risk (CONFIRMED: zero graph-runtime features, minimal API surface). The risk is **behavior drift in the 4 preservation contracts** (§4) + the **two-phase disposition ordering** (`:957` then `:1211`) — a subtle reorder silently changes verdicts. *Mitigation:* the by-construction packs + the `v2_runs.ndjson` ledger are the regression oracle; diff in-process verdicts against captured `:8002` replay baselines before re-pointing the BFF.
2. **S-BS-24 (RED backend) — honored, but a trap for the port.** The backend suite is RED pre-existing (`test_council_evidence_extraction.py:12` stale `RetrievalMatch`). **Do NOT treat green-backend as a port gate.** But also: do NOT "restore `RetrievalMatch`" — it was *renamed* to `HipaaRetrievalMatch` (`hipaa_retrieval.py:37`, CONFIRMED alive); fix the one stale test import if 6d-KB touches it (WS-3b map risk).
3. **Stale-source trap (§5).** Highest-consequence risk: porting from the parked bench mirror (CONFIRMED differs) or the stale snapshot (`ba84608`) instead of `493b533`. *Mitigation:* re-snapshot first; port from backend SSOT; pin the source commit in the WS-6c PR.
4. **Split-tables trap (§5).** Grabbing only `app/models/safety_flags.py` loses Tier-1 owner-gating. *Mitigation:* the port checklist must enumerate both files.
5. **Cost (memory `feedback_llm_cost_conscious`).** The DSPy judge-prompt optimization (WS-6c-DSPy) and any live `:8002`/Azure grading burn LLM spend. *Mitigation:* the harness replay path is $0 (`grade_replay`); do offline analysis on captured baselines first, batch-then-validate; the by-construction packs grade deterministically without re-running the council where possible. Verdict-floor + per-verdict cost discipline applies (memory `feedback_verdict_pricing_floor`).
6. **Calibration is REPORT-ONLY, not a gate** (`report.py:14-17,159-173`, bench map). The WS-0 baseline has only 2 non-null confidences (both 1.0). Do NOT promote `calibration_check` to a gate without preregistered thresholds (memory `project_val_r1_accuracy` — expanded golden cases need recalibration).
7. **The known unsafe-approve FN stays visible-not-fixed** (bench map, `run_smoke_v4_toolbox.py:25-31`): when the council emits only a *wrong-class* flag (FABRICATED_HISTORY for a hallucinated detail), the matched tool legitimately clears it and the verdict approves — `HALLUCINATED_DETAIL` is intentionally UNROUTED→UNRESOLVED. This is an upstream-attribution problem composition cannot solve. *Decision needed:* does WS-6 route `HALLUCINATED_DETAIL` to a transcript/record-RAG tool, or keep it visible-unrouted?

**Open questions for plan-review:**
- **Q1 (v1 vs v2 scope).** Topology spec says "the product wants v2." Port *both* v1 and v2 paths (they diverge sharply, §5) or commit to v2-only? v2 HARD-requires Azure (`_resolve_model:76-79`) — does the desktop/BYOK tier have Azure multi-deployment access, or does BYOK fall back to v1 monoculture?
- **Q2 (Azure deployment-id substitution).** Is the Mistral/Llama-via-deployment-id assumption (`llm_provider.py:44-63`, a smoke-only "200 OK") verified against the *target* Azure AI Foundry resource for the product, not just dev? (Infra map risk.)
- **Q3 (DSPy module boundary).** Does WS-6c-DSPy rebuild *all* per-judge prompts at once, or start with the one judge whose prompt-optimization the packs can score most cleanly (lowest-risk first)? The hybrid (§6) allows incremental — ported consensus wraps DSPy or non-DSPy judges identically.
- **Q4 (agents scope).** Confirm: drop `evaluation_agent` (dead), park LiveKit `simulation_agent` (out-of-scope for the verification pipeline). Is live-call ingest a WS-6 requirement or deferred?
- **Q5 (6d-KB timing).** Is `kb_rag`/RecordRag (deferred WS-3b, ~1GB ONNX + Pinecone + Mongo infra) in WS-6 scope, or does the recomposed pipeline run with the structural floor + suppress registry only (the committed `clinical_v1.json` declares NO structural-floor contract, only one `presence_check` — `clinical_v1.json:385-418`, so a recompose relying on the floor must *author* floor `VerificationContractDecl`s)?
- **Q6 (frozen-contract surface).** Confirm the §10 v1 BFF contract is frozen and documented before WS-6c starts, so the in-process swap is invisible to WS-5 (the topology spec asserts this but the §10 contract doc was not in scope for this audit).

---

**Files most relevant to WS-6c execution (all absolute):**
- PORT-as-IP source (SSOT, port from here): `/Users/aregee/Workspace/github.com/lithrim-backend/app/services/compliance_council.py` (tables :176-356, consensus+veto :1798-2398), `/Users/aregee/Workspace/github.com/lithrim-backend/app/models/safety_flags.py`, `/Users/aregee/Workspace/github.com/lithrim-backend/app/prompts/council_roles/*.txt`
- Workflow-side recompute (port in lockstep): `/Users/aregee/Workspace/github.com/lithrim-backend/app/workflows/compliance_workflow.py` (:2206, :2281)
- SALVAGE infra: `/Users/aregee/Workspace/github.com/lithrim-backend/app/services/llm_provider.py`, `/Users/aregee/Workspace/github.com/lithrim-backend/app/config.py`, `/Users/aregee/Workspace/github.com/lithrim-backend/app/services/pipeline/provenance.py`
- RECOMPOSE source: `/Users/aregee/Workspace/github.com/lithrim-backend/app/workflows/observation_workflow.py`, `/Users/aregee/Workspace/github.com/lithrim-backend/app/agents/`
- DSPy prior art (reference, NOT import — worktree/throwaway): `/Users/aregee/Workspace/github.com/lithrim-bench/.claude/worktrees/agent-adefc36309f77ed1b/experiments/dspy_council_smoke/council_v2.py`, `council_dspy.py`, `v2_runs.ndjson`, `smoke_result_v3_grounded.json`
- Recompose TARGET (bench): `/Users/aregee/Workspace/github.com/lithrim-bench/lithrim_bench/runtime/council/` (parked seed — stale, re-derive), `/Users/aregee/Workspace/github.com/lithrim-bench/lithrim_bench/verification/` (toolbox), `/Users/aregee/Workspace/github.com/lithrim-bench/lithrim_bench/harness/` (grade-ground loop), `/Users/aregee/Workspace/github.com/lithrim-bench/scripts/run_eval.py`
- Frozen contract + frame: `/Users/aregee/Workspace/github.com/lithrim-bench/docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md`, `/Users/aregee/Workspace/github.com/lithrim-bench/docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md`
- Re-snapshot before port: `/Users/aregee/Workspace/github.com/lithrim-bench/scripts/snapshot_taxonomy.py`, `/Users/aregee/Workspace/github.com/lithrim-bench/taxonomy/taxonomy_snapshot.json` (re-snapshotted @ `493b533`, 2026-06-01)

---

## Ratification (2026-06-01) — §8 open questions RESOLVED

WS-6b ratified (monitor + user). The 6 open questions are locked:

- **Q1 (council version) → v2-ONLY (Azure trio).** Port the cross-provider v2 (gpt-4.1 + Mistral + Llama via deployment-id); drop the v1 code path. **Makes Q2 load-bearing:** the product's target Azure AI Foundry resource MUST host all three deployments. v2-only fixes the recomposed council's production trio as `risk/policy/faithfulness_judge` (see S-BS-30).
- **Q2 (Azure deployment-id substitution) → ✅ VERIFIED 2026-06-01 (user).** The product's target Azure resource hosts all three v2 deployments (gpt-4.1 + Mistral + Llama) and they are accessible. The deployment-id substitution route is confirmed against the product resource (not just dev), so **v2-only is fully unblocked on the Azure-access front.**
- **Q3 (DSPy judge rollout) → incremental** (one judge first; the §6 hybrid wraps DSPy or non-DSPy judges identically). Final call at the WS-6c-DSPy plan-review.
- **Q4 (agents scope) → recompose the 6 KPI agents; DROP the dead `evaluation_agent`; PARK the LiveKit `simulation_agent`** (live-call/voice ingest out of WS-6).
- **Q5 (KB/RAG) → DEFER to WS-6d-KB.** WS-6 core runs on the structural floor + suppress registry; author floor `VerificationContractDecl`s in the ontology (clinical_v1 declares none today).
- **Q6 (§10 BFF contract freeze) → already satisfied** (ratified at WS-5-BFF, extended at WS-5d). Port behind `run_eval.run` / `report.composite` / §10.

**Taxonomy re-snapshot DONE + verified.** `taxonomy_snapshot.json` re-stamped `ba84608`→`493b533`. **No council-taxonomy drift:** `TIER_1/2/3` + `tier1_owners` + `production_judges` + `declared_but_not_running` all set-identical (re-sorted only); `structural_codes` (5) preserved. Admissibility lint GREEN (`examples/proof_case.jsonl` 7/7 + 5 scribe packs). Two `snapshot_taxonomy.py` bugs fixed en route: the `sys.modules`/`exec_module` import crash + the lossy `structural_codes` drop. New seam **S-BS-30**: `production_judges` is hardcoded `policy/risk/behavior_judge` but the v2 trio is `risk/policy/faithfulness_judge` — reconcile at WS-6c (derive `production_judges` from the v2 council config, not hardcode).

**Next:** `/devloop-expand-driver bench-salvage WS-6c` (council PORT, v2-only) → 6c-DSPy ∥ 6c-AGENTIC → 6d (+6d-KB) → 6e.

---

## Amendment (2026-06-02) — WS-6c-AGENTIC re-scope vs §4/§7 (M1-spine reality)

§4 and the §7 `WS-6c-AGENTIC` row describe "recompose `compliance_workflow` → straight-line async fns" as **future** work. Re-grepping at WS-6c-AGENTIC authoring (2026-06-02) shows that is **already built** as the parked **M1 in-process spine** (`8f9beae`, "park 2026-05-29 in-process salvage (M1 spine) for WS-6"):

- `lithrim_bench/runtime/pipeline/orchestrator.py:187` — `PipelineOrchestrator.evaluate() -> PipelineResult` (the straight-line async compliance recompose).
- `lithrim_bench/runtime/pipeline/stages.py` — the recomposed stages; `:28` imports the ported `..council.compliance_council`.
- `lithrim_bench/backends/local_pipeline.py:42` — `LocalPipelineBackend` (runs the orchestrator in-process; M1 docstring pins `COMPLIANCE_COUNCIL_VERSION=v1`, structural/artifact skipped, `NoOpProvenanceStore`, retrieval stubbed).

**Consequent re-scope (monitor+user, 2026-06-02):**
- **`WS-6c-AGENTIC` = the compliance grade-wire milestone**, NOT a greenfield recompose: D0 S-BS-31 fix (option (a) reassign-by-domain) + upgrade the M1 spine **v1→v2 trio** + verify the §4/§5 behavior contracts survive in the existing orchestrator + **wire the in-process council into the grade seam** (`grade_inprocess` behind the frozen `grade.py`/`run_eval.run`/`report.composite` seam) so the council scores real cases for the first time. Regression oracle = diff in-process v2 verdicts vs the captured `:8002` replay baselines (`tests/fixtures/ws0/baseline.*.json`).
- **The observation/KPI half of the §7 AGENTIC row is split to a new `WS-6c-OBS` phase** (recompose `observation_workflow` + the 6 KPI agents; greenfield — grep of the agent classes across `lithrim_bench/` = 0 hits; not in the compliance grade path).

**Two citation corrections to §4 (re-grepped on `lithrim-backend@mvp-ready` 2026-06-02):**
1. **§4 contract-2 node names are STALE.** `check_hipaa_compliance` (`:746-751`) and `evaluate_artifacts` (`:1005-1009`) do **not** exist. `compliance_workflow.py` has **7 nodes**: `retrieve_context, run_safety_prescreening, run_confidence_gate, run_council` (`:859`), `extract_evidence` (`:1034`), `store_report` (`:1286`), `handle_error` (`:1514`). The fatal/non-fatal "swallow-errors" contract must be re-derived from these (best-effort: HIPAA retrieval in `retrieve_context`, artifact eval; fatal → `handle_error`).
2. **§4 "6 KPI agents" = 7 instantiated.** `observation_workflow.py` instantiates `transcription + 6 KPI` (`:333/391/447/481/503/537/613`). `evaluation_agent` is dead (drop), `simulation_agent` is a separate LiveKit flow (park). Confirm the recompose set at WS-6c-OBS plan-review.