# SPEC: Standalone Core (CE) Validation — the domain-agnostic walking-skeleton

> Prove the OSS **Core** runs **standalone** as a domain-agnostic eval engine: set up a non-clinical domain, author judges from a provider, connect a tool, grade a case, get a verdict — **with the healthcare pack unloaded and `:8002` down.** This is the *falsification* of the decoupling claim: PACK-1..2c proved "swap the domain pack"; this proves "remove the domain entirely and the engine still works."
>
> **Status: DRAFT (findings + design).** Authored 2026-06-11 from a live audit + experiments (this doc's §2 evidence). **Direction LOCKED 2026-06-11 (user): the Core is a genuinely generic CE — ZERO clinical content, releasable/demonstrable standalone — and ALL clinical content (including the prompt logic) continues into the `healthcare` pack.** The disposition is therefore **relocation** (finish the strangler-fig: move the last clinical residue out of core into the pack — like PACK-3 moved the floors), NOT a carve-out and NOT routing-around. Owner: monitor + user. Precedes any driver.

---

## 0. Demarcation principle (LOCKED 2026-06-11)

**Core (CE, OSS, releasable standalone):** the generic engine only — the authored ontology-driven prompt path (`render_role_questions`), the consensus/withstands MECHANISM (already pack-resolved), the provider seam, the generic case schema, the pack loader, the generic grounding/tool registry. **`grep lithrim_bench/` for any domain word → empty** is the acceptance bar, extended now to the council's *prompt* layer (not just its data layer).

**Healthcare (a Pro pack):** ALL clinical content — ontology, taxonomy, role prompts, floors, generators, **the clinical flag-definition prose, AND the clinical prompt-assembly logic** (the HIPAA scaffold + the scheduling/coding/intake/scribe nuance currently in `build_prompt`). "Continue healthcare work as a pack" = these relocate into `packs/healthcare/`, the same strangler-fig that ran PACK-1..2c.

The strangler-fig is therefore **not** complete (the PACK-2c close overstated it for the *data* layer): the council's clinical **prompt** still lives in core. This spec defines the final layers + the standalone proof that the demarcation holds.

---

## 1. Why this, why now

The PACK-2c second-pack proof swapped a pack's **data** (taxonomy/owners/lenses/roster) and showed a different council with zero core edits. But **every existing non-healthcare pack** (`_tiers_fixture`, `_nondeployable_fixture`, `story_audit`) **reuses `packs/healthcare/council_roles` + `packs/healthcare/ontology.json`** (verified — all four manifests point `council_roles`/`ontology` at `packs/healthcare/`). So the decoupling was **never exercised with healthcare *content* (prompts + ontology) absent.** The honest claim today is "the *data* layer is pack-resolved," not "the Core is a standalone domain-agnostic CE."

This spec closes that gap with a single falsifiable test and the minimum work to pass it.

---

## 2. Audit findings (evidence-backed)

### 2.1 The grade path is **two paths** with asymmetric domain-agnosticism — CONFIRMED by experiment

`scripts/run_eval.py:235-279`: `--in-process` selects the **authored** stage iff the agent carries `assignments|models|roles`, else the **default** in-process council.

**Experiment (`$0`, debuglithrim) — render both prompt paths, grep for clinical needles** (`HIPAA|patient|medication|dosage|allerg|clinical|SOAP|escalat|consent|transcript`):

```
DEFAULT council path  — get_flag_prompt_section():  218 needle hits; 23 core-hardcoded clinical flag defs
                        (MISSED_ESCALATION, WRONG_DOSAGE, MEDICATION_NOT_IN_TRANSCRIPT, …) — emitted regardless of active pack
AUTHORED path         — render_role_questions(non-clinical pack):  0 needle hits — a clean non-clinical judge prompt
```

- **AUTHORED path = domain-agnostic.** `runtime/council/judges_dspy.py:375` → `render_role_questions(ontology, role)` (`judge_assignment.py:46-101`) = the active pack's `council_roles/<role>.txt` **base** + an ontology-derived refinement. A non-clinical pack flows through with **zero** clinical leakage. **This is the standalone engine.**
- **DEFAULT/legacy council = clinical-hardcoded in CORE.** `ComplianceCouncil.build_prompt` (`compliance_council.py:517-787`) injects `get_flag_prompt_section()` (`:752`) → `SAFETY_FLAG_DEFINITIONS` (`safety_flags.py:37`, **23 core-resident clinical flag definitions** with prose) + a literal clinical rule (`safety_flags.py:642` *"If a patient has emergency symptoms… use MISSED_ESCALATION"*) + a HIPAA/agent-category scaffold (`:596-655`). **This is what the owed `ws0_default` eval ran** (no assignments).

### 2.2 Gap taxonomy

| Gap | What | Severity | Blocks standalone? |
|---|---|---|---|
| **G1 — no independent non-clinical pack** | every non-healthcare pack reuses healthcare's `council_roles` + `ontology` | — | The *test* doesn't exist yet. Building one is step 1. |
| **G2 — the default council path is clinical-hardcoded in core** | `build_prompt` + `get_flag_prompt_section` + `SAFETY_FLAG_DEFINITIONS` (`safety_flags.py`, 23 clinical defs) inject clinical content regardless of pack | **HIGH** | Yes — *if* the standalone CE uses the default path. **No** if it uses the authored path. |
| **G2a — `safety_flags.py` is core-resident clinical content** | the relocation moved taxonomy *codes* (snapshot) but not the flag-definition *prose* | HIGH (couples to G2) | Same as G2 |
| **G3 — tool/vector grounding is backend-coupled** | KB grounding → `:8002` HTTP only (`verification/tools.py:233-394`); no direct-Pinecone in core; `runtime/pipeline/retrieval.py` is an M1 stub (returns empty) | MEDIUM | **No** — KB grounding is *optional + degradable* (`:8002` down → `conforms=None`, the flag stays active, never silently clears). BYO-vector is a *capability*, not a blocker. |

### 2.3 What is already clean (do NOT rebuild)

- **Provider seam — domain-agnostic + proven.** `build_judge_lm` (`judges_dspy.py:205-256`) routes Azure / OpenAI / BYO-Claude via env (`settings.LITHRIM_LLM_PROVIDER`) + `_ROLE_DEPLOYMENT`. No clinical logic. `_ROLE_DEPLOYMENT` is keyed by role **names** (a pack subsets known deployable identities — the PACK-2c OQ-2 boundary). BYO-Claude is live-proven (BYOC-1).
- **Case schema — generic.** A case needs `case_id` + `artifacts[0].content` (+ optional `transcript`, `expected_compliance_verdict`); `picklist.py:101-112`, `grade.py:65-82`. The clinical assumption is in the *prompt* (G2), not the data schema — a non-clinical case grades through the schema fine.
- **The MECHANISM is pack-resolved (PACK-1..2c).** tiers/owners/lenses/roster/prompts-dir/ontology all resolve from the active pack; the consensus oracle + the withstands-gate read pack lenses/owners. Domain-agnostic.

---

## 3. The validation design — the standalone walking-skeleton

**One headless end-to-end run, healthcare unloaded, `:8002` down, over the AUTHORED path:**

```
LITHRIM_BENCH_PACK=<generic>   (+ no :8002, no etlp)
  setup/configure a generic non-clinical pack
  → author a judge (BYO provider) with an ontology ASSIGNMENT   (→ the authored path)
  → grade a non-clinical case
  → verdict, with 0 clinical leakage in the judge prompts
```

### 3.1 Deliverable A — a genuinely independent non-clinical pack (`packs/<generic>/`)

Closes **G1**. Must supply its OWN (no `packs/healthcare/` paths):
- `pack.json` — `tier: core` (the redacted sample tier), own `ontology` + `flags_ref` + `council_roles`, `judges` ⊆ `_ROLE_DEPLOYMENT` (reuse role *names* risk/policy/faithfulness; the OQ-2 boundary).
- `ontology.json` — a non-clinical domain (e.g. support-ticket-QA or doc-review): `flags` (each `flag/definition/tier/gradeable/owner_roles/when_to_use/when_NOT_to_use/category`), `questions`, `severity_map`, `verification_contracts`, versions.
- `taxonomy_snapshot.json` — `tiers` / `tier1_owners` / `production_judges` / `lenses` over the non-clinical codes (internally consistent: lens ⊆ owners; codes ⊆ tiers).
- `council_roles/{risk,policy,faithfulness}_judge.txt` — non-clinical role prompts.
- A tiny non-clinical **case** (`case_id` + an `artifacts[0].content` text + `expected_compliance_verdict`).

### 3.2 Deliverable B — a headless standalone E2E test (`tests/test_standalone_ce.py`)

A subprocess (mirror `test_pack_layer2c.py`) with `LITHRIM_BENCH_PACK=<generic>` and **no `:8002`**, asserting:
- **A-STANDALONE-1:** the council assembles + the authored judge prompts render with **0 clinical-needle hits** (the §2.1 grep, inverted-green).
- **A-STANDALONE-2:** a non-clinical case grades end-to-end → a verdict, **healthcare unloaded** (no `packs/healthcare/` path read — assert via a path-trace or an import guard).
- **A-STANDALONE-3:** `:8002` down does not crash the grade (KB grounding absent or degraded; the non-clinical ontology declares no `kb_grounding` contract for the minimal cut).
- **A-STANDALONE-4 (provider):** the judge binds to a BYO provider via env (offline/mock LM for `$0` CI; a separately-gated live smoke for the real paid confirmation).

### 3.3 Deliverable C — relocate the residual clinical content into the pack (the demarcation)

The clinical residue in core splits into two relocations, very different in risk. **Continuing healthcare-as-pack:**

**Layer 6a — `safety_flags.py` flag-defs → pack ontology (cheap, non-frozen, the data is already there).**
- **CONFIRMED:** `SAFETY_FLAG_DEFINITIONS` (23 core defs) is an **exact stale duplicate** of `packs/healthcare/ontology.json`'s flags — codes match (core ⊆ pack, no core-only), prose matches (`definition`/`when_to_use` byte-equal on spot-check). So the data already lives in the pack.
- **Move:** make `get_flag_prompt_section()` build the taxonomy section from the **active pack's ontology** (not the core literal); delete `SAFETY_FLAG_DEFINITIONS` + the hardcoded clinical escalation line (`safety_flags.py:642`) — relocate that rule into the healthcare role prompts/ontology. `safety_flags.py` is **NOT under the freeze guard** → a clean refactor (the 2c-lens-half shape). Value-preserving: the emitted section for healthcare must be equivalent to today's.
- Removes **23 clinical flag defs + the escalation rule** from core.

**Layer 6b — the clinical `build_prompt` council → healthcare pack (the deep one, FROZEN, its own HARD-GATE cycle).**
- `compliance_council.py:517-787` `build_prompt` is ~270 lines of clinical prompt-assembly LOGIC (HIPAA framing + `agent_category` branches scheduling/coding/intake/scribe) inside the FROZEN file. This is the LEGACY/default council path; the product direction is the authored path (UAP).
- **Move (relocation, not carve-out):** the clinical default-council prompt builder becomes a **healthcare-pack artifact** — relocate `build_prompt` (and its clinical scaffold) into `packs/healthcare/` as the pack's council-prompt provider; the core council retains only the **generic authored-path assembly** (`render_role_questions` from the active pack's ontology + role prompts) + the domain-agnostic mechanism. A core council with no pack prompt-builder uses the generic authored path.
- **This is the deepest cut to date** — it relocates LOGIC out of the trust anchor, not a data lookup. It needs: its own HARD-GATE cycle, a fresh-critic worktree pass, a re-pinned baseline (the default-council `ws0_default` verdict must be reproduced through the relocated pack builder), and a decision on whether `build_prompt` is relocated-as-is or **retired** in favor of the authored path with the clinical nuance folded into healthcare's role prompts/ontology.
- **OQ-1 (the only real open question):** relocate `build_prompt` verbatim into the pack (preserve the legacy default council exactly, just pack-homed) **vs.** retire it and fold its clinical evaluation nuance into the healthcare pack's role prompts + ontology (authored-path-only core). Monitor lean: **relocate-verbatim first** (value-preserving, re-pin the baseline), then optionally retire once the authored path demonstrably covers the nuance.

