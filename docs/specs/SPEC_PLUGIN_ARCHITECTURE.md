# SPEC: Plugin Architecture (Open-Core / Pro)

> The extension-point contract that lets lithrim-bench ship a generic OSS **Core** and separable, license-gated **Pro** capabilities (healthcare packs, premium grounding contracts) — the technical realization of the open-core GTM (free core + premium annual license + optional VPC; no us-hosted surface).
>
> **Status: DRAFT** — **OQ-1..3 RESOLVED 2026-06-09** (the conversational-first-Core direction; see §Open Questions). The full **Phase-1 spec-lock** — the §1 `frontend`-kind addition + the §4 JUTE-into-Core rewrite — lands in the **Plugin Phase-1** cycle (sequenced AFTER **CHATBIND-2**, the user's first pick). Authored 2026-06-09. Owner: monitor + user.

---

## The Problem

We are about to build a *batch* of new capabilities — the SNOMED terminology floor (HPACK), a custom expressions evaluator, more domain packs — and we want to sell on an **open-core** model: a genuinely useful free Core, with premium **Pro** capabilities (the full healthcare pack, premium grounding contracts) behind a license / VPC. Two problems if we don't fix the architecture first:

1. **Retrofit tax.** Capabilities built ad-hoc become expensive to later carve into Core vs Pro. Building them *as plugins from day one* is far cheaper than separating them after.
2. **No declared boundary.** Without a manifest that declares `tier: core | pro` and a load-time gate, there is no clean, auditable line for what ships in OSS vs what a license unlocks.

**Good news — the bench is already embryonically plugin-shaped.** This spec *formalizes and extends* existing seams; it is not greenfield (see §Existing seams).

**Non-goals (this spec):** building the registry/fetch/spawn distribution layer (Phase 3, deferred); changing the grading engine or the consensus seam; a marketplace/billing system. This spec defines the *contract*, not the storefront.

---

## Solution

### 1. Extension-point taxonomy — the plugin KINDS

| Kind | What it is | Existing seam to formalize |
|---|---|---|
| **`contract`** (grounding tool / verification contract) | The atomic plugin — disproves/suppresses a finding (suppress) or injects a BLOCK the council missed (floor). e.g. presence-check, kb-grounding, etlp structural, SNOMED terminology, expressions-evaluator. | `harness/grounding.py` `_CONTRACT_EXECUTORS` + `_FLOOR_CONTRACT_TYPES` + `_HTTP_CONTRACT_TYPES` (already a registry, already in-process-vs-HTTP aware) |
| **`provider`** (judge / model) | A model backend a judge binds to (Azure, BYO-Claude, …). | `runtime/council/judges_dspy.py` `build_judge_lm` + `_ROLE_DEPLOYMENT` (BYOC-1 made it swappable) |
| **`importer`** (case source / generator) | Turns external records or scenarios into bench cases. | `lithrim_bench/importers/backend_demo.py` (DOGFOOD-1), the Synthea injector pipeline |
| **`tool`** (agent MCP tool) | A read/lookup capability the conversational agent can call. | `apps/bff/agent/loop.py` allowlist + the S-BS-90 fail-closed deny-hook (Hermes MCP = the first external one) |
| **`pack`** (domain bundle) | A manifest bundling the above + ontology + judges + flags for a vertical domain. | the existing "pack" concept (ontology + judges + flags + grounding-tools); `harness/evalpack.py` |

The **`contract` is the unit that carries most of the Pro value** (terminology, JUTE, expressions); the **`pack` is how a vertical is sold** (healthcare pack v1).

### 2. The plugin CONTRACT — one interface, two transports

A plugin implements a **capability interface** for its kind and declares a **manifest**. It runs in one of two **transports**, behind the same interface:

- **In-process** — a Python entry-point / registry registration (the current `_CONTRACT_EXECUTORS` shape). Lowest latency, ships inside the wheel.
- **Out-of-process microservice** — composed over HTTP / MCP (the existing `_HTTP_CONTRACT_TYPES` pattern: `:8002` council, `:3031` etlp JUTE, the planned Hermes SNOMED). The host injects/reaches the client; the service is run by the operator (airgapped-friendly).

The transport is a manifest field, **not** a different interface — a `contract` is a `contract` whether it's an in-process callable or an HTTP/MCP service. This preserves the airgapped-trust posture (Pro services run *inside* the customer's VPC; nothing leaves the box).

