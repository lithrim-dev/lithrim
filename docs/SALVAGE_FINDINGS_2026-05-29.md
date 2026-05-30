# Lithrim Bench — Salvage Findings & Composition Spec
> What to copy from where to compose the shippable Bench product, and what the acceptance test is. Evidence is `file:line`; load-bearing claims tagged CONFIRMED / INFERRED / HYPOTHESIS per the diagnose-before-edit gate.

**Date:** 2026-05-29 · **Status:** findings (no code committed beyond the vendored council) · **Plan source:** `~/.claude/plans/toasty-twirling-forest.md`

---

## Executive Summary

Bench is the **core, downloadable product** (not a managed SaaS — the founder will not custody customer data; that is the trust wedge). The build strategy is **salvage and compose**: copy the relevant modules out of the existing repos into one shippable product hosted in `lithrim-bench`, rather than refactoring the repos in place. The **acceptance test is dogfooding our own paper**: reproduce the paper-authoring eval-run findings (LLM-judge council + structural validators) on the composed local stack.

The central finding: the product the founder describes already exists, but **latent and split across repos**, and the surrounding engine is already **separable services**. So the work is *unify + data-drive + swap cloud deps (Pinecone/Mongo) for local (local-vector/SQLite)*, not greenfield. The product's IP is the **SME-Question Ontology**, which today is hardcoded in three disconnected places.

---

## Scope & Methodology

Surveyed all 16 repos under `~/Workspace/github.com`. Traced, with `file:line` evidence, the verification data flow, the analyze + audio ingestion, the eval/promotion/compare loop, the offline/packaging surface, and the council I/O contract. The vendored council was the only code produced (imports verified). Everything else is documented, not built.

---

## Findings

### F1. Product framing — the intelligence layer (CONFIRMED)

Bench's IP is the **SME-Question Ontology**: the questions a domain expert asks at each process gate. Each question does triple duty — (1) shapes the judge prompt, (2) carries a per-payload KB **retrieval policy** (namespace + filters + top_k), (3) is a **reporting dimension**. Domain experts author the questions; engineers do not.

This already exists but is **latent and hardcoded across three places**:
- **The questions** = `KEY QUESTIONS TO ANSWER` baked into role prompts: `lithrim-backend/app/prompts/council_roles/{policy,risk,faithfulness}_judge.txt`, assembled in `compliance_council.py:517` (`build_prompt`) + `models/safety_flags.py` (`get_flag_prompt_section`).
- **The retrieval** = generic per `context_kind`, not per-question: `pipeline/retrieval.py:368-371` (fixed namespaces), `:49-51` (fixed top_k); metadata filters supported but unused (`hipaa_retrieval.py:102-110`); only a 1-entry seed `_FAILURE_TO_CHUNK` (`compliance_council.py:354`). Judges are **single-shot, no tool-use** (`_chat_completion_with_retry`, `compliance_council.py:86-147`).
- **The reporting** = 4 hardcoded Reliability-Contract dimensions (Identity Verification / PHI Boundary / Escalation / Scope Safety) via `SAFETY_FLAG_TO_PILLAR` (`agent_reliability_service.py:16-39`, weights/policy `:41-67`) + `failure_clustering.py:136-212,426-506`.

Two-layer taxonomy (CONFIRMED, `LITHRIM_SSOT.md:15-24`): the 4 verification **pillars** (Faithfulness/Completeness/Safety/Structural) are distinct from the 4 reliability **dimensions**; the Safety pillar's flags feed the dimensions via the flag→pillar map.

### F2. The product loop (CONFIRMED)

`observe -> judge -> promote -> calibrate -> re-run -> diff`:
1. **Observe** — analyze / analyzeWithAudio ingests a conversation, produces artifacts + signals.
2. **Judge** — council + KB + ontology produce a verdict.
3. **Promote** — an observed case becomes an eval-pack case (analyze→eval); council verdict is the expected label (SME can correct).
4. **Eval harness** — run the pack N times, score per question/dimension.
5. **Calibrate** — improve/tighten or loosen the SME questions; the intentionally-miscalibrated start is the teaching moment.
6. **Re-run + diff** — Compare Runs shows improved/regressed.

