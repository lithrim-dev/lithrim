# Injected SNOMED cases — the tool-grounded flip demo (Stage 4)

`snomed_injected_v1.jsonl` — 11 **by-construction** clinical-scribe cases for the SNOMED/Hermes
tool-grounding demo (healthcare pack). Synthetic (no PHI); the label is true by construction.

Each case is the admissible healthcare shape: a `fhir_document_reference` artifact whose SOAP body
carries a `PMH:` section, plus `patient_profile.conditions` (the SNOMED-FSN record oracle the
`snomed_subsumption` contract grounds against). The executor resolves FSN **strings** → SNOMED codes
via Hermes `search`, then checks `subsumed_by` — so subsumption is **verified live at grade time**.

## The three groups

| Group | n | Construction | What it demonstrates |
|---|---|---|---|
| **Suppress flip** | 4 | note documents the specific **child** (e.g. *Diabetes mellitus type 2*); record lists the general **parent** (*Diabetes mellitus*) | the council false-flags `FABRICATED_HISTORY` on the specificity; `snomed_subsumption` (child is-a parent) **clears it** → PASS. The headline flip. |
| **Genuine fabrication** | 4 | note documents a concept **not** in / not subsumed-by any record condition (e.g. *Rheumatoid arthritis* with no arthritis in the record) | the floor **correctly does NOT clear** a real fabrication (conservative; suppress-only). |
| **Clean control** | 3 | note PMH item is **verbatim** in the record | grounded baseline, no flag. |

## Honest mechanism notes

- `snomed_subsumption` is a **suppress** executor: it clears a *false* `FABRICATED_HISTORY`, it does
  **not** catch a *missed* one (that's the floor direction, e.g. `concept_preservation`). So the
  flip this corpus demonstrates is the **suppress** direction — a confidently-wrong judge corrected
  by terminology grounding.
- The suppress flip only fires if the council first raises `FABRICATED_HISTORY` on the specificity
  case (the known false-positive pattern these cases are constructed to invite). That's **live**
  behavior — the flip is a demonstration, not a guarantee; an honest run reports whichever way it goes.
- Subsumption pairs are canonical is-a relationships (T2DM⊑DM, acute MI⊑MI, allergic asthma⊑asthma,
  bacterial pneumonia⊑pneumonia); **Hermes verifies them live** (Stage 5). If a pair doesn't subsume
  in the loaded SNOMED edition, that case won't flip — surface it, don't hide it.
