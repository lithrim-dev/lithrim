# Inline critique — bench-salvage CE-STANDALONE-1 (generic-pack walking-skeleton)

**Date:** 2026-06-12 (close-out) · **Mode:** inline (Routine, non-frozen) · **Verdict:** CLEAN (PROCEED-WITH-CAVEATS)
**Commits:** fe1d170 (D1 pack) · c996f50 (D2 test) · e2f9b8e (D3 docs) — on `5b6eecf`, 10 files.
**Cold-read basis:** the driver §2/§5 + `git diff 5b6eecf HEAD` + a monitor re-run of `test_standalone_ce.py`.

## 7-item mechanical audit — CLEAN
Commits exist · exactly the 10 deliverable files · no core council/pack file touched (`git diff --name-only` clean of `runtime/council`/`compliance_council`/`judges_dspy`/`safety_flags`/`harness/pack.py`) · monitor re-ran the test (6/6) + ruff clean · A7 boundary grep empty · session log present · the one acceptance reframe (A4) is justified + honest (below).

## The 4 questions
- **Q1 Surface fidelity — PASS.** The pack satisfies the accessor contract (`pack_tiers/owners/lenses/production_judges/prompts/ontology`); judges reuse the 3 deployable role names (OQ-2 boundary); `verification_contracts: []` keeps `:8002` off the path by construction.
- **Q2 Behavioral fidelity — PASS.** (1) 0-leakage: A1 renders all 3 production judges' authored prompts under the generic pack and greps the SPEC §2.1 needle set → 0 hits (the experiment inverted-green). (2) authored grade: A2 grades via `build_authored_semantic_stage` + `grade_inprocess` (the `$0` deviation, approved) → `reject` with `policy_judge` BLOCK[FABRICATED_POLICY], risk/faithfulness PASS — the verdict moves on the authoring marker, deterministic. (3) healthcare-unloaded: A4 via `sys.addaudithook` (below).
- **Q3 Out-of-scope intrusion — NONE.** Exactly the pack + the test + 2 doc edits. No core change. The case lives in `tests/fixtures/standalone/` (approved deviation, keeps the pack dir pure config).
- **Q4 Judgment calls — all surfaced + honest** (the `$0` mechanism; the A4 reframe; the case location).

## The A4 reframe (S-BS-130) — honest, non-vacuous
A4 was "healthcare unloaded — no `packs/healthcare/` path read." The walking-skeleton discovered that `council_roster()` reads `DEFAULT_PACK="healthcare"` metadata for canonical-roster validation even under a non-healthcare pack, so the strict gate could not hold. The reframe is **stricter and more precise, not softer**: (i) **forbids** ANY healthcare DOMAIN content (`ontology.json`/`council_roles`/`floors.py`/`generators`) → asserts zero leak — the load-bearing decoupling claim, which `story_audit` would FAIL; (ii) **permits ONLY** `packs/healthcare/{pack.json,taxonomy_snapshot.json}` (the roster metadata) and asserts nothing else is read. This documents the exact residual coupling (S-BS-130) rather than hiding it. Endorsed.

## Findings (the honest-Δ — neither blocks the pack running; both reshape the program)
- **S-BS-129 (medium)** — the core DSPy `JudgeSignature` (`judges_dspy.py` `_build_signature`) hard-codes clinical prose ("clinical"/"patient"/"hipaa"). OFF the authored render path (A1 clean), bypassed by the `$0` predictor path (pack runs with no core change), but reaches the LLM on the LIVE authored path. A self-closing non-gating diagnostic quantifies the residual. **Corrects the audit** (a THIRD core clinical residue beyond `build_prompt` + `safety_flags`). → folds into **6b-CLEAN** (genericize the signature).
- **S-BS-130 (medium, load-bearing for the RELEASE)** — `DEFAULT_PACK="healthcare"` (`pack.py:46`) → `council_roster()` reads healthcare's `pack.json` + `taxonomy_snapshot.json` for canonical validation regardless of active pack. The active DOMAIN is 100% decoupled (A4 proves it), but **the core cannot ship WITHOUT the healthcare pack present on disk** — directly blocking "releasable standalone CE." Same root as **S-BS-125** (council_roster → canonical). Fix = a **neutral core-shipped DEFAULT_PACK** (declares the generic deployable-judge universe); resolves S-BS-130 + S-BS-125's tripwire together. → a new layer, **CE-PACK-NEUTRAL-DEFAULT**.

## Owed
- The env-gated **live smoke** (A-STANDALONE-5, real BYO provider) — user-fired, no CI spend. Watch whether the clinical `_build_signature` (S-BS-129) degrades the non-clinical verdict — the empirical motivation for the 6b signature cleanup.

**Disposition:** CLEAN. The standalone generic-CE walking-skeleton is real and green; the active-domain decoupling is proven non-vacuously. Two findings surfaced (S-BS-129, S-BS-130) — exactly what a falsification test is for. Register both; fold into the program (6b-CLEAN gains the signature; add CE-PACK-NEUTRAL-DEFAULT).
