# SPEC: Reproducing the judge-vs-floor research purely via the Lithrim UI (REPRO-1)

**Status: DRAFT v2 for owner review, 2026-07-03.**

## THE CLEAN-SURFACE CONSTRAINT (owner, 2026-07-03 — binding)

Nothing is loaded from the backend, a pack drop-in, or any ad-hoc seed. The reproduction starts
from a **fresh, neutral `_core` workspace** and the user authors EVERYTHING step by step on the
product surface: the failure taxonomy (flags + criterion text via CriterionBuilder/FlagEditor),
the reviewers (JudgeBuilder + Connect AI bindings), the terminology tool (ToolBuilder), the
grounding contracts (ContractBuilder), the corpora (chat ingest), and then runs the cost-confirmed
cohort grade. No `LITHRIM_BENCH_PACK=healthcare`, no `packs-dropin/`, no pre-seeded ontology, no
CLI. Consequence: **every executor the experiment needs must be a CORE, domain-agnostic contract
type** — domain knowledge enters ONLY through UI-authored params, the authored ontology, and the
user-connected terminology tool. The healthcare pack's clinical-tuned floors stay where they are;
this program ships their generic core equivalents.
**Target:** `docs/thesis_llm_judges_and_the_grounding_floor.md` + `out/linkedin_judge_vs_floor/` is
reproducible end-to-end on Lithrim by a user who never touches a script: ingest → author judges →
connect tools → author contracts → one cost-confirmed cohort grade per corpus → read the matrix,
the tallies, and the per-case evidence. The `out/linkedin_judge_vs_floor/run_*.py` scripts become
unnecessary; the product IS the harness the research ran on.

## The shape of the reproduction (the load-bearing design decision)

The research is NOT a generic A/B framework problem. Its whole judge side is **one council whose
members are the same generalist reviewer bound to different models**: four roles, one shared
prompt, k=5 @ temp 1.0 each. Under that framing:

- per-model verdict = the per-judge vote (already stored per role),
- the K=5 ensemble split (e.g. `3B/2P`) = the per-judge `sampling.scores_raw` (already captured),
- cross-model majority = a deterministic reduction over the votes (reported BESIDE the frozen
  council consensus, never replacing it — the moat is untouched),
- judge-only vs judge+floor = the pre-floor vs post-floor verdicts already in ONE run blob
  (LAYER0-READ-1), so the headline delta needs NO second run and NO cross-run compare framework.

**One cohort grade per corpus carries the entire experiment.** What's missing is (a) two ingest/
prompt fidelity gaps, (b) N-role authoring/binding friction, (c) the read surfaces that aggregate
what is already recorded, and (d) two floor executors that today exist only as research scripts.

## What already works via UI (verified, evidence in the 2026-07-03 exploration)

| Step | Status | Evidence |
|---|---|---|
| Anthropic + OpenAI direct-API judges, per-role cross-provider binding | ✅ | `judges_dspy.py` `_LITELLM_PREFIX`; `/v1/roles/bind`; `test_provider_center_types.py` mixed council |
| Per-judge k / temperature / criterion / role prompt via UI | ✅ | JudgeEditor k+temp inputs; PROMPT-EDIT-1 textarea; JudgeBuilder new-role card |
| Hermes SNOMED connect via UI + grade-time resolution | ✅ | ToolBuilder `tool.terminology` + test-connection; `resolve_tool` authored→pack→core |
| snomed_subsumption (clears false blocks), dosage_grounding (enforces missed blocks), concept_preservation | ✅ shipped | pack `floors.py`; ContractBuilder types come live from `/v1/grounding-contract/types` |
| Sharif corpus ingest ($0 deterministic known-shape) + gold-label merge | ✅ | `_AGENT_TRACE_TEMPLATE`; `_merge_byo_labels` |
| Cohort grade (cost-confirmed run-all) + scorecard vs gold | ✅ | `grade_cases_endpoint`; `_cohort_scorecard`; ScorecardCard |
| Per-run floor visibility, run trail, per-judge confidence (logprob override where supported) | ✅ | ReportTab floor section; RUNTRAIL; `extract_verdict_confidence` |

## The gaps (the REPRO-1 program)

### R1 — Corpus & prompt fidelity (without this the experiment isn't even runnable honestly)

