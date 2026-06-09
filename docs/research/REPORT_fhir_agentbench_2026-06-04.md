# Research synthesis — FHIR-AgentBench (arXiv 2509.19319) and its bearing on the Lithrim thesis

> **Date:** 2026-06-04 · **Type:** external-paper research synthesis (for PAPER_OUTLINE related-work + a product-validation experiment) · **Status:** SOURCED + verified
> **Subject:** *FHIR-AgentBench: Benchmarking LLM Agents for Realistic Interoperable EHR Question Answering* — Gyubok Lee, Elea Bach, Eric Yang, Tom Pollard, Alistair Johnson, Edward Choi, Yugang Jia, Jong Ha Lee. **ML4H 2025 / PMLR 297.** Code: `github.com/glee4810/FHIR-AgentBench`.
> **How verified:** deep-research harness — 13 primary sources fetched, 55 claims extracted, 25 adversarially verified (3-vote, kill on 2/3 refute) → **22 confirmed, 3 killed**. Sourcing is overwhelmingly the primary paper (arXiv v1+v2, the PDF, OpenReview `Le1hGVQNb8`) + the authors' GitHub. v1 and v2 carry identical methodology + numbers.
> **Honesty tags:** facts = **[V]** verified-against-primary; first-party-blog-only = **[M]** medium; Lithrim analysis = **[I]** interpretive (not a claim the paper makes).

---

## 1. What it is + how correctness is judged

- **[V] 2,931 single-patient clinical QA questions over REAL de-identified EHR data** — the **MIMIC-IV Clinical Database Demo on FHIR** (PhysioNet, ~100 patients), **HL7 FHIR R4 v4.0.1** — explicitly chosen over Synthea. Realism-over-synthetic is the paper's stated wedge (Table 1 contrasts it with Synthea-based FHIRDATA / ICUDATA).
- **[V] Questions are reused from EHRSQL-2024** (clinician-sourced question–SQL pairs over MIMIC-IV-Demo); multi-patient questions excluded. "Real-world" = clinician-authentic questions over real records, **not** newly bedside-collected.
- **[V] Gold is by-construction.** Restore anchor years + reverse term normalization (`lorazepam → Lorazepam`) → **re-execute the SQL on raw MIMIC-IV** → map answer rows to FHIR resource types via `uuid_5(...)` from the official MIMIC-FHIR definitions → "an unambiguous ground truth for retrieval precision and recall."
- **[V] Two-tier judging — the load-bearing point:**
  - **Retrieval = deterministic / by-construction:** precision `|R̂∩R|/|R̂|`, recall `|R̂∩R|/|R|` vs. the gold FHIR resource IDs.
  - **Answer correctness = LLM-as-judge (OpenAI o4-mini)** on free-text output; "Manual review of 500 samples confirmed a 97% agreement rate," plus a no-directional-bias check. **NOT** exact-match or execution.
  - **[V, killed-claim guard]** The harness *refuted* (0–3) the tempting reading that "correctness is purely execution/retrieval-based." Be precise: **gold is by-construction; the agent-answer grade is an LLM.**
- **[M] first-party-only figures** (Verily blog, co-authored, not in the arXiv text): 80 question templates, ~100 patients, 43,000+ benchmark-relevant FHIR records, 15 FHIR resource types.

## 2. Experiment + headline results [V]

Three axes — **retrieval** (direct "FHIR Query Generator" vs. specialized "Retriever") · **interaction** (single- vs. multi-turn ReAct) · **reasoning** (NL vs. code-gen). Four models: **o4-mini, Gemini-2.5-Flash, Qwen3-32B, Llama-3.3-70B.** Table 3 (o4-mini), *Precision / Recall / Answer-Correctness*:

| config | P | R | AC |
|---|---|---|---|
| single-turn · FHIR Query Generator (direct API) | 0.46 | 0.43 | 0.25 |
| single-turn · Retriever | 0.41 | 0.58 | 0.22 |
| single-turn · Retriever · Code | 0.41 | 0.58 | 0.33 |
| multi-turn · Retriever | 0.33 | 0.71 | 0.20 |
| **multi-turn · Retriever · Code** | 0.35 | 0.68 | **0.50** |