### 3. Packs as manifest bundles

A **pack** = a manifest that names the plugins + config a vertical needs. The **"redacted-in-core" freemium hook**: the *same* pack ships at a **sample/redacted tier** in OSS (a few cases, a trimmed ontology, the contract stubbed or rate-limited) and at a **full tier** behind the license — try-before-you-license.

### 4. Core / Pro tiering + the licensing gate

Every plugin and pack manifest declares **`tier: core | pro`**. **Core** loads always. **Pro** is **license-gated** at load time and **distributed separately** (private registry / VPC bundle). The split:

- **Core (OSS):** the engine (council orchestration, the grounding-floor *mechanism*, the SQLite config plane, `run_eval`, eval-pack + the DOGFOOD-1 CI/CD gate-CLI), the generic harness + importer, **a redacted sample pack**.
- **Pro (licensed / VPC):** the **full healthcare pack**, **premium grounding contracts** (SNOMED terminology, JUTE structural, the expressions evaluator), the registry/spawn, and FDE/SME calibration.

The **moat is not the bits** (Core is genuinely useful and open) — it is the verticalized packs, the SME-calibration loop, the corpus/flywheel, and the brand (see `eval-services-venture-thesis`, `gtm-launch-and-journey-thesis`).

---

## Data Contracts

### Plugin manifest (proposed)

```json
{
  "id": "snomed_terminology",
  "kind": "contract",
  "version": "1.0.0",
  "tier": "pro",
  "transport": "service",
  "implements": "grounding.floor",
  "contract_types": ["terminology_check"],
  "service": { "base_url_env": "HERMES_URL", "health": "/v1/snomed/status", "spawn": null },
  "requires_license": true
}
```

### Pack manifest (proposed)

```json
{
  "pack_id": "healthcare", "version": "1.0.0", "tier": "pro",
  "plugins": ["snomed_terminology", "jute_structural", "expressions_eval"],
  "ontology": "clinical/1", "judges": ["risk_judge", "policy_judge", "faithfulness_judge"],
  "flags_ref": "taxonomy_snapshot", "sample_tier": { "tier": "core", "cases": 5, "contracts": ["redacted"] }
}
```

### The load-time gate (proposed)

`load_plugins(license)` → core plugins always register; a `tier: pro` plugin registers **iff** `license.permits(plugin.id)`, else it is **absent** (not stubbed) — fail-closed, mirroring the S-BS-90 deny-hook posture. The set of loaded plugins is recorded in the run-provenance blob (auditability: which Pro contracts were active for a given eval).

---

## Requirements

### P0 — Must Have (Phase 0–1)
- A **plugin manifest** schema (`kind/tier/transport/implements`) + a **registry** that the existing `_CONTRACT_EXECUTORS` / `build_judge_lm` / pack loaders are refactored onto (no new features — pure formalization).
- A **`tier: core|pro`** field honored by a load-time gate (Phase 1 may default `license=permit-all` until OQ-3 lands).
- The loaded-plugin set recorded in the provenance blob.

### P1 — Should Have (Phase 2)
- HPACK terminology floor + the expressions evaluator built **as `contract` plugins to the interface** (the first Pro plugins).
- A redacted **sample healthcare pack** in Core.

### P2 — Nice to Have (Phase 3, deferred)
- The **registry + fetch/spawn** for microservice plugins; license **enforcement** + VPC packaging; the marketplace surface.

---

## Existing seams to formalize (grounding the refactor, not aspiration)

- `lithrim_bench/harness/grounding.py` — `_CONTRACT_EXECUTORS`, `_FLOOR_CONTRACT_TYPES`, `_HTTP_CONTRACT_TYPES`, `_build_contract` (the contract registry; already in-process-vs-HTTP aware).
- `lithrim_bench/runtime/council/judges_dspy.py` — `build_judge_lm`, `_ROLE_DEPLOYMENT` (the swappable provider).
- `lithrim_bench/verification/etlp_client.py` + the structural floor (`build_floor_correction`) — the compose-over-a-local-service precedent (`:3031`).
- `apps/bff/agent/loop.py` — the MCP allowlist + the fail-closed deny-hook (the `tool`-plugin gate; the licensing gate mirrors this posture).
- `lithrim_bench/harness/{config,evalpack}.py` — the Agent/EvalProfile + the pack concept.

