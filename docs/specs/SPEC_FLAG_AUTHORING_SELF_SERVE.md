# SPEC: Flag-Authoring Self-Serve — a physician authors a deterministic floor by talking

> **Status: DRAFT 2026-06-19.** A non-coder physician (Dr Sharif) authors and tests an eval
> **criterion** by conversation + inline gen-UI — never by editing Python. The criterion that
> ships is a **deterministic grounding-floor `verification_contract`**, not a fallible LLM judge.
> External clinical-evidence retrieval (OpenEvidence), the org policy KB (`kb_context`), and coded
> concepts (Hermes/SNOMED) are **authoring-time assists** that help the human WRITE the contract;
> only the pinned deterministic contract DECIDES at grade time.
> Companions: `SPEC_CONVERSATIONAL_FIRST.md` (the conversation is the product), `SPEC_UNIFIED_AUTHORING_PRODUCT.md`
> (the author→process loop), `SPEC_PLUGIN_ARCHITECTURE.md` (TOOL-1, the `kind:tool` plane),
> `SPEC_CALIBRATION_TRAINER.md`. This spec is the **flag-authoring** slice of the unified product.

---

## 1. Thesis + the contrast (case 10)

**How Dr Sharif authors a criterion today (ClinVerdict).** A "criterion" is one rubric dimension
(Faithfulness / Completeness / Safety, scored 1–5) living inside a single hardcoded LLM-judge
prompt in a Colab notebook (`evaluators/clinical_scribe_agent.py`, `prompts.md` in
`../ClinVerdict-Physician-Curated-Clinical-AI-Evals-Suite`). Arize Phoenix is telemetry ONLY
(span/cost tracing), never the verdict engine. **Adding a criterion = edit Python + re-run the
notebook + hand-write a markdown meta-verdict.** It is a code task, gated on an engineer.

**His thesis (the indictment).** LLM judges have an ~85.7% hallucination-blindness rate; only
physician review + a DETERMINISTIC floor reliably catches safety omissions. **Flagship case 10:**
the scribe note ERASED a patient's explicit tetanus-vaccine refusal. Gemini caught it; Lithrim's
council MISSED it (Risk-Severity Blindness). The lesson is not "buy a better judge" — it is
"the floor that decides must be deterministic, and the human must be able to author it."

**The Lithrim self-serve goal.** Dr Sharif states the rubric in plain language, the system ASSISTS
him with authoritative evidence + coded concepts, and he PINS a deterministic
`verification_contract` that runs over the artifact and can inject a BLOCK on its own — all by
conversation, no notebook, no Python. The criterion he ships is **true-by-construction**
(deterministic oracle), not another fallible judge.

---

## 2. The two-plane model — and why the floor plane is the right one

A Lithrim "criterion" decomposes into two distinct planes. Only one is chat-authorable, and that
is by design.

### Plane (1) — JUDGE-LENS (subjective LLM). **Leave alone — not chat-authorable.**
A gradeable flag carries `gradeable=True` + a `tier` + `owner_roles` + a lens (the "codes you may
raise" scope). Minting one requires a **backend taxonomy re-snapshot** (it is load-bearing at
runtime: the council reads `KNOWN_TAXONOMY_CODES`, tier sets, `_TIER1_OWNERS`, the v2 roster, and
`LENS_BY_ROLE` from the snapshot — CLAUDE.md "Taxonomy snapshot is the contract").

  - **CONFIRMED:** `create_flag` deliberately HARDCODES `gradeable=False`, `tier=None`,
    `owner_roles=[]` (`apps/bff/agent/tools.py:494-526`) — a chat-created flag is **inert as a
    judge by construction**. This is correct and must NOT be relaxed: chat must not be able to mint
    a new fallible LLM judge. Doing so would manufacture exactly the hallucination-blind judges
    Sharif indicts.

### Plane (2) — GROUNDING-FLOOR (deterministic tool). **THE self-serve plane.**
A `verification_contract` on a flag runs over the ARTIFACT at grade time and can INJECT a BLOCK
independent of any judge (`lithrim_bench/harness/grounding.py:647-665`). It is chat-authorable
via `add_grounding_contract` (`apps/bff/agent/tools.py:552`) + an audited `POST /v1/grounding-contract`.

  - **CONFIRMED:** the ONLY chat-authorable write into the grade path is `add_grounding_contract`,
    which persists a deterministic `(flag_code, contract_type, params)` via a structurally-gated PUT
    (404 unknown flag / 422 malformed surfaced, never bypassed); its own success text says "the
    floor runs at grade time over this flag" (`tools.py:552-582`).

