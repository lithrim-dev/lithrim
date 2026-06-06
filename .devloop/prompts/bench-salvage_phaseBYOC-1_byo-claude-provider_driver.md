# Driver — `bench-salvage` phase `BYOC-1`: BYO-Claude as a first-class LLM provider (a model-composition lab)

> **Bundle ID:** `bench-salvage-phaseBYOC-1-byo-claude-provider-driver`
> **Version:** v1 · **Authored:** 2026-06-06 · **Last re-verified against code:** 2026-06-06
> **Capture:** `docs/research/REPORT_byo_claude_provider_2026-06-06.md` (the 5 live de-risks behind this cycle)
> **⚠️ REGISTRATION DEFERRED:** authored during a concurrent session (ONB-0/ASAFE-1; `index.json`/`TASK_PACK` dirty). Register this bundle in `index.json` + `TASK_PACK` AFTER the active session's edits to those files land. New seams start **≈S-BS-92** (active session holds S-BS-90/91).

---

## KICKOFF (paste into a fresh executor session)

```
You are the EXECUTOR for the .devloop/ cycle: bench-salvage phase BYOC-1 — make BYO-Claude a
first-class Lithrim LLM provider (selectable per-judge + platform-wide), turning the council into a
model-composition lab. The capability is already PROVEN live (5 spikes; see the capture report) —
this cycle PRODUCTIONIZES it.

WHAT'S PROVEN (do not re-litigate, see docs/research/REPORT_byo_claude_provider_2026-06-06.md):
  - ClaudeCliLM(dspy.BaseLM) — dspy.Predict/ChainOfThought run on `claude -p`, $0, no API key.
  - A real risk_judge graded a scribe case on BYO-Claude, $0, structured findings — and gave a
    DIFFERENT verdict than the by-construction gold (the composition effect, visible).
  - The seam is ONE function: build_judge_lm (judges_dspy.py:205→232). _ROLE_DEPLOYMENT already
    binds 3 different models (GPT/Mistral/Llama) — this adds a Claude role, cross-provider.

TWO LOAD-BEARING SAFETY/HONESTY CONSTRAINTS:
  1. TOOL-LESS LM. `claude -p` is Claude *Code* (Bash/Read enabled). The ASAFE-1 finding (S-BS-90,
     concurrent session) proved an agent under bypassPermissions ran Bash. A judge/generation LM is a
     COMPLETION, not an agent — ClaudeCliLM MUST invoke claude tool-less (disable tools / restrict to
     none), and a test must PROVE a judge prompt cannot trigger a tool call. This is the A-SAFE gate.
  2. NO LOGPROBS. build_judge_lm runs `logprobs=True` for the council's calibrated confidence;
     Anthropic models don't expose logprobs. A BYO-Claude judge loses logprob-confidence (the
     calibration axis). Do NOT silently drop it — surface it; Azure stays the logprob option; both
     selectable. Decide the non-logprob confidence approach at plan-review (D-E).

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseBYOC-1_byo-claude-provider_driver.md  (this doc)
  3. docs/research/REPORT_byo_claude_provider_2026-06-06.md  (the proofs + the seam)
  4. lithrim_bench/runtime/council/judges_dspy.py (build_judge_lm:205, _ROLE_DEPLOYMENT:65, _build_signature:175)
     + llm_provider.py (the provider switch) + settings.py (LITHRIM_LLM_PROVIDER:30)
  5. apps/bff/agent/loop.py (the ASAFE-1 _deny_non_lithrim PreToolUse hook — the pattern for ANY conversational-loop touch)
  6. .devloop/state/STREAM_bench-salvage.md (skim; coordinate — concurrent session active)

Post plan-review per EXECUTOR.md. Resolve D-A..D-F. Do not write code until "go".
DIRTY SHARED BRANCH + CONCURRENT SESSION: pathspec-only commits; never bare-commit; verify scope with
`git diff <parent> HEAD --stat`; do NOT touch the active session's dirty files (index.json/TASK_PACK/MONITOR.md).

Bundle ID: bench-salvage-phaseBYOC-1-byo-claude-provider-driver
```

---

## 0. Why
The whole pitch/de-risk arc converges here. Today the **conversational shell** runs BYO-Claude (the Agent SDK) but the **judges are Azure-locked** — so "no keys, fully airgapped" isn't actually true. Making BYO-Claude a **first-class provider for judges + generation** closes that gap (one provider — the customer's own Claude — powers conversation + judging + generation) and turns the council into a **swap-a-model-and-measure lab**. Every load-bearing piece is already proven live (the report); this cycle wires it into the real surfaces honestly.

