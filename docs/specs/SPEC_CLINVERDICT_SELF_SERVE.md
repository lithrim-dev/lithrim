# SPEC: ClinVerdict-on-Lithrim — running a physician-curated clinical eval suite self-serve

> A practicing physician built **ClinVerdict** (a physician-curated adversarial clinical-AI eval suite)
> on **Arize Phoenix** — a 2-skill scribe SUT, an LLM judge, a 10-case golden suite, and a 4-layer
> evaluation workflow. **Question:** what would it take to do that on lithrim-bench **without writing
> code**? This spec maps ClinVerdict's four layers onto Lithrim's no-code surface, names what already
> works, and drives the **minimum** stopgap drivers so a clinician can run this self-serve.
> **Status: DRAFT 2026-06-17.** Source: `ClinVerdict-Physician-Curated-Clinical-AI-Evals-Suite`
> (Dr. Sharif Al Zaber). Companion docs: [`SPEC_NARRATIVE_EVAL.md`](SPEC_NARRATIVE_EVAL.md) (the
> "eval anything" wedge this extends), [`SPEC_GROUNDING_TOOL_LAYER.md`](SPEC_GROUNDING_TOOL_LAYER.md)
> (the floor/withstands layer), [`SPEC_UNIFIED_AUTHORING_PRODUCT.md`](SPEC_UNIFIED_AUTHORING_PRODUCT.md)
> (the author→process loop). Derived from workflow `wf_d6df157e-64b` (6 readers → gap matrix →
> per-gap adversarial verify → synthesis); every claim below was refuted-then-survived against the code.

## 1. The thesis (and why the fit is strong)

