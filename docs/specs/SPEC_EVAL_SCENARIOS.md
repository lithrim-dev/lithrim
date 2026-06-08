# SPEC: Eval Scenarios — the fluid multi-domain product

> The capability to **stand up, run, refine, pitch, and ship an entire LLM-eval scenario** for an arbitrary domain — clinical scribe (the paper thesis), a FHIR bench, a generic StoryWorld — over **one** fluid product. This is the real capability the **4-act journey scripted**: the journey becomes a **domain-agnostic working frame** that any Scenario flows through, instead of a hardcoded clinical story.
>
> **Status: DRAFT** — authored 2026-06-09. Owner: monitor + user. Sits atop `SPEC_UNIFIED_AUTHORING_PRODUCT` (the locked product) + `SPEC_PLUGIN_ARCHITECTURE` (a Scenario ≈ a pack + dataset + journey). Two shape decisions LOCKED 2026-06-09 (see §Decisions).

---

## The Problem

To release for end-users and to pitch, the product must run **whole eval scenarios across domains**, not one wired-in clinical demo. Today:

- The **engine is already domain-agnostic** — the harness grades over the SQLite config plane + an ontology; the council + grounding floor carry no clinical assumption (`walking-skeleton-architecture`).
- But the **clinical-specificity is hardcoded shallowly** in three places: the **journey frame** (`apps/shell/src/data.jsx:13` `"Clinical scribe · encounter transcripts"`; `cards.jsx` Domain widget hardwires "Clinical scribe"), there is **only one ontology/pack** (`data/ontology/clinical_v1.json`), and the cases.
- There is **no first-class Scenario object** — just a single `ws0_default` agent + ad-hoc imported cases.

So a pitch can show clinical, but cannot fluidly stand up "…and here's a FHIR bench… and here's a totally generic StoryWorld — same platform, your domain." That fluidity is the product.

**This is NOT a rebuild.** It is: (1) make a **Scenario** first-class, (2) **un-hardcode** the journey frame so it parameterizes per Scenario, (3) add **≥1 more reference scenario** to prove domain-agnosticism. Everything else composes threads already sequenced (CHATBIND-2, IMPORT-1, Plugin Phase-1).

**Non-goals (this spec):** the data-ingestion layer (that is IMPORT-1); the plugin registry/license gate (Plugin Phase-1); a marketplace; auto-generated per-scenario *pitch* narratives (a later refinement — see §Decisions).

---

## Decisions (LOCKED 2026-06-09, user)

- **D-A — the journey: working frame now, pitch-narrative later.** Make the existing **5-step setup-journey** (`Domain → Judge → Flag → Run → Review`) **domain-agnostic** — that is the working frame every Scenario flows through. Keep the polished **4-act journey FROZEN** as the clinical pitch (untouched). Generalizing the 4-act into a per-Scenario pitch narrative is a later refinement (R-LATER), not now. [[unified-authoring-product-frozen-journey]] stays in force for the 4-act.
- **D-B — FHIR bench is the first new Scenario** (after the frame). A real published benchmark (FHIR-AgentBench), more pitch-credible to technical buyers, partial assets exist (`data/picklist_fhir_mini.json` + `docs/research/REPORT_fhir_agentbench_2026-06-04.md` + [[fhir-agentbench-benchmark]]). StoryWorld (the generic domain-agnostic proof) follows.

---

## Solution

### 1. The Scenario — the first-class unit

A **Scenario** is the thing you select, run, clone, pitch, and ship:

```
Scenario = {
  domain/ontology (flags + taxonomy)        // the "what is true" contract
  council (judges + their LLM providers)     // who grades
  grounding contracts                        // the by-construction floor (can overrule the council)
  dataset (cases)                            // what gets graded
  eval-pack config                           // how it batches + the CI/CD gate
  journey framing                            // the domain label + the 5-step frame it flows through
}
```

It composes existing concepts: it **is** the plugin spec's **`pack`** (ontology + judges + flags + grounding) **+ a dataset + a journey framing**. A Scenario carries `tier: core|pro` (clinical/StoryWorld = core samples; the full FHIR/healthcare packs = pro) — the open-core line from `SPEC_PLUGIN_ARCHITECTURE`.

### 2. The domain-agnostic working frame

