# Clinical-AI Governance & Semantic-Stability — Research Brief + Demonstrable-Journey Thesis

> **Date:** 2026-06-02 · **Type:** research synthesis + strategy · **Owner:** monitor
> **Provenance:** adversarially-verified deep-research pass (run `wf_d086118b-460`, 2026-06-02): 5 angles → 23 sources fetched → 112 claims extracted → 25 verified (20 confirmed / 5 killed) → 7 after synthesis. Plus a thesis refinement (the "demonstrable journey" constraint).
> **Cross-refs:** `docs/PAPER_OUTLINE.md`, `docs/LITHRIM_BENCH_PRODUCT_SPEC.md`, `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`, `docs/specs/RECOMPOSITION_PLAN_ws6.md`, the WS-6c-AGENTIC grade-wire milestone, memory `semantic-eval-equivalence-is-a-contract` + `eval-services-venture-thesis` + `gtm-launch-and-journey-thesis`.

**Confidence tags (load-bearing — do not strip):**
`[CONFIRMED]` survived 3-vote adversarial verification · `[INFERRED]` analyst transfer-by-analogy · `[UNVERIFIED]` harness found NO verified evidence (treat as open, not as "no signal") · `[internal]` from lithrim memory/work, not externally verified. **Do not launder `[UNVERIFIED]`/`[INFERRED]` into facts** — the honesty is the deliverable (same culture as the bench: every causal claim is tagged).

---

## §0 — Executive summary

1. The literature **strongly confirms the system-under-test (SUT) instability story**: clinical LLMs flip their diagnosis under small rephrasings, text-similarity metrics are blind to it, and *consistency is not correctness*. `[CONFIRMED]`
2. **By its silence, the literature confirms lithrim's distinct angle (thesis-4): everyone instruments the SUT; no surveyed paper instruments the *evaluator/judge's* own semantic instability.** That is genuine white-space. `[CONFIRMED gap — but "no paper exists" should be confirmed exhaustively before the paper claims novelty]`
3. **Governance accountability was just formally assigned to a multidisciplinary *committee*, not a single owner** (Joint Commission + CHAI RUAIH, Sept 17 2025). `[CONFIRMED]`
4. **GTM thesis (sharpened):** lithrim sells *"the instrument a governance committee uses to prove correctness against ground truth — including proving the judge itself is stable,"* **not** "a better judge." The committee buyer is why the forward-deployed-engineer / services motion exists. `[INFERRED]`

---

## §1 — The Demonstrable-Journey Thesis (the refinement — lead with this)

**Constraint:** whatever the paper claims, the **data → evaluation → audit** journey must be *demonstrable, walkable, and auditable inside lithrim.*

This collapses the paper/product split. The paper stops being "a benchmark + numbers" and becomes **a reproducible audit journey the product instantiates.** The epistemic claim flips from *"trust our results"* to *"re-walk the journey and audit it yourself."* That is the strongest form of the repo's "true by construction" ethos — not just the labels, but the entire eval→verdict→audit chain is reconstructable. **The paper describes the journey; the product *is* the journey; the governance committee *walks* it. One artifact, three audiences.**

### The three stages