**Why the floor plane is the right one.** It is deterministic → true-by-construction → it never
hallucinates → a physician can author it without minting a fallible judge. The floor is precisely
the thing that catches the case-10 omission the council missed. Authoring on the floor plane
**generalizes the tool-grounded moat to a non-coder** without weakening the core invariant.

---

## 3. THE SPINE INVARIANT (the section that gets checked hardest)

> **One-line, non-negotiable rule:** An assist source (OpenEvidence, policy-KB) that returns
> NATURAL-LANGUAGE evidence is **AUTHORING-TIME ONLY** and MUST NOT be bound to a
> `verification_contract`. The only thing `ground()` runs at grade time is a **pinned DETERMINISTIC
> contract** whose `contract_type` resolves to a registered executor — and a registered executor
> MUST decide from the artifact + an oracle (code / structure / value), **never** from free-text
> inference, and MUST leave the finding STANDING when inconclusive.

### Why this holds — the code mechanism (CONFIRMED)

1. **`ground()` runs CONTRACTS, not the KB.** It builds its executor set strictly from
   `ontology.contracts` partitioned into `suppress_decls` / `floor_decls`, runs each per-finding
   `contract.check`, injects floors, and rescores the verdict over `active` findings. **There is no
   read of any KB/evidence tool anywhere in the grade path** — the only inputs are the pinned
   ontology contracts + the artifact (`grounding.py:589-681`; partition 589-603, per-finding
   check 624-645, floor inject 647-668, rescore over active 676).

2. **An unknown `contract_type` raises — a prose tool cannot be pinned.** If a contract's type has
   no registered executor, `ground()` raises a `ValueError` (`grounding.py:592-600`). So an evidence
   tool that returns prose **literally cannot be pinned as a contract today** — there is no path
   from "OpenEvidence prose" into the verdict without someone hand-authoring a contract whose
   executor is deterministic.

3. **Assists are read-only by construction.** `kb_context` only retrieves + displays chunks; its
   own banner says "RETRIEVAL ONLY, this does NOT change any verdict" and the source comment is
   explicit ("It NEVER changes a verdict (retrieval-only)") — there is NO write path from
   `kb_context` into the ontology or into `ground()` (handler `tools.py:668-700`; the
   `tools.py:138-140` reference is the KB-CONTEXT-1 **schema-declaration comment**, NOT a second
   handler). The HONESTY-IS-THE-PRODUCT loop block already binds the agent to "the
   verdict a tool returns IS the verdict" (`loop.py:103-116`).

4. **A deterministic floor that already lives here:** `snomed_subsumption` is a REAL grade-time
   contract (registered in the pack's `SUPPRESS_EXECUTORS`, reached by `ground()`'s suppress pass),
   deciding `disproved=True/False` purely by SNOMED code subsumption over Hermes, and
   **conservatively leaving the finding STANDING on any inconclusive case** (non-SOAP artifact /
   empty PMH / unresolved code) — `../lithrim-pack-healthcare/healthcare/floors.py:448-502`
   (inconclusive ⇒ stands 459-468, 496-502), registered `:519`. This is the template: a tool can
   have a grade-time role **iff it is deterministic and ground-by-oracle**, not prose.

### The half that is NET-NEW (the spec must add it)

The first half of the invariant is **already half-enforced by the code** (`grounding.py:599-600`
raises on an unregistered `contract_type`). The spec adds the **second half — a registration GATE**:
the system MUST refuse to register any executor that decides from free-text / LLM inference rather
than a deterministic oracle, so a future OpenEvidence integration can never be smuggled in as a
`contract_type:"openevidence_judge"`. **Authoring-time evidence informs the human; the pinned
deterministic contract decides; the two never share a code path.** (NET-NEW; see G3 + NARR-FLOOR-1.)

  - **Exact seam (the only place the invariant is currently unenforced).** Today executors register
    by a bare dict merge with NO predicate: the core `_CONTRACT_EXECUTORS` / floor merge
    (`grounding.py:295-298`) and the pack fold via
    `getattr(module, "SUPPRESS_EXECUTORS"/"FLOOR_EXECUTORS")` (`grounding.py:366-368`). The gate is a
    validation pass at the registration ACCESSORS — `suppress_executors()` / `floor_executors()`
    (`grounding.py:377-395`) — that asserts every registered executor exposes a **deterministic-oracle
    marker** (e.g. an `oracle_kind ∈ {code, structure, value}` attribute); a free-text / LLM executor
    has none → fails the pass → never registers, and `ground()` then never sees it. This is OQ-2.

