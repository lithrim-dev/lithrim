# Paper Framing Decisions — 2026-05-26

**Status:** load-bearing for the next paper-drafting session. Layered on top of `HANDOFF_2026-05-23.md` and the two prior `PAPER_OUTLINE.md` scope-change notes (2026-05-22 + 2026-05-23). Nothing in those is overwritten; this doc records the third reframe.

## Context for the next session

A lithrim-verse audit ran today (backend + bench + UI + SDK + ETLP + sales-outreach + strategy + landing page). Four subagents reported in parallel; their findings are captured by reference rather than reproduced here (see "Audit source artifacts" at the bottom). The audit surfaced a structural mismatch:

- **Paper today:** 1 of 4 pillars empirically proven (Structural Validity on HL7); 1 of 5 product layers measured (Layer A = artifact-verification primitive); no trace-level audit, no external semantic-eval baseline, no measured safety/completeness/faithfulness deltas.
- **Product today:** four pillars (Faithfulness, Completeness, Safety, Structural Validity) × five layers (verification primitive, release-gate eval primitives, trace-level audit + attestation, domain-specific failure taxonomy + remediation, Jute Copilot). All five are in production code in `lithrim-backend` + `etlp-mapper`.
- **Market deck today:** the 4-pillar value reframe is locked (POSITIONING_ANALYSIS_agentic_ai_value.md, 2026-04-04), the 9-procurement-question framework is the closest thing to a category-defining claim, content is shipping at volume; **zero signed design partners, zero customer logos**.

**Net:** the paper as currently scoped underclaims what the product does and is narrower than what the market deck already argues for. Reframing the paper resolves all three.

---

## Decisions

### D1 — Rescope paper 1 from composition-rule paper to four-pillar framework paper

- **New working title:** *"Reliable Evaluation and Observability for LLM Applications in Regulated Industries: A Four-Pillar Framework with Deterministic Provenance and Generative Validator Composition."*
- The current `PAPER_OUTLINE.md` §1 narrow claim ("worst-of composition recovers a categorical blind spot") becomes one section of this paper (§3), not the whole paper.
- The four-pillar framework (Faithfulness, Completeness, Safety, Structural Validity) is the load-bearing contribution. Worst-of is the composition rule *inside* the framework.
- This aligns the paper with the product's actual contribution and with the market deck's 4-pillar value model.

### D2 — Lead §3 with silent-confident-certification, not the +28.6 / +100 pp number alone

- Run the 1-day experiment scoped in `HANDOFF_2026-05-23.md`: measure per-judge confidence on the 28 HL7 defects the live council missed in run #1.
- Frame the §3 headline as **"the council confidently certifies spec-violating clinical artifacts"**, not just "validator catches what judge missed."
- Effort: ~1 day. **Cost: ~$5 of council time** (S-P1-1 verified 2026-05-27: $0 path unavailable — `out/run1_archive/` contains no HL7 file; `_parse`/`JudgeOutput` discard `confidence` at capture; live re-run is the only path. See `STREAM_paper-1-copilot.md` open-seams table for the evidence summary, and `.devloop/prompts/paper-1-copilot_phaseP1-EXP-0_council_confidence_driver.md` §0 for the verbatim diagnosis.)
- This is the single next runnable step that closes paper 1's headline measurement.

### D3 — Promote the Jute Copilot from footnote to named contribution as §4, with stripped disclosure

- §4 of paper 1: describe **what** the copilot does — LLM-driven, generate→test→refine, confidence-graded retry (`high`/`medium`/`low`/`partial`/`failed`), merge mode (extends an existing template), produces a domain conformance validator from prose spec + sample input + expected output.
- **Withhold from paper 1:** the exact system prompt, the Jute DSL spec injection text, the retry-on-mismatch logic, the merge-mode subset-matching algorithm. Reserve those for paper 2.
- Cite mapping 25 → mapping 93 as a concrete, reproducible example: one API call, `confidence: high`, lifted HL7 coverage from 2/5 → 5/5 defect classes.
- This is the moat. It is currently undocumented externally (no public spec, no blog post, three-line `CLAUDE.md` note). The reframe surfaces it as a contribution while protecting the build spec.

### D4 — Add §7 on release-gate primitives as the deployment surface

