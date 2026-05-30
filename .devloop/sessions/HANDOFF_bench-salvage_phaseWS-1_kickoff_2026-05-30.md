# HANDOFF — `bench-salvage` phase `WS-0` → phase `WS-1` kickoff

> **Written by the monitor on cycle close (2026-05-30).** Load-bearing context for
> the next monitor session that takes over after a compaction or after-hours break.
> Committed alongside the close-out commit.
>
> **Path:** `.devloop/sessions/HANDOFF_bench-salvage_phaseWS-1_kickoff_2026-05-30.md`

---

## What just landed

- **Closed phase:** `WS-0` — one case end-to-end over live APIs, the walking-skeleton spine (commits `9001a36..0859c8d`, 6 atomic; session-log commit `9d2b721`)
- **Critique verdict:** `NON-BLOCKING FINDINGS` (`.devloop/sessions/critique-bench-salvage-phaseWS-0-2026-05-30.md`)
- **Audit verdict:** `CLEAN` (7/7 mechanical items; two non-blocking notes: pre-existing working-tree drift outside the cycle, and one ratified-and-documented mid-cycle deviation)
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseWS-0-2026-05-30.json`
- **What it delivered:** new `lithrim_bench/harness/` package — `grade.py` (compose-over-live `:8002` + replay), `persist.py` (fs blob + SQLite doc-shim, S-BS-4), `grounding.py` (the `MedPresenceCheck` verification contract + null-code skip-log), `correction.py` (versioned RLVR record), `report.py` (composite + report-only calibration) — plus `scripts/run_ws0.py` and `tests/test_ws0.py`. **Zero new paid calls** (built/tested offline against the captured baseline; `--live` present but unexercised). 89/89 tests green; new code ruff-clean.

## What's next

- **Next phase:** `WS-1` — SQLite config plane (Agent eval-profile) + the ontology data model
- **Driver bundle:** `bench-salvage-phaseWS-1-sqlite-config-plane-driver` (**stub**)
- **Driver path:** `.devloop/prompts/bench-salvage_phaseWS-1_sqlite_config_plane_driver.md` (not yet authored — `/devloop-expand-driver bench-salvage WS-1`)
- **Blocked by:** `none` — WS-0 close unblocks WS-1.

## Open seams for `bench-salvage`

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-BS-1 | v1 pure-legacy vs findings-first | medium | council judge-output capture | COUNCIL-EVIDENCE-GATE planning | **resolved** (findings-first w/ validated spans) |
| S-BS-2 | v2 over-fire family (FABRICATED_CONSENT / INCOMPLETE_DOCUMENTATION / …) | medium | grounding contracts | COUNCIL-EVIDENCE-GATE planning | **open** — confirmed live on the scribe note (WS-0); additional grounding targets → **WS-3** |
| S-BS-3 | blast radius of authoritative findings | high | (aggregation fix) | COUNCIL-EVIDENCE-GATE planning | **superseded/moot** (fix doesn't land) |
| S-BS-4 | SQLite shape (doc-shim vs relational) | medium | `runtime/services/` data layer | M1 close-out | **DECIDED = document shim** — applied in WS-0 persist; extend in WS-1 |
| S-BS-5 | local vector stub; sqlite-vec blocked | medium | `runtime/pipeline/retrieval.py` | M1 close-out | **open** → WS-3 (numpy over rag receipts; or `:8002 /v1/kb/search`) |
| S-BS-6 | v1-vs-v2 as the canonical baseline | medium | council v2 config / eval-profile | M1 close-out | **disposition recorded (WS-0); ratify in WS-1** — adopt compose-over-live-v2 |
| S-BS-7 | MED FP is judge-calibration, not aggregation | **high** | ontology verification_contract | COUNCIL-EVIDENCE-GATE pre-check | **HYPOTHESIS confirmed (WS-0)** — presence-check disproves+suppresses live; generalize to ontology in WS-1, mid-loop in WS-3 |
| S-BS-8 | live findings with **null taxonomy code** (4 in baseline) | medium | harness finding-normalization | WS-0 smoke test | **handled in WS-0** (skip+log; never dropped). Upstream backfill out of harness scope. |
| S-BS-9 | same `case_id`, divergent `expected_compliance_verdict` shape across pack files | low | pack generation + `picklist.py` | WS-0 | **open — CONFIRMED.** Worked around (source-pin + shape-tolerant `expected_block`); normalize in **WS-1** pack hygiene |

## Load-bearing context the next monitor MUST know

1. **The grounding contract is currently a single hardcoded class, by design — WS-1's job is to lift it into the ontology, not to leave it hardcoded.** `grounding.WS0_CONTRACTS = [MedPresenceCheck()]` and `correction.ONTOLOGY_VERSION = "ws0-hardcoded/0"` are deliberate sentinels marking "no ontology table yet." WS-1 promotes `MedPresenceCheck` to the ontology's first `verification_contract` and drives the WS-0 run from SQLite config instead of hardcoded args. **Critique Q4.3 is binding here:** the med-name extraction strategy (`_med_tokens`: dosage/form/noise strip, `len>=4` floor, `active_medications` as the authoritative source) must become an *explicit, testable* part of the contract definition — interrogate the 3-letter-drug and brand/generic edge cases when you formalize it.

2. **Landmine for WS-4 — do not let the WS-0 calibration "correct" definition silently become the gate.** `report.py:75` scores **every** judge's vote against the **single case-level** `expected_block`, so `risk_judge`'s role-correct PASS is counted "incorrect" (it's why ECE=0.5 on a 2-confidence baseline). That is fine for a report-only diagnostic and is honestly small-N caveated, but **when WS-4 locks a calibration gate, the "correct" predicate must be role-aware or measured against the composite verdict** — otherwise a well-calibrated, role-specialized council fails the gate for the wrong reason. This is critique Q4.1; it is recorded here precisely so the WS-4 spec author can't miss it.

3. **S-BS-6 is decided in spirit, ratified in WS-1: the harness baseline is compose-over-live-v2, and grounding is what cleans the over-fire.** WS-0 confirmed the live backend is `COMPLIANCE_COUNCIL_VERSION=v2` and over-fires (FABRICATED_CONSENT + INCOMPLETE_DOCUMENTATION on the clean-ish scribe note, on top of the MED FP). The strategic bet — adopted by the monitor and to be encoded in the WS-1 Agent eval-profile `council_config` — is that we keep the prod-real v2 path (more FP exhibits for the paper) and rely on the verification contracts to clean it, rather than reverting to the quieter in-process v1 (which is now demoted to WS-6 compartmentalize-local). The in-process M1 council still exists (`lithrim_bench/runtime/`, currently uncommitted working-tree drift) and is the WS-6 input, not the spine.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + open seams — both updated at this close).
3. Read this handoff doc.
4. Read the most recent session log: `.devloop/sessions/session-bench-salvage-phaseWS-0-2026-05-30.json`, and the critique `.devloop/sessions/critique-bench-salvage-phaseWS-0-2026-05-30.md`.
5. Run `git log --oneline -10` in `lithrim-bench` to see the commit timeline (`9001a36..9d2b721` are the WS-0 cycle).
6. Wait for user input. Don't autonomously start the next cycle — next action is `/devloop-expand-driver bench-salvage WS-1`.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Task pack: `.devloop/tasks/TASK_PACK_bench-salvage.json` (WS-1 deliverables/acceptance/guardrails)
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseWS-0-2026-05-30.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseWS-0-2026-05-30.md`
- WS-0 driver: `.devloop/prompts/bench-salvage_phaseWS-0_one_case_over_live_driver.md`
- Roadmap context: `docs/PAPER_OUTLINE.md` (locked one-claim guardrail) + monitor memory `walking-skeleton-architecture`