| Stage | Paper claim (what we assert) | Demonstrable in lithrim (what you walk) | Governance consumer | Status |
|---|---|---|---|---|
| **DATA** | Labels true by construction; equivalence is a *written, purpose-relative contract*; text-similarity cannot measure equivalence (BERTScore/ROUGE-L stay >0.89 as the diagnosis flips) `[CONFIRMED — 2507.21188]` | Injector emits case + label (recipe **is** the label) **and** a family of *declared* transforms — style-preserving vs framing-shifting (the 2604.05051 axes). You read the contract → original → transform → expected-label-unchanged | **Clinical SME** (defines "correct"/"equivalent" — the "who calibrates?" seat) | Built: injectors + by-construction packs `[internal]`. **Gap: the equivalence-contract object + the paired-case generator along declared axes** |
| **EVALUATION** | Consistency ≠ correctness (invariance is not a quality signal) `[CONFIRMED — FairMedQA]`; **the judge has its own semantic instability** `[CONFIRMED white-space]`; a deterministic grounded floor can *flip* the judge `[internal]` | Run case → verdict + per-judge votes. Re-run the *declared-equivalent* rephrasings N× → **watch the judge's votes/codes disperse** (thesis-4 made visible; the N=5 dispersion pilot is the seed). Then the verification contract checks the artifact vs the record → **overrides the judge, logged with reason** | **Quality / safety / risk** (trusts the floor over the judge) | Built: ported v2 council + DSPy judges + the grade-wire (**WS-6c-AGENTIC, landed 2026-06-02**) `[internal]`. **Gap: a judge-stability product surface; grounding-flip proven on HL7-structural, not yet scribe-semantic** |
| **AUDIT** | Every verdict traces to ground truth; the eval is auditable end-to-end; audited records become training data | Open any case → recipe (label justification) → judge votes → grounding flip + reason → final verdict, as one record. Audited records → fine-tuning-ready data (RLVR / data-lake north star) | **Compliance / regulatory** + the emerging **AI-governance leader** | Built: run/session records, grounding-flip logging `[internal]`. **Gap: provenance is NoOpProvenanceStore (WS-6d); committee-facing audit view (shell)** |

### The unifying claim + the moat

lithrim does not *report* a benchmark — it ships a **walkable audit journey**: by-construction data → an evaluation whose own stability is instrumented and whose verdicts are grounded → an audit trail that doubles as training data. **A result you can re-walk and audit is categorically different from a PDF number.** For a RUAIH-style committee accountable for *proving* (not asserting) correctness, a walkable audit journey is literally the deliverable they owe. The paper becomes the spec for the demo; the demo becomes the proof for the paper.

### Roadmap consequence (north-star ordering for remaining work)

Each WS phase = "make one more stage demonstrable":
- **DATA-demonstrable** → the equivalence-contract object + paired-case generator (next data-layer build; motivated directly by 2604.05051 framing≠style).
- **EVAL-demonstrable** → WS-6c-AGENTIC (done: the council now scores real cases through the grade seam) + a judge-stability view (re-run-under-paraphrase, show dispersion).
- **AUDIT-demonstrable** → WS-6d persistence (retire NoOp provenance) + the shell's audit pane (the committee walk-through).

**Honesty line that stays in the thesis:** DATA and EVAL are well-supported by *verified* research; the AUDIT stage's per-role governance mapping rests on one verified fact (the committee) + `[INFERRED]` role detail the harness could not confirm. We demonstrate what we can verify and mark the seams — same discipline as the bench.

---

## §2 — Persona / Governance Map (clinical-anchored → generalized)

### The one verified anchor `[CONFIRMED]`

On **Sept 17 2025** the **Joint Commission** (dominant US accreditor, ~22,000 orgs) + the **Coalition for Health AI (CHAI)** released **"Guidance on the Responsible Use of AI in Healthcare" (RUAIH)** — the **first AI-governance framework from a US accrediting body.** It assigns accountability to a **named multidisciplinary governance committee**: executive leadership, regulatory/ethical compliance, IT, data privacy & cybersecurity, clinical/operational expertise, frontline staff/providers, and patients/caregivers. *Not a single owner.*
**Caveats `[CONFIRMED]`:** currently **voluntary** ("should," not "must"); certification operationalizes ~May 2026; it names a *composition*, **not** specific C-suite titles.
Sources: jointcommission.org RUAIH announcement + the primary RUAIH PDF; corroborated by AHA, Polsinelli, Hooper Lundy ("multidisciplinary governance body rather than a single owner").

**GTM implication `[INFERRED]`:** a committee buyer = longer sales cycle, no single champion title closes it, and the multidisciplinary calibration must be *facilitated* → this is the structural justification for the **FDE / services motion** and the calibration-trainer journey.

### Persona-seat → lithrim wedge