---

## Open Questions — RESOLVED 2026-06-09 (user)

> Resolved in the conversational-first-Core direction-setting (2026-06-09). The full Phase-1 spec-lock (the §1 `frontend`-kind addition + the §4 JUTE-into-Core rewrite) lands in the **Plugin Phase-1** cycle — these are the locked decisions it implements.

- **OQ-1 — the Core/Pro line. RESOLVED.** **Core (OSS)** = the **conversational shell** (the chat-first eval interface) + the engine (council orchestration + the grounding-floor mechanism) + the SQLite config plane + `run_eval`/eval-pack/the gate-CLI + the generic harness/importer + **ALL of JUTE** (the validator authoring/apply engine, *incl.* structural contracts) + **BYOK** + the **publicly-listed plugins**. **Pro (locked)** = the **vertical domain packs** (the full healthcare pack — ontology bundles + calibrated validators) + the **SME-calibration loop** + registry/VPC + FDE. *JUTE line (user, OQ-1 refinement): **all JUTE is Core**; only the domain packs + calibration are Pro — the generous-core OSS-adoption wedge.* The moat is the calibrated vertical CONTENT + the flywheel, **not** the bits.
- **OQ-2 — transport. RESOLVED: BOTH.** In-process AND microservice behind one interface (the existing `_HTTP_CONTRACT_TYPES` pattern). Locked Pro packs run as services *inside the operator's stack / VPC* (airgapped-friendly); BYOK + the conversational core run in-process.
- **OQ-3 — licensing. RESOLVED: separate distribution.** A subset of plugins is **listed publicly** (OSS, shipped in Core); the rest are **locked in the owner's private stack** (separately distributed — *not present in the OSS bits*). The stronger trust model (no us-hosted surface; you cannot have the locked bits without access) — **not** a license key that unlocks locally-bundled Pro plugins.
- **NEW — a `frontend`/`component` plugin kind (extends §1).** The 5 existing kinds are backend-only; the gen-UI cards + the artifact-pane surfaces are **FE plugins** under the same `tier: core|pro` + public/locked split (some gen-UI OSS, some Pro). To be formalized in **Phase-1**. **CHATBIND-2 builds the runtime trigger channel** (the conversational agent driving FE surfaces — the chat opens/focuses the 3rd pane + smart inline gen-UI); it does **not** build the registry.

---

## Build sequencing (PHASES)

- **Phase 0 — this spec.** Lock the extension points + the plugin contract + the Core/Pro boundary (resolve OQ-1..3).
- **Phase 1 — formalize the existing registries** into the plugin interface + tag `core/pro`. **Pure refactor, no new features** (grounding registry → plugin registry; provider; pack loader).
- **Phase 2 — build HPACK terminology + the expressions evaluator AS plugins** — the first Pro plugins built to the interface (not retrofitted).
- **Phase 3 (deferred) — the registry + fetch/spawn + license enforcement + VPC packaging.** The heaviest, most speculative layer; productize later.

### Critical sequencing
- **This INFORMS but does NOT BLOCK DOGFOOD-1** — DOGFOOD-1 is all Core surface (importer / judge-sets / eval-pack / gate-CLI). Let it proceed.
- **This SHOULD land before HPACK** — so the SNOMED terminology floor is the *first Pro plugin built to the interface*, not a retrofit. (Phase 0 + a minimal Phase 1 unblock HPACK.)

### Healthcare-realm-as-pack (the user's 2026-06-09 sharpening of Phase-1)

> User decision: **the entire healthcare/clinical realm loads as a PACK, not hardcoded** — for a *verifiable* boundary (grep the core for `clinical`/`snomed`/`scribe` → empty; load/unload the pack → core still runs). This sharpens Phase-1 from "tag the registries core/pro (pure refactor)" to "**relocate the clinical CONTENT into the pack so the core has zero clinical hardcoding.**" [[healthcare-realm-as-pack]]

Strangler-fig, layered, green at each step: (1) **ontology + taxonomy** → (2) judges → (3) floors/verification-contracts → (4) journey literals (`apps/shell/src/data.jsx:13` / `cards.jsx:25,29`) → (5) dataset. Completion test = the boundary grep returns empty.