The 5-step `Domain → Judge → Flag → Run → Review` rail becomes **parameterized by the active Scenario** — the Domain step reads the Scenario's `domain_label`/ontology (not the hardcoded "Clinical scribe"); Judge/Flag/Run/Review operate on the Scenario's council/flags/dataset. The frame is the *same* for every domain; only the Scenario's data differs. This is what makes the product *fluid*.

### 3. The reference set (the pitch arc + the proof)

| Scenario | Role | Status |
|---|---|---|
| **Clinical scribe** | *= the paper thesis* — the grounding floor correcting a confident-but-wrong council (the moat). | ✅ exists (`clinical_v1`) |
| **FHIR bench** | The credible external benchmark (FHIR-AgentBench / MIMIC-IV-FHIR QA): judge-only vs +floor; semantic-over-valid-FHIR errors a conformance check misses → a **graph/resolution floor**. | 🔜 first build (D-B); partial assets |
| **StoryWorld** | A fully generic/narrative domain, **no SME needed** — the cleanest proof the frame generalizes off clinical. | 🔜 after FHIR |

The contrast *is* the pitch: **the moat → a real benchmark → literally anything.**

---

## Data Contracts

### Scenario manifest (proposed — refine in SCENARIO-1)

```json
{
  "scenario_id": "fhir_agentbench",
  "title": "FHIR-AgentBench (MIMIC-IV-FHIR QA)",
  "domain_label": "FHIR clinical QA · MIMIC-IV records",
  "tier": "pro",
  "pack": {
    "ontology": "fhir/1",
    "judges": ["risk_judge", "policy_judge", "faithfulness_judge"],
    "flags_ref": "fhir_taxonomy",
    "grounding_contracts": ["fhir_graph_resolution"]
  },
  "dataset": { "source": "data/scenarios/fhir_agentbench/cases.jsonl", "cases": 30, "ground_truth_basis": "ehrsql_retrieval_gold" },
  "providers": { "risk_judge": "", "policy_judge": "", "faithfulness_judge": "byo-claude" },
  "journey": { "frame": "default-5-step" }
}
```

A Scenario reuses the plugin **pack manifest** verbatim under `pack`; `dataset` + `domain_label` + `providers` + `journey` are the Scenario additions. `clinical_v1` is back-filled as `scenario_id: clinical_scribe`.

---

## Requirements

