# HANDOFF — `bench-salvage` phase `WS-3` (WS-3a) → next-cycle kickoff

> **Written by the monitor on cycle close (2026-06-01).** Load-bearing
> context for the next monitor session. Committed alongside the close-out
> commit.

---

## What just landed

- **Closed phase:** `WS-3` (WS-3a scope) — promote the verification core into `lithrim_bench/verification/` + wire the structural FLOOR into `harness/grounding` (PASS→BLOCK on a bench-accepted contract the council missed). WS-3b (KB/RAG/ONNX + judge-calls-tool mid-loop) deferred.
- **Critique verdict:** `NON-BLOCKING` (fresh-critic, HARD GATE) — `.devloop/sessions/critique-bench-salvage-phaseWS-3-2026-06-01.md` (0 BLOCKING / 6 NB / 3 OQ)
- **Audit verdict:** `CLEAN` (7/7; A1/A3/A4/A5 monitor-re-verified independently: import-isolation `[]`, floor test 5/5, packs diff==0, 164 passed / 3 dspy-skipped)
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseWS-3-2026-06-01.json`
- **Commits:** 5 atomic (D0 core / D1 extra / D2 floor+run_eval / D3 packs / D4 tests) + 1 close-out — **landed on user sign-off**; real hashes appended to the session log at landing.

## What's next (monitor's choice — do NOT autostart)

- **Next phase:** `WS-3b` or `WS-4` (fork)
  - **WS-3b** — KB/RAG/ONNX stack (S-BS-5 local vector + pinecone via `:8002 /v1/kb/search`) + judge-calls-tool MID-LOOP into the live council. The KB half is independent; the **mid-loop half waits on WS-2's paused backend** `council_config`/`ontology` injection. Natural home for **S-BS-16** (floor inject-param validation — small, touches the core invariant), the S-BS-15 rename, the S-BS-14 DX fix, and the stale `tools.py` spike comments + dangling `TOOL_KB_RAG` constant.
  - **WS-4** — eval-pack loop + LOCKED calibration gate. **Driver:** queued (run `/devloop-expand-driver bench-salvage WS-4`).
- **Blocked by:** nothing for WS-3b's KB half or WS-4's authoring. The mid-loop half of WS-3b is blocked by WS-2's HARD-GATE-paused backend.

## Open seams for `bench-salvage` (WS-3-relevant)

| ID | Title | Severity | Fix loc | Opened | Status |
|---|---|---|---|---|---|
| S-BS-13 | `run_eval` floor not replayable offline (live `:3031` under `--replay`) | medium | `scripts/run_eval.py run()` | WS-3a | **open → WS-4 GATE** |
| S-BS-14 | Floor w/o `[verification]` extra → ImportError at apply-time not config-load | low | `grounding.py _run_floor` | WS-3a | open |
| S-BS-15 | `_CONTRACT_EXECUTORS` is suppress-only but keeps generic name | low | `grounding.py` | WS-3a | open (rename deferred) |
| S-BS-16 | Floor-injected flag bypasses gradeable/owner + severity validation | medium | `grounding.py:355-365` / ontology-load | WS-3a | **open → GATE before any floor ships** |
| S-BS-12 | one-directional snapshot lint | medium | `seed_ontology.py:152-160` | WS-2 | open → WS-2 backend / follow-up |
| S-BS-5 | local vector stub | medium | — | — | open → WS-3b |

## Load-bearing context the next monitor MUST know

1. **The two-registry split is intentional — do not "unify" it.** Suppress contracts are per-finding (`_CONTRACT_EXECUTORS = {presence_check: …}`); the floor is per-artifact (`_FLOOR_CONTRACT_TYPES = {structural_jute, jute_gen}` + `_run_floor`). Decision 2 (APPROVED-AT-PLAN) chose the sibling registry over the driver's literal "add to `_CONTRACT_EXECUTORS`" precisely because the floor is a genuinely different shape (it *injects* a finding the council missed, rather than *suppressing* one). The fresh critic ratified this as "more faithful to the code than the driver." The flip mechanic: floor injects `{code, severity:HIGH, _floor:True}` into `active` after the per-finding loop → `severity_map.rescore` lifts HIGH→1.0 ≥ `block_at_or_above` 1.0 → BLOCK.

2. **Landmine — S-BS-13 is a GATE, not a nice-to-have.** `run_eval.run()` calls `ground()` with no `http_client`, so the *eval-runner* floor path hits live `:3031` even under `--replay`. This is inert TODAY only because `clinical_v1` declares no floor — the offline-deterministic charter (CLAUDE.md §Stack) holds for every shipped ontology. The FIRST ontology to declare a floor breaks offline determinism unless WS-4's eval-pack loop adds a floor-apply replay capture FIRST. Same gate applies to **S-BS-16**: a floor's `inject_flag_code`/`inject_severity` are read raw with no validation against the gradeable set / `severity_map.weights`, so a misconfigured floor could BLOCK on an ownerless code (violating core-invariant #4) or silently never fire on a typo'd severity. Validate at ontology-load before any floor-declaring ontology ships.

3. **"byte-identical" → "additively backward-compatible" (Q4-1).** Driver §5 A3 said the no-floor path is "byte-identical" to the pre-WS-3 `ground()`. It is *additively* identical (verdict + all partitions unchanged, no floor HTTP) but not literally byte-identical — `GroundedResult` gained a defaulted `floor_blocks=[]` field and `composite()`/`run_eval` always emit inert floor keys. Re-operationalized at plan-review (refinement #1, monitor-approved) as "pre-existing fields + verdict identical AND `floor_blocks==[]`." Reword the driver. This is the **second** time an A3 floor-clause was re-interpreted at close (precedent: P1-VALIDATE-12 Path T) — future drivers should phrase backward-compat precisely up front.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + open seams + First move).
3. Read this handoff doc.
4. Read the session log: `.devloop/sessions/session-bench-salvage-phaseWS-3-2026-06-01.json`.
5. Run `git log --oneline -10` to see the commit timeline.
6. Wait for user input. Don't autonomously start the next cycle.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseWS-3-2026-06-01.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseWS-3-2026-06-01.md`
- Driver: `.devloop/prompts/bench-salvage_phaseWS-3_dspy_jute_validator_generator_driver.md`
- Roadmap context: `.devloop/state/STREAM_bench-salvage.md` (milestone arc) + paired `STREAM_paper-1-copilot.md` (S-P1-22)