## 1. Pre-flight (citations re-grepped 2026-06-06)
- **The seam:** `runtime/council/judges_dspy.py` — `build_judge_lm(role, **overrides):205→232` (today `return dspy.LM(f"azure/{deployment}", …, logprobs=True)`); `_ROLE_DEPLOYMENT:65` (risk→COUNCIL, policy→MISTRAL_LARGE_3, faithfulness→LLAMA_4_MAVERICK); `_build_signature():175` (JudgeSignature: transcript/artifact/role_key_questions/taxonomy_context → decision/findings/reason); the judges bind their LM at `:347 lm=build_judge_lm(role)`.
- **The provider switch:** `runtime/council/llm_provider.py` (`_current_provider`/`_resolve_model` — azure/openai-direct) + `settings.py:30 LITHRIM_LLM_PROVIDER`.
- **The judge `model` field (the selector):** `apps/bff/app.py:622` (put_judge); the conversational `author_judge` hardcodes `model=""` (`app.py:946`, the NB-2 carry).
- **The proven `ClaudeCliLM`** (the report): `dspy.BaseLM` subclass; `forward` shells `claude -p`, returns a litellm `ModelResponse`.
- **The ASAFE-1 deny-hook** (concurrent S-BS-90 fix): `apps/bff/agent/loop.py` `_deny_non_lithrim` `PreToolUse` — the pattern any conversational-loop touch inherits.

## 2. Deliverables (file-by-file)
**D1 — `ClaudeCliLM`, productionized + TOOL-LESS** (a provider module, e.g. `lithrim_bench/runtime/council/byo_claude_lm.py` or `verification/`): the `dspy.BaseLM` over `claude -p`, **invoked tool-less** (disable all tools; the LM is a completion, not an agent). Robust: timeout, error surface, the litellm `ModelResponse` shape, DSPy cache. Import-isolated (claude SDK/CLI not pulled into default deps).
**D2 — provider-aware `build_judge_lm`** (the ONE intended council change): if the role's `model` (or the global `LITHRIM_LLM_PROVIDER`) selects `byo-claude` → return `ClaudeCliLM` (tool-less, no logprobs); else the existing Azure path **byte-unchanged**. Thread the judge `model` field → the provider. (Resolves NB-2: a conversationally-authored judge can now bind `byo-claude`.)
**D3 — the `$0` Claude-judge test** (offline/`$0`): a `risk_judge` (or any role) bound to `ClaudeCliLM` grades a real scribe case → a valid `decision`/`findings`/`reason` (proven in the spike; make it a committed test, predictor-injectable for hermeticity).
**D4 — the mixed-council composition demo** (the headline; A-LIVE, cost-gated): the council with ONE role on BYO-Claude + the others on Azure, vs the all-Azure baseline, on the same case → the per-judge votes + composite **differ** → the model-composition effect, **measured against the by-construction gold**. Driven from the conversational UI (`assemble_agent`/the model selector). **Paid (Azure for the contrast judges) → cost-confirm-gated.**
**D5 — the global switch:** `LITHRIM_LLM_PROVIDER="claude-cli"` → judges + generation run BYO-Claude platform-wide (`llm_provider.py` + `settings.py`).
**D6 — docs + the logprob-confidence design note:** how a BYO-Claude judge reports confidence WITHOUT logprobs (self-report / sampling — D-E); ratify the provider in the spec; session log. Note: the same `ClaudeCliLM` is the DSPy provider for the future jute-transform generator (the lenador ingestion track).

## 3. Plan-review decisions
- **D-A.** The tool-less `claude` invocation (the exact mechanism to disable tools) + the test that proves a judge prompt can't trigger a tool call. **Load-bearing (A-SAFE).**
- **D-B.** Which role goes BYO-Claude for the demo (candidate: `risk_judge`), and the all-Azure baseline contrast.
- **D-C.** The A6 scope: `build_judge_lm` is THE intended change; `_apply_consensus` + the JudgeSignature + the judge decision logic + the seam dict stay byte-identical. Confirm.
- **D-D.** The judge `model` field → provider mapping (`byo-claude` value; how `author_judge`/the selector set it).
- **D-E.** Confidence without logprobs (self-report vs sampling vs "confidence unavailable on this provider"). Don't fake a logprob.
- **D-F.** The D4 cost envelope (paid Azure for the contrast judges) — confirm + gate.

