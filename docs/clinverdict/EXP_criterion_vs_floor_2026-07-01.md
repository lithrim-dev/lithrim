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