---

## 4. The 4-step inline flow (Define → Assist → Compile → Test)

All four steps happen inline in the conversation (per `SPEC_CONVERSATIONAL_FIRST.md`); the pane
opens only on an explicit drill-down.

| Step | What the physician does | Gen-UI component | Honesty tag |
|---|---|---|---|
| **1. Define** | States the rubric in plain language ("the note must preserve a documented vaccine refusal"). | `FlagEditor` (rubric prose) | **EXISTS** (read-only today; `apps/shell/src/genui/index.js`) |
| **2. Assist** | Asks for standard-of-care + materiality (OpenEvidence), what OUR policy says (`kb_context`), and which codes mean "refusal" (SNOMED) → compiled into contract params. | `ContractBuilder` ASSIST sub-step with retrieval wired in | **NET-NEW** — the keystone (G2); today params are HAND-WRITTEN JSON |
| **3. Compile** | Pins a deterministic contract; live-gate against `:3031` where applicable; PIN. | `ContractBuilder` → `add_grounding_contract` → `POST /v1/grounding-contract` | **EXISTS-PARTIAL** — the write seam exists (`tools.py:552`); the inline widget is not surfaced today (adapter emits `flag_editor`, not the builder) |
| **4. Test** | Re-runs case 10; sees the floor inject the BLOCK the council missed (the honest Δ). | inline verdict card (`run_eval` → verdict + votes) | **EXISTS** — the Run/verdict surface already exists (per CONVERSATIONAL_FIRST §3) |

**Define → Assist → Compile → Test mapped:** Define (rubric prose; OpenEvidence shapes
materiality/severity) → Assist (OpenEvidence "is this standard-of-care?" + `kb_context` "what our
policy says" + SNOMED "which codes mean refusal" → contract params, never hand-JSON once G2 lands)
→ Compile (pin a `snomed_subsumption` / `structural_jute` / `jute_gen` deterministic contract,
live-gate `:3031`, raise if no executor) → Test (re-run; the floor injects the BLOCK).

---

## 5. THE ASSIST TRIO (the new heart)

Three distinct authoring-time sources. Each grounds a different knob of the contract. **Only one
of the three (SNOMED) has a legitimate grade-time role — and only because it is deterministic and
ground-by-code, not prose.** That dual role is the *template* (the rule is determinism), not an
exception to the spine invariant.

| Source | What it grounds | Tier | BYO-key / offline | Authoring-only or also grade-time |
|---|---|---|---|---|
| **OpenEvidence** (NEW · **staged LAST, access-pending** — §5.1) | External standard-of-care + medico-legal MATERIALITY ("is documenting an informed refusal the standard? is erasing a tetanus-refusal a *material* omission?") → shapes rubric prose + the chosen `inject_severity` | `core` (domain-agnostic authoring assist — see §5.1) | BYO-key on env `OPENEVIDENCE_API_KEY` (+ `OPENEVIDENCE_ORG_ID`); never the manifest; BAA for any PHI | **AUTHORING-ONLY.** Returns NL evidence; admitting it at grade time reintroduces the 85.7% blindness. NO `contract_type`, NO executor. |
| **kb_context** over `hipaa-compliancev2` (EXISTING) | The ORG's policy KB — "what OUR policy requires" (internal standard vs OpenEvidence's external/literature standard) | `core` (shipped, read-only handler) | `kb:read` credential on the BFF env; namespace in `tools.json` | **AUTHORING-ONLY** — deliberately so: "KB-grounding-as-suppress over-clears on these flags" (`tools.py:138-140`) is exactly why it was demoted to retrieval-only. |
| **Hermes / SNOMED** `snomed_subsumption` (EXISTING) | Coded-concept expansion at authoring time (pick the codes/synonyms: refusal/declines/does-not-consent = the subsumption set) | `pro` (pack-bound, `transport:service` over Hermes MCP) | Offline — local `hermes` binary + `snomed.db`, user-run, never autostarted | **BOTH.** Authoring: helps WRITE params. Grade-time: the SAME tool, bound into a pinned `snomed_subsumption` contract, decides `disproved` by CODE subsumption, leaving findings standing on inconclusive (`floors.py:448-502`). |

