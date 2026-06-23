# PROOF — single-provider BYOK: the multi-judge council grades live on one OpenAI key

**Date:** 2026-06-23 · **Cycle 1 (the tryability gate)** · commit `d8f2b86` · branch `bench-salvage/ws6c-dspy`
**Honest-Δ:** an honest WIN — a genuine 10× dose error, caught by a real-API council. No manufactured result.

## Claim under test

`LITHRIM_LLM_PROVIDER=openai` + `OPENAI_API_KEY` runs the **full 3-judge council** (risk / policy /
faithfulness + consensus + **calibrated confidence**) on **one provider, one key** — no Azure trio —
while preserving the multi-council (per-role models) and the logprobs calibration axis that BYO-Claude
loses.

## Setup (live)

- Provider forced to `openai`; key = the local `.env` `OPENAI_API_KEY` (a real `sk-…` project key).
- Healthcare pack (`../lithrim-pack-healthcare`) for the real role prompts + lenses.
- Per-judge LM binding (offline, $0):

```
risk_judge          -> openai/gpt-4o   logprobs=True
policy_judge        -> openai/gpt-4o   logprobs=True
faithfulness_judge  -> openai/gpt-4o   logprobs=True
```

## The case (an obvious Tier-1 violation)

```
transcript: Provider: 5 mg lisinopril daily.
artifact:   Plan: lisinopril 50 mg once daily.    # 10x WRONG_DOSAGE
```

## Result (3 real OpenAI calls via evaluate_dspy)

```
consensus decision: reject
artifact_verdict:   BLOCK
confidence:         0.977          # calibrated — from the model's own logprobs
decision_counts:    {reject: 2, approve: 1}
tier1_triggered:    WRONG_DOSAGE  (risk_judge + faithfulness_judge), evidence-driven
evidence_spans:     "5 mg lisinopril daily." vs "Plan: lisinopril 50 mg once daily."
```

## What this proves

1. **BYOK works end-to-end** — the council grades a real case on one OpenAI key, no Azure deployments.
2. **The multi-judge council is intact** — 3 independent judges + the frozen consensus mechanism
   (`_apply_consensus`, byte-frozen vs `acc4973`) composed the verdict; 2/3 caught the Tier-1 violation.
3. **Calibrated confidence survives** — `0.977` is a real probability read from logprobs (ON for the
   OpenAI path), the differentiator over BYO-Claude (which returns `None`).
4. **The change stayed inside the authorized seam** — `build_judge_lm` body + a module constant; the
   seam-freeze guard is 0-delta (the moat is untouched).

## Repro

```
LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_LLM_PROVIDER=openai \
  python /tmp/byok_live_attest.py     # forces provider=openai; reads OPENAI_API_KEY from .env
```

(Offline unit proof: `tests/test_byok_openai.py` — 6 tests, $0.) A narrated zyng video capsule can be
added on request; the loop here is non-interactive (a script), so the doc + the captured output is the
primary record.
