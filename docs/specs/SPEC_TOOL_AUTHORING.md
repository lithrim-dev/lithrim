# SPEC — Tool Authoring (bring / declare your own grounding tool)

> **Status:** DRAFT for review · v0.1 · **POST-v1** companion to `SPEC_TOOL_CONNECTORS.md`.
> **Goal:** a user (helped by Claude) **authors and loads their own grounding tool** — a SNOMED /
> terminology service, a SQL record-check, a RAG / KB query, or any MCP server — into a workspace
> **at runtime, without editing repo files**, audited, tier-tagged, and fail-clean when absent.
> **The connector is _declared_, never _coded_** — custom execution lives behind the user's own MCP
> server, in their trust boundary; Lithrim calls it over the transport and treats the output as
> untrusted.
> **Grounded in (verified, not assumed):** `harness/plugins.py` (`tool_plugins`, `PluginManifest`),
> `harness/pack.py` (`load_pack_tools`), `harness/grounding.py` (the executor registries +
> `KbGrounding`/`WebSearchGrounding`), `apps/bff/app.py` (`POST /v1/judges` 2559–2641,
> `/v1/connector/config` 3698–3760, `/v1/connectors` 4886–4913), `apps/bff/agent/tools.py` (the ~18
> SPINE/CONTAINMENT SDK-MCP tools), `apps/shell/src/genui/JudgeBuilder.jsx` (the card to mirror),
> `lithrim_bench/verification/mcp_client.py` (`McpStdioClient` — exists, **zero call sites today**).

---

## 0. Relationship to v1 — this is NOT in the release

The first Community Release (`COMMUNITY_RELEASE_v1_PLAN.md`) ships the connector **pattern** + two
**reference** connectors (Hermes SNOMED, web search) declared as pack-file `tools.json`, with the
graceful-absent guarantee (`SPEC_TOOL_CONNECTORS.md` §7). That is enough for v1.

**This spec is the post-v1 program** that turns "a maintainer edits a `tools.json` file" into "a user
authors a tool from the chat / UI and loads it into their workspace." It is two coherent additions:

- **Part A — the authoring palette (depth):** the kinds of tool a user can author and the *authority*
  each carries (authoritative floor vs advisory evidence), plus the per-flag **lens join**. (§2)
- **Part B — the authoring spine (runtime):** the SPINE/CONTAINMENT path — gen-UI card → `POST /v1/tools`
  → config-plane store → audit → grade-time union — that mirrors how judges/flags are already authored.
  (§3–§6)

Neither is a v1 blocker. Build it after the Cycle-1 BYOK gate. The healthcare-depth instances
(authoritative SNOMED, the EHR SQL record-check) belong in the **Pro pack repo**, behind the license.

---

## 1. The safety thesis — read this first

"Author a tool" must **never** mean "upload code Lithrim executes." That is the RCE-unsafe path the
whole architecture exists to avoid (the airgapped-trust thesis; transforms are JUTE, the safe DSL —
`[[harness-jute-is-the-safe-transform-dsl]]`). Authoring a tool means exactly **two safe acts**:

1. **DECLARE a connector** — a `kind: tool` `PluginManifest` (id, `implements` sub-kind, `transport`,
   non-secret `service` config, `tier`). You are *pointing at a service*, not shipping logic.
2. **BIND it to a flag** — a `verification_contract` criterion naming *which flag* the tool grounds, the
   *authority tier*, and *pinned / parameterized* params. The flag is already lens-scoped, so the bind
   makes the tool a specific reviewer's grounding tool (§2.3).

Custom execution logic lives behind the **user's own MCP server / API**, which runs in *their* trust
boundary. Lithrim invokes it over the MCP / HTTP transport (`McpStdioClient`, §5) and treats its output
as **untrusted input** (the model never executes connector-returned code). This is precisely what makes
"anyone can author a tool" safe: the dangerous part (arbitrary execution) stays on the author's side of
an explicit, named, transport boundary.

> **One-line rule:** *Declare the connector here; keep the code over there.*

---