- **Best agent = 50.0% answer correctness** (68% recall, 35% precision). All four models cluster **0.44–0.50** on the top architecture (o4-mini 0.50, Qwen3 0.47, Llama 0.46, Gemini 0.44).
- **Code-gen is the dominant lever** (0.20 → 0.50), but **code + iteration are conjunctive, not additive** — multi-turn *alone* (no code) is marginally *worse* than single-turn (0.20 vs 0.22). **Precision is low everywhere (0.33–0.46).**

## 3. Failure modes [V]

Two **co-equal** bottlenecks (paper gives **no per-error-type frequencies** — do not claim one "dominates"):
1. **Retrieval — wrong search space:** searching `Procedure` when the outcome lives in `Observation`; over-narrow queries.
2. **Reasoning over *valid* FHIR:** not following the `MedicationRequest → Medication` reference link (misses the drug name); counting *all* `Encounter`s instead of filtering inpatient; **filtering on human-readable text instead of the standardized FHIR code.**

Critical characterization: these are **semantic errors over well-formed, conformant FHIR** — not schema/well-formedness violations.

## 4. Novelty vs. neighbors [V]

Real de-identified data in the **mandated interoperability format** is the wedge: vs. **EHRSQL** (relational SQL, not FHIR), vs. **Synthea-based** FHIR benchmarks, and **read-only QA** vs. action-oriented **MedAgentBench / FHIR-AgentEval** (create/modify). Reuses EHRSQL questions, re-grounds them on the FHIR resource graph.

## 5. Implications for the Lithrim thesis [I — interpretive]

- ✅ **External validation of "deterministic floor under an LLM judge."** They report a deterministic, by-construction grounding metric (retrieval P/R vs. SQL-derived gold) *beneath* an LLM answer score, and the two **decouple** — 50% answer correctness despite 68% recall. Evidence that a deterministic grounding signal captures an error class an answer-only judge conflates. **Citable in PAPER_OUTLINE §3 (related work) / the motivation.**
- ✅ **Code-gen > NL reasoning (0.20 → 0.50)** supports tool-grounding: deterministic execution over structured data beats free-text reasoning.
- 🎯 **Their circularity is our gap, not their solution.** The final-answer judge is an LLM with no deterministic floor — and in the top config **o4-mini grades o4-mini's own runs.** That is precisely the hole a Lithrim structural floor fills. FHIR-AgentBench is a *motivating precedent*, not a competitor that closed it.
- ⚠️ **Moat refinement (important):** §5.2 errors are **semantic-over-valid-FHIR** — an **etlp-mapper conformance/well-formedness validator alone would NOT catch them.** The floor for this class must be **graph/resolution-level**: was `medicationReference` dereferenced? was `Encounter.class = inpatient` applied? coded value vs. free text? Sharpens our "structural floor ≠ mere conformance" framing.
- 🔧 **Directly adoptable:** their **SQL → UUID5 gold-resource-ID recipe** + **retrieval-P/R-as-set-overlap** is a ready-made by-construction grounding metric for a Lithrim FHIR-QA pack.

## 6. Product validation — replicate on Lithrim, then MEASURE whether grounding improves the outcome [I — plan, not a result]

> The whole point of running this on Lithrim is to **measure** the grounding claim non-circularly, not assume it. By-construction gold makes that possible. **The result may be positive OR null — report which.**

### 6a. Can it be replicated on Lithrim? **Yes — low-to-moderate effort.**
- **Data is public/credentialed:** MIMIC-IV-FHIR-Demo (PhysioNet) + EHRSQL-2024 questions + the repo's gold FHIR resource IDs.
- **Maps onto the harness as a "FHIR-QA pack":** each case = `(question, patient FHIR bundle, gold FHIR resource IDs, gold answer)` — **by-construction labels**, which satisfies the CLAUDE.md core invariant. The SUT (agent) emits `(answer, tool-call trace)`.
- **Lithrim already has the primitives:** it consumes FHIR (etlp-mapper), runs the council (judge), and has the grounding-floor mechanism (can flip a verdict). The missing piece is a FHIR-graph floor (below).

### 6b. The experiment: *does the grounding floor improve eval agreement with truth?*
Hold the SUT fixed (replicate a mid-tier config, e.g. multi-turn + retriever + code). Grade each case **three ways**, scoring **agreement with the by-construction gold**:

