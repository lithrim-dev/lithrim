# DRIVER — `bench-salvage` — PACK-DIST-1 — extract the healthcare realm to an externally-loaded pack (release-clean the CE core)

> **Bundle:** `bench-salvage-phasePACK-DIST-1-extract-healthcare-to-external-pack`
> **Hardness:** **HARD GATE** (structural / cross-repo: a pack-discovery seam + physically moving the entire clinical realm OUT of the CE repo + a CE-clean proof + the moat/frozen-seam must stay intact). Fresh-critic close.
> **Last re-verified against code:** 2026-06-12 (every citation below re-grepped live on HEAD `672a96e`).
> **Specs:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (§Build-sequencing **Phase-3 = separate distribution**; **OQ-3 RESOLVED: separate distribution — the locked Pro bits are NOT present in the OSS repo**); `docs/specs/SPEC_STANDALONE_CORE_VALIDATION.md` (the CE-clean contract).

---

## KICKOFF (paste into a FRESH executor session in `lithrim-bench`)

You are the **executor** for `bench-salvage` phase **PACK-DIST-1**. This is a fresh session, ONE driver, ONE scope. Read in order:
1. `.devloop/personas/EXECUTOR.md`
2. This driver, top to bottom.
3. `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (§KINDS, §Data-Contracts, §Build-sequencing, OQ-3) + `SPEC_STANDALONE_CORE_VALIDATION.md`.
4. `CLAUDE.md` (the frozen-seam + healthcare-realm-as-pack + CE-PACK invariants).
5. `git log --oneline -6`; `git show acc4973 --stat | head` (the moat baseline).

**WHY this cycle:** the user wants to release the **CE (OSS core)**. You cannot open-source a repo that ships the Pro `healthcare` pack. The relocation arc (PACK-1..2c) made the core domain-agnostic *in one repo*; PACK-DIST-1 makes the clinical realm **physically external** so the CE repo's tracked tree is genuinely clean + releasable, and the core loads `healthcare` from outside (entry point / external dir). HPACK (the SNOMED floor + tools + cases) then gets built **in the external pack repo**, never in CE.

Then **STOP and produce a PLAN-REVIEW** (no code first). Rule forks F1–F6 with diagnose-before-edit evidence (paste the verbatim code/paths you reason over). Wait for the monitor's GO.

**Standing constraints (§0).** LOCAL is SSOT — **do NOT push** (this cycle CREATES a new local sibling repo; that is not a push). Pathspec-scoped commits on the CE side (`git commit -- <files>`, never bare; the branch `bench-salvage/ws6c-dspy` is shared/dirty). Services are user-run — `curl`-check, never autostart. The moat (`_apply_consensus` + signals/withstands) stays **byte-identical vs `acc4973`**. The frozen council carve-outs must keep resolving `healthcare`'s data **via the new discovery** (behavior-identical). Honest-Δ — no manufactured wins.

---

## §0 — Standing constraints

- **LOCAL is SSOT.** Nothing pushed all program. PACK-DIST-1 creates a NEW sibling git repo `../lithrim-pack-healthcare/` (a local `git init`, not a push/publish). The owner-gated push stays the user's call.
- **Pathspec-scoped commits** on the CE repo. Verify scope each commit with `git diff <parent> HEAD --stat`.
- **The recurring count-inflation.** The executor env over-reports the green bar (Azure vars + gitignored fixtures). Judge **0-new vs parent**, not absolute; the bare-worktree count is the truth (the fresh critic re-runs it). After THIS cycle, the suite count CHANGES legitimately (clinical tests relocate/skip) — so the bar is "the CE interface suite is green + the clinical suite is green where it now lives," not a single 0-new number. Document the move precisely.
- **The moat + frozen seam are untouchable.** `_apply_consensus`, `extract_verdict_confidence`, the council carve-outs (`pack_tiers`/`pack_tier1_owners`/`pack_lenses`/`pack_production_judges` reads), `signals.py`/`withstands.py` — this cycle changes pack DISCOVERY (above the seam), never the council's logic. The carve-outs must still resolve `healthcare` (now external) identically.

---

## §1 — Context: what PACK-DIST-1 is

**Distribution, not decoupling.** The decoupling shipped (PACK-1..2c + PLUGIN-1: the core is domain-agnostic, `tier` is load-bearing, packs load by file path). What remains for a CE release is **physical separation**: move the clinical realm out of the CE repo so the public bits contain no Pro content (OQ-3). PLUGIN-1 set this up perfectly — discovery is one chokepoint, packs aren't in the wheel, zero `import packs.*`.

**This cycle = the discovery seam + the extraction.** The pip-package CI/devloop formalization + the clean clinical-test MOVE are **PACK-DIST-2** (deferred). The escape hatch (§3) defines the minimum that still leaves CE release-clean if the full test reshaping can't land green in one session.

---

## §1.5 — Diagnostic map (re-grepped on HEAD `672a96e`, 2026-06-12)

**The discovery chokepoint (the seam — D1):**
- `lithrim_bench/harness/pack.py` — `PACKS_DIR = REPO_ROOT / "packs"` (`:46`); `_manifest(pack)` reads `PACKS_DIR / pack / "pack.json"` (`:78`, the SINGLE resolve point); `_resolve(ref)` (`:75`) resolves a manifest's relative refs against `REPO_ROOT`. **No enumerate-all** (resolve-by-id only). `active_pack()` (`:62`) reads `LITHRIM_BENCH_PACK`. `pyproject.toml` `[tool.setuptools.packages.find] include = ["lithrim_bench*"]` (`:83`) — **`packs/` is already excluded from the wheel**. No `entry-points` yet.

**The clinical footprint to relocate (D2) — what lives in the CE repo beyond `packs/healthcare/`:**
- The pack dir itself: `packs/healthcare/` (ontology, taxonomy_snapshot, council_roles, floors.py, generators/, safety_flags_seed.py).
- **Clinical corpora:** `examples/{scribe_v1*,coding_v1,hl7_adt_v1,scheduling_v1,triage_v1,judge_calib_v1,imported_demo_*,s_bs_74_med_overfire_demo,uap5a_flip_demo,proof_case}.jsonl` (the by-construction generated clinical datasets — they belong with the generators, in the pack).
- **Clinical agent seeds:** the seeds whose `eval_profile.ontology_path == packs/healthcare/ontology.json` (pinned by `tests/_seam_freeze.py::assert_seed_ontology_path_relocated_only`) — enumerate them at plan-review.
- **Fixtures that REUSE healthcare ontology:** `packs/_tiers_fixture/pack.json` + `packs/_plugin_fixture/pack.json` both point `"ontology": "packs/healthcare/ontology.json"` — these must de-couple (a tiny self-contained CE fixture ontology) so the CE tree has NO healthcare path.

**The test surface (D3) — references `packs/healthcare` from `tests/`:**
- Boundary/relocation proofs (clinical-CONTENT): `test_pack_layer{1a,1b,2,2b,2c,3,5a,5b}.py`, `test_ground_floor1.py`, `test_uap3b2_grounding_check.py`, `test_standalone_ce.py`, `test_launch_standalone.py`, `test_ws1.py`, `test_audit.py`.
- Interface/neutral (STAY in CE): `test_neutral_default.py`, `test_plugin_phase1.py`, the seam-freeze guards.
- **Pin sites:** `tests/conftest.py:17` (`setdefault LITHRIM_BENCH_PACK=healthcare`), `lithrim_bench/runtime/council/tests/conftest.py` (the S-BS-134 pin), `test_pack_layer1b.py`, `test_neutral_default.py`.

**The frozen-seam constraint (D4):** the council's inline `__import__` carve-outs (`compliance_council.py` `_PACK_TIERS:195`/`_TIER1_OWNERS:238`/`_ROLE_PROMPTS_DIR:445`/roster`:495`) call `harness.pack.pack_*()` AT IMPORT. After the seam they resolve `healthcare` via discovery — must be **behavior-identical** when `healthcare` is discoverable. `tests/_seam_freeze.py` guards stay green (pack.py isn't frozen; the discovery change is above the seam).

---

## §2 — Deliverables

**D1 — the discovery seam** (`lithrim_bench/harness/pack.py`). `_manifest`/`_resolve` resolve a pack id via a SEARCH, in order: (1) installed **entry points** (`importlib.metadata.entry_points(group="lithrim_bench.packs")` → a registered manifest dir/module), (2) **`LITHRIM_BENCH_PACKS_DIR`** (one or more external dirs, `os.pathsep`-joined), (3) the in-repo `packs/`. A new `_pack_root(pack) -> Path` helper centralizes resolution; `_manifest`/`_resolve`/`PACKS_DIR` consumers route through it. Stdlib-only (no new heavy dep). **Non-breaking:** in-repo packs resolve unchanged (fallback (3)).

**D2 — the external pack repo + relocation.** Create `../lithrim-pack-healthcare/` (`git init`; a minimal `pyproject.toml` declaring `[project.entry-points."lithrim_bench.packs"] healthcare = "..."` + the pack payload). **Relocate** (git-history-preserving where possible): `packs/healthcare/` + the clinical `examples/*.jsonl` corpora + the clinical agent seeds → the pack repo. The CE repo **removes** them. Wire the dev/test env to discover it (`LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare` or `pip install -e ../lithrim-pack-healthcare`).

**D3 — keep the CE suite green with healthcare external.** De-couple the two fixtures from `packs/healthcare/ontology.json` (a tiny self-contained CE fixture ontology under `packs/_*fixture/`). For the clinical-CONTENT tests, take the F3 decision (move-to-pack vs skip-when-pack-absent + dev-install). The CE INTERFACE tests (seam, gate, load/unload, neutral-default, the boundary sweep) run against `_core`/`story_audit`/fixtures with NO healthcare path.

**D4 — the CE-clean proof + moat/frozen-seam parity.** A test (`tests/test_pack_dist.py`): the CE tracked tree has **no `packs/healthcare/`, no clinical corpora, no clinical content** beyond the enumerated interface vocabulary (extend the PACK-3 closed-carve-out sweep over a now-genuinely-clinical-free repo); the seam **discovers `healthcare` from the external location** and the council binds its 19 codes / clinical floors identically (the load/unload proof, now permanent); `_apply_consensus`/`extract_verdict_confidence` byte-identical vs `acc4973`; the 3 frozen-seam guards green.

**D5 — docs.** `SPEC_PLUGIN_ARCHITECTURE.md` (PACK-DIST = the OQ-3/Phase-3 distribution realization; what shipped vs PACK-DIST-2); a **CE-release README** (the clean repo = the OSS core; how to add a Pro pack via entry point / `LITHRIM_BENCH_PACKS_DIR`); the pack repo's README; `CLAUDE.md` (the external-pack topology; the taxonomy-snapshot contract now lives in the external pack).

---

## §3 — Plan-review checkpoint (rule BEFORE editing)

- **F1 — discovery mechanism.** Entry points vs `LITHRIM_BENCH_PACKS_DIR` vs **both**. Lean: BOTH (entry-points = the pip-installable/idiomatic path; the dir env = dev/airgap), in-repo `packs/` as the final fallback. Confirm `importlib.metadata` resolves a pack installed `-e`.
- **F2 — the pack-repo shape.** A real sibling `git init` repo + minimal `pyproject` + entry point NOW (lean — it's genuinely separate + `pip install -e`-able), vs a bare sibling dir loaded only via the env (defer pyproject). The pack's full CI/devloop scaffolding is **PACK-DIST-2** either way.
- **F3 — the clinical-test home (the fork-heavy one).** (a) MOVE the clinical-content tests to the pack repo (cleanest public CE suite) vs (b) keep them in CE but **skip-when-pack-absent** + dev-install `healthcare` in CI. Lean for PACK-DIST-1: **(b) skip-when-absent + dev-install** (smallest, keeps the suite runnable both ways); the clean MOVE (a) is PACK-DIST-2. Decide per-file; the relocation-PROOF tests (`test_pack_layer*`) may stay in CE (they assert "clinical is in the pack" — still true, now external).
- **F4 — the exhaustive clinical-content manifest.** Produce the what-moves / what-stays list (pack dir, corpora, seeds, the two fixtures, per-test). This IS the plan's core artifact — the monitor signs off on it before any `git rm`.
- **F5 — CE-clean definition + release procedure.** What "clean" asserts (the D4 sweep) + how the public release is produced (the clean tracked tree IS the release — no filter pipeline). Confirm the boundary sweep is non-vacuous over the post-extraction tree.
- **F6 — git-history strategy.** `git mv` within CE won't move across repos; relocating to a sibling repo loses CE git-history-linkage for those files unless you `git filter-repo`/subtree-split. Lean for -1: a plain move + a fresh add in the pack repo (history starts in the pack repo; CE history retains them up to the removal commit) — call it out; a history-preserving subtree split is a PACK-DIST-2 nicety.

**Escape hatch (the minimum that still leaves CE release-clean):** D1 (seam) + D2 (relocate the pack + corpora to the sibling repo so the **CE tracked tree is clean**) + F3-(b) skip-when-absent + D4 (the CE-clean proof). Defer the clean test-MOVE, the pyproject/entry-point install polish, and the fixture-decouple niceties to **PACK-DIST-2** if they threaten green-at-each-step. **Do NOT force a red intermediate, and do NOT `git rm` healthcare until the seam + external discovery is proven loading it.**

---

## §4 — NOT in scope

- **HPACK** — the SNOMED terminology floor, vector/KB querying, the SNOMED MCP tool, the clinical cases. These are built **in the external pack repo AFTER PACK-DIST**. (HPACK also has its own CE/Pro split — the generic `tool`-kind interface + generic KB-grounding mechanism are a SEPARATE CE cycle; only the SNOMED content is pack.)
- **PACK-DIST-2** — the pack-repo CI/devloop, the history-preserving subtree split, the clean clinical-test MOVE (if F3 chose skip-when-absent), the published private-index packaging.
- **Phase-3 proper** — the registry/fetch/spawn/marketplace + license **enforcement** (permit-all default stays).
- Editing the frozen council logic, the moat, or the consensus/withstands mechanism.
- The owner-gated push.

---

## §5 — Acceptance (gates)

- **A1 — the seam works.** `healthcare` loads from an EXTERNAL location (entry point and/or `LITHRIM_BENCH_PACKS_DIR`) with the CE repo's `packs/healthcare/` absent; in-repo packs (`_core`, fixtures) still resolve (non-breaking).
- **A2 — the CE tree is clean.** No `packs/healthcare/`, no clinical corpora, no clinical content beyond the enumerated interface vocabulary (the D4 sweep, non-vacuous over the post-extraction tree). The two fixtures no longer reference a healthcare path.
- **A3 — behavior-identical under the active healthcare pack.** With `healthcare` discoverable, the council binds the SAME 19 codes / 8 owners / clinical floors (`record_presence`, `dosage_grounding`) / roster as before; the consensus oracle is green; the by-construction corpus (regenerated from the pack) is byte-identical.
- **A4 — fail-closed when the pack is genuinely absent.** `LITHRIM_BENCH_PACK=healthcare` with no discovery hit → fail-closed (the existing `FileNotFoundError`/`PackLicenseError` posture), not a silent fallback.
- **A5 — moat + frozen seams green.** `_apply_consensus`/`extract_verdict_confidence` byte-identical vs `acc4973`; `assert_compliance_council_carveouts_only`, `assert_judges_dspy_consensus_seam_frozen`, `assert_clinical_ontology_seam_frozen` green (the clinical-ontology guard reads the pack's ontology — now external; confirm it resolves via the seam or relocate the guard's baseline).
- **A6 — both suites green.** The CE interface suite is green standalone; the clinical suite is green where it now lives (pack repo, or skip-when-absent + dev-install). ruff 0-new on touched CE files. Document the precise test-count delta + where each moved.
- **A7 — release procedure documented.** The CE-release README states what the clean repo is + how a Pro pack plugs in.

---

## §6 — Commit structure (CE side; the pack repo is its own history)

1. `feat(pack): external pack discovery — entry points + LITHRIM_BENCH_PACKS_DIR (D1)`
2. `refactor(fixtures): decouple the test fixtures from the healthcare ontology (D3)`
3. `chore(pack): relocate healthcare + clinical corpora/seeds out of the CE repo (D2)`  ← the `git rm`; only AFTER D1 proves external load
4. `test(pack): skip-when-absent guards for clinical tests; CE interface suite standalone (D3)`
5. `test(pack-dist): the CE-clean proof + external-load + moat parity (D4)`
6. `docs(pack-dist): the external-pack topology + the CE-release README (D5)`

(Reorder per the plan; each commit green + pathspec-scoped. The pack repo gets its own initial commit.)

---

## §7 — Verification checklist (handback must show)

1. `git diff <parent> HEAD --stat` (CE) — scope = D1–D6; no foreign files. `git -C ../lithrim-pack-healthcare log --oneline` — the pack repo's commits.
2. A1–A7 each PASS, with the external-load (A1) + CE-clean sweep (A2) + fail-closed (A4) pasted.
3. `_apply_consensus`/`extract_verdict_confidence` sha vs `acc4973`; the 3 frozen guards green.
4. The CE interface suite green standalone (no healthcare on disk/path); the clinical suite green where it lives. The test-count delta, explained.
5. ruff 0-new on touched CE files. Which forks (F1–F6) were taken; whether the escape hatch fired.

---

## §8 — First move + HARD GATE

**First move:** STOP. Produce the PLAN-REVIEW — the F4 what-moves/what-stays manifest is the centerpiece; rule F1–F6 with evidence. **Do NOT `git rm` anything until the seam (D1) proves external discovery loads `healthcare`.** Wait for the monitor's GO.

**HARD GATE (close):** a fresh-critic worktree pass must independently reproduce A1 (external load), A2 (CE-clean sweep, non-vacuous), A3 (behavior-identical council), A4 (fail-closed), A5 (moat byte-identity + guards). The structural blast radius + the irreversibility-feel of the `git rm` make this non-negotiable.

**HALT conditions:** the council can't resolve `healthcare` via the seam (behavior drift); a frozen guard goes red with no authorized reason; the moat isn't byte-identical; the green bar forces a red intermediate (→ take the §3 escape hatch). When in doubt about what's "clinical," over-relocate to the pack (the CE repo must err clean).

---

## §9 — References
- `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (OQ-3 separate distribution; Phase-3) · `SPEC_STANDALONE_CORE_VALIDATION.md` (the CE-clean contract).
- Code anchors: `harness/pack.py:46,62,75,78` (discovery chokepoint) · `pyproject.toml:83` (wheel scope) · `compliance_council.py:195,238,445,495` (the carve-out reads) · `tests/_seam_freeze.py` (the guards + the seed-path pin) · `tests/conftest.py:17` + `runtime/council/tests/conftest.py` (the pins) · `tests/test_pack_layer3.py` (the closed-carve-out sweep to extend) · `examples/*.jsonl` (the clinical corpora).
- Memory: `conversational-first-core-plugin-line` (the OSS-core/Pro line) · `healthcare-realm-as-pack` (the relocation arc this finishes) · `gtm-launch-and-journey-thesis` (open-core + no-us-hosted; separate distribution).
- Prior: `HANDOFF_bench-salvage_plugin-phase1-DONE_2026-06-12.md` (PLUGIN-1 — the interface this ships on).
