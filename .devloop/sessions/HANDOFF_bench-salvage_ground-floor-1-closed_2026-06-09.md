# HANDOFF — bench-salvage — 2026-06-09 (GROUND-FLOOR-1 CLOSED → grounding-floor next steps)

> **For the next session.** GROUND-FLOOR-1 closed PROCEED-WITH-CAVEATS (HARD-GATE fresh-critic NON-BLOCKING). The record-presence SUPPRESS floor shipped offline/$0 — the moat's first real per-flag verification contract beyond the lone med one. **Resume:** `/devloop-resume bench-salvage`, read memory `grounding-floor-is-the-moat-next`.

## ✅ What landed (GROUND-FLOOR-1)
The `record_presence` SUPPRESS executor — `InRowTool` grounds an artifact's documented PMH against `patient_profile.conditions` (`snomed_core` string). `conforms is True` → `Verdict(disproved=True)` → a false `FABRICATED_HISTORY` finding leaves `active` → rescore flips **BLOCK→PASS**; ANY ungrounded item → the whole finding **STANDS**; non-SOAP / empty-PMH → never suppress. Registered in `grounding._CONTRACT_EXECUTORS` → wires **both** `ground()` (post-consensus) and the withstands-gate (pre-consensus). **Floor coverage 1/19 → 2/19.**

- Build `8c45ffc..1d5a4a5` (6 atomic pathspec-only, **NOT pushed**).
- Monitor 7-item audit CLEAN + **HARD-GATE fresh-critic `a4e8ba1418e7cfd49` NON-BLOCKING [0/2/1]** — 5 adversarial attacks on the by-construction guard repelled + 5 non-additive ontology mutations caught; full close in `critique-bench-salvage-GROUND-FLOOR-1-2026-06-09.md`.
- **Honest-Δ:** A7/D5 (the visceral live verdict-flip) was **SPLIT, not faked** — the offline mechanism is proven; the live flip is GROUND-FLOOR-1b.

## 🔴 NEXT — monitor's pick (do NOT autostart; the user authorizes paid runs)
1. **GROUND-FLOOR-1b (re-scoped) — design the honest live test.** The naive D5 ("provoke `FABRICATED_HISTORY` over-fire on the clean twin, then `ground()` flips it") most likely **won't reproduce**: per S-BS-74 / S-BS-100 / [[live-overfire-context-primed]] an engineered clean-negative gets *unanimously approved* (0 findings → no FP → no flip). So 1b's first task is **design**, not run: pursue (a) a near-miss surface-mismatch case (an abbreviation/brand-generic the council mis-reads but that grounds clean), or (b) a held-block case where suppression flips WARN→PASS, or (c) accept the offline twin + `8a41ef3e`'s live suppression as the demo. One user-authorized paid run; honest-Δ; proof capsule if it fires.
2. **TERMINOLOGY-1** — the Hermes code-based grounding phase (`subsumed_by`, never fuzzy): generalizes `record_presence` from `snomed_core` string to `snomed_code`, unlocks the 4 coding flags (zero validators today). Spec §4 + the phased plan. The string-match caveat in GROUND-FLOOR-1 is bench-bounded until this lands.
3. **The carried owner-gated push.** The unpushed stack on `bench-salvage/ws6c-dspy` keeps growing (LAUNCH-PREP → CHATBIND-3/4 → calibration → GROUND-FLOOR-1). Owner runs `git push`/PR/tag per `docs/RELEASE_v1.md`.

## ⚠️ Open seam opened this cycle
- **S-BS-113** (med) — `data/ontology/clinical_v1.json` is **stale vs its seed sources**: a clean `seed_ontology.py` re-seed sweeps 3 unrelated pre-existing `owner_roles` additions (policy_judge on FABRICATED_CONSENT, faithfulness_judge ×2 on MISSING_ALLERGY/VALUE_MISMATCH). The committed JSON is correct and the seeder is forward-correct (carries the new contract), but the seeder is not currently the byte-source-of-truth. **Fix = re-snapshot/owner-reconcile** so a clean re-seed reproduces the committed JSON byte-identically (then A5 "re-seed survives" is unconditional). Triage this before the next ontology-touching cycle.

## Standing context (unchanged)
- **No autostart** (`curl /health`, halt+ask if down); **no push without explicit owner approval**; **LLM-cost-conscious** (the user fires paid/live runs); **honest-Δ only** (a manufactured win = FAIL); **pathspec-only commits** (the dirty shared index) [[git-commit-pathspec-dirty-index]]; **shell JSX is hand-compact, NO prettier** [[shell-no-prettier-handcompact-jsx]]; run tests via the explicit `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python` [[council-runtime-test-env]].
- The user runs the executor sessions + the paid/live runs; the monitor audits + commits close artifacts pathspec-only.

## Pointers
- **Authority:** `docs/specs/SPEC_GROUNDING_TOOL_LAYER.md` (Phase-1 done; TERMINOLOGY-1/KB-VENDOR-1/FHIR-1 phased).
- **Memory:** `grounding-floor-is-the-moat-next`, `live-overfire-context-primed`, `jute-for-data-transformations`, `proof-capsule-convention`.
- **Verification core:** `lithrim_bench/verification/` (`jute_gen`/`jute_dspy` for the generated-contract experience — see the spec OQ-4 / the user's "generate-extract-freeze" ideation, a candidate `CONTRACT-AUTHOR` phase).
- **The demo pair:** `examples/proof_case.jsonl` + `examples/judge_calib_v1.jsonl` (`clean_negative_aaecd73c3bcf` / `inject_condition_1bd0f10dc7b5`).
