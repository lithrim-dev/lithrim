# HANDOFF — bench-salvage — 2026-06-09 (PACK-2 layer-2 CLOSED → the strangler-fig continues to layer-3)

> **For the next session.** PACK-2 (healthcare-realm-as-pack, layer-2: judges → pack) closed PROCEED-WITH-CAVEATS (HARD-GATE fresh-critic `afda337585b683404` NON-BLOCKING [0/1/1]). The clinical council **role prompts** are physically out of the core and in the loadable `healthcare` pack — the **judge** layer of the core↔domain boundary is now grep-verifiable. **Resume:** `/devloop-resume bench-salvage`, read memory `healthcare-realm-as-pack`.

## ✅ What landed (PACK-2 layer-2)
The 5 council role prompts (`council_roles/{risk,policy,faithfulness,behavior,source_message}_judge.txt`) `git mv`'d (**R100 byte-identical**) into `packs/healthcare/council_roles/`. Both readers now resolve via `harness/pack.py` `pack_prompts_path()`: the council-LIGHT `judge_assignment.py:25` (direct edit, above the seam) and the **FROZEN** live council `compliance_council.py:470` (the **authorized surgical carve-out** — a path-only, behavior-preserving edit, inline `__import__` to keep it to ONE diff hunk). A `assert_pack_judges_consistent` + `council_roster()` AST-gate (no council import — the core env has no `openai`) bridges to the still-frozen roster/owners. Build `11b3811..5efbc1c` (6 atomic pathspec-only, **NOT pushed** — local SSOT).

- **The layering nuance (why NOT "same shape as PACK-1"):** in 1a the council carried a *value-copy* of the codes (byte-untouched); here the live council **globs the prompt files itself** (`_load_role_prompts`), so relocating them forced the carve-out. **User-authorized** the surgical path-only touch (the BYOC-1/GROUND-FLOOR/PACK-1 carve-out precedent), guarded by a `difflib` one-hunk freeze.
- Monitor 7-item audit CLEAN + fresh-critic NON-BLOCKING (carve-out one-hunk path-only; R100 SHA256-matched; frozen engine/roster/owners/taxonomy byte-0-delta; boundary real [empty `git ls-files`, bogus pack fails clean]; gate non-vacuous + both defeat-tests fail correctly; **0-new test failures**). Full close: `critique-bench-salvage-PACK-2-2026-06-09.md`.

## 🔴 NEXT — the strangler-fig continues (do NOT autostart)
Continue extracting the healthcare realm, **one layer at a time, green at each step** ([[healthcare-realm-as-pack]]):
- **Layer 3 — floors / verification-contracts → pack.** The grounding contracts (incl. GROUND-FLOOR-1's `record_presence` suppress floor) move with the pack. Author the layer-3 driver (same shape; HARD-GATE-class if it touches the grounding wiring). **Watch for a frozen-seam analogue:** the floors live in `harness/grounding.py` + the ontology's `verification_contracts` — check whether anything frozen reads them before scoping a clean "above-the-seam" cut.
- **Layer 4 — journey literals + the FE fixtures (S-BS-114) → pack.** `apps/shell/src/data.jsx` / `cards.jsx`.
- **Layer 5 — dataset → pack.** The clinical agents/cases become pack content (load/unload fully switches the eval domain).
- **Layer 2b (gated, separate authorization) — un-freeze the council's roster/`LENS_BY_ROLE`/owners.** Today the role NAMES + lenses + owners stay hardcoded in the FROZEN `compliance_council.py`/`judge_metric.py`; the AST gate bridges them. 2b makes the council read its roster FROM the pack — a frozen-seam change needing your explicit go. **Layer 1b** (un-freeze `KNOWN_TAXONOMY_CODES`) still also deferred.

## ⚠️ Seams opened + owed
- **S-BS-117** (low, NEW) — `examples/judge_calib_v1.jsonl` carries a machine-ABSOLUTE `cohort_path`, so the determinism guard `test_uap4_corpus_superset::test_committed_corpus_matches_a_fresh_generator_run` is non-portable (fails on any checkout at a different path — it failed in the critic's worktree; passes canonical). Fix = record a relative/normalized `cohort_path` at corpus-regen. Self-contained spin-off candidate.
- **OWED (carried, unchanged):** the **PAID before/after eval on `ws0_default`** (you fire it; A2 proven $0 via byte-identity — belt-and-suspenders, same OWED as PACK-1).
- Pre-existing carried: **S-BS-96** (the ~2 canonical isolation-sensitive full-suite failures; ~5 in a bare worktree — env/path artifacts, all 0-new), **S-BS-113/114/115/116**.

## ⚠️ The green-bar lesson for the next monitor (diagnose-before-edit)
The executor's handback green-bar numbers (`554p/2f S-BS-96`) did NOT match the fresh critic's worktree re-run (`537p/5f`, different tests). **Resolution: both were "right" for their environment** — the suite has **test-isolation + env sensitivity**. A bare worktree surfaces MORE failures (missing `AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3`; the absolute-`cohort_path` corpus guard; 3 `assert case is not None` isolation failures that pass in `-k` isolation). PACK-2 = 0-new was triple-confirmed (critic parent re-run + 18 disputed tests pass canonical + observation 13/13). **Takeaway:** when a critic runs in `isolation:'worktree'`, expect env/path-sensitive pre-existing failures the canonical checkout doesn't show; verify "0-new" by re-running at parent IN THE SAME ENV (the critic did), not by comparing absolute counts across environments.

## Standing context (unchanged)
No autostart; **no push — local is SSOT (no remote)**; LLM-cost-conscious (you fire paid runs); honest-Δ only; pathspec-only commits (the dirty shared index — `git commit -- <files>`, never bare); shell JSX hand-compact NO prettier; run the council suite via `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python`. HARD-GATE critics spawn with `isolation:'worktree'` (scan close-commit output for `[detached HEAD]`).

## Pointers
- **Authority:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the healthcare-realm-as-pack §; Phase-1, now with the judge layer recorded).
- **Memory:** `healthcare-realm-as-pack` (the layered plan + the prompts-as-carve-out vs roster-as-2b nuance — UPDATED this cycle), `conversational-first-core-plugin-line`, `devloop-critic-worktree-isolation`, `council-runtime-test-env`.
- **The pack:** `packs/healthcare/pack.json` (now declares `council_roles`) + `lithrim_bench/harness/pack.py` (`pack_prompts_path`, `assert_pack_judges_consistent`, `council_roster`).
- **Driver:** `.devloop/prompts/bench-salvage_phasePACK-2_healthcare-pack-judges-layer_driver.md`; session log `session-bench-salvage-phasePACK-2-2026-06-09.json`.
