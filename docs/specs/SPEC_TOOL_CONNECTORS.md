# SPEC — Tool / MCP Connectors (the extensible grounding plane)

> **Status:** DRAFT for review · v0.1 · target: first Community Release.
> **Goal:** a community user can connect any MCP / tool / API service (terminology, search,
> KB, custom) as a grounding/eval connector — with two shipped references (**Hermes SNOMED**,
> **web search**) and a documented recipe for adding more — and the harness stays **usable when a
> connector is absent** (fail-clean, never crash, never silently flip a verdict).
> **Grounded in:** `harness/plugins.py`, `harness/pack.py`, `harness/grounding.py`,
> `apps/bff/agent/{tools,loop}.py`, `packs/*/tools.json`, and the Hermes executor in the
> external `healthcare` pack's `floors.py` (distributed separately).

---

## 0. Current state (verified, not assumed)

There are **two connector planes**; this spec is primarily about the first.

### Plane A — grounding/eval connectors (the load-bearing one)
A flag's `verification_contract` names a `contract_type`; `harness/grounding.py` dispatches it to an
**executor**, chosen by transport:
- `_CONTRACT_EXECUTORS` / `floor_executors()` map `contract_type → executor` (core ∪ active pack).
- `_contract_transport(contract_type)` returns `"service"` for `_SERVICE_CONTRACT_TYPES`
  (`kb_grounding`, `structural_jute`, `jute_gen`) plus any the pack declares via its `floors` module's
  `SERVICE_CONTRACT_TYPES`; otherwise `"in_process"`.
