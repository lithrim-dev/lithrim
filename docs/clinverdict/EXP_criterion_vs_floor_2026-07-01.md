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
