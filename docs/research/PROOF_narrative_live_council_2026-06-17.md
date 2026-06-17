# PROOF CAPSULE — NARR-5 D5: a live multi-model council grading a narrative case ($-real, honest-Δ)

> **Proof-capsule convention** (`[[proof-capsule-convention]]`): a doc + (NARR-6) a zyng-narrated video. **Honest-Δ only** — every result below is exactly what the live council did; nothing was tuned to manufacture a win. The zyng video is deferred to NARR-6.

**Date:** 2026-06-17 · **Branch:** `bench-salvage/ws6c-dspy` (not pushed) · **Cycle:** NARR-5 D5 (the owner-approved PAID live run) · **Driver:** `.devloop/prompts/bench-salvage_phaseNARR-5_narrative-demo-offline-cut_driver.md` (v2)

## What ran (live, paid, deliberate)

Three `in_process` v2 Azure council runs driven through the **live BFF** (`:8787`, all 4 services up), under the `storyworld_` workspace (pack `narrative`, `tier:core`), graded in the pack-bound subprocess (`_grade_via_subprocess`). The trio is the default `_ROLE_DEPLOYMENT` roster — **3 distinct Azure deployments**: `risk_judge`→`AZURE_OPENAI_DEPLOYMENT_COUNCIL` (GPT), `policy_judge`→`_MISTRAL_LARGE_3`, `faithfulness_judge`→`_LLAMA_4_MAVERICK`. Run 3 swaps `risk_judge` to `byo-claude` (the local `claude` CLI, tool-less). Each run was issued **once**, no retry.

| # | case | trio | composite verdict | stage | floor blocks | run_id |
|---|---|---|---|---|---|---|
| 1 | `narrative_jinn_silent_degradation` | GPT / Mistral / Llama | **reject** | **BLOCK** | 1 (`SILENT_DEGRADATION`) | `49a87739…` |
| 2 | `narrative_jinn_exposure_clean` | GPT / Mistral / Llama | **approve** | PASS | 0 | `e8846cd3…` |
| 3 | `narrative_jinn_silent_degradation` | **Claude** / Mistral / Llama | **reject** | **BLOCK** | 1 (`SILENT_DEGRADATION`) | `a58cb06c…` |

## The three things this proves (live, honest)

1. **The deterministic floor flips a clean council PASS→BLOCK→reject, LIVE.** On the silent-degradation case (a scene that hit `content_filter` and silently fell back to `source: baseline` yet shipped as final), the `SILENT_DEGRADATION` floor injected a BLOCK (`conforms=false`, `disposition=VIOLATION`) → composite **reject**. This is the SPEC §5 day-one headline, now proven on a real multi-model live run (not just the offline subprocess test).

2. **The council does not always-block.** The clean case graded **approve** (PASS, 0 floor blocks, 0 active findings) — the floor + council are discriminating, not a rubber stamp.

3. **Per-judge model swap is real and record-visible.** `risk_judge` confidence went **0.970535 (Azure GPT, run 1) → `None` (BYO-Claude, run 3)** — the tool-less Claude-CLI LM returns no logprobs, the record-visible signature of an actual per-judge model swap (cf. `[[byo-claude-provider-thesis]]` S-BS-94's `None→0.998808`). Same case, same lens, only the model changed.

## The strongest honest-Δ point — the floor corrects a *model-dependent* judge

`risk_judge`'s own verdict on the silent-degradation case **changed with the model**: **WARN on Azure GPT (run 1) → PASS on BYO-Claude (run 3)**. The LLM judge disagreed with itself across models. **Yet the deterministic `SILENT_DEGRADATION` floor caught it on BOTH runs → reject either way.** This is the moat thesis demonstrated live: a hand-wavy / model-dependent judge is corrected by the by-construction floor. (`faithfulness_judge` also fired independently — `BODY_CONTRADICTION` on run 1; `BODY_CONTRADICTION` + `PERSONALIZATION_MISS` on run 3.)

## Honest gaps / caveats (reported, not hidden)

- **S-BS-97 (per-judge-model provenance not surfaced):** the run record labels each vote's `.model` with the **role name** (`"risk_judge"`), and `deployment`/`provider` are `null`. So the "3 distinct models" claim is evidenced by (a) the `_ROLE_DEPLOYMENT` wiring + the D3 offline seam proof, and (b) the `0.97→None` confidence-swap signature — **NOT** by the record's `model` field. Surfacing the real deployment per vote is the S-BS-97 fix (NARR-6 / a provenance cycle).
- **Cost not surfaced (NEW seam, S-BS-NARR5-1):** `provenance.cost_tokens` returned `{prompt:0, completion:0, total:0}` for all three `in_process` subprocess runs. The runs were genuinely paid (17.3s / 15.5s / 25.8s of real Azure latency + heterogeneous model outputs), but the token/$ accounting is not wired for the subprocess grade path — so the exact spend is not captured here. Estimate: ~8 Azure judge calls (low single-digit $) + 1 $0 Claude-CLI call.
- **`LENGTH_VIOLATION` did NOT fire** — expected: these are silent-degradation / clean cases, not over-length-preamble scenes. The REAL live `LENGTH_VIOLATION` positive-catch (`S-BS-NARR4-1`) needs a genuine over-length scene + a real `policy_judge` LM call; it remains the open obligation (D4 proved it offline via a predictor mock).
- **`policy_judge` (Mistral) returns `confidence: None`** on every run (WARN both times) — a real model-behavior signal (no logprobs surfaced), not a bug.

## Reproduce
```
# all 4 services up; .env carries the 3 Azure deployments; claude CLI on PATH
curl -X POST :8787/v1/workspace -d '{"name":"storyworld_"}'          # narrative pack
# create an agent over the case (GET /v1/agent/template -> repoint dataset.case_id -> PUT /v1/agent)
curl -X POST :8787/v1/run-eval -d '{"agent":"narrative_sd","in_process":true}'   # PAID
# swap: PUT /v1/judges/risk_judge {"model":"byo-claude"} ; re-run -> risk_judge confidence: None
```
Run artifacts: `out/narr5_d5/run_{silent_degradation,clean,byoc_swap}.json` (not committed — local run output).

## Disposition
NARR-5 D5 is the visceral live moment, captured honestly: the floor flip is live, the multi-model swap is real and record-visible, the floor corrects a model-dependent judge, and the clean case approves. Two honest gaps (S-BS-97 model-provenance, S-BS-NARR5-1 cost-not-surfaced) and one open obligation (S-BS-NARR4-1 real LENGTH_VIOLATION catch) are recorded, not papered over. The polished browser walkthrough + zyng video are NARR-6.
