# Spec-Adherence Critique — `bench-salvage` phase PLUGIN-1

> Fresh-critic mode (HARD GATE). Worktree-isolated, adversarial-by-reproduction. The full Plugin Phase-1 registry-unification.

## Metadata

- **Stream:** bench-salvage
- **Phase:** PLUGIN-1 — the full Plugin Phase-1 registry-unification (manifest schema + load-time tier gate + fold contract/provider/pack onto one manifest + provenance recording + a frozen-seam parity proof)
- **Driver bundle:** `bench-salvage-phasePLUGIN-1-plugin-registry-unification-tier-gate`
- **Commits audited:** `6234164..8187b33` (8 cycle commits `ef2e61c`(D1)..`8187b33`(log) atop parent `6234164`); moat baseline `acc4973`
- **Specs read against:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (§1 KINDS, §2 transports, §4 tiering, §Data-Contracts, §Requirements P0, §Test Plan, §Success Metrics); the driver §3 forks + §5 acceptance; `tests/_seam_freeze.py`
- **Critique mode:** `fresh-critic` (separate worktree-isolated opus session)
- **Date:** 2026-06-12
- **Reviewer:** critic session `a164f36488ee9faa0` (opus, `isolation: worktree`)

---

## Verdict

**NON-BLOCKING FINDINGS — [0 BLOCKING / 2 NON-BLOCKING / 0 OPEN-QUESTION] → PASS, CLEAR TO CLOSE**

Every load-bearing claim independently reproduced by reproduction (not handback-trust), several by scratch-mutation. The cycle is a genuine **pure refactor**: grading is byte-identical by default, the `tier` gate is non-vacuously real, the moat is untouched, open/closed is honored, zero foreign files. The escape hatch was not needed — full D1–D7 shipped. The 2 NB are pre-existing/cosmetic.

---

## 1. Surface fidelity — the forks landed as ruled

| Fork (monitor ruling) | Implementation | Match? |
|---|---|---|
| F1 — separate `plugins.py`; validate the 6 JSONs as-is; wrap code registries as `PluginManifest` | `harness/plugins.py` (+210); `extra=forbid` + `kind`/`tier` Literals; all 7 live `pack.json` validate | exact |
| F2 — `License.permits`, permit-all default, gate via `assert_pack_licensed` mirroring `assert_pack_council_consistent`; only `pro` gated | gate at the 3 `*_path` resolvers; permit-all default | exact |
| F3 — body-only `build_judge_lm`; no new top-level symbol; `_ROLE_DEPLOYMENT` read-through | `resolve_provider_id` is a LOCAL import inside `build_judge_lm`; judges_dspy top-level symbol set IDENTICAL vs `acc4973` (added=[], removed=[]) | exact |
| F4 — declaration-only; no re-route of `_build_contract`/`_run_floor`/`suppress_executors()` | D3 adds `contract_plugins()` enumerator only; dispatch byte-unchanged | exact |
| F5 — default-safe provenance fields; populate at `orchestrator.py:336` | `loaded_plugins`/`active_pack`/`pack_tier` additive; raw-dict replay/live path default-safe | exact |
| **R-GUARD** — gate ABSENT from the 4 council carve-out accessors | AST-verified: `assert_pack_licensed` at exactly `pack_ontology_path`/`pack_taxonomy_path`/`pack_prompts_path`, NONE of `pack_tiers`/`pack_tier1_owners`/`pack_lenses`/`pack_production_judges` | exact |

No surface drift. Foreign/demo files (`apps/shell`, `journeys/*`) untouched.

---

## 2. Behavioral fidelity — reproduced

### A1 — parity (byte-identical by default): PASS
`set(suppress_executors())` and `set(floor_executors())` under `LITHRIM_BENCH_PACK=healthcare` are **value-equal at HEAD and parent** (suppress=`{kb_grounding, presence_check, record_presence}`, floor=`{dosage_grounding, jute_gen, structural_jute}`) and match the test's explicit `_EXPECTED_*` snapshot (exact kind/tier/transport/implements tuples). Non-vacuous (scratch-mutating the fixture tier flipped the A4 tier assert). `test_consensus.py` = 20 passed under the healthcare pin (HEAD and parent); `test_plugin_phase1.py` = 17 passed. **Chain closes? YES.**

### A2 — the tier gate is non-vacuous: PASS
Subprocess, real env: `_plugin_fixture` (pro) + `healthcare` (pro) under `LITHRIM_BENCH_LICENSE=deny-all` → `PackLicenseError` (absent, not stubbed); `_core` loads under the same deny; pro loads under permit-all. Confirmed the error is the **license** error, not a masked consistency-gate error. **Scratch-mutation:** neutering `License.permits` (deny→`return True`) flipped exactly `test_a2_pro_pack_under_deny_is_absent` + `test_a2_gate_keyed_to_pro_only` + `test_a2_license_grammar` to FAIL while `test_a2_core_pack_under_deny_still_loads` stayed green. Reverted clean. **The gate is real. Chain closes? YES.**

### A4 — open/closed: PASS
`git show 3c4883d --stat` touches only `packs/_plugin_fixture/{floors.py,pack.json,taxonomy_snapshot.json}` + `tests/test_plugin_phase1.py` — **zero** `grounding.py`/`runtime/council/*` edits; the fixture's `fixture_suppress` registers through `suppress_executors()`/`contract_plugins()` via the manifest `floors` path alone. **Chain closes? YES.**