## 2. Part A — the authoring palette (what you can author, and its authority)

### 2.1 Authority tiers — a knob, not a fixed kind

Every authored tool sits at one of three authority levels. The level — not the tool's technology — is
what determines whether it may flip a verdict. The bench already encodes the two endpoints in code
(`KbGrounding` can flip on corroboration; `WebSearchGrounding` is non-authoritative by construction —
`grounding.py:317`, `:417`).

| Tier | Can flip a verdict? | When to use | Honesty discipline |
|---|---|---|---|
| **Authoritative floor** | Yes — clears or holds a finding | a deterministic check: terminology subsumption, a pinned SQL record lookup | the answer is a real yes/no over structured truth |
| **Corroborated** | Yes, but only on a *positive, corroborated* hit; **never on silence** | retrieval where a tight predicate (`claim_in_chunk`) adjudicates what was retrieved | a miss / error is **inconclusive**, never a pass |
| **Advisory evidence** | **No** — attaches evidence only (`conforms=None`) | open web search, fuzzy retrieval | results are unverifiable; the withstands-gate *weighs* them |

### 2.2 The three connectors this program targets

| Connector | `implements` | Authority | Safe-execution envelope |
|---|---|---|---|
| **SNOMED / terminology** | `tool.terminology` | **Authoritative floor** | ground by **code subsumption**, never fuzzy text (`subsumed_by`). The proven reference (`SnomedSubsumptionGrounding`, pack repo). |
| **exec-to-SQL record-check** | `tool.sql_query` *(new sub-kind)* | **Authoritative floor** | the **Alvera envelope**: **SELECT-only** (writes rejected), **pinned / parameterized** query as a contract param (not model-authored), **egress-controlled** — the executor returns a *signal* (does row X exist? does value match?), **never rows into a prompt**. |
| **RAG / KB query** | `tool.kb_query` | **Corroborated** (or dial down to Advisory per flag) | retrieval is the *retriever*; the floor authority is the **corroboration predicate** (`match: claim_in_chunk`), not the embedding score; **never clears by silence** (`KbGrounding`, `grounding.py:396`). Direct-Pinecone connector variant for standalone/BYOK (no `:8002`). |

> **exec-to-SQL — the only piece without a repo precedent.** Model the executor on Alvera's
> `execute-sql`: read-only, parameterized, rows written to a `0600` artifact and reduced to a boolean
> signal, never streamed to the judge. The model may, at most, *select a pinned query template* — it
> never authors raw SQL that gets executed. (Model-authored "text-to-SQL" is allowed only as **Advisory**
> evidence, reviewed, never as a floor.)

### 2.3 The lens join — you bind a tool to a *flag*, not to a lens

There is no `lens → tool` table and there should not be one. A `verification_contract` is keyed by
`flag_code`; a flag is *already* lens-scoped (a reviewer cannot raise an out-of-lens code without
failing the withstands-gate). **The flag is the join.** "Give the faithfulness reviewer a SQL
record-check" = "attach a `sql_query` contract to the flags faithfulness owns." This keeps the authoring
surface small and leaves the frozen council untouched.

The composition that makes the three sing together: **RAG feeds the deterministic tools.** Retrieval
finds *what to check* (candidate codes, candidate records); SNOMED / SQL *decides*. Retrieval never
decides on its own — that preserves the moat (*the agent narrates; the floor decides*).

---

## 3. Part B — the authoring spine (mirror the judge/flag path)

The bench already authors judges, flags, criteria, and grounding contracts into the config plane via one
repeated shape — **SPINE/CONTAINMENT**: the agent (or UI) *emits a card*; the human's **Save** is the
*sole* write; the write is *audited*; the grade path *picks it up*. Tool authoring is the same shape with
a new entity. The chain to clone (judge authoring, verified):

