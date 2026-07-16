# Defect families that share the upcoding pattern

Analysis 2026-07-15 (Fable 5 under the synthetic-research safeguard rail, adversarially
ranked; SEVERITY_ESCALATION and grounding-oracle claims verified against the repo). Purpose:
which other defect families are true siblings of
diagnostic upcoding, so we know what to build next, and where the deterministic floor earns
its keep.

## The pattern, stated precisely

The upcoding thesis lives in one cell: **the judge NOTICES but cannot TYPE, and the
deterministic floor supplies the typed, source-cited verdict it cannot.** A family is a true
sibling only if it is (a) clinically plausible, (b) a directional over-assertion up an ordered
or taxonomic axis, (c) resolvable by a deterministic source/ontology oracle, and (d) sits in
that notice-yes / type-no cell with no prompt-invited judge code to fall back on. Value/dose
drift and stark negation reversal fail (d): the judge already types them, so they are
contrasts that sharpen the thesis, not clones of it.

## Ranked

| family | axis | floor value | verdict |
|---|---|---|---|
| miscoding / wrong code | taxonomic (lateral) | high | tight sibling |
| severity escalation | ordinal (mild<severe, stageN) | high | tight sibling |
| status: resolved to active | status/temporality (ordered) | high | tight sibling |
| temporal / duration fabrication | temporal (precisification) | high, but gated | tight sibling, ranks lower |
| erasure / omission (inverse) | under-assertion | high (recall) | reframe, not clone |
| certainty / hedge removal | epistemic modality | medium (bimodal) | partial sibling |
| family-to-personal history bleed | attribution/provenance | medium | notice-axis, not typing |
| value / dose drift | quantitative | low (recall only) | contrast, prune |

## The three to build first (all squarely in cell d)

1. **Miscoding / wrong code** (build first, cheapest, most defensible). The note carries a
   diagnosis code that is a lateral sibling under the same parent, or a wrong category
   entirely, that the source does not license (E11 to E10 diabetes; NSCLC to squamous-cell
   carcinoma). The judge either cannot SEE it (wrong code buried in a FHIR Claim field while
   the SOAP prose reads correct) or notices-but-mistypes a prose-visible sibling. The floor
   oracle already ships and is live-proven in `lithrim_bench/harness/grounding.py`
   (mislabel + semantic-tag + bidirectional subsumed_by + ICD refset), so this is
   manifest-and-corpus work, no new oracle. By-construction: substitute the source-licensed
   code with a sibling under the shared SNOMED parent, pin pre/post codes; add a
   wrong-code-in-Claim-field variant.

2. **Severity escalation** (purest notices-but-cannot-type archetype; highest new-oracle
   cost). The note escalates an ordinal grade the source does not support (CKD G3a to G4 with
   a contradicting eGFR; mild to severe; stable to unstable angina; diverticular disease to
   diverticulitis). Verified: `SEVERITY_ESCALATION` exists in the frozen clinical council seam
   and the HPACK snapshot, but is ABSENT from the study judge lens (`ontology_armR`), so in the
   measured configuration the judge falls to `HALLUCINATED_DETAIL`; and SNOMED is-a cannot rank
   an ordinal escalation, so the floor's typed verdict is net-new regardless of the code's
   existence. A numeric anchor (eGFR to KDIGO stage) gives a crisp second oracle. By
   construction: mutate one ordinal token upward, pin the record's stated/measured grade as
   pre_value. Floor needs a NEW curated per-condition ordinal table (KDIGO / NYHA / cancer
   stage + mild<moderate<severe SNOMED qualifier ranks) plus a numeric-cutoff map, gated
   behind a negation/assertion detector and a same-problem span index. The is-a-blind sibling
   pairs (stable/unstable angina, diverticulosis/diverticulitis) are the ones
   `SPEC_SNOMED_CHECK_BATTERY.md` currently parks as DEFER; they need an SME severity ranking.

