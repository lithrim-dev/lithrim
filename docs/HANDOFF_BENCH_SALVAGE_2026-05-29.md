# HANDOFF: Lithrim Bench Salvage — M1 spine proven (2026-05-29)

> The salvaged compliance council now runs **fully in-process** (no Mongo / Pinecone / Celery /
> etlp-mapper) and reproduced a `scribe_v1` verdict end to end with a BYOK Azure key.
> **Plan:** `~/.claude/plans/toasty-twirling-forest.md` · **Findings (file:line evidence):**
> `docs/SALVAGE_FINDINGS_2026-05-29.md`

---

## TL;DR

- **Strategy:** salvage-and-compose (copy modules out of the repos into one shippable product hosted
  in `lithrim-bench`), not refactor-in-place. **Acceptance test = reproduce our own paper eval-run
  findings on the local stack.**
- **Done this session:** vendored the council + the sync-`/v1/pipeline/evaluate` orchestrator path
  into `lithrim_bench/runtime/`, wrote an in-process `LocalPipelineBackend`, made it scribe-aware,
  and ran one `scribe_v1` case live.
- **Result (CONFIRMED):** `reject == reject` (verdict match 1/1), `FABRICATED_HISTORY` caught.
  The council also emitted `MEDICATION_NOT_IN_TRANSCRIPT`, which is a **confirmed false positive**
  (the med is plainly in the transcript) — a real calibration target, i.e. the product thesis on
  case 1. **M1 spine proven.**

---

## Context (one paragraph)

Bench is the **core, downloadable product** (not a managed SaaS — the founder won't custody customer
data; that's the trust wedge). Its IP is the **SME-Question Ontology** (questions an SME asks at each
process gate; each does triple duty: shape the judge prompt, carry a per-payload KB retrieval policy,
be a reporting dimension), which today is **latent and hardcoded in three places**. The build is
*unify + data-drive + swap cloud deps (Pinecone/Mongo) for local (local-vector/SQLite)*, not
greenfield. Full framing + `file:line` evidence in `docs/SALVAGE_FINDINGS_2026-05-29.md` and the plan.

---

## What was done this session

1. **Investigation + plan.** Surveyed all 16 repos; corrected the original handoff's stack claim
   (the Hub backend is **Python/FastAPI/Celery/Mongo**, not Clojure; the Clojure piece is
   `etlp-mapper`). Produced the plan (`toasty-twirling-forest.md`, §1-12) and the findings doc:
   the intelligence-layer/ontology framing, the product loop (`observe → judge → promote → calibrate
   → re-run → diff`), the analyze + analyzeWithAudio ingestion front door, and the
   eval/promote/compare loop — all mapped with evidence.
2. **Code (the real deliverable).** Vendored cluster A (council) + cluster B (orchestrator path) into
   `lithrim_bench/runtime/`, rewrote imports, stubbed the cloud deps, wrote the in-process backend +
   run script, and added a scribe-aware fix. Then ran 1 case live to prove the spine.

---

## Code produced / modified (file inventory)

**Vendored council — `lithrim_bench/runtime/council/`** (imports clean in `debuglithrim`):
- `compliance_council.py`, `llm_provider.py`, `phi_redaction.py`, `safety_flags.py`,
  `settings.py` (copied from backend `config.py`), `council_roles/*.txt` — copied from
  `lithrim-backend/app/...` with `app.*` → relative import rewrites and `_ROLE_PROMPTS_DIR` repointed.
- `_compat.py` — **NEW** no-op stubs for the backend's observability utils
  (`get_structured_logger`, `start_timer`, `emit_counter`, `emit_timing`) + a permissive module
  `__getattr__` so any other `app.utils.*` symbol resolves to a no-op.

**Vendored orchestrator path — `lithrim_bench/runtime/pipeline/`:**
- `orchestrator.py`, `stages.py`, `models.py` — copied + import rewrites.
- `retrieval.py` — **replaced with a STUB** (`retrieve_for_request` returns empty matches → no
  Pinecone; council tolerates empty grounding).
- `provenance.py` — **replaced with a STUB** (`NoOpProvenanceStore`; `MongoProvenanceStore` aliased
  to it → no Mongo).
