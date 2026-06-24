# PROBE — Phase 2: can the frozen council admit *arbitrary user-created judges*?

**Date:** 2026-06-25 · **Branch:** `bench-salvage/ws6c-dspy` · **Gate:** SPEC_COMMUNITY_EDITION §8
("test cheaply BEFORE committing"). **Probe test:** `lithrim_bench/runtime/council/tests/
test_phase2_arbitrary_judge_probe.py` (10 deterministic, $0, bare-CE). **Frozen seam UNTOUCHED**
(`_apply_consensus` byte-frozen vs `acc4973` — this probe only READS + monkeypatches a synthetic
taxonomy onto module globals, auto-reverted).

## The question (verbatim from §8)

> does the frozen `_apply_consensus` handle N≠3 votes, AND does every new judge get a **lens + a
> Tier-1 owner** (the owner↔emit invariant forbids an inert owner)?

## Verdict

**Phase 2 is feasible WITHOUT touching the frozen seam — but it is a *structured authoring bundle*
over the taxonomy snapshot, not free-text.** A new judge participates as a first-class vote the moment
it runs; but its codes only COUNT when they are in the active pack's `tiers`, its SOLO one-strike only
exists when it is in `tier1_owners`, and it can raise codes in-scope only when it is in `lenses`. The
corroboration threshold is an ABSOLUTE 2 (frozen) — a bigger council does not raise the bar.

## Evidence

### 1. `_apply_consensus` is `len(valid)`-driven — N≠3 (N≥2) needs no seam edit — **CONFIRMED**

```python
# compliance_council.py:1496-1498  (frozen)
min_valid = 1 if gate_mode else 2
valid = [result for result in results if not result["errors"]]
if len(valid) < min_valid:
    return {"decision": "needs_review", ... "reason": "insufficient_valid_models", ...}
```
```python
# judges_dspy.py:403-406  — the authored (live) path's roster builder, docstring:
# "the frozen _apply_consensus requires len(valid) >= 2 in full-council mode, so a 2- or 3-role
#  roster grades normally but a SINGLE-role roster returns insufficient_valid_models"
# judges_dspy.py:466-472 — aggregation: council._apply_consensus(results, gate_mode=gate_mode)  UNCHANGED
```
The roster identity is already the active pack's `production_judges` (no fixed 3):
```python
# compliance_council.py:495-496
_pack_judges = pack_production_judges()
models = tuple(_ROLE_DEPLOYMENT[_r] for _r in _pack_judges)   # default-council only
```
Probe: `test_consensus_admits_four_judges…`, `…five_judges…`, `…single_role_degenerates` (N=4/5 with
arbitrary role names → a clean verdict; N=1 → `insufficient_valid_models`).

### 2. A new identity IS aggregated; the snapshot is the gate — **CONFIRMED**

The consensus dedups findings by `model` with NO role-allowlist (`compliance_council.py:1618-1632`), so a
new role's finding counts. But a code outside the active taxonomy produces no tier finding.

Probe (synthetic taxonomy: `DEMO_NEVER_EVENT` Tier-1 owned by `policy_judge`):
- `test_new_role_finding_is_aggregated_into_tier1`: `clinical_safety_judge` + `policy_judge` flag
  `DEMO_NEVER_EVENT` → `tier1_triggered == ["DEMO_NEVER_EVENT"]`. The new identity counted.
- `test_unknown_code_is_dropped…`: two judges flag `NOT_IN_TAXONOMY` with evidence → `tier1 == []`,
  `tier2_flagged == []`. The snapshot is the by-construction contract.

### 3. One-strike needs registered OWNERSHIP; corroboration is ABSOLUTE-2 — **CONFIRMED**

```python
# compliance_council.py:1700  (frozen)  — solo Tier-1 authority is gated on ownership
owners = _TIER1_OWNERS.get(violation, set())     # off-domain solo firing → downgraded
# corroboration thresholds are an absolute >= 2 (1678 / 1730 / 1789), NOT proportional to N
```
Probe:
- `test_new_role_solo_tier1_downgrades_without_ownership`: a new role's SOLO `DEMO_NEVER_EVENT` (it does
  NOT own it) → `tier2_flagged == [("DEMO_NEVER_EVENT", "tier1_off_domain_single_judge")]`, `tier1 == []`.
- `test_registered_owner_solo_one_strike_fires`: `policy_judge` (the registered owner) solo → `tier1 ==
  ["DEMO_NEVER_EVENT"]`.
