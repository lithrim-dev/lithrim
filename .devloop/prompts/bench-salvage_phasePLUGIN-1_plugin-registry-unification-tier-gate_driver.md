# DRIVER — `bench-salvage` — PLUGIN-1 — the full Plugin Phase-1 registry-unification

> **Bundle:** `bench-salvage-phasePLUGIN-1-plugin-registry-unification-tier-gate`
> **Hardness:** **HARD GATE** (new architecture surface — a unified plugin manifest/registry + the load-time `tier` gate + the provider-seam fold + a frozen-seam *parity* proof). Fresh-critic close.
> **Last re-verified against code:** 2026-06-12 (every citation below re-grepped live on HEAD `c372ec1`).
> **Spec:** `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (LOCKED 2026-06-11; §1 KINDS, §2 transports, §4 tiering, §Data Contracts manifests, §Requirements P0, §Test Plan, §Build-sequencing Phase-1). OQ-1..3 RESOLVED.

> **⚠️ Post-close citation-drift reconciliation (PLUGIN-1 CLOSED 2026-06-12, NON-BLOCKING).** Two claims in this driver were corrected at plan-review + verified at close — read the body with these in mind:
> - **D-1 (tier set):** the live manifests use **`{core, pro, fixture, demo}`**, not just `{core, pro}` (D1 below). The schema must admit all four; **only `pro` is license-gated** (`core`/`fixture`/`demo` always load).
> - **D-2 (moat pin):** the verifiable moat pin vs `acc4973` is **`_apply_consensus` + `extract_verdict_confidence`** (byte-identical — `d1b7956e`/`ed867bce`). **`signals.py`/`withstands.py` POST-DATE `acc4973`** (they landed `8cb388b`/`d9a5bb0`), so the §0/§5/§7 phrase "byte-identical vs acc4973" is ill-defined for them — the honest check is **0-diff vs parent** (both untouched this cycle). See `critique-bench-salvage-PLUGIN-1-2026-06-12.md`.

---

## KICKOFF (paste into a fresh executor session in `lithrim-bench`)

You are the **executor** for `bench-salvage` phase **PLUGIN-1**. Read, in order:
1. `.devloop/personas/EXECUTOR.md`
2. This driver, top to bottom.
3. `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the whole thing — it is short and load-bearing).
4. `CLAUDE.md` (the "Taxonomy snapshot is the contract" + the CE-PACK / healthcare-realm-as-pack notes — they define what is frozen).
5. `git log --oneline -8` and `git show acc4973 --stat | head` (the moat baseline).

Then **STOP and produce a PLAN-REVIEW** (do not edit code first). The plan must rule the forks in §3 with `diagnose-before-edit` evidence (paste the verbatim code you are reasoning over in fenced blocks). Wait for the monitor's GO before touching code.

**Standing constraints (non-negotiable — §0).** LOCAL is SSOT (do **not** push). Pathspec-scoped commits only (`git commit -- <your files>`, never bare). Services are **user-run** — `curl`-check, never autostart. The moat (`_apply_consensus` + the withstands/signals mechanism) stays **byte-identical vs `acc4973`**. Honest-Δ — no manufactured wins. This is a **pure refactor: no grading-behavior change** — the whole cycle's worth is that grading is *byte-identical by default* and the new boundary is *non-vacuously enforced*.

---

## §0 — Standing constraints (the program's rails)

- **LOCAL is SSOT.** Nothing has been pushed across the entire generic-CE program; PLUGIN-1 keeps that. The owner-gated push is the user's call, not this cycle's.
- **Pathspec-scoped commits.** Concurrent `.devloop` sessions leave foreign files in the index — always `git commit -- <explicit paths>`; verify scope with `git diff <parent> HEAD --stat`.
- **Services are user-run.** `:8002` council / `:3031` JUTE / `:8787` BFF — `curl` to check, never start. The suite that matters runs offline in `debuglithrim`.
- **The recurring count-inflation.** The executor env carries Azure vars + the gitignored `out/scribe_v1.jsonl`, so the handback over-reports the green bar (642→639, 647→644 the last two cycles). **Judge 0-new vs parent, not absolute counts.** The S-BS-96 observation pair fails only under full-suite module pollution (passes in isolation). The bare-worktree count is the truth — the fresh critic will re-run it.
- **The moat is frozen.** `_apply_consensus`, `extract_verdict_confidence`, `signals.py`, `withstands.py` — byte-identical vs `acc4973`. This cycle has **no authorized reason to touch them**.

---

## §1 — Context: what PLUGIN-1 is

