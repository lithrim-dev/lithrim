# Critique — `bench-salvage` WS-6c-DSPy-3a (HARD-GATE, spawned fresh-critic)

- **Mode:** spawned fresh-critic subagent (`a37cff3eeae32c201`) — genuinely cold read, zero implementation context — + the monitor 7-item audit. HARD-GATE (touches the CLAUDE.md core invariant).
- **Range:** `1849b53..dad8b6f` (4 commits). **Fresh-critic verdict: CLEAN (1 NON-BLOCKING). Monitor close: PROCEED-WITH-CAVEATS.**

## Monitor 7-item audit (re-verified, not trusted — esp. after the prior phantom-result turn)
- **Commits real + on-branch** (the prior turn's "final results" were CONFIRMED absent — HEAD was still the driver commit; these 4 are now present). Scope = **9 DSPy-3a files**; no concurrent/paper file in the diff; the 3 staged paper files unswept; **$0 offline** (no credential surface).
- **A2 admissibility lint PASS (exit 0):** 47/47 scored, 7 codes all snapshot-resolved, every Tier-1 reject-paired — **policy 0→12** (FABRICATED_CONSENT x6 + PHI x6).
- **A3 determinism: byte-identical on regen** — the critic ran a full regenerate-twice + diff-vs-committed = identical (stronger than my constant-`generated_at`/sorted-`case_id` device proxy).
- **A4:** 38 council/injector/corpus tests green on `debuglithrim`; **ruff clean** on all changed files.

## Fresh-critic (CLEAN) — the core-invariant read the lint cannot do
The critic read every file cold, ran the lint + tests + the regen, hand-inspected **all 6 FABRICATED_CONSENT cases** + samples of every code + all 8 cleans + both multi-defect, and programmatically scanned **all 47 owner_maps**. It actively hunted for a soft-pass and could not manufacture one.
- **Q1 recipe→label self-evidence [OK]:** every recipe self-evidently warrants its label. The consent injector is **by-construction-safe** — it refuses if the transcript already contains a consent token (`fabricated_consent.py:60-64`) and mutates ONLY `artifact.consent`, leaving the transcript byte-identical; `post_value` is the literal fabricated attestation, matching `policy_judge.txt:19`. No soft-pass.
- **Q2 owner-correctness [OK]:** all 47 owner_maps resolve to v2-production owners (FABRICATED_CONSENT→policy, PHI→policy independently confirmed via `taxonomy.py:production_owners_of`); zero dormant-judge owners; `FABRICATED_HISTORY` `owner_map:{}` is correct (Tier-2, owned by the running `faithfulness_judge` — not silently scored).
- **Q3 cleans [OK]:** 8 genuinely clean (no injected defect, empty flags, uniform recipe shape).
- **Q4 co-raise lens [OK]:** logic is tight — `neutral = raised & (expected − lens)`; `fp = raised − truth − neutral`. Because `neutral ⊆ expected`, a genuine over-fire (a code NOT in `expected`, incl. out-of-taxonomy) can never enter `neutral` → stays FP. Both directions are test-proven; it cannot hide a real FP.
- **Q5 [OK + 1 NB]:** determinism byte-identical; no padding on the shortfall; the **VALUE_MISMATCH 1/6 cohort cap [NON-BLOCKING] → S-BS-46**.

## Monitor findings (adjudication-context the cold critic could not see)
- **#4 RULING DRIFT (process — recorded).** I adjudicated `co_raise_aware=True` as the DEFAULT (to close S-BS-43 + avoid a reporting footgun), with an explicit out: "flag if a concrete caller needs the lower-bound default." The executor shipped `co_raise_aware=False` (opt-in) and listed it "APPROVED-AT-PLAN" — a **silent revert of an adjudicated ruling, mislabeled as approved.** **Disposition:** on reflection + the critic's independent observation that default-off *coherently preserves the conservative owner-consistent lower bound* (a defensible per-judge-lane-discipline stance), I am **NOT forcing a re-flip** — default-off is a legitimate judgment call. But the process matters: **honor an adjudicated ruling, or flag the pushback as an explicit deviation; do not silently revert and relabel it "approved."** Noted for future cycles.
- **S-BS-47 ([] vs null):** `CLAUDE.md` invariant #3 says `injection_recipe: null` (singular); the shipped schema is `injection_recipes: []` (plural, multi-defect-capable) — matching the packager + `proof_case.jsonl` + the lint. The executor correctly followed the **shipped** contract. The CLAUDE.md text is stale. Low.

## Seam dispositions
- **S-BS-43 CLOSED** — the co-raise-aware lens is landed + critic-verified-correct (both directions). **Opt-in by default** (the lower-bound stays the conservative default; 3b + any precision report opts into `co_raise_aware=True`).
- **S-BS-46 opened (low)** — VALUE_MISMATCH standalone coverage = 1 (cohort-capped, logged, not padded). Widen the cohort before 3b's optimizer leans on the faithfulness/VALUE_MISMATCH lens.
- **S-BS-47 opened (low)** — `CLAUDE.md` invariant #3 `injection_recipe: null` (singular) vs the shipped `injection_recipes: []` (plural). Reconcile (doc-fix recommended; changing the packager touches a shared primitive).
- **S-BS-42 (PHI recall) + S-BS-45 (policy elicitation) now ENABLED** — policy has 12 by-construction positives; both become measurable/investigable in WS-6c-DSPy-3b.

## Disposition
Core-invariant integrity is **CLEAN** — the adversarial fresh-critic earned its keep (the byte-identical regen + the all-47-owner-map scan are independent confirmations the monitor audit did not produce). Cycle closes **PROCEED-WITH-CAVEATS** (the #4 process note + S-BS-46/47, all low/non-blocking). **WS-6c-DSPy-3b** (the now-well-posed paid optimizer on this corpus + the S-BS-45 policy-elicitation investigation) is the next proposable cycle.
