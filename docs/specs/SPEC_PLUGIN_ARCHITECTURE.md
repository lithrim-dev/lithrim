# SPEC: Plugin Architecture (Open-Core / Pro)

> The extension-point contract that lets lithrim-bench ship a generic OSS **Core** and separable, license-gated **Pro** capabilities (healthcare packs, premium grounding contracts) — the technical realization of the open-core GTM (free core + premium annual license + optional VPC; no us-hosted surface).
>
> **Status: DRAFT** — OQ-1..3 open (the Core/Pro line, the transport stance, the licensing mechanism). Authored 2026-06-09. Owner: monitor + user.

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

## Open Questions (the user resolves; these gate the lock)

- **OQ-1 — the exact Core/Pro line.** *Lean:* Core = engine + generic harness + the gate-CLI + a redacted sample pack; Pro = the full healthcare pack + premium contracts (terminology/JUTE/expressions) + registry/VPC + FDE. Where exactly does the line sit — e.g. is the *expressions evaluator* core (a generic math primitive) or pro?
- **OQ-2 — transport stance.** *Lean:* support **both** in-process and microservice behind one interface (flexible, reuses the existing pattern). Alternative: **microservices-only for Pro** (cleaner VPC isolation + license enforcement, heavier ops). Which?
- **OQ-3 — licensing mechanism.** A **license key** that unlocks *locally-bundled* Pro plugins (simpler, but the bits are present) vs Pro plugins **only fetchable from a private registry** (can't have the bits without a license — stronger, ties to the no-us-hosted/trust-wedge stance). Which enforcement model?

---

## Build sequencing (PHASES)

- **Phase 0 — this spec.** Lock the extension points + the plugin contract + the Core/Pro boundary (resolve OQ-1..3).
- **Phase 1 — formalize the existing registries** into the plugin interface + tag `core/pro`. **Pure refactor, no new features** (grounding registry → plugin registry; provider; pack loader).
- **Phase 2 — build HPACK terminology + the expressions evaluator AS plugins** — the first Pro plugins built to the interface (not retrofitted).
- **Phase 3 (deferred) — the registry + fetch/spawn + license enforcement + VPC packaging.** The heaviest, most speculative layer; productize later.

### Critical sequencing
- **This INFORMS but does NOT BLOCK DOGFOOD-1** — DOGFOOD-1 is all Core surface (importer / judge-sets / eval-pack / gate-CLI). Let it proceed.
- **This SHOULD land before HPACK** — so the SNOMED terminology floor is the *first Pro plugin built to the interface*, not a retrofit. (Phase 0 + a minimal Phase 1 unblock HPACK.)

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