| condition | what grades the case | analog |
|---|---|---|
| **A — judge only** | LLM-judge on the free-text answer (replicate their o4-mini-as-judge) | FHIR-AgentBench's headline metric |
| **B — floor only** | deterministic: retrieval P/R vs gold IDs **+** graph checks (reference-resolution, `Encounter.class` filter, coded-vs-text) on the trace/output | Lithrim's structural floor, FHIR variant |
| **C — worst-of (judge ∧ floor)** | Lithrim composition: floor can flip/flag the judge | the product |

**Primary metric:** agreement-with-gold of A vs C. **The thesis is supported iff C > A** — specifically if the floor **recovers false-accepts** (judge says "correct," but retrieval/structure is wrong — the decoupling FHIR-AgentBench already shows: 50% correct despite 68% recall) **without** introducing material **false-rejects** (the false-regression cost Lithrim already measures on the scribe pack).

**Three honest outcomes, all worth reporting:**
1. **Positive** — C meaningfully > A → grounding improves the outcome on the FHIR axis; the moat generalizes from HL7-structural/scribe-semantic to FHIR-QA.
2. **Null/weak** — C ≈ A → the LLM-judge already captures most of what the floor would; the floor's value is narrower than claimed (a real, publishable correction).
3. **Conditional** — C > A only on a subclass (e.g. reference-resolution / `Encounter.class` errors) → quantifies *which* error class the floor owns. This is the most likely outcome given §3, and the **single biggest missing number** (FHIR-AgentBench gives no per-error frequencies).

**Determinism subtlety to exploit:** much of the gold is exact (counts, dates, lab values), so for that subset you can score answers by **deterministic normalized-match against the gold answer** and measure how far the **LLM-judge diverges from it** — i.e. test whether the judge itself is reliable, the cleanest non-circular check.

### 6c. The deployment question (productization, beyond the benchmark)
Can the floor flag a §5.2 error **from the agent's tool-call trace alone, without the gold** (no SQL/gold-ID set exists in production)? E.g. detect an un-dereferenced `medicationReference` or a missing `Encounter.class=inpatient` filter directly from the trace. **If yes → a deployable floor; if it needs the gold → only a benchmark metric.** This is the line between "a paper result" and "the product."

## 7. Caveats, open questions, refuted claims

- **[caveat]** Lithrim §5–§6 here are **interpretive/plan**, not claims the paper makes. The "o4-mini judges o4-mini" circularity is a defensible inference the paper partially pre-empts (97% human agreement on 500 samples + a no-directional-bias check) — but the validation is **aggregate, not per-model**, so same-model self-grading could still inflate o4-mini's 50% relative to the other three.
- **[caveat]** No per-error-type frequencies in §5.2 → retrieval-vs-reasoning are **co-equal**; don't assert structural errors dominate. Code-gen + iteration are **conjunctive**, not independently additive.
- **[summarizer artifacts, discarded]** one small-model pass hallucinated "Claude" as the judge (real = **o4-mini**); a PMC hit was a *different* paper (**FHIR-AgentEval**, Mokssit et al., Boston Children's — action-oriented create/modify tasks, cites this as prior work). Don't trust raw-PDF-byte summaries for this paper.
- **[killed claims]** "correctness judged by three execution/retrieval metrics rather than an LLM judge" (0–3); "the repo ships `evaluation_metrics.py` that scores answers deterministically" (0–3); "PMC source IS this paper" (0–3).
- **Open:** (1) is the self-grading circularity material per-model? (2) per-error-type frequency distribution (sizes the floor's addressable slice); (3) floor-without-gold feasibility (6c); (4) does the structural-error class persist for *action-oriented* FHIR agents (write/modify) vs read-only QA?

## 8. Sources (primary unless noted)
- arXiv abstract / HTML v1 / HTML v2 / PDF: `arxiv.org/abs/2509.19319`, `arxiv.org/html/2509.19319v2`, `arxiv.org/pdf/2509.19319`
- OpenReview (ML4H 2025): `openreview.net/forum?id=Le1hGVQNb8`
- Code + README (data setup, FHIR R4, gold-ID construction): `github.com/glee4810/FHIR-AgentBench`
- First-party blog **[M]** (Verily, co-authors; 50/68/35 match the paper): `verily.com/perspectives/Introducing-FHIR-AgentBench`
- Adjacent (context): MedAgentBench (`arxiv.org/abs/2501.14654`); FHIR-AgentEval (`pmc.ncbi.nlm.nih.gov/articles/PMC12919212/`) — a *different*, later paper.
