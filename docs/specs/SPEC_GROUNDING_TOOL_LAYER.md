# SPEC: Self-Sufficient Grounding Tool Layer
> The tool-grounded verification layer that lets lithrim-bench ground and flip verdicts **without depending on lithrim-backend** — composing over local sidecars (SNOMED terminology, FHIR, Jute) it owns. Status: **DRAFT (proposed lock)**. Authored 2026-06-09 from a live derisking session; every claim is evidence-backed (ad-hoc scripts). Follow diagnose-before-edit.

## The Problem

Two problems, one spec.

**(A) The runtime grounding floor is thin, and the prior plan to thicken it was mis-specified.** Only **1 of 19 gradeable flags** (`MEDICATION_NOT_IN_TRANSCRIPT`) has a `verification_contract`. The handoff's plan — *"generate Jute validators for `FABRICATED_HISTORY` to fix the diabetes over-fire"* — is wrong on four independent axes, each confirmed against code + run evidence:

| # | Claim | Evidence | Verdict |
|---|---|---|---|
| 1 | over-fire is `FABRICATED_HISTORY` | `RUN_clean_compliant_overfire_in_process_2026-06-09.json` shows **`HALLUCINATED_DETAIL` + `INCOMPLETE_DOCUMENTATION`** (each `judges=1`); FABRICATED_HISTORY never fired | wrong **flag** |
| 2 | fix with a Jute validator | `jute_gen`/`structural_jute` ∈ `_FLOOR_CONTRACT_TYPES` = **PASS→BLOCK**; an over-fire is a false **BLOCK** needing **SUPPRESS** (BLOCK→PASS) | wrong **direction** |
| 3 | a presence/Jute check closes it | the fired flags are **semantic** (contradiction/omission); cited spans (`"4. Annual eye exam due"`, `"Diet adherence fair."`) are legitimate content | wrong **tool-class** |
| 4 | it is a floor gap | one judge (`faithfulness_judge`, conf 0.996; `risk_judge`=PASS) + rescore = `max(severity)` so a lone MEDIUM → BLOCK (`harness/ontology.py:86`) | wrong **root cause** |

`judge_optimize` is **already grounded** (it tunes against the by-construction `recipe=label` corpus, not judge self-report — the anti-circularity FHIR-AgentBench lacks). Optimize is **out of scope**; do not touch it.

**(B) The grounding executors that *do* generalize couple lithrim-bench to lithrim-backend.** The only floor/suppress executors that reach outside the process are `kb_grounding` (→ `:8002 /v1/kb/search`) and `record_rag` (→ Pinecone via `lithrim_search_sdk`). Per the project invariant, **lithrim-backend is reference/salvage only** — the bench must ground on tools it owns.

## Solution

Keep the existing `grounding.py` architecture; **add local, code-based grounding tools** and **cut the two backend/external dependencies**.

### Existing architecture (unchanged)

`lithrim_bench/verification/tools.py` defines `VerificationTool` (`verify(claim, spec) -> VerificationResult`, tri-state `conforms`). `lithrim_bench/harness/grounding.py` adapts tools into two registries, keyed by `contract_type` declared in `data/ontology/clinical_v1.json → verification_contracts`:

- **SUPPRESS** — `_CONTRACT_EXECUTORS` (per-finding; `disproved=True` removes the finding from `active` → can flip **BLOCK→PASS**). The over-fire-fix direction.
- **FLOOR** — `_FLOOR_CONTRACT_TYPES` (per-artifact; `conforms is False` injects a finding → **PASS→BLOCK**). The catches-a-missed-violation direction. `conforms is None` ⇒ inconclusive, never flips.

### Target contract-type taxonomy

| contract_type | direction | backend | status | grounds against |
|---|---|---|---|---|
| `presence_check` | suppress | stdlib | shipped | transcript (token presence) |
| `record_presence` | suppress | stdlib | **NEW** (wrap `InRowTool`) | `patient_profile.conditions` (PMH set-membership) |
| `terminology` | suppress/floor | Hermes sidecar | **NEW** | SNOMED code resolution + subsumption |
| `kb_grounding` | suppress | **vendored Pinecone** | **RE-HOME** (was → `:8002`) | KB corpus (`hipaa-compliancev2`) |
| `fhir_record` | suppress | local HAPI sidecar | **NEW** (was `record_rag` → Pinecone) | real FHIR `Condition`/`MedicationStatement`/`AllergyIntolerance` |
| `dosage_grounding` | floor | stdlib | shipped | transcript + chart doses |
| `structural_jute` / `jute_gen` | floor | `:3031` sidecar | shipped | FHIR/HL7 structural conformance |

Each NEW suppress executor is a **thin adapter** mapping `VerificationResult.conforms → Verdict(disproved=)` — mirror the existing `KbGrounding` adapter (the `True ⇒ disproved=True` convention; `None`/`False` never clears by silence).

### Code-based grounding principle (CRITICAL — Hermes-proven)

**Ground by SNOMED code or exact FSN; never fuzzy free-text.** Live proof from the Hermes spike:

