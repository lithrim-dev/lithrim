# HANDOFF — bench-salvage — 2026-06-10 (PACK-5b CLOSED → the core-boundary relocation is FINISHED)

> **For the next session.** PACK-5b (healthcare-realm-as-pack, layer-5b: the core-boundary finisher) closed PROCEED-WITH-CAVEATS (HARD-GATE fresh-critic `a5bec7f38933138d6` NON-BLOCKING [0/3/2]). The last 4 clinical agent-type generators + the `_pmh` residual are OUT of the core. **The strangler-fig's relocation arc is DONE: `grep lithrim_bench/` carries no relocatable clinical generation CODE — only the FROZEN council remains.** **Resume:** `/devloop-resume bench-salvage`, read memory `healthcare-realm-as-pack`.

## ✅ What landed (PACK-5b)
The clinical **hl7_adt / coding / scheduling / triage** generation realms — their injectors + synthesizers + the 4 `PackDefinition` recipes — relocated **byte-verbatim** (only imports re-pointed: core→absolute `lithrim_bench.*`, intra-pack→relative `.`) into `packs/healthcare/generators/`, through the proven `load_pack_generators` interface PACK-5a built. The `_pmh` scribe residual (S-BS-121) relocated with them; the 2 pack scribe synths flip to relative `._pmh`. Core `lithrim_bench/packs.py` is now a **thin resolver** (`_CORE_PACKS = {}` + the `PackDefinition` class + `active_packs()`); `injectors/__init__.py` = the generic `base` re-exports only; `synthesizers/` git-removed. Build `d185b56..426914b` (6 atomic pathspec-only, NOT pushed — LOCAL is SSOT).

- **The crux — by-construction byte-identity × 4 — CONFIRMED (strongest evidence).** The critic's worktree had the cohort, so it ran the gold-standard method: regenerate all 4 corpora at `d185b56` (pre-move) vs HEAD (post-move) with a fixed `--generated-at` → **all 4 sha256-identical**. Every `injection_recipe` + `expected_safety_flags` unchanged across the move. The recipe IS the label; the relocation didn't touch it.
- **FabricatedConsent-excluded invariant** preserved byte-exact + proven non-vacuous (critic added it to the scheduling list → the scheduling gate failed → reverted).
- **Boundary milestone met:** `injectors/`=base-only, `synthesizers/` gone, `_CORE_PACKS=={}`, all 5 recipes pack-sourced, no core→pack leak (AST), `import lithrim_bench.packs` heavy-dep-free.
- Monitor 7-item CLEAN; OQ-1 (debuglithrim) monitor-resolved (51/51 relocation suites green in py3.10.15; the only full-suite failures = the 2 pre-existing S-BS-96 observation guards, causally disjoint → 0-new CONFIRMED). Full close: `critique-bench-salvage-PACK-5b-2026-06-10.md`.

## 🗺️ Finish-line map — the relocation arc is COMPLETE
`PACK-1 (ontology/taxonomy) ✓ → PACK-2 (judges) ✓ → PACK-3 (floors, first packs-as-CODE) ✓ → PACK-5a (scribe generation, the UNIFY) ✓ → PACK-5b (coding/hl7/scheduling/triage + _pmh + thin core) ✓ → grep lithrim_bench/ ≈ empty (only the FROZEN council) → 1b/2b (un-freeze the council) = the true endgame, DEFERRED behind explicit authorization.`
A pack is now **data + grading + generation**, and the core↔domain boundary is grep-and-AST verifiable. Layer-4 (FE journey) was DROPPED — a frozen pitch demo in a separate app, a product follow-on, not a core-boundary layer.

## 🔴 NEXT — monitor's pick (do NOT autostart; the user authorizes the next cycle)
The relocation finisher is done, so the candidates are now cleanups + the endgame:
1. **1b/2b — un-freeze the council** (un-hardcode `KNOWN_TAXONOMY_CODES` at `compliance_council.py:292` [1b] + the roster/`LENS_BY_ROLE`/owners [2b]). **The true finish, but DEFERRED behind explicit user authorization** — touches the frozen seam. The monitor brings it as an explicit decision.
2. **S-BS-122** (low) — the stale `active_packs()` docstring (a 4-line fix; offered as a supplement at close).
3. **The docstring-scrub** of the generic-engine examples in `runtime/pipeline`/`backends` (§5-deferred trivial cleanup; makes `grep` literally clean).
4. **S-BS-117** — normalize the committed corpora's absolute `cohort_path` to a repo-relative provenance string so the byte-identity gates pass in any worktree/CI (the recurring per-cycle worktree cycle-tax; now widened by 4 baselines).
5. Or a non-pack stream (the eval/corpus-depth fork: S-BS-46/49).

## ⚠️ Seams + owed
- **Closed:** S-BS-120 (`--generated-at` frozen-timestamp flag) · S-BS-121 (`_pmh` relocated).
- **Opened:** S-BS-122 (low — stale `active_packs()` docstring, packs.py:64-68).
- **Carried:** S-BS-117 (corpus abspath, now +4 baselines), S-BS-118 (packs-as-code trust surface, Phase-3-deferred), S-BS-119 (gitignored fixtures), S-BS-113/114/115/116, S-BS-96 (the 2 observation guards).
- **OWED:** the PAID before/after on `ws0_default` (user-fires; A2 proven $0 by byte-identity).

## Standing context (unchanged)
No autostart; **no push — LOCAL is SSOT (no remote)**; LLM-cost-conscious (the user fires paid/live runs); honest-Δ only; **pathspec-only commits** (the dirty shared index); shell JSX hand-compact **NO prettier**; council suite via `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python`. HARD-GATE critics: `isolation:'worktree'`, scan the close-commit output for `[detached HEAD]`; re-spawn on infra stall. Green by **0-new-at-parent in the same env**, never absolute counts (S-BS-117/119).

## Pointers
- **Authority:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the Layer-5b entry + the unified pack model) + CLAUDE.md (labels true by construction).
- **Memory:** `healthcare-realm-as-pack` (the layered plan — now relocation-complete), `conversational-first-core-plugin-line`, `devloop-critic-worktree-isolation`.
- **The pack:** `packs/healthcare/{pack.json,generators/,floors.py,council_roles/,ontology.json,taxonomy_snapshot.json}` + `harness/pack.py` (`load_pack_generators`/`load_pack_floors`/`active_pack`/`pack_prompts_path`) + `lithrim_bench/packs.py` (`active_packs()` thin resolver).
