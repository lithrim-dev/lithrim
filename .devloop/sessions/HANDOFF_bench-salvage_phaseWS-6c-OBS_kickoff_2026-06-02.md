# HANDOFF — `bench-salvage` phase `WS-6c-AGENTIC` → `WS-6c-OBS` kickoff

> **Written by the monitor on cycle close.** Load-bearing context for the next monitor
> session. Committed alongside the close-out commit.

---

## What just landed

- **Closed phase:** `WS-6c-AGENTIC` — the compliance grade-wire milestone: **the in-process council scores real cases through the harness grade seam for the first time.** Commits: bench `903478e..5cf438b` (6, branch `bench-salvage/ws6c-dspy`, **not pushed**) + backend `6720c70` (@ `mvp-ready`) + monitor docs (`b619f2e` registration, `118af7d` dispositions, + this close).
- **Audit:** CLEAN. **Critique:** HARD-GATE **genuinely-fresh-critic** (6-agent from-source workflow `wf_fdb93c9c-776`) → **NON-BLOCKING**; test-integrity **PRINCIPLED** (not gamed — the negative-control non-owner oracle survived). File: `.devloop/sessions/critique-bench-salvage-phaseWS-6c-AGENTIC-2026-06-02.md`.
- **A5 (option B):** live v2 trio on `proof_case:drop_allergy` → BLOCK/`reject`, Mistral `None` tolerated, **committed on-disk fixture** `tests/fixtures/ws0/a5_live.drop_allergy.json` + an env-gated real-council `grade_inprocess` test (1 paid call, ~$0.09–0.20).
- **Seams:** closed **S-BS-31** (owner reassignment) + **S-BS-32** (test footprint) + **S-BS-35** (A5 evidence); opened **S-BS-34** (pre-existing ruff). **S-BS-33** rerouted → WS-6d-KB.
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseWS-6c-AGENTIC-2026-06-02.json`.

## What's next

- **`WS-6c-OBS`** (recommended next — the observation/KPI half split from AGENTIC). **Bundle:** stub exists (`bench-salvage-phaseWS-6c-OBS-…`) → `/devloop-expand-driver bench-salvage WS-6c-OBS`. Recompose `../lithrim-backend/app/workflows/observation_workflow.py` (StateGraph + 7 instantiated agents: transcription + 6 KPI) → straight-line async in `lithrim_bench/runtime/`; **DROP** dead `evaluation_agent`, **PARK** LiveKit `simulation_agent`. **Greenfield** (grep of the agent classes across `lithrim_bench/` = 0 hits). **NOT in the compliance grade path** — independent of the grade-wire, so parallel-safe with everything.
- **Parallel:** the **remaining two judges** (policy/faithfulness on DSPy, same §6 seam) ∥ **6d** persistence (+ **6d-KB**, where S-BS-33 lands) → **6e** ETLP ∥ shell **WS-5e** (HARD-GATE lead). **S-BS-34** (ruff exclude) is a low-priority cleanup, no gate.
- **Blocked by:** nothing. OBS is greenfield + grade-path-independent.

## Open seams for `bench-salvage` (OBS-relevant)

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-34 | `ruff check .` not clean — 865 pre-existing (vendored port + worktrees + scripts) | low | open — fix = `ruff.toml` exclude, **NOT a reformat** (would break the byte-faithful port). Not a gate. |
| S-BS-33 | per-judge seam doc omits optional `citations_used` read | low | open → **WS-6d-KB** (inert until KB lands) |
| S-BS-24 | backend not-slow suite RED pre-existing | medium | open — NOT a green gate |

## Load-bearing context the next monitor MUST know

1. **The D2 reframe is the recompose pattern, and it recurs at OBS.** The in-process orchestrator is the `pipeline/` **PRIMITIVE** (`runtime/pipeline/orchestrator.py`), not a 1:1 port of the backend's LangGraph workflow. It calls `council.evaluate()` **once** and has no confidence-gate / two-phase-disposition / store_report / lockstep-recompute nodes. The fresh-critic verified this is **verdict-equivalent-or-STRICTER** than the backend: the backend's `run_confidence_gate` (`compliance_workflow.py:785`) can approve *without* the council when gate-confidence ≥ 0.85 and no safety signals, and it can ONLY approve + always escalates when artifacts are present — so backend strictness ≤ bench strictness, and on by-construction defect packs there is no case where the backend rejects and the bench passes. **Therefore the recompose contract is "verify-and-document," not "rebuild the workflow nodes."** When OBS recomposes `observation_workflow`, expect the same shape: port the *primitive* (the agent calls + the merge), and where the backend workflow has orchestration scaffolding (gates, error sinks, recompute), **document the deliberate divergence rather than replicate it** — and prove no verdict/score drift with a diff-vs-baseline, not by porting nodes. Adding nodes risks introducing exactly the approve-without-work false-negative path the HARD-GATE exists to prevent.

2. **The owner↔emit pairing invariant + the safety-IP edit pattern.** S-BS-31 was fixed by reassigning Tier-1 owners to the v2 trio **by clinical domain**, and the critical rule the fresh-critic enforced is: **a code's production owner must be a judge whose prompt actually EMITS that code** — else the ownership is *inert* (an owner that can never fire). `risk_judge` was correctly DROPPED from MISSING_ALLERGY for exactly this reason (it emits FABRICATED_ALLERGY, not MISSING_ALLERGY). This invariant is the seed for the WS-1 SQLite config-plane validation (when owner-residency moves to a config store, the store must validate owner↔emit, or it reintroduces the inert-owner footgun as a data-entry error). Any future owner edit is a backend-SSOT change (`../lithrim-backend` `_TIER1_OWNERS` + the prompt) → byte-faithful re-port → re-snapshot → coupled test-assertion updates; never hand-edit the bench mirror or the snapshot.

3. **Evidence standard for live milestones (set this cycle).** A HARD-GATE live claim needs an **on-disk artifact**, not session-log prose. WS-6c-AGENTIC's A5 was completed to that standard under option (B): a committed fixture + an env-gated (importorskip openai; `debuglithrim`) real-council test that captures its own output. Reuse this pattern for any OBS live validation: one cost-confirmed paid call, captured as a committed fixture + a gated test (skips $0 by default). Env: `debuglithrim` pyenv for council/dspy + the live smoke; `../lithrim-backend/.env` for Azure (source via a clean temp-env — it has unquoted-space + list-field entries that break naive sourcing; gpt-4.1 = `DEPLOYMENT_COUNCIL`, Mistral/Llama deployment ids present for the full trio). Cost-conscious: inspect-1-then-stop.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + seams S-BS-1..35 + first move).
3. Read this handoff + the WS-6c-AGENTIC session log + critique.
4. Read `docs/specs/RECOMPOSITION_PLAN_ws6.md` §4 (the observation_workflow citations) + the Amendment before expanding the OBS driver. Re-grep the `observation_workflow.py` agent-instantiation lines against `../lithrim-backend@mvp-ready` at authoring.
5. `git log --oneline -10` in bench.
6. Wait for user input; the next action is `/devloop-expand-driver bench-salvage WS-6c-OBS`. Don't autostart the next cycle.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- WS-6c-AGENTIC driver: `.devloop/prompts/bench-salvage_phaseWS-6c-AGENTIC_compliance-grade-wire_driver.md`
- Session log + critique: `.devloop/sessions/session-…AGENTIC….json` / `critique-…AGENTIC….md`
- Recompose plan: `docs/specs/RECOMPOSITION_PLAN_ws6.md` (§4 RECOMPOSE-IN-PROCESS, §7 phases, the 2026-06-02 Amendment)
- The grade-wire + D2 reframe, durably: `lithrim_bench/runtime/council/tests/test_grade_wire.py` module docstring; memory `[[ws6c-agentic-grade-wire-and-recompose-pattern]]`