Key unifier (CONFIRMED): the internal eval runner `tasks/eval_runner_tasks.py` already invokes `ObservationWorkflow` per case, so **the eval harness is the analyze flow looped over pack cases**. Submitters into the analyze front door: SDK, observability imports (Arize/LangSmith), the demo scribe voice agent (live), and the eval/paper harness.

### F3. Architecture & the one engine gap (CONFIRMED)

- **Consolidated Clojure server** (~60-80% exists): Jute mappings + AI copilot `POST /mappings/generate` (`etlp-mapper` `copilot/engine.clj`, `llm/client.clj`, azure/anthropic BYOK) + ETLP processor trigger (`etlp-base` EtlpSource/EtlpDestination protocols + integrant; CLI today, HTTP trigger is net-new) + KB→embeddings populate (`lithrim-rag-via-etlp`: source→chunk→ONNX mpnet+SPLADE→Jute→destination; one 12-key canonical record + per-corpus extras; HIPAA parity rtol 1e-5). `jute.clj` is GraalVM-safe (compile-time macros, no runtime eval). All Clojure projects have `:uberjar` profiles.
- **Slim Python orchestrator**: the council is **Mongo-free** and pure+LLM; ontology + judge config + results target **SQLite**.
- **The one consistent gap: a LOCAL vector store.** Everything targets Pinecone (`clinical_kb_service.py:70-77`, `config.py:121-127`, 26 files). `sqlite-vec` is blocked because **neither `python3` (3.12.8) nor `debuglithrim` (3.10.15) has `enable_load_extension`** (CONFIRMED — `AttributeError`, compiled without it). Mitigation: the Phase-0 spike uses **numpy brute-force** over the existing `lithrim-rag-via-etlp/reports/{hipaa,clinical,hl7v2,medication}/receipts-*.jsonl` (vectors already present); productized local vector becomes a later choice (apsw / LanceDB / Clojure-side `xerial sqlite-jdbc`, which does support extensions).

### F4. Council I/O contract (CONFIRMED, pinned this session)

INPUT — `ComplianceCouncil.evaluate(context_payload, *, context_kind="transcript", gate_mode=False, case_id=None)`. The `context_payload` keys read anywhere in the council are: `artifacts` (list of `{type, target_system, content}`), `agent_metadata` (`.category` selects the **scribe** prompt branch at `build_prompt` `:645`), `call_context` (**the transcript lives at `call_context.transcript` / `.raw_transcript`**, read in `_prepare_full_analysis_payload` `:1147-1148`), `retrieval.matches`, `clinical_context`, `safety_prescreening`, `organization_id`, `conversation_item_id`. **There is no top-level `transcript` key** (a naive assumption would yield a transcript-less prompt and a wasted paid run).

OUTPUT — `evaluate()` returns `{consensus, models, risk_determinations, evidence_summary}` (`:2728-2732`). `consensus` (`_apply_consensus`, `:2388-2398`) = `{decision: approve|needs_review|reject, conversation_verdict, artifact_verdict: PASS|WARN|BLOCK, confidence, consensus(bool), uncertainty, reason, decision_counts, evidence_summary}`. Flag codes = keys of `consensus.evidence_summary.violation_judges`. Per-judge output from `models[]` (`_normalize_result`, `:1549-1569`): each `{model, provider, decision, confidence, violations_found, findings, ...}`. v1 council = 3 judges (policy/risk/behavior, same model, `:499-503`); v2 = cross-provider (risk gpt-4.1 / policy mistral / faithfulness llama, `:472-497`) and requires Azure. BYOK provider via `LITHRIM_LLM_PROVIDER=openai|azure` (`config.py:81`, `llm_provider.py:38-146`).

### F5. Offline / packaging surface (CONFIRMED)

Hard cloud couplings on the verify path: Pinecone (no local fallback), council LLM (OpenAI/Azure only, no local switch), MongoDB (Motor only, `database.py:8-21`, no SQLite), Redis (Celery, `celery_app.py:12-16`). Already offline-capable: ONNX embeddings (`hipaa_embeddings.py`) and a local Whisper path. `docker-compose.yml` defines only Redis; Mongo is brew, MinIO a container. The sync `/v1/pipeline/evaluate` (`routes/pipeline.py:3`, Lane 1) and `/v1/validate-artifact` (`routes/validate.py:142`) bypass Celery, so the analyze workflow can run **in-process** via its async entry (`ObservationWorkflow.process()`); Celery only adds dispatch/retries.