- Describe the SDK contract: `eval.create_run(pack_id, baseline_run_id, threshold_config)`, `eval.compare(run_a, run_b)`, `eval.promote_case(...)`, `POST /v1/eval-runs/{id}/finalize` with `baseline_diff` + threshold-based ship/harden/block.
- Show how the framework lands as a deployment surface — CI/CD for LLM-driven clinical agents.
- Withhold: the threshold-evaluation weighting scheme, the failure-clustering algorithm, the agent KPI weights. Describe the contract, not the implementation depth.

### D5 — Discipline preserved from prior notes

- The 4-pack semantic sweep remains **baseline characterization**, not thesis validation (per 2026-05-23 reframe note). Pillars beyond Structural Validity are framed as *baseline characterization across the framework's other axes* in paper 1, not as new deltas measured against external baselines.
- The narrow-scope discipline from `PAPER_OUTLINE.md` §11 stays: this is **framework + benchmark + measurements + architectural contribution**, not "we beat the baseline by X."
- The pipeline-composition finding (scheduling "+71 pp" attributed to the artifact_judge, §7b.8) stays in. It is an *honest* finding, not a flaw; do not disable the artifact_judge to clean up the measurement (per `HANDOFF_2026-05-23.md` "things to NOT do").
- The 2026-05-22 and 2026-05-23 scope-change notes on `PAPER_OUTLINE.md` are **preserved**. The 2026-05-26 note is **layered on top**, not in place of. Audit trail intact.

### D6 — What to withhold from paper 1, with rationale

| Asset | Disclosure cost | Decision |
|---|---|---|
| 4-pillar framework + worst-of rule | Low (composition rule, copyable but not deployable without stack) | **Publish** |
| HL7 result + silent-confident-certification | Low (depends on validator stack) | **Publish (headline)** |
| Trace-level provenance architecture (pipeline_run, audit-view, idempotency_key, request_hash, stage_results) | Medium (others can claim back) | **Describe at high level**, withhold deterministic hashing scheme |
| Jute Copilot mechanism | **High** (replicable in 2–3 weeks if prompt + retry disclosed) | **Withhold mechanism**, name as contribution. Full disclosure → paper 2. |
| Eight-link evidence chain hashing scheme | Medium-high | Describe the eight-link concept, withhold the deterministic hash construction |
| ~80-flag safety taxonomy | Medium (named 6 already public) | Reference the named 6, withhold the full taxonomy |
| Failure clustering + patch templates | Medium-high (algorithmically modest, operationally valuable) | **Withhold**, demo in product |
| Release-gate primitives (SDK contract) | Low (copyable, not the moat) | **Publish** the contract |
| Agent KPI weighting scheme | Medium | Withhold |

### D7 — Staged disclosure: three papers, three distribution events

- **Paper 1 (now, 1-week sprint):** framework paper as scoped above. Ships **paired** with framework deck refresh + first dispatched outreach wave + a LinkedIn long-form post riding the Clinical API Layer thesis. Target: arXiv first to establish priority date, then a workshop track (NeurIPS / ICLR LLM-evaluation, SoLaR-style). **Not a top venue first.**
- **Paper 2 (3–6 months, paired with design-partner announcements):** the Jute Copilot paper. *"Generative Validator Composition: Producing Domain Conformance Checks from Specification Text with Confidence-Graded Retry."* Full mechanism disclosure. By the time it publishes, the copilot in production has moved beyond what gets disclosed.
- **Paper 3 (6–12 months, paired with v2 SDK launch or seed/A round):** trace-level audit + multi-step agent evaluation. Anchors the v2 narrative. Requires the 4-week measurement sprint from `HANDOFF_2026-05-23.md` (external baseline + safety pillar + completeness pillar + trace-level experiments).

### D8 — Pair every paper with a distribution event

- Don't publish a paper alone. Each publication is a category-anchoring moment with priority-dating + marketing flywheel attached.
- Paper 1 → framework deck + outreach wave + LinkedIn long-form.
- Paper 2 → first design-partner case study + public copilot demo + category-claim escalation.
- Paper 3 → v2 SDK launch or fundraise touchpoint.

### D9 — Product positioning lead does NOT lead with structural validation

- "Structural validation" is a $50M-niche feature description, not a category claim. Confirmed in this session.
- Product page / deck / outbound lead with the umbrella: **"Lithrim makes clinical AI deployable, defensible, and insurable."** Or the long-form: **"Lithrim is the evaluation and observability framework for LLM applications in regulated industries — four-pillar verification with deterministic provenance, domain-validated structural checks, and a copilot that generates the validators on demand."**
- Cite paper 1 when buyers push back with "how is this different from semantic eval?" Cite paper 2 when buyers push back with "anyone can build validators." Cite paper 3 when buyers ask about agent runtimes.

