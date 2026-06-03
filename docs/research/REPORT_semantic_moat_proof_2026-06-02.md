# Semantic-Moat Proof — record-grounded floor flips the confident FABRICATED_HISTORY false-block

> **Date:** 2026-06-02 · **Type:** experimental thesis validation (throwaway-scripted, NOT a tracked cycle) · **Status:** VALIDATED
> **Claim proven:** on the scribe-**semantic** axis, a patient-record-grounded verification floor flips a *confident, unanimous* FABRICATED_HISTORY false-block that a transcript-only judge (and self-critique) cannot — with **zero false-regression** (it does not clear a genuine fabrication).
> **Relation to prior:** the semantic analog of `p1_exp_0` (the HL7-**structural** proof: the council confidently approved 35% of HL7 defects; the structural validator caught all and flipped the verdict). The moat was proven on structural; this proves it on the harder, higher-value semantic axis. Both error directions, both axes, now demonstrated.
> **Provenance:** `examples/proof_case.jsonl[4]` (`bench_scribe_v1_inject_condition`); live v2 trio via `../lithrim-backend/.env` (gpt-4.1 / Mistral-Large-3 / Llama-4-Maverick); throwaways `/tmp/semantic_moat_proof.py` (offline), `/tmp/semantic_moat_live.py` (4 calls), `/tmp/semantic_moat_fullnote.py` (offline floor program). Floor registered into the real `harness/grounding.py` pipeline at runtime — **no committed edits**.

---

## 1. The exhibit (one sentence)

> **A confident, unanimous LLM council renders the identical verdict — BLOCK, FABRICATED_HISTORY, confidence 1.0 — on a real clinical note and a fabricated one. Only tool-grounding against the patient record tells them apart.**

## 2. Method — a by-construction pair

From one real Synthea-derived case (`proof_case[4]`), differing by exactly one condition:

- **Case F (defect):** the artifact PMH contains an injected **"Diabetes mellitus type 2"** — **∉** `patient_profile.conditions` (20 real conditions) and **∉** the transcript → a genuine FABRICATED_HISTORY. `expected = reject`.
- **Case L (legit):** Case F with the injected diabetes line removed → the PMH is **only** the patient's real conditions (all **∈** record), none in the 256-char transcript. `expected = approve`. The near-miss the council should *not* flag.

