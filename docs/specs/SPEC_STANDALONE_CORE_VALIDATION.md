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
| **G4 — core DSPy `JudgeSignature` is clinical-hardcoded** (S-BS-129) | `judges_dspy.py` `_build_signature()` frames judge I/O with "clinical/patient/HIPAA" prose — a THIRD core clinical residue the §2.1 audit missed, surfaced by CE-STANDALONE-1 | MEDIUM | **No** for the `$0` path (bypasses `_build_signature`); **YES on the LIVE authored path** (the prose reaches the LLM). → folds into **6b-CLEAN**. |
| **G5 — `DEFAULT_PACK="healthcare"` blocks shipping core without the pack** (S-BS-130) — ✅ **CLOSED 2026-06-12** | was: `pack.py` → `council_roster()` reads `packs/healthcare/{pack.json,taxonomy_snapshot.json}` for canonical validation under ANY active pack; same root as S-BS-125 | MEDIUM (**release-gating**) | **RESOLVED by CE-PACK-NEUTRAL-DEFAULT** — `DEFAULT_PACK="_core"` (a neutral pack); `council_roster()` now reads `packs/_core/`, so the core boots + grades standalone with healthcare absent (`tests/test_neutral_default.py`: zero `packs/healthcare/` reads). Retires the S-BS-125 tripwire. |

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

**Layer 6b — RETIRE the clinical `build_prompt` council; the authored path is the single live prompt source (OQ-1 RESOLVED 2026-06-11, user).**

Decision: **retire**, not relocate-verbatim. Rationale (user): no users / no legacy to preserve, and a hardcoded `build_prompt` is a **second, conflicting source of prompt truth** that would silently ignore UI-authored prompt edits (the product authors prompts via the ontology + role prompts = the authored path). One live prompt source is the only coherent model. Bonus: the authored path gives each judge *only its assigned lens*; `get_flag_prompt_section()` dumps the entire taxonomy to every judge — so retiring is a focus/quality gain, not a compromise.

Phased so the product concern is solved WITHOUT frozen-council surgery first:

- **6b-ROUTE (non-frozen, immediate, solves the product concern).** Make the in-process grade dispatch (`scripts/run_eval.py` / the grade path — NOT frozen) ALWAYS use the authored path: when an agent carries no explicit assignments, default each judge's assignment to its **pack lens** (`pack_lenses()[role]`) and run `build_trio`/`render_role_questions`. The default `build_prompt` council becomes **dead code** (still physically in the frozen file, but unreachable). Re-pin the `ws0_default` baseline on the authored path (a behavior change to the reference verdict, justified by no-legacy). After this, UI prompt edits are the only thing that moves the prompt — the product model is coherent.
- **6b-CLEAN (FROZEN, later HARD-GATE cycle, for grep-clean).** Physically remove `build_prompt` (+ its `get_flag_prompt_section` import) from the frozen `compliance_council.py` and delete `safety_flags.py` (subsumes 6a — once nothing live reads it). This is the frozen-file edit; fresh-critic worktree. End state: `grep lithrim_bench/runtime/council/` for clinical content → empty; the core council is the generic CE.

- **Deferred deeper layer (noted, not scoped here):** even the authored path's BASE is a static `council_roles/<role>.txt` (`load_role_prompt`). FULLY UI-editable prompts need the **ontology as the single prompt source** (full `.txt` retirement — `render_role_questions` flags it as deferred: the ontology doesn't yet carry the full safety prose / codes-you-may-not-raise / HL7 exceptions). Retiring `build_prompt` is necessary but not sufficient for that; tracked as a follow-on, not in 6b.

After 6b-ROUTE the live path is authored-only (product-correct); after 6b-CLEAN the core is clinical-clean (CE-pure).

### 3.4 Deliverable D (follow-on, not in the first cut) — BYO-vector tool (G3 / KB-VENDOR-1)

Once the engine is proven standalone, add a **connect-your-own-vector-store** validation: implement `runtime/pipeline/retrieval.py` (the M1 stub) OR override `KbRagTool.service`/`_search` to hit a BYO Pinecone directly (no `:8002`). ~50 LOC per the audit. Validates the *tool* layer is also backend-free. **Separate cycle.**

---

## 4. Sequencing

The strangler-fig continues; the standalone validation is the *proof* the demarcation holds, run after the relocations.

