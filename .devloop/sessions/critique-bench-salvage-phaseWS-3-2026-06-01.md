# Spec-Adherence Critique — `bench-salvage` phase `WS-3`

> Fresh-critic mode (HARD GATE). Cold read of spec + working-tree diff, formed
> independently of the executor's session log (read last, to cross-check only).

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-3` (WS-3a scope: generator core + harness/grounding wiring; KB/ONNX deferred to WS-3b)
- **Driver bundle:** `bench-salvage-phaseWS-3-dspy-jute-validator-generator-driver`
- **Commits audited:** **NONE — working tree** (HARD GATE: all changes staged, not committed; close precedes commit)
- **Spec(s) read against:** `.devloop/prompts/bench-salvage_phaseWS-3_dspy_jute_validator_generator_driver.md` §2 (D0–D4) + §4 (scope) + §5 (A1–A5); `CLAUDE.md` §"Core invariant" / §"What this repo is NOT" / §"Stack"; `lithrim_bench/harness/grounding.py` pre-WS-3 (`git show HEAD:…`)
- **Critique mode:** `fresh-critic`
- **Date:** 2026-06-01
- **Reviewer:** `critic session (fresh)`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

WS-3a implements the spec faithfully: the structural floor flips PASS→BLOCK on a bench-accepted contract the council missed, backward-compat is functionally demonstrated (no-HTTP + verdict/partitions identical + `floor_blocks==[]`), and A1/A4 I re-verified independently (import isolation clean on default deps; all three packs regenerate `diff==0`). Every deviation from the driver's literal citations is a documented, monitor-approved plan-review decision and is **more faithful to the code than the driver's self-flagged-unstable citations**. The findings below are non-blocking notes and open questions for the spec author — no BLOCKING drift. Cycle MAY close.

---

## 1. Surface fidelity

The driver's §1 citation table was authored in an unstable session and explicitly demanded re-grep. The three "cited symbol does not exist / wrong shape" cases were all caught at plan-review and resolved; I confirm each resolution against the code.

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| Driver D2:155 "Add a `structural_jute` (and `jute_gen`) executor **to `_CONTRACT_EXECUTORS`**" | `grounding.py:189` `_FLOOR_CONTRACT_TYPES = {"structural_jute","jute_gen"}` — a **sibling** registry + `_run_floor`, NOT added to `_CONTRACT_EXECUTORS` | Deviation — **documented** (Decision 2, APPROVED-AT-PLAN, session log:40–43) | NON-BLOCKING |
| Driver D2:168 "Log the flip via `correction.build_correction`" | `correction.py:91` `build_floor_correction` — a **new sibling** (inverse rollout); `build_correction` left suppress-shaped | Deviation — **documented** (Decision 6 + citation-drift, log:27–38) | NON-BLOCKING |
| Driver D2:169 "surface it in `report.build_report`" | `report.py` `composite()` (`build_report` **does not exist** anywhere — confirmed `grep`); floor surfaced via `composite()` `floor_adjustments`/`floor_block_count` | Deviation — **documented** (citation-drift, log:21–26) | NON-BLOCKING |
| Driver D2:177 "Export the new symbols from `harness/__init__.py`" | `harness/__init__.py:15–38` exports the **full harness surface** (ground, GroundedResult, grade_*, build_correction, composite, calibration, …), not just the new floor symbols | Broader than "the new symbols," but file was docstring-only pre-WS-3 (driver §1:91) and driver says "add exports" | NON-BLOCKING |
| Spike `__init__` "must drop the `KbRagTool` import" (driver §1:106) | `verification/__init__.py` drops `KbRagTool` class import/export ✓ — but **retains** `TOOL_KB_RAG` constant (`spec.py:31`) + the `kb_rag` entry in `_REQUIRED_REFERENCE_KEYS` (`spec.py:43`) | Class dropped (the load-bearing isolation fix); dangling constant with no tool behind it | NON-BLOCKING |

**Findings:**

- `[NON-BLOCKING]` The three citation drifts (Decisions resolving them at session log:14–50) are correctly resolved and the resulting surface (`build_floor_correction`, `_FLOOR_CONTRACT_TYPES`, `composite().floor_*`) is internally consistent. No unauthorized surface drift detected.
- `[NON-BLOCKING]` `TOOL_KB_RAG` (`spec.py:31`) and its `_REQUIRED_REFERENCE_KEYS["kb_rag"]` entry (`spec.py:43`) remain exported (`verification/__init__.py:67`) although `KbRagTool` is deferred to WS-3b. Harmless (a string constant), but it advertises a tool the WS-3a surface cannot construct. Suggest a one-line note or deferral to WS-3b alongside the tool.

---

## 2. Behavioral fidelity

### Behavior 1: structural floor flips a confident PASS → BLOCK

- **Spec assertion:** Driver §5 A3 (:270) — "a bench-accepted contract flips a council PASS → BLOCK, flip logged + correction emitted"; D2 (:164–:169).
- **Test:** `tests/verification/test_grounding_floor.py:154` `test_floor_flips_pass_to_block_and_emits_correction` — faked `jute_gen` floor (`_ReplayHttp(checks=_FAIL)`) over a `COUNCIL_PASS` result; asserts `g.original_verdict=="PASS" and g.verdict=="BLOCK"`, `FHIR_STRUCTURAL_VIOLATION` in `g.active`, `composite()["verdict"]=="reject"`, and `build_floor_correction(...)` → `ws3-floor-correction/1` with the PASS vote retained.
- **Implementation:** `grounding.py:354–366` — on `vr.conforms is False`, injects `{code, severity, _floor:True}` into `active`; `severity_map.rescore` (`ontology.py:86`) lifts `HIGH`→weight 1.0 ≥ `block_at_or_above` 1.0 → `BLOCK`. Correction at `correction.py:91`.
- **Chain closes?** **YES.** Independently traced: injected `severity:"HIGH"` → `weight_of` 1.0 → BLOCK; the test's severity_map sets `block_at_or_above:1.0`.

### Behavior 2: backward-compat — no floor declared ⇒ identical to pre-WS-3 `ground()`

- **Spec assertion:** Driver §5 A3 (:270) — "`structural_contracts=None` is **byte-identical** to current `ground()`"; D2 (:182).
- **Test:** `test_grounding_floor.py:201` `test_backward_compat_default_ontology_has_no_floor` — loads the committed clinical ontology, asserts it declares **0** floor contracts, then `ground(..., http_client=_BoomHttp())` asserts `floor_blocks==[]` and `verdict=="PASS"`; `_BoomHttp` raises on any HTTP call (proves the floor path is never entered).
- **Implementation:** `grounding.py:304` partitions `floor_decls` (empty for clinical_v1) → the floor loop (`:350`) is a no-op; `floor_blocks` defaults `[]` (`GroundedResult` field `:84`).
- **Chain closes?** **PARTIAL.** The functional claim is fully demonstrated (no HTTP, verdict + active/suppressed/ungrounded/skipped partitions unchanged, `floor_blocks==[]`). The **literal** "byte-identical" is not strictly true: `GroundedResult` gained a `floor_blocks` field (changes `repr`), and downstream `composite()` (`report.py`) now always emits `floor_adjustments:[]` + `floor_block_count:0`, and `run_eval.py:73` always emits a `floor_blocks` key. The plan-review **refinement #1** (log:46–49) explicitly re-operationalized A3 as "pre-existing fields + verdict identical AND `floor_blocks==[]`" — i.e. the executor narrowed "byte-identical" to additive-compatibility, with monitor approval. See Q4 Ambiguity 1.

### Behavior 3: inconclusive floor is surfaced but NEVER flips (false-negative guardrail)

- **Spec assertion:** Driver D2 / `spec.py:8–14` — `conforms is None` → "the flag stays OPEN (never cleared)"; for the floor, inconclusive must not flip the verdict.
- **Test:** `test_grounding_floor.py:187` `test_floor_inconclusive_never_flips` — uncompiled template (`compiled=False`) → `conforms None`; asserts `verdict=="PASS"`, one `floor_blocks` entry with `injected_finding is None`, `composite()["floor_block_count"]==0`.
- **Implementation:** `grounding.py:367–369` — `elif vr.conforms is None:` records the block with `injected_finding=None` and injects nothing into `active`. `jute_gen` returns `conforms=None` on non-compile (`jute_gen.py:102–111`).
- **Chain closes?** **YES.**

**Findings:**

- `[NON-BLOCKING]` Behavior 2: the literal word "byte-identical" (driver:270) is not met for `GroundedResult.repr` / `composite()` / `run_eval` output (each gains inert floor keys). The intended additive-compatibility IS met and IS what refinement #1 (approved) requires. Flagged so the spec author can lock the precise wording (Q4-1).

---

## 3. Out-of-scope intrusion

Driver deliverables (verbatim §2): **D0** promote core module (guarded imports, KB deferred); **D1** `[verification]` extra; **D2** wire structural floor into `harness/grounding.py` (+ ontology decl + `correction`/`report` surfacing + `harness/__init__` exports); **D3** oracle packs + pinned validator + README; **D4** offline core tests.

Working-tree diff (`git status --short` + untracked dirs):

```
 M lithrim_bench/harness/__init__.py     # D2 (exports)
 M lithrim_bench/harness/correction.py   # D2 (build_floor_correction)
 M lithrim_bench/harness/grounding.py    # D2 (floor wiring)  <-- headline
 M lithrim_bench/harness/report.py       # D2 (composite floor surfacing)
 M pyproject.toml                        # D1 ([verification] extra)
 M scripts/run_eval.py                   # <-- NOT named in the §2 deliverables file-list