### A5 — frozen seams + moat: PASS
Independent AST sha: `_apply_consensus` = `d1b7956e70a8` (acc4973 == HEAD), `extract_verdict_confidence` = `ed867bce8be3` (acc4973 == HEAD) — byte-identical, matching the driver's expected shas. The 3 seam guards green (`test_pack_layer1b/2b/2c` + `test_6bclean_seam_guard` + `test_a5_frozen_seam_guards_green`). `judges_dspy.py` top-level symbol set identical (D4 fold is body-only). `signals.py`/`withstands.py` **0-diff vs parent `6234164`** and **ABSENT at acc4973** → the D-2 honest pin (vs-parent, NOT vs-acc4973) is correct, not an overclaim. **Chain closes? YES.**

### A6 — clean bar: PASS
Full `debuglithrim` suite, bare worktree: **HEAD = 661 passed / 4 failed / 3 skipped; parent = 644 passed / 4 failed / 3 skipped → 0-new** (+17 = the new test file). The 4 fails are the pre-declared env artifacts (`test_byoc_provider` Azure; `test_uap3_grade` missing gitignored `out/scribe_v1.jsonl`; 2× S-BS-96 observation-pollution). ruff 0-new on all touched files. *(The executor handback's "2 fails" was env-masked — the bare-worktree truth is 4, all pre-existing; the recurring §0 inflation.)*

---

## 3. Out-of-scope intrusion

`git diff 6234164 8187b33 --stat` = 13 entries; every code file maps to D1–D7. The 4 frozen council files (`compliance_council.py`/`signals.py`/`withstands.py`/`judge_metric.py`) have empty diffs vs parent. No `apps/shell`, no `journeys/*`, no foreign files. Every commit pathspec-scoped.

---

## 4. Spec ambiguity / deviations surfaced (the two plan-review CITATION-DRIFTs — verified honest)

- **D-1 (tier values):** the schema admits `{core, pro, fixture, demo}` (the spec said `{core, pro}`); only `pro` is gated. Verified — the 4 values are live in the 7 manifests; narrowing would break parity (A6). Honest, monitor-approved at plan-review.
- **D-2 (moat framing):** A5's signals/withstands leg is framed "0-diff vs parent" + `_apply_consensus` sha-vs-`acc4973`, because both files post-date `acc4973`. Critic confirmed both ABSENT at acc4973 → the executor's framing is the honest one, not an overclaim. The session log pre-discloses both drifts and notes the monitor caught + fixed an *earlier* vacuous empty-string `_apply_consensus` sha before ship.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity / honesty | 0 | 2 | 0 |

**Total BLOCKING: 0** → cycle MAY close.

### NON-BLOCKING dispositions
1. **Bare-path `test_consensus` collection artifact.** `tests/runtime/council/tests/*` fail 12/20 when invoked **by bare path** because `tests/conftest.py`'s `LITHRIM_BENCH_PACK=healthcare` pin isn't an ancestor of `lithrim_bench/runtime/council/tests/`. **Reproduces identically at parent** → pre-existing collection ergonomics, NOT a PLUGIN-1 regression; 20/20 green under the healthcare pin / full-suite collection. A future cleanup could add a council-tests conftest pin. No action this gate. *(Recorded as a low STREAM observation.)*
2. **S-BS-133 (transport mis-tag).** A future pack shipping a service-transport floor would be declared `transport=in_process` (`_SERVICE_CONTRACT_TYPES` is a fixed core set; pack executors default in_process). Declarative metadata only — dispatch never reads it → **zero grading impact**. Fix when a pack first ships a service-transport floor (Phase-2/HPACK). *(The executor's session log filed this as "S-BS-132", which collides with the open 6c source_message-retire seam — renumbered S-BS-133 in the STREAM.)*

---

## Critic discipline self-check (fresh-critic mode)
- [x] Verified the diff via `git show`/`git diff` against commits, not the handback
- [x] Re-ran the full suite + ruff independently in an isolated worktree; ground-truthed the count vs parent (4f both → 0-new)
- [x] Reproduced gate non-vacuity by scratch-mutation (neutered `License.permits`; flipped exactly the expected tests; reverted)
- [x] Independently AST-extracted + sha-compared the moat pins vs `acc4973`
- [x] Did NOT edit the user's tree (worktree-isolated; all mutations reverted)
- [x] Did NOT confer before writing the verdict

## Appendix: commits audited
```
8187b33 chore(devloop): session log — PLUGIN-1 (7 commits, CLEAN, HARD GATE pending fresh-critic)
1915057 docs(plugins): Phase-1 CODE cycle DONE; frontend kind still deferred (D7)
3c4883d test(plugins): parity + gate non-vacuity + open/closed + frozen-seam (D6)
7e9ac26 feat(provenance): record the loaded-plugin set on PipelineProvenance (D5)
b6c2db3 refactor(council): route the judge provider selection through the plugin registry (D4)
c22540a refactor(grounding): declare the contract registry as kind:contract plugins (D3)
f1fe448 feat(plugins): the load-time tier gate — permit-all default, pro-under-deny absent (D2)
ef2e61c feat(plugins): the plugin/pack manifest schema + License gate model (D1)
```

## Appendix: suite observed
`HEAD 8187b33 = 661 passed / 4 failed / 3 skipped`; `parent 6234164 = 644 passed / 4 failed / 3 skipped` → **0-new** (the +17 are the new `test_plugin_phase1.py`). Same 4 pre-existing env-artifact failures both refs.
