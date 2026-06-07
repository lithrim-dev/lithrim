# NOTE — BYO-Claude judge: the tool-less A-SAFE recipe + confidence-without-logprobs

**Date:** 2026-06-07 · **Cycle:** BYOC-1 (`bench-salvage`) · **Status:** ratified design note
**Code:** `lithrim_bench/runtime/council/byo_claude_lm.py` · seam `judges_dspy.build_judge_lm`
**Proof behind it:** `docs/research/REPORT_byo_claude_provider_2026-06-06.md` (the 5 live de-risks)

This note ratifies BYO-Claude as a **first-class Lithrim provider** (a judge / generation LM,
selectable per-judge and platform-wide) and records the two load-bearing design decisions the
HARD-GATE turned on: the **tool-less A-SAFE recipe** and **confidence without logprobs**.

## 1. The provider, in one paragraph

`build_judge_lm` is provider-aware: when a judge's `model` field (or the global
`LITHRIM_LLM_PROVIDER`) selects `byo-claude` / `claude-cli`, it returns `ClaudeCliLM` — a
`dspy.BaseLM` whose `forward` shells the customer's local `claude -p` (subscription / desktop
auth, **no API key**); otherwise the existing Azure `dspy.LM` path is byte-unchanged. The council
already binds three different models (GPT / Mistral-Large-3 / Llama-4-Maverick); this extends it
**cross-provider**. `build_trio(models=)` threads a per-role selector so a council can run **1
BYO-Claude + N Azure** — the model-composition lab. This completes the airgapped/BYO trust thesis:
one provider (the customer's own Claude) can now power conversation **and** judging **and**
generation.

## 2. The tool-less A-SAFE recipe (load-bearing) — live-verified 2026-06-07

`claude -p` is Claude *Code*: Bash/Read/Write are enabled by default, and ASAFE-1 / S-BS-90 proved
an agent under `bypassPermissions` **will** run them (a host-username leak). A judge LM is a
**completion, not an agent**. The bound is three layers, each verified live:

| Layer | Flag | What it stops | Live evidence (2026-06-07) |
|---|---|---|---|
| **L1 no execution** | `--tools ""` | the model has zero built-in tools — it cannot execute one | tool-baiting judge prompt → `num_turns==1`, `permission_denials==[]` |
| **L2 no agentic priming + no env leak** | `--system-prompt "<neutral>"` | replaces the agentic prompt **and** excludes the dynamic env (cwd/username/git) sections | bare `--tools ""` alone leaked the host username (`aregee`) into the completion; adding `--system-prompt` → `NO_TOOLS_AVAILABLE`, no leak |
| **L3 isolation** | `--strict-mcp-config` · `--setting-sources ""` · `--no-session-persistence` | no MCP servers, no inherited `~/.claude` settings/allow-rules, no on-disk session | — |

**Never** `--dangerously-skip-permissions` / `--permission-mode bypassPermissions` (the S-BS-90
hole). **Never `--bare`** — it forces `ANTHROPIC_API_KEY` / apiKeyHelper auth and never reads
OAuth/keychain, so it breaks BYO-Claude subscription auth (`is_error:true, "Not logged in"`). The
prompt rides **stdin**, never argv, so a long judge prompt can't hit `ARG_MAX` and no prompt
content can masquerade as a CLI flag.

**The test (two tiers).** The load-bearing guarantee is the **argv construction** (`$0`,
deterministic): `build_toolless_argv()` always carries `--tools ""` + a neutral `--system-prompt`
+ the isolation flags and never a forbidden flag (`tests/test_byoc_provider.py`). The **live
behavioral** check (a tool-baiting prompt stays clean) is the cost-gated USER-RUN attestation, not
CI — the same posture as ASAFE-1's allowlist-bounds test.

## 3. Confidence without logprobs (honesty — D-E)

Anthropic models expose **no token logprobs**, the axis the council's calibrated confidence reads
(`extract_verdict_confidence` = the verdict token's `exp(logprob)`). `ClaudeCliLM.forward` returns
a `ModelResponse` **with no logprobs**, so:

> A BYO-Claude judge reports **`confidence = None`** — logprob-confidence *unavailable on this
> provider* — **not** a synthesized or self-reported float.

This is **byte-consistent with the existing Mistral path** (`supports_logprobs=False`): the council
already runs a no-logprob judge today and never coerces `None → float`. `judges_dspy` explicitly
names a self-reported `confidence` output field "the self-report anti-pattern this avoids"; we do
**not** add one. **Azure stays the logprob/calibration option; both are selectable per-judge** — so
when the calibration trainer (the product) needs logprob confidence, that judge is bound to Azure.
Sampling-based confidence (N samples → agreement rate) is a possible future axis; it is **not**
built this cycle, and would be surfaced as a distinct, labelled metric — never as a logprob.

## 4. Cost honesty

Each `claude -p` reports a `total_cost_usd` (~$0.03 for a trivial call). That is a
**subscription-equivalent estimate**, not an incremental charge: **$0 out-of-pocket on a Claude
subscription** — consistent with `apps/bff/agent/loop.py`'s `COST_LABEL`
("subscription-equivalent estimate — not a per-call charge"). In a **mixed council** the BYO-Claude
judge is $0-incremental; the **Azure contrast judges** are the real paid surface, so the live
mixed-council demo (A-LIVE) is cost-confirm-gated and USER-RUN.

## 5. Selecting the provider

- **Per-judge:** set the judge `model` field to `byo-claude` — via `PUT /v1/judges/{role}` or the
  conversational `author_judge` tool (the selector resolves NB-2: a conversationally-authored judge
  can now bind BYO-Claude). The BFF threads `{role: model}` into `run_eval.run(models=)` → the
  authored in_process trio.
- **Platform-wide:** `LITHRIM_LLM_PROVIDER="claude-cli"` → every judge binds `ClaudeCliLM`.
  **Scope:** this switch governs the **DSPy judge path** (`build_judge_lm`). The OpenAI-direct
  client factory (`llm_provider.get_sync_openai_client`, used by the v1 prompt-council / kb-search)
  still requires `openai`/`azure`; a `claude-cli` adapter for that factory is a separate follow-on
  (the jute-transform generator track reuses the same `ClaudeCliLM`).

## 6. Future: the same LM is the DSPy generation provider

`ClaudeCliLM` is also the BYO-Claude DSPy provider for the parked jute-transform generator (the
`lenador` ingestion track) — a sibling follow-on that REUSES this module unchanged. Out of scope
for BYOC-1.
