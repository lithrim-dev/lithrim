# HANDOFF — `bench-salvage` — 2026-06-12 (Plugin Phase-1 is DONE; the open-core split is now enforced)

> Written by the monitor on the PLUGIN-1 close. **Plugin Phase-1 (the registry-unification CODE cycle) is COMPLETE** — the Core/Pro boundary is a single, auditable, **load-bearing** manifest field, the three registries are unified, and grading is byte-identical by default. **Services: the user runs them — `curl`-check, never autostart. LOCAL is SSOT (nothing pushed all program). The owner-gated push remains the user's call.**

---

## What just landed

- **Closed phase:** PLUGIN-1 — the full Plugin Phase-1 registry-unification (commits `ef2e61c..8187b33`, atop parent `6234164`; 7 deliverables + session log)
- **Critique verdict:** **NON-BLOCKING** [0/2/0] (HARD-GATE fresh-critic `a164f36488ee9faa0`, worktree-isolated opus) — `.devloop/sessions/critique-bench-salvage-PLUGIN-1-2026-06-12.md`
- **Audit verdict:** CLEAN (monitor 7-item — moat byte-identical, R-GUARD honored, F3 seam intact, scope tight)
- **Session log:** `.devloop/sessions/session-bench-salvage-phasePLUGIN-1-2026-06-12.json`

**What it did:** formalized the three ad-hoc registries (`harness/pack.py` pack loaders, `harness/grounding.py` `_CONTRACT_EXECUTORS`+floors, `judges_dspy.py` `build_judge_lm` provider) onto **one plugin manifest** (`lithrim_bench/harness/plugins.py` — `PluginManifest`/`PackManifest`, `extra=forbid`, kind/tier/transport Literals). Made the previously-**inert** `tier` field **load-bearing** via a fail-closed `License`/`assert_pack_licensed` gate (permit-all default → byte-identical; `pro`-under-deny → **absent**, mirroring the S-BS-90 deny-hook). Recorded the loaded-plugin set on `PipelineProvenance` (additive, default-safe). All proven by a 17-test parity proof + a discovery-inert `_plugin_fixture` pack. The escape hatch was **not needed** — full D1–D7 shipped green at each step.

**The moat held:** `_apply_consensus` (`d1b7956e`) + `extract_verdict_confidence` (`ed867bce`) byte-identical vs `acc4973` (critic-reproduced); the 3 frozen-seam guards green; `judges_dspy.py` top-level symbol set identical (the D4 fold is a **body-only local import** inside `build_judge_lm`; `_ROLE_DEPLOYMENT` read-through, deployment stays core per PACK-2c); `signals.py`/`withstands.py` 0-diff vs parent.

> ⚠️ **Count correction (carry this — same env-inflation as every cycle):** the executor handback said "2 fails"; the fresh-critic bare-worktree truth is **HEAD 661p / 4f / 3s, 0-new vs parent 644p/4f/3s**. The 4 fails are pre-existing (`test_byoc_provider` Azure, `test_uap3_grade` missing gitignored fixture, 2× S-BS-96 observation pollution). Cite **0-new (661/4/3)**.

## Plugin Phase-1 — the picture now

The **content-relocation half** shipped earlier (PACK-1..2c + the generic-CE demarcation program). PLUGIN-1 was the **registry-unification half**. Together: the OSS Core is a domain-agnostic eval+calibrate+gate engine; the `healthcare` realm is a `tier:pro` pack; the boundary is **one grep-auditable manifest field, enforced at load**. A new contract or pack can be added + tier-tagged **without touching the engine** (the open/closed test, A4, passed). The **`frontend` kind remains deferred** (post-CHATBIND-2 — it needs the runtime trigger channel).

## What's next — the user's strategic call (NO autostart)

Plugin Phase-1 is done; **Phase-2 is the natural successor but the user picks**:
- **HPACK (SPEC Phase-2)** — build the **SNOMED terminology floor + the expressions evaluator AS `contract`-kind plugins to the now-live interface** (the first Pro plugins built-to-interface, not retrofitted). This is exactly what PLUGIN-1 unblocked. Ties into [[grounding-floor-is-the-moat-next]] (TERMINOLOGY-1 = Hermes-as-MCP). **Strong default.**
- **CHATBIND-2** — the chat-drives-the-3rd-pane line; also the precondition for the deferred `frontend` plugin kind.
- The **grounding-floor / KB-VENDOR-1 / TERMINOLOGY-1** stream.
- Cleanups: **S-BS-133** (transport mis-tag, Phase-2/HPACK) · **S-BS-132** (retire the inert source_message machinery) · the bare-path `test_consensus` conftest pin · the **owner-gated push**.