- `test_corroboration_is_absolute_two_not_proportional_to_n`: 2-of-5 corroborate → `tier1` fires. The bar
  is absolute 2 regardless of N. **We cannot make it proportional without touching the frozen seam.**

> Caveat (scope): the probe asserts on `evidence_summary` tier bookkeeping, NOT the composed final
> `decision` — the v2 llama-veto / artifact-pillar layer maps tier findings → verdict and is pack/verdict-
> mapping-specific (observed live: under `support_ticket_qa` a triggered Tier-1 did not always compose to
> `reject`). The Phase-2 question is judge admission, which the tier bookkeeping answers directly.

### 4. The lens authority — an unregistered role is MUTE — **CONFIRMED**

`LENS_BY_ROLE` ← the snapshot `lenses` block (`judge_metric.py:64`); the withstands-gate scope-checks each
raised code against it. Probe `test_unregistered_role_has_empty_lens`: an unknown role → empty lens (every
code out-of-scope); `risk_judge` → non-empty (non-vacuous contrast).

### 5. The owner↔emit authoring contract, vs a REAL non-clinical pack — **CONFIRMED**

`test_support_pack_owner_emit_invariant…` reads `packs/support_ticket_qa/taxonomy_snapshot.json`:
every Tier-1 owner role ∈ `production_judges` (no inert owner); a hypothetical `escalation_judge` is absent
from `production_judges` + `lenses` + `tier1_owners` → must be authored in all three.

### 6. Two judge-binding planes — **CONFIRMED**

- **Default council** (`ComplianceCouncil.__init__`): `models = tuple(_ROLE_DEPLOYMENT[r] for r in
  pack_production_judges())` — an identity NOT in the frozen 3-`CouncilModel` tuple → `KeyError` fail-clean,
  and that tuple is INSIDE the frozen seam. **Dead on the product path** (CE-PACK-6b-ROUTE).
- **Authored / live path** (`build_judge_lm`, `judges_dspy.py:266,278`): `_ROLE_DEPLOYMENT.get(role,
  "AZURE_OPENAI_DEPLOYMENT_COUNCIL")` / `_OPENAI_ROLE_MODEL.get(role, "OPENAI_MODEL_RISK")` — permissive,
  a new role binds to a default. **`judges_dspy.py` is NOT the frozen seam** → extensible.

## What a new judge needs (the Phase-2 authoring bundle) — grounded in the evidence

1. **Roster** — add the role id to the pack snapshot `production_judges` (≥2 total; never a 1-judge council).
2. **Lens** — a `lenses[role]` entry (codes it may raise) — else mute at the withstands-gate (§4).
3. **Owner (optional, for one-strike)** — a `tier1_owners[code]` entry — else its solo findings downgrade;
   it still corroborates (§2/§3). **Owner↔emit:** every owner must be a running `production_judge` (§5).
4. **Deployment binding** — extend `judges_dspy._ROLE_DEPLOYMENT` / `_OPENAI_ROLE_MODEL` / `V2_ROLES` (core,
   NOT frozen), or bind via the model registry (extend the BFF per-role env maps from 3 → N).
5. **Role prompt** — an authored role prompt (`judge_assignment.load_role_prompt`).
6. **Codes in `tiers`** — any code the judge raises must be in the snapshot `tiers` (§2).

## The fork, resolved

- **Arbitrary-N judges (N≥2): YES, no frozen-seam edit.** The consensus already runs variable rosters.
- **True per-judge cross-PROVIDER: NO (separate seam, S-BS-MR1a-CROSSPROVIDER)** — `build_judge_lm` reads a
  global `LITHRIM_LLM_PROVIDER`; per-role is model/deployment only. A new judge runs on the global provider.
- **Proportional consensus for large councils: NO** — the absolute-2 corroboration is frozen; surface it
  honestly in the Phase-2 UX rather than imply a bigger council is a higher bar.

## Recommended Phase-2 build shape (for review — NOT yet built)

A **judge-authoring surface over the snapshot** (the snapshot stays the contract; the frozen seam stays
frozen): UI/agent authors `{role id, lens codes, optional owned codes, deployment binding (pool entry),
role prompt}` → writes the pack snapshot blocks + the `judges_dspy` role maps → the new judge joins the
authored trio→N-tet. Admissibility gate at author time enforces the bundle (owner↔emit, lens non-empty,
codes ∈ tiers, roster ≥2). This composes the model registry (MR-1a/1b/1c, deployment) + the existing
authoring plane (lens/prompt). **Deferred decision for the owner:** proportional-vs-absolute consensus is
out of scope (frozen) — accept absolute-2 + document, or revisit the seam under an explicit moat decision.