- Service executors call a sidecar over HTTP/MCP (e.g. `KbRagTool` → an external KB service; the
  JUTE connector → `:3031`; the pack's Hermes executor → the Hermes MCP). In-process executors run
  locally (e.g. `value_presence`, `record_presence`).

**Declaration vs execution:** `kind: tool` `PluginManifest` entries (`plugins.py`,
`tool_plugins()`/`load_pack_tools()`) *declare* a connector (id, transport, `service` config, tier);
*execution* lives in `verification`/`grounding`. Declaring a service-transport tool that reuses an
existing `contract_type` is **manifest-only, zero engine edits**. A new capability needs a new
executor.

### Plane B — conversational agent tools (in-process SDK-MCP)
`apps/bff/agent/tools.py` + `loop.py` wrap BFF ops as in-process SDK-MCP tools
(`create_sdk_mcp_server(name="lithrim", …)`). **Built-ins are deliberately off** (`tools=[]`,
`disallowed_tools=["ToolSearch"]`) for BYO-Claude safety. New conversational tools are added
here explicitly — **never** by re-enabling built-ins.

---

## 1. The connector contract (manifest)

A connector is a `kind: tool` `PluginManifest` (core static `_CORE_TOOL_PLUGINS`, or a pack's
`tools.json` loaded by `load_pack_tools`):

```jsonc
{
  "id": "hermes_snomed",
  "kind": "tool",
  "implements": "tool.terminology",      // tool.mcp_server | tool.api_connector | tool.kb_query
                                         //  | tool.terminology | tool.builtin
  "transport": "service",                // service (external MCP/HTTP) | in_process (SDK-MCP)
  "tier": "core",                        // core | pro  (pro absent under a denying LITHRIM_BENCH_LICENSE)
  "service": { "default_base_url": "http://localhost:8581" }  // config only — NEVER secrets
}
```

Rules:
- **Secrets ride env, never the manifest** (`HERMES_BASE_URL`, `WEB_SEARCH_API_KEY`, …). The manifest
  carries only non-secret config + a `default_base_url`.
- **Tier-gated at load** (`assert_pack_licensed` / `tool_plugins`); a `tier: pro` tool is *absent*
  under a denying license, not stubbed.
- **Recorded in provenance** (`provenance_snapshot()` → `loaded_plugins`), so every run states which
  connectors were active.

---

## 2. The execution binding + the fail-clean invariant

A connector becomes *used* when a flag's `verification_contract` criterion references its
`contract_type`. The executor is registered:
- **service-transport, new capability:** pack `floors` module exports the executor in
  `FLOOR_EXECUTORS` (or `SUPPRESS_EXECUTORS`) **and** lists its `contract_type` in
  `SERVICE_CONTRACT_TYPES`; core adds to `_CONTRACT_EXECUTORS` / `_SERVICE_CONTRACT_TYPES`.
- **declaration-only (reuse an existing `contract_type`):** just the manifest entry. Zero engine edits.

**The usable-harness invariant — graceful absence.** A connector that is unreachable (sidecar down,
key unset, MCP server not installed) MUST resolve to `not_applicable` / `conforms = None`
(inconclusive) — **the finding stands, the verdict does not silently flip, nothing 500s**, and the
absence is surfaced in the result. (Mirrors the existing `structural_jute` → `not_applicable` when
`ETLP_MAPPER_PUBLIC_URL` is unset, and the Hermes floor's fail-clean.)

**Live-bench-gate.** A generated/serviced connector's behavior is validated against the *real* service
before it is trusted (a service's spec can lie; the runtime can differ).

---

## 3. Reference connector #1 — Hermes SNOMED (terminology · published · `tier` per pack)

The proven instance. A **terminology** connector that grounds clinical concepts by **SNOMED code
subsumption** (authoritative), not string match.

- **Manifest:** pack `tools.json` → `{id: "hermes_snomed", implements: "tool.terminology", transport:
  "service", service: {default_base_url: <Hermes MCP>}}`. Base URL via `HERMES_BASE_URL` env.
- **Executor:** `SnomedSubsumptionGrounding` in the external `healthcare` pack's `floors.py`
  (`contract_type = snomed_subsumption`, listed in the pack's `SERVICE_CONTRACT_TYPES`).
- **Binding:** a flag's `verification_contract` names `snomed_subsumption`; the executor calls Hermes
  `subsumed_by` to decide whether a recorded PMH code subsumes/equals the noted concept.
- **Graceful absence:** Hermes unreachable → fail-clean (the finding stands; no flip). Tests:
  `test_snomed_grounding.py`, `test_specificity_flip.py` (in the pack's test suite).
- **Safety rule:** ground by **code**, not fuzzy search — fuzzy terminology lookup is unsafe as a
  clinical floor.

This is the template a pack author copies to ship any **authoritative** connector (LOINC, RxNorm,
ICD, a customer's coding service).

## 4. Reference connector #2 — Web search (general retrieval · new · core)

A **general retrieval** connector — an MCP search server (e.g. Brave/Tavily MCP) or an
`tool.api_connector`. Ships as a usable, non-clinical-safe grounding/assist tool.

- **Manifest:** `{id: "web_search", implements: "tool.mcp_server", transport: "service", tier:
  "core", service: {default_base_url: <search MCP>}}`. API key via `WEB_SEARCH_API_KEY` env.
- **Executor / use:** a `contract_type = web_search` retrieval executor (citation-assist / open
  grounding), and/or exposed as a conversational tool in Plane B for non-clinical workspaces.
- **HONEST SAFETY BOUNDARY — read this before wiring it to clinical grading.** Web results are
  **non-authoritative and unverifiable**. Web search is legitimate as: a *general/CE* grounding tool,
  a citation-finder, a non-clinical-pack retrieval aid. It is **NOT** a clinical safety floor — it
  must never be the thing that clears or raises a *clinical* safety finding (that's Hermes/KB/
  by-construction territory). The withstands-gate treats a web-search result as *evidence to weigh*,
  not as an authoritative floor that overrides the verdict. Position it accordingly in any pack that
  enables it.
- **Agent-side:** added as an explicit named MCP connector, NOT by flipping `tools=[]` back on
  (preserve the tool-less default for BYO-Claude).
- **Graceful absence:** key/server absent → the tool is simply unavailable; grading proceeds without it.

## 5. The recipe — "add a connector"

| You want to… | Do this | Engine edits? |
|---|---|---|
| Reuse an existing capability over a new MCP/API service | add a `tools.json` manifest entry (transport `service`, `service` config, env secret) | **none** |
| Add a new grounding capability (new `contract_type`) | manifest entry **+** an executor in the pack's `floors.FLOOR_EXECUTORS`/`SUPPRESS_EXECUTORS` **+** list it in `SERVICE_CONTRACT_TYPES` **+** reference it from a flag's `verification_contract` **+** a live-bench-gate test | pack-local |
| Add a conversational (in-process) tool | add a handler in `apps/bff/agent/tools.py` + the SDK-MCP server, keeping the tool-less-by-default safety posture | BFF-local |

Every connector: **secret via env**, **tier-tagged**, **fail-clean when absent**, **recorded in
provenance**, **live-bench-gated** before trust.

## 6. Security & safety

- Secrets: env only, never the manifest or `tools.json`.
- Transport: `service` connectors are external processes — treat their output as untrusted input;
  the model never executes connector-returned code (transforms are JUTE, the safe pinned DSL).
- Authority: authoritative connectors (terminology by code) may back a clinical floor; non-authoritative
  ones (web search, fuzzy retrieval) may **not**.
- BYO-Claude stays tool-less by default; tools are added by explicit, named MCP connectors only.
- Tier: `pro` connectors are absent under a denying license — fail-closed, not stubbed.

## 7. Scope for the first Community Release

Ship the **abstraction + two reference connectors + this spec** — *not* a marketplace:
- Hermes SNOMED (already in the pack) — the authoritative-terminology reference.
- Web search (new, core) — the general-retrieval reference, with the safety boundary above.
- The JUTE/`:3031` connector (already core) — the importer/transform reference (see
  `docs/JUTE_MAPPER_ADDON.md`).

The spec is what lets the community **create more**; the release ships the pattern, the references, and
the graceful-absent guarantee.

> **Post-v1 (deferred):** runtime user-authoring of tools into the config plane (no repo edit), the
> authority palette (authoritative / corroborated / advisory), a `tool.sql_query` envelope, and
> "bring your own MCP server" are deferred to a post-v1 companion spec.

> **Status:** `web_search` shipped (non-authoritative-by-construction — the executor
> always resolves `conforms=None`, attaching citations/snippets + a `web_support` assessment as evidence;
> it can never clear or raise a finding). Declared core in `tool_plugins()`; executes mocked, fails clean
> when absent/erroring.

## 8. Tests (acceptance, per connector)

- **Declaration:** manifest validates; appears in `tool_plugins()`/provenance; a `tier: pro` entry is
  absent under a denying license.
- **Execution (mocked):** the executor produces the right verdict on a recorded service response.
- **Graceful absence:** service unreachable / key unset → `not_applicable` / inconclusive, finding
  stands, no 500, no silent flip.
- **Live-bench-gate (when the real service is up):** behavior matches the live service (the gate that
  catches spec-vs-runtime drift).
