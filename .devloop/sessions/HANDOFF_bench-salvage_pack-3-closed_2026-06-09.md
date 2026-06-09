# HANDOFF — bench-salvage — 2026-06-09 (PACK-3 layer-3 floors CLOSED → packs-as-code landed)

> **For the next session.** PACK-3 (healthcare-realm-as-pack, layer-3 floors) closed PROCEED-WITH-CAVEATS (HARD-GATE fresh-critic `a24596f7030bc9a07` NON-BLOCKING [0/2/1]). The clinical grounding executors are OUT of the core engine and in the loadable `healthcare` pack — the **FIRST packs-as-CODE** step. **Resume:** `/devloop-resume bench-salvage`, read memory `healthcare-realm-as-pack`.

## ✅ What landed (PACK-3 layer-3)
The clinical grounding executors — `RecordPresence` + `_decode_artifact_soap` (from `harness/grounding.py`) and `InRowTool` + `DosageGroundingTool` + the SOAP/PMH/dose extractors `_core`/`extract_pmh_items`/`extract_plan_dose_tokens`/`_norm_dose`/`_DOSE_RE` (from `verification/tools.py`) — relocated **behavior-identical** into the new `packs/healthcare/floors.py`, behind a pack executor-registration interface: `pack.load_pack_floors()` importlib-loads the manifest's `floors` module (cached on the resolved pack id → one stable class identity, else `isinstance` breaks); the engine lazily merges via `grounding.suppress_executors()`/`floor_executors()`/`floor_contract_types()` (dep points **pack→core**, no cycle, `import grounding` stays stdlib-only — A6); `_run_floor` became registry-dispatch (inline branches lifted verbatim). The generic engine (`ground()`, `_build_contract`, `PresenceCheck`, `KbGrounding`, the generic toolbox) stays core. **THE MOAT** (`signals.py:183`, the UAP-3b withstands-gate) reads the pack-merged registry — proven non-vacuous (monkeypatch the pack registries → empty → the `record_presence` signal vanishes + suppression disappears). Build `ca54008..f5e6590` (8 atomic pathspec-only, NOT pushed — LOCAL is SSOT).

- **A1 re-scoped (user-approved at plan-review, the only material deviation):** the driver's literal `grep dosage → empty` over the engine was unsatisfiable — the generic `PresenceCheck` (stays core) reads a FROZEN `dosage_regex` ontology contract param key (`grounding.py:137`), and the `dosage_grounding`/`record_presence`/`in_row` NAME constants are interface vocab in `spec.py`. Re-scoped to the PACK-1/2 precedent — precise clinical-CODE needles (`class RecordPresence`/`InRowTool`/`DosageGroundingTool`, `def extract_*`, literals `soap_pmh_items`/`snomed_core`/`dose_token`) absent-in-engine + present-in-pack, with a CLOSED enumerated carve-out. Boundary fully grep-verifiable.
- Monitor 7-item audit CLEAN + fresh-critic CONFIRMED (7 ways, couldn't break it): behavior-identity AST-verbatim (every moved symbol byte-identical bar `RecordPresence`'s 2 non-logic deltas), `_run_floor` behavior-preserving, lazy merge cycle-free + fail-clean, boundary real + helper partition correct, frozen seam 0-delta, 0-new both envs. Full close: `critique-bench-salvage-PACK-3-2026-06-09.md`.

## ⚠️ DURABLE NOTE — the green-bar baseline (read before the next fresh critic)
For TWO cycles running (PACK-2 + PACK-3), the fresh-critic worktree saw a different failure count than the executor's canonical run. Root cause now nailed: **`examples/proof_case.jsonl` is gitignored + untracked** (`git check-ignore` confirms) but present on disk in the canonical checkout. So a bare `isolation:'worktree'` critic lacks it → ~3 spurious failures (5 total: + the S-BS-117 absolute-`cohort_path` corpus test + a byoc env-var test); the canonical checkout shows ~2. **Both are 0-new at parent.** Opened **S-BS-119**. **Judge green by *0-new at parent in the same env*, NEVER by absolute counts.**

## 🔴 NEXT — the strangler-fig continues (do NOT autostart)
- **Layer 4 — journey literals + FE fixtures → pack.** `apps/shell/src/data.jsx` / `cards.jsx` (+ the S-BS-114 stale `ontology_path` fixtures). A cleaner DATA relocation (like PACK-1/2), but it spans the FE — expect the shell-JSX hand-compact-NO-prettier hazard. Author the PACK-4 driver (HARD-GATE-class if it touches journey-bound config).
- **Layer 5 — dataset → pack** (the clinical agents/cases become pack content; load/unload then fully switches the eval domain → the boundary grep returns empty = the completion test).
- **Layer 2b** (un-freeze the roster/`LENS_BY_ROLE`/owners) + **layer 1b** (un-freeze `KNOWN_TAXONOMY_CODES`) — both still gated behind explicit authorization.

## ⚠️ Seams + owed
- **S-BS-118** (low) — packs-as-code trust surface: a Pro pack now ships in-process Python (`importlib.exec_module` from the manifest's `floors` ref). Loader fails-clean; license/sandbox Phase-3-deferred, flagged in the spec. (Executor labeled it `S-BENCH-SALVAGE-PACK3-1`.)
- **S-BS-119** (low) — gitignored `examples/proof_case.jsonl` → worktree/CI/fresh-clone spurious failures (see the durable note).
- **NB2** (cosmetic, fixed at close) — `SPEC_PLUGIN_ARCHITECTURE` `signals.py:182`→`:183`.
- Carried: S-BS-117 (corpus abspath), S-BS-113/114/115/116, S-BS-96 (canonical observation isolation-order pair).
- **OWED:** the PAID before/after on `ws0_default` (user-fires; A2/A4 already proven $0 via byte-behavior identity).

## Standing context (unchanged)
No autostart (`curl /health`, halt+ask if down); **no push — LOCAL is SSOT (no remote)**; LLM-cost-conscious (the user fires paid/live runs); honest-Δ only; **pathspec-only commits** (the dirty shared index); shell JSX hand-compact **NO prettier**; run the council suite via `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python`. HARD-GATE critics: spawn with `isolation:'worktree'`, scan the close-commit output for `[detached HEAD]`.

## Pointers
- **Authority:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the Layer-3 entry + the BE plugin / executor-registration interface) + `SPEC_EVAL_SCENARIOS.md`.
- **Memory:** `healthcare-realm-as-pack` (the layered plan + the packs-as-code nuance), `conversational-first-core-plugin-line`, `grounding-floor-is-the-moat-next`.
- **The pack:** `packs/healthcare/{pack.json,floors.py}` + `lithrim_bench/harness/pack.py` (`load_pack_floors`) + `lithrim_bench/harness/grounding.py` (the merge accessors `suppress_executors`/`floor_executors`).