## Open seams for `bench-salvage` (PLUGIN-1 delta)

| ID | Title | Severity | Status |
|---|---|---|---|
| S-BS-133 | A pack's service-transport floor would be mis-tagged `transport=in_process` (declarative metadata only, zero grading impact) — fix when a pack first ships one (HPACK) | low | **open (PLUGIN-1)** — *the executor's log filed this as "S-BS-132"; renumbered (collision with the open 6c seam)* |
| — | Bare-path `test_consensus` collection artifact (conftest healthcare-pin not an ancestor of `runtime/council/tests/`); pre-existing, 20/20 under the pin | cosmetic | observation (PLUGIN-1) |
| S-BS-132 | source_message machinery now fully inert — retire wholesale (NON-frozen) | low | carried-open (CE-PACK-6c) |
| S-BS-127 | freeze-guard marker-SUBSTRING residual | low | carried-open |
| S-BS-113 | `seed_ontology --check` STALE + the D2-a deleted-path refresh | low/med | carried-open |

## Load-bearing context the next monitor MUST know

1. **The plugin interface is now LIVE — build to it.** Any new grounding contract or domain pack must declare a `PluginManifest`/`PackManifest` (`harness/plugins.py`) with `kind/tier/transport`; `tier:pro` is license-gated at the `*_path` resolvers. **R-GUARD is permanent:** never add the license gate to the 4 council inline-import accessors (`pack_tiers`/`pack_tier1_owners`/`pack_lenses`/`pack_production_judges`) — gating them re-enters the frozen council's module import. The gate lives only on the ontology/taxonomy/prompts `*_path` resolvers (beside `assert_pack_council_consistent`).

2. **The provider fold kept deployment in core.** D4 routed only the BYOC-1 *selection* (`resolve_provider_id`, a local import in `build_judge_lm`) through the registry; `_ROLE_DEPLOYMENT` (provider/Azure-id/capability) stays byte-frozen core (PACK-2c, infra ∉ a domain pack). A brand-new deployable provider needs core support — the deployment boundary is intentional.

3. **The two plan-review CITATION-DRIFTs are now reconciled into the driver + STREAM** (D-1: tier ∈ {core,pro,fixture,demo}, gate only `pro`; D-2: the moat pin is `_apply_consensus`/`extract_verdict_confidence` sha-vs-`acc4973` + signals/withstands 0-diff-vs-parent — NOT "byte-identical vs acc4973" for files that post-date it). The honest moat framing is the load-bearing one; don't regress to the imprecise claim.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_bench-salvage.md` (First move → the strategic options; Open seams).
3. Read this handoff.
4. `git log --oneline -12`.
5. Wait for the user's strategic call. **No queued next cycle — do NOT autostart.** If the user picks HPACK, the next monitor action is `/devloop-expand-driver bench-salvage HPACK` (author from `SPEC_PLUGIN_ARCHITECTURE` §Phase-2 + the HPACK terminology recon + [[grounding-floor-is-the-moat-next]]).

## References
- This cycle: session `session-bench-salvage-phasePLUGIN-1-2026-06-12.json` · critique `critique-bench-salvage-PLUGIN-1-2026-06-12.md` · driver `bench-salvage_phasePLUGIN-1_plugin-registry-unification-tier-gate_driver.md`
- Spec: `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` (§Phase-1 DONE; §Phase-2 = HPACK; the `frontend` kind still deferred)
- Memory: `conversational-first-core-plugin-line` (the OSS-core/Pro line) · `healthcare-realm-as-pack` (the relocation arc) · `grounding-floor-is-the-moat-next` (HPACK/TERMINOLOGY-1) · `live-reassess-before-driver-lock` (the escape hatch held in reserve, not needed)
- Prior handoff: `HANDOFF_bench-salvage_generic-ce-DONE_2026-06-12.md`
