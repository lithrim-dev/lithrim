# Experiment: can a pure LLM criterion line fix HALLUCINATED_DETAIL? (2026-07-01)

**Question (owner):** instead of a hardcoded floor, can the SME just write a natural-language
criterion into the judge prompt and have the LLM self-correct? Measured on the 173-case
`clinverdict_mts_v1` corpus.

## Baseline (fixed-floor, before the criterion)

```
OVERALL  P=22.9%  R=42.4%   (TP=56 FP=189 FN=76)
HALLUCINATED_DETAIL    9.0% precision  100% recall   (7 TP, 71 FP, 0 FN)   ← worst offender
FABRICATED_CLAIM      18.5% precision   83% recall   (15 TP, 66 FP)
```

## The SME criterion (natural language, added to `faithfulness_judge.txt`)

> A fabricated detail is always a POSITIVE, ABNORMAL clinical assertion. Two note forms are
> therefore NOT hallucinations: (a) a VITALS/MEASUREMENT line (a wrong number is VALUE_MISMATCH);
> (b) a NEGATED/NORMAL/ABSENT finding ('no focal deficits', 'unremarkable', 'within normal
> limits'). Raise HALLUCINATED_DETAIL ONLY for a positive abnormal finding the transcript never
> contained.

Live on the next grade (clinverdict grades via a fresh subprocess import — no restart).

## Result

**Safety — PASS.** All **7/7 true positives still fire** HALLUCINATED_DETAIL. The criterion did
not blind the judge to any real fabrication. (The 7 TPs are positive abnormal findings; 3 are
named verbatim in the criterion as must-fire.)

**Efficacy — WEAK lever.** On a 12-case FP sample, only **2/12** dropped HALLUCINATED_DETAIL —
and even those 2 are inside k=3 sampling noise, so the criterion produced **no attributable FP
reduction**. Diagnosis via the flagged spans:

| FP case | what faithfulness flagged as HALLUCINATED_DETAIL | form |
|---|---|---|
| cv_mts_161 | `"PMH: - Migraine with aura"` | history-term **subsumption bait** |
| cv_mts_158 (clean-neg) | whole objective paragraph incl. `"3+ pitting edema"` + normals | **grounding** error (real finding wrongly called fabricated) |

## Conclusion

The HALLUCINATED_DETAIL false positives are **not vitals/negation forms** — they are
**grounding and subsumption disagreements** (a real positive finding called fabricated; a history
term subsumed by a documented one). A prompt criterion cannot reliably fix a grounding
disagreement — that is exactly what the **deterministic grounding floor** (SNOMED-subsumption +
transcript-presence) exists for.

**So: pure LLM criterion writing is SAFE but marginal here.** It's a good free add (kept), but it
is not the report-mover. The report-mover for this flag is the deterministic floor. This re-proves
the thesis empirically: *the judge prompt is a soft lever; the floor is the moat.*

## Next

The real lever is confirming the SNOMED-subsumption / transcript-grounding floor is **live** on
these grades — cv_mts_161's "Migraine with aura" subsumption bait survived, which the floor should
suppress (and `:3031` was down at test time). Measure criterion-only vs criterion+floor on the
full 173 as the customer-facing contrast.

---

# Follow-up: the clean baseline + the FP anatomy + FINDING-UNITS-1 (2026-07-01/02)

## Clean baseline (criterion reverted, one frozen-config pass, 173/173, 0 errors)

Batch-graded via `POST /v1/cases/grade` (in_process, ~34 min, ~12s/case — k>1 sampling rides ONE
native-`n` call with `cache: False`, `sampling.py`). Numbers validated on TWO independent surfaces
(the BFF cohort scorecard == an independent measure off the grade records' `grounded` blocks):

```
PRE-floor  (judges raised):  P=25.5%  R=52.3%   (TP=69 FP=202 FN=63)
POST-floor (grounded/real):  P=27.0%  R=52.3%   (TP=69 FP=187 FN=63)   verdict-acc 132/173
```

Floor effect replicated: 15 FP suppressed (FABRICATED_CLAIM 11, HALLUCINATED_DETAIL 4), **0 TP
loss**. NOTE the earlier mixed-era record measurement (P=24.2 R=42.4) understated recall ~10pts —
never measure across config eras.

## FP characterization (187 post-floor FPs) — the story flips

The precision problem is mostly **attribution double-counting, not over-firing**:

| bucket | n | meaning |
|---|---|---|
| twin-code, same span | **84 (45%)** | the RIGHT defect on the RIGHT span, raised under a sibling code alongside the gold code — the twin scores FP |
| same family, different span | 26 | fabrication-family scatter on a fabrication-gold case |
| defect case, other form | 47 | negation-shaped, self-refuting-evidence, paraphrase |
| gold-CLEAN case over-fire | **30 (16%)** | the only TRUE over-firing |

By groundable FORM (suppress-contract backlog, ranked): **47 self-refuting** (the judge's own
evidence quote is verbatim IN the transcript → evidence-integrity gate), **43 negated/normal**
(negation gate), **~75 lay→clinical paraphrase** ("peeing a lot / always thirsty" → "polyuria and
polydipsia", token overlap 0.0 → concept-level Hermes/SNOMED presence). Recall side: 4 dead codes
(UNSUPPORTED_ASSERTION, MISSED_ESCALATION, STYLE_VIOLATION never raised; INTENT_ERASURE only
wrongly) = a lens coverage gap, not a floor problem.

## FINDING-UNITS-1 — the attribution clerk (shipped)

One defect span = ONE finding unit. Sibling codes from the ontology-declared `code_families`
block that fired on overlapping evidence quotes (token containment ≥ 0.6) consolidate into a
single unit carrying the full code-set. A **clerk, not a critic**: gold-blind, never judges
correctness, never drops a code (invariant-tested), so it cannot lose recall — survivor-PICKING
rules dropped 11–17 golds and were rejected. Computed post-hoc over stored grade records, BESIDE
the byte-frozen consensus moat. Dual-reported (`scorecard.units` next to the strict `flag` block).

```
strict: P=27.0%  R=52.3%   (TP=69 FP=187 FN=63)
units : P=46.3%  R=52.3%   (TP=69 FP=80  FN=63, matched_gold=69 — zero loss)
```

The blind merge reaches the oracle-adjudication ceiling exactly. Implementation:
`lithrim_bench/harness/finding_units.py` + the `/v1/cases/grade` scorecard `units` block;
gate test `tests/test_finding_units.py::test_a6_corpus_gate_*` (runs against the clean-run
snapshot via `LITHRIM_BENCH_CLEANRUN_DIR`).

## The trust ladder (agreed 2026-07-02)

0. **Read layer** — fold `grounded` verdict/findings into the persisted blob; project post-floor
   in `/audit` + `/v1/runs`; wire `cost_tokens` (unwired today). Separate driver.
1. **Attribution** — FINDING-UNITS-1 (this doc). DONE.
2. **Suppress contracts** by measured form: evidence-integrity gate (47) → negation gate (43) →
   concept-level presence via Hermes (paraphrase class). Each corpus-gated: clear FPs, 0 TP loss,
   pinned.
3. **Scope honesty** — author lenses for the 4 dead codes or descope them with a stated reason.
4. **Number honesty** — headline numbers as mean ± range over ≥3 passes, config hash pinned.

## LAYER2-SUPPRESS-1 — corpus-gated suppress contracts by measured form (shipped 2026-07-02)

Ladder step (2), first slice. The prototype (scratchpad `evgate_proto.py` + census) corrected
the plan's own estimate: the FP characterization's "47 self-refuting" was a per-FP
*classification*, not a gate yield — most transcript-verbatim matches are judges quoting the
TRANSCRIPT side as evidence, and on SOURCE_CONTRADICTION / VALUE_MISMATCH that quote belongs to
REAL defects (the any-span rule fires on 11/19 golds → those codes are undeclarable). The hard
corpus gate (clear FPs, touch 0 of the 69 gold TPs, per code) sanctioned exactly three
declarations:

| contract | code | FP cleared | gold touched |
|---|---|---|---|
| `evidence_presence` (any-span verbatim-in-source) | INTERNAL_INCONSISTENCY | 13 | 0/5 |
| `evidence_presence` (any-span verbatim-in-source) | HALLUCINATED_DETAIL | 7 | 0/7 |
| `observation_form` (all spans negation/vitals) | HALLUCINATED_DETAIL | 19 | 0/7 |

Rejected by the gate: negation form on FABRICATED_CLAIM (2 gold hits — the corpus has
fabricated-VITALS golds, cv_mts_166/170: "a fabrication is a positive assertion" is false
there) and on INTERNAL_INCONSISTENCY (1 gold); quote-in-artifact on MISSING_CONTEXT (1 gold).
The corpus is the referee — it both licenses and REFUSES contracts.

**What shipped** (commits 26a000f red → f0cebf3 green):

* `EvidencePresence` — core-generic, pure-stdlib, span-level: a finding whose OWN evidence
  spans are verbatim (normalized) source text refutes itself. Conservative `mode="all"`
  default; declarations opt into `"any"` explicitly.
* **Suppress-contract composition** in `ground()`: a flag_code now declares a CHAIN, run in
  declaration order, first disprove wins; an executor error no longer silences the rest of the
  chain. This unblocked `observation_form` (written 2026-06, never declarable — the
  one-contract-per-code binding had snomed_subsumption occupying HALLUCINATED_DETAIL).
  `Ontology.contracts_for` is the chain read; `contract_for` (the frozen `signals.py`
  withstands binding) stays first-declared byte-identical — the pre-consensus gate challenges
  with the first contract only, the full chain is ground()-side authority.
* Drop-in declarations appended to `packs-dropin/clinverdict/ontology.json` (untracked, like
  the pack): the 3 sanctioned rows above, versions `evidence-presence/v1` / `observation-form/v1`.
* The corpus gate pinned as `tests/test_layer2_suppress.py::test_cg_corpus_gate_39_fps_zero_tp_touch`
  (env-gated on `LITHRIM_BENCH_CLEANRUN_DIR` + the drop-in, A6 pattern): REAL `ground()` +
  the REAL declarations over the 173 stored records → 39 FP / 0 TP, `skipped_malformed == []`.

**Predicted scorecard** (simulation over the clean-run snapshot; the floor's snomed effect is
already in the stored baseline):

```
strict: P=27.0% → 31.8%   R=52.3% unchanged   (TP=69, FP 187→148, FN=63)
units : P=46.3% → 49.3%   R=52.3% unchanged   (FP 80→71, matched_gold=69 — zero loss)
```

Not yet live-verified: the running BFF grades against its own copy of the agent ontology —
the next paid pass (or a re-ingested agent) picks the declarations up; ladder step (4) will
measure the realized numbers. Next slices: a fabricated-vitals-safe negation form for
FABRICATED_CLAIM (21 negation-shaped FPs remain), then the Hermes concept-presence
paraphrase class (~75 FPs) — each through the same gate.

## The measurement pass — realized Layer 2 + the catch (2026-07-02, pass 2)

Fresh full 173-case pass on the rebuilt stack (same frozen multi-council config; 173/173,
0 errors; validated on two surfaces — BFF scorecard == independent measure off the grounded
blocks, byte-equal).

```
pass 2 realized (Layer-2 v1 live): PRE-floor P=26.0 → POST-floor P=29.8  R=51.5
                                   (TP=68 FP=160 FN=64, verdict-acc 137/173)
suppressions: snomed-subsumption/v1 ×15 · observation-form/v1 ×17 · evidence-presence/v1 ×5
```

**The catch — one GOLD suppressed (cv_mts_118).** The judge's span this pass bundled a
negation cue with the injected fabrication in ONE quote — `"O: Alert, no acute distress.
Limited abduction of the right eye on examination."` — and observation-form/v1's whole-span
regex *search* classified it non-fabrication on the negation cue while it carried the
positive fabrication. The single-pass corpus gate could not see this (pass 1's judge quoted
differently); the fresh pass is what caught it. **This is the ladder working:** measure →
catch → tighten → re-gate → pin.

**observation-form/v2 (shipped same day):** every SENTENCE of the span (decimal-safe split;
standalone SOAP-header fragments skipped) must independently be a vitals/negation form.
Re-gated on BOTH passes: 0 golds (v1 touched 1); yield honestly drops 19→4 (pass 1) /
16→5 (pass 2). The tracked corpus-gate pin moves 39→24 (284030a). A suppressed real
fabrication is the worst error class; the yield is the price of the safety bar.

**Honest headline under the current config (v2), strict flag-level, both passes:**

```
P = 29.2% ± 0.5   (pass1 sim 29.7, pass2 sim 28.7)     R = 52.3%  (both passes)
units realized band: P ≈ 44.7–46.3
```

vs the 25.5/26.0 pre-floor baseline: the floor is now worth ~+3.2pts strict with zero gold
loss under the two-pass gate. NOTE: the running BFF caches the pack floors module — the v2
EXECUTOR takes effect on the next BFF restart (the v2 declaration is already synced to the
workspace draft). Contract-gating discipline going forward: gate against ≥2 passes, not one.

## Layer-2c — concept-presence suppress: REFUSED by the referee (2026-07-02, negative result)

The hypothesis: the ~75 low-overlap "paraphrase class" FPs are groundable by SNOMED
concept-presence over Hermes (note "polyuria" ↔ transcript "peeing a lot"). Prototyped
end-to-end against BOTH passes (scratchpad `concept_bridge_proto.py`: exact-term n-gram
concept extraction from the flagged span; bridge = any active SNOMED description of the
concept present in the transcript by substring or content-token containment; numeric guard
for dose/value spans; ~3.7k local Hermes calls, $0):

```
FP pool cleared : 12/235  (~5% — nowhere near the classified 75)
GOLD TPs fired  : 2/49    (HARD GATE: 0 — FAIL)
```

Three independent reasons to refuse, each structural, not tunable:
1. **Mentioned ≠ asserted.** cv_mts_142 (both passes): "The nursing home completed a
   voiding diary" — the fabrication is the EVENT; the concepts all appear in the
   transcript where the diary was merely discussed. Concept-presence cannot see the
   difference.
2. **Polarity-blind.** Most clears sat on contradiction-case twins ("Reports a history of
   tobacco use" vs a transcript denial) — the same mechanism would erase a real
   NEGATION_REVERSAL.
3. **The vocabulary bridge is partial anyway**: hand-set lay→clinical bridging resolved
   3/10 via SNOMED descriptions ("passes too much urine" ≠ "peeing a lot").

The eyeballed pool composition confirms the class is a MIX, mostly judge territory:
certainty inflation ("confirmed by mechanism and presentation"), event assertions,
dose/value forms, chart demographics. **Descoped: the paraphrase class stays with the
judge — this is the owner's scope line ("judge + floor are COMPLEMENTARY") landing in
data.** The corpus refusing a contract is the same moat as the corpus licensing one.

Layer 2 CLOSES with: snomed-subsumption/v1 + evidence-presence/v1 + observation-form/v2,
strict P 25.5/26.0 → 29.2±0.5, R 52.3, 0 gold loss under the two-pass gate. Remaining
precision work is attribution (units, shipped) and judge-side; the next honest lever for
the HEADLINE is the RECALL side — Layer 3, the 4 dead lenses (FN≈63 dwarfs everything
suppression can buy).

## Layer 3 — honest recall accounting (shipped 2026-07-02, LAYER3-DESCOPE-1)

Recall diagnosis (both passes, CONFIRMED): 64 FN, 21 on THREE codes no judge ever emits
(`MISSED_ESCALATION`, `UNSUPPORTED_ASSERTION`, `STYLE_VIOLATION` — absent from raw
votes/evidence/findings). Not a prompt gap (the risk/faithfulness questions already ask) nor
a lens/owner gap (all three are in a reviewer lens) — **taxonomy overlap**: gpt-4.1 codes the
same defect as a salient sibling. Of the 21 gold cases, 17 still BLOCK (caught, miscoded),
4 truly blind.

Owner decisions (2026-07-02): **family-merge UNSUPPORTED_ASSERTION + honest-descope
MISSED_ESCALATION & STYLE_VIOLATION**, and — after the corpus gate surfaced that the broad
`fabrication` family credits more than the UA pair — **credit the full fabrication family**
at unit level (each extra verified as a same-defect sibling catch: a contradiction/date
mismatch coded FABRICATED_CLAIM, the FAB↔HALL twin).

Two engine seams (tracked, no council edit):
* `score_units(..., code_families)` — a gold code is matched when a DECLARED family-sibling
  fired on it (recall mirror of the twin-FP merge; `None` = exact, byte-identical). STRICT
  flag scoring untouched (UA stays a strict FN — the judge never used that code).
* the cohort scorecard filters gold to the agent's GRADEABLE codes (a descoped axis leaves
  the FN denominator, matching grounding's S-BS-10 skip-log) and drops a fully-descoped case
  from `labeled` rather than rescoring it clean (protects verdict accuracy). Drop-in data:
  `code_families.fabrication += UNSUPPORTED_ASSERTION`; `gradeable:false` for the two descoped.

**Realized ledger (pass 2, descope applied — 161 labeled, down from 173 as fully-descoped
cases leave the denominator):**

```
                       precision      recall     matched golds
strict flag             31.3%          57.1%       68            (was 52.3% pre-descope)
unit, exact              48.2%          57.1%       68
unit, family-aware       63.3%          72.3%       86  (+18 vs exact: 7 UA + 11 sibling-caught)
```

Descope lifts strict recall 52.3→57.1 by removing 13 unwinnable FN + the fully-descoped
cases; family-aware unit recall reaches **72.3%** — the honest ceiling of "the defect was
caught, whatever the panel named it." Both reported NEXT TO strict (never replacing it). The
4 truly-blind cases (cv_mts_057/059/085/136) remain honest FN. Not live-verified through the
BFF yet (the draft ontology is synced; next paid pass realizes it). The generic-CE trust
ladder (0 read-layer · 1 attribution · 2 suppress · 3 scope honesty) is COMPLETE; the only
open lever is a real escalation/style reviewer (paid, judge-side — deferred by owner).

## Layer 4 — the headline, honestly formatted (shipped 2026-07-02, LAYER4-HEADLINE-1)

The final rung: the headline is a REPRODUCIBLE SURFACE, not a pasted number.
`lithrim_bench/harness/headline.py` + `scripts/headline_report.py` recompute every banked
pass under the CURRENT scoring config — pre-floor findings − stored service-transport
(Hermes) suppressions − a fresh offline re-ground with the current pure-stdlib contracts —
then apply the Layer-1/3 scoring (descope, units, family credit) and aggregate
mean/min/max/spread per metric, config-signature pinned. Passes graded under superseded
floor versions become comparable: the recompute CORRECTS observation-form/v1's cv_mts_118
gold false-clear, so both passes land strict tp=69.

**THE HEADLINE (2 frozen-config passes, 161 labeled cases each, config `3bf461c210cb14c4`):**

```
strict flag     P 30.1–31.1% (mean 30.6)    R 58.0–58.0% (mean 58.0 — byte-stable)
units (family)  P 61.1–65.7% (mean 63.4)    R 71.4–72.3% (mean 71.8)
n = 2 passes (below the ≥3 target — spread is provisional until pass 3)
```

Journey of the strict numbers across the ladder: P 25.5 → 30.6 (floor + attribution-honest
denominators), R 52.3 → 58.0 (descope), with ZERO gold loss enforced at every rung; the
family-aware unit view — "the defect was caught, whatever the panel named it" — reads
P 63.4 / R 71.8. The 0.0 strict-recall spread across two stochastic passes is a STABILITY
result, not determinism (precision spreads 1.0pt — the floor is deterministic, the judges
are not). Rerun anytime:

    python scripts/headline_report.py --ontology <pack>/ontology.json \
      --corpus <pack>/examples/clinverdict_mts_v1.jsonl --pass-dir <p1> --pass-dir <p2>

The trust ladder (0 read-truth · 1 attribution · 2 suppress · 3 scope · 4 number honesty)
is COMPLETE.
