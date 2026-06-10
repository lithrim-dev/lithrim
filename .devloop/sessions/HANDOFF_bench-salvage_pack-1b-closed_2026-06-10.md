# HANDOFF — bench-salvage — 2026-06-10 (PACK-1b CLOSED → the council taxonomy is UN-FROZEN; the endgame is half-done)

> **For the next session.** PACK-1b (council taxonomy un-freeze, layer 1b) closed PROCEED-WITH-CAVEATS (HARD-GATE fresh-critic `aeb96d98f752fc53f` NON-BLOCKING [0/2/2]). **The first substantive edit inside the FROZEN `compliance_council.py` succeeded, value-preserving.** The council now reads its taxonomy FROM the active pack. **Resume:** `/devloop-resume bench-salvage`, read memory `healthcare-realm-as-pack`.

## ✅ What landed (PACK-1b)
The FROZEN `compliance_council.py` resolves its 3 tier sets (`TIER_1_NEVER_EVENTS`/`TIER_2_HIGH_RISK`/`TIER_3_MEDIUM`) **from the active pack's `taxonomy_snapshot.json`** via the PACK-2 inline-`__import__` carve-out (`harness/pack.py:pack_tiers()`). The pack snapshot is now the **single source of truth**; the 1a one-way ⊆ gate became a self-consistency no-op; equivalence is re-pinned by `tests/test_pack_layer1b.py` (a `[council]`-env test that imports the council). **Behavior 0-delta — same 19 values (8/7/4), different source** (the `sorted()` DSPy prompt is byte-identical; the consensus oracle is green unchanged). Build `856deba..728c5fb` (6 atomic pathspec-only, NOT pushed).

- **The crux — value preservation — CONFIRMED in `[council]`:** `council-resolved TIER_1/2/3 + KNOWN == acc4973 literals == snapshot == load_taxonomy() == 19`.
- **The relaxed freeze guard is non-vacuous BOTH directions** (critic induced all 3 failure modes); its residual is parity with PACK-2 (→ S-BS-124, a someday-hardening).
- **The carve-out is exactly 2 hunks vs `acc4973`** (taxonomy + the pre-existing prompts-dir); 2b (`_TIER1_OWNERS`/roster/`LENS_BY_ROLE`) + the moat (`signals`/`withstands`) + the ontology are **byte-frozen**.
- **S-BS-123 closed** — the carve-out broke a 2nd `ast.literal_eval`-of-the-tier-literals site (`scripts/seed_ontology.py`, which the driver §1.5 under-enumerated); fixed in-cycle (tiers→snapshot, output-neutral), critic-confirmed there's **no 3rd reader**.

## 🗺️ Finish-line map — the endgame is half-done
`PACK-1a..5b (relocation arc) ✓ → PACK-1b (council TAXONOMY un-freeze) ✓ → PACK-2b (council ROSTER/owners/lens un-freeze) → the council reads its FULL config from the pack = the true finish.`
After 1b the council reads taxonomy from the pack; 2b is the remaining hardcode (the roster + `_TIER1_OWNERS` + `LENS_BY_ROLE`).

## 🔴 NEXT — PACK-2b (the meatier half; the user directs — do NOT autostart)
**2b = un-freeze the council's roster + owners + lens.** Distinct from 1b (taxonomy was 4 contiguous symbols; 2b is more invasive):
- `_TIER1_OWNERS` (`compliance_council.py:232`) → pack-resolved (the snapshot already carries `tier1_owners`); `council_roster()` (`pack.py:137`, which AST-`literal_eval`s `_TIER1_OWNERS`) is the **3rd AST-reader** that will break — re-point it atomically (the S-BS-123 pattern, now expected).
- The `CouncilModel` roster (`compliance_council.py:485-516`, inside `__init__`) → role names driven by `manifest["judges"]` + snapshot `production_judges` (provider/deployment fields stay infra-config).
- **THE SCOPING FORK (decide before authoring 2b):** `LENS_BY_ROLE` (`judge_metric.py:110`) is the **moat's owner authority** (`signals.py:10`) and is hardcoded clinical content in a non-frozen module — but the snapshot carries **no lenses**. Either pack-resolve it (needs a new snapshot/manifest field or derive from the ontology) OR leave it hardcoded. This is the load-bearing 2b decision; raise it at plan-review (or surface to the user first).
- The freeze guard relaxes AGAIN (S-BS-124 compounds — harden the changed-hunk-shape assertion at/with 2b).

## ⚠️ Seams + owed
- **Closed:** S-BS-123 (the 2nd AST-reader; fixed + critic-confirmed complete).
- **Opened:** S-BS-124 (low — the carve-out guard's inside-an-authorized-hunk residual; harden with 2b).
- **Carried:** S-BS-113 (the seed `--check` owner_roles drift — pre-existing, from the untouched `_TIER1_OWNERS`; NOT 1b's; relevant to 2b which touches `_TIER1_OWNERS`), S-BS-117/118/119, S-BS-96.
- **OWED:** the PAID before/after on `ws0_default` (user-fires; offline mechanism proven $0).

## Standing context (unchanged)
No autostart; **no push — LOCAL is SSOT (no remote)**; LLM-cost-conscious (the user fires paid/live runs); honest-Δ only; **pathspec-only commits** (the dirty shared index); shell JSX hand-compact **NO prettier**; council suite via `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python`. HARD-GATE critics: `isolation:'worktree'`, scan the close-commit output for `[detached HEAD]`; re-spawn on infra stall. Green by **0-new-at-parent in the same env** (the live-key tests fail in a bare worktree but pass credentialed; both 0-new — S-BS-117/119). **`git stash` is BANNED mid-cycle** (it clobbered uncommitted work once).

## Pointers
- **Authority:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the Layer-1b LANDED entry) + CLAUDE.md (the taxonomy snapshot is now load-bearing **at runtime** — the council reads it).
- **Memory:** `healthcare-realm-as-pack` (1b done; 2b next), `devloop-critic-worktree-isolation`, `clinical-ontology-reseed-owner-drift` (S-BS-113).
- **The seam:** `compliance_council.py:176-199` (the taxonomy carve-out) + `harness/pack.py:pack_tiers()` + `tests/_seam_freeze.py:assert_compliance_council_carveouts_only` (the relaxed guard) + `tests/test_pack_layer1b.py` (equivalence + the `_tiers_fixture` non-vacuity). Full close: `critique-bench-salvage-PACK-1b-2026-06-10.md` + `session-bench-salvage-phasePACK-1b-2026-06-10.json`.
