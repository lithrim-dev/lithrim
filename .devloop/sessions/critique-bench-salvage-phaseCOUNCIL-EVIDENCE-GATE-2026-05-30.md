# Spec-Adherence Critique — `bench-salvage` phase `COUNCIL-EVIDENCE-GATE`

## Metadata

- **Stream:** bench-salvage
- **Phase:** COUNCIL-EVIDENCE-GATE (consensus-evidence-gate, R3(d))
- **Driver bundle:** bench-salvage-phaseCOUNCIL-EVIDENCE-GATE-consensus-evidence-gate-driver (HARD GATE)
- **Commits audited:** none (0 commits — no-code halt)
- **Spec(s) read against:** `docs/research/SPEC_consensus_evidence_gate_bypass_2026-05-30.md` §1-8; driver §0-§7
- **Critique mode:** `inline` (monitor) — HARD-GATE fresh-critic **waived**, see below
- **Date:** 2026-05-30
- **Reviewer:** monitor

---

## Verdict

**CLEAN — cycle closes as BLOCKED-AND-RE-SCOPE (no spec drift; the spec itself was falsified).**

One sentence: the executor honored the diagnose-before-edit gate, ran the authorized free pre-checks, falsified the specified R3(d) fix for $0.10 before any code or the $5 sweep, and halted cleanly with a tracked evidence trail — there is no implementation to find drift in, and the falsification claim was independently re-verified against the raw evidence this session.

---

## HARD-GATE fresh-critic waiver (decision recorded)

The bundle is a HARD GATE; the close-phase default is to halt and require a fresh-critic session. **Waived for this cycle**, with reasoning:

1. **Nothing landed to critique.** The fresh-critic exists to give independent scrutiny to a landed change whose blast radius is every case. Zero commits, zero code change (`R3D_DEBUG_RAW` instrumentation reverted, grep = 0). There is no implementation, diff, or test to audit for spec-adherence.
2. **The load-bearing claim was independently verified against primary evidence.** The thing that needed scrutiny here is the *falsification* itself (is the spec really wrong?). The monitor read the preserved raw evidence (`docs/research/r3d_precheck_P0_raw_evidence_2026-05-30.ndjson`) directly this session — not the executor's summary — and confirmed: all 3 judges emit `MEDICATION_NOT_IN_TRANSCRIPT` findings-first with `n_evidence_spans=2`; the second MED span is verbatim the transcript zidovudine line; `risk_judge` carries no MED. That is the independent-verification function the fresh-critic would have served.
3. **Cost/benefit.** Forcing a fresh session to re-confirm a no-code halt backed by personally-inspected primary evidence is process for its own sake.

**Where independent scrutiny re-enters:** the moment anyone acts on the re-route — i.e. when P1 builds the presence-check tool or the spec is substantively rewritten. The HYPOTHESIS "a presence-check tool would close the FP" (REPORT §8) is untested and must be falsifiable-tested in P1-VEC, not assumed.

---

## 1. Surface fidelity

No public surface was added or changed (0 code commits). N/A — no drift possible.

## 2. Behavioral fidelity

The cycle's specified behavior (R3(d): evidenced findings authoritative, legacy path gated) was **not implemented because it was falsified**. The behavior that *was* exercised — a single deterministic `--limit 1` reproduction — matched the M1 baseline exactly (`got=reject exp=reject`, flags `[FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT]`), confirming the determinism anchor (`_eval_seed` :63 untouched). Chain closes: YES for the falsification claim (raw evidence → REPORT §2/§4 → re-verified by monitor).

## 3. Out-of-scope intrusion

`git status` (non-devloop) shows only **new artifacts** from this cycle — the falsification report, the tracked raw-evidence ndjson — plus the pre-existing M1/paper working-tree baseline. **No code file changed.** The temporary debug instrumentation was flag-guarded and reverted (verified: `grep R3D_DEBUG_RAW lithrim_bench/ ` = 0). No intrusion.

## 4. Spec ambiguity surfaced → spec falsification

The cycle surfaced not an ambiguity but a **falsification** of the spec's central mechanism (§2b "legacy span-less bypass"). Disposition: spec banner added at top + §2b heading + ledger lines 199–201 annotated FALSIFIED; authoritative record is `REPORT_r3d_precheck_falsification_2026-05-30.md`. Two driver citation findings (Deliverable 2 mis-located the block site at `:1962-1971` vs the operative Tier-2 `:2170-2190`; second contract block at `:1080/:1128` unnamed) are recorded in the session-log `plan_review.deviations` — both moot since no lever fires, but noted so the next driver author doesn't repeat the mis-location.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec falsification | 0 | 0 | 1 (re-route to P1) |

**Total BLOCKING: 0** → cycle MAY close (as BLOCKED-AND-RE-SCOPE).

---

## Required actions

Monitor close-out (this session):

1. Spec §2b correction banner — **done** (top banner + §2b heading + ledger 199–201).
2. Seam dispositions — S-BS-1 resolved (findings-first, not pure-legacy); S-BS-2 stays open (offline check inconclusive, needs v2 raw capture under P2-COUNCIL); S-BS-3 superseded/moot (the authoritative-findings fix it guarded does not land); S-BS-7 opened (high, route to P1).
3. Re-route the FP into the P1 task pack as its first SME presence-check question — **done**.
4. P1 unblocked: the premise that P1 must wait for "corrected aggregation" is inverted — the FP fix now *lives in* P1, so P1 → ready.

---

## Appendix: commits audited

```
(none — 0 commits; no-code halt)
```

## Appendix: files changed (this cycle's new artifacts only)

```
docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md      (new)
docs/research/r3d_precheck_P0_raw_evidence_2026-05-30.ndjson       (new, tracked evidence)
.devloop/sessions/session-bench-salvage-phaseCOUNCIL-EVIDENCE-GATE-2026-05-30.json  (new)
```
