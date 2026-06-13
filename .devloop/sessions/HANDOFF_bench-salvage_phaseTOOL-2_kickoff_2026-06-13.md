# Handoff — `bench-salvage` → TOOL-2 (the 2 Pro tools)

> Written at the TOOL-1 close, 2026-06-13. The `kind: tool` declaration plane is in (TOOL-1, `487b7e1`, fresh-critic CLEAN). TOOL-2 makes the 2 Pro tools REAL — declared + executable + bound to a flag so they actually ground.

## What just landed — TOOL-1 (the kind:tool plane)

- **Verdict:** CLOSED CLEAN — built inline on the user's go + a HARD-GATE fresh-critic worktree pass **CLEAN** (7/7 checks PASS, 1 NIT). Commit `487b7e1`, parent `6468ee5`, LOCAL SSOT.
- A `kind: tool` `PluginManifest` is the consistent interface: `transport` (service=external MCP/HTTP, in_process=SDK-MCP) + `implements` (`tool.mcp_server`/`api_connector`/`kb_query`/`terminology`/`builtin`) + `service: dict` config + `tier` gate. `plugins.tool_plugins()` (core tuple ⊕ pack `tools.json` via `pack.load_pack_tools()`) → `provenance_snapshot()`, tier-gated. Declaration-only — a tool is USED by a flag's `verification_contract`.
- Session log: `.devloop/sessions/session-bench-salvage-phaseTOOL-1-2026-06-13.json`. Memory `[[tool-plane-kind-tool]]`.

## What's next — TOOL-2 (builds IN the pack repo `../lithrim-pack-healthcare`, never back in core)

Two Pro tools, each a `kind: tool` manifest + a `kind: contract` executor binding a flag.

**The decomposition (core/CE vs pack/Pro):**
- **CORE / CE (lithrim-bench):** a generic **MCP-stdio-client `VerificationTool`** + a `terminology` (or `mcp_tool`) contract executor — the *execution* half of "configure any MCP tool" (domain-agnostic; CE users wire their own MCP tools). Add its id to `verification/spec.py` `_KNOWN_TOOLS` + `_REQUIRED_REFERENCE_KEYS`. The KB side reuses the existing `KbRagTool` (already core, composes over `:8002`).
- **PACK / Pro (lithrim-pack-healthcare):** declare `hermes_snomed` + a KB tool in a new `healthcare/tools.json` (+ a `tools` ref in `healthcare/pack.json`); bind `FABRICATED_HISTORY` → Hermes `subsumed_by` in `healthcare/floors.py` + the ontology `verification_contract`.

**The Hermes grounding upgrade (the headline):** today `FABRICATED_HISTORY`'s `record_presence` contract uses `match: snomed_core` — a *string* set-membership check (sound only because the synthetic bench mints both the note PMH and `patient_profile.conditions` from identical SNOMED FSN strings; the floors.py docstring itself flags this does NOT generalize and that code-based Hermes `snomed_code` is "TERMINOLOGY-1, the next phase"). TOOL-2 delivers exactly that: upgrade `match` to `snomed_code` → resolve both to codes (Hermes `search`) → `subsumed_by(artifact_code, record_codes)` → grounded iff `==` or is-a. The `query2.clj` spike already proves the contract (T2DM `44054006` subsumed-by DM `73211009`).

**The exact wiring (from the grounding map):**
- `FABRICATED_HISTORY` contract (`healthcare/ontology.json`): `contract_type: record_presence`, params `{artifact_decode: fhir_documentreference, extractor: soap_pmh_items, match: snomed_core, oracle_path: patient_profile.conditions}`, version `record-presence/v1`.
- `RecordPresence` (`healthcare/floors.py`): `InRowTool._ungrounded` implements `match=snomed_core` as string set-membership. TOOL-2 adds a `snomed_code` branch that calls the Hermes tool.
- `KbRagTool` reference: `{namespace, service(:8002), query_field, top_k, min_score, match, expect, api_key}` over `GET :8002/v1/kb/{namespace}/search`.

**The Hermes runtime prereq (user-run, never autostarted):** the runnable `hermes` binary/uberjar (`hermes --db snomed.db mcp` — stdio JSON-RPC; the `com.eldrix.hermes.mcp` 29-tool surface). The spike's `deps.edn` `:run` alias is BROKEN (`com.eldrix.hermes.cli` isn't a ns in 1.4.1614) — the library jar ships the MCP *defs* but not the CLI `-main`; need the uberjar/native binary. `snomed.db` is built at `../hermes-spike/snomed.db`.

## Build approach (offline-first, like the existing tools)

The MCP-stdio-client + the Hermes binding are **buildable + unit-testable OFFLINE with a fake** (mirror `FakeKbHttp`/`FakeRecordRagTool`): prove the grounding flip on a by-construction pair (a carry-forward/specificity FP suppressed when the artifact code is subsumed-by a record code; an unrelated fabrication stays). Live-test once the user runs the hermes MCP server. Honest-Δ only.

## Open seams (unchanged) + standing rules

- Open: S-BS-132 (won't-fix), S-BS-135..139 (PACK-DIST-2), the older gate seams S-BS-13/16/41 (inert). TOOL-1 opened 0.
- **Standing rules:** LOCAL is SSOT (nothing pushed — the pack repo HAS a remote `origin`, so be careful: do NOT push). Services user-run (curl-check, never autostart). Commits pathspec-scoped. Moat byte-frozen vs `acc4973`; R-GUARD — never gate the 4 council accessors. Honest-Δ. **The core MCP-client must stay dependency-light** (stdlib subprocess+json stdio client; no heavy MCP dep into the default path — keep it behind the `[verification]` extra like the other tools).