### 5.1 OpenEvidence — what it is + the EXACT manifest dict

OpenEvidence is a medical-AI answer engine: it takes a free-text clinical question and returns an
evidence-based answer synthesized from peer-reviewed primary literature, with **direct citations**
to the underlying studies so a clinician can verify every claim. Its corpus is backed by formal
content partnerships with NEJM, JAMA / the JAMA Network, Cochrane, NCCN, and Wiley (full text,
figures, tables); it was built under Mayo Clinic Platform Accelerate and powers Elsevier's
ClinicalKey AI. Access is a developer SDK/API: BYO API key + an organization id (`OPENEVIDENCE_API_KEY`,
`OPENEVIDENCE_ORG_ID`), over HIPAA-compliant infra requiring a signed BAA for any PHI.
**It answers and cites; it does not adjudicate.** (CONFIRMED: openevidence.com/about; the
JAMA/Cochrane/NCCN partnerships. HYPOTHESIS: the exact per-citation field names —
title/journal/doi/pmid/url — are reconstructed from a community skill's truncated examples, NOT
official docs; verify against a live key before pinning UI to specific field names.)

> **Access status (2026-06-19, HONEST):** a reachable OpenEvidence developer API has NOT been
> located — it is primarily a clinician-facing product and no public API/MCP is confirmed. This is
> why OpenEvidence is staged **LAST** (§9) and why the design binds to a VENDOR-SWAPPABLE
> **evidence-connector interface** (one `kind:tool` slot; the assist handler's I/O is *clinical
> question → citation-backed answer*), NOT to OpenEvidence specifically. If OpenEvidence access never
> materializes, the SAME slot takes an open-literature backend (PubMed / Europe PMC E-utilities,
> which DO expose public APIs). The assist layer (G2) does NOT depend on this leg — it ships on
> `kb_context` + SNOMED/Hermes first; the case-10 flip needs neither.

**Register it as a CORE `kind:tool` (manifest dict — paste-ready, every field admitted by
`PluginManifest`, `extra='forbid'`):**

```python
# append to _CORE_TOOL_PLUGINS  (lithrim_bench/harness/plugins.py:203-212)
PluginManifest(
    id="openevidence",
    kind="tool",
    tier="core",                       # domain-agnostic authoring assist → never gated
    transport="service",               # external MCP/HTTP
    implements="tool.api_connector",   # or "tool.mcp_server" if reached as a real MCP server
    service={
        "default_base_url": "https://api.openevidence.com",
        "api_key_env": "OPENEVIDENCE_API_KEY",
    },
)
# defaults fill: version="0.0.0", contract_types=[], requires_license=False
```

  - **CONFIRMED:** `id/kind/tier/transport/version/implements/contract_types/service/requires_license`
    are the only legal keys (`plugins.py:53-68`); the shape is byte-for-byte the live `etlp_jute`
    core-tool pattern (`plugins.py:203-212`). `implements` is a free `str | None` (`plugins.py:64`)
    — `tool.api_connector` for a plain REST call, `tool.mcp_server` if you adopt OpenEvidence's
    actual MCP packaging (preferred per CLAUDE.md TOOL-1: "MCP is the tool-transport standard").
  - **CONFIRMED — secrets ride ENV, never the manifest:** `service` carries only the endpoint + the
    NAME of the env var, never the value (TOOL-1 rule; mirrors `kb_hipaa` / the kb_context posture,
    `tools.py:688-690`).
  - **CONFIRMED — `contract_types=[]`:** that field is populated only on `kind:contract` plugins;
    a `kind:tool` entry leaves it at its `Field(default_factory=list)` default (`plugins.py:65`).
  - **CONFIRMED — zero engine edits:** appending the dict is the whole change; `tool_plugins()` +
    `provenance_snapshot()` pick it up automatically (`plugins.py:215-236`, `:239-271`) — the
    open/closed property (CLAUDE.md TOOL-1: "adding one = a manifest entry, ZERO engine edits").