```
fuzzy search("Diabetes mellitus type 2 (disorder)") -> 422014003 "Disorder due to type 2 diabetes mellitus"
   ...which is NOT subsumed by Diabetes mellitus (73211009).  A WRONG NEIGHBOR.
code path:  concept 44054006 -> FSN "Diabetes mellitus type 2 (disorder)"   (exact, deterministic)
```

Free-text→concept is itself the NLP error class we are eliminating. The grounding contract is:

> An artifact code is **grounded** iff it `==` a record code **or** is `subsumed-by` (is-a) a record code.

Proven live:

```
artifact T2DM(44054006) vs record [DM 73211009]            -> grounded=true   (specificity/carry-forward -> suppress FP)
artifact T2DM(44054006) vs record [Hypertension 38341003]  -> grounded=false  (unrelated -> true fabrication stays)
artifact T2DM(44054006) vs record [T2DM 44054006]          -> grounded=true   (exact)
subsumed-by?(46635009 T1DM, 73211009 DM)=true ; (44054006,73211009)=true ; ECL "<< 73211009"=324
```

This **generalizes** the synthetic string match (`InRowTool`'s `snomed_core`), which passes only because the bench mints note-PMH and `conditions` from identical strings — it breaks on real clinical text.

## Data Contracts

**`verification_contract` (record_presence, suppress) — proposed:**
```json
{
  "contract_type": "record_presence",
  "flag_code": "FABRICATED_HISTORY",
  "params": {
    "oracle_path": "patient_profile.conditions",
    "extractor": "soap_pmh_items",
    "match": "snomed_core",            // P0 string; P1 -> "snomed_code" (Hermes)
    "artifact_decode": "fhir_documentreference"
  },
  "question": "Is each documented history item grounded in the patient record?",
  "version": "record-presence/v1"
}
```

**`verification_contract` (terminology, code-based) — proposed:**
```json
{
  "contract_type": "terminology",
  "flag_code": "WRONG_CATEGORY_CODE",
  "params": {
    "service": "http://localhost:8500",     // Hermes sidecar (or mcp://hermes)
    "release": "SnomedCT_InternationalRF2_PRODUCTION_20260501T120000Z",
    "relation": "subsumed_by",               // ==, subsumed_by, member_of_refset
    "artifact_code_path": "...", "record_code_path": "..."
  },
  "version": "terminology/v1"
}
```

**Hermes consumed via its built-in MCP server** (`com.eldrix.hermes.mcp` — `tools` + `call-tool`, transport-agnostic; ~27 tools). Grounding uses **code-based** tools (`concept`, `subsumed-by`, `expression-subsumes`, `map-to`/`map-from`); `search`/`autocomplete` are **authoring-only, never grounding** (the fuzzy-search-is-unsafe finding, §4). The Clojars *library* artifact ships the tool defs + dispatcher (no `-main`); the runnable server ships with the Hermes CLI/source — point it at `snomed.db`.

## Requirements

### P0 — Must Have
- **`record_presence` suppress executor** wrapping `InRowTool`; registered in `_CONTRACT_EXECUTORS`; adapter `conforms→Verdict`.
- **FHIR-DocumentReference decode** before `extract_pmh_items` (SOAP at `content[0].attachment.data`, base64-or-plaintext; reuse `injectors/_soap.py` read path). **Non-SOAP artifacts → `conforms=None`** (never suppress by silence).
- **`FABRICATED_HISTORY` contract** declared in `clinical_v1.json`.
- Offline tests asserting the demo pair (clean→suppress, violation→stands) + the **16/16** non-regression on `judge_calib_v1.jsonl` + the non-SOAP `None` guard.

### P1 — Should Have
- **Hermes terminology sidecar** — run Hermes' **built-in MCP server** (`com.eldrix.hermes.mcp`; ~27 SNOMED tools incl. `subsumed-by`, `expand-ecl`, `expression-subsumes`, and **`map-to`/`map-from`/`map-into`** SNOMED↔ICD-10 cross-maps) pointed at `snomed.db` — **no wrapper to build**. Determinism: pin the SNOMED release; drift → `conforms=None`.
- **`terminology` executor**; switch `record_presence` `match` from `snomed_core` (string) to `snomed_code` (Hermes); **carry SNOMED codes on `patient_profile.conditions`** (data-model change, see Dependencies).
- Unlock the **coding flag class** (`WRONG_CODE`, `WRONG_CATEGORY_CODE`, `MISSING_DUAL_CODING`, `MALAFFI_CODE_PROPAGATION`) — zero validators today.
- **Vendor the KB pipeline**: lift `lithrim-backend/lithrim_search_sdk/backend_client.py` (Pinecone-direct + ONNX `all-mpnet-base-v2`/`Splade_PP` + optional FlashRank) into lithrim-bench behind a `[kb]` extra; re-home `kb_grounding` off `:8002`.

### P2 — Nice to Have
- **`fhir_record` executor** + local **HAPI** sidecar loaded with **MIMIC-IV-FHIR-demo** (PhysioNet 2.1.0, open). Localize `FHIR-AgentBench/fhir_client.py` (GCP-targeted → local base_url). Generalizes `InRowTool` from the in-row profile to real FHIR resources, grounding by code.
- Surface contracts in the JudgeEditor **ATTACH VALIDATORS** row (S-BS-112) — the withstands-gate.

## Dependencies
- **Sidecars** (all sidecar-gated, Python/stdlib fallback so OSS core stays self-contained, per [[jute-for-data-transformations]]): Hermes (SNOMED, `:8500`-ish), HAPI FHIR, `:3031` etlp-mapper (existing).
- **Runtime**: Java 21 + Clojure 1.12 (present) for Hermes; `pinecone` + `onnxruntime` (+ `flashrank`) for the `[kb]` extra.
- **Data-model change**: `patient_profile.conditions` carry SNOMED codes (synthea source has them; `injection_recipe` already carries `fabricated_snomed_code`). Additive, by-construction-deterministic; the `taxonomy_snapshot.json` contract is unaffected.
- **Cross-refs**: `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` (the withstands-gate / §2A entity model), `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (sidecar topology), `docs/specs/SPEC_CONVERSATIONAL_CONTROL_PLANE.md` (MCP-tool surface), `CLAUDE.md` (labels-true-by-construction; taxonomy snapshot = the contract).

## Test Plan
- **Offline, $0 (P0):** unit tests on the real `InRowTool` over the demo pair + the 16/16 corpus scan; decode + non-SOAP-guard tests; `ground()` flip assertion (clean BLOCK→PASS when the council over-fires; violation stays BLOCK). Import-isolation: default deps must not pull Hermes/onnx.
- **Live, 1 paid run (P0 precondition):** in-process council on `clean_negative_aaecd73c3bcf` → confirm/deny the FABRICATED_HISTORY over-fire → run `ground()` → capture flip **or honest loss** (over-fire is context-primed; [[live-overfire-context-primed]]). Proof capsule per convention. **Honest-Δ: a no-flip is a documented PASS, not a manufactured win.**
- **Terminology (P1):** re-run the spike asserts (code resolution exact; fuzzy demonstrably unsafe; subsumption + ECL) as committed live-bench-gated tests.

## Success Metrics
- Floor coverage: gradeable flags with a `verification_contract` rises from **1/19**; the coding class (4 flags) gains terminology validators.
- **Zero backend dependency** in `ground()` (no `:8002`, no `lithrim_search_sdk`).
- No false-regression: every by-construction true positive stays blocked (measured on `judge_calib_v1.jsonl`).

## Phased Plan (executor cycles)
1. **GROUND-FLOOR-1** — offline `record_presence` (string-match `snomed_core`); ships now, $0, proven. + the 1 paid live-confirmation run.
2. **TERMINOLOGY-1** — Hermes sidecar + MCP + `terminology` executor; switch to code-based; unlock the coding flags.
3. **KB-VENDOR-1** — vendor `backend_client.py` behind `[kb]`; re-home `kb_grounding`.
4. **FHIR-1** — MIMIC-IV-FHIR-demo + local HAPI + `fhir_record`.

## Open Questions
- `terminology` as SUPPRESS vs FLOOR per coding-flag (a wrong code is a missed violation → likely FLOOR; a wording-mismatch FP → SUPPRESS).
- Floor transport: the agent uses Hermes' built-in **MCP** server; for the **deterministic** floor, consume the same MCP, or embed the library (`com.eldrix.hermes.mcp/call-tool`, or `core` directly) for an in-process deterministic call. Decide at TERMINOLOGY-1.
- How condition codes flow through `synthea_loader`.
- Whether `record_presence` and `terminology` ultimately merge into one record-grounding executor (string match = the degenerate, code match = the general case).

## Evidence Appendix
- **Spike:** `~/Workspace/github.com/hermes-spike/` (`deps.edn`, `import.clj`, `query2.clj`). Hermes imported the real RF2 dump → 2.3 GB `snomed.db` in ~2 min.
- **SNOMED dump:** `~/Workspace/github.com/SnomedCT_InternationalRF2_PRODUCTION_20260501T120000Z.zip` (valid RF2 Snapshot: Concept 32 MB / Description 228 MB / Relationship 398 MB + Refsets).
- **Salvage sources:** `lithrim-backend/lithrim_search_sdk/backend_client.py` (KB pipeline); `~/Workspace/github.com/FHIR-AgentBench/` (FHIR client + MIMIC loaders, GCP-targeted).
- **Over-fire RUN:** `docs/research/RUN_clean_compliant_overfire_in_process_2026-06-09.json`. **Demo pair:** `examples/proof_case.jsonl` + `examples/judge_calib_v1.jsonl` (`clean_negative_aaecd73c3bcf` / `inject_condition_1bd0f10dc7b5`).
- **Code anchors:** `harness/grounding.py` (registries, `ground`, `_run_floor`, `PresenceCheck`, `KbGrounding`); `harness/ontology.py:86` (`rescore`); `verification/tools.py` (`InRowTool`, `extract_pmh_items`); `verification/spec.py` (contract-type constants); `injectors/_soap.py` (decode).
