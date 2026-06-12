# Handoff — `bench-salvage` → next phase (HPACK or PACK-DIST-2)

> Written at the PACK-DIST-1 close, 2026-06-12. The clinical realm is now physically
> external; the OSS core is release-clean. The next monitor presents; the user picks.

## What just landed — PACK-DIST-1 (the clinical realm is PHYSICALLY EXTERNAL)

- **Verdict:** CLOSED — monitor 7-item audit CLEAN + HARD-GATE fresh-critic **NON-BLOCKING [0 BLOCKING / 2 NON-BLOCKING]**. The critic independently reproduced A1/A2/A4/A5 in a clean worktree.
- **CE repo (`lithrim-bench`):** `9168670..4573088` (7 code commits) + `3501639` (session log). Parent baseline `af25065`; moat baseline `acc4973`. Branch `bench-salvage/ws6c-dspy`, **not pushed**.
- **Pack repo (`../lithrim-pack-healthcare`):** `0d61175` (initial healthcare pack) + `fca2147` (dogfood_v1). A **local `git init`, 0 remotes** — LOCAL SSOT.
- **Session log:** `.devloop/sessions/session-bench-salvage-phasePACK-DIST-1-2026-06-12.json`
- **Critique:** `.devloop/sessions/critique-bench-salvage-PACK-DIST-1-2026-06-12.md`

What moved out of CE → the sibling pack repo: the `healthcare` pack (`packs/healthcare/**`), the 11 by-construction `examples/*.jsonl` corpora, the 7 clinical demo agent seeds, and `data/config/judge_sets/dogfood_v1.json`. What stayed (decoupled): the 4 fixture/sample packs (`_tiers_fixture`, `_plugin_fixture`, `_nondeployable_fixture`, `story_audit`) now carry their own generic `council_roles/`; `ws0_default.json` is a genuine blank slate (0 clinical strings); `DEFAULT_AGENT="ws0_default"` unchanged → `apps/bff/` byte-identical.

## What's next — the user's call (do NOT autostart)

**(a) HPACK — build the 1st Pro plugin IN the pack repo `../lithrim-pack-healthcare`.** This is the user's stated goal: *"I need the vector querying + snomed mcp tool, tie in the product narrative."* Scope: the SNOMED terminology floor (code-based subsumption grounding — fuzzy search is UNSAFE, ground by code; Hermes-as-MCP is LIVE-PROVEN) + vector/KB querying (keep Pinecone `hipaa-compliancev2`, vendor the pipeline, drop `lithrim_search_sdk`) + the SNOMED MCP tool + clinical cases + the product narrative. See [[grounding-floor-is-the-moat-next]], [[healthcare-realm-as-pack]], [[kb-grounding-corpus-hipaa-compliancev2]], TERMINOLOGY-1. **HPACK has its own CE/Pro split:** if it needs a new generic `tool`-kind plugin interface in the *core*, that is a **separate CE cycle in `lithrim-bench`** (open/closed — the pack must not require core engine edits).

**(b) PACK-DIST-2 — the deferred CE polish.** The clean clinical-test MOVE into the pack repo (today they skip-when-absent) + pack-repo CI/devloop + the history-preserving subtree split + **S-BS-135..139** (the script path-repoints · the `tests/fixtures/ws0/` house-fixture genericization · lock the canonical dev invocation · standalone offline-key hermeticity). None of these block HPACK.

**(c)** CHATBIND-2 (chat-drives-the-3rd-pane; also the deferred `frontend` plugin kind). **(d)** the owner-gated **push** (LOCAL SSOT — user keeping LOCAL, explicitly fine).

## Open seams (this stream)

All five new seams are **PACK-DIST-2-bound**, none blocks HPACK:
- **S-BS-135** (low) — clinical `scripts/` default at the now-gone in-repo paths (passive residual, not in the wheel).
- **S-BS-136** (medium) — clinical tests skip-when-absent vs the clean MOVE into the pack repo.
- **S-BS-137** (medium) — `tests/fixtures/ws0/` scribe house fixture stays in CE (the agent-seed mandate IS met; this is the test-fixture residual).
- **S-BS-138** (low, critic OQ) — `LITHRIM_BENCH_PACKS_DIR`-alone dev invocation races the council import → lock the canonical invocation.
- **S-BS-139** (low, critic) — standalone proofs depend on the council conftest's offline-key leak.

Prior open seams unchanged: **S-BS-132** (ACCEPTED won't-fix — frozen-inert source_message machinery, re-openable only if a future cycle touches the frozen council).

## Load-bearing context the next monitor MUST know

**The discovery seam + the dev/CI invocation gotcha.** A pack id resolves via `pack.py` `_pack_root`: installed entry point (`lithrim_bench.packs` group) → `LITHRIM_BENCH_PACKS_DIR` (os.pathsep-joined) → in-repo `packs/`. Manifest refs are now **pack-root-relative** (`_resolve_ref`), so a pack is relocatable. **To run the clinical suite in dev/CI you MUST either `pip install -e ../lithrim-pack-healthcare` (entry-point — robust) OR set BOTH `LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare` AND `LITHRIM_BENCH_PACK=healthcare`.** Setting `PACKS_DIR` alone races the council's import-time `KNOWN_TAXONOMY_CODES` bind (active pack is `_core` until `tests/conftest.py` setdefault-pins) → 12 `PackConsistencyError` collection errors. That error is the consistency gate behaving *correctly* (fail-closed), not a regression (S-BS-138). A bare CE checkout (neither set) stays on the neutral `_core` default and the clinical suite **skips-when-absent** via the new root `conftest.py` (RELOCATED / NEEDS_PACK, function-level).

**HPACK builds in the pack repo, never back in core.** The whole point of PACK-DIST-1 was to make `lithrim-bench` release-clean. Do NOT reintroduce clinical content into `lithrim-bench` — `tests/test_pack_dist.py` A2 is the tripwire (a planted clinical needle on the shipped data surface fails the sweep; the 4-file passive carve-out is bounded by `test_a2_carve_out_is_minimal`). The pack repo is free to add floors/tools/cases (its code is NOT under the frozen-seam discipline), **but** the core's moat stays frozen: `compliance_council.py` is byte-identical vs `acc4973` (`_apply_consensus` `d1b7956e`, `extract_verdict_confidence` `ed867bce`); the frozen council binds the pack only through the authorized inline-`__import__` carve-outs (`pack_tiers`/`pack_tier1_owners`/`pack_lenses`/`pack_production_judges`) and the `*_path` resolvers. **R-GUARD** (binding): never put the license gate on the 4 council accessors.

**Standing rules (persist):** LOCAL is SSOT — neither repo pushed (owner-gated; user keeps it LOCAL, explicitly fine). Services are user-run — curl-check, never autostart. Commits pathspec-scoped (`git commit -m … -- <files>`, never bare — the shared branch accumulates foreign staged files). HARD GATEs need a fresh-critic worktree pass before close. Honest-Δ — no manufactured wins (the commercial moat).
