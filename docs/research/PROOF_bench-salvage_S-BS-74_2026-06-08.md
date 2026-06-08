# Proof — bench-salvage S-BS-74: the grounding floor is a correct no-op on a clean negative the live council already approves; the engineered flip did NOT reproduce (2026-06-08)

> A-LIVE attestation. Env: :8787 BFF / :8002 council (v2 trio). $≈0.01 (one paid call, 26,115 tokens, wall ~25.9s). **Honest-Δ: a DOCUMENTED LOSS — recorded as a loss, not a manufactured win.**

## Claim

S-BS-74 engineered a by-construction **clean-negative** scribe case to make the live prompt-council over-fire `MEDICATION_NOT_IN_TRANSCRIPT` on a medication that is verbatim in the transcript, so the post-hoc `ground()` presence-check would disprove+suppress it and the composite would flip **BLOCK→PASS / reject→approve** — the visceral "watch grounding correct a confidently-wrong judge" demo.

**What this run actually proves:** the live council (risk/policy/faithfulness, all v2) **unanimously approved** the clean case with **zero findings**. No judge over-fired MED — so there was **no confidently-wrong judge for the floor to correct**. The composite is `approve`, but it was **already `PASS` pre-grounding**; grounding was a **correct no-op** (`0 suppressed by contract`). **The flip did not reproduce because there was no false positive.** The floor mechanism is therefore *unexercised-but-correct* here, and remains proven elsewhere (offline twin + the prior live suppression in run `8a41ef3e`).

## What changed

- Commits (branch `bench-salvage/ws6c-dspy`; **not pushed**):
  - `3c48cb2` — feat: the clean-negative case `examples/s_bs_74_med_overfire_demo.jsonl` + the demo agent `data/config/agents/s_bs_74_demo.json`
  - `c3e7dcb` — test: the offline floor-flip `tests/test_s_bs_74_live_correction.py` (suppression-attributable, both loci) + a one-line committed-seed-manifest update in `tests/test_crud_delete.py` (the additive agent makes `/v1/agents` return a third seed)
  - `docs(s-bs-74)` (this capsule + the run blob)
- Mechanism / files (REUSED as-is — no grading logic changed):
  - The committed `med-presence-check/v1` contract in `data/ontology/clinical_v1.json` (BYTE-UNTOUCHED) and `ground()`/`composite()` in `lithrim_bench/harness/`.
  - `taxonomy_snapshot.json` + the frozen consensus seam BYTE-UNTOUCHED.

## Before → After

| dimension | intended (the demo) | actual (this live run) |
|---|---|---|
| live council on the clean case | over-fires `MEDICATION_NOT_IN_TRANSCRIPT` (a lone MEDIUM FP) | **unanimous PASS, 0 findings** (risk/policy/faithfulness) |
| pre-grounding composite | `BLOCK` (held only by the MED FP) | **`PASS`** (nothing fired) |
| `ground()` presence-check | disproves the FP → `1 suppressed` | **`0 suppressed`** (nothing to suppress) |
| post-grounding composite | flip → `approve` | `approve` — but a **no-op**, not a flip |
| verdict Δ caused by grounding | reject → approve | **none** (PASS → PASS) |

The honest delta: **no flip.** The intended correction never had an FP to correct.

### Why (diagnosis, INFERRED from the two run blobs)

The `8a41ef3e` MED over-fire appears **context-dependent**. There the faithfulness_judge was already in "this artifact is full of unsupported content" mode — the case carried an injected `Diabetes mellitus type 2` plus a 20-item PMH absent from a ~5-line transcript — and swept the medication line in alongside the genuine `FABRICATED_HISTORY`. To avoid the documented held-block risk (the `policy_judge`'s `FABRICATED_CONSENT` + the null-code hallucinations that held `8a41ef3e` at WARN), S-BS-74 stripped the artifact to spotless-faithful — and **that removed the MED FP's trigger too**. A clean case that invites *only* the MED FP is a narrower target than the blob suggested. Corroborating: KB retrieval returned **0 matches** this run (all namespaces failed), so the `policy_judge` had no HIPAA chunk to anchor a `FABRICATED_CONSENT` FP to either.

## Evidence (grounded, not narrated)

- Run id: `6c431bf2-deda-4822-8f24-a77eea705be6` · grade_path `live` · case `bench_s_bs_74_med_overfire_clean_negative_74de0c0117a2`
- Blob: [docs/research/RUN_s_bs_74_live_2026-06-08.json](RUN_s_bs_74_live_2026-06-08.json) (full result + grounded + composite); raw at `out/s_bs_74/live_raw_response.json`
- Council votes: risk_judge PASS (gpt-4.1, conf 1.0) · policy_judge PASS (Mistral-Large-3) · faithfulness_judge PASS (Llama-4-Maverick, conf 1.0) — all `findings: []`
- composite: `0 active finding(s) after grounding; 0 suppressed by contract … Composite stage verdict PASS (was PASS pre-grounding).`
- **The mechanism still stands (proven, not on this run):**
  - Offline, on THIS exact case: `python -m tests.test_s_bs_74_live_correction` → `ground OFF → reject` / `ground ON → approve (suppressed zidovudine)` = `FLIP PROVEN` (suppression-attributable; `ground OFF` = the same `ground()` with the contract removed).
  - Live, prior: run `8a41ef3e` ([RUN_uap5a_a8_live_2026-06-06.json](RUN_uap5a_a8_live_2026-06-06.json)) — the same `med-presence-check/v1` suppressed the same MED FP LIVE (matched_token `zidovudine`), moving BLOCK→WARN (held only because that case had genuine HIGH defects).
- Reproduce the live run: `curl -X POST :8787/v1/run-eval -d '{"agent":"s_bs_74_demo","live":true}'` (paid; no `confirm` field — `/v1/run-eval` has no API cost-gate).

## Journey impact

- Launch-journey phase: **P3 Calibration** (the grounding-correction proof). This run does **not** advance the visceral live demo; it sharpens the target.
- De-risk gap: **#3 grounding floor + withstands-gate.** Net learning: the live "confidently-wrong judge" the floor corrects is **harder to provoke by construction** than the multi-defect blob implied — over-firing is primed by *other* unsupported content, which a clean case lacks. The flip demo likely needs either (a) a near-miss case with a *real* surface mismatch the council mis-reads (brand/generic, abbreviation) that still grounds clean, or (b) accepting the demo lives on the offline twin + `8a41ef3e`'s live suppression rather than a single-FP clean flip.
- Unblocks next (NOT this cycle; monitor's call): the entangled seam **S-BS-70** (the visceral live-flip) should be re-scoped around this finding — a single-FP-on-clean live flip is lower-probability than assumed; consider the near-miss-surface-mismatch construction or a held-block case where suppression flips WARN→PASS.

## Video

Optional per the driver (offline $0). **Not produced this cycle** — honest reason: the run is a no-op/loss, so there is no flip to narrate; a "watch nothing happen" clip has no pitch value. The flip that *is* demonstrable lives offline (`python -m tests.test_s_bs_74_live_correction`) and in the `8a41ef3e` suppression; a future S-BS-70 cut should narrate one of those, or a successful near-miss live flip.

## References
- Driver: `.devloop/prompts/bench-salvage_phaseS-BS-74_live-correction-demo_driver.md`
- Honest-Δ law: `.devloop/templates/PROOF_CAPSULE_TEMPLATE.md`; memory `self-asserting-loop-honesty-moat`, `proof-capsule-convention`
- Prior live evidence: `docs/research/RUN_uap5a_a8_live_2026-06-06.json` (run `8a41ef3e`)
