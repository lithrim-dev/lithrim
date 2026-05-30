# HANDOFF — `bench-salvage` phase `COUNCIL-EVIDENCE-GATE` (halted) → phase `P1` kickoff

> Written by the monitor on cycle close (2026-05-30). Load-bearing context for the next monitor session.

---

## What just landed

- **Closed phase:** `COUNCIL-EVIDENCE-GATE` — **HALTED / BLOCKED-AND-RE-SCOPE, 0 commits, no code changed.**
- **Critique verdict:** CLEAN — cycle closes as re-scope; no implementation to find drift in. HARD-GATE fresh-critic **waived** (no-code halt + monitor independently re-verified the raw evidence). File: `.devloop/sessions/critique-bench-salvage-phaseCOUNCIL-EVIDENCE-GATE-2026-05-30.md`
- **Audit verdict:** CLEAN (no code, instrumentation reverted, working tree clean of cycle code).
- **Session log:** `.devloop/sessions/session-bench-salvage-phaseCOUNCIL-EVIDENCE-GATE-2026-05-30.json` (verdict BLOCKED)
- **Falsification record:** `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md`
- **Raw evidence (tracked):** `docs/research/r3d_precheck_P0_raw_evidence_2026-05-30.ndjson`
- **Spec corrected:** `docs/research/SPEC_consensus_evidence_gate_bypass_2026-05-30.md` — top banner + §2b heading + ledger 199–201 marked ⛔ FALSIFIED.

## What's next

- **Next phase:** `P1` — SQLite data layer + SME-Question Ontology + **the first SME presence-check question (re-routed scribe_v1 MED FP, S-BS-7).**
- **Driver bundle:** `bench-salvage-phaseP1-sqlite-data-layer-sme-ontology-driver` (**stub** — author with `/devloop-expand-driver bench-salvage P1`)
- **Blocked by:** none. P1 is **READY** (unblocked 2026-05-30).

## Open seams for `bench-salvage`

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-BS-1 | v1 pure-legacy vs findings-first | medium | — | COUNCIL-EVIDENCE-GATE planning | **resolved** — findings-first, not pure-legacy (pre-check P0) |
| S-BS-2 | v2 over-fire span class | medium | v2 raw capture under P2-COUNCIL | COUNCIL-EVIDENCE-GATE planning | **open** — offline check inconclusive (projection-lossy); needs v2 raw capture |
| S-BS-3 | blast radius of authoritative findings | high | — | COUNCIL-EVIDENCE-GATE planning | **superseded/moot** — guarded fix does not land |
| S-BS-4 | SQLite doc-shim vs relational | medium | `runtime/services/` | M1 close-out | open — decide consciously **in P1** (recommended doc-shim) |
| S-BS-5 | local vector stub; sqlite-vec blocked | medium | `runtime/pipeline/retrieval.py` | M1 close-out | open — numpy spike in P1-VEC |
| S-BS-6 | v1-vs-v2 canonical config | medium | `compliance_council.py` v2 | M1 close-out | open — resolved in P2-COUNCIL |
| **S-BS-7** | **MED FP is judge-calibration, not aggregation** | **high** | **P1 / P1-VEC presence-check tool** | COUNCIL-EVIDENCE-GATE pre-check P0 | **open — P1's first SME question** |

## Load-bearing context the next monitor MUST know

1. **The blocker premise inverted — that is why P1 is ready, not blocked.** P1 was originally gated behind COUNCIL-EVIDENCE-GATE so the ontology bindings would be "built on corrected aggregation, not a known-FP baseline." The pre-check proved the FP is **not** an aggregation defect at all — it is a judge-reasoning miss (the judge cites the transcript line that *contains* zidovudine as proof of its *absence*). The fix lives **in** P1/P1-VEC (a per-question presence-check tool), so there is nothing upstream to wait for. The MED FP is now P1's worked example and motivates the per-question KB-retrieval binding directly.

2. **The S-BS-7 fix is a HYPOTHESIS — do not let P1 assume it works.** "A presence-check tool closes this FP" is untested (REPORT §8). The falsifier is a P1-VEC presence-check prototype run on `scribe_v1` case 1 under the deterministic seed: does it suppress `MEDICATION_NOT_IN_TRANSCRIPT` *without* dropping the true defect `FABRICATED_HISTORY`? P1 specifies the binding; P1-VEC (where retrieval is real, not stubbed) runs the falsifier. The diagnose-before-edit gate carries forward. This is also where independent scrutiny re-enters, since the HARD-GATE fresh-critic was waived for the no-code halt.

3. **The bench is a calibration instrument, not just a reproduction harness (user, this cycle).** The user reframed the stream: the value is being able to tweak judge prompts and give judges per-question KB-query tools — "reproduce paper findings" is the acceptance test, not the goal. The COUNCIL-EVIDENCE-GATE falsification is the first demonstration the instrument works: for $0.10 it isolated a calibration miss the aggregation layer could never have fixed, and the persisted-judge-reasoning enabler (M1, SPEC §6) is what made that offline root-cause possible without paid re-runs. Decide S-BS-4 (doc-shim vs relational) consciously during P1 — recommended document-shim; it gates the P-CLUSTERS vendoring shape and P4 separability.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (phase table + open seams + First move).
3. Read this handoff doc.
4. Read `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md` and the session log.
5. `git log --oneline -10`.
6. Author the P1 driver via `/devloop-expand-driver bench-salvage P1`. Don't autonomously start the cycle.

## References

- Stream state: `.devloop/state/STREAM_bench-salvage.md`
- Prior cycle session log: `.devloop/sessions/session-bench-salvage-phaseCOUNCIL-EVIDENCE-GATE-2026-05-30.json`
- Prior cycle critique: `.devloop/sessions/critique-bench-salvage-phaseCOUNCIL-EVIDENCE-GATE-2026-05-30.md`
- Falsification report: `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md`
- Falsified spec (banner-corrected): `docs/research/SPEC_consensus_evidence_gate_bypass_2026-05-30.md`
- Task pack: `.devloop/tasks/TASK_PACK_bench-salvage.json` (P1 now `ready`; S-BS-7 registered)