**The frozen-seam tension (grounded 2026-06-09).** `KNOWN_TAXONOMY_CODES` is hardcoded in the **FROZEN** `compliance_council.py:292` (+ enforced `judges_dspy.py:142` / `judge_metric.py`). So layer 1 splits: **1a** = the ontology/taxonomy LOAD path (`harness/ontology.py:38` `DEFAULT_ONTOLOGY_PATH`, `taxonomy.py:13` `_SNAPSHOT_PATH` — *above* the seam, tractable) + a consistency gate; **1b** = un-hardcode the council's taxonomy (*inside* the frozen seam — explicit un-freeze authorization, a later cycle). The invariant MOVES not weakens: `taxonomy_snapshot` becomes the **pack's** contract; the admissibility gate parameterizes on the loaded pack (D-C in `SPEC_EVAL_SCENARIOS`).

**First cut = PACK-1** (driver `bench-salvage_phasePACK-1_healthcare-pack-ontology-layer_driver.md`, **HARD GATE**): the pack manifest + layer-1a extraction (the core loads ontology/taxonomy from the active `healthcare` pack) + the consistency gate + the boundary grep test. 1b + layers 2–5 + the story/second pack are explicit follow-ons.

**✅ Layer 1a LANDED (PACK-1, 2026-06-09).** The clinical ontology + taxonomy snapshot **relocated** (byte-identical `git mv`, R100) into `packs/healthcare/{ontology,taxonomy_snapshot}.json`; a `packs/healthcare/pack.json` manifest + `lithrim_bench/harness/pack.py` (`active_pack()` default `healthcare`, env-overridable via `LITHRIM_BENCH_PACK`; `pack_ontology_path()`/`pack_taxonomy_path()`) resolve the two former hardcodes (`harness/ontology.py` `DEFAULT_ONTOLOGY_PATH`, `taxonomy.py` `_SNAPSHOT_PATH`). The **consistency gate** (`assert_pack_council_consistent`) AST-parses the FROZEN council's `KNOWN_TAXONOMY_CODES` (no `import` — the core env has no `openai`) and fails closed if the pack declares an out-of-council code. Boundary verified by grep (`tests/test_pack_layer1a.py`): `lithrim_bench/` + `data/config/` carry no relocated clinical path; the only residual in `scripts/` are `taxonomy_snapshot` PROVENANCE LABELS in committed-corpus generators (documented carve-out — output metadata, not live load paths). **Still 1a-deferred:** layer **1b** (un-hardcode the council's `KNOWN_TAXONOMY_CODES` — inside the frozen seam; the gate bridges to it until then) + layers 2–5 (judges, floors, journey literals, dataset) + the story/second pack. The CLAUDE.md "taxonomy snapshot = the only coupling point" invariant **moved into the pack** (it did not weaken).

**✅ Layer 2 LANDED (PACK-2, 2026-06-09).** The **judge layer**: the 5 clinical council role prompts **relocated** (byte-identical `git mv`, R100) into `packs/healthcare/council_roles/`. Both readers resolve via `pack.pack_prompts_path()` — the above-seam council-light `judge_assignment.py:25` (the BFF `$0` preview, runnable with no `openai`) **and** the FROZEN live council `compliance_council.py:470`. Unlike 1a (the council carried its own value-copy of the codes, so its file was byte-untouched), the live council **globs the prompt files itself** (`_load_role_prompts`), so relocating them required repointing its `_ROLE_PROMPTS_DIR` — an **AUTHORIZED, path-only, behavior-preserving carve-out** (the established `build_judge_lm` / `verification_contracts` / `seed ontology_path` pattern). It is provably MINIMAL: a `difflib` guard (`tests/_seam_freeze.py::assert_compliance_council_prompts_dir_relocated_only`) pins `compliance_council.py` byte-identical to `acc4973` **except the single `_ROLE_PROMPTS_DIR` line** (non-vacuous — reverting it FAILS the guard); the consensus engine, the `CouncilModel` roster (`:485-516`), `_TIER1_OWNERS` (`:233-262`), `KNOWN_TAXONOMY_CODES`, and `_load_role_prompts` are 0-delta. The **judges consistency gate** (`assert_pack_judges_consistent`) AST-parses the council roster (`council_roster()` = `CouncilModel` name/prompt_role ∪ `_TIER1_OWNERS` owners — no `import`) and fails closed if the pack's declared judges lack a prompt, declare an off-roster judge, or carry a `.txt` for a non-roster role. Boundary verified by grep (`tests/test_pack_layer2.py`): `lithrim_bench/` carries no `council_roles` dir or load-path literal. **Still deferred:** layer **2b** (un-hardcode the role NAMES + `LENS_BY_ROLE` [`judge_metric.py`, still whole-file-frozen] + the owners/roster so the council reads its roster FROM the pack — the *real* council un-freeze, separate authorization) + layers 3–5 (floors, journey literals, dataset) + the story/second pack.