- **R1a. Known-shape ingest template for the bench-case JSONL shape** (corpus A: `case_id`,
  `transcript`, `patient_profile.conditions`, `artifacts[0]` = FHIR DocumentReference whose
  `content[0].attachment.data` is the note, `expected_*` labels). Today this falls to the paid,
  slow LM-gen path and silently DROPS `patient_profile`. A deterministic template makes the
  173-case corpus a $0 instant ingest with the record preserved. Generic by construction: the
  template keys on structure, not clinical strings.
- **R1b. The record reaches the judge.** The council's case context renders transcript + response
  only; `patient_profile.conditions` never reaches the judge prompt. The research's judge prompt
  has a "PATIENT RECORD – PROBLEM LIST" section — without it the subsumption over-block behavior
  is not reproducible. Fix: a generic, data-driven "source record" section in the authored-stage
  case context (present only when the ingested case carries it). No clinical strings in core.

### R2 — The N-model council (authoring friction)

- **R2a. 3→N role model binding.** `AssignModelsSection` hardcodes the v2 trio
  (`risk_judge`/`policy_judge`/`faithfulness_judge`); a JudgeBuilder-authored role (e.g.
  `reviewer_gpt41`) cannot be bound to a model via Connect AI. Enumerate the active roster
  (pack production judges ∪ authored roles) instead. (Already a known P1.)
- **R2b. Roster control via UI.** Selecting WHICH judges run (the 4 clones; or single-reviewer
  mode) is `council_config.reviewer_roster` — today API-only (chat `assemble_agent` edits one
  judge at a time and may be v2-bound). Surface roster membership in the UI (AgentEditor or
  JudgeEditor list) so "this agent grades with exactly these N reviewers" is authorable.
- **R2c. Per-sample votes surfaced.** `sampling.scores_raw` (the raw K verdicts) is captured in
  provenance but not projected. Project it into the `judge_votes` read surface and render the
  split in VerdictCard/report (`3B/2P` chip). Where both exist, carry self-reported AND
  logprob-derived confidence side by side (the 0.92-vs-0.29 decoupling is a thesis claim; today
  the logprob value overwrites the self-report).

### R3 — The research read surface (aggregating what is already recorded)

- **R3a. Per-judge scorecard split.** `_cohort_scorecard` scores only the council verdict.
  Add: per judge-role (= per model) matches-gold / silent-misses / over-flags; a deterministic
  cross-model majority row; and the per-case matrix (case × judge, cell = verdict + K-split,
  disagreement-with-gold highlighted) — the `report_clinverdict.md` table, generated live.
- **R3b. Floor tallies + judge-only vs judge+floor columns.** Aggregate per cohort: false blocks
  cleared (n/of), blocks enforced by floor, genuine defects cleared (must be 0 — the safety
  property, asserted visibly), cannot-ground count (declines are a feature — show them). Verdict
  accuracy shown pre-floor vs post-floor from the same blobs. This is the thesis headline in one
  card.

### R4 — The core generic executor set (under the clean-surface constraint)

The experiment needs FOUR checks; today two live only in research scripts and two live only as
clinical-tuned pack floors unavailable on `_core`. All four ship as CORE, domain-agnostic types
(they appear automatically in ContractBuilder via the live types endpoint; every one is
conservative by construction and lands its evidence/samples in the run blob):

- **R4a. `fact_preservation` (new, core).** Param: the pinned fact (SME text) + optional
  source/note paths. Mechanism: bounded LLM extraction (`stated_in_transcript`,
  `preserved_in_note`) at temp 0, K-repeat majority, verdict = deterministic logic over the
  booleans; declines when the fact can't be confirmed in the source. Floor direction (injects
  the UI-authored flag, e.g. DISSENT_ERASURE / INTENT_ERASURE / HISTORY_OMISSION). The extraction
  LM rides the existing role-binding seam.
- **R4b. `speaker_attribution` (new, core).** Param: the statement + who the artifact ascribes it
  to. Same bounded-extraction pattern (`transcript_speaker`, `note_attributes_to`); blocks on
  proxy→claimed-speaker misattribution. Governs the UI-authored PROXY_MISATTRIBUTION.
