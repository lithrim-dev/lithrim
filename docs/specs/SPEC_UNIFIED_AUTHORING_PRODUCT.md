# SPEC: Unified Authoring + Processing Product
> The complete product is the UI-driven **author → process** loop over the config plane: **create judges → create flags → run processing**, all from the UI. The 4-act journey is a **frozen** pitch/onboarding demo *inside* this product. **Compose, don't rebuild** — the engine, the config plane, the BFF, the shell, and the gen-UI widgets already exist; this spec wires them into one operational product.

**Status:** DRAFT · **Authored:** 2026-06-04 · **Owner:** monitor (bench-salvage)
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
- **GroundingCheck.** A first-class **INDEPENDENT** entity (not necessarily attached to any judge), declared in the eval profile and **executed per evaluation alongside the LLM judges** — the current `harness/grounding.py` floor/suppress model (`dosage_grounding` floor, `kb_grounding`/`presence_check` suppress), promoted to a config-plane-authored, standalone entity.

### The critique-as-verification gate (Ralph-Loop)
The assigned **ontology rules** (tagged: tier, owner, when/when-NOT, severity) + the executed **validator outputs** together form **signals**. A **Ralph-Loop-like critique** incorporates these signals, and a judge's verdict **stands ONLY IF its reasoning, on the given input, withstands the tagged ontology + contract rules**:
- a judge claim that **contradicts a deterministic validator result** (e.g. the dose IS grounded in the chart, but the judge raised `WRONG_DOSAGE`) is caught and corrected by the critique;
- a judge raise that **violates a tagged ontology rule** (a code outside its assigned lens/owner, or used against its `when_NOT_to_use`) is rejected;
- a judge whose reasoning **survives** the signals is admitted.

This is the **tool-grounded floor generalized into a per-judge critique loop** — and it is precisely what makes a critique *ground* rather than merely self-critique: the `critique-pass-precision-not-floor` spike showed a transcript-only self-critique cannot flip a transcript-only blind spot; **feeding it the ontology + validator signals is what closes that gap.** The deterministic layer can correct the LLM layer (the by-construction-true + record-grounded floor principle), now per-judge and critique-mediated.

### Invariant boundary
All of this lives **above the frozen consensus seam** (`compliance_council._apply_consensus` stays byte-frozen). Validators/grounding remain **deterministic** (no LLM in the floor). The critique can **down-rank or correct** a judge's reasoning but cannot relabel a by-construction case. Compose: judges (`runtime/council`), validators (`verification/`), grounding (`harness/grounding.py`), the critique (the DSPy spike) all exist — **the NET-NEW is the orchestration**: ontology-assignment → refinement questions, the signals bus, and the withstands-gate.

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

All new write routes follow the WS-5d `PUT /v1/ontology` precedent: validate (round-trip + snapshot/owner lint) → **422** on violation, write a **clobber-safe working copy** (never the committed seed), prefer the working copy on read.

### gen-UI registry (`apps/shell/src/genui/registry.js`)
The `tool-<name>` → component contract (WS-5c). Add `JudgeEditor` + `RunPanel`; `FlagEditor`/`ContractBuilder`/`KbPicker`/`VerdictCard`/`CalibrationChart` exist.

---

## 5. Requirements

### P0 — Must have (the loop closes)
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

---