### F6. Deployment topology — sidecar == container (INFERRED from the service shapes)

Both runtimes are HTTP/WSS servers, packaged once, deployed two ways. **Desktop (download):** Tauri/launcher bundles them as **sidecars** (`externalBin`) on localhost; Python = FastAPI/uvicorn (PyInstaller or bundled venv), Clojure = uberjar on a bundled JRE; state = local SQLite + local vector. **Cloud (licensed):** same services as **container images on ACA/ECS**; served UI + SDK + integrations point at their URLs; Clojure ingestion/ETLP and the Python council scale independently (the "fan out"); state = managed store + served vector. One artifact serves both because the UI is a pure HTTP/WSS client (env base URL) and **state is the swappable boundary**. The salvage exposes the core BOTH as a library (eval/paper test, in-process) AND as the FastAPI service (product runtime).

---

## Salvage Map (source → product)

| Cluster | Source (lithrim-backend unless noted) | Notes |
|---|---|---|
| **Council** (DONE) | `services/compliance_council.py`, `llm_provider.py`, `phi_redaction.py`, `models/safety_flags.py`, `config.py`, `prompts/council_roles/*` | Vendored to `lithrim_bench/runtime/council/` with import-path rewrites + `_compat.py` stub + `_ROLE_PROMPTS_DIR` fix. **Imports clean in `debuglithrim` (`IMPORT OK: ComplianceCouncil`).** |
| **Analyze flow** (~28 modules) | `workflows/observation_workflow.py` + `compliance_workflow.py`; `tasks/observation_tasks.py` (strip Celery); `agents/{intent_quality,sentiment,safety,technical_metrics,audio_analysis,kpi_aggregation}_agent/`; `services/{artifact_evaluator,compliance_guard,hipaa_retrieval,hipaa_embeddings,evidence_extraction,failure_clustering,transcript_parser,gemini_service,s3_service}`; `models/{call_kpi,compliance_report,conversation_item,conversation_session,base}` | Run in-process (no Celery). intent/sentiment/safety call **Google Gemini** (a second provider). 4 Mongo collections → SQLite: `conversation_item`, `conversation_session`, `call_kpi`, `compliance_report` (~14 writes). |
| **analyzeWithAudio** | `agents/transcription_agent/*` (local `openai-whisper` loader is **commented out**, `transcription_service.py:44-75`), `agents/audio_analysis_agent/*` (pyannote diarization + turn/latency metrics, `analyze_audio` node `observation_workflow.py:381-421`); SDK `lithrim-sdk/lithrim/async_client.py:529-652` | Offline deps ~1.1GB: openai-whisper (+~140MB base), pyannote.audio (+~500MB, HF token), torch-cpu (~400MB), ffmpeg. 3 pre-vendor fixes: enable local whisper loader; fix `audio_bytes` use-after-delete (`~:340/:393`); add `TRANSCRIPTION_PROVIDER=local|cloud`. |
| **Eval / promote / compare** | `routes/{eval,eval_external,admin_eval,scenarios}.py`; `models/{eval_run,eval_case,eval_pack,scenario}.py`; `services/{eval_comparison,eval_finalization,eval_promote_flags,eval_case_builder}.py`; `tasks/{eval_runner_tasks,eval_external_results_task}.py`; `schemas/eval.py`; bench `analysis.py` + `eval_runner.py` | Promote: `routes/eval.py:1077-1280`, expected_verdict = override → `report.verdict` → `needs_review`, flags captured from report. Compare: `eval_comparison_service.py:98-290` (regressions/improvements). Golden (JSONL) vs Promoted (Mongo+S3). `analysis.py` = verdict-instability, false-block rate, Fleiss kappa, bootstrap CI. |
| **Reporting / ontology target** | `agent_reliability_service.py`, `failure_clustering.py`, `routes/audit.py:506-544` (scorecard), `schemas/audit.py` | Data-drive the hardcoded dims into the SME-question ontology; Compare Runs already provides the before/after diff. |
| **KB ingest + local vector** | `lithrim-rag-via-etlp/src/**` + templates; **NEW** local-vector destination | Clojure/ETLP; ONNX local; gap = local vector dest. |
| **Copilot + mappings** | `etlp-mapper` `copilot/engine.clj`, `llm/client.clj`, `handler/mappings.clj`; `jute.clj` | English→Jute; GraalVM-safe. |
| **UI** (fresh build, NOT code-salvaged) | scaffold from `mapify-io` (Vite+React+TS+Tailwind+shadcn + its Jute/copilot UI); theme from `lithrim-ui` / `lithrim.com` (`v0-lithrim-landing-page`) | `lithrim-ui` is behavior reference only (`ConversationDetail.jsx`, `AuditViewMultiArtifactPanel.jsx`, `/demo` offline fixtures, `onboarding/welcome.jsx` is a generic stepper, not the journey; no chat/copilot component exists). |

