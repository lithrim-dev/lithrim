# Lithrim Bench — Product Spec

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