- `__init__.py` — emptied (it carried the backend's `app.*` re-exports).

**Stub — `lithrim_bench/runtime/services/artifact_evaluator.py`** (**NEW**): `validate_artifact_structural`
(skip) + `_run_artifact_judge` (NotImplemented) so `stages.py` imports resolve while the structural
and artifact stages are skipped.

**Backend — `lithrim_bench/backends/local_pipeline.py`** (**NEW**): `LocalPipelineBackend(BackendClient)`.
Builds a `PipelineRequest` from a pack case, constructs `PipelineOrchestrator` with `structural_stage`
+ `artifact_stage` injected as skips and a `NoOpProvenanceStore` (so **only the semantic/council stage
runs**), executes in-process via `asyncio.run`, and maps `PipelineResult` → `BackendVerdict` (reusing
`_build_context` + `_GATE_TO_COMPLIANCE` from `lithrim_pipeline.py`). `eval_mode=True` +
`conversation_id="run:local:case:<id>"` give deterministic per-judge seeds.

**Scribe-aware fix (3 vendored edits)** so the council selects its scribe prompt branch
(`build_prompt:597-655`), matching how the analyze flow judges a typed agent:
- `runtime/pipeline/models.py` — `PipelineRequest` gained `agent_metadata: Optional[Dict] = None`.
- `runtime/pipeline/stages.py` — `_build_transcript_payload` forwards `request.agent_metadata` into
  the council payload.
- `backends/local_pipeline.py` — sets `agent_metadata={"category": case.agent_type, ...}`.

**Runner — `scripts/run_local_scribe.py`** (**NEW**): runs `eval_runner.run_pack` over `scribe_v1`
with `LocalPipelineBackend` (`--limit`, `--n`) and prints a verdict-vs-expected comparison.

---

## M1 result (CONFIRMED)

**Run command (BYOK):**
```bash
cd lithrim-bench
# Export ONLY the 5 LLM/Azure keys. Do NOT `source` the whole backend .env — it has complex
# Settings fields (e.g. HIPAA_ELIGIBLE_LLM_PROVIDERS) that pydantic-settings JSON-parses and fails on.
for k in LITHRIM_LLM_PROVIDER AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_API_VERSION AZURE_OPENAI_DEPLOYMENT_COUNCIL; do
  v=$(grep -E "^$k=" ../lithrim-backend/.env | head -1 | cut -d= -f2-); v="${v%\"}"; v="${v#\"}"; export "$k=$v"; done
PYENV_VERSION=debuglithrim COMPLIANCE_COUNCIL_VERSION=v1 PYTHONPATH=. \
  pyenv exec python scripts/run_local_scribe.py --limit 1
```

**Output:** `bench_scribe_v1_inject_condition_1bd0f10dc7b5` → `got=reject exp=reject` (**match 1/1**);
`flags got=[FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT]`, `flags exp=[FABRICATED_HISTORY]`.

- `FABRICATED_HISTORY` — **correctly caught**. Injector added "Diabetes mellitus type 2" to the PMH;
  the sprain-visit transcript never discusses it.
- `MEDICATION_NOT_IN_TRANSCRIPT` — **confirmed false positive** (verbatim transcript: *"Dr: I see
  you're on zidovudine 300 MG Oral Tablet. Continue at 300 MG daily." / "Patient: Got it, 300 MG of
  the zidovudine, every day."*). A real council error → exactly the kind of miscalibration the
  product's calibration loop exists to surface and fix.

---

## Current state

- **M1 spine proven:** salvaged council + orchestrator run fully in-process; reproduce the verdict on
  the local path; BYOK Azure `gpt-4.1`, council `v1` (3 judges policy/risk/behavior, same model).
- **Grounding is empty** (retrieval stubbed). The local vector store (numpy spike / sqlite-vec) is
  **not yet wired**; the council produces verdicts without grounding by design.
- **No data layer yet** — `eval_runner` writes NDJSON to `out/`. SQLite is the next decision (OPEN).
- **Only the council/orchestrator slice is vendored.** The full analyze flow, audio, the
  eval/promote/compare harness, the Clojure server, and the UI are **mapped but not yet salvaged**
  (see `SALVAGE_FINDINGS` salvage map).

---

## Key decisions (flag-if-wrong)

1. **Host = `lithrim-bench`** (extend it; its `CLAUDE.md` charter still says "not a copy of
   lithrim-backend / CLI + JSONL until phase 4" and should be updated to "this is the product").
2. **Orchestrator path, not direct `ComplianceCouncil.evaluate`** — faithful to `/v1/pipeline/evaluate`,
   reuses payload-building + result mapping, and dodges the F4 transcript trap (transcript lives at
   `call_context.transcript`, not a top-level key).
3. **Scribe-aware** vendored `PipelineRequest.agent_metadata` so the scribe prompt branch fires.
   This is a deliberate divergence from the cloud sync path (which omits it); it matches the analyze
   flow and suppresses false positives on legit scribe output.
4. **Spike grounding = empty / numpy** — sqlite-vec is blocked because neither `python3` (3.12.8) nor
   `debuglithrim` (3.10.15) has `enable_load_extension`. Productized local vector (apsw / LanceDB /
   Clojure-side `xerial sqlite-jdbc`) is deferred.
5. **Deferrals:** audio → M2 (~1.1GB whisper/pyannote); Gemini signal-agents stubbed in M1,
   BYOK-routed in M3; scribe-first (semantic-only pack), structural deferred.
6. **SQLite data layer: OPEN** — document-shim (vendored code runs with import rewrites only; swaps
   back to Mongo for cloud) vs relational tables (queryable for reporting). Recommended: doc-shim,
   add indexed columns later. Does **not** block M1 (eval_runner writes NDJSON).

---

## Next steps

1. **(Immediate, ~90 gpt-4.1 calls)** Full 30-case `scribe_v1` run for the real pack-level numbers:
   verdict accuracy, flag precision/recall, and **false-block rate on clean negatives** (the
   `MEDICATION_NOT_IN_TRANSCRIPT` FP makes this the interesting metric). `--limit 30` on the runner.
2. **Phase 1 — SQLite + SME-Question Ontology:** the 3 bindings (prompt-shaping, per-question
   retrieval policy, reporting dimension); data-drive the hardcoded council constants
   (`TIER_1/2/3_*`, `_TIER1_OWNERS`) and the Reliability-Contract dims.
3. **Local vector + per-question retrieval:** replace the `retrieval.py` stub (numpy over
   `lithrim-rag-via-etlp/reports/*/receipts-*.jsonl` for the spike).
4. **Salvage the remaining clusters:** analyze flow + analyzeWithAudio (in-process, local whisper),
   the eval/promote/compare loop (the internal eval runner already loops `ObservationWorkflow` per
   case), reporting/dimensions.
5. **Phase 2** consolidated Clojure server (uberjar) + KB ingest → local vector; **Phase 3** UI
   (mapify-io scaffold, TS+Tailwind, theme from lithrim-ui/lithrim.com) + demo voice agent;
   **Phase 4** packaging/installer + licensed-production separability.

---

## Open questions / risks

- **SQLite data layer** (doc-shim vs relational) — gates how the ~28 analyze-flow modules vendor.
- **v1 vs v2 council** — M1 used `v1` (3× gpt-4.1) for simplicity; the prod default is `v2`
  (cross-provider, needs Azure Mistral/Llama deployments). Fidelity question for full reproduction.
- **Council false-positive rate** — characterize `MEDICATION_NOT_IN_TRANSCRIPT`-class FPs across the
  full pack; it's a calibration signal, not a wiring bug.
- The vendored runtime is a **snapshot** of `lithrim-backend@mvp-ready`; no link back to upstream.

---

## References

- Plan: `~/.claude/plans/toasty-twirling-forest.md` (§9-11 = salvage map)
- Findings (evidence): `docs/SALVAGE_FINDINGS_2026-05-29.md`
- Produced: `lithrim_bench/runtime/{council,pipeline,services}/`, `lithrim_bench/backends/local_pipeline.py`, `scripts/run_local_scribe.py`
- Council source (branch `mvp-ready`): `lithrim-backend/app/services/compliance_council.py`; orchestrator: `lithrim-backend/app/services/pipeline/`
- Pack under test: `out/scribe_v1.jsonl` (30 cases); 5 packs in `lithrim_bench/packs.py`; taxonomy `taxonomy/taxonomy_snapshot.json` (24 codes)