**PLACEMENT — CORE, not the healthcare pack (INFERRED):** it is a domain-agnostic authoring-time
assist (clinical-evidence retrieval helps a human WRITE any criterion; it is not clinical CONTENT
that decides a grade). Putting it in `../lithrim-pack-healthcare/healthcare/tools.json` would (i)
make it ABSENT on a bare CE checkout where the pack is undiscoverable, and (ii) inherit `tier=pro`
(pack tools default to the pack tier, `plugins.py:230-235`), gating a free assist. As a CORE tool
it carries `tier=core` and is NEVER gated — `is_gated` returns True only for `tier in {"pro"}`
(`plugins.py:45,48-50`), and `provenance_snapshot`'s permitted filter keeps every core plugin
regardless of license (`plugins.py:266`), so OpenEvidence loads even under
`LITHRIM_BENCH_LICENSE=deny-all`. (The pack-`tools.json` path is the ALTERNATIVE only if the
maintainer wants it bundled + sold WITH the clinical pack.)

> **Note — strand divergence (HONEST):** strand B/C recommend `tier:pro` for OpenEvidence ("external
> authoritative literature behind a commercial API → gated"); strand A recommends `tier:core`
> (domain-agnostic authoring assist → free). **This spec picks `tier:core`** because the assist
> should not be absent on a CE checkout and is not clinical *content*. This is an OPEN QUESTION
> (§9, OQ-1) — the tier flips a single field, zero engine edits either way.

### 5.2 HOW USED — the two-face pattern (INFERRED)

  - **Registry face (declaration-only):** the manifest dict above → flows into `tool_plugins()` +
    `provenance_snapshot()` for the auditable boundary record. The registry records + tier-gates;
    it executes nothing (`plugins.py:189-196`: DECLARATION-ONLY).
  - **Live authoring face (NET-NEW):** a new SDK `@tool` handler `openevidence_context_handler(ctx, args)`
    modeled EXACTLY on `kb_context_handler` (`tools.py:668-700`) — $0, retrieval-only, returns
    citation-backed evidence text with a literal "AUTHORING AID — this does NOT change any verdict"
    banner, surfaces transport/auth failures (401/403/429 → backoff; **never fabricates**), reads
    the key from `OPENEVIDENCE_API_KEY` in the BFF env. Wire it into `build_sdk_tools` (`tools.py:970`).
  - **HARD GUARDRAIL (the spine invariant):** NEVER reference this tool from a flag's
    `verification_contract`; never give it a `contract_type`; never add it to any `*_EXECUTORS`
    registry. `verification_contract`s decide at grade time; an evidence/LLM tool there reintroduces
    the 85.7% blindness. Its only legitimate home is the authoring-time assist plane alongside
    `kb_context`. **That single placement choice IS the honesty boundary.**

### 5.3 The 5 case-10 authoring queries (each sharpens a contract knob)

For the case-10 criterion (the scribe ERASED a documented tetanus-vaccine refusal):

1. *"What are the documentation requirements for a patient's informed refusal of a recommended
   vaccination or treatment?"* → **CONCEPT** (the required-present element: the patient's
   refusal/declination + that risks of declining were discussed → the token/assertion the contract
   requires survive into the scribe note).
2. *"Is informed refusal a legally distinct documentation obligation from informed consent, and
   what elements must the note contain?"* → **LOCUS + completeness** (check the refusal element
   specifically, not just that the vaccine was mentioned; the sub-elements offered/declined/risks).
3. *"Does omitting a documented treatment or vaccine refusal from the record constitute a consent /
   medico-legal documentation failure, and what is the standard of care?"* → **SEVERITY** (hard
   BLOCK vs soft warning → drives `PASS→BLOCK` `inject_severity`, not a 1–5 subjective score).
4. *"For tetanus prophylaxis specifically, what must be documented when a patient declines the
   vaccine after a wound/injury?"* → **CONCEPT specificity** (bind the required concept to the
   tetanus context — require both "tetanus" AND a declination assertion co-present — tightening the
   locus to avoid a generic match).
5. *"What downstream clinical and liability risks arise if a patient's vaccine refusal is absent
   from the note?"* → **MATERIALITY** (the citation-backed rationale the author writes into the
   contract's why/who/what `AuditRecord` + the BLOCK message — making the floor's rationale
   traceable to NEJM/JAMA/Cochrane-grade evidence, not the author's say-so).

