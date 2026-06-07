# Proof — bench-salvage ASAFE-1: honesty as the moat — the live run caught our own A-SAFE hole (2026-06-06)

> A-LIVE attestation capsule (per `.devloop/templates/PROOF_CAPSULE_TEMPLATE.md`). **This is the
> honest find→fix capsule.** Env: `:8787` BFF + isolated `ClaudeSDKClient`, BYO-Claude. $0 (BYO subscription).

## Claim
Across four cycles we *asserted* the conversational agent was bounded to its 8 safe `mcp__lithrim__*`
tools — "it can never spend." The **ONB-0 live run falsified that** (S-BS-90): the agent reached for a
built-in shell tool and ran a command on the host. ASAFE-1 makes the floor **real** — a fail-closed
tool-layer deny gate — and an independent critic proved it **live, in both directions**.

## What changed
- **Commits** (`bench-salvage/ws6c-dspy`, not pushed): `6446615` PreToolUse deny gate + SDK isolation ·
  `b4ff9d3` offline fail-closed deny-hook unit + relabel the value-tests · `777512a` docs + live
  evidence · `f56d6f2` session log.
- **Mechanism:** a fail-closed `PreToolUse` hook (`_deny_non_lithrim`) returns `permissionDecision:
  "deny"` for any tool not `mcp__lithrim__*` (the only SDK mechanism that gates *every* call regardless
  of `bypassPermissions`); plus `setting_sources=[]`/`skills=[]` so the loop no longer inherits the
  user's `~/.claude` settings. The 8-tool surface + memory threading are byte-untouched (A6 0-delta).

## Before → After
| dimension | before (S-BS-90) | after (ASAFE-1) |
|---|---|---|
| the floor | `allowed_tools` + `bypassPermissions` = persona-only (allowlist not a bound) | tool-layer deny gate (enforced) |
| a `Bash` request | **executes** — leaks host username `aregee` | **denied** at the tool layer — no output |
| `get_agent` / `run_eval` | work | still work (under isolation) |
| the A-SAFE claim | asserted (stub tests only) | enforced + proven live |

## Evidence (grounded, not narrated)
- **The decisive A/B (fresh critic `a26d74ab`, live, built from the SHIPPED `_build_options`):**
  - WITH the hook: the non-lithrim built-in → `ToolResultBlock is_error=True` with the hook's deny
    reason, **no output, host username never leaked**; `get_agent` succeeded.
  - WITHOUT the hook (parallel control, identical otherwise): the agent emitted `Bash` → it
    **executed**, `is_error=False`, output `ASAFE_NOHOOK_aregee` — **username leaked.**
  → confirms the finding *and* that the hook is the load-bearing floor.
- **Gates:** monitor 7-item audit CLEAN; HARD-GATE fresh-critic NON-BLOCKING [0 / 2 NB / 1 OQ].
  Non-vacuity: scratch-revert the deny branch → 4 offline tests fail. A6 0-delta (frozen surface +
  ONB-0 threading byte-identical). **27 passed** / Vitest 52 / ruff clean.
- Blobs: `docs/research/RUN_asafe1_live_2026-06-06.json` (executor's `Bash`+`Read` denials) ·
  `.devloop/sessions/critique-bench-salvage-phaseASAFE-1-2026-06-06.md` (the critic's A/B).
- Origin: `docs/research/FINDING_S-BS-90_asafe_bypass_2026-06-06.md` (RESOLVED).

## Journey impact
- **The trust wedge made real.** "The agent can never spend / the host is safe" is now an *enforced*
  property, not a prompt persona — the local-first/BYOK trust claim (`gtm-launch-and-journey-thesis`)
  is defensible.
- **The honesty moat, demonstrated** (`self-asserting-loop-honesty-moat`): the value isn't that we were
  never wrong — it's that **running it live catches what the proofs miss, and we fix it in the open.**
  Four cycles + four critics passed a stub-based A-SAFE test; the first real multi-tool turn caught it.
- **Method correction:** A-SAFE allowlist *value* tests are necessary-but-insufficient; the *enforced*
  floor (the deny gate, proven live) is the real check. Carried into the docs.

## Video
- `out/zyng_narrate/asafe1_findfix_narrated.mp4` (+ render) — the find→fix narration (mode: card-based,
  since the demonstration is a tool-layer A/B, not a UI flow). Honest-Δ: it narrates the *hole we found*
  and the *fix*, not a clean pass.
