# Driver STUB — `bench-salvage` phase `UAP-3b-2`: GroundingCheck first-class entity + the LLM Ralph-Loop critique (the UAP-3b split)

> **STUB — authored by the UAP-3b executor at close to record the pre-authorized
> D-E split (deferred-not-dropped). The monitor expands this into a full bundle via
> `/devloop-expand-driver bench-salvage UAP-3b-2` before handing it to an executor.**
>
> **Parent:** `bench-salvage-phaseUAP-3b-withstands-gate-driver` (the moat CORE landed:
> D1 signals + D2 gate + D4 audit + D5 tests + D6 docs).
> **Authored:** 2026-06-04 (UAP-3b close).

---

## Why this phase (what UAP-3b deferred)

UAP-3b shipped the per-judge, pre-consensus **withstands-gate** (THE MOAT) deterministically
and proved the moat **mechanism** offline (A2: a deterministic signal corrects a wrong judge
→ the composite flips reject→approve, gate-attributable). Three things were split out at
plan-review (D-A + D-E, monitor-approved):

1. **D3 — GroundingChecks as first-class config-authored entities (was UAP-3b A6).** Promote
   the `harness/grounding.py` floor/suppress contracts to **independent, config-plane-declared
   GroundingCheck entities** (an `EvalProfile.grounding_checks` view over the ontology
   `verification_contracts`), run alongside the judges at the existing **post-consensus**
   `ground()`/`composite()` locus (`run_eval.py:224-225`) and distinguished from the
   **judge-attached** validators the UAP-3b signals bus already consumes. Keep `ground()`
   additively identical for the floor-less clinical ontology. *(Light promotion — surface +
   audit; a full config-plane GroundingCheck CRUD UI stays a follow-on.)* **This is the UAP-3b
   A6 acceptance, carried forward.**

2. **The LLM Ralph-Loop critique PASS (D-A).** UAP-3b's gate is deterministic-only (the
   `critique-pass-precision-not-floor` finding: deterministic signals are what close the gap).
   The gate's interface already admits an LLM critique WITHOUT a reshape (`apply_withstands_gate`
   takes the deterministic signals; a `critique=` hook slots in). Add a **cost-gated** gpt-4.1
   critique that produces a *reasoned* withstands-ruling over the SAME signals — richer "why it
   withstands / why it was corrected" prose, never a relabel, always above the frozen seam.

3. **The LIVE moat attestation (S-BS-70's visceral finale).** UAP-3b proved the moat mechanism
   **offline** (injected predictors). The paid "watch a REAL LLM judge get corrected by a
   deterministic signal → the verdict change in the UI" is still owed — a real trio run on a
   case where a base judge genuinely FPs an out-of-lens code (or under-fires a semantic defect),
   the gate corrects it live, the composite flips in-browser. Cost-gated, ~1 run.

## Carry-ins (already built — compose, don't rebuild)
- `runtime/council/signals.py` — `build_judge_signals` (the deterministic SIGNAL engine; reuses
  `grounding._build_contract` + `LENS_BY_ROLE`).
- `runtime/council/withstands.py` — `apply_withstands_gate(results, *, ontology, case, …)` (the
  pre-consensus gate; `critique=` is the un-built LLM hook).
- `harness/correction.py:build_withstands_correction` (`uap3b-withstands-correction/1`) + the
  `withstand` AuditRecord action.
- `harness/config.py:EvalProfile` (`tools`, `kb_bindings` — where `grounding_checks` surfaces).

## Invariants (unchanged from UAP-3b)
- ABOVE the frozen `compliance_council._apply_consensus` (byte-0-delta). Deterministic floor stays
  deterministic (no LLM in the floor — the LLM critique is an ADDITIONAL signal, never the floor).
- The gate **cannot relabel a by-construction case** (the A5 guard: a corroborated/true finding is
  never suppressed). Any LLM critique is bounded by the same guard.
- Pathspec-only; HARD-GATE-class (fresh-critic at close).

## Acceptance sketch (expand at `/devloop-expand-driver`)
- A6: GroundingChecks declared as first-class entities, run at the post-consensus locus,
  `ground()`/`composite()` additively identical for the floor-less clinical ontology; each is
  audited as an independent entity.
- The LLM critique (if pulled in): cost-confirmed, the ruling recorded in the §2B audit, the gate
  interface unchanged for the deterministic path.
- The live moat attestation: one cost-gated real-trio run, the flip captured.
