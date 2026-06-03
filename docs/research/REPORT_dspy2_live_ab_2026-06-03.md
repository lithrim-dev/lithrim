# REPORT — Live prompt-vs-DSPy council A/B (WS-6c-DSPy-2-live)

- **Date:** 2026-06-03
- **Stream / phase:** `bench-salvage` / `WS-6c-DSPy-2-live`
- **Driver:** `bench-salvage-phaseWS-6c-DSPy-2-live-ab-run-driver`
- **Arms:** control = imperative prompt-council (`ComplianceCouncil.evaluate`); treatment = DSPy-rebuilt council (`build_trio()` → `evaluate_dspy`), the v2 trio (risk_judge / policy_judge / faithfulness_judge).
- **Case set:** `examples/proof_case.jsonl`, n=7 (3 clean negatives + WRONG_DOSAGE / MISSING_ALLERGY / FABRICATED_HISTORY / VALUE_MISMATCH defects), recipe=label.
- **Run:** ONE captured live run, real Azure fan-out (gpt-4.1 + Mistral-Large-3 + Llama-4-Maverick), temperature=0. 42 chat completions, 390.9s. Raw diff record: [`ab_result_dspy2_live_2026-06-03.json`](ab_result_dspy2_live_2026-06-03.json).

> ## ⚠️ Read the caveats before any number below
>
> 1. **Per-judge precision/recall are a LOWER BOUND (S-BS-43).** The lens is owner-consistent, so a judge's *correct* corroborating raise of another owner's code counts as an out-of-lens false positive. Absolute per-judge precision here is **not** the judge's true precision.
> 2. **This is a captured snapshot, not a deterministic fixture.** Live LLMs vary run-to-run even at temperature=0; re-running will not reproduce these byte-for-byte.
> 3. **n=7 is small.** Report the comparison; claim nothing beyond what 7 cases support. Do **not** read this as "DSPy beats / matches the prompt-council."
> 4. **The transcript-only blind spot dominates this set (the load-bearing caveat).** The proof_case artifacts are FHIR clinical notes carrying PMH / record content the short transcripts never speak. Transcript-only judges (both arms) therefore flag that legitimate record content as `FABRICATED_HISTORY` / `INCOMPLETE_DOCUMENTATION` on nearly every case — including the clean negatives. So (a) the clean negatives systematically false-reject, and (b) every judge's lens score is flooded with out-of-lens `FABRICATED_HISTORY` noise. The absolute precision numbers are a lower bound *of a blind-spot-saturated run*; only patient-record grounding (not in this council) would clear it. This is a known, not-paper-changing finding — it is the very gap the bench exists to surface.

---

## Headline (as of this run)

| Metric | Value |
|---|---|
| Verdict agreement (prompt vs DSPy) | **85.71%** (6/7) |
| Divergent cases | 1 — `clean_negative_aef8bc9c0cca` (prompt=`reject`, dspy=`needs_review`) |
| Confidence calibration (mean signed Δ, dspy−prompt, paired floats) | risk **−0.0042** (n=7); faithfulness **0.0** (n=6); policy **n/a** (Mistral, no logprobs, 0 paired) |
| Cost | 42 calls full run + 6 calls smoke = **48 chat completions**; estimated **≈ $0.75–1.5** (see Cost); **within the $3 ceiling** |

**One-line read:** on this blind-spot-saturated n=7 set the two arms agree on the composite verdict 6/7 times and produce near-identical confidence where both report it; the one material behavioral divergence is the **Mistral policy_judge** (verbose in the prompt arm, silent in the DSPy arm), and the DSPy faithfulness judge caught every in-lens labeled defect where the prompt arm missed one.

---

## Per-arm, per-role lens scores (LOWER BOUND — see caveat 1 & 4)

| Role | Arm | tp | fp | fn | precision | recall |
|---|---|---|---|---|---|---|
| risk_judge | prompt | 1 | 6 | 0 | 0.143 | 1.000 |
| risk_judge | dspy | 1 | 6 | 0 | 0.143 | 1.000 |
| policy_judge | prompt | 0 | 22 | 0 | 0.000 | 1.000 |
| policy_judge | dspy | 0 | 0 | 0 | 1.000 (vacuous) | 1.000 |
| faithfulness_judge | prompt | 2 | 18 | 1 | 0.100 | 0.667 |
| faithfulness_judge | dspy | 3 | 15 | 0 | 0.167 | 1.000 |

