# REPORT — BYO-Claude as a first-class Lithrim LLM provider (a model-composition lab)

**Date:** 2026-06-06 · **Status:** research / live de-risk capture (5 spikes, all `$0` or noted) · **Owner:** monitor (bench-salvage)
**Branch:** `bench-salvage/ws6c-dspy` (NOT pushed). Authored alongside a concurrent session (ONB-0/ASAFE-1) — see "Coordination."

## TL;DR
BYO-Claude can be a **first-class Lithrim provider** — usable as a judge's model, platform-wide for generation, and (already) for the conversational shell. Proven live across five spikes against a real second domain (the `lenador`/my_story_world children's story-gen product). The integration seam is **one function** (`build_judge_lm`). It **completes the airgapped/BYO trust thesis** (today the chat is BYO-Claude but the *judges* are Azure-locked) and turns the council into a **swap-a-model-and-measure lab**. Two honest caveats gate it: Claude has **no logprobs** (the calibration-confidence axis), and `claude -p` is Claude *Code* (tools enabled) → the judge/generation LM must run **tool-less** (rhymes with the concurrent ASAFE-1 finding).

## Motivating use case (the domain-agnostic test)
`lenador` story sessions (`/api/admin/sessions`) = real, non-clinical LLM I/O (prompts, responses, story artifacts, scenes). A second non-clinical pull (after the insurance-extraction signal). Pitch under test: *"drop a dump → set up a judge → run → eval-pack,"* domain-agnostic.

## The five live de-risks
1. **jute is a general JSON normalizer (not FHIR-only).** A hand-written JUTE template normalized a real lenador session → a Lithrim case shape live on `:3031/mappings/test-template`. Corrects an earlier mischaracterization; the harness already wraps it (`verification/etlp_client.py`).
2. **The generation layer is bench-owned; the mapper just executes.** `jute_dspy.py` docstring: *"This REPLACES the etlp-mapper Copilot's `POST /mappings/generate` loop … the generate→test→refine loop is OURS (`forward`), the feedback is the live `:3031/mappings/test-template`."* `:3031`'s openapi confirms no `/mappings/generate`. The loop is **artifact-general** — validator today, transform is a sibling signature + metric.
3. **Our tooling auto-generates the normalization (not hand-written).** A generate→`test-template`→refine loop, predictor = **BYO-Claude CLI cold** (given only the DSL excerpt + a target schema + a sample; no access to the hand-written template), **converged on iteration 1** and extracted `llm_prompts` / `llm_responses` / `story_content` / `scenes` / `enhanced_scenes` — inferring real field names (`prompt`, `response_preview`) itself.
4. **DSPy runs on BYO-Claude (no API key).** `ClaudeCliLM(dspy.BaseLM)` (≈30 lines; `forward` shells `claude -p`, returns a litellm `ModelResponse`). `dspy.Predict` → `42`; `dspy.ChainOfThought` ran. The standardized DSPy path (Predict/ChainOfThought/optimizers) runs unchanged, `$0`. **Also:** the bench has **Azure** (the council's `.env`: `AZURE_OPENAI_DEPLOYMENT_COUNCIL` etc.) as a faster, parallelizable second LM — `dspy.LM(f"azure/{dep}", …)`. So two interchangeable providers.
5. **A Lithrim judge runs on BYO-Claude — and the composition effect is visible.** A real `risk_judge` (`judges_dspy._build_signature()`) graded a defect-bearing scribe case on BYO-Claude (`$0`, no Azure), producing structured output: `decision="needs_review"`, finding `{taxonomy_code: "FABRICATED_ALLERGY", evidence_spans:[…]}`. The by-construction gold was `FABRICATED_HISTORY → reject`. **Same case, a different model in the seat → a different verdict + finding, measured against the gold.** That is the model-composition lab, demonstrated in one run.

## The seam (where BYO-Claude plugs in)
- **`build_judge_lm(role, **overrides)`** (`runtime/council/judges_dspy.py:205→232`) is the single seam — today hardwires `dspy.LM(f"azure/{deployment}")`. Make it provider-aware: model/provider `byo-claude` → return `ClaudeCliLM`; else the Azure path.
- **`_ROLE_DEPLOYMENT`** (`:65`) already binds **three different models** (`risk_judge`→GPT, `policy_judge`→Mistral-Large-3, `faithfulness_judge`→Llama-4-Maverick) — the council is *already* a cross-model panel; this extends it cross-provider.
- **The judge `model` field** already exists (`app.py:622`; the conversational `author_judge` hardcodes `model=""` — the NB-2 carry). It becomes the **selector** ("create a judge with model `byo-claude`"). NB-2 resolves into this feature.
- **`LITHRIM_LLM_PROVIDER`** (`settings.py:30`) is the global switch — add `"claude-cli"` for a platform-wide BYO-Claude.

## Strategic synthesis
- **Completes the airgapped/BYO trust thesis.** Today: chat = BYO-Claude, judges = Azure-locked → "no keys, fully airgapped" is not actually true. This closes it — one provider (the customer's own Claude) powers conversation + judging + generation. No Azure, no API keys.
- **The council becomes a model-composition lab** — swap a judge's model and *see + score* the divergence against by-construction labels.
- **Unparks the DSPy generation track** on a real provider (the `dspy-jute-prompt-builder-deferred` blocker — "no demonstrable provider / not e2e" — both halves fell).

## Honest caveats (load-bearing)
1. **No logprobs.** `build_judge_lm` runs `temperature=0 + logprobs=True` for the council's calibrated-confidence; Anthropic models don't expose logprobs. A BYO-Claude judge is **verdict-capable + airgapped but loses logprob-confidence** — and the *calibration trainer is the product*. Needs a non-logprob confidence (self-report / sampling). Azure stays the option when logprob-calibration is wanted; **both, selectable.**
2. **Tool-less requirement (safety).** `claude -p` is Claude *Code* — tools (Bash/Read) are enabled. The spikes were benign text-gen, but the productionized `ClaudeCliLM` (judge + generation LM) **must run tool-less** (no agent surface). This rhymes with the concurrent **ASAFE-1 / S-BS-90** finding (an agent under `bypassPermissions` ran `Bash`); the judge/generation LM is a *completion*, not an agent, and must be constrained accordingly.
3. **All spikes, uncommitted.** Nothing is wired into `verification/` or the frozen council; this is a de-risk capture, not a shipped feature.

## Proposed cycle
**BYOC-1 — BYO-Claude first-class provider / model-composition lab** (driver: `.devloop/prompts/bench-salvage_phaseBYOC-1_byo-claude-provider_driver.md`). Deliverables: productionize `ClaudeCliLM` (tool-less) → provider-aware `build_judge_lm` + the judge-`model` selector → the `$0` Claude-judge (proven) → the **conv-UI-driven mixed-council composition demo** (cost-gated Azure for the contrast = the A-LIVE) → the global `LITHRIM_LLM_PROVIDER=claude-cli` → the logprob-confidence design note.

## Coordination (concurrent session)
Authored while a concurrent session is mid-cycle on `bench-salvage` (ONB-0 + ASAFE-1 landed; `index.json`/`TASK_PACK`/`MONITOR.md` dirty). This report + the BYOC-1 driver are **new files**, committed pathspec-only; **registering BYOC-1 in `index.json`/`TASK_PACK` is DEFERRED** until the active session's edits to those files land. New seams should start **≈S-BS-92** (active session holds S-BS-90/91).