## 6. Invariants preserved (CLAUDE.md — non-negotiable)
- **Labels true by construction.** The corpus/cases remain recipe=label; the UI authors *judges and flags*, never silently relabels a case. Optimize reports the measured Δ; no tuning-to-win.
- **Snapshot = the taxonomy contract.** Every *gradeable* flag is in `taxonomy/taxonomy_snapshot.json` with a tier + a production-resident owner (invariants #1/#4). The gradeable/reference partition (S-BS-10) and owner↔emit (S-BS-31 — an owner must actually emit the code, S-BS-42) are author-time gates, surfaced as **422**, never soft-passed.
- **Frozen consensus seam.** Authoring lives strictly ABOVE the per-judge seam; `compliance_council._apply_consensus` stays byte-frozen (the whole DSPy track's A1).
- **No services autostarted; cost-gated live runs; offline/$0 default** (replay).

---

## 7. Proposed phasing (build sequence — reframed WS-7)
- **WS-7a** ✅ (the journey Verify beachhead — now the frozen demo's live act).
- **UAP-1 / R1+R3** — the config-plane write-path (`/v1/agent`) + the draft→grade loop. Smallest change that makes authored config actually run.
- **UAP-2 / R2** — `JudgeEditor` + `/v1/judges` via **ontology-assignment** (OQ-1 decided: a judge's refinement questions derive from its assigned flags) + attached-validator selection. The headline gap.
- **UAP-3 / R4+R6** — `RunPanel` + processing/eval-pack/history surface.
- **UAP-3b / §2A** — the **signals + withstands-gate** orchestration: run independent GroundingChecks alongside the judges + the Ralph-Loop critique reconciling LLM reasoning with the ontology+validator signals (locus per OQ-4). The new entity-model orchestration — the moat made operational.
- **UAP-4 / R5** — the optimize/calibration loop in the UI (after S-BS-49). Realizes `SPEC_CALIBRATION_TRAINER.md`.
Each is a HARD-GATE-class shell phase (SPEC §8) with the `:5180` visual smoke as the load-bearing gate, and pathspec-only commits (the shared-branch discipline).

---

## 8. Non-goals
- **Journey rework** (frozen; demo-only — improvements ride the product, not standalone).
- **Tauri / VPC packaging** (the genuine last mile — WS-5e; deferred per the 2026-06-02 ship decision). But honor the indirection now (**S-BS-50**: route fetches through `bff.js`'s `VITE_BFF_URL`, don't hardcode `:8787`).
- **New `../lithrim-backend` endpoints** — compose over the existing `:8002`/`:3031` via the BFF + the in-process council (strangler-fig).
- **Multi-tenant / auth** beyond the existing BFF scheme.

## 9. Test plan
- Per-stage Vitest+RTL (the WS-5c/5d `bff.js`-mock + the WS-7a `JourneyApp.test.jsx` pattern): authoring a judge/flag → the right `PUT` body; a run → the real composite renders; 422 on an invalid (snapshot/owner) author.
- Python: `/v1/agent` + `/v1/judges` round-trips (the `tests/test_ws5_bff.py` direct-handler pattern — S-BS-40 gates `TestClient` on debuglithrim).
- e2e (user-run, no-autostart): author a flag + a judge in the UI → run → see it grade → optimize → see the Δ. The `:5180` smoke per phase.

## 10. Success metrics
- An SME stands up a **new domain ontology + judge trio + one processing run** entirely in the UI, zero file edits. (the "who calibrates?" gap closed)
- Author→grade latency: a flag/judge edit is reflected in a replay grade in one click ($0).
- Zero invariant escapes: no gradeable flag ships without snapshot+owner (422 enforced), no judge owns a code it doesn't emit.

## 11. Dependencies + cross-refs
- `SPEC_PRODUCT_SHELL.md` §2/§8/§10 (shell + the locked v1 BFF surface — §10 must be **extended/ratified** to admit the new routes; cf. **S-BS-51** where the journey grew it unratified) · `SPEC_CALIBRATION_TRAINER.md` (Stage-1 optimize) · `SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (service plane).
- Config plane `harness/config.py` · ontology `harness/ontology.py` · DSPy `runtime/council/{judges_dspy,judge_optimize,judge_metric}.py` · grounding `harness/grounding.py` + `verification/tools.py` (floor + KB, `dc1cb7c`).
- Open seams that gate stages: **S-BS-49** (optimize, R5) · **S-BS-13/16/41** (floor/KB ship, Stage 3) · **S-BS-26b** (draft→grade, R3) · **S-BS-12** (bidirectional lint, R7) · **S-BS-50/51** (journey-BFF hardcode + §10 surface).

## 12. Open questions (+ resolutions)
1. ~~The prompt↔ontology bridge~~ — **RESOLVED (user 2026-06-04; §2A + §3.1.2): ontology-as-source via ASSIGNMENT.** A judge's refinement questions are *formed by assigning ontology flags to it*; the runtime prompt renders from the assignment; `council_roles/*.txt` becomes a render target / retires. Judges **execute** persisted validators, never generate them.
2. **Judge persistence — converging:** the assignment model implies a thin `/v1/judges` that **writes through** to the ontology (`questions`) + a small judge-config row (model + assigned-lens + attached-validator refs). Confirm: a judge = (assignment + model + validator-refs), with the ontology owning the questions? (Recommended — one source of truth.)
3. **Does "optimize" ship the demos** or only measure? Per S-BS-48, bind-back-by-default is its own decision; the UI measures + lets the user *choose* to adopt, never auto-ships a negative-Δ judge.
4. **The withstands-gate's locus (§2A) — needs your call.** Is the Ralph-Loop critique applied **per-judge** (gate each judge's reasoning *before* consensus) or **post-consensus** (verdict-level, as `harness/grounding` does today), or both? Your wording ("the judge's reasoning withstands") reads **per-judge**; today's grounding is post-consensus. Both compose — but the locus sets where the new orchestration sits relative to the **frozen** `_apply_consensus` (a per-judge gate is a new pre-consensus stage; a verdict-level gate is the existing post-consensus grounding generalized).