```
ToolBuilder.jsx                 ← gen-UI card (mirror JudgeBuilder.jsx; registerTool("tool-tool_builder"))
   │  user fills: id, sub-kind, transport, service.base_url, tier, + bind: flag_code, authority, params
   ▼
bff.js  createTool({...})       ← mirror createJudge (bff.js:374); rationale rides ?rationale= (the audit "why")
   ▼
POST /v1/tools                  ← mirror POST /v1/judges (app.py:2559); validate manifest + bind, then persist + audit
   ▼
authored_tools (config plane)   ← new table, mirror the judges table (judges.py:91, ON CONFLICT upsert) — §4
   ▼
AuditRecord (who/when/why/what) ← the §2B spine, transactional, with rollback on failure
   ▼
grade time: tool_plugins() ∪ authored  → executor invokes the connector, fail-clean when absent  — §5
```

**The agent path (A-SAFE):** add **one** SDK-MCP tool, `author_tool`, to `apps/bff/agent/tools.py`
`_TOOL_SPECS` — *emit-only*, mirroring `create_judge` (`tools.py:682`). It surfaces the ToolBuilder card;
it **never writes**, **carries no paid key** (the S-BS-81 A-SAFE invariant), and the human's Save is the
sole write. Built-ins stay off (`tools=[]`, `disallowed_tools=["ToolSearch"]`) — preserve the BYO-Claude
tool-less default; tools are added by explicit named connectors only.

---

## 4. The config-plane store (new) — `authored_tools`

Mirror the `judges` table exactly (`harness/judges.py`), **per-workspace** and **Postgres-portable**
(the live BFF is Postgres — use `ON CONFLICT … EXCLUDED`, never `INSERT OR REPLACE`;
`[[config-plane-sql-must-be-postgres-portable]]`):

```sql
CREATE TABLE IF NOT EXISTS authored_tools (
  workspace_id TEXT NOT NULL,
  tool_id      TEXT NOT NULL,
  manifest_json TEXT NOT NULL,   -- the kind:tool PluginManifest (no secrets)
  bind_json     TEXT,            -- {flag_code, authority, contract_type, params, version}
  created_at   TEXT NOT NULL,
  PRIMARY KEY (workspace_id, tool_id)
);
-- upsert:
INSERT INTO authored_tools (workspace_id, tool_id, manifest_json, bind_json, created_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (workspace_id, tool_id) DO UPDATE SET
  manifest_json = excluded.manifest_json,
  bind_json     = excluded.bind_json;
```

- **Secrets never land here.** Reuse the existing `/v1/connector/config` surface (`app.py:3698`) — it
  validates the key with a read-only probe and writes it to the gitignored `.connector_env` /
  `.connector_sidecar`, recording an audit row with **no secret**. The manifest carries only
  `default_base_url` + non-secret config; the live base URL + key resolve from env at call time.