`SPEC_PLUGIN_ARCHITECTURE` Phase-1 = **formalize the existing ad-hoc registries into one plugin manifest + registry, tag `core|pro`, gate at load, record the loaded set in provenance** — *pure refactor, no new features* (§Build-sequencing). The **content-relocation half already shipped** (PACK-1..2c + the generic-CE demarcation program: the core council is domain-agnostic, the clinical realm is the `healthcare` pack). 

**The user chose the FULL Phase-1 unification in one cycle** (2026-06-12) — not the minimal tier-gate cut. So PLUGIN-1 folds **all three** existing registries onto one manifest:

| Registry | Today | Phase-1 |
|---|---|---|
| `pack` loaders (`harness/pack.py`) | manifest-driven already (`pack.json`); `tier` present but **INERT** | the unified schema + **load-time `tier` gate** |
| `contract` (`harness/grounding.py` `_CONTRACT_EXECUTORS` + the pack-floors merge) | half-folded (pack contributes via `load_pack_floors`); no `kind`/`tier`/`transport` declaration | declared as `contract`-kind plugins (transport from `_HTTP_CONTRACT_TYPES`) |
| `provider` (`judges_dspy.py` `build_judge_lm`/`_ROLE_DEPLOYMENT`) | not manifest-driven; deployment in core (PACK-2c) | declared as `provider`-kind plugins; **binding stays core** |

Plus: **provenance recording** of the loaded set, and a **frozen-seam parity proof** that grading is byte-identical by default.

**Explicitly DEFERRED by the SPEC** (do not build): the `frontend` kind (→ post-CHATBIND-2; needs the runtime trigger channel), HPACK terminology/expressions contracts (Phase 2), the registry/fetch/spawn + license **enforcement** + VPC (Phase 3 — Phase-1 defaults `license=permit-all`).

---

## §1.5 — Diagnostic map (re-grepped on HEAD `c372ec1`, 2026-06-12)

