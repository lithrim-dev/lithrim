# Critique — bench-salvage / PACK-1 (healthcare-realm-as-pack, layer-1a) — 2026-06-09

> **HARD GATE.** Genuinely-fresh critic (agent `a288ace3f4072d77b`, 97.3k tokens / 48 tool-uses / ~13 min), spawned with NO prior context. This relocated the **CLAUDE.md core invariant** (the `taxonomy_snapshot` = "the only coupling point to lithrim-backend") + reconciled a **moat guard** (`tests/_seam_freeze.py`). Monitor 7-item audit (CLEAN) precedes it.

## Verdict: NON-BLOCKING [0 blocking / 2 non-blocking / 0 open-questions]

PASSES the HARD GATE. The realm relocated byte-identically, the boundary is real, the moat guard can't be defeated, and the clinical product is byte-behavior-identical.

## What landed
The clinical `ontology` + `taxonomy_snapshot` `git mv`'d (R100 byte-identical) into `packs/healthcare/{ontology,taxonomy_snapshot}.json`; the core resolves them via `harness/pack.py` `active_pack()` (default `healthcare`, `LITHRIM_BENCH_PACK`-overridable) instead of the two hardcodes; a consistency gate AST-parses the FROZEN council's `KNOWN_TAXONOMY_CODES` (no import — the core env has no openai) and fails closed. Build `dd8b78d..953da37` (5 atomic, pathspec-only, NOT pushed). Decisions (user-locked): **D-B = RELOCATE**; the 8 seeds get a behavior-preserving `ontology_path`-only edit (A5 re-scoped to behavior-frozen); the 5 generator provenance labels stay as historical record.

## Monitor 7-item mechanical audit — CLEAN
| # | Item | Result |
|---|---|---|
| 1 | Renames | both files **R100** (byte-identical content) |
| 2 | FROZEN council 0-delta | compliance_council.py / judges_dspy / judge_metric empty (D-A held) |
| 3 | Per-seed diffs | all 8 = exactly the `ontology_path` line, nothing else |
| 4 | A1 boundary | lithrim_bench/ + data/config/ clean; 5 scripts/ residuals = provenance labels |
| 5 | The 2nd-guard reconcile | sound — freezes content vs `acc4973`, + the new seed-path guard |
| 6 | CLAUDE.md | coupling-point relocated; "invariant moves, doesn't weaken"; rule preserved |
| 7 | `pack.py` | clean resolver + AST gate; non-vacuous; only core `healthcare` = env-overridable `DEFAULT_PACK` |

Monitor re-ran `test_pack_layer1a.py` + the 2 reconciled guards + `test_ground_floor1.py` → 21 passed.

## Fresh-critic adversarial findings (all 10 CONFIRMED)
1. **Byte-identity (HIGH):** SHA256 identical pre/post for both files (`taxonomy_snapshot.json` `45a6e5a6…`, `ontology.json` `bf177aec…`); empty content diffs. The core-invariant content did NOT change.
2. **Moat guard non-defeatable (HIGH):** drove 4 mutations of `packs/healthcare/ontology.json` (owner_roles / severity-weight / gradeable-flip / flag-remove) → all FAIL; `assert_seed_ontology_path_relocated_only` catches a non-path seed edit + a wrong path; the additive carve-out is directional (edit existing contract → FAIL, add new → PASS). Tree restored.
3. **Seed diffs path-only (HIGH):** all 8 exactly `2 +-`, the `ontology_path` line only.
4. **Frozen council 0-delta (HIGH):** `compliance_council.py` SHA256 identical pre/post; whole `runtime/council/` empty.
5. **Gate non-vacuous + import-free (HIGH):** in the no-openai env, `import lithrim_bench.harness.pack` succeeds and does NOT import the council (`sys.modules`-asserted); `council_known_codes()` AST = 19 ground-truth codes; `assert_codes_known` fail-closed on an extra code; on the load path (`ontology.py:42`, `taxonomy.py:17`).
6. **A1 boundary real (HIGH):** grep of lithrim_bench/ + data/config/ empty; only core `healthcare` literal = `pack.py:31 DEFAULT_PACK`; the 5 scripts/ residuals are `generate_*`/`build_*` provenance metadata, never load-read.
7. **A2 byte-behavior-identical (HIGH):** 23 flags / 19 gradeable; the typed `Ontology` is pydantic deep-equal pre/post incl. `severity_map`. No paid run (byte+typed equality sufficient).
8. **48-file footprint path-only (HIGH):** every `+/-` line in the 5 core load sites + 6 larger scripts inspected — path-relocation / import-of-pack / docstring only. No hidden logic.
9. **Full suites green (HIGH):** default 410→**420**; debuglithrim 533→**543**; the only 2 failures are the pre-existing S-BS-96 observation pair (fail at parent too). 0 new. *(A worktree-7-failures first read was reconciled to 2 — 5 were worktree-absolute-path artifacts.)*
10. **Pre-existing staleness (MED):** the 2 observation failures = S-BS-96; `seed_ontology --check` exit-1 = S-BS-113 owner drift — both byte-identical parent vs tip; neither introduced nor fixed.

## Non-blocking
1. **ruff whole-repo 457 errors at BOTH parent and tip** (pre-existing debt); the changed files carry 1 ruff error (`SIM102` in `lint_golden:74`) that is **pre-existing** in untouched code. The touched lines are ruff-clean. Not a regression.
2. **The 5 generator provenance labels now stamp a dangling path** — `generate_*`/`build_fhir_mini_pack` write `"taxonomy_snapshot": "taxonomy/taxonomy_snapshot.json"` (no longer on disk) into newly-generated provenance blocks. Metadata-write, not load-read → this cycle unaffected; matches the locked "labels stay as historical record" decision. **Forward-fix** (when corpora regenerate, stamp the active-pack-resolved path) → **S-BS-116**.

## Disposition
- **S-BS-114** (low) — apps/shell FE fixtures stale `ontology_path` (layer-4).
- **S-BS-115** (low) — docs/ + research script reference the old path (docs sweep).
- **S-BS-116** (low) — the generator provenance labels forward-fix (corpus-regen layer).
- Pre-existing carried: S-BS-96, S-BS-113.
- **OWED:** the PAID before/after eval on `ws0_default` (user-fires; A2 already proven $0).
- **NEXT:** the strangler-fig continues — layer-2 (judges → pack) → 3 (floors) → 4 (journey + S-BS-114) → 5 (dataset); **layer-1b** (un-freeze the council's `KNOWN_TAXONOMY_CODES`) deferred behind explicit authorization.
- Tree clean at `953da37`; no tracked file modified by the critic.