### P0 — SCENARIO-1 (the spine; the next cycle)
- A **Scenario object** in the config plane (manifest above) + `GET /v1/scenarios` (list) + select/clone — composing `harness/config` + the plugin `pack`.
- **Un-hardcode the journey frame** — the Domain step + the rail read the active Scenario's `domain_label`/ontology (kill the `data.jsx:13` / `cards.jsx` clinical literals; default to the active Scenario).
- A **scenario picker** in the shell (and reachable from chat — composes CHATBIND-2's pane control).
- `clinical_scribe` re-expressed as a Scenario (parity: the existing clinical flow runs unchanged *as a Scenario*).
- Proven by the frame standing up a **second** (non-clinical) Scenario end-to-end.

### P1 — the reference scenarios
- **FHIR bench Scenario** (D-B, first): a `fhir/1` ontology + flags, a council, the **graph/resolution grounding floor** (a new `contract` over the existing WS-3a floor registry — *not* the full Plugin Phase-1 refactor), a seeded FHIR mini-dataset, and the **judge-only vs +floor experiment** (does the floor improve the outcome — may be null; honest-Δ). Composes `picklist_fhir_mini.json` + the FHIR-AgentBench report.
- **StoryWorld Scenario**: a generic/narrative ontology + flags + a seeded dataset — the domain-agnostic proof.

### P2 — fluid + release (compose the in-flight threads)
- **IMPORT-1** feeds a Scenario's dataset (SDK/JSON/API → bucket → process) — fluid data load, not seeded.
- **Plugin Phase-1** makes packs + the **provider registry/BYOK** first-class (judges from a real provider set per Scenario).
- **End-user release:** starter Scenarios (core samples) the user clones + points at their data.
- **R-LATER:** generalize the 4-act into a per-Scenario pitch narrative (the zyng pipeline can render a Scenario's run as a narrated walkthrough).

---

## Existing seams to compose (grounding — not greenfield)
- **The engine** — `lithrim_bench/harness/` (grade over config-plane + ontology) + the v2 council + the WS-3a structural floor (`_FLOOR_CONTRACT_TYPES`/`_CONTRACT_EXECUTORS` — hosts the new FHIR graph/resolution contract without a registry rebuild).
- **The config plane** — `harness/config.py` Agent/EvalProfile + `harness/evalpack.py` (the pack + the CI/CD gate).
- **The journey frame** — `apps/shell/src/data.jsx` (the 5-step rail, clinical-hardcoded) + `cards.jsx` (the Domain widget) — the un-hardcode site.
- **The plugin `pack` kind** — `SPEC_PLUGIN_ARCHITECTURE` (a Scenario reuses it + `tier`).
- **Drive/show** — CHATBIND-1 (active-agent binding) + CHATBIND-2 (the chat drives the artifact pane).
- **FHIR assets** — `data/picklist_fhir_mini.json` + `docs/research/REPORT_fhir_agentbench_2026-06-04.md` + [[fhir-agentbench-benchmark]] (the graph/resolution-floor motivation).

---

## Open Questions
- **OQ-1 — the FHIR grounding floor shape.** The semantic-over-valid-FHIR errors (reference-resolution / `Encounter.class` / code-vs-text) need a **graph/resolution** check, not conformance. Is it an in-process contract or an etlp-mapper/`:3031`-style service? (Resolve at the FHIR-scenario cycle.)
- **OQ-2 — the Scenario↔pack boundary.** Is a Scenario a thin wrapper over a `pack` (+ dataset + journey), or does it own fields the pack doesn't? (Lean: thin wrapper; the pack carries the gradeable config.)
- **OQ-3 — end-user release model.** Clone-a-starter-Scenario-and-point-at-your-data (lean) vs author-from-blank. (Resolve at the release cycle.)

---

## Build Sequencing (PHASES)
1. **CHATBIND-2** (in flight) — drive + show everything from chat.
2. **SCENARIO-1** (P0) — the Scenario object + un-hardcode the working frame + a scenario picker; clinical re-expressed as a Scenario; proven by a second Scenario standing up.
3. **FHIR Scenario** (P1, D-B) — the credible bench: `fhir/1` + the graph/resolution floor + a seeded dataset + the judge-only-vs-floor experiment.
4. **StoryWorld Scenario** (P1) — the generic domain-agnostic proof.
5. **IMPORT-1 + Plugin Phase-1** (P2) — fluid data ingestion + the provider registry/BYOK + packs first-class.
6. **R-LATER** — per-Scenario pitch narratives; end-user starter Scenarios.

### Critical sequencing
- **SCENARIO-1 needs only the frame + seeded data** — it does NOT block on IMPORT-1 (seed the proof Scenario like the imported demo cases). Fluid data-load (IMPORT-1) thickens it later.
- **The FHIR floor rides the existing WS-3a floor registry** — it does NOT block on the full Plugin Phase-1 refactor.

## Dependencies
- No new external service for SCENARIO-1 (config-plane + shell only). The FHIR graph/resolution floor may add an in-process contract or a sidecar (OQ-1). IMPORT-1 + Plugin Phase-1 are their own specs/cycles.

## Test Plan
- **SCENARIO-1:** clinical-as-a-Scenario grades **byte-identically** to today (parity); the frame renders a second Scenario's `domain_label` (no clinical literal); the scenario picker switches the active Scenario; `GET /v1/scenarios` lists them.
- **FHIR:** the graph/resolution floor flips/holds a verdict on a labeled FHIR case (non-vacuous); judge-only vs +floor measured + reported honest-Δ (the floor's effect may be null).
- **Frozen:** the 4-act journey + the grading engine + the consensus seam unchanged across SCENARIO-1.

## Success Metrics
- A **new domain** can be stood up as a Scenario + run end-to-end **without touching the engine or the journey frame** — the open/closed test for "fluid."
- A pitch can show **clinical → FHIR → StoryWorld** over one product, same loop.
- An end-user can clone a starter Scenario and run their own data (P2).

## References
- `SPEC_UNIFIED_AUTHORING_PRODUCT.md` (the locked product; the 4-act frozen) · `SPEC_PLUGIN_ARCHITECTURE.md` (the `pack` kind + core/pro) · `SPEC_CALIBRATION_TRAINER.md` (P3 = the calibration loop atop a Scenario) · `docs/PAPER_OUTLINE.md` (the clinical/paper-thesis claim).
- Memory: `walking-skeleton-architecture` (domain-agnostic engine) · `conversational-first-core-plugin-line` (Core = conversational eval platform) · `fhir-agentbench-benchmark` (the FHIR bench + the floor motivation) · `unified-authoring-product-frozen-journey` (the 4-act frozen).
