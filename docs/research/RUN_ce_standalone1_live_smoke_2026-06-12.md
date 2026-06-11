# RUN — CE-STANDALONE-1 live smoke (A-STANDALONE-5): the standalone generic CE, LIVE

**Date:** 2026-06-12 · **Type:** A-LIVE PAID (real Azure v2 trio, in-process authored path) · **Cost:** ~$2 (two fires — the first's grade succeeded but a display bug lost the per-judge detail; one clean re-fire).
**Pack:** `support_ticket_qa` (the CE-STANDALONE-1 independent non-clinical pack) · **Healthcare:** unloaded · **Provider:** Azure v2 (openai/mistral/meta).
**Owed since:** CE-STANDALONE-1 (the env-gated live confirmation; CI used a mock LM).

## Invocation
`LITHRIM_BENCH_PACK=support_ticket_qa` + the authored path **without** injected predictors → `build_authored_semantic_stage(ontology, assignments={role: pack_lenses()[role]})` → real trio via `build_judge_lm` → `grade_inprocess` → `ground` → `composite`. Each production judge assigned its non-clinical pack lens.

## Result

```
VERDICT: reject | composite score: 1.0
  risk_judge          vote=BLOCK    findings=['UNSUPPORTED_COMMITMENT']  conf=1.0
  policy_judge        vote=WARN     findings=[]                          conf=None
  faithfulness_judge  vote=BLOCK    findings=['UNRESOLVED_ISSUE']        conf=0.992422
clinical-needle leakage in the live judge OUTPUT: (none)
```

## Findings (honest-Δ)

1. **Standalone CE LIVE-PROVEN.** A non-clinical case grades to a correct `reject` through the REAL authored path on real Azure LLMs, with the healthcare pack unloaded (`active_pack()=="support_ticket_qa"`). The CI proof (mock LM) + this live run together attest the demonstrable standalone generic CE.
2. **S-BS-129 did NOT degrade the live grade.** The core DSPy `JudgeSignature` (`_build_signature`) still carries clinical prose ("clinical/patient/HIPAA"), and on the live path it reaches the LLM. Yet the real judges raised ONLY the pack's non-clinical codes and the output had **zero clinical-needle leakage**. So the signature residue is real (and stays a 6b-CLEAN cleanup target for purity) but the live evidence shows **no signature-induced degradation** on this non-clinical grade. (NOT overclaimed: one case; a clinical signature confusing a different domain remains plausible — worth re-checking when 6b lands.)
3. **Code-attribution Δ (calibration, not a failure).** The case was planted (by-construction) to flip on `policy_judge` raising `FABRICATED_POLICY` (the CI mock predictor did exactly that). LIVE, `policy_judge` WARNed with no finding; instead `risk_judge` (`UNSUPPORTED_COMMITMENT`) + `faithfulness_judge` (`UNRESOLVED_ISSUE`) BLOCKed. The **verdict is correct** (`reject` — the reply IS a bad fabricated-refund-policy answer), but via DIFFERENT codes than the planted label. This is the verdict-deterministic / finding-code-dispersed phenomenon (the dispersion study) — exactly what the calibration trainer surfaces, and an honest demonstration that by-construction labels ≠ live judge attribution.

## Disposition
A-STANDALONE-5 **DISCHARGED**. The standalone generic CE produces a sane live verdict on a non-clinical domain with healthcare absent. S-BS-129's live impact: **none observed on this grade** (residue still cleaned in 6b for purity). Honest-Δ recorded: the live code attribution diverged from the by-construction label while the verdict held.