Pack under test: `out/scribe_v1.jsonl` (30 cases); 5 packs in `packs.py:54-93`; taxonomy = 24 codes (`taxonomy/taxonomy_snapshot.json`). The scribe pack is semantic-only by construction, so structural validation is deferrable.

---

## Recommendations (sequencing)

- **M1 (spine, data-layer-independent):** run one `scribe_v1` case through the council in-process via a new `LocalCouncilBackend` (or the salvaged orchestrator) and the existing `eval_runner` (writes NDJSON, not Mongo); BYOK OpenAI `v1`; reproduce the recorded baseline. This is the paper test on the shipped path. The council is already vendored; the remaining piece is the backend that builds the `context_payload` (transcript at `call_context.transcript`, `agent_metadata.category="scribe"`, `artifacts`) and maps the consensus to `BackendVerdict`.
- **Phase 1:** SQLite document-store + the SME-Question Ontology (the 3 bindings); data-drive the hardcoded council constants + reliability dims.
- **Phase 2:** consolidated Clojure server (uberjar) + local vector destination + KB ingest.
- **Phase 3:** desktop shell + the calibration journey UI (TS+Tailwind from mapify-io) + the demo voice agent.
- **Phase 4:** packaging/installer + licensed-production separability.

---

## Decisions (flag-if-wrong) & Open Questions

1. **SQLite data layer [OPEN]:** Mongo-shaped **document shim** (vendored code runs with import-path rewrites only; swaps back to Mongo for cloud) vs **relational tables** (queryable for reporting, but rewrites every DB call). Recommended: document shim, add indexed columns for reporting later.
2. **Audio deferred to M2** (~1.1GB whisper/pyannote; scribe pack is text+artifact).
3. **Gemini signal-agents stubbed in M1** (they feed KPI signals, not the council verdict the paper measures); routed through BYOK provider in M3.
4. **Bundle = uberjar + JRE + PyInstaller** (GraalVM native-image later; instaparse needs reflection config).
5. **Mongo→SQLite only on the slim path**, not the whole backend; **scribe-first**.
6. **Local vector = numpy brute-force for the spike**; productized store choice (sqlite-vec via apsw / LanceDB / Qdrant / Clojure-side) deferred.

---

## References

- Plan: `~/.claude/plans/toasty-twirling-forest.md` (sections 1-12)
- Council contract: `lithrim-backend/app/services/compliance_council.py` (mvp-ready branch)
- Sync verify path: `lithrim-backend/app/routes/pipeline.py`, `routes/validate.py`
- Eval loop: `lithrim-backend/app/routes/eval.py`, `services/eval_comparison_service.py`; `lithrim-bench/lithrim_bench/{eval_runner,analysis}.py`
- KB ingest: `lithrim-rag-via-etlp/src/**`; copilot: `etlp-mapper/src/etlp_mapper/copilot/engine.clj`
- Vendored council: `lithrim-bench/lithrim_bench/runtime/council/`
- Related: `docs/LITHRIM_BENCH_PRODUCT_SPEC.md`, `docs/PAPER_OUTLINE.md`, `docs/ARCHITECTURE.md`

