# Fresh-critic critique — `bench-salvage` DOGFOOD-1 (load real cases → judge-set ladder → run → reusable eval-pack + CI/CD gate)

> **Mode:** HARD-GATE → genuinely-fresh critic (Agent `a33d9235c4d470a4d`, cold context, isolated worktree) + monitor 7-item audit.
> **Date:** 2026-06-09 · **Verdict: NON-BLOCKING** (fresh-critic [0 BLOCKING / 2 NB / 0 OQ]; monitor audit CLEAN). DOGFOOD-1 closes **PROCEED-WITH-CAVEATS** — the offline platform + the premium CI/CD gate are proven; **A-LIVE (the paid composition run + the narrated-video capsule) is OWED, user-run.**

## What landed
The generic eval platform, proven end-to-end on real (synthetic, no-PHI) lithrim-backend cases: **(D1)** an ~80-line importer + 5 second-class `imported_demo` cases + agent seeds; **(D2)** a judge-set ladder — call-time `models=` model-mix sets + `build_trio roles=` for 2/3-judge rosters (no S-BS-98 refactor); **(D3)** `build_pack(in_process=,models=,roles=,assignments=)` + a locked manifest; **(D4)** `pack_gate.py` + `lithrim-bench-pack` — a **Mongo-free CI/CD gate** replicating `ci_cd_gate.py`'s rule (`reliability ≥ threshold AND never_events == 0`, exit 0/1) = the premium eval-pack-SDK parity; **(D5)** the runbook + tests.

## Monitor 7-item audit (independent)
1. **Commits** `6557fb1..f4738ac` (4 executor atomic + the interleaved unrelated SPEC `2c66caf`, docs-only, separable), parent `b692678`, NOT pushed; tree clean except the foreign `root.jsx` (M) + 3 untracked. ✓
2. **Files** = 26 DOGFOOD deliverables (importer + 5 seeds + 3 `imported_demo` jsonl + judge_sets + evalpack + pack_gate + the CLI + the council `roles=` threading + pyproject entry + runbook + 3 test files + the `test_crud_delete` subset edit + session log) — matches the driver + plan-review. ✓
3. **Tests** — monitor re-ran: new **25 passed**; full debuglithrim **506/2/3** (the 2 = the pre-existing S-BS-96 observation pair, **0 new**); ruff clean on all touched. ✓
4. **Scope** — frozen byte-checks **EMPTY** (`compliance_council._apply_consensus`, `judge_metric.py`, `taxonomy_snapshot.json`, `ws0_default.json`, `s_bs_74_demo.json`); `examples/` name-status is `A`-only for `imported_demo_*` (no first-class example modified); `../lithrim-backend` read-only (not in the diff). ✓
5. **Prefs** — pathspec-only (the interleaved SPEC + foreign files never swept); A-LIVE **skipped/owed** (no autostart, no paid run fired); no push. ✓
6. **Session log** present + well-formed (deviations + the 2 seams logged). ✓
7. **Deviations** justified — the gate-ON-for-all confound fix (user-approved at plan-review); the `test_crud_delete` `==`→`<=` subset edit (D1-seed consequence, well-commented, still asserts the 3 canonical seeds); the `pyproject` entry-point. ✓

