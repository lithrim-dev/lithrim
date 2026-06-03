# RUN — JUTE generate → test → enforce (live), 2026-06-03

**The JUTE north star, demonstrated live.** Define a contract → our DSPy generator authors the Jute
validator → test it locally against the by-construction pack via `:3031 /mappings/test-template` →
the **bench-gate** (not the LLM's confidence) accepts or rejects → persist as an etlp mapping and
apply via its id. Auditable, reproducible, and honest about where generation fails.

- **Tool (yours):** `.claude/worktrees/agent-adefc36309f77ed1b/experiments/dspy_council_smoke/jute_dspy_smoke.py`
  (branch `spike/verification-toolbox`). Report: `…/REPORT_jute_dspy_generator.md`.
- **Substrate:** live `:3031` (etlp-mapper, 92 mappings) + Azure `gpt-4.1` (council deployment).
- **Contract:** `US_CORE_PATIENT_RULES` — identifier/name/gender REQUIRED; birthDate OPTIONAL but
  format-checked when present.
- **Bench-gate (the oracle):** `fhir_boundary_pack_v1.jsonl` — 10 by-construction cases; ACCEPT iff
  0 false-positives, 0 compile errors, all 6 structural defects blocked.
- **Reproduce:** `.venv/bin/python jute_dspy_smoke.py --copilot-attempts 3 --n 2 --max-iters 3`

## Result (live, verbatim)

| authoring path | pack result (10 cases) | accepted? |
|---|---|---|
| seeded `fhir-patient-validator` id 23 (the Copilot few-shot anchor) | caught 5/6 · **FP=1** | ❌ |
| raw etlp Copilot `POST /mappings/generate`, 3 attempts | a1 `conf=high` 0/6 **ERR=9** · a2 6/6 · a3 **HTTP 400** | ❌ **1/3** |
| **DSPy generator (best-of-2, refine≤3)** — generate→test-template→refine on real error | iter0 ERR=10 → iter1 ERR=10 → **iter2 6/6 · 0 FP/ERR** | ✅ |
| DSPy + BootstrapFewShot single-shot (1 demo) | caught 0/6 · **ERR=10** | ❌ |
| **DSPy accepted → persisted mapping id 101 → applied via `/mappings/101/apply`** | **6/6 · 0 FP/ERR** | ✅ |

## Findings (tagged)

- **CONFIRMED — the bench, not the LLM's confidence, decides trust.** The raw Copilot's *first*
  attempt self-reported `confidence='high'` and produced **9 compile errors / 0 caught**; a single
  `(sample, expected)` oracle would have shipped it. The 10-case pack rejected it.
- **CONFIRMED — the raw Copilot is unreliable: 1/3 accepted** (one 400, one all-errors-but-confident,
  one good). Generation cannot be trusted on faith; it must be gated.
- **CONFIRMED — the refine-on-real-error loop is what converges.** DSPy iters 0–1 ERR'd (YAML syntax
  slips); feeding the live engine error back fixed them and iter 2 hit 6/6 · 0 FP/ERR. The LLM's
  *logic* was right early; only the syntax needed the loop. (Matches `jute-runtime-builtin-gap`: the
  served DSL spec lies about builtins, so generated validators MUST be live-tested.)
- **CONFIRMED — honest negative: single-shot BootstrapFewShot is insufficient** here (0/6, ERR=10).
  One bench-verified demo does not make one-shot generation reliably emit valid JUTE for this
  syntax-sensitive grammar. The refine loop, not the demo, is the load-bearing piece.
- **CONFIRMED — the accepted validator is a live, applicable artifact:** persisted as mapping
  **id 101**, re-scored through `StructuralJuteTool({by:title})` via `/mappings/101/apply` → 6/6.

## Why this is the local north star

It is the third calibration lever, end to end and live: **plain-English contract → generated Jute →
local bench-gate → enforce (persist + apply)**. Paired with the prompt lever (non-monotonic, see
`RUN_calib_progression_2026-06-03`) and the deterministic grounding floor (`dosage_grounding`), it
completes the honest calibration story: prompts are unreliable, the generated-and-bench-gated
structural validator is enforceable and reproducible. The agents build toward running this loop live
in the product (journey M4) and on the paper thesis.
