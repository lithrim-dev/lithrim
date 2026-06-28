# Lithrim — Product Spec

**Status:** v0.1 draft, not committed-to.
**Owner:** Rahul (founder)
**Last updated:** 2026-05-21

---

## 1. What it is

A self-serve clinical-AI benchmark generator and scoring service for developers building healthcare agents (scribe, coding, triage, intake, scheduling). A developer signs up, picks an agent type, picks defect classes they want to stress-test, and gets:

1. A **JSONL pack** of golden cases — deterministically labeled, multi-modal (transcript + artifact + patient profile, optional HL7 in Phase 3), versioned, citable.
2. A **scoring endpoint** — they POST their agent's outputs for those cases, we return per-defect-class precision / recall / F1, false-block rate on clean negatives, verdict-instability over N runs, and an aggregate Lithrim Reliability Score.
3. A **failure dashboard** — which defect classes their agent missed, anchored to the exact transcript span and the verbatim `injection_recipe` that proves the label.

The same engine produces the paper benchmark. Internal cost is the same as external cost; the product is the engine + a thin web surface.

## 2. Who buys it

| Buyer | Pain | Why Bench is the wedge |
|---|---|---|
| AI scribe startups (Abridge, DeepScribe-likes, Suki competitors) | "Our customers want SOC2 + faithfulness numbers. Hand-curated 50-case test sets are a joke and we know it." | Bench is the only thing offering deterministically-labeled, taxonomy-tied multi-modal golden cases at scale, with a clinical safety frame. |
| Health-system AI safety officers | "We need to audit an external vendor's agent before we let it into the EHR." | A reproducible third-party benchmark with stable provenance. |
| Insurance / coding agent vendors | "We're being asked to prove our coder isn't upcoding." | UPCODING_RISK injection class + ICD/CPT-aware artifact synth. |
| Lithrim itself | "We need a self-serve on-ramp that demonstrates the platform's value before sales conversations." | First touch: developer runs their agent through a free pack → sees a score → wants the full Lithrim platform. |

## 3. The funnel

```
Developer signs up
  └─ Picks agent_type (scribe | coding | triage | intake | scheduling)
       └─ Picks defect classes to stress-test (Tier 1 only / +Tier 2 / all)
            └─ Picks pack size (50 free / 250 paid / 1000 paid)
                 └─ Downloads bench-<agent>-<seed>.jsonl
                      └─ Runs their agent locally, dumps outputs.jsonl
                           └─ POSTs outputs.jsonl to /v1/bench/score
                                └─ Gets back a dashboard URL
                                     └─ See per-defect-class metrics +
                                        a "Lithrim Reliability Score"
                                          └─ Upgrade prompt:
                                             "Get continuous monitoring
                                              on your production traffic
                                              with Lithrim Platform"
```

## 4. API surface (v1)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/v1/bench/packs` | Create a new pack. Body: `{agent_type, defect_classes, size, seed, include_clean_negatives}`. Returns `pack_id` + JSONL download URL. |
| GET | `/v1/bench/packs/{id}` | Pack metadata: pinned generator version, taxonomy snapshot SHA, Synthea cohort SHA, design matrix. |
| GET | `/v1/bench/packs/{id}/cases.jsonl` | The JSONL file. |
| POST | `/v1/bench/packs/{id}/score` | Body: developer's `outputs.jsonl` (one row per case with their agent's `(verdict, flags)`). Returns `run_id`. |
| GET | `/v1/bench/runs/{id}` | Per-case match, per-defect precision / recall / F1, false-block rate, verdict-instability if N>1. |
| GET | `/v1/bench/runs/{id}/dashboard` | Hosted human-readable failure dashboard. |

Determinism contract: the same `(agent_type, defect_classes, size, seed)` returns byte-identical cases. This is non-negotiable and is what lets a buyer cite "we score 0.83 on Bench v0.4".

## 5. Pricing (proposed)

| Tier | Cases per pack | N runs (determinism) | Price |
|---|---|---|---|
| **Free / Eval** | 50 | N=1 | $0 — single pack per agent_type per org per month |
| **Pro** | 250 | N=3 | $499 / pack |
| **Scale** | 1000+ | N=10 (paper-grade) | custom; bundled with Lithrim Platform |

The Free tier is the lead-gen surface. Pro is the "we're serious about reliability" tier. Scale is the on-ramp into the platform.

## 6. What Bench-the-product needs that Bench-the-paper-artifact does not

