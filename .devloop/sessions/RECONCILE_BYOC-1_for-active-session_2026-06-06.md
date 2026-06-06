# RECONCILE — fold **BYOC-1 (BYO-Claude provider)** into the active cycle before you close

> **FOR:** the active `bench-salvage` session (ONB-0 / ASAFE-1 / pitch-derisk arc).
> **FROM:** a concurrent `bench-salvage` session, 2026-06-06. **Read this before you close your current phase.**
> **ACTION (≈5 min, mechanical):** register the **BYOC-1** bundle + open seam **S-BS-92** during your close-out, so a real, proven de-risk doesn't fall on the floor between our two sessions.

---

## TL;DR
A concurrent session ran a long de-risk thread (lenador story-gen → jute → DSPy-on-BYO-Claude → **BYO-Claude as a first-class LLM provider**), proved it live in 5 spikes, and authored a **report + a HARD-GATE driver (BYOC-1) + a memory** — all committed pathspec-only at **`9f850e3`** (your dirty `index.json`/`TASK_PACK`/`MONITOR.md` were left untouched). The only thing it could **not** do safely was register BYOC-1 in `index.json`/`TASK_PACK` (those were dirty in your tree). **That registration is the reconciliation you do at close** — paste-ready below.

---

## 1. What the concurrent session already did (committed — do NOT redo)
Commit **`9f850e3`** (`docs(bench-salvage): BYOC-1 driver + capture report …`), 2 new files only:
- `docs/research/REPORT_byo_claude_provider_2026-06-06.md` — the 5 live de-risks + the seam + caveats.
- `.devloop/prompts/bench-salvage_phaseBYOC-1_byo-claude-provider_driver.md` — the **BYOC-1** driver (HARD-GATE, `status: ready` once you register it).
- (+ a memory `byo-claude-provider-thesis.md` + a `MEMORY.md` pointer — outside the repo.)

