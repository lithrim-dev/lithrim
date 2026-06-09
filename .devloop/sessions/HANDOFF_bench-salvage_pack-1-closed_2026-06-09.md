# HANDOFF — bench-salvage — 2026-06-09 (PACK-1 layer-1a CLOSED → the strangler-fig continues)

> **For the next session.** PACK-1 (healthcare-realm-as-pack, layer-1a) closed PROCEED-WITH-CAVEATS (HARD-GATE fresh-critic NON-BLOCKING [0/2/0]). The ontology+taxonomy realm is physically out of the core and in a loadable `healthcare` pack — the core↔domain boundary is now grep-verifiable. **Resume:** `/devloop-resume bench-salvage`, read memory `healthcare-realm-as-pack`.

## ✅ What landed (PACK-1 layer-1a)
The clinical `ontology` + `taxonomy_snapshot` `git mv`'d (**R100 byte-identical**) into `packs/healthcare/{ontology,taxonomy_snapshot}.json`. The core resolves them via `harness/pack.py` `active_pack()` (default `healthcare`, `LITHRIM_BENCH_PACK`-overridable) instead of the two hardcodes. An AST-parse consistency gate bridges the still-FROZEN council (`KNOWN_TAXONOMY_CODES`) and fails closed — so 1a ships **above the frozen seam** (`compliance_council.py` byte-untouched). Build `dd8b78d..953da37` (5 atomic pathspec-only, **NOT pushed** — local SSOT).

- **Decisions (user-locked):** D-B = **RELOCATE** (the 8 seeds get a behavior-preserving `ontology_path`-only edit; **A5 re-scoped** from "seed files frozen" → "seed *behavior* frozen", enforced by the new test guard `assert_seed_ontology_path_relocated_only`); the 5 generator provenance labels stay as historical record.
- **CLAUDE.md** coupling-point relocated to `packs/healthcare/taxonomy_snapshot.json` — *the invariant moves into the pack, it does not weaken*.
- Monitor 7-item audit CLEAN + fresh-critic `a288ace3f4072d77b` NON-BLOCKING (SHA256 byte-identity, moat-guard defeated 6 ways, gate works in the no-openai env, A2 pydantic-deep-equal). Full close: `critique-bench-salvage-PACK-1-2026-06-09.md`.

## 🔴 NEXT — the strangler-fig continues (do NOT autostart)
The boundary is real for layer 1. Continue extracting the healthcare realm, **one layer at a time, green at each step** ([[healthcare-realm-as-pack]]):
- **Layer 2 — judges → pack.** The clinical judges (risk/policy/faithfulness roles + their config) relocate into `packs/healthcare/`. Author the layer-2 driver (same shape as PACK-1; HARD-GATE-class if it touches judge config).
- **Layer 3 — floors / verification-contracts → pack.** The grounding contracts (incl. GROUND-FLOOR-1's `record_presence`) move with the pack.
- **Layer 4 — journey literals + the FE fixtures (S-BS-114) → pack.** `apps/shell/src/data.jsx:13` / `cards.jsx`.
- **Layer 5 — dataset → pack.** The clinical agents/cases become pack content (so load/unload fully switches the eval domain).
- **Layer 1b (gated, separate authorization) — un-freeze the council's `KNOWN_TAXONOMY_CODES`.** Today it's hardcoded in the FROZEN `compliance_council.py:292` + the consistency gate bridges it. 1b makes the council read taxonomy from the loaded pack — a frozen-seam change that needs your explicit go.

The founder-dogfood (**scribe + coding** = healthcare-pack content; **story-audit** = a 2nd pack) validates the seam — the clinical↔story delta is where the interface gets carved. The story-audit's admissibility is the cliché/repetition floor (D-C: the floor IS the by-construction label).

## ⚠️ Seams opened (all low) + owed
- **S-BS-114** — apps/shell FE fixtures stale `ontology_path` (layer-4; frozen, green).
- **S-BS-115** — docs/ + a research script reference the old path (docs sweep).
- **S-BS-116** — the 5 generator provenance labels stamp a now-dangling path; forward-fix = stamp the active-pack-resolved path when corpora regenerate (corpus-regen layer).
- **OWED:** the **PAID before/after eval on `ws0_default`** (you fire paid runs; A2 already proven $0 via byte + typed equality — this is belt-and-suspenders).
- Pre-existing carried: **S-BS-96** (the 2 observation-isolation failures), **S-BS-113** (`seed_ontology --check` STALE owner drift — byte-identical to pre-move).

## Standing context (unchanged)
No autostart; **no push — local is SSOT (no remote)**; LLM-cost-conscious (you fire paid runs); honest-Δ only; pathspec-only commits (the dirty shared index); shell JSX hand-compact NO prettier; run the council suite via `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python`. The user runs the executor + paid/live runs; the monitor audits + commits close artifacts pathspec-only.

## Pointers
- **Authority:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the healthcare-realm-as-pack §; Phase-1) + `SPEC_EVAL_SCENARIOS.md` (SCENARIO-1, D-C).
- **Memory:** `healthcare-realm-as-pack` (the layered plan + the frozen-seam tension), `conversational-first-core-plugin-line`, `jute-generated-contracts-unification`.
- **The pack:** `packs/healthcare/pack.json` + `lithrim_bench/harness/pack.py` (`active_pack`, the gate).