- **The bind** persists into the agent's ontology working-copy `verification_contracts`
  (`out/workspaces/<ws>/agents/<agent>.json`) — already grade-time-consumed via the mtime-keyed
  ontology cache (`ontology.py load_ontology`), so a re-grade sees the new tool with no extra wiring —
  **or** alongside the manifest in `authored_tools.bind_json`. Prefer the ontology overlay for the bind
  (it's already on the honest draft→grade seam); use `authored_tools` for the connector manifest.

---

## 5. Grade-time pickup + the MCP executor (close the gaps)

Two seams to add (both **above** the frozen council — no touch to `compliance_council.py` /
`_apply_consensus` / `signals` / `withstands`):

1. **Union the authored tools.** `tool_plugins()` (`plugins.py:238`) today returns core ⊕ pack. Add a
   third fold: ⊕ the workspace's `authored_tools` (validated through `PluginManifest`, tier defaulted).
   Pass the workspace/db through the grade subprocess the same way assignments/models are threaded
   (today the grade subprocess defaults to full-lens — extend the same wiring point in `run_eval.py`).

2. **Wire the MCP executor.** `verification/mcp_client.py::McpStdioClient` exists (initialize handshake +
   `tools/call`) but has **zero call sites**. Add a generic grounding executor — `mcp_call` /
   `http_query` / `sql_query` (contract_types) — that resolves an authored connector by id and invokes
   it: stdio MCP via `McpStdioClient` for `tool.mcp_server`; httpx for `tool.api_connector` /
   `tool.kb_query`; the pinned-SELECT envelope for `tool.sql_query`. The executor maps the connector
   result to a `Verdict` per the tool's authority tier (§2.1).

**The graceful-absent invariant is non-negotiable** (`SPEC_TOOL_CONNECTORS.md` §2): an unreachable
connector (server down, key unset, MCP not installed) resolves to `not_applicable` / `conforms = None` —
the finding **stands**, the verdict does **not** silently flip, nothing 500s, and the absence is
surfaced. A live-bench-gate validates a connector against the real service before it is trusted (the
spec lies / the runtime differs).

---

## 6. "Someone with Claude" — three readings, all supported

1. **Claude authors the manifest _with_ you (conversational).** The BFF Agent-SDK loop surfaces the
   ToolBuilder card; you fill / confirm the connector + bind; your Save is the sole write. (§3, the
   `author_tool` SDK tool.)
2. **Your tool _is_ an MCP server.** You already run MCP servers in the Claude / Anthropic ecosystem —
   declare one as `implements: tool.mcp_server`, `transport: service`, bind it to a flag, and Lithrim
   invokes it via `McpStdioClient` (§5). Your code never enters Lithrim's process.
3. **Claude is the reviewer (BYO-Claude provider)** that consumes the tool's evidence / floor signal —
   the judge LM and the tool are independently chosen; the tool grounds whatever council you've authored.

---

## 7. Acceptance tests (per the existing connector test shape, `SPEC_TOOL_CONNECTORS.md` §8)

- **Author → load:** `POST /v1/tools` upserts an `authored_tools` row (Postgres-portable), records one
  `AuditRecord` (who/when/why/what), and the manifest validates through `PluginManifest`.
- **Grade-time union:** a workspace-authored tool appears in `tool_plugins()` / provenance for that
  workspace; a `tier: pro` authored tool is absent under a denying `LITHRIM_BENCH_LICENSE`.
- **Bind → flip (mocked):** an authored authoritative connector, bound to a flag, suppresses / holds the
  right finding on a recorded service response; an advisory one attaches evidence and **never** flips.
- **Graceful absence:** connector unreachable / key unset → `not_applicable`, finding stands, no 500, no
  silent flip.
- **A-SAFE:** the `author_tool` SDK tool emits the card only, carries no paid key, performs no write
  (the agent never mints the tool).
- **MCP live-gate (real server up):** `McpStdioClient` round-trips the declared server and the executor's
  verdict matches the live behavior (catches spec-vs-runtime drift).

---

## 8. Build sequence (post-v1)

1. **`authored_tools` store + `POST /v1/tools` + audit** (mirror judges; Postgres-portable). RED tests
   first.
2. **`tool_plugins()` union + grade-subprocess wiring** (authored tools picked up at grade time).
3. **The generic MCP / HTTP executor** — wire `McpStdioClient`; `tool.mcp_server` + `tool.api_connector`
   + `tool.kb_query` over the existing transports; graceful-absent.
4. **ToolBuilder gen-UI card + `author_tool` SDK tool** (the conversational authoring surface, A-SAFE).
5. **`tool.sql_query` + the pinned-SELECT envelope** (the Alvera record-check — the one genuinely new
   executor). Pro-pack instances (SNOMED authoritative, EHR SQL) build in the pack repo.

> The frozen council is untouched throughout — every seam here is above the withstands-gate. The moat
> stays byte-frozen vs `acc4973`.

## 9. References

- `docs/specs/SPEC_TOOL_CONNECTORS.md` — the v1 connector pattern + Hermes / web-search references + the
  fail-clean invariant (this spec extends it post-v1).
- `docs/specs/SPEC_PLUGIN_ARCHITECTURE.md` — the `kind: tool` plane, tiering, TOOL-1 / TOOL-2.
- `CLAUDE.md` — the frozen seam, the plugin registry, the by-construction invariant.
- The Alvera CLI execute-sql pattern (SELECT-only · parameterized · egress-controlled) — the safe-SQL
  envelope for `tool.sql_query`.
