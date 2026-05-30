# HANDOFF — `bench-salvage` phase `WS-1` → phase `WS-2` kickoff

> **Written by the monitor on cycle close (2026-05-30).** Load-bearing context for
> the next monitor session. Committed alongside the close-out commit.
>
> **Path:** `.devloop/sessions/HANDOFF_bench-salvage_phaseWS-2_kickoff_2026-05-30.md`

---

## What just landed

- **Closed phase:** `WS-1` — SQLite config plane + ontology data model (commits `6f4612f..0c73ff0`, 8 atomic; session-log commit `6d26a4e`)
- **Critique verdict:** `NON-BLOCKING FINDINGS` (`.devloop/sessions/critique-bench-salvage-phaseWS-1-2026-05-30.md`)
- **Audit verdict:** `CLEAN` (7/7; re-ran 99/99 tests + ruff clean; seed-not-import + zero-paid-call re-verified)
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseWS-1-2026-05-30.json`
- **What it delivered:** `lithrim_bench/harness/{ontology,config,collections}.py`; a byte-deterministic `data/ontology/clinical_v1.json` (23 flags / 16 questions / 1 verification_contract / severity_map) built by `scripts/seed_ontology.py`; a committed `data/config/agents/ws0_default.json` driving `scripts/run_eval.py` (canonical) with `run_ws0.py` as a thin shim over one grounding path. WS-0 critique Q4.2 + Q4.3 **closed** (severity thresholds + extraction params as data); Q4.1 **recorded-only** (owner_roles in the correction record). S-BS-4 (doc-shim), S-BS-6 (compose-over-live-v2 stored), S-BS-9 (shape contract) all **resolved**.

## What's next

- **Next phase:** `WS-2` — generalize `:8002` grading to accept injected config (domain-agnostic)
- **Driver bundle:** `bench-salvage-phaseWS-2-generalize-backend-config-injection-driver` (**stub** — not yet authored)
- **Driver path:** `.devloop/prompts/bench-salvage_phaseWS-2_*.md` (run `/devloop-expand-driver bench-salvage WS-2`)
- **Blocked by:** **S-BS-10 must be decided first** (see context #1). Also note WS-2 **touches `../lithrim-backend/`** — confirm hardness at expansion (likely re-classifies from routine).

## Open seams for `bench-salvage`

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-1 | v1 pure-legacy vs findings-first | medium | resolved |
| S-BS-2 | v2 over-fire family | medium | open → WS-3 grounding targets (FABRICATED_CONSENT + INCOMPLETE_DOCUMENTATION visible in WS-0/WS-1 active findings) |
| S-BS-3 | blast radius of authoritative findings | high | superseded/moot |
| S-BS-4 | SQLite shape | medium | **resolved (WS-1)** — doc-shim |
| S-BS-5 | local vector stub | medium | open → WS-3 |
| S-BS-6 | v1-vs-v2 baseline | medium | **resolved (WS-1)** — compose-over-live-v2 stored |
| S-BS-7 | MED FP = judge calibration | high | HYPOTHESIS confirmed (WS-0); generalized to ontology contract (WS-1); mid-loop → WS-3 |
| S-BS-8 | null-code findings | medium | handled (WS-0 skip-log) |
| S-BS-9 | divergent expected-verdict shape | low | **resolved (WS-1)** — shape contract + normalizer |
| **S-BS-10** | **ontology flag-source fork — 4 flags outside `taxonomy_snapshot.json`** | **medium** | **open — WS-2 pre-condition** |

## Load-bearing context the next monitor MUST know

1. **S-BS-10 is a `taxonomy/` contract decision and gates WS-2 — do not let it slip.** `seed_ontology.py` sources 23 flags from the council's `runtime/council/safety_flags.py`, but four — `FABRICATED_CONSENT_SCOPE`, `MALAFFI_CODE_PROPAGATION`, `MISSING_DUAL_CODING`, `WRONG_PATIENT_INFO` — are **absent from `taxonomy/taxonomy_snapshot.json`**, which `CLAUDE.md` §"Taxonomy snapshot is the contract" makes the single coupling point / contract-of-record. The WS-1 executor handled them correctly (`tier=null`, surfaced in diagnostics) and they're inert for WS-1 (the WS-0 case uses only in-snapshot flags). But the moment WS-2 lets the ontology drive *live grading*, the harness has two flag-source-of-truth surfaces. **Decide before WS-2 lands:** backfill the 4 into the snapshot (via `scripts/snapshot_taxonomy.py`, never hand-edit), OR have `seed_ontology.py` treat the snapshot as the tier/owner/membership authority and the council source as definitions-only. This is a contract change — **user-confirm before it lands.**

2. **WS-2 is the first cross-repo cycle since the pivot — it edits `../lithrim-backend/`.** The deliverable adds Optional `council_config`/`ontology` to `PipelineRequest` (`app/services/pipeline/models.py:237`; the `council_config` object hook is already at `:191`) threaded into `run_semantic`/`build_prompt` + model selection + tier/owner lookup, **additive and backward-compatible** (existing clinical callers unaffected by Optional-with-default). The harness then injects the Agent's stored `council_config` (the S-BS-6 disposition, currently *stored only*) into the live evaluate call. Because it touches a backend contract surface, **the WS-2 driver should likely be HARD-GATE** (fresh-critic close, not inline) — confirm at expansion. Per-repo atomic commits (no cross-repo single commit).

3. **The Q4.1/owner-roles thread is for WS-4, but it's already half-built.** Every WS-1 correction record now carries `owner_roles`, sourced from `_TIER1_OWNERS` only (8 of 23 flags; `[]` for the rest — the role-file "CODES YOU MAY RAISE" eligible-raiser lists were deliberately NOT merged). When WS-4 locks the calibration gate, the "correct" predicate must be role-aware/composite-based (the WS-0 Q4.1 landmine), and it will have to decide whether calibration ownership = `_TIER1_OWNERS` (authoritative single-judge-BLOCK ownership) or the broader eligible-raiser set. The data to make that choice is now recorded; the decision is not yet made.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + open seams — both updated at this close; note S-BS-10).
3. Read this handoff doc.
4. Read the WS-1 session log + critique (`session-`/`critique-bench-salvage-phaseWS-1-2026-05-30.{json,md}`).
5. `git log --oneline -12` in `lithrim-bench` (`6f4612f..6d26a4e` are the WS-1 cycle).
6. Wait for user input. Next action: settle S-BS-10, then `/devloop-expand-driver bench-salvage WS-2`. Don't autonomously start the cycle.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Task pack: `.devloop/tasks/TASK_PACK_bench-salvage.json` (WS-2 deliverables/acceptance/guardrails)
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseWS-1-2026-05-30.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseWS-1-2026-05-30.md`
- WS-1 driver: `.devloop/prompts/bench-salvage_phaseWS-1_sqlite_config_plane_driver.md`
- Contract-of-record: `taxonomy/taxonomy_snapshot.json` + `CLAUDE.md` §"Taxonomy snapshot is the contract" + `scripts/snapshot_taxonomy.py`
- Monitor memory: `walking-skeleton-architecture`, `etlp-ecosystem-capability-map`