**HONESTY CAVEAT (non-negotiable):** the OpenEvidence response is itself an LLM synthesis — it can
be wrong or incomplete. It is an authoring-time assist that informs the HUMAN's rubric; the
physician reads the cited evidence, decides concept/locus/severity, and PINS the deterministic
contract that does the deciding. The evidence (+ its citations) must NEVER sit in the verdict path
and must NEVER be promoted into an LLM-judge-at-grade-time. The citations exist so the physician —
and later an auditor — can verify the human's authoring decision, not so the machine can defer to a
model.

**Combine with the rest of the trio:** OpenEvidence gives the standard-of-care concept + materiality;
`kb_context` gives the org-policy standard; Hermes/SNOMED gives the exact code/term to require
present — all three compile into the deterministic contract before it is pinned.

---

## 6. Gap list G1–G5

| Gap | Statement | Tag | Code seam (file:line) |
|---|---|---|---|
| **G1** | Emit authoring widgets INLINE — the agent must emit the `tool-contract_builder` widget, not just the read-only `flag_editor`, for `add_grounding_contract`. | **EXISTS-PARTIAL** (adapter emits `flag_editor` today) | `apps/bff/agent/adapter.py` (the `add_grounding_contract` → `flag_editor` mapping); target widget `apps/shell/src/genui/index.js` (`ContractBuilder`) |
| **G2** | The ASSIST layer = the keystone: wire retrieval (OpenEvidence + `kb_context` + SNOMED) INTO the builder so **prose → params**, no hand-JSON. OpenEvidence is G2's **authoritative external-evidence source**. | **NET-NEW** | new `openevidence_context_handler` modeled on `kb_context_handler` `apps/bff/agent/tools.py:668-700`, wired at `build_sdk_tools` `tools.py:970`; manifest at `lithrim_bench/harness/plugins.py:203-212`; consumed by `ContractBuilder` ASSIST sub-step (`genui/index.js`) |
| **G3** | Align `ContractBuilder` contract-types with REAL engine executors. `negation_check` / `code_match` / `range_check` have NO executor → `ground()` raises (`grounding.py:599-600`); `presence_check` is a SUPPRESS, not a block-floor. Add the **registration gate** (spine invariant 2nd half: refuse any free-text/LLM executor). | **NET-NEW** | `ContractBuilder` `CONTRACT_TYPES` list (`genui/index.js`) must equal the registered executor keys; gate at the executor-registration site feeding `grounding.py:592-600` |
| **G4** | NARR-FLOOR-1: the presence/semantic FLOOR executor. Today floors are `jute_gen` / `structural_jute` over STRUCTURED artifacts; `record_presence` is a SUPPRESS, not a block-floor. A floor that injects a BLOCK on a MISSING required concept does not yet exist. | **NET-NEW** | new executor registered into the floor set; plugs into `ground()`'s floor loop `grounding.py:647-665` (see §7) |
| **G5** | Retire / re-point `KbPicker` (STUB: placeholder namespaces, legacy-inert `kb_bindings`). | **EXISTS-PARTIAL** (stub present) | `apps/shell/src/genui/index.js` (`KbPicker`); re-point at the live `kb_context` assist or remove |

---

## 7. NARR-FLOOR-1 — the presence/semantic FLOOR executor interface (NET-NEW)

The case-10 criterion needs a floor that injects a BLOCK when a REQUIRED concept is MISSING from
the artifact — the structural twin of `snomed_subsumption` (which proves a *present* concept is
subsumed). Today this executor does not exist; `record_presence` is a SUPPRESS (clears a finding),
not a block-injector, and the existing floors (`jute_gen` / `structural_jute`) operate over
STRUCTURED artifacts. NARR-FLOOR-1 is the net-new floor executor.

**It takes:**

  - `expected_concept` — the concept/assertion that MUST be present (e.g. a vaccine-refusal
    assertion). Bound to an oracle: a coded set (SNOMED subsumption via Hermes, ground-by-code) or
    a structural span — **never free-text LLM inference** (spine invariant).
  - `locus` — where in the artifact it must appear (e.g. the assessment/plan span; the co-presence
    of "tetanus" AND a declination assertion, per query 4).
  - `inject_flag_code` — the flag the BLOCK is raised under when the concept is absent.
  - `inject_severity` — `PASS→BLOCK` (or WARN), chosen by the author from the OpenEvidence materiality
    evidence (query 3/5), NOT a 1–5 subjective score.