- **R4c. `terminology_subsumption` (core-generic twin of the pack floor).** Grounds the FLAGGED
  SPAN's term(s) — span-driven BY CONSTRUCTION, so the SPAN-BIND-1 lesson is structural, not a
  gate — against record concepts by is-a subsumption through a **user-connected**
  `tool.terminology` connector (ToolBuilder; Hermes is one such tool, named only in the user's
  authored config, never in core code). Params: the tool id + `record_path` + optional
  `term_regex` + op names. Suppress direction, conservative (never cleared by silence). The
  healthcare pack's `snomed_subsumption` remains as its clinically-tuned variant (SOAP/PMH
  extraction); core carries zero clinical strings.
- **R4d. ~~`value_consistency`~~ — DESIGNED OUT (build finding, 2026-07-03).** The core
  `value_presence` floor with `match='all'` already covers the dose-conflict reproduction: the
  source's stated value absent from the artifact blocks (the 0.15-vs-0.10 case), and the
  corrected control does not fire. No new executor; the SME authors a `value_presence` contract
  with a value-extracting regex. (The pack's `dosage_grounding` remains the clinically-tuned
  variant with unit normalization.)

Negative controls are just contracts on preserved facts — no new mechanism; R3b's tallies make
"controls did not fire" visible.

### R5 — The experiment report (capstone, optional)

A shareable per-cohort research report (the matrix + tallies + per-case evidence links) rendered
from the stored runs — the `README.md`/`report_*.md` artifacts as a product surface instead of a
build script. Candidate: an artifact-pane "Experiment" view + markdown export.

## Sequencing & effort

| Cut | Est. | Unblocks |
|---|---|---|
| R1a + R1b | ~1 day | both corpora ingest $0 into a clean workspace; judges see the record |
| R2a + R2b + R2c | ~1–1.5 days | the 4-model council authorable from scratch; votes/K-splits readable |
| R3a + R3b | ~1–1.5 days | the matrix + tallies + pre/post-floor headline |
| R4a–R4d | ~2.5 days (incl. live gating) | all four checks authorable on `_core`; the 4 Sharif flips + subsumption/dose demos, product-native |
| R5 | ~0.5–1 day | shareable report |

Order R1 → R2 → R3 → R4 → R5; each cut independently shippable and demonstrable live. A dry-run of
the full journey on a clean workspace (the stranger test below) closes the program.

## Non-goals / honesty constraints

- The frozen consensus (`_apply_consensus`) is untouched; the cross-model majority is a REPORTED
  reduction beside it, never a new verdict mechanism.
- No generic multi-run A/B framework in this program: the reproduction needs none. (Cross-run
  repeat-stability views and the before/after criterion-edit compare remain separate, later work.)
- The Composo contrast (reward-model endpoint as a 5th judge) is out of scope for v1; if wanted,
  it is an `openai_compatible`-style provider adapter question, not a matrix question.
- Exact thesis numbers are not the acceptance bar (models drift; SNOMED edition-dependence is
  documented); the bar is the SAME experiment, same shape of outputs, runnable by a stranger.

## Definition of done (the stranger test, clean-surface edition)

From a fresh Docker boot on the neutral `_core` default — no pack env, no drop-ins, no seeds —
via UI/chat only, in journey order:

1. **Create a workspace**; connect providers (OpenAI + Anthropic) in Connect AI.
2. **Author the taxonomy**: mint the experiment's flags with criterion text (FABRICATED_HISTORY,
   WRONG_DOSAGE, DISSENT_ERASURE, INTENT_ERASURE, PROXY_MISATTRIBUTION, HISTORY_OMISSION, …) via
   CriterionBuilder/FlagEditor.
3. **Author 4 generalist reviewers** (JudgeBuilder), one shared prompt, full lens; bind each to a
   different model across the 2 providers; set k=5 @ temp 1.0 (JudgeEditor).
4. **Ingest both corpora** with gold labels (chat ingest; both on deterministic $0 templates).
5. **Connect the terminology server** (ToolBuilder) and **author the contracts**: subsumption,
   value-consistency, preservation ×3, attribution, + 2 negative controls (ContractBuilder).
6. **Run one cost-confirmed cohort grade per corpus.**
7. **Read**: (a) the per-model × per-case matrix with K-splits, (b) matches/misses/over-flags per
   model + cross-model majority, (c) judge-only vs judge+floor accuracy, (d) floor tallies incl.
   fabrications-cleared = 0 and cannot-ground counts, (e) per-case drill-down to
   transcript/note/votes/floor trace. Every number traceable to an immutable run record.

If ANY step requires a script, an env flag, a pack file, or a backend seed, the program is not done.