**The pack registry (already manifest-driven — extend, don't rebuild):**
- `lithrim_bench/harness/pack.py` — `active_pack():62`, `_manifest():67` (the `@lru_cache` manifest reader — the **natural gate slot**), `_resolve():75`; the resolvers `pack_ontology_path/pack_taxonomy_path/pack_prompts_path/load_pack_floors/load_pack_generators/pack_tiers/pack_tier1_owners/pack_lenses/pack_production_judges`.
- `packs/{healthcare,_core,support_ticket_qa,story_audit,_tiers_fixture,_nondeployable_fixture}/pack.json` — **every manifest already carries `tier`** (`healthcare:pro`, `_core:core`, `support_ticket_qa:core`, fixtures `fixture`/`demo`). **Inert:** `grep '\["tier"\]' lithrim_bench/ apps/` finds only the unrelated *flag*-tier (`ontology.py:150`, `app.py:1271`) — **nobody reads the pack `tier`**.
- **No gate exists:** `grep 'load_plugins|permits|requires_license'` → empty.

**The contract registry (`harness/grounding.py`):**
- `_CONTRACT_EXECUTORS:297` (`presence_check`, `kb_grounding`) + `_HTTP_CONTRACT_TYPES:301` (`{kb_grounding}` — the **transport hint**) + `_core_floor_executors():318` (`structural_jute`, `jute_gen`) + `_pack_registries():358` (the pack's `SUPPRESS_EXECUTORS`/`FLOOR_EXECUTORS` via `load_pack_floors`).
- Accessors that already MERGE core∪pack: `suppress_executors():379` (the **withstands-gate reads this**, `signals.py:183`), `floor_executors():388`, `floor_contract_types():395`. Dispatch: `_build_contract():400`, `_run_floor():421`, `ground():469`.
- **Note:** the pack-floors half of the fold is *done* — the cycle adds the `kind/tier/transport` **declaration layer**, behavior-identical.

**The provider (`runtime/council/judges_dspy.py`):**
- `_ROLE_DEPLOYMENT:65` (the core Azure-deployment table — `risk/policy/faithfulness → AZURE_*`); `build_judge_lm():205` (reads `_ROLE_DEPLOYMENT.get(role,…):236`); the trio binds it at `:389`.
- **Seam status (load-bearing):** `tests/_seam_freeze.py:85` `assert_judges_dspy_consensus_seam_frozen` — *"everything except the BYOC-1 provider binder `build_judge_lm`/`build_trio` and the CE-PACK-6b-CLEAN `_build_signature` is byte-identical to `acc4973`"* (`_BYOC1_PROVIDER_SEAM = {build_judge_lm, build_trio}`). So **`build_judge_lm`/`build_trio` bodies are editable; the module-level `_ROLE_DEPLOYMENT` dict is FROZEN** → read it through, do not edit it. PACK-2c already ruled **deployment ∉ a domain pack** (infra stays core).

**Provenance:**
- `lithrim_bench/runtime/pipeline/models.py:176` `class PipelineProvenance(BaseModel)` (field `pipeline_run_id:179`); constructed at `runtime/pipeline/orchestrator.py:336`. `runtime/pipeline/provenance.py:62` `SqliteProvenanceStore.save` dumps `provenance.model_dump(mode="json")` → the `pipeline_runs` doc-shim. **An additive field auto-persists** — no store change.

**Frozen-seam guards that must stay green** (`tests/_seam_freeze.py`): `assert_judges_dspy_consensus_seam_frozen:85`, `assert_compliance_council_carveouts_only:226` (the 4 council carve-outs — markers at `:184-194`), `assert_clinical_ontology_seam_frozen:127`. The 8 `tests/test_pack_layer*.py` are the **parity-proof precedent** (subprocess-with-fixture-pack non-vacuity).

---

## §2 — Deliverables

> One commit per deliverable group. Pathspec-scoped. Green at each step.

**D1 — The plugin/pack manifest schema (net-new).** A typed manifest model + validator (`kind ∈ {contract, provider, importer, tool, frontend, pack}`, `tier ∈ {core, pro}`, `transport ∈ {in_process, service}`, `implements`, optional `contract_types`/`service`/`requires_license`) per `SPEC §Data Contracts:65-94`. Suggested home: a new `lithrim_bench/harness/plugins.py` (the registry module) — keep it stdlib/pydantic-core only (no `openai`/`dspy`), so the dependency-light core importers (`signals`/`withstands`/`judge_metric`) are unaffected. The **pack manifest** is validated through it (it already has `tier`); decide F1 (typed entries vs a `plugins:[]` block).

**D2 — The unified registry + the load-time `tier` gate.** Make `tier` **load-bearing**: a `tier: pro` plugin/pack registers **iff** `license.permits(id)`, else it is **ABSENT** (not stubbed) — fail-closed, mirroring the S-BS-90 deny-hook. **Phase-1 default = `permit-all`** (so default behavior is byte-identical). Slot the gate into the pack-resolution path (`pack.py:_manifest`/`active_pack`) and/or a `load_plugins(license)` entry point (F2). `_core`/`core` always loads.

**D3 — Fold the contract registry** (`grounding.py`). Formalize `_CONTRACT_EXECUTORS` + `_core_floor_executors` + the pack-floors merge as `contract`-kind plugin declarations (transport from `_HTTP_CONTRACT_TYPES`; tier from the owning manifest). The accessors (`suppress_executors`/`floor_executors`) keep merging core∪pack **byte-identically** — the withstands-gate read (`signals.py:183`) is unchanged. F4 = declaration-only vs re-route dispatch.

**D4 — Fold the provider** (`judges_dspy.py`). Declare Azure (+ BYO-Claude, already swappable via BYOC-1) as `provider`-kind plugins. **`build_judge_lm`/`build_trio` (seam-exempt) consult the provider registry; `_ROLE_DEPLOYMENT` stays byte-frozen** as the core deployment table (read-through). The deployment binding stays **core** (PACK-2c). The `judges_dspy` seam guard must stay green (F3).

**D5 — Provenance recording.** Add a `loaded_plugins` (and/or `active_pack` + `tier`) field to `PipelineProvenance` (`models.py:176`); populate at `orchestrator.py:336` (or where the pack/council is resolved). It auto-persists via `model_dump` → `pipeline_runs`. Additive; default-None-safe for replay/no-op stores. F5 = the field shape.

**D6 — Parity tests + gate non-vacuity + the open/closed test** (`tests/test_plugin_phase1.py`, mirroring `test_pack_layer*`):
- **(a) parity:** grading is byte-identical under the permit-all default — the consensus oracle (`runtime/council/tests/test_consensus.py`) stays green; a graded fixture case is identical pre/post (or assert the merged registries are value-equal to the pre-refactor dicts).
- **(b) gate non-vacuity:** a `tier: pro` pack/plugin under `license=deny` is **ABSENT** (subprocess-with-fixture, the `_tiers_fixture` pattern); `core` always loads; permit-all is the default.
- **(c) provenance:** a graded run's `pipeline_runs` row carries the loaded set + tier.
- **(d) open/closed:** a NEW fixture `contract` plugin (and/or pack) is added + tier-tagged **via manifest only**, with **zero engine edits**, and the engine picks it up (`SPEC §Success Metrics`).
- **(e) frozen-seam:** all three guards green; the moat byte-identical vs `acc4973`.

**D7 — Docs.** `SPEC_PLUGIN_ARCHITECTURE.md` (mark the Phase-1 CODE cycle DONE; note `frontend` still deferred). `CLAUDE.md` (a one-paragraph plugin-registry note — the manifest is the single Core/Pro boundary field, read at load). The STREAM/index/handoff are the **monitor's** close-out, not the executor's.

---

## §3 — Plan-review checkpoint (rule these BEFORE editing)

Produce a plan that resolves each fork with `diagnose-before-edit` evidence:

- **F1 — manifest shape.** Extend `pack.json`'s existing typed fields (`floors`/`generators`/`judges` → typed plugin entries) **vs** add a separate `plugins: []` array (the `SPEC §Data Contracts:84-89` shape). Lean: the smallest change that carries `kind/tier/transport` without breaking the 6 existing manifests.
- **F2 — the gate's `license` object + slot point.** The `license.permits(id)` interface + where `permit-all` defaults (env? a default object?) + whether the gate lives in `pack._manifest` (every resolve) vs a one-shot `load_plugins(license)` at council/grade construction. Must be **fail-closed** and **byte-identical under permit-all**.
- **F3 — the `_ROLE_DEPLOYMENT` freeze.** Confirm the provider fold edits only `build_judge_lm`/`build_trio` bodies (exempt) and reads `_ROLE_DEPLOYMENT` unchanged (frozen). If a new top-level provider symbol is unavoidable, that is an **insert** the `judges_dspy` seam may forbid — show the guard stays green (paste the predicate's logic). **Deployment stays core** (no domain-pack provider binding — PACK-2c).
- **F4 — contract-fold depth.** Declaration-only (formalize + tier-tag the existing merge, behavior-identical — lower risk) **vs** re-route `_build_contract`/`_run_floor` dispatch through manifest entries. Lean: declaration-only this cycle (the merge already works; re-routing risks the moat-visible `suppress_executors()` read).
- **F5 — provenance field.** A rich `loaded_plugins: [{id,kind,tier,transport}]` **vs** a thin `{active_pack, tier}`. Either must be default-safe for replay/no-op stores (no crash when unset).

**Escape hatch:** if the full unification cannot land green in one cycle, the monitor-authorized fallback is to ship **D1+D2+D5+D6** (schema + gate + provenance + parity — the boundary made real) and split **D3/D4** (the contract/provider fold) into **PLUGIN-2** to land *with* HPACK (the SPEC's "minimal Phase-1 unblocks HPACK"). Flag this at plan-review if the green-at-each-step bar is at risk — do **not** force a red intermediate.

---

## §4 — NOT in scope (scope guardrails)

- The **`frontend`/`component` plugin kind** — deferred to post-CHATBIND-2 (`SPEC §1`, `OQ-NEW`). Do not touch `apps/shell` gen-UI.
- **HPACK** terminology + the expressions evaluator (Phase 2). No new grounding contracts.
- The **registry + fetch/spawn**, license **enforcement**, VPC packaging, marketplace (Phase 3). Phase-1 is `permit-all`.
- **Any grading-behavior change.** The consensus seam, `_apply_consensus`, the withstands-gate, the ontology — untouched. Grading is byte-identical by default.
- **Moving `_ROLE_DEPLOYMENT` into a domain pack** — PACK-2c: infra stays core.
- Editing the frozen council carve-outs, the `judges_dspy` consensus seam, or the clinical-ontology seam beyond the authorized provider-binder exemption.
- The **owner-gated push** (LOCAL SSOT).

---

## §5 — Acceptance (gates — all must pass to close)

- **A1 — parity (byte-identical by default).** With `license=permit-all` (the default), grading is unchanged: the consensus oracle is green; the merged `suppress_executors()`/`floor_executors()` are value-equal to the pre-refactor registries for `healthcare` and `_core`.
- **A2 — the gate is non-vacuous.** A `tier: pro` pack/plugin under `license=deny` is **ABSENT** (not stubbed); `core`/`_core` always loads; the default is `permit-all`. Proven by a subprocess-with-fixture (the `_tiers_fixture`/`story_audit` precedent).
- **A3 — provenance records the set.** A graded run's `pipeline_runs` row carries the loaded pack + tier (+ plugins). Default-safe when unset.
- **A4 — open/closed.** A new fixture `contract` plugin (and/or pack) is added + tier-tagged **via manifest only**, picked up with **zero edits** to `grounding.py`/`judges_dspy.py`/the council (`SPEC §Success Metrics`).
- **A5 — frozen seams green + moat frozen.** `assert_judges_dspy_consensus_seam_frozen`, `assert_compliance_council_carveouts_only`, `assert_clinical_ontology_seam_frozen` all pass; `_apply_consensus` + `signals.py` + `withstands.py` byte-identical vs `acc4973`.
- **A6 — clean bar.** `ruff check`/`format` 0-new on touched files; the full `debuglithrim` suite **0-new vs parent** (cite the bare-worktree count, **not** the executor env — the §0 inflation).
- **A7 — the boundary is one auditable field.** `tier` is read at load (no longer inert); the Core/Pro line is a single manifest field, grep-auditable.

**Diagnostic stats (report, NOT gates):** plugins registered per kind; the fold LOC; whether the escape-hatch split was taken.

---

## §6 — Commit structure (suggested)

1. `feat(plugins): the plugin/pack manifest schema + validator (D1)`
2. `feat(plugins): the load-time tier gate — permit-all default, pro-under-deny absent (D2)`
3. `refactor(grounding): declare the contract registry as kind:contract plugins (D3)`
4. `refactor(council): declare the judge provider as a kind:provider plugin; binding stays core (D4)`
5. `feat(provenance): record the loaded-plugin set on PipelineProvenance (D5)`
6. `test(plugins): parity + gate non-vacuity + open/closed + frozen-seam (D6)`
7. `docs(plugins): Phase-1 CODE cycle DONE; frontend kind still deferred (D7)`

(Collapse/reorder as the plan dictates; keep each commit green + pathspec-scoped.)

---

## §7 — Verification checklist (the executor's handback must show)

1. `git diff <parent> HEAD --stat` — scope is exactly D1–D7 files; no foreign files.
2. The 3 frozen-seam guards green (paste the test names + PASS).
3. `_apply_consensus`/`signals`/`withstands` byte-identical vs `acc4973` (the moat).
4. The full `debuglithrim` suite count **at HEAD and at parent** → the 0-new delta (not the absolute).
5. `ruff check`/`format` 0-new on touched files.
6. A1–A7 each PASS, with the open/closed (A4) test pasted (the no-engine-edit proof).
7. Which forks (F1–F5) were taken; whether the escape hatch fired.

---

## §8 — First move + HARD GATE

**First move:** STOP. Produce the PLAN-REVIEW (the forks F1–F5 ruled with diagnose-before-edit evidence). Do **not** edit code until the monitor says GO.

**HARD GATE (close):** this phase closes only after a **fresh-critic worktree pass** (paste `.devloop/prompts/KICKOFF_CRITIC.md` into a separate session) returns NON-BLOCKING — the critic must independently reproduce: (A1) parity by value-equality, (A2) the gate ABSENT-under-deny by scratch-mutation, (A4) the open/closed no-engine-edit, (A5) the moat byte-identity + the 3 seam guards. The monitor's `/devloop-close-phase` will not close on the executor's word alone.

**HALT conditions:** a frozen-seam guard goes red with no authorized carve-out; the moat is not byte-identical; the gate cannot be made byte-identical under permit-all; the green-at-each-step bar forces a red intermediate (→ take the §3 escape hatch, do not push through red).

---

## §9 — References

- `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (the contract; §Data Contracts manifests; §Build-sequencing Phase-1; §Success Metrics).
- `CLAUDE.md` (the frozen-seam + healthcare-realm-as-pack + CE-PACK invariants).
- Code anchors: `harness/pack.py` · `harness/grounding.py:290-470` · `runtime/council/judges_dspy.py:65,205` · `runtime/pipeline/{models.py:176,orchestrator.py:336,provenance.py:62}` · `tests/_seam_freeze.py:85,127,226` · `tests/test_pack_layer*.py` (the parity-proof precedent).
- Memory: `conversational-first-core-plugin-line` (the OSS-core/Pro line) · `healthcare-realm-as-pack` (the relocation that shipped) · `live-reassess-before-driver-lock` (right-sizing + the escape hatch) · `gtm-launch-and-journey-thesis` (open-core/BYOK/no-us-hosted; the moat is the flywheel, not the bits).
- Prior cycle: `HANDOFF_bench-salvage_generic-ce-DONE_2026-06-12.md` (the program this builds on).