**Tri-state `conforms` (the conservative contract):**

  - `present`  → the required concept is found at the locus → **no inject** (the note is conformant).
  - `absent`   → the required concept is MISSING at the locus → **inject `inject_flag_code` at
    `inject_severity`** (the floor raises the BLOCK the council missed).
  - `inconclusive` → non-applicable artifact / unresolved code / empty span → **finding STANDS,
    no inject either way** (mirrors `snomed_subsumption`'s inconclusive-⇒-stands posture,
    `floors.py:459-468,496-502`). Never silently clear; never silently block on ambiguity.

**How it plugs into `ground()`'s floor loop (`grounding.py:647-665`):** registered into the floor
executor set so it is partitioned into `floor_decls`; for each pinned NARR-FLOOR-1 contract,
`ground()` runs the tri-state check over the artifact; on `absent` it injects a new finding under
`inject_flag_code`/`inject_severity` into the `active` set; the verdict is rescored over `active`
(`grounding.py:676`). Because it is registered (a real executor key), it satisfies
`grounding.py:592-600` (no `ValueError`); because it decides from a coded/structural oracle, it
satisfies the §3 registration gate.

  - **Paste-accurate plumbing.** Add it to a `FLOOR_EXECUTORS` dict as a `FloorExecutor`
    (`tool_factory` + `reference_builder`, the shape at `grounding.py:302-353`). The floor-inject
    loop reads `decl.params["inject_flag_code"]` and `decl.params["inject_severity"]`
    (`grounding.py:654-660`) — the NARR-FLOOR-1 param names above already satisfy that exact contract.

---

## 8. Case-10 worked example — "no code, just talk" + the honest Δ

**Define.** *"Add a Safety criterion: the scribe note must preserve a documented vaccine refusal —
if the patient refused a vaccine, the note must record that refusal."* → inline `FlagEditor` with
the rubric prose; the agent calls `create_flag` (`gradeable=False` by construction — a label, not a
judge).

**Assist.** *"Is documenting an informed refusal the standard of care, and how serious is erasing
it?"* → the agent calls the OpenEvidence assist (query 1, 3, 5) → inline citation-backed evidence
(NEJM/JAMA/Cochrane-grade) with the "AUTHORING AID — does NOT change a verdict" banner. *"What
codes mean refusal?"* → Hermes/SNOMED expands the subsumption set (declines / does-not-consent /
refusal). *"What does our policy say?"* → `kb_context` surfaces the org's documentation policy.
The physician now has CONCEPT (refusal assertion), LOCUS (co-present with "tetanus"), SEVERITY
(`PASS→BLOCK` — a consent/medico-legal failure), MATERIALITY (the rationale text).

**Compile.** Inline `ContractBuilder` (G1) shows the params **pre-filled from the assists** (G2),
not hand-JSON. The physician confirms; the agent calls `add_grounding_contract` → audited
`POST /v1/grounding-contract` (`tools.py:552-582`) pinning a NARR-FLOOR-1 (or `snomed_subsumption`)
deterministic contract on the flag; live-gate `:3031` where the contract is JUTE; PIN. The
`AuditRecord` carries the OpenEvidence-cited rationale (why/who/what).

**Test.** *"Re-run the vaccine-refusal case."* → inline verdict card. Without the contract: the
council returns **approve** (it missed the erased refusal — the case-10 Risk-Severity Blindness).
With the pinned floor: NARR-FLOOR-1 finds the refusal assertion ABSENT at the locus → injects a
BLOCK under the new flag → the verdict flips **APPROVE → BLOCK**, deterministically, traceable to
the contract, independent of any judge.

**The honest "what would flip" (and what would NOT):**

  - **Flips** only if the artifact genuinely lacks the required refusal assertion at the locus
    (`absent`). That is the case-10 win — the floor catches what the council missed.
  - Does **NOT** flip on `inconclusive` (non-SOAP artifact, unresolved code) — the finding STANDS,
    no fabricated block. Honesty over a manufactured win (the commercial moat: sell verifiable
    truth, not a promised flip).
  - Does **NOT** flip on a clean note that DOES record the refusal (`present`) — no false BLOCK.
  - The OpenEvidence evidence never enters the verdict path — if OpenEvidence were wrong about the
    standard of care, the human (not the machine) authored the wrong contract; the floor still
    decides deterministically from the artifact.

---

## 9. Open questions + build sequence