The label is true by construction: diabetes ∈ record is decidable (it isn't); the 20 others ∈ record (they are). Three legs: **(a)** live council on the pair; **(b)** the tool-grounded floor; **(c)** self-critique control.

## 3. Results

### 3a. Live council — it cannot tell them apart [CONFIRMED, observed; 4 live v2-trio calls]

| Case | Council verdict | FABRICATED_HISTORY fired by (per judge) |
|---|---|---|
| **F** (diabetes — *real* fab) | **BLOCK** | risk **1.0**, policy **None**, faithfulness **1.0** (unanimous) |
| **L** (all-real PMH — *no* fab) | **BLOCK** | risk **1.0**, policy **None**, faithfulness **1.0** (unanimous) |

Reproduced ×2 each. The transcript-only council is structurally blind to the record: a genuinely clean note and a fabricated one get the **identical** confident, unanimous BLOCK. (Mistral `confidence=None` tolerated end-to-end — the WS-6c invariant, live.)

### 3b. The record-grounded floor — it discriminates per finding [CONFIRMED, deterministic on real artifacts]

| Council finding | grounding source | Case L | Case F | clearance basis |
|---|---|---|---|---|
| FABRICATED_HISTORY | **patient record** | cleared | **retained** (diabetes ∉ record) | airtight |
| HALLUCINATED_DETAIL | **patient record** | cleared | **retained** (diabetes ∉ record) | airtight |
| MEDICATION_NOT_IN_TRANSCRIPT | **transcript** | cleared | cleared | airtight (zidovudine ∈ transcript) |
| FABRICATED_CONSENT | **note** | cleared | cleared | sound (note asserts no consent → vacuous) |
| INCOMPLETE_DOCUMENTATION | section profile | cleared | cleared | **assumption-laden** (required = {PMH, Assessment, Plan}) |

### 3c. The full-note flip [CONFIRMED]

| Case | council → floor | detail |
|---|---|---|
| **L** (all-real) | **BLOCK → PASS** | all 5 over-fires grounded-as-false; `remaining_active = []` |
| **F** (diabetes) | **BLOCK → BLOCK** | 3 false-positives stripped; `remaining_active = [FABRICATED_HISTORY, HALLUCINATED_DETAIL]` = the genuine fabrication |

The floor flips the clean note to PASS **and** improves the defect verdict's *reasoning* — stripping the council's 3 spurious findings off Case F while preserving the 2 real ones. **Zero false-regression.**

### 3d. Self-critique control [CITED, prior CONFIRMED]

The DSPy critique spike (`critique-pass-precision-not-floor`) confirmed a transcript-only self-critique pass *cannot* flip this false-block (shared transcript-only blind spot). Only record grounding does. (Not re-run here.)

## 4. Honesty / caveats

- **Airtight vs assumption-laden.** The discriminating clearances (FABRICATED_HISTORY, HALLUCINATED_DETAIL — record-grounded; MEDICATION_NOT_IN_TRANSCRIPT — transcript-grounded) are airtight and *differ correctly between F and L*. FABRICATED_CONSENT (note asserts no consent → vacuous) is sound. **INCOMPLETE_DOCUMENTATION's clearance is assumption-laden** — it encodes a required-sections profile ({PMH, Assessment, Plan}); a stricter profile (HPI/ROS/vitals) could legitimately fire it. The clean Case-L PASS depends on that profile being part of the contract-of-record.
- **The pair is a regression test for the FLOOR, not just the judge.** Building this caught **two** bugs in the floor contracts mid-flight — (i) grounding the artifact against *itself* (circular), (ii) a PMH-parser slip that emptied the candidate set — each of which produced a *false-regression* (Case F → PASS). The by-construction invariant `Case F must stay BLOCK` made both impossible-results visible immediately. A floor must be validated by-construction the same way the judge is.
- **Live vs reconstructed.** Leg 3a (council can't distinguish) and the FABRICATED_HISTORY/MED discrimination are on **live, observed** output. The full-note flip (3c) feeds the council finding-set **reconstructed from the observed live runs** through the floor (the contracts run against the *real* case artifacts, so F-vs-L discrimination is real); the live result dicts were not persisted. A 2-call upgrade would make 3c byte-clean live.

## 5. Cost + reproduction

- **Live:** 4 v2-trio calls, **116,908 tokens** (106k prompt / 11k completion) ≈ **$0.3–0.6**.
- **Offline:** $0 (record floor + the full-note program are pure data comparison — no `:3031`, no LLM).
- Reproduce: the three `/tmp` scripts; debuglithrim pyenv; live leg needs `LITHRIM_LLM_PROVIDER=azure` + the three `AZURE_OPENAI_DEPLOYMENT_*` from `../lithrim-backend/.env` + `COMPLIANCE_COUNCIL_VERSION=v2`.

## 6. What this unlocks

- **Paper:** scope **RATIFIED 2026-06-02** — v1's locked §1 stays **structural/copilot**; this semantic-moat result is **Paper 2's anchoring keystone** (framework / Faithfulness pillar), NOT a v1 widening. Used in the **design-partner demo + GTM now** (the demo is the channel for the differentiation; the paper is not). Recorded in the `PAPER_OUTLINE.md` 2026-06-02 amendment.
- **Product / design-partner demo:** the believe-it moment — show the two notes side by side, identical confident BLOCK, then the record floor flips only the real one. The `record_presence` contract family is the next data-layer build (productionizing the runtime-registered experiment).
- **Thesis status:** moat now demonstrated on **both** axes (HL7-structural via `p1_exp_0`; scribe-semantic here), in **both** error directions (false-negative: council approves a real defect → floor blocks; false-positive: council blocks a real note → floor clears). The deferral ("motivate, don't prove") is closed.