---

## What this changes in the bench

- `PAPER_OUTLINE.md` gets a 2026-05-26 scope-change note appended (the prior 2026-05-22 + 2026-05-23 notes are preserved verbatim).
- `paper_draft/01_abstract.md` needs a rewrite to frame as the framework paper. The 2026-05-23 abstract draft is a good starting point but is anchored on HL7 alone — extend to four pillars, name the Jute Copilot as a contribution, keep the silent-confident-certification headline.
- `paper_draft/04_method.md` needs §4 expanded to describe the Jute Copilot at the stripped-disclosure level (D3).
- `paper_draft/07_results.md` §7.3 (HL7) becomes §3 in the framework paper. New §7.7 lands the council-confidence-on-misses measurement when the 1-day experiment runs.
- New section needed: §7 (release-gate primitives) — pull from `lithrim-sdk/README.md` + `lithrim-backend/app/routes/eval_external.py` for accurate contract description.
- No code or measurement changes required for the reframe. Doc-only work + the 1-day council-confidence experiment.

## What this does NOT change

- Run #2 N=10 test-split numbers (`out/judge_calibration_n10_test.json`) stay as the §7-equivalent paper anchors.
- The 2026-05-23 reframe note's framing (worst-of recovery unambiguously demonstrated only on HL7; 4-pack sweep is baseline characterization) carries forward. The framework reframe **layers on top**: HL7 becomes §3 headline within the framework, not a competing claim.
- The pipeline-composition honesty (§7b.8 — scheduling BLOCK = artifact_judge, not safety_prescreening) stays.
- The bench's measurement protocol (eval-spec §2.4 reportability gate, deterministic split, N≥10 + bootstrap CI) stays.
- The narrow-scope discipline. This is still a framework paper, not a "we-beat-baseline-by-X" paper.

## Single next runnable step

The 1-day council-confidence-mining script on the 28 missed HL7 defects (D2). Closes paper 1's headline measurement. Everything else in the framework reframe is doc-only editing on top of existing measurements.

Suggested script location: `scripts/measure_council_confidence_hl7.py`. First check `out/run1_archive/hl7*` and `LithrimPipelineBackend._parse` raw payloads before re-running the council — if confidence values were persisted, the experiment is $0.

## Audit source artifacts for these decisions

- This session's conversation (2026-05-26), four parallel audit subagents
- `HANDOFF_2026-05-21.md` — Phase 1 close
- `HANDOFF_2026-05-23.md` — Phase 2 close + first reframe decision
- `PAPER_OUTLINE.md` 2026-05-22 scope-change note (critique-pass deferral)
- `PAPER_OUTLINE.md` 2026-05-23 reframe note (HL7 + silent-confident-certification as headline; 4-pack sweep as baseline characterization)
- `lithrim-backend/CLAUDE.md` — diagnose-before-edit gate, four-pillar architecture description, eval spec references
- `lithrim-backend/docs/strategy/POSITIONING_ANALYSIS_agentic_ai_value.md` (2026-04-04) — 4-pillar value reframe
- `lithrim-backend/docs/pitch/PitchDeck_HMC_RFP_Refresh.md` — 9-procurement-question framework
- `lithrim-backend/docs/sales-outreach/` — design partner agreement, prospect list, outreach templates (Tier 1: Zato AI, Prosper AI, SuperDial, Hello Patient)
- `etlp-mapper/src/etlp_mapper/handler/copilot.clj` + `copilot/engine.clj` — Jute Copilot implementation
- `lithrim-bench/scripts/_gen_strict_hl7_mapping.py` — reproduction script for mapping 25 → mapping 93
- `lithrim-bench/validators/hl7_adt_a04_strict.yaml` — generated strict validator (frozen artifact)
- `lithrim-sdk/README.md` + `lithrim-sdk/lithrim/__init__.py` — SDK public surface
- `v0-lithrim-landing-page/app/page.tsx` + `components/hero-section.tsx` — landing page positioning copy

## Open framing question intentionally left open

Paper 1's framing tradeoff between **"framework paper backed by HL7 measurement"** and **"HL7 paper extended with framework architecture sections"** is left to the drafting session. Both versions of paper 1 land the framework reframe; they differ in which is the load-bearing claim and which is the supporting evidence. My read from this session: **lead with the framework as the contribution; let HL7 + silent-confident-certification carry the measurement weight inside §3.** But the drafting session should pressure-test this against the actual abstract that comes out.

