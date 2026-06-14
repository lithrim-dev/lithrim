# Handoff — `bench-salvage` → next session (post-PACK-DIST-2)

> Written at phase close, 2026-06-14. **PACK-DIST-2 is CLOSED CLEAN.** The CE/pack clinical
> split is finished: CE is genuinely clinical-free on scripts + fixtures + tests, the pack repo
> is self-contained + CI-authored. Executed via the "no inline" discipline — scoped + authored
> the driver, then delegated 4 fresh-critic-gated batches to executor agents.

## What landed (PACK-DIST-2, LOCAL, not pushed — both repos)

- **D1** `323fcf3` re-point the 3 generic admissibility scripts off the gone path · **D2** `23c20d3` lock the canonical invocation + standalone-CE hermeticity · **D3** `ba1e2dc` the neutral `_core` house fixture + chokepoint + ~11 plumbing tests genericized + the `ground_floor1` latent crash fixed.
- **D4** CE `a9ae8a3` / PACK `71d0379` move 34 clinical scripts · **D5** CE `0ef0b8d` / PACK `52fe8c7` relocate the clinical tests + author the pack `tests/conftest.py` + shrink the CE ledger.
- **C1** CE `f5e93e3` / PACK `9a95926` extract the 8 unlisted MIXED modules + **retire `_RELOCATED_FUNCS`** · **C2** CE `421c192` relocate `ws0` + re-point consumers · **C3** CE `d8cad59` / PACK `2bd6ef2` **decouple `seed_ontology` from the BFF** (new `lithrim_bench/harness/admissibility.py` — the one snapshot path) + relocate it.
- **D6** PACK `93f341c` pack CI + Makefile + `pyproject testpaths` (collection trap fixed) + ruff.toml · **D7** CE `955526c` / PACK `4a73a1e` relocate 12 clinical-experiment doc capsules (reference-safe).
- Ledger (CE): `25b5eb0` driver + `0465a4f`/`52e163e`/`42775d2` batch records + the close commit.
- ⚠️ A parallel `.devloop` session committed PACK `4d5b368` (lint auto-fix) between D6 and D7 — benign, makes `ruff check` green; the pack history has this one non-PACK-DIST-2 commit.

## State (verified on the integrated final state)

- **A1–A11 met** (A10 conservatively partial-by-design — the no-broken-link rule wins). Moat **byte-frozen** (0-line cycle diff; guard trio 27 passed). CE 527 passed / 2 pre-existing S-BS-96 / bare-CE 527 collected 0 errors; pack 170 passed / 10 skipped. Both trees clean. BFF PUT /v1/ontology gate behavior-preserved.

## Follow-ons (none blocking — each its own small driver when picked)

- **PACK-DIST-3** — the history-preserving subtree split (gated out: the pack has 5 orphan TOOL-2 commits + no CE ancestry + the move renamed paths; a rewrite risks the moat hash attestations). Provenance archaeology, not load-bearing.
- **S-BS-142** — the A10 doc residual: ~4 KEEP-anchored clinical capsules (REPORT_fhir_agentbench, REPORT_semantic_moat_proof, +2) need their KEEP-file citations rewritten before they can relocate.
- **S-BS-143** — rewrite-or-retire the 4 `record_presence` funcs honest-`@skip`'d as TOOL-2-superseded (redundant with the pack's `test_specificity_flip`).
- **S-BS-144** — the 2 S-BS-96 observation-pipeline tests (full-suite sys.modules ordering; pass in isolation) → a subprocess-hermeticity de-flake.
- **Pack CI is LATENT** until both repos are pushed (`ci.yml` checkout uses a placeholder ref; `make test` is the local equivalent). Re-point on push.

## Next moves (do NOT autostart — user steers)

The bench-salvage post-pack arc options remain: the **EVAL-FLOW** product surface (pick N cases → evaluate → calibrate → Eval Pack), **KB-VENDOR-1** (vendor the Pinecone pipeline, drop the SDK/Mongo coupling), the **SEAM-HARDEN** quick wins (S-BS-140/141/143/144), or **PACK-DIST-3**. Plus the owner-gated push (LOCAL SSOT — user keeping LOCAL, explicitly fine).