---

## The Bench Journey (final, end-to-end)

Reconciles the original handoff's 12-step onboarding with the product loop (F2), the ontology (F1),
and the salvage map. **Reuse** = exists to salvage; **Net-new** = must be built.

**A. Install & configure**
1. Download + run Bench — the shell spawns the Python + Clojure **sidecars**; local SQLite + local
   vector (F6). In licensed prod, the UI instead points at the ACA/ECS services. *(Net-new: shell/packaging; Reuse: the services.)*
2. Paste **BYOK** LLM key. *(Reuse: `llm_provider` provider switch, `config`.)*
3. Pick pack `scribe_v1` + agent type **Scribe**, configure agent meta. *(Reuse: `packs.py` `scribe_v1`, `out/scribe_v1.jsonl`; Net-new: pack/agent picker UI.)*

**B. First observation (the "taste")**
4. A clean **Scribe Exchange** — audio + transcript + the generated artifact (SOAP / FHIR
   DocumentReference), **no badges yet**. Source = the demo scribe voice agent (live), a pack case,
   or an SDK-submitted conversation. *(Reuse: `ConversationDetail` panels as behavior reference; Net-new: TS+Tailwind reimplementation + the demo voice agent.)*
5. Click **Verify** → the in-process analyze flow runs (transcript/audio → signals → council + KB +
   ontology → verdict); micro-interactions animate the 4 badges (Faithfulness/Completeness/Safety/
   Structural) + verdict + confidence. First time the user sees verification. *(Reuse: `observation_workflow` + council; Net-new: the verify micro-interaction UI.)*

**C. The miscalibration reveal (the product moment)**
6. The full scribe evalpack — multiple cases, results **intentionally miscalibrated** (overly
   lenient or strict). The user's task is to calibrate. *(Net-new: seed the deliberately mis-tuned start — knob = `tuned_mock` + the ontology defaults.)*
7. Open a finding → the **judge council** (RISK/POLICY/FAITHFULNESS) + audit/provenance chain + the
   **SME question** behind it and its retrieval policy (which KB chunk grounded it). *(Reuse: `AuditViewMultiArtifactPanel` behavior, `evidence_summary.violation_judges`; Net-new: surface the question + policy.)*

**D. Calibrate (the loop's knob)**
8. **Edit the ontology** — improve/tighten or loosen the SME questions, add a knowledge base, adjust
   judge prompts/policies — fronted by the **conversational/generative agent** (plain English → the
   generated Jute conditional / retrieval policy / question). *(Net-new: the chat/generative UI — none exists in `lithrim-ui`; Reuse: `etlp-mapper` copilot `/mappings/generate`, `jute.clj`.)*
9. **Promote** an interesting observed case into the eval pack — the verdict becomes the expected
   label, SME-editable. *(Reuse: `routes/eval.py` promote-to-eval-case.)*

**E. Re-run + diff (close the loop)**
10. **Re-run** the pack → the eval harness scores it → **Compare Runs** shows the before/after diff
    (improved/regressed cases, verdict-accuracy delta, false-block rate). Calibration becomes
    tangible. *(Reuse: `eval_runner` + `analysis.py` + `eval_comparison_service`; Net-new: the diff view UI.)*
11. The **reporting dimensions** (the question-clusters) show higher-order performance. *(Reuse: `agent_reliability_service` + scorecard, made data-driven.)*

**F. Scale ingestion**
12. **Load more conversations** — SDK push, observability import (Arize/LangSmith), the demo voice
    agent, or the paper methodology. All hit the same **analyze front door** → the loop. *(Reuse: the analyze API contract + SDK; Net-new: the Arize importer.)*

**Net-new for the journey (everything else is salvage):** the journey-mode UI (TS+Tailwind+shadcn
from mapify-io), the conversational/generative authoring agent, the intentional-miscalibration
seeding, the demo scribe voice agent, and the observability importers. The verify path, council,
audit/provenance, promotion, eval scoring, and Compare-Runs diff all exist to salvage.

**Acceptance restated:** the journey is "real" when steps 5/10 run on the salvaged, in-process
analyze→council→eval path (not fixtures) and reproduce our own paper eval-run findings.