## 4. Scope guardrails — NOT in scope
- **The conversational tool surface** — BYOC-1 is the *provider/judge LM*, not new chat tools. **If anything touches `apps/bff/agent/loop.py`, it inherits the ASAFE-1 deny-hook + a live-canary** (S-BS-90); prefer not to touch it.
- **A hosted/multi-tenant Claude** — BYO-Claude/desktop only (the licensing guardrail).
- **The jute-transform generator** (lenador ingestion) — a sibling follow-on that REUSES `ClaudeCliLM`; not this cycle.
- **FROZEN (A6, except `build_judge_lm`):** `_apply_consensus` + the per-judge seam dict + `judge_metric` + `authored_stage` + the `JudgeSignature` + the committed seeds + the existing BFF ops. The ONE intended council touch is `build_judge_lm`.
- Touching the active session's dirty files (`index.json`/`TASK_PACK`/`MONITOR.md`); drive-by formatting.

## 5. Acceptance
- **A1.** A judge runs on BYO-Claude end-to-end (`decision`/`findings`/`reason`), `$0`, no Azure — committed test.
- **A2.** The selector works: a judge with `model="byo-claude"` binds `ClaudeCliLM`; an Azure judge is byte-unchanged.
- **A-SAFE (load-bearing).** The BYO-Claude LM is **tool-less** — a judge/generation prompt cannot trigger a tool call (negative-tested); if the conversational loop is touched, the ASAFE-1 deny-hook + live-canary apply.
- **A3 (the headline).** The mixed council (1 BYO-Claude + N Azure) produces a **measurably different** verdict/votes vs all-Azure on the same case, scored against the by-construction gold (the composition effect). (A-LIVE, cost-gated.)
- **A4 (honesty).** Confidence-without-logprobs is **surfaced**, not faked (D-E); the report/spec states the BYO-Claude judge's confidence semantics.
- **A6.** `git diff` over the frozen set (excl. the intended `build_judge_lm` change) == 0; Azure path byte-unchanged.
- **A5/A7.** Import-isolation; green bar (default + debuglithrim + Vitest + ruff); pathspec-only; no pushes; the active session's dirty files untouched.
- **A-LIVE (BLOCKING, USER-RUN, cost-gated).** The conv-UI-driven mixed-council demo on `:5180`/`:8787` — talk → assemble a council with a Claude judge → run → see the votes diverge.

## 6. Commit structure (atomic, pathspec-only — concurrent session live)
1. `feat(council): ClaudeCliLM — BYO-Claude as a tool-less dspy.LM (no API key)`
2. `feat(council): build_judge_lm provider-aware — byo-claude judge LM (Azure path byte-unchanged)`
3. `test(byoc-1): a risk_judge grades on BYO-Claude ($0) + the tool-less A-SAFE negative test`
4. `feat(council): LITHRIM_LLM_PROVIDER=claude-cli (global) + the judge model selector`
5. `docs: ratify the BYO-Claude provider + the logprob-confidence note; session log`
**Verify each:** `git diff <parent> HEAD --stat` shows ONLY your files; never the active session's `index.json`/`TASK_PACK`/`MONITOR.md`.

## 7. Verification checklist
- [ ] A-SAFE: the BYO-Claude LM is tool-less (negative-tested a judge prompt can't call a tool)
- [ ] A1/A2/A3: judge-on-BYO-Claude works; selector binds it; mixed-council diverges vs all-Azure (gold-scored)
- [ ] A4: confidence-without-logprobs surfaced, not faked
- [ ] A6: frozen set 0-delta except the intended `build_judge_lm`; Azure path byte-unchanged
- [ ] import-isolation + green bar; pathspec-only; active session's dirty files untouched; no pushes
- [ ] new seams numbered ≥S-BS-92 (coordinate with the active session)

## 8. First move
1. Read EXECUTOR.md + the capture report + the seam (`build_judge_lm`/`_ROLE_DEPLOYMENT`/`_build_signature`).
2. Reproduce the `$0` Claude-judge (the report has the recipe) so the build sits on a proven base.
3. Resolve D-A (tool-less mechanism — the A-SAFE crux) first; post plan-review.

## 9. References
- Capture: `docs/research/REPORT_byo_claude_provider_2026-06-06.md`
- Seam: `runtime/council/judges_dspy.py` · `llm_provider.py` · `settings.py`
- Safety pattern: the concurrent **ASAFE-1 / S-BS-90** deny-hook (`apps/bff/agent/loop.py _deny_non_lithrim`)
- Memory: `byo-claude-provider-thesis` · `zyng-claude-cli-provider` · `conversational-authoring-surface-complete` (the ASAFE-1 correction) · `git-commit-pathspec-dirty-index`

## Hardness
- [x] **HARD GATE** — fresh-critic required. *Reason: introduces a new LLM provider into the council (the eval's load-bearing judges) + a tool-less-LM A-SAFE property + a confidence-semantics change (no logprobs) that touches the calibration product; the ONE intended council change (`build_judge_lm`) must be proven scoped (rest byte-frozen). Live runs are cost-gated (Azure contrast).*
