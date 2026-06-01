# HANDOFF — `bench-salvage` phase `WS-6c-DSPy` → `WS-6c-AGENTIC` kickoff

> **Written by the monitor on cycle close.** Load-bearing context for the next
> monitor session that takes over the 6c build track after a compaction or break.
> Committed alongside the close-out commit.

---

## What just landed

- **Closed phase:** `WS-6c-DSPy` — rebuild the per-judge layer on DSPy, wrapping the ported v2 consensus (the §6 hybrid). Commits `95174c0..4e1d3cc` (4 atomic, branch `bench-salvage/ws6c-dspy`, **not pushed**), in `lithrim-bench`.
- **Audit verdict:** **CLEAN (7/7)** — monitor independently re-verified: A4 consensus byte-ZERO-delta vs the WS-6c tip `6bae3c0` (`git diff` over the full ported set = 0 lines), scope held (only `runtime/council/` + log; frozen seam intact), 39 passed/1 skipped on `debuglithrim`, ruff clean, S-BS-32 directly reproduced.
- **Critique verdict:** **NON-BLOCKING FINDINGS** (0 BLOCKING / 4 NB-OQ). File: [.devloop/sessions/critique-bench-salvage-phaseWS-6c-DSPy-2026-06-02.md](critique-bench-salvage-phaseWS-6c-DSPy-2026-06-02.md). HARD-GATE closed on an **inline-by-continuation** critique (see landmine #2).
- **A5/live smoke:** **PASS** — 1 gpt-4.1 call, **$0.0067**. DSPy `risk_judge` → `reject` on a WRONG_DOSAGE case (2 grounded spans) → ported `_apply_consensus` → `reject`, matching the recipe=label. **D2 logprobs bridge validated live** (`confidence=0.999999`; Mistral `None`-path pinned offline; sourced from `extract_verdict_confidence`, not a self-report field).
- **Session log:** [.devloop/sessions/session-bench-salvage-phaseWS-6c-DSPy-2026-06-02.json](session-bench-salvage-phaseWS-6c-DSPy-2026-06-02.json).
- **Seams:** **closed S-BS-27** (DSPy prior art re-authored clean in-package, worktree never imported); **opened S-BS-32** (S-BS-31 footprint in the packager/triage suite) **+ S-BS-33** (seam doc omits the optional `citations_used` read).

## What's next

The 6c build track (parallel-safe with the shell track):

- **`WS-6c-AGENTIC`** (recommended next; **⛔ S-BS-31-GATED**) — recompose the LangGraph `compliance_workflow` + `observation_workflow` into straight-line async fns + recompose the 6 KPI agents in-process, and **wire the ported council into the grade seam** (the first time the council scores real cases). **Driver bundle:** none yet → `/devloop-expand-driver bench-salvage WS-6c-AGENTIC`. **This is also the home for the genuinely-fresh-critic** deferred from 6c-DSPy (landmine #2).
- **Remaining two judges** (parallel, low-risk) — `policy_judge` (Mistral) + `faithfulness_judge` (Llama) on DSPy behind the SAME `_JudgeSignature` + seam, mixed with the ported imperative fan-out (the hybrid wraps DSPy/non-DSPy identically). `policy_judge` exercises the Mistral `confidence=None` path live; `faithfulness_judge` is the llama-veto judge. Could fold into AGENTIC or a small `WS-6c-DSPy-b`.
- **`WS-5e`** (parallel shell lead, HARD-GATE) — Tauri packaging; unaffected by 6c.
- **Blocked by:** 6c-AGENTIC is gated on the **S-BS-31** decision (council-IP/clinical) before grade-wiring; **S-BS-32** resolves with it.

## Open seams for `bench-salvage` (6c-relevant; full table in STREAM)

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-BS-31 | 3 Tier-1 flags have no production-resident owner under v2-only | medium | `../lithrim-backend …compliance_council.py _TIER1_OWNERS:232` | WS-6c | **open → 6c-AGENTIC (GATE)** |
| S-BS-32 | S-BS-31 footprint: 3 default-deps packager/triage tests RED under v2-only | medium | `lithrim_bench/packager.py:153` + 2 test files | WS-6c-DSPy | **open** (pre-existing; resolves with S-BS-31) |
| S-BS-33 | per-judge seam doc omits the optional `citations_used` read (`_apply_consensus:1942`) | low | `runtime/council/__init__.py:43-49` (doc) + `judges_dspy.py` (emission) | WS-6c-DSPy | **open → 6c-AGENTIC** (inert; decide at KB-wire) |
| S-BS-27 | DSPy prior art (re-authored clean) | low | `runtime/council/judges_dspy.py` | WS-6b | **RESOLVED (6c-DSPy)** |
| S-BS-24 | backend `not slow` suite RED pre-existing | medium | backend suite | WS-6a | open (NOT a green gate; bench analogue = S-BS-32) |

## Load-bearing context the next monitor MUST know

1. **The per-judge dict seam is the stable contract, and the ported consensus is byte-frozen below it.** `judges_dspy.py` emits `{model, decision, confidence:float|None, findings:[{taxonomy_code, evidence_spans}], errors:[]}` (`runtime/council/__init__.py:43-49`); `_apply_consensus` (`compliance_council.py:1853`) consumes it UNCHANGED — WS-6c-DSPy proved `git diff 6bae3c0..HEAD` over the full ported set is **0 lines**. **6c-AGENTIC must preserve this:** when it wires the council into grade, the recomposed pipeline feeds the SAME seam dict; do NOT edit the consensus math to accommodate the recompose. The critic enumerated every consumer read — the only one NOT in the documented seam is the optional `citations_used` at `:1942` (S-BS-33), verdict-neutral and inert until KB lands. **Confidence is sourced from logprobs (`extract_verdict_confidence`), never a self-report `OutputField`** — preserve that; a DSPy adapter that drops the decision-token logprob silently degrades gpt-4.1 to `None` (a reported diagnostic, not a gate; the offline None/float round-trips are pinned via synthesized response dicts).

2. **S-BS-31 is the AGENTIC gate, AND the genuinely-fresh-critic independence is owed there, not here.** WS-6c-DSPy's HARD-GATE critique was **inline-by-continuation** — the same session that prepped the kickoff ran the critic pass. It was adversarial and found 2 real findings from source (`citations_used`, A3-NKA), so it was *stronger* than WS-6c's monitor self-audit, and the council scores **no real cases** this cycle (S-BS-31/32 inert under A6), so the monitor judged it sufficient to close. **But the independence budget was deliberately reserved for 6c-AGENTIC** — the cycle that first wires the council into grading, where a fidelity miss would score real cases. Run `KICKOFF_CRITIC.md` in a **genuinely separate session** there. And resolve **S-BS-31** (reassign a v2-trio owner for `MISSING_ALLERGY`/`FABRICATED_CONSENT`/`VALUE_MISMATCH` in the backend `_TIER1_OWNERS`, OR ratify corroboration-only escalation under v2 and document it) **before** the council scores real cases — `_TIER1_OWNERS` was ported VERBATIM (A2), so the fix is a backend-IP/clinical decision above the executor's remit. S-BS-32 (3 RED packager/triage tests) is the same defect's test-surface footprint and resolves with it.

3. **Env + cost discipline (carried from this cycle).** The council + DSPy tests run on the **`debuglithrim` pyenv** (3.10.15) — it now carries `dspy 3.2.1` (added this cycle) on top of `openai`/`tenacity`/`pydantic_settings`/`pytest`/`ruff` + `lithrim_bench` importable; the default `python3` lacks dspy so the DSPy tests `importorskip`-skip (the A7 evidence). The one live Azure call ran from `debuglithrim` with `../lithrim-backend/.env` (which has `AZURE_OPENAI_DEPLOYMENT_COUNCIL`=gpt-4.1 + `_MINI` — but **NOT** Mistral/Llama deployment ids, so a full-v2-trio live run needs more than this dev `.env`). The user is LLM-cost-conscious: offline/replay-first, inspect-1-then-stop; the smoke came in at $0.0067 vs a $0.05 ceiling. See memory `[[council-runtime-test-env]]`.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + seams S-BS-1..33 + First move).
3. Read this handoff.
4. Read the WS-6c-DSPy session log + critique (paths above) + `docs/specs/RECOMPOSITION_PLAN_ws6.md` §4 (RECOMPOSE-IN-PROCESS — the LangGraph removal + the 4 behavior-preservation contracts) before expanding the 6c-AGENTIC driver.
5. `git log --oneline -8` in bench (the WS-6c-DSPy close commit + `95174c0..4e1d3cc`).
6. Wait for user input. Don't autonomously start the next cycle; the next action is `/devloop-expand-driver bench-salvage WS-6c-AGENTIC`.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Driver: `.devloop/prompts/bench-salvage_phaseWS-6c-DSPy_dspy-judge-rebuild_driver.md`
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseWS-6c-DSPy-2026-06-02.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseWS-6c-DSPy-2026-06-02.md`
- The §6 hybrid + RECOMPOSE-IN-PROCESS: `docs/specs/RECOMPOSITION_PLAN_ws6.md` (§4 LangGraph recompose, §6 hybrid, §7 the WS-6c-AGENTIC row)
- Ported package: `lithrim_bench/runtime/council/` (consensus IP byte-faithful to `lithrim-backend@493b533`; `judges_dspy.py` = the new DSPy layer above the seam)
- Paired publication stream: `.devloop/state/STREAM_paper-1-copilot.md`