| Committee seat (RUAIH function `[CONFIRMED]`) | Role title `[UNVERIFIED — RUAIH names functions, not titles]` | lithrim wedge |
|---|---|---|
| Clinical / informatics | CMIO, Chief Health AI Officer, clinical informaticist | The SME who **writes the equivalence contract** + defines by-construction labels (the "who calibrates?" seat) |
| Quality / safety / risk | Patient-safety officer, model-risk | The **tool-grounded floor** that catches what the judge misses; defect-injection coverage |
| Regulatory / compliance | Compliance lead | By-construction **provenance**: every label traceable to its injected defect |
| IT / data / security | CISO, data governance | The **no-US-hosted / VPC** trust wedge `[internal]` |
| (emerging) operational AI owner | "AI governance leader" `[UNVERIFIED — trade-press signal only]` | Operates the calibration-trainer journey end-to-end |

### Generalization `[INFERRED, externally UNVERIFIED]`

The cleanest structural analog is **finance model-risk management under SR 11-7** — "effective challenge" by an *independent validator* who must *demonstrate* model soundness, not assert it. The cross-domain archetype: **the independent validator accountable for proving correctness against ground truth rather than vibes.** The harness found **zero verified evidence** for the finance/legal/insurance archetype or buying titles — this is reasoning, not data; it needs its own research pass before any GTM use.

### Verified gaps in this section (do NOT build copy on these yet)

Per-role accountability detail (owns / measured-on / fears / buys), the cross-domain archetype, and the competitor/ICP picture are all **`[UNVERIFIED]`** — RUAIH gives committee *composition* only; the Composo/eval-vendor pages were fetched but no claim survived verification.

---

## §3 — The two papers (evidence layer, secondary)