**ClinVerdict's reason to exist is Lithrim's core mechanism.** ClinVerdict's headline finding —
*an LLM judge anchored to a defective human reference note inherits the reference's blind spots, and
the fix (its Recommendation #1) is to cross-validate the judge's claim against the raw transcript
INDEPENDENTLY of that reference* — **is** Lithrim's deterministic grounding floor + the Ralph-Loop
withstands-gate. That is not an analogy: `scripts/extract_clinverdict.py` already demotes the human
reference note to a non-grading auditable input and grades against the transcript, and the
`presence_check` floor + withstands-gate already strips a validator-disproved finding and flips a
council verdict (`reject → approve`) honestly.

So the **executional spine of all four ClinVerdict layers is reachable today, no-code, on an existing
pack** (§3). The gap is not the mechanism — it is four specific seams (§4): the human meta-audit loop,
from-scratch domain authoring, gold-label attachment, and per-skill performance tracing.

## 2. ClinVerdict's four layers → Lithrim status

| ClinVerdict layer | What the physician did | Lithrim no-code status |
|---|---|---|
| **1 · Execution** | Run a 2-skill scribe (extract → SOAP) as the SUT | **Supported** — author the SUT/judges by chat; `$0` replay or cost-gated paid council grade |
| **2 · Automated judge** | LLM judge scores Faithfulness/Completeness/Safety vs the reference | **Supported (authoring)** — assign ontology lenses to roles, pick BYO-Claude vs Azure so judge-model ≠ SUT-model; capture per-judge votes + confidence + reason + findings + ECE |
| **2 · …tracing dashboard** | Phoenix span tree: per-skill tokens / latency / cost | **Reframe (not parity)** — Lithrim captures a decision/calibration/governance trace, **not** a system trace. No span tree; per-judge token/cost capture is effectively absent on the live path |
| **3 · Clinical validator (HITL)** | Physician meta-audits the judge, records an independent verdict, **dissents**, names the judge's fallacy, flags the reference note as defective | **Stopgap (the big one)** — the *transcript-grounding floor* is here and works, but there is **no surface anywhere** to record a human verdict / dissent / fallacy / reference-defect |
| **4 · Pipeline architecture** | Diff skill-1 extraction vs skill-2 SOAP → "Silent Drop" | **Stopgap** — the floor reads one artifact; no two-output diff primitive; and the source data doesn't carry skill-1 output |
| **0 · Curation / suite** | Hand-curate a 10-case golden suite; attach gold labels; stand up the domain | **Partial** — `ingest_cases` loads outputs no-code, but a new domain needs 4 hand-edited pack files, gold-labels aren't attachable, and a new *gradeable* criterion is gated |

## 3. What already works — the no-code minimum path today

A clinician can run this **right now**, no code, on the existing `narrative` (scribe-shaped) pack.
Honest caveats inline; some steps are chat, some are UI cards.

0. **Pin the domain (UI).** Titlebar workspace pack-picker (`WorkspaceSwitcher`,
   `apps/shell/src/app.jsx:13`) → create+pin a workspace to a pack; the whole config plane and grade
   subprocesses resolve under `LITHRIM_BENCH_PACK=<pack>`. *Caveat:* this pins a **pre-existing** pack
   (§4 NARR-9).
1. **Load the scribe outputs (chat).** Paste the scribe JSON into the composer → the agent calls
   `ingest_cases` → JUTE transform on `:3031` (live-gated) → pin/reuse → corpus upsert → one
   `AuditRecord`. `$0`, audited (`apps/bff/agent/tools.py` `INGEST_CASES_SCHEMA`; `app.py:2058`).
   *Caveat:* chat-only — no drop-zone yet (§4 NARR-8-UPLOAD-1).
2. **Author the judges (chat or UI card).** `author_judge` assigns ontology lenses to a role
   (faithfulness/policy/risk ship generic over "source material" vs "response" → transcript=source,
   SOAP=response); pick the judge **model** (Azure vs `byo-claude`) so it differs from the SUT — an
   audited `$0` write (`tools.py:230`; `PUT /v1/judges` `app.py:1214`; `JudgeEditor.jsx`).
3. **Attach the transcript-grounding floor (chat or UI card).** `add_grounding_contract` /
   `ContractBuilder` splices a `presence_check` onto a flag — **ClinVerdict Recommendation #1
   realized**: at grade time the withstands-gate strips the validator-disproved finding and flips the
   council verdict honestly (`tools.py:512`; `POST /v1/grounding-contract` `app.py:1456`;
   `grounding.py` PresenceCheck; `runtime/council/withstands.py`). *Caveat:* only **attaching existing
   executors** is no-code, and the ContractBuilder dropdown currently lists 3 **dead** types (§4
   CONTRACT-GUARD-1) — stick to `presence_check` / `kb_grounding` / the pack floor codes.
4. **Grade (UI).** "Run eval" = `$0` replay (real verdict card; Report/Judges tabs project per-judge
   votes/confidence/reason/findings); "Run live" = paid in-process council, gated behind a human in-DOM
   `CostModal`. The chat agent can **never** spend (`PAID_KEYS` asserted absent from every tool schema;
   PreToolUse deny hook, `loop.py:225`).
5. **Review verdicts + calibration (UI).** Report tab shows per-judge votes + reliability bins + ECE,
   **honestly withheld** ("No ground truth — withheld") when the case is unlabeled (`report.py:95`;
   `artifact.jsx:149`). *Caveat:* attaching a gold label to turn this into a measured verdict-match
   scorecard is **not** yet no-code (§4 NARR-LABEL-1).
6. **Read the audit trail (UI).** Every write in 1–3 emitted an immutable why/who/when/what
   `AuditRecord`; `AuditView` / `GET /v1/audit` surface it. The conversation **is** the audit log.

**Cannot do no-code today:** record your own clinician pass/fail and dissent from the council, name the
judge's fallacy, flag the reference note as defective, attach a gold label, stand up a fresh domain,
mint a new gradeable criterion, or see per-skill token/latency/cost. Those are the stopgaps.

## 4. The stopgaps — prioritized drivers (reuse-first)

> "Engine edits" = touches `lithrim_bench/runtime/council/` or the frozen `_apply_consensus` /
> withstands / `Judge.forward` seam. The moat stays byte-frozen unless explicitly noted.

### P0 — the blocking minimum

**META-VERDICT-1 — record an independent clinician verdict + judge meta-audit** *(M · no engine edit)*
- *Problem:* a physician can read the council's votes but cannot record their own pass/fail, say "the
  judge **erred**" and name the fallacy, or **dissent** on the record — ClinVerdict's Layer-3 reason to
  exist. Confirmed absent (grep `meta_verdict|human_verdict|agrees_with|reviewer` over `apps/bff/` +
  `apps/shell/src` is empty; the Report "Author labels…" line is render-only). Also blocks the cohort
  matrix + the 85.7% blindness stat.
- *Minimal scope:* `POST /v1/meta-verdict {run_id, human_verdict, agrees_with_council, judge_fallacy_code(closed enum, nullable), rationale}` → one immutable `AuditRecord` via the already-imported `AuditLog`, byte-for-byte the `put_ontology_endpoint` audited-write idiom; a `record_meta_verdict` SDK-MCP tool modeled on `add_grounding_contract` (`$0`, no `PAID_KEY`); a Save control in ReportTab's Calibration slot. `judge_fallacy_code` enum = {Hallucination Blindness, Reference Bias, Metric Conflation, Risk-Severity Blindness, Boundary Violation}.
- *Exit:* a physician runs a `$0` replay, records `{human_verdict=fail, agrees_with_council=false, judge_fallacy_code='Reference Bias', …}`; `GET /v1/audit?target_type=verdict&target_id={run_id}` returns it; a second submission appends; out-of-enum 422s; no `lithrim_bench/harness/` file touched.

**NARR-9 — `create_pack` scaffolder (author a new eval domain self-serve)** *(M · no engine edit)*
- *Problem:* you can pin a pre-existing pack but cannot **author** a new domain — no write path creates a pack on disk; the 4 files (`pack.json` + `ontology.json` + `council_roles/*.txt` + `taxonomy_snapshot.json`) are hand-edited. This blocks the dependents: `create_flag`, gold-labels, and `PUT /v1/ontology` all resolve via `_pack_root`, which raises when the pack dir is absent.
- *Minimal scope:* `POST /v1/packs` + a tool that writes a valid, admissible, **domain-neutral** skeleton into the workspace `packs_dir` (copy the 4-file shape verbatim from `packs/_core/`: the 3 generic `council_roles/*.txt`, a minimal `ontology.json`, a `_core`-shaped `taxonomy_snapshot.json` — introduce no new role file) + one `AuditRecord`. Discovery is automatic via `_pack_root` / `discover_packs` / `_resolve_ref`. Pack model is already file-driven → zero engine edit.
- *Exit:* "create a new scribe-eval domain called clinverdict" writes `<packs_dir>/clinverdict/` (4 files + audit); `GET /v1/packs` lists it; a workspace pins to it; `assert_pack_judges_consistent` + `pack_tiers`/`pack_lenses`/`pack_production_judges` load; zero `packs/healthcare/` reads.

**NARR-LABEL-1 — self-serve gold-label authoring on an ingested case** *(M · no engine edit)*
- *Problem:* cases land **unlabeled by construction** (`_to_envelope` hardcodes `expected_safety_flags:[]`, emits no `expected_compliance_verdict`). `report.py:195` **already** scores `expected_compliance_verdict`; the fields just have to be hand-placed in JSONL today. The Report empty-state says "Author labels…" behind a button that doesn't exist. This is the gate from "metrics withheld" → a measured verdict-match scorecard.
- *Minimal scope:* `POST /v1/case/{case_id}/label` (+ `set_case_label` chat tool) resolving the row via `picklist.load_case`, merging `expected_safety_flags` + `expected_compliance_verdict` at top level, rewriting `ingested_cases.jsonl` with the read-merge-rewrite block already inline in `_ingest_cases`; **gate** through `admissibility.active_snapshot_codes()` (`⊆` active-pack tier union → keeps labels-true-by-construction); one `AuditRecord` (`Target(type='case')`). Wire the empty-state to a label form.
- *Exit:* ingest → "Author labels" → pick verdict + gold codes → save → row carries top-level labels → re-run flips Calibration from "withheld" to a real `verdict_match_rate` + ECE; out-of-snapshot code 422s; round-trip test passes.

### P1 — completes the suite

**NARR-5-COHORT — `GET /v1/cohort-matrix` (derived run × label cross-tab, honest-degrade)** *(M · no engine edit)*
- The ClinVerdict master matrix + cohort stats. A `report.py cohort_matrix(records)` aggregator beside `calibration_check`, joining stored run blobs (`PIPELINE_RUNS.list_all`) to label/meta rows; the clinician-verdict / judge-fallacy / **blindness** columns emit only once META-VERDICT-1 rows exist (else `label_status:"no_meta_verdict"`, never a fabricated 85.7%). Ships the verdict-match half now; reads existing blobs (no new persistence).
- *Exit:* a Report → Cohort sub-view shows one row/case + a cohort header (`n_cases`, `verdict_match_rate` over the labeled subset, pooled ece); blindness columns render withheld until meta-verdicts exist.

**NARR-META-2 — typed judge-fallacy / agent-error / reference-defect taxonomy (DATA-only)** *(S · no engine edit)*
- Seed the three taxonomies as **non-gradeable reference flags** in `packs/narrative/ontology.json` only (do **not** touch `taxonomy_snapshot.json` — non-gradeable flags aren't snapshot-gated) via a reserved-category convention (`category=judge_fallacy|agent_error|reference_defect`), each `gradeable:false / tier:null / owner_roles:[]` — the exact shape `_create_flag` already mints. The closed-enum guard rides META-VERDICT-1's record validation.
- *Exit:* under `pack=narrative` the ontology carries the three taxonomies as admissible `gradeable:false` flags; offline test (zero `packs/healthcare` reads) asserts they load + `gradeable_flags_outside_snapshot` returns `[]`.

**NARR-5-CRIT — self-serve gradeable-criterion authoring into the active pack snapshot** *(M · no engine edit · ⚠ needs human sign-off)*
- *Problem:* minting a new **scoreable** criterion (Layer-2) is reachable today only by hand-editing the pack snapshot before the pack is live. `create_flag` hardcodes `gradeable=False`; a new gradeable code 422s — and that 422 **misdirects**, telling the SME to run the clinical `snapshot_taxonomy.py --backend-path`, which is false for a hand-authored domain.
- *Minimal scope:* `create_gradeable_criterion` + `POST /v1/criterion` splicing a code into the **active** pack's snapshot (resolve via `_pack_ref(active,'flags_ref')`, splice into `tiers[tier]` + `lenses[owner_role]` + `tier1_owners` when T1) and appending the ontology flag `gradeable=True` through the frozen `put_ontology_endpoint`, under the existing admissibility lint; reject if `owner_role ∉ production_judges`; clear `_council_known_codes`; **fix the misleading 422**; gate to `tier:core` packs.
- *⚠ Sign-off:* this adds the **first snapshot writer** above the CLAUDE.md "never hand-edit the snapshot / read-only at grade time" invariant, and decides `SPEC_NARRATIVE_EVAL §11`'s open question toward UI-emit. The gate itself (labels-true-by-construction) stays intact — this is the *admissible* self-serve path into it, not a weakening.
- *Exit:* "create a gradeable T2 completeness criterion EVERY_DOSE_IN_SOAP owned by faithfulness_judge" writes it into the snapshot (tiers + lenses) + ontology in one audited action; the re-snapshot 422 does **not** fire; a case carrying it grades with the owner judge able to raise it; bad owner 422s, dup 409s, cache cleared, zero `packs/healthcare` reads.

**NARR-FLOOR-1 — ship the inverse-direction `value_presence` completeness floor** *(M · one additive registration line, above the moat)*
- The completeness move splits two ways. **Forward** ("every SOAP value grounded in the transcript") is **already** `dosage_grounding` (configurable regex + sources, tri-state PASS→BLOCK) — only its clinical *name* hides it; generalize the param in place (pack-local, no core edit). **Inverse** ("every spoken value must appear in the SOAP") has no tool: ship one parametric, pure-stdlib `value_presence` floor (token regex + dotted `source_path` default `transcript`, presence-checked against `artifacts[0].content`; `conforms=False` on a missing required token, `None` on nothing parseable). Register the **name** once in core (`_KNOWN_TOOLS` + `_REQUIRED_REFERENCE_KEYS` — the one unavoidable additive line); the tool class + executor ship pack-local (`packs/narrative/floors.py`, BracketLeakTool is the template). After registration, authoring is **params-only**.
- *Exit:* a `contract_type='value_presence'` entry grades a crafted pair offline/`$0` through `ground()` (source token absent → `conforms=False` → PASS→BLOCK; clean twin → no blocks; no token → `None`); a second inverse floor needs no new code.

**NARR-DIFF-1 — `inter_stage_diff` floor (the "Silent Drop")** *(M · one additive registration line + DATA authoring)*
- ClinVerdict Layer 4 (4/10 cases): a token extracted by skill-1 but silently dropped from the skill-2 SOAP. Unreachable for **two** reasons: (a) the floor sees one artifact (`_artifact_content → artifacts[0]`); (b) **the load-bearing one** — no case carries the second stage output, and the ClinVerdict extractor itself records `skill_1_extraction.available=False` (it lives only in the Phoenix trace). An `InterStageDiffTool` reading both outputs off `claim.source['artifacts']` (no `_artifact_content` edit needed) + a gradeable `VALUE_SILENTLY_DROPPED` flag closes (a); **the real work is the data** — author ≥1 admissible 2-artifact by-construction case + its clean twin, and the upstream SUT must be instrumented to emit skill-1 output.
- *Exit:* offline, a hand-authored 2-artifact case [SOAP missing a value; a `produced_by=skill_1` artifact containing it] grades to BLOCK with the dropped token in evidence; the clean twin passes; a single-artifact case returns `None` and never flips.

**CONTRACT-GUARD-1 — 422 a dead `contract_type` at author time + honest dropdown** *(S · no engine edit)* — **confirmed bug**
- *Problem:* a non-coder using ContractBuilder (or `add_grounding_contract`) can pick `negation_check` / `code_match` / `range_check` — three types with **zero** registered executor in any pack (`ContractBuilder.jsx:27` vs an empty grep). The write **succeeds** (`_validate_ontology` never inspects `contract_type`); the card shows "added ✓"; then `ground()` **raises** at grade time and withstands silently `continue`s. The author believes a floor guards their judge when nothing runs.
- *Minimal scope:* add a `contract_type ↔ registered-executor` check inside `_validate_ontology` (assert each type ∈ `grounding.suppress_executors()` ∪ `grounding.floor_contract_types()`, read at request time for the active pack; 422 naming the dead type) — guards all three write paths at once; `GET /v1/contract-types` returns the live union; point `ContractBuilder.jsx:27` at it.
- *Exit:* a `negation_check` PUT/POST 422s naming the dead type and writes nothing; `presence_check` + the pack floor code still 200; the dropdown renders only fetched types; `ground()` never reaches its ValueError for a UI-authored contract; moat byte-frozen.

### P2 — honesty + ergonomics

- **NARR-REF-1** *(S · 1 request-model enum)* — fold an optional `reference_defect_code` + note onto the META-VERDICT-1 record (the third audit target: agent / judge / **reference note**). Carry the 3 codes as an enum constant (not seed flags — that would pollute the judge-lens set).
- **TRACE-1** *(S · no engine edit)* — project the already-persisted run-level `cost_tokens` + `duration_ms` into `_run_audit_report` / ReportTab. **Honesty:** per-judge usage is **not** captured on the live path (`Judge.forward` discards DSPy's `Usage`; `emit_timing` is a stub; `cost_tokens` falls back to `{0,0,0}`), so render **"n/a"**, never "$0". Per-judge capture is a separate freeze-guarded seam edit, split out.
- **OBS-COST-1** *(S · no engine edit)* — `data/config/model_prices.json` + a pure `_price_run()` → project `cost_usd` (null + marker for unpriced models, never fabricated) onto the run-eval response + Report tab.
- **NARR-8-UPLOAD-1** *(S · FE-only)* — a drop-zone / file-picker in the composer that `FileReader.readAsText` → `setInput(...)`; flows through the already-wired `ingest_cases` path. Never auto-sends, never fires a paid run.

## 5. Honest delta — what Lithrim can and cannot claim vs ClinVerdict-on-Phoenix

**CAN claim today (real, load-bearing, self-serve on an existing pack):**
- The executional spine of all 4 layers: define a 2-skill scribe SUT, author faithfulness/completeness/safety judges by chat on a model ≠ the SUT, run a `$0` replay or a cost-gated paid council grade, capture structured per-judge verdicts, compute calibration/ECE (honestly withheld when unlabeled).
- **ClinVerdict's central thesis as a working mechanism, not an analogy:** attach a transcript-grounding `presence_check` → the withstands-gate flips the council verdict honestly. Recommendation #1, realized.
- Governance/audit parity (arguably a Phoenix surplus): every authoring action is an immutable why/who/when/what `AuditRecord`.

**CANNOT claim — genuine stopgaps (capability missing, not reframed):** the human meta-audit loop
(META-VERDICT-1, P0); from-scratch domain authoring (NARR-9, P0); gold-label attachment
(NARR-LABEL-1, P0); new gradeable criteria self-serve + the misdirecting 422 (NARR-5-CRIT, P1); the
Silent-Drop comparator **and its missing source data** (NARR-DIFF-1, P1).

**CANNOT claim — and this is a REFRAME, not a fix-it:** Lithrim is **not** a Phoenix observability
substitute. No nested-span tree, no per-skill token/latency/cost. Lithrim answers a *different*
question — a decision/calibration/governance trace, not a system trace. The honest move (TRACE-1) is to
project the run-level numbers and render "n/a" until per-judge usage capture lands; full span/dashboard
parity is explicitly out of scope (needs a non-stub OTel sink).

## 6. Phased plan

1. **P0 trio** — META-VERDICT-1 → NARR-9 → NARR-LABEL-1. After this a clinician can stand up a domain,
   ingest, grade, **record their own verdict + dissent + fallacy**, and attach gold labels — the
   minimum to reproduce ClinVerdict's value self-serve. (NARR-9 is the unblocker; the other two need a
   pack on disk.)
2. **P1 suite** — CONTRACT-GUARD-1 (do early — it's a live bug) → NARR-META-2 → NARR-5-COHORT →
   NARR-5-CRIT *(human sign-off)* → NARR-FLOOR-1 → NARR-DIFF-1. Yields the typed taxonomy, the cohort
   matrix + blindness stat, self-serve gradeable criteria, and the completeness/Silent-Drop floors.
3. **P2 polish** — NARR-REF-1, TRACE-1, OBS-COST-1, NARR-8-UPLOAD-1.

## 7. Open questions

- **NARR-5-CRIT sign-off:** is a UI-driven snapshot *writer* acceptable, or does gradeable-criterion
  authoring stay an SME/CLI step? (Decides `SPEC_NARRATIVE_EVAL §11`.) The invariant is preserved either
  way; the question is *where* the admissible write happens.
- **Demo data:** reproduce ClinVerdict's 10 cases as a by-construction `clinverdict` pack corpus, or
  ingest the markdown via `scripts/extract_clinverdict.py` (untracked, already drafted) as unlabeled +
  layer gold via NARR-LABEL-1? The latter is the honest "drop your data" demo.
- **NARR-DIFF-1 source data:** the Silent-Drop check is only as real as the skill-1 artifact — does the
  scribe SUT get instrumented to emit it, or is this deferred until a real multi-stage SUT is wired?
- **Packaging:** ships the scribe/clinverdict pack as a Core demonstration pack or a Pro plugin?

## 8. Evidence appendix (verified anchors)

- **Already-works (CONFIRMED):** `apps/bff/agent/tools.py` (`author_judge` 230, `add_grounding_contract`
  512, `ingest_cases` schema, `PAID_KEYS`); `apps/bff/app.py` (`PUT /v1/judges` 1214,
  `POST /v1/grounding-contract` 1456, `_ingest_cases` 2058, run-eval 551, `_council_view` 633);
  `grounding.py` PresenceCheck + `floor_contract_types`/`suppress_executors`; `runtime/council/withstands.py`;
  `report.py:95` (ECE/reliability bins, withheld-when-unlabeled); `harness/audit.py` (AuditRecord);
  `harness/admissibility.py:43` (pack-resolved snapshot).
- **Stopgaps (CONFIRMED):** `apps/bff/app.py:1912` `_create_flag` hardcodes `gradeable=False` ("the one
  law"); `ContractBuilder.jsx:27` lists 3 executor-less types + `_validate_ontology` never checks
  `contract_type`; `_to_envelope` hardcodes `expected_safety_flags:[]`; grep for
  `meta_verdict|create_pack|onDrop|type=file` over the product plane is empty; `stages.py:874-886` sums
  per-message `usage` but `Judge.forward` (`judges_dspy.py:300`) emits none → `cost_tokens` `{0,0,0}`;
  `_compat.py:45` `emit_timing` is a stub.
- **Reuse precedent:** `packs/support_ticket_qa/` + `packs/narrative/` (non-clinical, file-driven packs);
  `tests/bff/test_storyworld_ingest.py` (ingest round-trip test template); `SPEC_NARRATIVE_EVAL.md` §8
  (the driver idiom this follows).
