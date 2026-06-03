# WS-6c-DSPy-3b — DSPy judge-optimizer loop closure (`risk_judge`)

**Date:** 2026-06-03
**Stream / phase:** bench-salvage / WS-6c-DSPy-3b (`judge-optimizer`)
**Driver:** `bench-salvage-phaseWS-6c-DSPy-3b-judge-optimizer-driver`
**Status:** loop **CLOSED + MEASURED** (held-out Δ is **negative** — a valid, reportable closure; the gate was NOT loosened to manufacture a win)
**Cost:** smoke ~$0.067 + full $0.197 ≈ **$0.26** (litellm estimate; one full run; $3 ceiling)

> **This is NOT a paper claim.** It is an engineering loop-closure: it demonstrates
> that `BootstrapFewShot` can compile a judge against the by-construction bench-accept
> metric and that the compiled-vs-baseline held-out delta is *measured*. The numbers
> are small-N, blind-spot-saturated, and captured-not-deterministic (see Caveats).

---

## 1. What ran

The DSPy judge loop is: judges-as-modules → bench-accept metric (`make_judge_metric`)
→ recipe=label corpus (`examples/judge_calib_v1.jsonl`) → **optimize** → **measure**
held-out → **bind back**. The first three existed (WS-6c-DSPy / -3a); this cycle added
the last three for ONE judge, `risk_judge` (the rebuilt-first judge with the most
positives).

- **Corpus split (recipe = label):** calibration → trainset, test → held-out, filtered
  to `risk_judge`'s lens (`RISK_JUDGE_LENS`). Lens-filter (D4): keep a row with an
  in-lens label OR a clean negative; drop other-lens-only rows.
  - **trainset = 12** (7 in-lens positives + 5 clean negatives)
  - **held-out = 10** (7 in-lens positives + 3 clean negatives)
- **Optimizer:** `dspy.teleprompt.BootstrapFewShot`, `metric =
  make_judge_metric(lens_codes=RISK_JUDGE_LENS, co_raise_aware=True)`,
  `max_bootstrapped_demos=4`, **`max_labeled_demos=0`**.
  - `max_labeled_demos=0` is deliberate: our corpus examples carry the *metric label*
    (`expected_safety_flags`), **not** gold `JudgeSignature` outputs
    (`decision`/`findings`/`reason`), so labeled demos are degenerate in dspy 3.2.1 —
    only bootstrapped demos (real traced signature I/O, kept iff the exact-accept gate
    passes) are valid few-shot exemplars here.
- **Both arms scored identically** via `score_judge` on the held-out split, through the
  SAME `JudgeProgram.forward` (which runs the production `_validate_findings`), so the
  delta reflects the production-faithful findings a bound-back `Judge` would emit.