1. **CE-STANDALONE-1 — the demonstrable proof — ✅ DONE 2026-06-12** (`fe1d170..e2f9b8e`; `packs/support_ticket_qa/` + `tests/test_standalone_ce.py`). A1–A7 green; active-domain decoupling proven non-vacuously (A4 audit-hook: zero healthcare DOMAIN content read). **Surfaced G4/S-BS-129 (signature) + G5/S-BS-130 (DEFAULT_PACK) — folded in below.** Live smoke owed.
1b. **CE-PACK-NEUTRAL-DEFAULT — ✅ DONE 2026-06-12** (`0b70d61..` ; `packs/_core/` + `DEFAULT_PACK="_core"` + `tests/conftest.py` + `tests/test_neutral_default.py`). A neutral core-shipped `DEFAULT_PACK` (`packs/_core/` — generic codes, the deployable-judge trio as `production_judges`, the canonical owner-role SET incl. owner-only `behavior_judge`/`source_message_judge`) so `council_roster()` validates without reading a Pro pack — the core ships WITHOUT healthcare. `tests/test_neutral_default.py` proves it: env-unset → `active_pack()=="_core"`, identity-stable roster, a generic case grades to a `reject` verdict, and an audit hook records **ZERO `packs/healthcare/` reads** across boot+grade. The existing suite is pinned back to `healthcare` by `tests/conftest.py` (`setdefault LITHRIM_BENCH_PACK=healthcare`) — pack resolution is import-frozen, so the bounding mechanism is a session env pin, not a per-test sweep; full suite 0-new. **Resolves S-BS-130 + retires the S-BS-125 tripwire.**
2. **CE-PACK-6b-ROUTE — authored-path-only live grade** (non-frozen). Default no-assignment agents to their pack lens; `build_prompt` becomes dead code; re-pin `ws0_default` on the authored path. Solves the product concern (UI-authored prompts are the only live source). Immediate, no frozen surgery.
3. **CE-PACK-6b-CLEAN — remove `build_prompt` + `safety_flags.py` + genericize `_build_signature` from the frozen core** (FROZEN, HARD-GATE, fresh-critic worktree). Subsumes 6a + **G4/S-BS-129** (the signature; the `test_standalone_ce` diagnostic flips green when it lands). End state: `grep lithrim_bench/runtime/council/` clinical-clean = the generic CE.
4. **CE-STANDALONE-2 (follow-on)** — Deliverable D — BYO-vector (KB-VENDOR-1 minimal).
5. **ChatBind / Agentic Protocol — AFTER.** It drives the (now-proven-standalone) engine; it is not part of *validating* the boundary. Sequence per `SPEC_PLUGIN_ARCHITECTURE` (`frontend` kind, post-CHATBIND-2).

> Note: Layer 6a (relocate `safety_flags` → pack ontology) is **subsumed by 6b-CLEAN** under the retire decision — once the authored path is the only live path, nothing reads `get_flag_prompt_section()`, so `safety_flags.py` is deleted outright rather than relocated. The pack ontology already carries the flag prose (CONFIRMED §3.3).

## 5. Acceptance — "standalone CE" goes INFERRED → CONFIRMED when

- **DONE (CE-STANDALONE-1, 2026-06-11).** A real independent non-clinical pack exists with **no `packs/healthcare/` reuse** — `packs/support_ticket_qa/` (`tier: core`; its OWN `ontology.json` + `council_roles/` + `taxonomy_snapshot.json`; A7 grep-verified empty of `packs/healthcare`). It is the OSS sample pack (OQ-2: **yes**, it earns its keep twice).
- **DONE for the CI legs (CE-STANDALONE-1).** `tests/test_standalone_ce.py` is green: the non-clinical case (`tests/fixtures/standalone/case.support_ticket_qa_fabricated_policy.jsonl`) grades end-to-end via the **authored path** to a `reject` verdict with **the healthcare pack unloaded + `:8002` down + 0 clinical leakage** in the rendered judge prompts, at `$0` via injected predictors (the `test_uap3_grade` pattern). A-STANDALONE-1..5 each pass.
- **OWED.** A gated live smoke producing a sane verdict on a BYO provider (the real-provider confirmation via `run(in_process=True, assignments=…)`; not CI spend) — still to run.

Honest-Δ — the two residual couplings this falsification test **pinpointed** (that is the *point* of the test; NEITHER blocks the pack from running, so each is a finding, not an escalation; both are relocation/6b targets, not in CE-STANDALONE-1's scope):
- **S-BS-129** — the core DSPy `JudgeSignature` (`runtime/council/judges_dspy.py` `_build_signature`, the `:175-200` region) still hard-codes clinical prose ("clinical artifact", "HIPAA / clinical-safety council", "provider/patient conversation", "transcript"). It is OFF the authored render path (A-STANDALONE-1 stays clean) and the `$0` predictor path bypasses it — but the LIVE path sends it to the LLM. Tracked by the non-gating diagnostic in `test_standalone_ce.py`; retire in **6b-CLEAN**.
- **S-BS-130 — ✅ CLOSED 2026-06-12 (CE-PACK-NEUTRAL-DEFAULT).** `DEFAULT_PACK` used to be `"healthcare"` (`harness/pack.py`), making `council_roster()` read `packs/healthcare/{pack.json,taxonomy_snapshot.json}` for canonical-roster validation even under a non-healthcare active pack. The default is now the neutral `_core` pack, so the canonical capability roster is sourced from a core origin; A-STANDALONE-4 tightened to assert **zero** `packs/healthcare/` reads (was: permit-only the two metadata files), and `tests/test_neutral_default.py` proves the env-unset shipped default reads zero healthcare files across boot+grade.

## 6. Open questions

- **OQ-1 — RESOLVED 2026-06-11 (user): RETIRE `build_prompt`** (not relocate-verbatim). No users / no legacy; a hardcoded prompt builder conflicts with UI-authored prompt edits (two sources of prompt truth). The authored path is the single live prompt source. Phased: 6b-ROUTE (non-frozen, immediate) → 6b-CLEAN (frozen, grep-clean). See §3.3.
- **OQ-2:** does the non-clinical pack ship as a committed `tier: core` **sample pack** (doubling as the freemium redacted-sample hook in `SPEC_PLUGIN_ARCHITECTURE`)? Likely yes — it earns its keep twice (validation fixture + OSS sample).
- **OQ-3:** mock-LM vs a real `$0`-replay for the CI grade (A-STANDALONE-2) — keep CI free while still exercising the full assembly.

## 7. References
- Audit experiments + caller graph: this doc §2 (2026-06-11, monitor + 2 recon agents).
- `SPEC_PLUGIN_ARCHITECTURE.md` (the Core/Pro boundary; the `tier: core` sample-pack hook).
- Memory: `walking-skeleton-architecture` (domain-agnostic tool-grounded harness — the original thesis), `healthcare-realm-as-pack`, `grounding-floor-is-the-moat-next` (KB-VENDOR-1).