| Item | Paper | Product |
|---|---|---|
| Determinism harness (`N` runs of the developer's agent) | needed | **needed** — verdict-instability is a headline metric for buyers |
| Web dashboard | not needed (JSONL + tables suffice) | **needed** |
| Auth + org scoping | not needed | **needed** (JWT + API key, reuse lithrim-backend's auth) |
| Billing | not needed | **needed** for Pro/Scale |
| Per-defect-class drill-downs | nice | **needed** for the upgrade prompt |
| HL7 modality (Phase 3) | strongly needed (main paper claim) | **needed**, but later — most buyers' agents are text-in-text-out |
| Custom defect injection (BYO defect) | not needed | **needed** for Scale tier ("we want to stress-test our own bespoke failure modes") |

## 7. Sequencing against the paper

The paper requires phases 1–3 of the engine (scribe/scheduling first; then coding/triage/intake; then HL7). The product requires phase 4 (the API surface, dashboard, auth, billing).

**Practical order:**

1. **Now → +3 weeks:** Phase 1 engine. Paper-ready scribe + scheduling cases. Internal use only.
2. **+3 → +5 weeks:** Phase 2 engine + first dogfood pack. Phase 4a (the `/v1/bench/packs` and `/v1/bench/packs/{id}/cases.jsonl` endpoints — no scoring yet). One handpicked design-partner can already self-serve a JSONL pack.
3. **+5 → +8 weeks:** Phase 3 (HL7) + Phase 4b (`/v1/bench/score` + dashboard). Public Bench v1 release.
4. **+8 → +10 weeks:** Paper submission (arXiv) coincides with Bench v1 launch. The paper *is* marketing for the product.

The single insight: **the paper is the announcement and the product is the offering**. They ship together.

## 8. What this spec deliberately does not commit to

- A UI for case authoring. Buyers cannot upload their own cases at Pro tier. Custom injection is Scale-only.
- A free Scale tier "for academics." Resist; the engine is the moat.
- A way to expose `injection_recipe.pre_value` / `post_value` in the developer dashboard before the developer has submitted their score. (Giving the answer key away is dumb.) The dashboard reveals the recipe only post-scoring.
- Sub-agent-type specialization (e.g., "pediatric scribe" vs "adult scribe"). v1 is one taxonomy per agent_type.

## 9. Open questions

- Does Bench score against the developer's *agent's outputs* or against the developer's *agent's outputs run through Lithrim Platform*? The latter is the upsell mechanic but adds latency and compute cost. v1 default: score against developer's raw outputs; Platform scoring is a Scale-tier upgrade.
- How does Bench handle Tier-2 / Tier-3 corroboration semantics? The pack should declare per-case whether multi-judge agreement is required, but the developer's single output cannot prove corroboration. v1 simplification: developer's single `flags` array is scored as "set of flags emitted"; we don't model their internal council.
- Synthea cohort licensing. Synthea is Apache-2.0 and explicitly public; no issue. Pin the version in the pack metadata anyway.

---

> **§10–§17 added 2026-05-31.** These capture the converged go-to-market / packaging / business-model / launch strategy and **supersede §1–§9 where they conflict** — most importantly: Bench is a **downloadable, local-first, open-core** product, **not** a managed SaaS scoring service. There is **no Lithrim-hosted scoring endpoint or hosted dashboard** in this model; §4/§5 above describe an earlier SaaS framing, retained for history. This strategy is deliberately **not** tracked in the `.devloop/` engineering flow — that flow (`bench-salvage` WS-0..WS-6 + `paper-1-copilot`) executes the engine and the paper; this document is the business plane.

## 10. Strategy at a glance (2026-05-31)

One line: **a deterministically-labeled, tool-grounded eval & calibration harness you download and run locally — the layer that catches the failures an LLM-judge confidently misses.**

- **Wedge:** analyst-led, local-first, open-core (trust + no-procurement adoption).
- **Users/buyers:** the domain **SME** (truth) + the **Product Manager** (decision / accountability).
- **Model:** open-core (free core) + **premium annual license** (+ optional VPC) + **FDE** professional services. No us-hosted surface.
- **Moat:** by-construction labels + a tool-grounded structural/verification floor that can **overrule a confident-but-wrong judge** — demonstrated with data (see §17).
- **Launch:** the paper (provenance) + the free local journey, then the enterprise release-gate.

## 11. Positioning — vs. the eval landscape

The eval/observability layer is crowded but **horizontal and developer-first** (Braintrust, Arize, Galileo, Langfuse, promptfoo) or a **better-judge SaaS** (Composo). Bench is neither.

Closest comp — **Composo** (generative reward model; "deterministic" = low-variance scorer; SaaS/VPC; ~95% expert agreement) builds a *better judge*. Bench's claim is different in kind:

| | Composo / LLM-judge tools | Lithrim |
|---|---|---|
| Source of truth | a model trained to agree with experts | **construction** (the injection recipe *is* the label) + a deterministic tool oracle |
| "Deterministic" means | low-variance scoring | **epistemic** — the floor can *overrule* the judge |
| Judge confidently wrong | no independent oracle to catch it | the verification contract **flips the verdict** |

**Strongest vs. weakest differentiation:**
- **Strongest at the pre-release GATE** — you control the cases, labels are by-construction, the floor overrules the council. The lead use case.
- **Weakest at production observability** — live traffic has no ground truth (the incumbents' home turf). Observability is a deliberate fast-follow, **not** the headline.

**Company-shape comp: Metabase** — open-core, self-hosted (data stays put), analyst-self-serve, experience-led growth, monetize the operational layer. Bench targets that *shape*. The tax Metabase didn't pay: it served an existing need (BI); Bench must partly **teach** a latent one ("your LLM-judge eval is silently wrong") → category-creation → expect a slower ramp.

## 11a. NOT this — scope guards

- Not production observability/monitoring (that's the incumbents'; we're pre-release-first).
- Not a managed SaaS that custodies customer data (no hosted surface; that's the trust wedge).
- Not "a better LLM judge" (Composo's lane); the differentiator is the **floor that overrules the judge**.
- Not a contributor-community OSS play; OSS is a **trust + distribution** lever, not a devrel growth engine.

## 12. Who it's for — the SME + PM wedge

Two personas, **not** developer-led:
- **Domain SME** (clinical/legal/financial) — supplies **truth**: authors/validates criteria, calibrates judges to domain reality.
- **Product Manager** — supplies the **decision**: sets the bar, owns ship/no-ship + the release gate, carries the risk story to leadership/legal.

**The PM is the likely initiator/champion** (felt pain — accountable for shipping the AI feature — + tool-comfort + budget influence); the SME is the scarce collaborator the PM pulls in. **Build for the seam between them** — SME supplies what's correct, PM decides what's good enough. (This is the product's DDD bounded context: PM = product/eng side, SME = domain side, the ontology = the shared language.)

**Demand thesis (why buy):** for seed–Series B AI builders the eval/calibration layer is mission-critical but *not core* → build-vs-buy favors buy. The sharper truth: even buyers lack the scarce resource — **SME time + the SME↔dev translation**. A tool alone doesn't close it; Bench does, by bringing the SMEs *and* the plain-English authoring agent that lets an SME calibrate without a dev.

**ICP discipline:** "every team has a PM" is seductive, but the *qualified* PM ships a **regulated/high-stakes** agent and feels the quality-accountability pain. Persona breadth ≠ qualified funnel.

## 13. Packaging & business model

**Open-core + FDE-to-gate. No Lithrim-hosted surface — the trust wedge is absolute (we run no cloud that could hold customer data).**

| Tier | What | Price |
|---|---|---|
| **Free core** | local desktop, the engine + judges + ontology + by-construction packs + single-user; perpetual | $0 (the trust + marketing wedge) |
| **Premium** | all features, BYOK, support + upgrades, **optional VPC deployment** (their cloud; multi-user / server mode) | annual license, $X/yr |
| **FDE** | professional services — stand up the ontology + verification contracts + release gate per org | engagement, billed separately |

Principle: **monetize org/operational/assurance, keep capability open.** Premium = SSO/RBAC/audit, multi-user, the **CI/CD release-gate SDK**, (later) production observability, the data-lake/RLVR flywheel, and the **compliance/validation-evidence pack** a hospital hands its AI-governance committee. Decide the exact open-core line *from the working vertical slice* (≈ WS-4), not in the abstract.

**Local as procurement-bypass:** the real distribution unlock for regulated buyers is reaching first value with **no DPA / legal / IT ticket** — stronger than a VPC self-host. OSS is a **trust lever** (read-the-source custody proof), not a contributor-community engine.

**FDE discipline (the fundability test):** FDE early is a product-discovery + lighthouse + runway weapon, **not** the permanent delivery model. The number that decides venture-vs-consultancy: **services-intensity per deal must trend down**, via (1) a growing reusable ontology/contract library, (2) declining labor-per-engagement, (3) rising engagements-per-SME. Instrument from engagement one.

## 14. The product experience — the calibration trainer

**The experience *is* the value proposition: a calibration trainer, not a demo.** The free core must be excellent on first use (a disappointing wedge is anti-marketing). Four phases:

1. **First Contact** — download the desktop app (ships with `healthcarePackv1`); a journey-mode conversational agent guides setup (pick Scribe, BYOK key). No YAML, no docs.
2. **The Reveal** — a clean clinical exchange → click **Verify** → the four badges (Faithfulness / Completeness / Safety / Structural) + verdict + provenance chain animate in. First "aha."
3. **Calibration (the product)** — results are **intentionally miscalibrated**; the user tweaks the judge council (edit prompts / add KB / extend taxonomy; plain-English → Jute via the agent), re-runs, and sees the before/after. They learn calibration *by doing it*.
4. **Own It** — load their own conversations (SDK / paper methodology) → promote findings → golden cases + regression suite → premium features they now know they need.

**Coherence requirement (load-bearing):** because the paper's thesis is "LLM-judges alone don't suffice," the product's **hero moment must be a non-LLM check overruling the judges** — the tool-grounded verdict-flip / structural floor (the `MEDICATION_NOT_IN_TRANSCRIPT` exhibit), *not* "tune the judges smarter." Elevate the Structural badge + a staged flip to the climax so the product **enacts** the paper. Frame "intentionally miscalibrated" clearly as a teaching setup — never "our judges ship broken." The desktop install is the first gate (no hosted taste) → keep it light (transcript-first, signed/notarized, auto-update); the pre-install taste is marketing collateral, not a hosted product. License enforcement uses **offline signed keys** (no phone-home, or the airgap promise breaks).

## 15. Research & paper as provenance — the open-core flywheel

- **Paper = provenance.** It establishes (citably) that LLM-judges alone don't suffice for regulated data and that you need other checks-and-balances — trust currency marketing can't buy, and what legitimizes the free core.
- **A research *program*, not one paper.** Each added **layer** (structural validator → council → +tool-grounded contracts → +ontology) reveals more operationally-hidden failures → an **ablation / marginal-layer-yield** study with a **failure taxonomy** as the durable output. Keep the publishable claim anchored to the **by-construction denominator** (known ground truth); "operationally hidden" is the motivation, not a claim to prove on uncontrolled production data.
- **Open-core research flywheel.** The community runs the open bench on models/data you'd never reach → findings + citations → the de-facto eval standard in the vertical → compounding credibility. This **recovers the cross-customer network effect** forfeited by no-data-custody — usage/citations instead of data. Compatible with the trust wedge *because* the benchmark is synthetic-by-construction (publishable, PHI-free).
- **Contamination → your structural advantage.** Static open benchmarks die to training-set leakage. Bench ships a **generator**, so publish **versioned, regeneratable** packs (fresh cases on demand). Open the engine + a regeneratable public pack; keep customer ontologies + premium capabilities closed.

## 16. Launch sequencing

- **The paper + the free local journey is the announcement** (provenance + the product lens). Lead enterprise with the **CI/CD release gate** (where the differentiation is load-bearing); production observability is a fast-follow.
- **Don't let "ship together" force a half-baked enterprise product** to a paper date. Ship the paper when the claim is airtight and the free taste is solid; GA the enterprise surface into the inbound the paper creates.
- **Two streams converge at launch:** `paper-1-copilot` (provenance) + `bench-salvage` WS-arc (product). PLG fills the top of funnel; FDE/sales closes enterprise (personas cross: SME/PM champions → platform team integrates the SDK/gate).

## 17. What's proven vs. what's a bet (2026-05-31 grounding)

Honest readiness, so this spec isn't story-shaped:

- **PROVEN (with data):** the by-construction generator (5 packs), the 3-judge council, the structural floor + composition, and the keystone result — on 28 HL7 ADT^A04 defects the live council **unanimously approved 10 (35%) at confidence 1.0**, and the generated structural validator caught all 10 and flipped them approve→needs_review (`out/p1_exp_0_council_confidence.summary.md`). The thesis holds **on structured artifacts**.
- **NOT YET BUILT:** the **semantic** tool-grounded flip (the scribe `MEDICATION_NOT_IN_TRANSCRIPT` presence-check — grounding still stubbed) → `bench-salvage` **WS-3**; the **release gate** → **WS-4**; the **journey / desktop shell** → **WS-5**; **local / airgapped** → **WS-6**; the **NL→Jute authoring agent** (triply load-bearing) needs an explicit owner across WS-3/4.
- **Inverted risk profile:** the hard *science* bet is largely won; the open risks are *execution* (generalize the floor to semantic + build the product shell) — the more predictable kind.