The `fp` columns are dominated by out-of-lens `FABRICATED_HISTORY` / `INCOMPLETE_DOCUMENTATION` blind-spot raises, not by judge error — do not read these as precision.

---

## The interesting divergences (the real A/B signal)

1. **policy_judge (Mistral) is the load-bearing divergence.** The prompt-arm Mistral raises out-of-lens codes (`FABRICATED_HISTORY`, `INCOMPLETE_DOCUMENTATION`, sometimes `WRONG_DOSAGE`/`WRONG_CODE`) on **all 7** cases (fp=22). The DSPy-arm Mistral raises **nothing** on all 7 (fp=0). Same model, same deployment, same `.strip()`-identical role prompt (S-BS-44 closed) — the difference is the elicitation path (the prompt-council's monolithic `build_prompt` vs the DSPy signature). This is a genuine, reproducible-direction behavioral gap worth a closer look in DSPy-3; it is not explained by the blind spot.

2. **DSPy faithfulness recall ≥ prompt on the labeled defects.** On `drop_allergy` (label `MISSING_ALLERGY`) the DSPy faithfulness judge raised `MISSING_ALLERGY` (in-lens, correct); the prompt faithfulness judge did not (it raised `FABRICATED_HISTORY`/`HALLUCINATED_DETAIL`/`INCOMPLETE_DOCUMENTATION` instead) → prompt faithfulness fn=1, dspy fn=0. The labeled defects `WRONG_DOSAGE`, `FABRICATED_ALLERGY`, `VALUE_MISMATCH` were caught by both arms.

3. **The lone verdict divergence** (`clean_negative_aef8bc9c0cca`): prompt arm rejects (all 3 judges raise `FABRICATED_HISTORY`), DSPy arm lands `needs_review` because its policy and faithfulness judges raised nothing on that case while risk raised only `MEDICATION_NOT_IN_TRANSCRIPT` — i.e. the DSPy arm's quieter Mistral + faithfulness left it short of a one-strike. A clean-negative `needs_review` is "less wrong" than `reject`, but on n=1 this is anecdote, not a trend.

4. **Confidence is essentially uncalibrated-apart between arms** — risk mean Δ −0.0042, faithfulness 0.0. The DSPy rewrite did not shift judge confidence where it is observable (both are logprob-sourced; gpt-4.1/Llama report, Mistral does not — its `None` round-trips uncoerced in both arms).

---

## S-BS-42 (policy PHI prompt-naming) — not measurable here

`PHI_DISCLOSURE_PRE_VERIFICATION` (the policy lens's prompt-unnamed sole-owned code) did not appear in any proof_case, so this run cannot measure the predicted recall gap. Still open; needs a case that carries it.

## A3 frozen contract

`compliance_council.py` byte-identical vs the pre-cycle tip `c0a5463` (re-verified, diff = 0). No change to `_apply_consensus`, consensus tables, grade-wire, or lenses. The A/B is a standalone measurement over `evaluate` + `evaluate_dspy`.

## Cost

48 Azure chat completions total (6-call smoke + 42-call run). Prompts ≈ 30.8k chars ≈ ~7.7k input tokens/call; outputs are short findings JSON. Estimated **≈ $0.75–1.5** at Azure list prices (gpt-4.1 / Mistral-Large-3 / Llama-4-Maverick) — the council does not surface per-call metered usage to the harness, so this is a size-based estimate, not a billed figure. Comfortably **within the authorized $3 ceiling**. ONE run; no second run.

## Bottom line

The harness works end-to-end against real LLMs; the S-BS-44 parity gate and the D-1 payload fix hold on live data. On this n=7 (blind-spot-saturated) set the two councils agree 6/7 on the verdict with near-identical confidence — the prompt-vs-DSPy delta is concentrated in the **Mistral policy judge's verbosity** and a small **faithfulness-recall edge for the DSPy arm**. None of this is a paper claim; it is the first real measurement of the comparison the WS-6c-DSPy-2 substrate was built to make, and it confirms the substrate is sound while flagging the policy-judge divergence and the transcript-only blind spot as the two things to chase next (DSPy-3 + the grounding track).
