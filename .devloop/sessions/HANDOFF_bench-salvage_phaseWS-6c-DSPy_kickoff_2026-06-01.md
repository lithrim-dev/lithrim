# HANDOFF — `bench-salvage` phase `WS-6c` → `WS-6c-DSPy` / `WS-6c-AGENTIC` kickoff

> Written by the monitor on cycle close. Load-bearing context for the next
> monitor session that takes over the 6c build track after a compaction or break.
> Committed alongside the close-out commit.

---

## What just landed

- **Closed phase:** `WS-6c` — PORT the v2 council Mongo-free into `lithrim_bench/runtime/council/` (v2-only). Commits `12281e1..6bae3c0` (3 atomic, branch `bench-salvage/ws6c-council-port`, **not pushed**), in `lithrim-bench`.
- **Audit verdict:** **CLEAN (7/7)**, monitor-re-verified at tip `6bae3c0` (A2 byte-faithful diff vs `493b533`; offline oracle 19 passed / 1 skipped; ruff clean; lint green; scope held; backend untouched `@493b533`).
- **Critique verdict:** **NON-BLOCKING FINDINGS** (inline; HARD-GATE, **user-elected inline** over the recommended fresh-critic). File: [.devloop/sessions/critique-bench-salvage-phaseWS-6c-2026-06-01.md](critique-bench-salvage-phaseWS-6c-2026-06-01.md). 0 BLOCKING / 3 NB / 5 OQ.
- **Cycle verdict:** **PROCEED-WITH-CAVEATS** (caveats: fresh-critic not run; S-BS-31 open; A5 cost overage, all below).
- **A5 live smoke:** **PASS** on the Azure dev resource (`lithrim-dev-ai`) via `../lithrim-backend/.env`, user-go'd. v2 trio all-reject (gpt-4.1@1.0, Mistral@None, Llama@1.0) → consensus reject@1.0, matches the offline oracle. **Headline: Mistral `confidence=None` reproduced end-to-end on live data** (the BRS-3 None-tolerance invariant holds across providers). Actual cost ~$0.15–0.25 (3 runs: an empty-payload bug + a diagnostic dump + the pass) vs the ~$0.10 envelope; overage was a payload-shape bug the smoke caught and the executor fixed, user-aware.
- **Session log:** [.devloop/sessions/session-bench-salvage-phaseWS-6c-2026-06-01.json](session-bench-salvage-phaseWS-6c-2026-06-01.json) (committed in this close commit).
- **Seams:** **closed S-BS-30** (production_judges now derived from the v2 config) + **S-BS-28** (port verified byte-faithful to `493b533`, both tables files); **opened S-BS-31** (orphaned Tier-1 owners under v2, below).

## What's next

The 6c build track fans out (parallel-safe with the shell track):

- **`WS-6c-DSPy`** (recommended next) — rebuild the judges with DSPy, emitting the per-judge dict seam the ported `_apply_consensus` already consumes (`{model, decision, confidence, findings[taxonomy_code+evidence_spans], errors}`, documented in `runtime/council/__init__.py`). Wraps the ported consensus; lower risk; does NOT wire into grade. **Driver bundle:** none yet → `/devloop-expand-driver bench-salvage WS-6c-DSPy`. Prior art (reference-only, do NOT import): S-BS-27 DSPy council worktree.
- **`WS-6c-AGENTIC`** (parallel; **S-BS-31-GATED**) — recompose the LangGraph + agents in-process and call the ported council through the grade seam (the first time the ported council scores real cases). **Driver bundle:** none yet → `/devloop-expand-driver bench-salvage WS-6c-AGENTIC`. **Do not wire the council into grading until S-BS-31 is resolved** (see below).
- **`WS-5e`** (parallel shell lead, HARD-GATE) — Tauri packaging; unaffected by 6c.
- **Blocked by:** nothing for 6c-DSPy. 6c-AGENTIC is gated on the S-BS-31 decision (council-IP/clinical) before grade-wiring.

## Open seams for `bench-salvage` (6c-relevant; full table in STREAM)

| ID | Title | Severity | Fix loc | Status |
|---|---|---|---|---|
| S-BS-31 | 3 Tier-1 flags have no production-resident owner under v2-only (corroboration-only escalation) | medium | `../lithrim-backend …/compliance_council.py _TIER1_OWNERS:232` | **open → WS-6c-AGENTIC (GATE) / WS-6c-DSPy** |
| S-BS-30 | production_judges hardcoded | medium | `scripts/snapshot_taxonomy.py` | **RESOLVED (WS-6c)** |
| S-BS-28 | port-source discipline (stale mirror) | medium | `runtime/council/` | **RESOLVED (WS-6c)** — drift was mechanical, not logical |
| S-BS-7 | MED-FP is judge-calibration (the exhibit) | high | harness grounding | open (north-star thread) |
| S-BS-24 | backend `not slow` suite RED pre-existing | medium | backend suite | open (NOT a green gate; moot for the bench-side oracle) |
| S-BS-16 / S-BS-12 | floor inject-param validation / one-directional lint | medium | `grounding.py` / `seed_ontology.py` | open (pair the owner-residency lint here) |

