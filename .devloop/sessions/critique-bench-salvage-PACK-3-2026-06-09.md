# Critique — bench-salvage PACK-3 (healthcare-realm-as-pack, layer 3: floors → pack)

**Date:** 2026-06-09 · **Verdict:** PROCEED-WITH-CAVEATS · **Hardness:** HARD GATE (fresh-critic required)
**Build:** `ca54008..f5e6590` (8 atomic pathspec-only, parent `a502059`, NOT pushed — LOCAL is SSOT)
**Close commit:** (this close) · **Session log:** `session-bench-salvage-phasePACK-3-2026-06-09.json`

## What this cut is
The strangler-fig **layer 3** and the **FIRST packs-as-CODE** step (PACK-1/2 moved data — JSON/`.txt`; this moves executor *code*). The clinical grounding executors — `RecordPresence` + `_decode_artifact_soap` (from `harness/grounding.py`) and `InRowTool` + `DosageGroundingTool` + the SOAP/PMH/dose extractors `_core`/`extract_pmh_items`/`extract_plan_dose_tokens`/`_norm_dose`/`_DOSE_RE` (from `verification/tools.py`) — relocated **behavior-identical** into `packs/healthcare/floors.py`, behind a new pack executor-registration interface (`pack.load_pack_floors()` `importlib`-loads the manifest's `floors` module; the engine lazily merges via `grounding.suppress_executors()`/`floor_executors()`/`floor_contract_types()`). The generic engine (`ground()`, `_build_contract`, the registry-refactored `_run_floor`, `PresenceCheck`, `KbGrounding`, the generic toolbox) stays core. THE MOAT (`signals.py:183`, the UAP-3b withstands-gate) reads the pack-merged registry.

## Monitor 7-item mechanical audit — CLEAN
1. **Scope** — 8 commits / 14 files, no foreign swept; `floors.py` +382 (new), `grounding.py` 326-line registry refactor, `pack.py` +42 loader.
2. **A1 boundary (re-scoped, see caveat)** — clinical executor class/def needles ABSENT from `harness/`+`verification/`, PRESENT (5) in `packs/healthcare/floors.py` (relocation ≠ deletion).
3. **Frozen seam 0-delta** — `git diff a502059 HEAD --` empty for `ontology.json`, `taxonomy_snapshot.json`, `compliance_council.py`, `judge_metric.py`, `judges_dspy.py`, seeds.
4. **Import-isolation (A6)** — `grounding.py` module-top imports = `re` + `.ontology` only; the pack merge is lazy (pack→core, no cycle); `import grounding` stays stdlib-only.
5. **Moat touch** — `signals.py:183` `_CONTRACT_EXECUTORS` → `suppress_executors()` (one line + docstring); loader = `importlib…exec_module` (the new trust surface).
6. **ruff** — clean on changed files.
7. **Push-state** — no remote, pathspec-only, parent `a502059`.

## HARD-GATE fresh-critic — agent `a24596f7030bc9a07` — NON-BLOCKING [0 BLOCKING / 2 NB / 1 OQ]
Genuinely-fresh, worktree-isolated; re-derived every claim from git+code, ran BOTH envs, tested non-vacuity by unregistering the pack. "Tried to break it 7 ways and could not."
- **Behavior-identity CONFIRMED** — AST-extracted each moved symbol at HEAD vs parent `a502059` and diffed: all byte-identical EXCEPT `RecordPresence`'s two non-logic deltas (a docstring `:class:` cross-ref shortened + a now-redundant *function-local* import removed — the names resolve identically at module scope; `verification.spec` unchanged). **Zero control-flow/threshold/regex/literal/comparison change.**
- **`_run_floor` registry-dispatch behavior-preserving** — reference-builders lifted verbatim; same tool constructors, same spec/claim/verify tail, the `else: raise` preserved.
- **Lazy merge correct + cycle-free + fail-clean** — core env (no openai/httpx/dspy): `import grounding` pulls none + doesn't load the pack; default `healthcare`: `suppress_executors()` = {presence_check, kb_grounding, **record_presence**}, `floor_executors()` = {structural_jute, jute_gen, **dosage_grounding**}, the clinical ones sourced from the pack module (not core); no-`floors` pack degrades to generic-only (clinical executors absent, no core fallback); bad path → `FileNotFoundError` (fail-clean).
- **Boundary REAL** — needles absent-core/present-pack; helper partition correct (`_norm`/`_dig` stay — used by generic `KbRagTool`/`FakeRecordRagTool`; `_core`/`_norm_dose`/`_DOSE_RE` MOVED with the clinical tools).
- **THE MOAT CONFIRMED + non-vacuous** — false `FABRICATED_HISTORY` → BLOCK→PASS suppressed; true fabrication stays BLOCK; monkeypatching `_pack_registries → ({},{})` makes the `record_presence` signal **vanish** from the withstands-gate and removes suppression (proves the pack executor, not a core fallback, does the work).
- **Frozen seam 0-delta CONFIRMED.** **Green bar both envs, 0-new at parent CONFIRMED** (see reconciliation).

## The recurring caveat — the green-bar baseline (now root-caused, durable)
For the SECOND cycle running, the executor's handback mischaracterized the pre-existing failures (PACK-3 said "562p/2f observation-isolation"; PACK-2 said "554p/2f S-BS-96 observation"). **The 0-new claim holds both times** — but the baseline prose is loose. Root cause, ground-truthed by the monitor this cycle: **`examples/proof_case.jsonl` is gitignored + untracked** (`git check-ignore` confirms) but exists on disk in the canonical checkout. So:
- **Canonical checkout** (executor env): the proof_case-dependent tests PASS → ~2 pre-existing failures.
- **Bare worktree** (every fresh critic): the gitignored fixture is absent → +3 spurious failures (5 total), plus the `S-BS-117` absolute-`cohort_path` corpus test + a byoc env-var test.
- **0-new confirmed in BOTH** — each re-ran parent `a502059` in its own env and got the identical failure SET; the +8 passing delta is exactly the new `test_pack_layer3.py`.

This worktree-vs-canonical gap is a per-cycle cycle-tax. Recorded as **S-BS-119** so future critics judge by *0-new at parent*, not absolute counts.

## A1 re-scope (user-approved at plan-review — the only material deviation)
The driver's literal A1 (`grep dosage → empty` over the engine) is unsatisfiable without forbidden edits: the generic `PresenceCheck` (stays core) reads a FROZEN ontology contract param key `params["dosage_regex"]` (`grounding.py:137`), and the `dosage_grounding`/`record_presence`/`in_row` contract-type NAME constants are interface vocabulary in `spec.py`. Monitor ground-truthed the crux (`dosage_regex` is indeed generic-PresenceCheck). Re-scoped to the PACK-1/2 precedent: precise clinical-CODE needles (`class RecordPresence`/`InRowTool`/`DosageGroundingTool`, `def extract_*`, literals `soap_pmh_items`/`snomed_core`/`dose_token`) absent-in-engine + present-in-pack, with a CLOSED enumerated carve-out for the irreducible residual (the param key + the name constants + scrubbed docstrings). The spirit of A1 — *no clinical executor code in the engine, grep-verifiable* — is fully met.

## Seams
- **S-BS-118** (low) — packs-as-code trust surface: a Pro pack now ships in-process Python (`importlib.exec_module` from the manifest's `floors` ref). The loader fails-clean (missing → `FileNotFoundError`; no-floors → degrade) and doesn't traverse beyond the declared ref, but a manifest declaring `floors: "../../x.py"` would load arbitrary Python (critic OQ1). License/sandbox is Phase-3-deferred, flagged in `SPEC_PLUGIN_ARCHITECTURE`. (Executor labeled this `S-BENCH-SALVAGE-PACK3-1`.)
- **S-BS-119** (low) — gitignored test-required fixtures: `examples/proof_case.jsonl` (read by `test_ground_floor1`/`test_uap3b2_provenance`/`test_uap3b_withstands`/`test_grade_wire`) is gitignored, so bare worktrees/CI/fresh-clones see ~3 spurious failures. Fix = track the fixture, skip-clean on absence, or generate it in a conftest. Relates to S-BS-117 (both = non-portable test artifacts).
- **NB2 (cosmetic, fixed at close)** — `SPEC_PLUGIN_ARCHITECTURE` said the moat change is at `signals.py:182`; the actual membership-check line is `:183`.

## Disposition
The cut is a clean, behavior-identical, grep-verifiable relocation of the clinical floors into the pack behind a sound lazy registration interface; the moat survives and is non-vacuous; the frozen seam is 0-delta; 0-new in both envs. **CLOSED PROCEED-WITH-CAVEATS.** No proof capsule (offline mechanism; A2/A4 proven $0 by byte-behavior identity). Next = PACK-4 (journey literals). Layers 2b + 1b remain deferred behind explicit authorization.