**The proven capability (don't re-litigate — see the report):** `ClaudeCliLM(dspy.BaseLM)` runs `dspy.Predict`/`ChainOfThought` on `claude -p` (`$0`, no key); a real `risk_judge` (`judges_dspy._build_signature()`) graded a scribe case on BYO-Claude with structured findings, giving a **different verdict than the by-construction gold** (the model-composition effect, visible). The seam is **one function** — `runtime/council/judges_dspy.py build_judge_lm:205→232`; `_ROLE_DEPLOYMENT:65` already binds 3 different models, so this is just adding a Claude role cross-provider.

## 2. Why it's only half-wired
Your `index.json` / `TASK_PACK` / `MONITOR.md` were **modified-uncommitted** when BYOC-1 was authored. Per `git-commit-pathspec-dirty-index`, editing/committing them would have swept or clobbered your in-flight ONB-0/ASAFE-1 work. So shared-state registration was **deferred to you** — you own those files right now.

## 3. The reconciliation (do these during your close, pathspec-only)

### 3a. Open the seam — append to the `## Open seams` table in `STREAM_bench-salvage.md`
> Numbering: use **S-BS-92** *if free*. You hold S-BS-90 (ASAFE-1) — if your dirty index/TASK_PACK already claimed 91/92, bump this to your next free id and update the references.

```
| S-BS-92 | **BYO-Claude as a first-class LLM provider (judges + generation; the model-composition lab)** — PROVEN live (5 spikes, `docs/research/REPORT_byo_claude_provider_2026-06-06.md`) but UNWIRED into the frozen council. Seam = `build_judge_lm` provider-awareness (`judges_dspy.py:205`) + the judge `model` field selector (`app.py:622`) + `LITHRIM_LLM_PROVIDER=claude-cli` (`settings.py:30`). | medium | **open — driver BYOC-1 READY** (`bench-salvage_phaseBYOC-1_byo-claude-provider_driver.md`; concurrent-session authored, commit `9f850e3`). Caveats baked in: NO-logprobs (the calibration axis) + the LM must run TOOL-LESS (builds on your ASAFE-1/S-BS-90 finding). Register + run as a cycle. Fix loc: `runtime/council/judges_dspy.py build_judge_lm`. |
```

### 3b. Register the bundle — append to `bundles` in `prompts/index.json`
```json
{
  "id": "bench-salvage-phaseBYOC-1-byo-claude-provider-driver",
  "stream": "bench-salvage",
  "phase": "BYOC-1",
  "scope": "byo-claude-first-class-llm-provider-model-composition-lab",
  "file": "bench-salvage_phaseBYOC-1_byo-claude-provider_driver.md",
  "status": "ready",
  "version": "v1",
  "hardness": "HARD-GATE (a new LLM provider in the council's load-bearing judges + a tool-less-LM A-SAFE property + confidence-without-logprobs; the one intended council change is build_judge_lm, rest byte-frozen; live runs cost-gated). fresh-critic required.",
  "target_repos": ["lithrim-bench"],
  "_note": "BYO-Claude as a first-class provider (judges + generation + conversation). PROVEN live (5 spikes, REPORT_byo_claude_provider_2026-06-06). Seam = build_judge_lm provider-aware + the judge model selector + LITHRIM_LLM_PROVIDER=claude-cli. Completes the airgapped/BYO trust thesis + a model-composition lab. Caveats: no-logprobs + tool-less (ASAFE-1/S-BS-90). Tracks S-BS-92. Concurrent-session authored 2026-06-06, commit 9f850e3.",
  "created": "2026-06-06",
  "last_re_verified": "2026-06-06 (build_judge_lm:205 + _ROLE_DEPLOYMENT:65 + _build_signature:175 + llm_provider.py + settings.py:30 + app.py:622)",
  "next_action": "READY -- /devloop-kickoff bench-salvage BYOC-1. Plan-review resolves D-A (tool-less mechanism, the A-SAFE crux) .. D-F (cost envelope). HARD-GATE: fresh-critic at close."
}
```

### 3c. Register the task — append to `tasks` in `TASK_PACK_bench-salvage.json`
```json
{
  "phase": "BYOC-1",
  "title": "BYOC-1 -- BYO-Claude as a first-class LLM provider (judges + generation; a model-composition lab).",
  "status": "ready",
  "blocked_by": [],
  "priority": "P1",
  "target": "executor",
  "repos": ["lithrim-bench"],
  "prompt_bundle": "bench-salvage-phaseBYOC-1-byo-claude-provider-driver",
  "milestone": "Make BYO-Claude selectable per-judge + platform-wide (build_judge_lm provider-aware). Completes the airgapped trust thesis (today judges are Azure-locked) + turns the council into a swap-a-model-and-measure lab. Tracks S-BS-92.",
  "origin": "Concurrent-session de-risk thread 2026-06-06 (commit 9f850e3): 5 live spikes proved the capability; this productionizes it. Builds on ASAFE-1/S-BS-90 (the tool-less requirement).",
  "hardness": "HARD-GATE; fresh-critic required at close.",
  "deliverables": ["D1 tool-less ClaudeCliLM(dspy.BaseLM)", "D2 provider-aware build_judge_lm + the judge model selector (Azure path byte-unchanged)", "D3 the $0 Claude-judge test + the tool-less A-SAFE negative test", "D4 the mixed-council composition demo vs all-Azure (cost-gated; the A-LIVE)", "D5 LITHRIM_LLM_PROVIDER=claude-cli global switch", "D6 docs + the logprob-confidence design note"],
  "acceptance": ["A1 a judge runs on BYO-Claude ($0, structured)", "A-SAFE the LM is tool-less (negative-tested)", "A3 mixed-council verdict differs vs all-Azure, gold-scored", "A4 confidence-without-logprobs surfaced not faked", "A6 frozen-set 0-delta except build_judge_lm", "A-LIVE the conv-UI-driven mixed-council demo (cost-gated)"],
  "scope_guardrails_not_in_scope": ["the conversational tool surface (inherits the ASAFE-1 deny-hook if touched)", "hosted/multi-tenant Claude (BYO/desktop only)", "the jute-transform generator (a sibling follow-on reusing ClaudeCliLM)", "FROZEN except build_judge_lm: _apply_consensus + JudgeSignature + judge_metric + seeds + existing BFF ops"],
  "next_action": "READY -- /devloop-kickoff bench-salvage BYOC-1. See the driver for D-A..D-F."
}
```

### 3d. (optional) note it in your close's next-cycle fork
Add BYOC-1 to the `current_phase` / First-move fork as a candidate — it **extends your pitch-derisk arc** (it de-risks the airgapped/provider claim and is the most strategically-loaded of the open forks).

## 4. Coordination guardrails
- **Don't clobber `9f850e3`** — it's the concurrent session's pathspec-scoped commit (the report + driver). It's an ancestor-safe addition on `bench-salvage/ws6c-dspy`.
- **Pathspec-only** when you commit the registration — `git commit -- STREAM_bench-salvage.md index.json TASK_PACK_bench-salvage.json …` (your normal discipline).
- **Seam id** — I reserved **S-BS-92**; if you've already claimed it, bump and fix the 3 references above.
- **The ASAFE-1 link is intentional:** BYOC-1's load-bearing A-SAFE gate is "the BYO-Claude judge/generation **LM must run tool-less**" — a direct application of your S-BS-90 finding (`claude` under bypass can run `Bash`). The driver references your `_deny_non_lithrim` hook for any conversational-loop touch. Your hole-find strengthened this spec.

## 5. Verify after registering
```
git show --stat 9f850e3        # the concurrent session's 2 files (report + driver) — already in
git diff --stat <your-parent> HEAD   # your close = your ONB-0/ASAFE-1 files + the 3 registration edits ONLY
grep -c 'BYOC-1' .devloop/prompts/index.json .devloop/tasks/TASK_PACK_bench-salvage.json   # 1 each
```

## References
- `docs/research/REPORT_byo_claude_provider_2026-06-06.md` — the 5 de-risks + the seam + caveats
- `.devloop/prompts/bench-salvage_phaseBYOC-1_byo-claude-provider_driver.md` — the BYOC-1 driver (D1–D6, A-SAFE tool-less, A6 scope)
- memory `byo-claude-provider-thesis` (+ the `conversational-authoring-surface-complete` ASAFE-1 correction you authored)
- Seam: `runtime/council/judges_dspy.py` `build_judge_lm` · `llm_provider.py` · `settings.py`
