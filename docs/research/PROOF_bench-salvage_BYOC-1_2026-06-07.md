# PROOF CAPSULE — BYOC-1: BYO-Claude as a live council judge (the model-composition lab)

> **Seam:** S-BS-94 (the conv-UI 1-Claude-2-Azure mixed-council A-LIVE, owed USER-RUN). **Date:** 2026-06-07.
> **Driver:** monitor, user cost-authorized (the D-F USER-RUN gate discharged). **Honest-Δ only** — an honest non-flip is documented as a non-flip; no manufactured win.
> **Evidence:** `docs/research/RUN_byoc1_alive_2026-06-07.json` (+ live run ids `259c2121…` / `53b76c50…`, audit actor `monitor@byoc-1-alive`).

## The claim under test
BYOC-1 made BYO-Claude (the local `claude` CLI, no API key) a first-class **tool-less** provider for the council's judges. The owed live proof: a real in-process council where one judge runs on BYO-Claude, assembled per-judge, and the **model-composition effect is measured** against the all-Azure baseline on the same case — driven through the live BFF (`:8787`, restarted/`--reload`'d on the committed BYOC-1 code; `claude` on PATH).

## What ran (live, `ws0_default`, case `bench_scribe_v1_inject_condition`)
Same case, same `policy_judge` (Mistral) + `faithfulness_judge` (Llama); **only `risk_judge`'s model swapped**, each run a real paid in-process council:

| run | risk model | risk vote | risk confidence | risk findings | composite |
|---|---|---|---|---|---|
| `259c2121` | **byo-claude** | PASS | **`None`** | — | **BLOCK** |
| `53b76c50` | gpt-4.1 | BLOCK | **`0.998808`** | FABRICATED_ALLERGY | **BLOCK** |

## Three confirmed facts
1. **BYO-Claude ran live (CONFIRMED).** `risk_judge` confidence went `None` (BYO-Claude — Anthropic exposes no logprobs) → `0.998808` (gpt-4.1 — logprobs) when only its model was swapped. The delta is **isolated to the swapped seat**: `policy_judge` stayed `None` (Mistral, no logprobs) and `faithfulness_judge` stayed `1.0` (Llama) across both runs. risk did **not** error-fallback (vote was a real PASS, not `needs_review`) → the tool-less `claude -p` judge executed.
2. **The model-composition effect is real + measured (CONFIRMED).** Swapping only the risk model changed its **vote** (PASS ↔ BLOCK), its **findings** (gpt-4.1 raised `FABRICATED_ALLERGY`; BYO-Claude did not), and its **confidence** (`None` ↔ `0.998808`). This is the "swap-a-model-and-measure lab," working live.
3. **Honest-Δ: the verdict does NOT flip.** Both runs → **BLOCK**, because `faithfulness_judge` raises `FABRICATED_HISTORY` + `INCOMPLETE_DOCUMENTATION` in **both** (the case's gold defect is FABRICATED_HISTORY). So BYO-Claude did **not** change the outcome here — this is documented as a non-flip, not dressed up as a win.

## Honest wrinkle (a finding, not a result)
gpt-4.1's `FABRICATED_ALLERGY` is **not** the case's by-construction injected defect (which is `FABRICATED_HISTORY`, per the WS-0 baseline). So gpt-4.1's finding looks like an **over-fire** that the BYO-Claude judge **avoided** — i.e., on this case BYO-Claude may be *more precise* on the risk lens. We do **not** crown a winner here: scoring each model's risk lens against the by-construction gold is exactly the measurement the model-composition lab now enables (a follow-up, not claimed as proven).

## Seam opened
- **S-BS-97 (low/med):** the run-provenance blob does **not** record the per-judge model/provider — the swap had to be proven via the confidence delta + judge order. For a model-composition lab (and auditability), the blob should tag each judge's resolved model/provider.

## Capsule
- Doc: this file. Evidence: `docs/research/RUN_byoc1_alive_2026-06-07.json`.
- Video: `out/zyng_narrate/byoc1_composition_alive_narrated.mp4` (RENDERED — 96.7s, 5 segments + `.srt` captions; zyng **offline** = `$0` silent preview proving visuals+timing; elevenlabs voice is an optional follow-on). The mp4 is gitignored/on-disk per convention; this doc is the tracked artifact. Honest-Δ script — "the verdict held; the composition effect is visible at the judge level; no manufactured win."

S-BS-94 **discharged** (the live mixed-council attestation ran; honest composition result captured). Baseline restored (`risk_judge.model=gpt-4.1`).
