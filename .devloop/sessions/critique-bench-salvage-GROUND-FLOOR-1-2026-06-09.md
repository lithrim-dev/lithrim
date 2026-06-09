# Critique — bench-salvage / GROUND-FLOOR-1 (record-presence suppress floor) — 2026-06-09

> **HARD GATE.** Genuinely-fresh critic session (agent `a4e8ba1418e7cfd49`, 117.9k tokens / 34 tool-uses / ~9.4 min), spawned with NO prior context and an adversarial "try to break it" mandate. This doc records the verdict; the monitor 7-item mechanical audit (CLEAN) precedes it.

## Verdict: NON-BLOCKING [0 blocking / 2 non-blocking / 1 open-question]

The cycle PASSES the HARD GATE. The record-presence suppress floor is wired, the by-construction invariant holds under attack, the ontology edit is provably additive, and the two GO-approved deviations are sound.

## Monitor 7-item mechanical audit — CLEAN (precedes the critic)
| # | Item | Result |
|---|---|---|
| 1 | Scope | 9 files = 5 deliverables + 3 seam-reconcile + 1 session log; all in-bounds |
| 2 | FROZEN 0-delta | `_apply_consensus` / judges_dspy consensus seam / `judge_metric` / `ws0_default` seed / `taxonomy_snapshot` — 0-delta (targeted `git diff` empty) |
| 3 | Ontology additive | `clinical_v1.json` diff = the single `record_presence` contract (12 lines, sorted keys), no owner/flag/severity sweep |
| 4 | Tests | monitor re-ran the new + reconciled guards: 11 passed in 0.30s |
| 5 | Guards correct | `_decode_artifact_soap` plaintext (base64 dropped per D-B); empty-extract + non-SOAP guards present & faithful |
| 6 | Deviations | S-BS-113 (additive hand-add + seeder constant) + moat carve-out (byte-freezes the seam) both sound |
| 7 | Hygiene | tree clean, no foreign sweep, $0, no push |

## Fresh-critic adversarial findings (all 7 priority probes CONFIRMED)

1. **By-construction guard (the moat invariant) — CONFIRMED.** The suppress can NEVER clear a true fabrication. 5 scratch attacks: TP twin `inject_condition_1bd0f10dc7b5` STANDS (`conforms=False`, ungrounded=`['Diabetes mellitus type 2 (disorder)']`); FP twin `clean_negative_aaecd73c3bcf` flips `BLOCK→PASS` (proven NOT pre-passing — pre-suppress is BLOCK); injected ungrounded leukemia bullet → repelled; `_core` qualifier-strip collision ("Hypertensive crisis" ≠ "Hypertension") → no over-match; partial N-1 grounding → BLOCK (all-or-nothing, `conforms = len(ungrounded)==0`).
2. **A3 16/16 non-vacuous — CONFIRMED.** Census: exactly 12 `inject_condition` + 4 `scribe_clean_negative` = 16; test asserts exact class counts; perturbation (grounding the fab item) flips that case BLOCK→PASS → real discriminator, not a tautology.
3. **Empty-extract guard non-vacuous — CONFIRMED.** `items_checked` pre-exists in `tools.py:140` (not in the cycle diff); raw InRowTool conforms vacuously on `[]` (the trap is real) but `RecordPresence.check` reads `items_checked==0 → disproved=False`.
4. **Moat-freeze carve-out — CONFIRMED, cannot be defeated.** 5 non-additive mutations (owner_roles += / edit the med contract / remove a contract / flip `gradeable` / tamper `severity_map`) ALL CAUGHT; a purely-additive new contract correctly PASSES. `cur == base` vs `acc4973` after popping `verification_contracts` + every baseline contract still present.
5. **Frozen set + scope — CONFIRMED.** `git diff 8c45ffc HEAD` touches only the 9 in-scope files; 0-delta on the frozen set; `clinical_v1.json` = the single additive contract.
6. **Import isolation — CONFIRMED.** `import lithrim_bench.harness.grounding` → `leaked: []` (no httpx/dspy/onnx/pinecone); the `from lithrim_bench.verification import …` is lazy inside `check()`.
7. **A5 re-seed deviation (S-BS-113) — CONFIRMED right call, honest.** The seeder carries `RECORD_PRESENCE_CONTRACT`; the hand-added JSON is byte-identical to the seeder's `sort_keys` emit; a clean re-seed would sweep 3 unrelated pre-existing `owner_roles` additions (policy_judge / faithfulness_judge ×2) → hand-add keeps the diff additive-only + leaves an honestly-tracked seam rather than hiding drift.

## Non-blocking findings
1. **Pre-existing test-isolation pollution = S-BS-96 (not new).** Full debuglithrim suite `533p / 2f / 3skip`; the 2f (`test_observation_pipeline.py::{test_importing_observation_does_not_load_compliance_modules, test_default_run_pulls_no_heavy_deps}`) fail in the full run, pass in isolation, and fail identically at parent `8c45ffc` (524p/2f). GROUND-FLOOR-1 adds +9 passing, 0 new failures. Folded into **S-BS-96**; canonical baseline reconciled to 533/2/3.
2. **String-match caveat — real but honestly disclosed.** `snomed_core` is sound only because the bench mints note-PMH and `conditions` from identical FSN strings; the code docstring + contract + SPEC + driver all state it and defer code-based resolution to **TERMINOLOGY-1**. Not a defect.

## Open question
- **D5 split, not run → GROUND-FLOOR-1b.** The paid live-confirmation run was correctly deferred (honest-Δ rationale recorded: the captured over-fire is a *different* case firing HALLUCINATED_DETAIL/INCOMPLETE_DOCUMENTATION, and S-BS-74 shows the clean twin is unanimously approved → a live FH flip likely won't reproduce). Offline mechanism fully proven; the live verdict-flip remains unconfirmed by design. No action for this gate — surfaced so 1b isn't forgotten.

## Disposition
- **S-BS-113** opened (med) — the `clinical_v1.json` seed↔source staleness (re-snapshot/owner-reconcile).
- **S-BS-96** reconciled (533/2/3; +9 passing, 0 new) — no new seam.
- **GROUND-FLOOR-1b** = the deferred, re-scoped honest live test (design a near-miss / held-block case; per S-BS-74/S-BS-100 the naive clean-twin probe likely won't fire).
- Tree clean at `1d5a4a5`; no tracked file modified by the critic.