## Load-bearing context the next monitor MUST know

1. **S-BS-31 is the WS-6c-AGENTIC gate, and it is the consequence of the ratified v2-only decision, not a bug.** Flipping `production_judges` to the v2 trio (risk/policy/faithfulness) leaves `MISSING_ALLERGY`, `FABRICATED_CONSENT`, `VALUE_MISMATCH` owned only by `behavior_judge`/`source_message_judge` (declared-but-not-running), so under v2 they can only escalate by 2+ corroboration, never single-judge one-strike. 2 of the 3 appear in shipped `examples/proof_case.jsonl`. It is **inert this cycle** because A6 keeps the grade seam frozen (the ported council scores nothing yet), and the admissibility lint gates D1/D8 only (not owner-residency), so it stays green. It becomes live the moment **WS-6c-AGENTIC** wires the council into grading. Resolution is a council-IP/clinical decision above the executor's remit: (a) reassign a v2-trio owner for the 3 codes in the backend `_TIER1_OWNERS` (then re-port), or (b) ratify corroboration-only escalation under v2 and document it. Pair an owner-residency lint with S-BS-12 when this lands. `_TIER1_OWNERS` was ported VERBATIM (PORT-not-rewrite / A2); do NOT hand-edit it in a port cycle.

2. **The port is byte-faithful; trust it.** S-BS-28 framed the parked `runtime/council/` mirror as "stale, do not trust." The executor's diagnose-before-edit measurement (CONFIRMED, monitor-re-verified) found the drift was **mechanical only** (the 6 vendored import lines + one `_ROLE_PROMPTS_DIR` path); the parked mirror was already byte-identical to `493b533` modulo imports, so the re-derive reproduced it with **zero git delta** on the IP files. This is consistent with WS-6b's S-BS-29 finding (no council drift `ba84608`→`493b533`). Practical consequence for 6c-DSPy/AGENTIC: the ported consensus IP (`_apply_consensus`, `_compose_council_verdict_v2`, `_worst_of_verdicts`, tier/owner tables, `extract_verdict_confidence`) is verified-equal to the backend and can be built on without re-auditing the math. The **per-judge dict seam** in `__init__.py` is the stable boundary DSPy judges must emit.

3. **This HARD GATE closed on an INLINE critique (user-elected), so the fresh-critic independence property was not exercised.** The driver permits inline ("User MAY elect inline"); the user elected it twice. The inline pass was run by this monitor (non-independent: it shaped the plan-review, approved 4a/6a, adjudicated both HALTs, ran the audit), compensated by tracing A3 oracle correctness against the ported impl directly and re-diffing A2. Also note: a concurrent session had pre-authored an inline critique at 23:54 against the pre-amend tip `c25510f`; it was reconciled in place at close (commit range → `6bae3c0`, a reversed §3 finding corrected, A5 PASS recorded, one `__init__` finding added). **If independence is required before 6c-AGENTIC wires the council into grading, run a fresh-critic (`KICKOFF_CRITIC.md`) against `6bae3c0`.** This stream runs concurrent cycles on shared state: `git status` and re-read STREAM/index before editing, and sequence close commits.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + seams S-BS-1..31 + First move).
3. Read this handoff.
4. Read the WS-6c session log + critique (paths above).
5. `git log --oneline -6` in bench (the WS-6c close commit + `12281e1..6bae3c0`).
6. Read `docs/specs/RECOMPOSITION_PLAN_ws6.md` §6 (the hybrid DSPy-judges + ported-consensus end state) before expanding the 6c-DSPy driver.
7. Decide the 6c-track next (6c-DSPy recommended ∥ 6c-AGENTIC S-BS-31-gated) or continue the shell track (WS-5e). Do NOT autostart; the next action is `/devloop-expand-driver`.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Driver: `.devloop/prompts/bench-salvage_phaseWS-6c_council-port_driver.md`
- Ported package: `lithrim_bench/runtime/council/` (consensus IP byte-faithful to `lithrim-backend@493b533`)
- Recomposition plan: `docs/specs/RECOMPOSITION_PLAN_ws6.md` (§5 PRESERVE-AS-IP, §6 hybrid, §Ratification)
- Next in track: WS-6c-DSPy (judge rebuild) ∥ WS-6c-AGENTIC (LangGraph recompose + grade wire) → WS-6d persistence (+WS-6d-KB) → WS-6e ETLP
