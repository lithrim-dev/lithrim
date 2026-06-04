# SPEC: Unified Authoring + Processing Product
> The complete product is the UI-driven **author → process** loop over the config plane: **create judges → create flags → run processing**, all from the UI. The 4-act journey is a **frozen** pitch/onboarding demo *inside* this product. **Compose, don't rebuild** — the engine, the config plane, the BFF, the shell, and the gen-UI widgets already exist; this spec wires them into one operational product. Every action — authoring and processing — is captured in a **why/when/who/what audit trail** (§2B): in a regulated domain, the audit *is* the product.

**Status:** **LOCKED 2026-06-04 (user)** · **Authored:** 2026-06-04 · **Owner:** monitor (bench-salvage) · **§13 conversational-driver surface ADDED 2026-06-04 (additive, surface-only — does not alter the lock)**
**Reframe of record:** memory `unified-authoring-product-frozen-journey`; `STREAM_bench-salvage.md` First-move banner (2026-06-04). Supersedes the *journey-on-real-service-calls* framing of WS-7 for everything except the now-closed **WS-7a** beachhead.
**Sits above:** `SPEC_PRODUCT_SHELL.md` (the shell UI) + `SPEC_CALIBRATION_TRAINER.md` (the judge-tuning surface = Stage 1's optimize step) + `SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (the strangler-fig service plane).

---

## 0. Context — the 2026-06-04 reframe

Two tracks ran in parallel: the **DSPy-judge / calibration engine** (`runtime/council/*`, the floor, the corpus) and the **shell/journey product UI** (`apps/shell`, `apps/bff`). The user froze the journey (it is the demo, not the product) and **unified the tracks**: the product is the tool an SME uses to *stand up and tune their own eval* — author the judges, author the flags they grade against, and run processing — then iterate. The journey demonstrates the payoff; this product *is* the payoff.

The load-bearing realization: **almost every block already exists.** The work is integration + closing three surface gaps, not greenfield.

---

## 1. The Problem

Today an eval is stood up by hand-editing files: judge prompts in `runtime/council/council_roles/*.txt`, flags/severity/contracts in `data/ontology/clinical_v1.json` (via `seed_ontology.py`), the agent eval-profile in `data/config/agents/*.json`, and processing via `scripts/run_eval.py`. The shell can *display* a graded result and *edit an ontology draft* (WS-5d `PUT /v1/ontology`), but it cannot **create a judge**, cannot complete a flag end-to-end into a live grade, and has no **processing surface** beyond the single replay run the journey calls. An SME cannot self-serve the author→process loop — which is the entire product thesis ("who calibrates?" — the SME, in the UI).

---

## 2. Solution — the author→process loop over the config plane

```
        ┌─────────────────────────  apps/shell (the product UI)  ─────────────────────────┐
        │   Stage 1: Judges        Stage 2: Flags          Stage 3: Processing             │
        │   ┌──────────────┐       ┌──────────────┐        ┌──────────────────────────┐    │
        │   │ JudgeEditor* │       │ FlagEditor   │        │ RunPanel* + ResultsView  │    │
        │   │ + optimize   │       │ ContractBldr │        │ (VerdictCard,            │    │
        │   │ (calib)      │       │ KbPicker     │        │  CalibrationChart)       │    │
        │   └──────┬───────┘       └──────┬───────┘        └──────────┬───────────────┘    │
        └──────────┼──────────────────────┼───────────────────────────┼────────────────────┘
                   │   gen-UI registry (tool-<name> → component, WS-5c) │
        ┌──────────┼──────────────────────┼───────────────────────────┼────────────────────┐
        │          ▼   apps/bff  (FastAPI judge-capability API v1)      ▼                    │
        │  /v1/judges* (GET/PUT/optimize)  /v1/ontology (GET/PUT)   /v1/run-eval, /v1/case,  │
        │  /v1/agent* (GET/PUT)                                     /v1/corpus, /v1/kb/*,    │
        │                                                          /v1/runs*                 │
        └──────────┬───────────────────────┬──────────────────────────┬─────────────────────┘
                   ▼                        ▼                          ▼
        ┌─────────────────────  WS-1 SQLite config plane  ─────────────────────┐   ┌── engine ──┐
        │  Agent { EvalProfile{judges, council_config, ontology_ref/path,      │   │ run_eval    │
        │          tools, kb_bindings, severity_map_ref}, Dataset }            │   │ grade(_*)   │
        │  Ontology { flags, questions, contracts, severity_map }              │   │ council v2  │
        │  (config.py save_agent/load_agent · ontology.py from_dict)           │   │ floor + KB  │
        └──────────────────────────────────────────────────────────────────────┘   └─────────────┘
              * = the net-new surfaces this spec adds; everything else exists.
```

The config plane (`harness/config.py` `Agent`/`EvalProfile`, `harness/ontology.py` `Ontology`) is the **single write-target**. The UI composes an `Agent`; the engine runs it; the results feed the calibration loop. The journey is a frozen `mode` of the same shell.

---

## 2A. Entity model + the critique-as-verification gate (2026-06-04 refinement)

An evaluation is composed of **first-class entities** that execute per evaluation. The UI assembles them; the engine runs them; a critique gate reconciles the LLM layer with the deterministic layer.

### The entities
- **LLM Judge.** A judge is **formed by ASSIGNING an ontology subset** (flags) to it — the assigned flags' `JudgeQuestion{role, ordinal, text}` **become the judge's refinement questions** (its lens + prompt). A judge does **not** carry free-text prose authored in isolation; its questions are *derived from the ontology it is assigned*. A judge may additionally **attach + EXECUTE** already-generated, persisted **smart-contract validators** as part of its evaluation — **but a judge never generates a validator** (generation is a separate authoring concern). The judge is a validator **consumer**.
- **Smart-contract validator** (`smartContractValidator`). A deterministic, **already-generated + persisted** validator (the verification toolbox: `structural_jute`, `jute_gen`, `dosage_grounding`, presence-checks, …). Authored/generated separately — the **DSPy bench-gated JUTE generator** (`verification/jute_dspy.py`, generate→test→refine against the by-construction oracle) — and persisted. Executed (never authored) by judges or as independent grounding checks. *Judges run them; the generator makes them.*
- **GroundingCheck.** A first-class **INDEPENDENT** entity (not necessarily attached to any judge), declared in the eval profile and **executed per evaluation alongside the LLM judges** — the current `harness/grounding.py` floor/suppress model (`dosage_grounding` floor, `kb_grounding`/`presence_check` suppress), promoted to a config-plane-authored, standalone entity. *(Impl status, UAP-3b-2 2026-06-05: the **light** surface landed — `EvalProfile.grounding_checks` declares the entities; each execution is audited at the post-consensus locus as its own `actor.type=grounding_check` record [action `run`/`suppress`/`floor_block`], distinct from the gate's `withstand`/`flip`; `ground()`/`composite()` byte-additively-identical for the floor-less `clinical_v1`. A config-plane CRUD UI is a follow-on.)*

### The critique-as-verification gate (Ralph-Loop)
The assigned **ontology rules** (tagged: tier, owner, when/when-NOT, severity) + the executed **validator outputs** together form **signals**. A **Ralph-Loop-like critique** incorporates these signals, and a judge's verdict **stands ONLY IF its reasoning, on the given input, withstands the tagged ontology + contract rules**:
- a judge claim that **contradicts a deterministic validator result** (e.g. the dose IS grounded in the chart, but the judge raised `WRONG_DOSAGE`) is caught and corrected by the critique;
- a judge raise that **violates a tagged ontology rule** (a code outside its assigned lens/owner, or used against its `when_NOT_to_use`) is rejected;
- a judge whose reasoning **survives** the signals is admitted.

This is the **tool-grounded floor generalized into a per-judge critique loop** — and it is precisely what makes a critique *ground* rather than merely self-critique: the `critique-pass-precision-not-floor` spike showed a transcript-only self-critique cannot flip a transcript-only blind spot; **feeding it the ontology + validator signals is what closes that gap.** The deterministic layer can correct the LLM layer (the by-construction-true + record-grounded floor principle), now per-judge and critique-mediated.

### Invariant boundary
All of this lives **above the frozen consensus seam** (`compliance_council._apply_consensus` stays byte-frozen). Validators/grounding remain **deterministic** (no LLM in the floor). The critique can **down-rank or correct** a judge's reasoning but cannot relabel a by-construction case. Compose: judges (`runtime/council`), validators (`verification/`), grounding (`harness/grounding.py`), the critique (the DSPy spike) all exist — **the NET-NEW is the orchestration**: ontology-assignment → refinement questions, the signals bus, and the withstands-gate.

---

## 2B. Auditability — every action is attributed, timestamped, justified (why · when · who · what)

**Non-negotiable product capability.** The system must produce **auditable reports** that answer, for any verdict or any change: **why / when / who / what was acted upon**. In a clinical/regulated domain this *is* the compliance artifact; it is also the **Execution-Integrity** proof and the **RLVR / data-lake** substrate (every correction is a verifiable record). Audit is woven through every entity (§2A) and stage (§3) — never bolted on, never optional.

### The universal record
Every action — authoring OR processing — emits an immutable `AuditRecord`:
```jsonc
AuditRecord {
  "ts":     "<UTC ISO8601>",                              // WHEN
  "actor":  { "type":"user|judge|validator|grounding_check|critique|agent|system",
              "id":"<sme-handle | risk_judge | dosage_grounding | ...>" },  // WHO
  "action": "author|edit|assign|run|raise|suppress|flip|withstand|reject|...",
  "target": { "type":"judge|flag|ontology|agent|case|verdict|finding|validator",
              "id":"<...>" },                              // WHAT (the object acted upon)
  "why":    { /* typed by action — always concrete, never prose-only */ },  // WHY
  "before": { /* authoring edits: the prior state */ },
  "after":  { /* authoring edits: the new state (the diff) */ },
  "run_id": "<...>", "case_id": "<...>"                    // processing context
}
```
`why` is **typed by the action**, so the justification is always grounded:
- **judge raise** → `{ taxonomy_code, decision, reasoning, evidence_spans[], confidence|null }` (the per-judge seam — already emitted).
- **validator execution** → `{ contract_type, conforms, deterministic_result, grounded_fact }`.
- **grounding flip** → `{ from_verdict, to_verdict, grounded_in, the evidence that flipped it }` (the correction/RLVR record, `corpus.py`).
- **critique withstand/reject** → `{ signals_weighed:[ontology_rules, validator_outputs], decision, what_failed }` (the §2A withstands-gate ruling).
- **user authoring edit** → `{ rationale, before→after }` (the SME's change reason).

### Two streams → one report
1. **Authoring audit (config plane).** Every assign/edit/PUT on a judge/flag/ontology/agent → an append-only record: who (the SME), when, the before→after diff, why. **NET-NEW:** the config plane overwrites today (`save_agent` upserts on `name`); it gains an **append-only audit log** + an **actor identity** on every write (the minimal "who" — full multi-tenant auth stays out, but an *attributable handle* is required).
2. **Processing audit / run provenance.** Every eval run = the full chain: each judge's vote+reasoning+evidence, each validator's execution+result, each grounding flip+grounded-fact, the critique's withstands-decisions, the final verdict+why. **EXISTS:** this IS the `SqliteProvenanceStore` blob (WS-6d, the immutable source-of-truth tier; memory `persistence-blob-projection-architecture`) + the correction records (`corpus.py`). **NET-NEW:** surface it as a queryable + human-readable **auditable report**.

The **auditable report** is the projection (the blob+projection architecture's rebuildable query tier) assembling these records:
- *"Why was case X blocked?"* → risk_judge raised `WRONG_DOSAGE` [reasoning + span] @ T; `dosage_grounding` confirmed [grounded fact]; critique: withstood; verdict **BLOCK**.
- *"Who changed `FABRICATED_CONSENT`, when, why?"* → SME `@handle` @ T: severity HIGH→MEDIUM; rationale "…".
- *"Why did the floor flip case Y PASS→BLOCK?"* → the dose was grounded in neither transcript nor chart [the grounded fact].

### Invariant
Audit records are **immutable + append-only**, blob-backed (RLVR/lake-bound); a report is **reconstructable from the blobs** (the projection is rebuildable, never the source of truth). **No action — authoring or processing — escapes a record**; an un-attributed write is a bug, not a silent default. *(As this grows it may spin into its own `SPEC_AUDIT_PROVENANCE.md`; for now it is a first-class section here.)*

---

## 3. The three stages — EXISTS vs NET-NEW

### Stage 1 — Judge creation (the largest gap)

Author a judge = a **role** + an **assigned ontology subset** (whose flags' `JudgeQuestion`s become its **refinement questions** — §2A) + a **model binding** + (optional) **attached persisted validators it executes** (never generates), then **optimize** it against the by-construction corpus. Authoring is **assignment + binding**, not free-text prose.

- **EXISTS:** the runtime — `judges_dspy.py` (`Judge`/`build_trio`, model binding via `build_judge_lm`), `judge_metric.py` (`LENS_BY_ROLE`, `make_judge_metric` + the co-raise-aware lens), `judge_optimize.py` (`compile_judge`/`run_optimize` — the BootstrapFewShot loop, WS-6c-DSPy-3b), the ontology's `JudgeQuestion{role, ordinal, text}` + `questions_for(role)`, the persisted validators (`verification/`), and the critique spike. `SPEC_CALIBRATION_TRAINER.md` is the optimize-step product surface.
- **NET-NEW:**
  1. **A `JudgeEditor` gen-UI widget**: role + **the ontology assignment** (pick the flags/lens this judge owns → its refinement questions auto-derive from `questions_for(role)`) + model deployment + **attached validators** (pick from the persisted set; execute-only). Owner-consistent + snapshot-checked.
  2. **The prompt↔ontology bridge — DECIDED (OQ-1, user 2026-06-04): ontology-as-source via ASSIGNMENT** (§2A). The assigned ontology's `JudgeQuestion`s ARE the judge's refinement questions; the runtime prompt is *rendered from* the assignment — `council_roles/<role>.txt` becomes a render target / retires; UI-authored questions write to the ontology (`questions`), the judge reads them. One source of truth. (Touches safety-critical prose, cf. S-BS-11 — render carefully + keep the byte-parity guard.)
  3. **The signals + critique-gate wiring (§2A)** — a judge's reasoning is checked against its assigned ontology rules + its attached validators' outputs via the Ralph-Loop critique; the verdict stands only if it withstands. (Composes the critique spike + `harness/grounding`; the orchestration is new.)
  4. **BFF judge surface** — `GET /v1/judges` (list role + model + assigned lens + questions + attached validators), `PUT /v1/judges/{role}` (assign + bind; validate owner↔emit + snapshot), `POST /v1/judges/{role}/optimize` (cost-gated `run_optimize` — the calibration trainer; reuses the WS-6c-DSPy-3b smoke→cost-go→one-run protocol). **Gate:** S-BS-49 (the exact-accept gate harvests only silent demos) must be addressed before "optimize" is trusted to *improve* a judge — the UI surfaces the measured held-out Δ honestly, win-or-not.

### Stage 2 — Flag creation (closest to done)

Author a flag = code + category + definition + when/when-NOT + **owner_roles** + **tier** + gradeable + **severity** + **verification_contract** + the **judge questions** that reference it.

- **EXISTS:** `harness/ontology.py` (`FlagDefinition`, `VerificationContractDecl`, `SeverityMap`, `JudgeQuestion`); the gen-UI `FlagEditor` + `ContractBuilder` + `KbPicker` (WS-5c); `PUT /v1/ontology` with round-trip + snapshot-lint validation → **422** on a gradeable-flag-outside-snapshot (WS-5d, clobber-safe working copy at `out/bff/ontology/<agent>.json`).
- **NET-NEW:**
  1. **Close the draft→grade loop (S-BS-26b).** A `PUT /v1/ontology` draft does NOT yet feed a run — `run_eval` reads the committed seed (`run_eval.py:118 agent.ontology_abspath()`), not the working copy. Stage 3's run must read the agent's working-copy ontology so "edit the flag → see it grade" actually holds.
  2. **JudgeQuestion authoring** in the `FlagEditor`/`JudgeEditor` (the per-role questions that cite the flag) — today seeded, not UI-authored.
  3. **Bidirectional snapshot lint (S-BS-12)** surfaced in the UI: not just "gradeable flag outside snapshot" but "snapshot code the runtime stopped tiering" — both must fail loudly at author-time.

### Stage 3 — Processing (net-new UI surface)

Run the authored `Agent` through the engine and return the graded result + grounding flips + calibration.

- **EXISTS:** `run_eval.run(agent, live, in_process)` + `harness/grade.py` (`grade_replay` $0 / `grade_live` :8002 / `grade_inprocess` v2 council); the merged **`dosage_grounding` floor** + **`KbRagTool`** suppress (`dc1cb7c`); `report.composite` + `calibration_check`; the `SqliteProvenanceStore` blob tier (WS-6d); the `corpus`/`evalpack` modules (WS-4a); the display widgets `VerdictCard` + `CalibrationChart`. BFF: `POST /v1/run-eval` (single agent) + `GET /v1/corpus` + `GET /v1/case`.
- **NET-NEW:**
  1. **A `RunPanel` UI** — pick agent + grade-path (replay/live/in-process) + floor/KB toggles + run; not the journey's hardcoded `ws0_default`/`live:false`.
  2. **Eval-pack / batch run** — `POST /v1/eval-pack/run` over a corpus (today only single-case `/v1/run-eval`), folding `report.calibration_check`.
  3. **Run history** — `GET /v1/runs` from the `SqliteProvenanceStore` (the blob tier exists; expose it) → the "did my edit move the number?" loop that Stage 1's optimize closes.
  4. **GATE before any floor/KB ships from a committed ontology:** S-BS-13 (floor-apply replay) + S-BS-16 (floor inject-param validation) + S-BS-41 (`run_eval` threads no `http_client` → `kb_grounding` hits live `:8002` under `--replay`). The UI must not let a floor/KB contract ship past these.
  5. **Execute the §2A entity model per evaluation** — a run fans out the LLM judges AND the standalone **GroundingChecks**, then reconciles the LLM verdict with the deterministic signals via the **withstands-gate** (the Ralph-Loop critique): judge-attached validators run as that judge's signals; independent GroundingChecks run alongside (the `harness/grounding` floor/suppress model, made first-class + config-authored). Building blocks exist (`runtime/council` + `verification/` + `harness/grounding` + the critique spike); the **orchestration is the NET-NEW**.

---

## 4. Data contracts

### Config plane (`harness/config.py`) — the write-target
```jsonc
Agent {
  "name": "ws0_default",
  "eval_profile": {
    "judges": ["risk_judge","policy_judge","faithfulness_judge"],   // tuple[str]
    "council_config": { /* disposition: compose-over-live-v2, S-BS-6 */ },
    "ontology_ref": "clinical_v1", "ontology_path": "data/ontology/clinical_v1.json",
    "tools": ["dosage_grounding", "kb_grounding"],                    // verification contracts
    "kb_bindings": { /* namespace → KB config */ },
    "severity_map_ref": "clinical_v1"
  },
  "dataset": { "case_id": "...", "source": "...", "baseline": "...", "mode": "replay" }
}
```
Persist via `save_agent(agent)` (idempotent upsert on `name`), load via `load_agent(name)`; JSON round-trips through `agent_to_dict`/`agent_from_dict`.

### Ontology (`harness/ontology.py`)
- `FlagDefinition { flag, category, definition, when_to_use, when_NOT_to_use, owner_roles[], tier|null, gradeable=false, reliability_pillar|null }`
- `JudgeQuestion { role, ordinal, text }` · `VerificationContractDecl { flag_code, question, contract_type, params, version }` · `SeverityMap { weights, block_at_or_above, warn_above }`
- `Ontology { ontology_version, domain, flags[], questions[], contracts[], severity_map }` with `gradeable_flags()` / `is_gradeable()` / `owners_of()` / `contract_for()` / `questions_for(role)`.

### BFF surface (`apps/bff/app.py`)
| Route | State | Stage |
|---|---|---|
| `POST /v1/run-eval {agent,live,in_process}` · `GET /v1/case` · `GET /v1/corpus` · `GET /v1/ontology` · `PUT /v1/ontology` · `GET /v1/kb/{namespace}/search` · `GET /health` | **EXISTS** | 2,3 |
| `GET /v1/judges` · `PUT /v1/judges/{role}` · `POST /v1/judges/{role}/optimize` | **NET-NEW** | 1 |
| `GET /v1/agent` · `PUT /v1/agent` (save/load the assembled `Agent`) | **NET-NEW** | all |
| `POST /v1/eval-pack/run` · `GET /v1/runs` (history from `SqliteProvenanceStore`) | **NET-NEW** | 3 |
| `GET /v1/runs/{id}/audit` · `GET /v1/audit?actor=&target=&since=` · actor-attributed + audit-logged config writes | **NET-NEW** | all (§2B) |

All new write routes follow the WS-5d `PUT /v1/ontology` precedent: validate (round-trip + snapshot/owner lint) → **422** on violation, write a **clobber-safe working copy** (never the committed seed), prefer the working copy on read.

### gen-UI registry (`apps/shell/src/genui/registry.js`)
The `tool-<name>` → component contract (WS-5c). Add `JudgeEditor` + `RunPanel`; `FlagEditor`/`ContractBuilder`/`KbPicker`/`VerdictCard`/`CalibrationChart` exist.

---

## 5. Requirements

### P0 — Must have (the loop closes)
- **R0 — audit (non-negotiable, cross-cutting):** every authoring + processing action emits an immutable `AuditRecord` (why/when/who/what, §2B); the config plane gains an append-only audit log + actor attribution; `GET /v1/runs/{id}/audit` + `GET /v1/audit` surface the reports. Built incrementally across UAP-1..4, but the **record shape + actor model land in UAP-1** — nothing is authored un-attributed from day one.
- **R1** `PUT/GET /v1/agent` — assemble + persist an `Agent` (judges + ontology + tools + kb) to the config plane from the UI.
- **R2** `JudgeEditor` + `GET/PUT /v1/judges/{role}` — author a judge (role, questions, model, lens) with owner↔emit + snapshot validation; resolve the prompt↔ontology bridge (§3.1.2).
- **R3** Stage-2 draft→grade loop (S-BS-26b) — a run reads the agent's working-copy ontology, so an authored flag/judge actually grades.
- **R4** `RunPanel` + Stage-3 processing over the authored agent (replay default; live/in-process opt-in, cost-gated).

### P1 — Should have (the loop is useful)
- **R5** `POST /v1/judges/{role}/optimize` — the calibration trainer (judge_optimize) in the UI, honest held-out Δ; **gated on S-BS-49**.
- **R6** `POST /v1/eval-pack/run` + `GET /v1/runs` — batch processing + run history (the "did it move the number?" loop).
- **R7** JudgeQuestion authoring + bidirectional snapshot lint (S-BS-12) in the UI.

### P2 — Nice to have
- **R8** Corpus authoring (`POST /v1/corpus`) — import/author by-construction cases from the UI (today CLI `generate_*`).
- **R9** Diff/version view of an ontology or judge across runs.

### P3 — Conversational surface (ADDITIVE 2026-06-04 — surface-only; does NOT alter R0–R9, §2A, §2B, or §4)
- **R10 — authoring-assist (describe→draft):** a structured-generation provider (a vendored `LLMClient` à la `../zyng/zyng/authoring.py` — a forced-tool `emit() -> dict` + a local-`claude`-CLI / API / offline-stub factory) behind `POST /v1/author/{kind}`: an NL description → a schema-valid `Agent`/judge/flag/contract **draft**, rendered as the *existing* §4 gen-UI `tool-*` card; the normal audited `PUT` path persists it. Single-shot (not a conversation); $0 on the local CLI; reuses zyng wholesale. Serves the "judge creation must be demonstrable" bar.
- **R11 — conversational shell (the agent loop):** the **Claude Agent SDK** hosted in the BFF; the §4 BFF ops exposed as in-process SDK-MCP tools (= the "tools registry"); `ClaudeSDKClient` driving a multi-turn author→process→review loop, streamed (SSE) to a shell chat pane; tool-results adapted to the §4 gen-UI message-parts the registry already renders. Every tool-call is a config write → already audited (R0): **the conversation IS the audit log.**

---

## 6. Invariants preserved (CLAUDE.md — non-negotiable)
- **Labels true by construction.** The corpus/cases remain recipe=label; the UI authors *judges and flags*, never silently relabels a case. Optimize reports the measured Δ; no tuning-to-win.
- **Snapshot = the taxonomy contract.** Every *gradeable* flag is in `taxonomy/taxonomy_snapshot.json` with a tier + a production-resident owner (invariants #1/#4). The gradeable/reference partition (S-BS-10) and owner↔emit (S-BS-31 — an owner must actually emit the code, S-BS-42) are author-time gates, surfaced as **422**, never soft-passed.
- **Frozen consensus seam.** Authoring lives strictly ABOVE the per-judge seam; `compliance_council._apply_consensus` stays byte-frozen (the whole DSPy track's A1).
- **No services autostarted; cost-gated live runs; offline/$0 default** (replay).
- **Every action is recorded; audit records are immutable + append-only** (blob-backed, RLVR/lake-bound). No authoring or processing action escapes an attributed, timestamped, justified record (§2B); an un-attributed write is a bug, not a silent default.

---

## 7. Proposed phasing (build sequence — reframed WS-7)
- **WS-7a** ✅ (the journey Verify beachhead — now the frozen demo's live act).
- **UAP-1 / R1+R3** — the config-plane write-path (`/v1/agent`) + the draft→grade loop. Smallest change that makes authored config actually run.
- **UAP-2 / R2** — `JudgeEditor` + `/v1/judges` via **ontology-assignment** (OQ-1 decided: a judge's refinement questions derive from its assigned flags) + attached-validator selection. The headline gap.
- **UAP-3 / R4+R6** — `RunPanel` + processing/eval-pack/history surface.
- **UAP-3b / §2A** — the **signals + withstands-gate** orchestration: run independent GroundingChecks alongside the judges + the Ralph-Loop critique reconciling LLM reasoning with the ontology+validator signals (locus per OQ-4). The new entity-model orchestration — the moat made operational.
- **UAP-4 / R5** — the optimize/calibration loop in the UI (after S-BS-49). Realizes `SPEC_CALIBRATION_TRAINER.md`.
- **UAP-5a / R10** — authoring-assist (describe→draft), reusing the zyng `LLMClient` pattern (§13). Rides on the UAP-2 judge/flag endpoints; **sequenced after UAP-3b** (moat before polish) but independent enough to pull forward after UAP-2 for a $0 demonstrability win.
- **UAP-5b / R11** — the conversational shell (Claude Agent SDK over the tool registry, §13). The capstone — **after UAP-3b/UAP-4**, when the tool surface (author + run + withstands signals) is complete enough for a multi-turn loop to earn its keep.
Each is a HARD-GATE-class shell phase (SPEC §8) with the `:5180` visual smoke as the load-bearing gate, and pathspec-only commits (the shared-branch discipline).

---

## 8. Non-goals
- **Journey rework** (frozen; demo-only — improvements ride the product, not standalone).
- **Tauri / VPC packaging** (the genuine last mile — WS-5e; deferred per the 2026-06-02 ship decision). But honor the indirection now (**S-BS-50**: route fetches through `bff.js`'s `VITE_BFF_URL`, don't hardcode `:8787`).
- **New `../lithrim-backend` endpoints** — compose over the existing `:8002`/`:3031` via the BFF + the in-process council (strangler-fig).
- **Full multi-tenant auth / SSO** beyond the existing BFF scheme. *But a minimal **actor attribution** — an SME handle on every write (the audit "who", §2B) — is IN scope; auditability requires it.*

## 9. Test plan
- Per-stage Vitest+RTL (the WS-5c/5d `bff.js`-mock + the WS-7a `JourneyApp.test.jsx` pattern): authoring a judge/flag → the right `PUT` body; a run → the real composite renders; 422 on an invalid (snapshot/owner) author.
- Python: `/v1/agent` + `/v1/judges` round-trips (the `tests/test_ws5_bff.py` direct-handler pattern — S-BS-40 gates `TestClient` on debuglithrim).
- e2e (user-run, no-autostart): author a flag + a judge in the UI → run → see it grade → optimize → see the Δ. The `:5180` smoke per phase.

## 10. Success metrics
- An SME stands up a **new domain ontology + judge trio + one processing run** entirely in the UI, zero file edits. (the "who calibrates?" gap closed)
- Author→grade latency: a flag/judge edit is reflected in a replay grade in one click ($0).
- Zero invariant escapes: no gradeable flag ships without snapshot+owner (422 enforced), no judge owns a code it doesn't emit.
- **Full auditability:** any verdict or config change is reconstructable as a why/when/who/what report from the immutable records — zero un-attributed actions.

## 11. Dependencies + cross-refs
- `SPEC_PRODUCT_SHELL.md` §2/§8/§10 (shell + the locked v1 BFF surface — §10 must be **extended/ratified** to admit the new routes; cf. **S-BS-51** where the journey grew it unratified) · `SPEC_CALIBRATION_TRAINER.md` (Stage-1 optimize) · `SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (service plane).
- Config plane `harness/config.py` · ontology `harness/ontology.py` · DSPy `runtime/council/{judges_dspy,judge_optimize,judge_metric}.py` · grounding `harness/grounding.py` + `verification/tools.py` (floor + KB, `dc1cb7c`).
- Open seams that gate stages: **S-BS-49** (optimize, R5) · **S-BS-13/16/41** (floor/KB ship, Stage 3) · **S-BS-26b** (draft→grade, R3) · **S-BS-12** (bidirectional lint, R7) · **S-BS-50/51** (journey-BFF hardcode + §10 surface).

## 12. Decisions (resolved at lock — 2026-06-04)
1. **Prompt↔ontology bridge → ontology-as-source via ASSIGNMENT.** A judge's refinement questions are *formed by assigning ontology flags to it*; the runtime prompt renders from the assignment; `council_roles/*.txt` becomes a render target / retires. Judges **execute** persisted validators, never generate them.
2. **Judge = (assignment + model + validator-refs); the ontology owns the questions.** A thin `/v1/judges` **writes through** to the ontology (`questions`) + a small judge-config row (model + assigned-lens + attached-validator refs). One source of truth.
3. **Optimize MEASURES; the user chooses adoption.** Per S-BS-48, never auto-ship a negative-Δ judge — the UI surfaces the held-out Δ honestly and the user adopts explicitly.
4. **Withstands-gate locus = BOTH.** The per-judge Ralph-Loop critique is the new **primary** gate over the LLM judges (a pre-consensus stage); the existing post-consensus `harness/grounding` serves the **independent** GroundingChecks. Both sit ABOVE the frozen `_apply_consensus`; the precise pre-consensus wiring is detailed at UAP-3b design.
5. **Confirmed scoping:** "assign ontology" = a **flag subset** per judge; the audit "who" = a single attributable **SME handle** for now (full multi-tenant auth deferred, §8).

---

## 13. Conversational-driver surface — ADDITIVE AMENDMENT (2026-06-04)

> **Additive + surface-only.** This section adds a *delivery surface* (how an SME drives the product) plus a **gated, post-moat** phase pair (UAP-5a/5b). It does **not** modify the locked content — the entity model (§2A), the withstands-gate, auditability (§2B), the data contracts (§4), or R0–R5. The lock holds; this is appended, not re-opened.

**Why it fits without disruption.** The product is already a *tools surface* (§4 BFF ops) + an *output surface* (§4 gen-UI registry — the Vercel AI-SDK `tool-<name>` message-parts shape, explicitly built so "a live chat host can layer on later"). The conversational layer is the **driver** that connects an utterance → those tools → those cards. It is a layer OVER what UAP-1..4 build, not a step that reorders them — and it grows in value as each UAP phase adds tools. Hence the founder's gate: *"once the tools registry is up."*

**Two tiers (→ R10/R11 → UAP-5a/5b):**
- **Tier 1 / R10 / UAP-5a — authoring-assist.** Reuse the proven `../zyng/zyng/authoring.py` provider pattern (the `LLMClient` Protocol + `ClaudeCliClient` local-CLI provider + the dev-CLI/prod-API/offline-stub `_BRAINS` factory). One forced-tool `emit()` per authoring kind → a schema-valid draft → the existing gen-UI card → the normal audited `PUT`. Single-shot, $0 on the local CLI, reuses zyng wholesale.
- **Tier 2 / R11 / UAP-5b — conversational shell.** The **Claude Agent SDK** in the BFF; §4 BFF ops wrapped as in-process SDK-MCP tools (the "tools registry"); `ClaudeSDKClient` → a multi-turn author→process→review loop → SSE → a shell chat pane; tool-results adapted to the §4 registry parts. The capstone — after the moat.

**Sequencing rule:** the conversational surface sits **after the withstands-gate (UAP-3b), not before it** — the moat is the differentiator; chat is adoption polish over an already-complete, click-driven product. UAP-5a *may* pull forward after UAP-2 for a cheap demonstrability win, but neither phase precedes UAP-3b by default, and neither disturbs the in-flight UAP-2 cycle (UAP-2 stays deterministic + LLM-free).

**OQ-6 (OPEN — the one decision this surface needs).** *Where does the agent loop run?* **(B)** Python Agent SDK in the BFF — in-process, offline, BYO-Claude on desktop, reuses the Python harness/council; cost = a parts-adapter + an SSE endpoint + a new `[agent]` extra → **monitor lean, on-thesis**; vs **(A)** a TS Vercel-AI-SDK / assistant-ui host in the shell — native parts, no adapter; cost = a second JS runtime + pushes toward API keys, and the local-CLI provider doesn't fit cleanly. Resolve at UAP-5b design.

**Licensing guardrail (non-negotiable — from the zyng `ClaudeCliClient` docstring).** A personal Claude Pro/Max subscription via the local CLI is **local/desktop/BYO-Claude only — it cannot license a multi-tenant backend.** Desktop bring-your-own-Claude is legit and on-thesis (no-hosted-surface, no trial-expiry); any hosted/multi-tenant path uses per-tenant API keys or the customer's Bedrock/Vertex/VPC. Consistent with §8 (actor attribution in; full multi-tenant auth out).

**Cross-refs.** Reuse target `../zyng/zyng/authoring.py` (memory `zyng-claude-cli-provider`) · the demonstrability bar (memory `judge-creation-must-be-demonstrable`) · §4 registry contract + §10 BFF-surface ratification — the new routes (`POST /v1/author/{kind}` + the SSE chat endpoint) must be **ratified into `SPEC_PRODUCT_SHELL.md` §10**, not grown unratified (the S-BS-51 pattern).