### Open questions

  - **OQ-1 (tier of OpenEvidence).** `core` (this spec — domain-agnostic authoring assist, free on
    a CE checkout) vs `pro` (strand B/C — external commercial literature, gated/absent under deny).
    Single-field flip, zero engine edits. **Deferred** — decide when the connector actually lands
    (§9 step 6), since access is currently blocked (OQ-4).
  - **OQ-2 (the registration GATE — §3 second half).** What is the exact, testable predicate that
    refuses a "free-text/LLM" executor at registration time (so `openevidence_judge` can never be
    smuggled in as a `contract_type`)? Must be mechanical, not prose — the spine invariant is only
    as strong as this gate. **Sharpest.**
  - **OQ-3 (NARR-FLOOR-1 oracle for a NL note).** The case-10 artifact is a free-text scribe note,
    but the floor must decide from a coded/structural oracle, not free-text inference. Is the oracle
    SNOMED-subsumption over an extracted concept set (Hermes), a `structural_jute` span check, or a
    `jute_gen` extraction-then-presence? The "presence over an NL artifact without LLM inference"
    bridge is the hardest unproven piece. **Sharpest.**
  - **OQ-4 (OpenEvidence access + citation shape).** No reachable OpenEvidence developer API has been
    located (it is clinician-facing; no confirmed public API/MCP) — so the evidence leg is staged
    LAST (§9 step 6) behind the vendor-swappable evidence-connector interface, with PubMed / Europe
    PMC E-utilities as the open-API fallback backend. The per-citation field shape (title/journal/doi/
    pmid/url) is HYPOTHESIS — verify against whichever backend lands before binding the
    `ContractBuilder` UI to specific field names.
  - **OQ-5 (KbPicker fate, G5).** Retire entirely, or re-point at the live `kb_context` assist as a
    namespace selector for the org-policy KB?

### Build sequence (smallest demonstrable cut first)

> **OpenEvidence is staged LAST (access-gated).** A reachable OpenEvidence developer API has not
> been located — it is primarily a clinician-facing product with no confirmed public API/MCP (OQ-4).
> So the assist layer (G2) ships on the AVAILABLE sources (`kb_context` + SNOMED/Hermes) and the full
> case-10 loop is demonstrable WITHOUT OpenEvidence; the evidence connector is a final, optional
> enrichment behind a **vendor-swappable evidence-connector interface** (§5.1).

  1. **G1 — surface the builder inline.** Re-point `adapter.py` so `add_grounding_contract` emits
     `tool-contract_builder`, not `flag_editor`. Demonstrable: the physician sees an interactive
     builder inline. (Zero new executors; smallest cut.)
  2. **G3 + OQ-2 — align contract-types + the registration gate.** Make `ContractBuilder.CONTRACT_TYPES`
     equal the registered executor keys; add the mechanical free-text-executor refusal gate.
     Demonstrable: an unregistered/prose contract-type is rejected at authoring time, not at
     `ground()` raise time.
  3. **G2 — wire retrieval → params (on the AVAILABLE assists).** The ASSIST sub-step pre-fills
     contract params from `kb_context` + SNOMED/Hermes (prose/codes → params, no hand-JSON) —
     **no OpenEvidence dependency.** Demonstrable: the case-10 contract authored with zero JSON.
  4. **G4 / NARR-FLOOR-1 + OQ-3 — the presence/semantic floor executor.** Build the tri-state
     block-injecting floor; plug into `grounding.py:647-665`. Demonstrable: the case-10 **APPROVE →
     BLOCK** flip, end-to-end by talking — the honest Δ. (The headline; it stands without OpenEvidence.)
  5. **G5 — retire/re-point KbPicker.** Cleanup after the live `kb_context` assist is the canonical
     org-policy surface.
  6. **OpenEvidence connector — LAST, access-gated.** Only once a developer key is obtained (or a
     swap-in backend is chosen): append the manifest dict (§5.1) + add `openevidence_context_handler`
     (§5.2) wired into `build_sdk_tools`. Demonstrable: the physician asks an authoring question and
     gets citation-backed evidence inline, $0, with the banner — proven NOT to touch any verdict. If
     OpenEvidence stays unreachable, bind the SAME interface to an open-literature backend
     (PubMed / Europe PMC E-utilities — public APIs) so the authoritative-evidence leg is not
     single-vendor-blocked.