**"Paper 1" resolved to TWO distinct papers** (the `lnkd.in` link is opaque; either could be the source post's):

- **`2507.21188` "Embeddings to Diagnosis: Latent Fragility under Agentic Perturbations in Clinical LLMs"** (Vijayaraj, KDD'25 workshop) `[CONFIRMED]`. Clinical-decision-support LLMs change diagnosis under small edits **while text metrics stay high** (BERTScore/ROUGE-L > 0.89) → they built a latent **Diagnosis-Flip-Rate** because surface metrics are blind. 6 models, 700 synthetic + 90 MIMIC-IV notes; LDFR 0.9125 → 0.35 (mask) / 0.71 (negation) / 0.73 (synonym). **Most quotable result for us:** you cannot measure semantic stability with text-similarity scoring. **Caveats:** single-author workshop, n=90 real notes, **no clinician adjudicated whether flips were *justified*** (negating a finding *should* change the dx — some "instability" is correct sensitivity).
- **`2604.05051` "This Treatment Works, Right? — LLM Sensitivity to Patient Question Framing in Medical QA"** (Yun/Wallace et al., 6 Apr 2026 preprint) `[CONFIRMED]`. Controlled RAG, evidence held constant → answers flip on **question framing** (positive/negative: β=−.219, p<.001; amplified multi-turn) but **NOT on language style** (technical vs plain: null, p=.86), **no interaction.** Empirically separates pragmatic framing from meaning-preserving paraphrase.
  - **Sharp correction to the source post:** the post's own example — "hypertension" → "high blood pressure" — is the **style axis 2604.05051 found *stable*.** It's *framing* that flips. The post is directionally right but its example is the stable case; that *reinforces* the equivalence-contract point (you must know which axis carries meaning).
  - **Caveat `[CONFIRMED]`:** the authors treat **both** axes as things a model should be invariant to. The "pragmatically-loaded vs meaning-preserving" / "equivalence contract" gloss is **ours, not theirs.** Cite the *result*; claim the framing as our contribution. Consistency was judged by an LLM (Gemini-2.5-Flash) with no human baseline; framing effect is modest (~4pt on a ~24% non-determinism floor).

**The three thesis-validators `[CONFIRMED]`:**
- **`2505.19562` FairMedQA** (v2; cite the v2 URL — v1 "AMQA" lacks the quote): verbatim — *"CFR measures invariance rather than correctness… a model that is consistently incorrect would still achieve a high fairness score,"* so they pair it with Accuracy Disparity. → This is our "consistency ≠ correctness, need a grounded floor" argument in someone else's peer work. *(Caveat: demographic fairness, not broad semantic stability — transfer-by-analogy.)*
- **`2408.01963` IBM / EMNLP-2024** *(NOTE: not `2508.01963`, which is a photocatalysis paper — a digit-transposition the verifier caught)*: replaces the Performance-Drop-Rate with a **normalized Cohen's h** because drop-rate is asymmetric and undefined at zero. → Use to make our dispersion metric **effect-size-aware**. *(Measures SUT instability under paraphrase, NOT the judge — does not itself cover thesis-4.)*
- **`2510.08616`** (Stanford, NeurIPS'25 workshop): meaning-preserving paraphrases → 6–10pt drop, **and the paraphrase-generator (an LLM) is itself an uncontrolled instability source** — *"the evaluation instrument has its own instability that confounds the measurement."* **Closest external echo of thesis-4** — but it is about the *paraphraser*, not the *judge*. *(`2501.08276` corroborates sociodemographic-style sensitivity on commonsense MCQ, NOT clinical; the "7–9% treatment recs" framing was mis-attributed and REFUTED.)*

**`2605.17101` SEMA-RAG** `[CONFIRMED]`: three role-prompted agents over **one** LLM (Interpreter / Explorer / Arbiter); an explicit **binary sufficiency-flag** stopping rule (halt at s_t=1 / T_max / stagnation; benefit mostly within 2 rounds). **Gain is +6.46 avg over the strongest baseline across 5 benchmarks × 5 backbones — NOT +13.** The 77.14 → 89.95 headline is a single deepseek-v3.1 / MedQA-US cell (same backbone gets 59.20 on PubMedQA). Ablation: removing the Explorer (retrieval) hurts most → gain is **agentic closed-loop retrieval**, which **bundles** sufficiency-reasoning (the clean "retrieval-not-reasoning" split was **REFUTED**). Consistent with USMLE MCQ being retrieval-friendly; durability on non-MCQ tasks is unestablished. *(2026 preprint, self-reported ablation.)*

---

## §4 — Incorporations

**Into the paper (`docs/PAPER_OUTLINE.md` / `docs/paper_draft/`):**
1. **Lead related-work with the white-space, not parity:** "prior work (2507.21188, 2604.05051, FairMedQA, IBM-2408.01963) measures the *system-under-test's* stability and warns invariance ≠ correctness; **none instruments the evaluator itself. We do.**" `[CONFIRMED gap; confirm exhaustively before publishing]`
2. **Borrow two methods outright:** the *grounded/latent flip signal* (text metrics are blind — 2507.21188) and **Cohen's h** for effect-size-aware dispersion (2408.01963). Our N=5 judge-dispersion data `[internal]` becomes the *judge-side* instance of the SUT-side phenomenon these papers establish.
3. **Frame the equivalence contract on the framing≠style result** (2604.05051) — credit the authors' actual stance, present the contract as *our* contribution.

**Into the product (`docs/LITHRIM_BENCH_PRODUCT_SPEC.md` + the journey/shell specs):**
1. **A semantic-stability bench for BOTH the SUT and the judge.** The judge half is the differentiator nobody ships — it operationalizes thesis-4 and is the demonstrable EVAL-stage surface.
2. **The by-construction paired-case generator *is* the equivalence-contract instrument:** "you declare which transforms are meaning-preserving; we generate the pairs; the label is true by construction." This is the demonstrable DATA-stage artifact.
3. **Committee-shaped onboarding:** RUAIH says the owner is a multidisciplinary body → the calibration-trainer journey + FDE motion should provide role-specific views along the data→eval→audit walk (clinical SME writes the contract; quality reads the floor; compliance reads the provenance; IT owns the VPC). `[INFERRED]`

---

## §5 — Contrarian / risk + open gaps

**Where the papers over-claim:** 2507.21188 is single-author / n=90 / no justified-flip adjudication; 2604.05051's framing effect is ~4pt on a ~24% non-determinism floor and judged by an LLM; SEMA-RAG's headline is cherry-picked from one cell. **Cite the phenomenon (carried by breadth of literature), not any single number.**

**Where our own framing is the risk:** the "equivalence contract" reading of 2604.05051 is *ours* — a reviewer who reads the paper will catch it if we attribute it to the authors. Cite the result; own the framing.

**Where the persona story is weakest:** the per-role detail, the cross-domain archetype, and the competitor/ICP picture are **`[UNVERIFIED]`**. No GTM copy on the role-level story until a dedicated research pass closes it.

**Citation hygiene for the paper:** `2408.01963` (not 2508); `2505.19562` cite the **v2** URL; `2604.05051` + FairMedQA-v2 are 2026 preprints (not peer-reviewed).

**Strategic risk:** a committee buyer = longer cycle, no single champion. Upside: it is precisely why the FDE/services wedge exists — but "land with one ML engineer" will not work in this segment.

### Follow-up research backlog (the 5 open questions from the run)

1. **Per-role clinical-AI personas** — what each (CMIO, Chief Health AI Officer, clinical informaticist, model-risk/quality-safety, MLOps/eval owner) actually owns, is measured on, fears, and buys. (RUAIH gives composition only.)
2. **Cross-domain archetype** — the "AI evaluation & governance owner" in finance (SR 11-7), legal, insurance + buying titles.
3. **Market / ICP signal** — how Composo and adjacent eval/observability/guardrails vendors describe their ICP, and which titles hold the eval-tooling budget.
4. **Judge/evaluator-instability literature** — confirm (don't assume) that no primary paper instruments the LLM-judge's own semantic instability; if none, thesis-4 is genuine white-space.
5. **SEMA-RAG durability** — how much of the gain survives on retrieval-*un*friendly clinical tasks (open-ended generation), vs USMLE-style MCQ.

---

## §6 — Sources (verified)

- **2507.21188** — Embeddings to Diagnosis (LDFR). `https://arxiv.org/abs/2507.21188` `[CONFIRMED]`
- **2604.05051** — This Treatment Works, Right? (framing≠style). `https://arxiv.org/abs/2604.05051` `[CONFIRMED]`
- **2505.19562** — FairMedQA (CFR ≠ correctness; cite v2). `https://arxiv.org/html/2505.19562` `[CONFIRMED]`
- **2408.01963** — IBM/EMNLP-2024 (normalized Cohen's h). `https://arxiv.org/abs/2408.01963` `[CONFIRMED]`
- **2510.08616** — Surface-Form Brittleness / instrument-has-its-own-instability. `https://arxiv.org/pdf/2510.08616` `[CONFIRMED]`
- **2501.08276** — sociodemographic paraphrase sensitivity (commonsense, not clinical). `https://arxiv.org/pdf/2501.08276` `[CONFIRMED, with mis-attribution refuted]`
- **2605.17101** — SEMA-RAG. `https://arxiv.org/abs/2605.17101` `[CONFIRMED]`
- **RUAIH** — Joint Commission + CHAI, Sept 17 2025. `https://www.jointcommission.org/en-us/knowledge-library/news/2025-09-jc-and-chai-release-initial-guidance-to-support-responsible-ai-adoption` `[CONFIRMED]`
- **Secondary/unverified leads** (fetched, claims not verified — for the follow-up pass): HTI-1 DSI fact sheet (healthit.gov), SR 11-7 (modelop.com), CHAI playbooks (hitconsultant.net), NEJM-AI governance, "evaluate the evaluator" (decodingai.com), "the AI governance leader" (hmacademy.com), Composo (techcrunch / composo.ai / maginative).

**Run provenance:** deep-research workflow `wf_d086118b-460` (2026-06-02); raw verified-claim set in the run's task output. 25 claims verified, 5 killed (incl. the over-stated "clean retrieval-vs-reasoning split" and a mis-attributed treatment-recs figure).
