# HANDOFF — `bench-salvage` phase `WS-4a` → next-cycle kickoff (WS-4b / WS-3b)

> **Written by the monitor on cycle close (2026-06-01).** Supersedes
> `HANDOFF_bench-salvage_phaseWS-4_kickoff_2026-06-01.md` for next-cycle
> purposes (that one covered the WS-3a→next transition).

---

## What just landed

- **Closed phase:** `WS-4a` (flywheel slice) — `corpus.py` (corpus-row/1) + `evalpack.py` (evalpack/1) + `report.py calibration_check`, offline/replay on clinical_v1.
- **Critique verdict:** `NON-BLOCKING` (inline) — `.devloop/sessions/critique-bench-salvage-phaseWS-4a-2026-06-01.md` (0 BLOCKING / 2 NB / 2 OQ)
- **Audit verdict:** `CLEAN` (A1–A4 monitor-re-verified: corpus-row/1 = corrected schema verbatim; both-direction projection tested; 171 passed / 3 dspy-skipped; ruff clean; deps unchanged)
- **Commits:** `894cc4d..da05779` (5 atomic) + close-out
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseWS-4a-2026-06-01.json`

## What's next (monitor's choice — do NOT autostart)

- **WS-4b** — eval-pack loop + LOCKED preregistered calibration gate + external-SDK `/eval-runs/compare` (cross-repo, HARD-GATE). Builds on WS-4a's corpus + thin eval-pack. **Gated** on S-BS-13 + S-BS-16 before any floor-declaring ontology ships; carries WS-1 Q4.2 (role-aware vs eligible-raiser ownership). Driver: `/devloop-expand-driver bench-salvage WS-4b`.
- **WS-3b** — KB/RAG/ONNX + judge-calls-tool MID-LOOP (mid-loop half waits on WS-2's paused backend; KB half doesn't). Natural home for S-BS-16 + S-BS-14/15.
- **Blocked by:** nothing for WS-4b authoring or WS-3b's KB half.

## Open seams for `bench-salvage` (next-cycle-relevant)

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-16 | floor inject-param validation at ontology-load (core invariant) | medium | **GATE** before any floor-declaring ontology ships |
| S-BS-13 | floor-apply offline replay in `run_eval` | medium | **GATE** for WS-4b's eval-pack loop |
| S-BS-14 / S-BS-15 | DX message / `_CONTRACT_EXECUTORS` rename | low | fold into WS-3b |
| S-BS-5 | local vector stub | medium | → WS-3b |
| S-BS-2 | v2 over-fire family | medium | additional grounding targets |

## Load-bearing context the next monitor MUST know

1. **`corpus-row/1` is frozen as v1 — consume it, don't re-author.** It is a *projection* over the WS-3a correction records (`build_correction`/`build_floor_correction`), not a new label authority: `flag_code` (= `tool_call.flag_code`, NOT the contract) + `action` (suppress|floor, which *is* the direction — there is deliberately no label column) + `verdict_before/after` + `owner_roles` + `rollout_ref` (sha256 canonical-JSON pointer into the lake). This shape was the load-bearing plan-review correction; WS-4b's eval-pack should embed corpus-row/1 provenance, not invent a parallel schema.

2. **The corpus is suppress-only until a floor-declaring ontology ships (Q4a-1).** clinical_v1 is floor-less, so today the corpus only accumulates `action="suppress"` rows. The floor *projection* is proven (`test_project_floor_record`), but `action="floor"` rows begin only when a floor ships — which is **gated by S-BS-16** (inject-param validation, core invariant). WS-4b's locked calibration gate must not assume floor rows exist before that lands.

3. **One baseline → one-case pack (Q4a-2).** Only `tests/fixtures/ws0/baseline.<case>.json` exists, so the thin eval-pack is genuinely one case. `build_pack` is N-case-general; multi-case breadth needs real `--live` baselines + floor-apply replay (**S-BS-13**) — both WS-4b. Do not fake breadth.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + open seams + First move).
3. Read this handoff + the WS-4a critique + session log.
4. `git log --oneline -10`.
5. Wait for user input. Don't autonomously start the next cycle.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- WS-4a session log: `.devloop/sessions/session-bench-salvage-phaseWS-4a-2026-06-01.json`
- WS-4a critique: `.devloop/sessions/critique-bench-salvage-phaseWS-4a-2026-06-01.md`
- WS-4a driver: `.devloop/prompts/bench-salvage_phaseWS-4a_flywheel_slice_driver.md`
- Prior handoff (superseded): `.devloop/sessions/HANDOFF_bench-salvage_phaseWS-4_kickoff_2026-06-01.md`