**✅ Layer 3 LANDED (PACK-3, 2026-06-09) — the FIRST packs-as-CODE step + the BE half of the plugin interface.** The **floor layer**: the clinical grounding *executors* relocated (behavior-identical) OUT of the domain-agnostic engine into the pack. PACK-1/2 moved DATA (ontology/taxonomy, role prompts); layer 3 moves CODE — `RecordPresence` + `_decode_artifact_soap` (from `harness/grounding.py`) + `InRowTool` + `DosageGroundingTool` + the SOAP/PMH/dose extractors (`extract_pmh_items`/`extract_plan_dose_tokens`/`_norm_dose`/`_DOSE_RE`/`_core`, from `verification/tools.py`) → `packs/healthcare/floors.py`. **The pack executor-registration interface** (this is `SPEC_PLUGIN_ARCHITECTURE`'s BE plugin contract, realized on the floor side): `pack.load_pack_floors()` importlib-loads the manifest's `"floors"` module (cached on the resolved pack id → one class identity) and the pack exposes two declarative module-level dicts — `SUPPRESS_EXECUTORS` (`record_presence`) + `FLOOR_EXECUTORS` (`dosage_grounding`, a `FloorExecutor(tool_factory, reference_builder)`). The engine merges them **lazily** (`grounding.suppress_executors()` / `floor_executors()` / `floor_contract_types()` — cached on `active_pack()`, loaded on first grounding use so the dependency points **pack→core** with no import cycle, and `import grounding` stays stdlib-only). `_build_contract` + `_run_floor` (now registry-dispatch, the inline if/elif lifted verbatim into the builders) + `ground()` route through the accessors. **The moat (A4):** the UAP-3b withstands-gate (`runtime/council/signals.py:183`) reads `grounding.suppress_executors()` (was `_CONTRACT_EXECUTORS`), so the pack's `record_presence` is moat-visible pre-consensus, behavior-identically. **The trust/packaging note:** a Pro pack now ships **in-process Python** — a real trust surface; the pack module is import-clean (pure-stdlib at import, no httpx/dspy) and the dependency points pack→core only (the critic confirms: no core→pack import, no cycle, a no-`floors` pack degrades to the generic engine). Boundary verified by grep (`tests/test_pack_layer3.py`): the clinical executor CODE is ABSENT from `harness/`+`verification/` AND PRESENT under the pack (relocation, not deletion); a blanket domain-WORD sweep is over-broad (the generic `PresenceCheck` reads a `dosage_regex` param key; `dosage_grounding`/`TOOL_DOSAGE_GROUNDING` is interface VOCABULARY) so the residual is a **CLOSED, enumerated carve-out** (the same precedent as PACK-1/2's provenance-label carve-outs). **Still deferred:** layers **4–5** (journey literals `apps/shell/src/data.jsx` / `cards.jsx`, dataset) + **2b** / **1b** (the council un-freeze) + the story/second pack.