---

# Amendment — 2026-05-26 (same day, later)

User pressure-tested the framework-paper framing with two pushbacks: (a) "structural validation isn't big TAM" → addressed in prior turn by promoting umbrella positioning; (b) **"the single-finding paper is just stating something obvious"** → triggers a deeper rethink. Honest re-audit of what's actually novel in the work:

| Asset | Genuinely novel? |
|---|---|
| HL7 0/28 → 28/28 | No. Validator built for spec catches spec violations. |
| Silent confident certification | Rhetorically sharp; research-wise expected (LLMs are known overconfident OOD). |
| Decision-vs-attribution gap 5.73× | Methodologically novel, but niche. |
| Worst-of composition | 40-year-old defense-in-depth. |
| Four-pillar architecture, deterministic provenance, eight-link chain, release-gate primitives | Engineering / regulatory infrastructure, not research. |
| **Jute Copilot — generate→test→refine + merge mode + confidence-graded retry, lifting HL7 ADT^A04 coverage from 2/5 → 5/5 in one call from public spec text** | **Genuinely novel. Nothing comparable published.** |

**The only thing in this work that is not "obvious-once-stated" is the Jute Copilot.** The earlier framework-paper-as-Paper-1 framing wrapped the obvious result in broader scaffolding; promoting the copilot to a footnote there did not make it the contribution. The single-finding-paper framing led with an obvious finding.

This amendment restructures D1, D3, D6, D7 to make **the Jute Copilot the lead contribution of Paper 1**.

## A1 — Restructure D1 (rescope)

**Was:** Paper 1 is the four-pillar framework paper.

**Is:** Paper 1 is the Jute Copilot paper. Working title: *"Closing the Validator-Authoring Bottleneck: Generative Production of HL7 Conformance Validators and Their Composition with LLM-Judge Councils on a Clinical Artifact Benchmark."*

**Lead argument:**

> Hand-authoring domain conformance validators is the bottleneck in deploying structural validation alongside LLM-judge councils in regulated industries. We show that a single LLM call with a generate→test→refine loop and confidence-graded retry can produce a covering HL7 v2 ADT^A04 conformance validator from public spec text — extending a 16-check field-presence template with three format / value-set / cross-segment-consistency checks, lifting coverage from 2/5 defect classes to 5/5 in one call at the highest confidence level. On a synthetic deterministically-labeled clinical artifact benchmark, an LLM judge council (gpt-4.1, three-judge ensemble at the published mid-80s accuracy ceiling) approves spec-violating ADT^A04 messages 28/28, unanimously and at high confidence — a failure mode that does not close with judge accuracy because the judge reasons about meaning rather than parsing fields. Composing the generated validator with the council under a worst-of rule recovers the entire defect class while preserving clean correctness. We release the benchmark, the copilot reproduction script, and the generated validator YAML.

**Section structure for Paper 1:**