After 6a + 6b: `grep lithrim_bench/runtime/council/` for clinical content → empty; the core council is the generic CE.

### 3.4 Deliverable D (follow-on, not in the first cut) — BYO-vector tool (G3 / KB-VENDOR-1)

Once the engine is proven standalone, add a **connect-your-own-vector-store** validation: implement `runtime/pipeline/retrieval.py` (the M1 stub) OR override `KbRagTool.service`/`_search` to hit a BYO Pinecone directly (no `:8002`). ~50 LOC per the audit. Validates the *tool* layer is also backend-free. **Separate cycle.**

---

## 4. Sequencing

The strangler-fig continues; the standalone validation is the *proof* the demarcation holds, run after the relocations.

1. **CE-PACK-6a — `safety_flags` flag-defs → pack ontology** (Deliverable C / Layer 6a). Cheap, non-frozen, data already in the pack. Removes the 23 clinical defs + escalation rule from core. Value-preserving (equivalent emitted section for healthcare).
2. **CE-STANDALONE-1 — the falsification test** (Deliverables A + B). Build the independent non-clinical pack + the headless E2E (authored path, healthcare unloaded, `:8002` down, 0 clinical leakage, a verdict). This can land in parallel with / right after 6a, since the authored path is already clean — it *proves* the core is generic and becomes the regression guard for 6b.
3. **CE-PACK-6b — the clinical `build_prompt` council → healthcare pack** (Deliverable C / Layer 6b). The deep, FROZEN, HARD-GATE cycle: relocate the legacy clinical default-council prompt builder into `packs/healthcare/`, re-pin the baseline, fresh-critic worktree. Resolves OQ-1 (relocate-verbatim vs retire). **After this, the core council greps clinical-clean.**
4. **CE-STANDALONE-2 (follow-on)** — Deliverable D — BYO-vector (KB-VENDOR-1 minimal).
5. **ChatBind / Agentic Protocol — AFTER.** It drives the (now-proven-standalone) engine; it is not part of *validating* the boundary. Sequence per `SPEC_PLUGIN_ARCHITECTURE` (`frontend` kind, post-CHATBIND-2).