3. **Status: resolved to active** (genuine sibling on the status axis; judge weak on BOTH
   legs). The note promotes a resolved or historical problem to active (h/o DVT resolved 2021
   to an active problem-list DVT; former to current smoker). No status-promotion code exists,
   so the judge cannot type it; and because the mutation is a dropped temporality qualifier on
   an axis LLMs are weak on, the judge may not even NOTICE the subtle sub-cases, making the
   floor load-bearing for detection too. By construction: flip a resolved/historical qualifier
   to active/current on the same SNOMED concept, pin the dropped span as pre_value. Floor needs
   the FHIR `Condition.clinicalStatus` ordered value set + concept-identity linkage + a
   live-gated ConText/NegEx temporality+assertion span extractor. The extractor's lower
   intrinsic precision is the gating risk; pin and best-of-N gate it like any generated
   validator.

## Ranks lower, and the honest reframes

- **Temporal / duration fabrication** is a real sibling for its precisification slice (vague
  to dated; acute to chronic is an ordered is-a analogue), but ranks below the top three:
  temporal is a low-salience slot so notice drops, and it carries the HIGHEST false-BLOCK risk
  against this repo's zero-false-clear bar (fragile TIMEX extraction, and the structured record
  may license an onset implicitly). Build only with a conservative floor that defers on
  implicit-onset cases.

- **Erasure / omission (inverse)** is the mirror image: the note says LESS than the source
  (dropped allergy, escalation trigger, patient dissent, stated intent). The judge's failure
  here is under-NOTICE (absence-blindness over unbounded negative space), so the floor is a
  recall / never-miss backstop, not the type-rescue the thesis is about. Highest patient-safety
  value (`MISSING_ALLERGY` is a never-event; `MISSED_ESCALATION` the roster does not own).
  Frame it separately as the recall gate, do not count it as a fourth clone.

- **Certainty / hedge removal** is bimodal. The soft `IMPLICIT_CONFIRMATION_OF_RECORD` /
  hedge-drop subtype ("should confirm" to "confirmed"; "possible pneumonia" to "pneumonia") IS
  a tight sibling: the judge notices but mistypes to a generic bucket. But `NEGATION_REVERSAL`
  ("denies chest pain" to "reports chest pain") is a near-contradiction the judge both notices
  AND types correctly, so drop it from the sibling framing. The family's cues are
  surface-lexical (in the source text) rather than ontology-latent like is-a, so a
  source-grounded judge is structurally stronger here than at upcoding. Scope the family to the
  soft subtype only.

- **Family-to-personal history bleed** ("mother had breast cancer" to patient PMH) does not
  sit in the notices-but-cannot-type cell: once the wrong experiencer is seen,
  `FABRICATED_HISTORY` is the natural correct type and the judge names it. Its value is on the
  NOTICE axis (lexical false-clears, because the term is present under a family subject), a
  provenance/attribution verification check, not the is-a type-rescue that defines the thesis.

## The prune (a contrast, not a sibling)

- **Value / dose drift** (`VALUE_MISMATCH`, `WRONG_DOSAGE`) is the one candidate to actively
  reject as a thesis sibling, and saying so strengthens the thesis. It fails (b): a numeric
  substitution is bidirectional, not a directional over-assertion up an ordered axis. It fails
  (d): those codes already exist as prompt-invited Tier-1 judge codes (confirmed live in
  `judge_metric.py` / `compliance_council.py`) and the judge applies them correctly once it
  notices. The judge's weakness here is recall / digit-attention, the INVERSE of upcoding's
  notice-yes / type-no gap, so the floor supplies a recall guarantee (already shipped as
  dosage_grounding), not the typed confirmation the judge cannot produce. Including it as a
  case the floor does NOT rescue is evidence that the floor's value is targeted, not universal.

## Bottom line

Build miscoding first (oracle ships, proven), then severity and status as net-new ordinal and
status oracles. Frame omission separately as the recall gate. Prune value/dose as a
thesis-sharpening contrast. Every family above is by-construction labelable and floor-groundable;
the ranking is by where the judge is weakest, which is where the thesis is strongest.