- §1 — The validator-authoring bottleneck (motivation: spec exists, validators are slow, judges fill the gap unreliably)
- §2 — Generative validator composition: the Jute Copilot mechanism (generate→test→refine loop, merge mode, confidence-graded retry — **full disclosure**)
- §3 — Benchmark + evaluation protocol (Synthea, 5 packs, deterministic labels, N=10 test-split)
- §4 — Demonstration: mapping 25 → mapping 93 in one call from public HL7 v2 spec text
- §5 — Why this matters: silent confident certification (the failure mode the copilot's output prevents)
- §6 — Composition results: worst-of with the generated validator recovers 28/28 at 12/12 clean correctness
- §7 — Complementary finding: decision-vs-attribution gap (5.73×) — why surfacing evidence beats surfacing codes
- §8 — Threats to validity (synthetic benchmark, single-spec demonstration, scoped to ADT^A04)
- §9 — Release: benchmark generator + copilot reproduction script + generated validator YAML

## A2 — Restructure D3 (Jute Copilot disclosure)

**Was:** name the copilot in passing; withhold the system prompt + Jute DSL spec injection + retry logic for Paper 2.

**Is:** **full mechanism disclosure in Paper 1.** Publish the system prompt, the Jute DSL spec injection structure, the generate→test→refine + merge-mode logic, the confidence-grading scheme. Release `scripts/_gen_strict_hl7_mapping.py` as the reproduction script. Release `validators/hl7_adt_a04_strict.yaml` as the generated artifact.

**Rationale for the disclosure flip:**

- Priority-dating a novel mechanism > a few weeks of replication risk, **especially at our stage where there is no distribution to lose**.
- The published *idea* is harder to clone than initially weighted: the implementation surface is Clojure + Jute + domain-specific prompt + LangChain-style retry + integrated with a production validator engine. A clone of the *concept* in 2–3 weeks does not produce a deployable system in 2–3 weeks.
- The product moat is the integrated stack (copilot + validator engine + SDK + benchmark + audit infrastructure), not the copilot algorithm in isolation. Disclosing the algorithm does not disclose the product.
- "First paper on generative conformance-validator composition" is a category-anchoring priority claim that compounds over years.

## A3 — Restructure D6 (disclosure table)

The Jute Copilot row flips from "withhold mechanism" to "publish, full mechanism, with reproduction script." All other rows in D6 stand as written:

| Asset | Decision (amended) |
|---|---|
| 4-pillar framework | Paper 2 (was Paper 1) |
| HL7 result + silent-confident-certification | **Paper 1** (motivation + demonstration in §5–§6) |
| Trace-level provenance architecture | Paper 3 (unchanged) |
| **Jute Copilot mechanism** | **Paper 1, FULL disclosure** (was Paper 2, withhold) |
| Eight-link evidence chain hashing scheme | Withhold (unchanged) |
| ~80-flag safety taxonomy | Reference 6, withhold full (unchanged) |
| Failure clustering algorithm + patch templates | Withhold, demo in product (unchanged) |
| Release-gate primitives | Paper 2 §7 (was Paper 1 §7) |
| Agent KPI weighting | Withhold (unchanged) |

## A4 — Restructure D7 (staged disclosure sequence)

**Was:**
- Paper 1 (now, 1-week sprint): framework paper
- Paper 2 (3–6 months): Jute Copilot mechanism
- Paper 3 (6–12 months): trace-level audit

**Is:**
- **Paper 1 (now):** Jute Copilot paper — *"Closing the Validator-Authoring Bottleneck"*. Tight, sharp, single-mechanism contribution + the demonstration on HL7 + the silent-confident-certification motivation + the decision-vs-attribution complementary finding. **Ships paired with framework deck refresh + first dispatched outreach wave + a LinkedIn long-form post.** arXiv first to establish priority date.
- **Paper 2 (3–6 months, paired with design-partner announcements):** the framework paper. Now the four-pillar contribution lands when there are customer logos to anchor it, and Paper 1 is already cited from it.
- **Paper 3 (6–9 months):** trace-level audit + multi-step agent evaluation paper.

**Effort to ship Paper 1 (amended scope):**

- 1-day council-confidence experiment (gates §5 — measures the confidence distribution on the 28 misses)
- §2 mechanism write-up (full disclosure of generate→test→refine + merge mode + retry logic): ~2 days
- §1 / §4 narrative pull-through: ~1 day
- Pull existing §7 (decision-vs-attribution gap) into Paper 1's §7: ~half day
- Abstract rewrite: ~half day
- Threats section adjustment: ~half day

Total: **4–5 days post-experiment**, mostly drafting from existing material.

## A5 — What this preserves

- The 2026-05-22 + 2026-05-23 scope-change notes on `PAPER_OUTLINE.md` stay verbatim.
- The 2026-05-26 reframe paragraph on `PAPER_OUTLINE.md` gets a parenthetical pointer to this amendment (the framework-paper framing in that paragraph is now Paper 2, not Paper 1).
- The narrow-scope discipline from `PAPER_OUTLINE.md` §11 stays.
- D2 (silent-confident-certification headline) stays — but is now Paper 1 §5 motivation, not Paper 1 §3 lead.
- D5 (pipeline-composition honesty, scheduling +71pp = artifact_judge) stays.
- The 1-day council-confidence experiment remains the single gating runnable.

## A6 — Open question intentionally left for the drafting session

How prominent should the decision-vs-attribution gap be in Paper 1 — §7 with a short framing as "complementary finding," or promoted to a co-headline with the copilot? My read: **§7 complementary finding.** The copilot is the load-bearing contribution; the gap is the methodological finding that makes the copilot's output (deterministic structural codes) preferable to the council's (noisy taxonomy codes). It supports the copilot story rather than competes with it.