?? lithrim_bench/verification/           # D0 (core module)
?? data/verification_packs/              # D3 (packs + README)
?? validators/fhir_us_core_patient_validator.generated.jute  # D3
?? scripts/build_{fhir_observation,fhir_patient,transaction}_pack.py  # D3
?? tests/verification/                   # D4
?? .devloop/sessions/session-…WS-3-2026-06-01.json  # session log (process artifact)
?? .claude/                              # tooling worktree (not a code change)
```

**Findings:**

- `[NON-BLOCKING]` `scripts/run_eval.py` (`:38–42`, `:73–86`, `:140–151`) is modified but is **not** in the §2 deliverable file-list (the wiring site driver §1:68 lists `harness/{grounding,ontology,grade,correction,report,__init__}` only). The change is in-scope **by necessity** — D2 requires the flip to be "logged via correction"; `run_eval` is the orchestrator that calls `ground()`→`composite()`→`emit()`, so without it the floor correction is never emitted in the actual eval run. The change is faithful to D2's intent. **However it introduced seam S-BS-13** (next finding). Map: D2.
- `[NON-BLOCKING]` `run_eval.py:140–151` emits floor corrections but calls `ground(result, case, ontology=ontology)` with **no `http_client`** (`:137` region) → a declared floor would use the **live `:3031`** path even under `--replay`. This is **S-BS-13** (log:99–108, severity medium, CONFIRMED), and contradicts driver Decision 4 (:236, "Apply is replay-able offline … tests use the replay path"). It is **inert today** (clinical_v1 declares no floor) and the *test* path is fully offline (injects the fake), so A3 is satisfied; but the eval-runner offline-replay leg the driver's Decision 4 envisioned is not wired. Correctly logged as a seam for WS-4. See Q4-2.
- `[NON-BLOCKING]` `verification/tools.py:352–355` `_MODELS_DIR` comment ("this file is `<spike>/verification/tools.py`") and the `:13–20` "WIRE CONTRACT NOTE" are spike-relative doc comments carried over verbatim; `_MODELS_DIR` now resolves to `lithrim_bench/models` (one level up from `verification/`). `RecordRagTool` is promoted (driver §1:101) but unused by the floor path and its deps are lazy, so this is cosmetic/stale-doc only. No functional intrusion.
- No drive-by formatting passes, no dependency bumps to `dependencies`, no `runtime/` import, no spike-throwaway swept in (verified: no `council_*.py`/`critique.py`/`run_smoke*` under `lithrim_bench/verification/`). `pyproject.toml` adds only the `[verification]` extra. Clean against §4 guardrails.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: what "byte-identical" means for the backward-compat guarantee

- **Spec text:** Driver §5 A3 (:270) "`structural_contracts=None` is **byte-identical** to current `ground()`."
- **Implementation decided:** Additive-compatibility — a new defaulted `floor_blocks=[]` field on `GroundedResult` (`grounding.py:84`) + always-present inert floor keys in `composite()`/`run_eval`. Re-operationalized at plan-review (refinement #1, log:46–49) as "pre-existing fields + verdict identical AND `floor_blocks==[]`."
- **Alternatives also spec-compliant:** (a) literal byte-identity — gate `floor_blocks` behind a `getattr`-only optional attribute, no field, no `composite()` key when empty; (b) accept additive-compat as the definition (current).
- **Question for spec author:** Is additive-compat (new defaulted field + inert empty floor keys) the intended reading of "byte-identical," or do you want the strict no-new-field/no-new-key reading for the no-floor default path?
- **Recommended resolution:** **Accept** the additive reading (it's the conventional one and breaks no caller — `composite()` uses `getattr(..., "floor_blocks", [])` at `report.py`), and **update the driver wording** from "byte-identical" → "additively backward-compatible: pre-existing fields + verdict identical, `floor_blocks==[]`."

### Ambiguity 2: offline replay for the floor apply in the eval runner (S-BS-13)

- **Spec text:** Driver Decision 4 (:236) "Apply is replay-able offline — mirror `grade_replay`/`grade_live`; tests use the replay path, the live smoke uses the live path."
- **Implementation decided:** `ground()` supports injection (`http_client=`, `grounding.py:280`) and the tests use it; but `run_eval.run()` passes no client → a declared floor hits live `:3031` even under `--replay`. Logged as S-BS-13.
- **Alternatives:** (a) capture/replay floor-apply responses in `run_eval` now; (b) defer to WS-4 (current, inert because clinical_v1 has no floor).
- **Question for spec author:** Is deferring the floor-apply replay capture in `run_eval` to WS-4 acceptable, given the default clinical ontology declares no floor so the offline-deterministic identity (CLAUDE.md §Stack) is preserved for the shipped config?
- **Recommended resolution:** **Accept the deferral** as S-BS-13; the offline-deterministic charter is not breached for any shipped ontology. Lock that WS-4's eval-pack loop must add a floor-replay capture before any domain ships a floor contract.

### Ambiguity 3: the floor-injected flag bypasses the gradeable/taxonomy partition (touches the core invariant)

- **Spec text:** `CLAUDE.md` §"Core invariant" #1 ("Every `expected_safety_flags` code is in `taxonomy/taxonomy_snapshot.json` `KNOWN_TAXONOMY_CODES`") + #4 ("Every flag has a `production_judges`-resident owner … never silently scored"); driver D2 leaves the injected-flag shape to the impl.
- **Implementation decided:** `grounding.py:355–365` — the floor appends its injected finding to `active` **after** the per-finding loop, so it never passes through `ontology.is_reference()`/gradeable filtering (`grounding.py:330`). The injected `code`/`severity` are read raw from `decl.params["inject_flag_code"]`/`["inject_severity"]` with **no validation** that the code is a declared gradeable flag or that the severity string is a key in `severity_map.weights`. (If `inject_severity` is an unknown string, `weight_of` returns 0.0 and the floor silently fails to flip.)
- **Alternatives:** (a) validate `inject_flag_code` against `ontology.gradeable_flags()` and `inject_severity` against `severity_map.weights` at ground-time (or ontology-load), raising on a bad declaration; (b) leave it as a by-construction authoring responsibility (current).
- **Question for spec author:** Should a floor contract's `inject_flag_code` be required to be a declared gradeable flag (with a `production_judges` owner per invariant #4), and `inject_severity` a known severity — validated loudly — so the core invariant ("labels true by construction; never silently scored") extends to floor-injected verdicts? The defect class this guards is a misconfigured ontology whose floor BLOCKs on a code with no owner, or silently never blocks on a typo'd severity.
- **Recommended resolution:** **Update the spec** to require floor `inject_flag_code` ∈ gradeable flags + `inject_severity` ∈ `severity_map.weights`, validated at ontology-load (cheap; the test ontology already satisfies it — `FHIR_STRUCTURAL_VIOLATION` is declared gradeable with owner `structural_validator`). Inert for the shipped clinical ontology (no floor), so a follow-up cycle, not a WS-3a blocker.

**Findings:**

- `[OPEN-QUESTION]` Q4-1 "byte-identical" definition — recommend accept additive + reword driver.
- `[OPEN-QUESTION]` Q4-2 S-BS-13 floor-apply replay in `run_eval` — recommend accept deferral to WS-4.
- `[OPEN-QUESTION]` Q4-3 floor-injected flag bypasses the gradeable/owner/severity validation that ordinary findings + the core invariant assume — recommend a follow-up spec update + ontology-load validation.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 2 | 0 |
| 2 | Behavioral fidelity | 0 | 1 | 0 |
| 3 | Out-of-scope intrusion | 0 | 3 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 3 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (if any)

No BLOCKING findings. Proposed dispositions for the non-blocking / open items:

1. **Q4-3 (floor flag bypasses gradeable/owner/severity validation)** — *Proposed disposition:* open a follow-up seam (suggest **S-BS-16**) + a small WS-3b/WS-4 cycle to validate `inject_flag_code`/`inject_severity` against the ontology at load-time. **Owner:** spec author / monitor. Highest-value of the three (touches the repo's core invariant) but inert for the shipped ontology.
2. **Q4-2 (S-BS-13 floor not replayable in `run_eval`)** — *Proposed disposition:* accept as the already-logged S-BS-13; gate WS-4's eval-pack loop on adding a floor-replay capture before any floor contract ships. **Owner:** WS-4.
3. **Q4-1 ("byte-identical" wording)** — *Proposed disposition:* spec-wording update in a doc-only pass; reword driver §5 A3 to "additively backward-compatible." **Owner:** spec author.
4. **Surface/intrusion non-blockers** (run_eval not in file-list but in-scope; stale spike comments `tools.py:13–20,352–355`; dangling `TOOL_KB_RAG` constant) — *Proposed disposition:* accept as-is for WS-3a; fold the stale-comment + `TOOL_KB_RAG` cleanup into WS-3b when `kb_rag` lands. **Owner:** WS-3b executor.

All four deviations the kickoff flagged for audit resolve as documented + correctly-handled:
- **A3 backward-compat:** functionally demonstrated; literal "byte-identical" narrowed by approved refinement #1 → Q4-1 (non-blocking).
- **3 citation drifts + Decision 6:** all documented (log:14–50); `build_report` confirmed non-existent; `build_floor_correction` + `composite()` surfacing is the correct resolution.
- **Decision 2 (`_FLOOR_CONTRACT_TYPES` vs `_CONTRACT_EXECUTORS`):** documented + approved ("more faithful to the code than my driver was"); the two-registry split is sound (suppress = per-finding, floor = per-artifact — a genuinely different shape).
- **S-BS-13:** correctly logged; inert for the shipped ontology → Q4-2 (non-blocking).

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec without reading the executor's session log first (session log read last, step 6)
- [x] Read the diff via the working tree (HARD GATE — nothing committed; `git diff` + untracked reads), not via the executor's prose summary
- [x] Each finding cites both spec file:line and implementation file:line
- [x] Did NOT edit any code, spec, or driver (read-only; ran import/determinism probes only)
- [x] Did NOT confer with monitor or executor before writing the verdict

Independent re-verification performed (not relying on the session log): A1 import isolation (`import lithrim_bench.verification` on default deps; `dspy/httpx/pinecone/onnx` all absent from `sys.modules`); A4 build determinism (all three packs `diff==0` on re-run); pack counts 10/8/10; `build_report` absence; floor-injection ordering bypasses the gradeable partition.

---

## Appendix: commits audited

```
NONE — HARD GATE. All WS-3a changes staged in the working tree, pending this
fresh-critic close + user sign-off before the 5 atomic commits land:
  feat(ws3): promote verification core module (guarded heavy imports) [D0]
  build(ws3): add [verification] optional extra [D1]
  feat(ws3): wire structural-floor VerificationContract into harness grounding [D2]
  chore(ws3): home by-construction verification packs + pinned validator [D3]
  test(ws3): verification core tests (offline; importorskip dspy) [D4]
```

## Appendix: files changed (working tree)

```
 M lithrim_bench/harness/__init__.py   |  29 +     (D2 exports)
 M lithrim_bench/harness/correction.py |  66 +     (D2 build_floor_correction)
 M lithrim_bench/harness/grounding.py  | 153 +     (D2 floor wiring — headline)
 M lithrim_bench/harness/report.py     |  28 +     (D2 composite floor surfacing)
 M pyproject.toml                      |   9 +     (D1 [verification] extra)
 M scripts/run_eval.py                 |  33 +     (D2 by necessity; → S-BS-13)
?? lithrim_bench/verification/         (D0: __init__,spec,etlp_client,tools,jute_gen,jute_dspy,mutation,router)
?? data/verification_packs/            (D3: fhir_patient_v1=10, fhir_observation_v1=8, transaction_v1=10, README)
?? validators/fhir_us_core_patient_validator.generated.jute  (D3: clean Patient, no timestamp check)
?? scripts/build_{fhir_patient,fhir_observation,transaction}_pack.py  (D3)
?? tests/verification/  (D4: test_toolbox, test_jute_dspy[3 importorskip], test_mutation, test_grounding_floor)
```