## Fresh-critic — honesty / non-vacuity checks H1–H6 (all CONFIRMED)
- **H1 — the gate is NON-VACUOUS + correct.** `decide()` = `reliability ≥ threshold AND len(never_events) == 0`; tiers read from the frozen snapshot (`Taxonomy.tier_of`, NOT hardcoded — proven by demoting the flag → the never-event vanishes). **Perturbations:** passing pack → exit 0; verdict-mismatch → 66.7% → exit 1; **Tier-1 false-alarm at 100% reliability → exit 1** (the floor blocks release independently of reliability). 15 gate tests pass.
- **H2 — frozen engine byte-untouched.** Empty diff over the consensus seam / accept-gate / snapshot / seeds; the only council change is the additive `build_trio roles=` (a `ValueError` guard + `for role in selected`) ABOVE `_apply_consensus`.
- **H3 — roster ladder honest.** `_apply_consensus` `min_valid = 1 if gate_mode else 2`; `gate_mode` is the policy-judge-only Lane-1 fast path — NOT repurposed. 2/3-judge rosters grade; 1-judge degenerates to `insufficient_valid_models` and is **documented as a seam**, the seam **never edited**. `dogfood_v1.json` omits a single-role rung.
- **H4 — imported cases genuinely second-class.** `A`-only `imported_demo_*` files; every row `ground_truth_basis:"imported_demo"` + `injection_recipes:[]` (cannot satisfy invariant #2); the strict lint only scans an explicit `--golden PATH`, never globs `examples/` — so they're never auto-linted into the first-class set. Synthetic (Synthea names); PHI scan clean.
- **H5 — model-contrast honest + the test edit not a weakening.** `dogfood_v1.json` applies the same `shared_assignments` to every set (gate ON for all) → the only variables are `models`/`roles` (a test asserts identical non-empty assignments across sets). The `test_crud_delete` edit is `==`→`<=`, still asserting the 3 canonical seeds.
- **H6 — scope/pathspec.** No `root.jsx`/`.claude/`/`apps/shell` in any executor commit; the SPEC touches only its one doc; `pyproject` adds only the entry-point; the `run_eval`/`authored_stage` edits are additive `roles=` threading + 2 ruff line-wraps (no logic change).

**Honesty assessment (critic, verbatim sense):** *nothing manufactures a pass.* The gate's pass/fail is real (the Tier-1 floor is enforced independently + snapshot-driven), the frozen engine is byte-identical, the imported cases are quarantined second-class, and the roster ladder ships only the rungs the frozen consensus genuinely supports.

## Findings
- **S-BS-101 (low, NEW).** Single-judge roster consensus policy: a 1-judge roster degenerates to `insufficient_valid_models` under the frozen `min_valid=2` floor. `build_trio roles=` supports it mechanically, but the consensus won't grade it. If a true single-role council is ever wanted, that's a deliberate `_apply_consensus`/gate-mode decision — out of scope here, the seam was honestly documented + not forced.
- **S-BS-102 (low, NEW — critic NB-1).** `pack_gate.reliability()`/`never_events()` iterate `outcomes` and silently skip an orphan/missing row (`if c is None: continue`). Benign for engine-built packs (always one paired outcome per case), but a hand-authored / partially-built pack could under-count `total`. Defense-in-depth: assert `len(outcomes) == len(cases)` in `decide()`. INFERRED.
- **A-LIVE OWED (user-run, cost-gated).** The honest "Claude vs Azure" composition Δ is not yet measured — correctly scoped out; runbook `docs/runbooks/DOGFOOD_eval_pack.md` ready (~25 Azure calls < $1; `$0` smoke = `all_claude` or `--pack`; BYO-Claude `confidence=None` disclosed). **The narrated-video proof capsule is the owed deliverable tied to this A-LIVE.**
- S-BS-96 re-confirmed (the executor's "second seam") — already tracked; the 2 observation failures are pre-existing + DOGFOOD-1-independent.

## Disposition
NON-BLOCKING → **DOGFOOD-1 CLOSED PROCEED-WITH-CAVEATS.** The generic eval platform is proven **end-to-end on real cases** — import → a judge-set ladder (model-mix + 2/3 rosters, same flags, gate ON for all) → `in_process` run → a reusable eval pack → a **non-vacuous CI/CD gate** (`lithrim-bench-pack`, exit 0/1) that is the Mongo-free parity of the lithrim-backend eval-pack SDK = **the premium product surface**. The frozen grading engine is byte-untouched; the imported cases are honestly second-class. Opened **S-BS-101** + **S-BS-102** (both low). **No proof capsule yet — it is the OWED narrated-video walkthrough tied to the A-LIVE composition run** (user-run; honest-Δ — the contrast is reported as measured, *under grounding*, never a staged win). This cycle is the "usable product" proof the user asked for: the platform performs evals on real data, and the open-core CI/CD-gate surface stands up.

## Post-close — live dogfooding (A-LIVE attestation + gaps surfaced)

The user had the monitor drive the live dogfood from the UI (Chrome MCP, `:5180`, paid-authorized; no autostart — `:8002`/`:8787` health-checked first). The 5 imported cases were seeded into the running BFF config DB (the standard `seed_config_db` path) so they appear in the rail.

**A-LIVE ATTESTED (platform-on-real-cases):** two `Run live` (`:8002` council) evals on real imported cases, driven from the UI —
- `imported_scribe_council_v2_smoke_nka_clean` → **approve** (PASS · 0 active findings · 0 grounded-suppressions · verdict-match PASS). The v2 council correctly did **NOT** false-flag `FABRICATED_ALLERGY` on the no-known-allergies note — well-calibrated, no over-fire. Reported as measured (not a manufactured "watch the floor save it").
- `imported_scribe_scribe_diabetes_soap_clean_violation` → **reject** (BLOCK · 12 active findings incl. the labeled `HALLUCINATED_DETAIL` · **1 grounding-suppression visible live** — `MEDICATION_NOT_IN_TRANSCRIPT` disproved by `med-presence-check/v1`, "metformin present verbatim in the transcript").

So the platform performs real evals on real cases live, with the **grounding floor visibly correcting** — honest results, 2 screenshots captured.

**Still owed — the model-mix composition contrast** (Claude-vs-Azure judge-set ladder): it is `in_process`-only, and the **shell UI does not expose `in_process`** (`runEval` posts `in_process:false`; "Run live" = the `:8002` *default all-Azure* council). So the ladder is **CLI/SDK-only** → **S-BS-105** (the in_process judge-set ladder is not a UI capability). The monitor's credential-less shell also lacked Azure creds for the CLI `in_process` path; the running BFF has them (the UI live runs worked).

**Gaps the dogfooding surfaced (honest, the real value of using the product live):**
- **S-BS-103 (med, NEW):** the conversational chat agent is bound to **`ws0_default`**, NOT the rail-selected agent — asking it to review the imported cases showed `ws0_default`'s runs/audit instead. The chat doesn't follow the UI selection. → the **CHATBIND-1** cycle (user-chosen) binds the chat tool-context to the active agent (A-SAFE intact: paid runs stay human-confirmed). S-BS-98-adjacent.
- **S-BS-104 (low, NEW):** the live council **over-fires** on the imported scribe cases (12 findings on the violation where the case labels one); and the imported scribe note is **free text, not JSON**, so the structural layer flags "Artifact content is not valid JSON". The verdict still matches (reject), but the finding-set is noisy — an import-fidelity / calibration note (the imported_demo cases are second-class by construction).

Honest-Δ held throughout — the correct clean-approve, the noisy-but-correct defect-reject, and the visible grounding correction all reported as measured. **The session itself became the dogfood, and it answered "is it usable?" honestly: yes — real evals on real cases, live, with a strong conversational layer — plus three concrete seams (S-BS-103/104/105) the moment we pushed on it.**