- **LM:** `azure/gpt-4.1` (risk_judge's `AZURE_OPENAI_DEPLOYMENT_COUNCIL`),
  `temperature=0`, `logprobs=True`, reached via the council `settings`/`dspy.LM`
  (not the :8002 service). **24 Azure calls** total for the full run.

Artifacts (captured live, this directory):
`compiled_demos_dspy3b_risk_judge.json`, `score_baseline_dspy3b_risk_judge.json`,
`score_optimized_dspy3b_risk_judge.json`, `result_dspy3b_risk_judge.json`.

---

## 2. Held-out Δ (risk_judge, n=10)

| metric    | baseline (uncompiled) | compiled (4 demos) |     Δ |
|-----------|----------------------:|-------------------:|------:|
| graded    |                  0.80 |               0.70 | −0.10 |
| precision |                0.7143 |             0.4444 | −0.27 |
| recall    |                0.7143 |             0.5714 | −0.14 |
| tp/fp/fn  |                 5/2/2 |              4/5/3 | fp +3, tp −1, fn +1 |
| accepted  |                 False |              False |     — |

`precision`/`recall` are the **co-raise-aware** figures (S-BS-43): a corroborating raise
of another owner's *expected* code scores neutral, not as an FP — so this precision is
NOT the owner-consistent lower bound.

**The optimization made `risk_judge` worse on held-out.** Per the driver, a measured Δ
— including ≤0 — IS the loop-closure. The loop is "complete" because it is *measured*,
not because it *wins*. No tuning to a positive number was performed.

---

## 3. Why it regressed — CONFIRMED diagnostic

**The 4 bootstrapped demos are all silent (no findings).**

```
demo 0: decision='approve'      finding_codes=[]
demo 1: decision='approve'      finding_codes=[]
demo 2: decision='needs_review' finding_codes=[]
demo 3: decision='approve'      finding_codes=[]
```
(verbatim from `compiled_demos_dspy3b_risk_judge.json`)

`BootstrapFewShot`'s gate is `metric(example, pred, trace=…) → bool(exact)`: a trace
becomes a demo ONLY if the un-compiled judge was per-case **perfect** (0 FP, 0 FN). On
this corpus + judge, the cases the baseline judge nailed exactly were predominantly the
**silent / approve** ones (clean negatives + cases it correctly approved). So all 4
bootstrapped demos teach the judge *when to stay silent* and carry **zero positive
exemplars** of a correctly-raised `WRONG_DOSAGE` / `MISSED_ESCALATION` finding.

The held-out regressions (verbatim, baseline → compiled):

```
bench_scribe_v1_multi_dosage_drift+drop_al...   exp=[MISSING_ALLERGY, WRONG_DOSAGE]
    baseline raised=[WRONG_DOSAGE]              tp=1 fp=0 fn=0   (in-lens label caught)
    compiled raised=[VALUE_MISMATCH]            tp=0 fp=1 fn=1   (lost the TP, spurious FP)

bench_triage_v1_downgrade_disposition_bb15...   exp=[MISSED_ESCALATION]
    baseline raised=[SEVERITY_ESCALATION]       tp=0 fp=1 fn=1
    compiled raised=[SEVERITY_ESCALATION,
                     VALUE_MISMATCH]            tp=0 fp=2 fn=1   (added a spurious FP)

bench_triage_v1_downgrade_disposition_d670...   exp=[MISSED_ESCALATION]
    baseline raised=[SEVERITY_ESCALATION]       tp=0 fp=1 fn=1
    compiled raised=[SEVERITY_ESCALATION,
                     VALUE_MISMATCH]            tp=0 fp=2 fn=1   (added a spurious FP)
```

**INFERRED** (from the demo composition + the regression pattern): few-shotting with
only-silent exemplars did not improve raise-precision and shifted the judge toward
emitting an out-of-lens `VALUE_MISMATCH` (a faithfulness code, never in the risk
trainset). The exact-accept gate is correct (it is exactly BootstrapFewShot's contract),
but on a small mixed corpus where the *positive* cases are the hard ones the judge
doesn't already get perfect, the gate harvests the wrong demos. This is the actionable
finding, not a defect in the loop.

**Standing pre-existing miss (NOT caused by optimization):** on both triage cases the
*baseline* already raises `SEVERITY_ESCALATION` where the recipe label is
`MISSED_ESCALATION` (fn on both arms). That is a baseline judge-prompt elicitation gap,
orthogonal to this cycle — a candidate for a future prompt-authoring / A/B follow-up.

---

## 4. Loop closure — the three added stages, demonstrated

1. **Optimize** — `BootstrapFewShot` compiled a `JudgeProgram` on the 12-case
   calibration split, bootstrapping 4 demos under the exact-accept gate. ✔
2. **Measure** — baseline and compiled programs scored on the 10-case held-out split via
   the SAME `score_judge`, yielding the concrete Δ above. ✔
3. **Bind back** — `bind_compiled_demos(judge, program)` copies `program.predict.demos`
   onto a production `Judge.predict.demos` (same `JudgeSignature`, so demos transfer).
   Mechanism + offline test only this cycle; flipping `build_trio` to load demos by
   default is a production-behavior change → **follow-up (S-BS-48)**. ✔ (mechanism)

The loop is closed: the optimizer runs end-to-end and its effect is measurable. The
*current* effect on `risk_judge` is negative; improving it (positive-exemplar
bootstrapping, MIPROv2, more positives/code) is downstream work, not loop-closure.

---

## 5. Caveats (mandatory)

1. **Small-N.** Held-out n=10 (7 positives + 3 cleans); a single case flip moves
   precision ~0.07. Treat the Δ as directional, not a measurement of optimizer quality.
2. **Precision is the co-raise-aware figure** (S-BS-43), not the owner-consistent lower
   bound; do not compare it to the lower-bound numbers in earlier reports.
3. **Transcript-only blind spot.** The judge sees transcript + artifact only; the
   clean-negative false-blocks and the `MISSED_ESCALATION` vs `SEVERITY_ESCALATION`
   confusion are saturated by the absence of patient-record grounding (the grounding
   track's whole motivation). Per-judge precision here is not the council's verdict.
4. **NOT a paper claim.** Captured live (gpt-4.1, temp=0, cache on, but cross-run Azure
   nondeterminism remains); these numbers calibrate the *engine*, they are not a result
   for `docs/PAPER_OUTLINE.md`.

---

## 6. Follow-ups opened

- **S-BS-48** — bind-back into the production trio by default (`build_trio` loading
  compiled demos) is a production-behavior change; deferred to its own cycle.
- **S-BS-49** — the exact-accept gate harvests only already-perfect (here: silent) demos
  on a small mixed corpus, yielding zero positive exemplars and a held-out regression.
  Candidate fixes: a demo-selection metric that requires positive coverage, MIPROv2,
  a teacher with higher raise-recall, or more positives/code. The risk-judge
  `MISSED_ESCALATION`/`SEVERITY_ESCALATION` baseline confusion is the prompt-side twin.