**✅ Layer 5a LANDED (PACK-5a, 2026-06-09) — the FIRST packs-as-GENERATION step; the UNIFIED pack model (data + grading + generation).** The **dataset-generation layer**: the clinical scribe DATASET-GENERATION realm relocated (a MOVE, not an edit) OUT of the domain-agnostic engine into the pack. This **unifies the two "pack" concepts** — `lithrim_bench.packs.PACKS` (per-agent generation *recipes*) ⊕ `packs/healthcare/` (eval-config) — so a pack is now **data + grading + generation**. **Relocated** (byte-identical `git mv`, R100; only the core-primitive imports repointed pack→core) into `packs/healthcare/generators/`: the 5 scribe injectors (`WrongDosageInjector`/`MissingAllergyInjector`/`FabricatedHistoryInjector`/`ValueMismatchInjector`/`HallucinatedDetailInjector`) + the shared `_soap.py` (`mutate_soap_body`) + the 2 scribe synthesizers (`synthesize_scribe_transcript`/`synthesize_scribe_artifact`) + the `SCRIBE_PACK` recipe instance. **The generic FRAMEWORK stays core** (domain-agnostic): `PackDefinition` (the recipe *class*), `DefectInjector`/`InjectionRecipe`/`InjectionResult` (`injectors/base.py` — the by-construction label machinery), `packager`, the Synthea loaders, `encounter_spec`, and the `_pmh` helper (`clinical_conditions`; **scribe-only today** — its driver "shared with coding" rationale is stale, coding uses `_coding_dx` — but kept core in 5a, it relocates with coding in 5b). **The pack generator-registration interface** (the generation-side twin of PACK-3's `load_pack_floors`): `pack.load_pack_generators()` importlib-loads the manifest's `"generators"` package by FILE PATH — never `import packs.*` — cached on the resolved pack id (one class identity); unlike `floors` (a single module) `generators` is a multi-file PACKAGE, so it loads with `submodule_search_locations` + a `sys.modules` registration that lets the relocated modules' intra-package relative imports resolve. The pack's `generators/__init__.py` exposes the declarative `PACKS = {"scribe_v1": SCRIBE_PACK}` (mirror `floors.py`'s `SUPPRESS_EXECUTORS`/`FLOOR_EXECUTORS`); the core's new `lithrim_bench.packs.active_packs()` merges it LAZILY over the non-scribe core recipes (cached on `active_pack()`, loaded on first generation use, so the dependency points **pack→core** with no cycle, and `import lithrim_bench.packs` stays heavy-dep-free). The 2 generator scripts + the 6 scribe tests + the 2 demo scripts repoint at the loader (`load_pack_generators()`), exactly as PACK-3's consumers reach `RecordPresence`. **The HARD-GATE crux (A2):** the relocation is a MOVE — the `InjectionRecipe` IS the label justification (CLAUDE.md "labels are true by construction") — so the scribe corpus regenerates byte-identical (`generate_pack.py --pack scribe_v1` modulo its wall-clock `generated_at`; and the frozen-timestamp `generate_judge_calib.py` reproduces the **tracked** `examples/judge_calib_v1.jsonl` byte-for-byte, the automated gate). Boundary verified by grep (`tests/test_pack_layer5a.py`): the scribe generator CODE (class/def needles) is ABSENT from `lithrim_bench/` AND PRESENT under the pack — precise code needles (no broad sweep, no carve-out needed: 5a is scribe-scoped). **Still deferred:** layer **5b** (coding/hl7/scheduling/triage generators + the `_pmh` relocation + emptying core `packs.py` to a thin resolver — only then does `grep lithrim_bench/ → empty` fully hold) + **layer 4** (FE journey literals — **DROPPED from the strangler-fig**: a frozen pitch demo in a separate app, a product follow-on, not a core-boundary layer) + **2b** / **1b** (the council un-freeze) + the story/second pack.

**✅ Layer 5b LANDED (PACK-5b, 2026-06-10) — the core-boundary FINISHER: the engine carries no relocatable clinical generation CODE.** The SAME proven mechanism as 5a (`load_pack_generators` + `active_packs` + the multi-file package loader + the by-construction byte-identity gate), applied to the **last four agent-types** + the `_pmh` residual + the core-thinning 5a deferred. **Relocated** (byte-identical `git mv`, R92–R100; only core-primitive imports repointed pack→core, cross-package synthesizer refs collapsed to flat relative siblings) into `packs/healthcare/generators/`: **hl7_adt** (5 injectors `Hl7MalformedDate`/`Hl7MissingSegment`/`Hl7InvalidFieldFormat`/`Hl7MissingRequiredField`/`Hl7TriggerEventMismatch` + `_hl7.py` + 2 synthesizers + `HL7_ADT_PACK`), **coding** (`UpcodingRiskInjector` + `coding_artifact`/`coding_note`/`coding_transcript` + `_coding_dx`/`_icd10_map` + `CODING_PACK`), **scheduling** (`FabricatedConsentInjector` + `PhiDisclosurePreVerificationInjector` + 2 synthesizers + `SCHEDULING_PACK`; the **label-affecting invariant preserved verbatim** — `FabricatedConsentInjector` re-exported but intentionally NOT in `SCHEDULING_INJECTORS`), **triage** (`MissedEscalationInjector` + 2 synthesizers + `_triage_scenarios` + `TRIAGE_PACK`), and the **`_pmh` scribe residual** (`clinical_conditions`; the 5a "shared with coding" rationale was confirmed stale — `_pmh` is scribe-only, so it relocated cleanly and the pack's scribe synthesizers flip to `from ._pmh import …`, **closing S-BS-121**). **The core thinned to a resolver:** `lithrim_bench.packs._CORE_PACKS == {}`; the `PackDefinition` class + `active_packs()` stay (now resolving the FULL 5-recipe set entirely from the pack); `injectors/__init__.py` is **base-only** (`DefectInjector`/`InjectionRecipe`/`InjectionResult`); the `synthesizers/` package is **removed**. **The S-BS-120 fix** (the gate substrate): `generate_pack.py` gained an optional `--generated-at` that freezes the wall-clock `generated_at` (default unchanged), so the four non-scribe corpora are byte-deterministic; 4 committed pre-move baselines (`examples/{coding_v1,hl7_adt_v1,scheduling_v1,triage_v1}.jsonl`) anchor the gate. **The HARD-GATE crux (A2):** every relocation is a MOVE — so EACH of the four corpora regenerates **byte-identical** to its committed baseline (`tests/test_pack_layer5b.py`, 4 gates not 1, cohort-gated); the existing `judge_calib` gate additionally cross-confirms scheduling+triage. Consumers repoint at the loader (`generate_judge_calib.py` — ALL injectors now pack-sourced; the 6 agent-type tests). Boundary verified (`tests/test_pack_layer5b.py`): agent-type generator CODE (class/def needles) ABSENT from `lithrim_bench/` AND PRESENT under the pack; `injectors/` = `{__init__.py, base.py}`; `synthesizers/` carries no `.py`; `active_packs()` all-5 pack-sourced + `_CORE_PACKS == {}`; AST no core→pack import. **The residue is NOT relocatable generation code** — `grep lithrim_bench/` for clinical still hits the **FROZEN council** (`runtime/council`, the 1b/2b endgame), the **PACK-3 enumerated carve-out** (`harness`/`verification` interface vocabulary), and **generic-engine docstring examples** (`runtime/pipeline`/`backends`, a trivial future scrub). **Still deferred:** **2b** / **1b** (the council un-freeze — the endgame, behind explicit authorization) + the docstring scrub + the story/second pack.

---

## Dependencies
- No external service changes. Phase 1 is internal refactor. Phase 3 introduces a registry + (optional) spawn lifecycle + a license verifier.

## Test Plan
- Phase 1: every existing contract/provider/pack registers through the new plugin registry with **byte-identical grading behavior** (the grounding floor + council unchanged; a frozen-seam parity check). A `tier: pro` plugin under `license=deny` is **absent** (fail-closed), not stubbed; the provenance blob records the loaded set.
- Phase 2: the terminology + expressions contracts pass the floor/suppress tests **through** the plugin interface; the sample-vs-full pack tiers differ only by manifest.

## Success Metrics
- A new grounding contract (or a new pack) can be added + tier-tagged **without touching the engine** — the open/closed test.
- The Core/Pro boundary is a **single auditable manifest field**, and the loaded-plugin set is provenance-recorded per run.

## References
- `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (the service topology / strangler-fig) · the HPACK terminology recon (the first Pro contract) · `docs/strategy/PLATFORM_THESIS_bounded_context.md`.
- Memory: `gtm-launch-and-journey-thesis` (open-core + license + VPC) · `eval-services-venture-thesis` (the moat is the flywheel/SME-loop, not the bits) · `dspy-jute-prompt-builder-deferred` (the sub-vs-license / open-core packaging decision) · `walking-skeleton-architecture` (compose-over-live-services).