## 5. Acceptance — "standalone CE" goes INFERRED → CONFIRMED when

- A real independent non-clinical pack exists (no `packs/healthcare/` reuse), and
- `test_standalone_ce.py` is green: a non-clinical case grades end-to-end via the authored path with **healthcare unloaded + `:8002` down + 0 clinical leakage**, and
- a gated live smoke produces a sane verdict on a BYO provider.

Honest-Δ: if any leg fails, it pinpoints the residual coupling — that is the *point* of the test.

## 6. Open questions

- **OQ-1 (6b disposition — the one real call):** relocate `build_prompt` **verbatim** into the healthcare pack (preserve the legacy default council exactly, re-pin the baseline) vs **retire** it (authored-path-only core; fold its clinical nuance into healthcare's role prompts + ontology). Monitor lean: relocate-verbatim first, retire later if the authored path demonstrably covers the nuance. (The demarcation direction itself is LOCKED §0 — this is only *how* 6b lands.)
- **OQ-2:** does the non-clinical pack ship as a committed `tier: core` **sample pack** (doubling as the freemium redacted-sample hook in `SPEC_PLUGIN_ARCHITECTURE`)? Likely yes — it earns its keep twice (validation fixture + OSS sample).
- **OQ-3:** mock-LM vs a real `$0`-replay for the CI grade (A-STANDALONE-2) — keep CI free while still exercising the full assembly.

## 7. References
- Audit experiments + caller graph: this doc §2 (2026-06-11, monitor + 2 recon agents).
- `SPEC_PLUGIN_ARCHITECTURE.md` (the Core/Pro boundary; the `tier: core` sample-pack hook).
- Memory: `walking-skeleton-architecture` (domain-agnostic tool-grounded harness — the original thesis), `healthcare-realm-as-pack`, `grounding-floor-is-the-moat-next` (KB-VENDOR-1).
