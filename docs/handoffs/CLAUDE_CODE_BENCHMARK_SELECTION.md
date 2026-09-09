# Claude Code handoff: assess RAGTruth versus MedCalc for Lithrim

Paste the prompt below into Claude Code opened at the Lithrim repository. This is an
assessment task, not permission to build both experiments or run paid inference.

---

You are my research engineer and ML learning partner. Explore two experimental approaches
for Lithrim, evaluate their feasibility against the current implementation, and recommend
which we should pursue first. Do not assume either approach will produce a positive result.

## Our goals

We want a project that can:

1. Test what Lithrim's deterministic grounding, judge council, feedback and audit trail add
   over simpler baselines.
2. Produce an externally scored, reproducible result against an established public benchmark.
3. Teach me actual ML through hands-on work, not only prompt tuning or agent orchestration.
4. Support an honest technical write-up and presentation, including negative or mixed results.

The two candidates are:

- **RAGTruth:** learn and evaluate hallucination detection against supplied sources, then
  measure the incremental contribution of Lithrim.
- **MedCalc-Bench Verified:** evaluate calculation answers and evidence-backed checks, then
  measure whether Lithrim improves outcomes beyond a model with calculator access.

These are bounded tests of components of the broader enterprise-governance hypothesis.
Neither can, by itself, validate enterprise compliance, clinical safety, an employee digital
twin, or a self-improving company knowledge system.

## Scope and operating rules

- Repository: `/Users/aregee/Workspace/github.com/lithrim-bench`.
- Expected existing UI: `http://localhost:5180`; BFF: `http://localhost:8787`.
- Follow `AGENTS.md` and any applicable nested instructions. Start with `README.md` and the
  orientation documents it and `AGENTS.md` require.
- Inspect `git status` first. Preserve all existing work, including the Archer starter under
  `repro/archehr/`, its tests, and unrelated untracked files. Do not delete or replace it.
- Assessment only: inspect code, documentation, public upstream sources and existing results.
  Report code capability separately from what is confirmed in the live service.
- Check service health before inspecting the running application. Never start, restart,
  reconfigure or switch its active workspace. If unavailable, report that live inspection
  stopped; any continued analysis must be explicitly repository-only.
- No paid inference, fine-tuning, GPU rental, credentialed data, bulk dataset/weight downloads,
  secret inspection, dependency changes, commits, pushes, publishing or deployment.
- Do not run downloaded scripts or model-generated code. Use public documentation and small
  public samples for feasibility checks; do not bypass access restrictions.
- Read-only, offline diagnostic tests are permitted when scoped and their prerequisites are
  already available. Record commands, failures and skips without silently fixing the repo.
- The only new persistent files authorized in this task are assessment/report artifacts in
  a new, non-overwriting directory under `out/benchmark-choice/`. Confirm this path is ignored
  before use; if it is not, return the report in the conversation instead. No engine edits,
  taxonomy edits, live grading jobs or changes to tracked demo files.
- Never edit the frozen council consensus/confidence seam. Any future implementation proposal
  must respect the pack system, sanctioned data surfaces and tests-first workflow.
- If parallel investigation is available, assign one read-only researcher per candidate,
  with a shared checklist. Otherwise examine both sequentially. Lack of subagents is not a
  blocker.

## Phase 1: establish what Lithrim already does

Inspect the relevant architecture, capability card, connector specification, flag lifecycle,
holdout-hygiene policy, grading interfaces and tests. Specifically inspect:

- `samples/ragtruth/README.md`, the sample cases and baseline provenance.
- `scripts/ragtruth_cases.py` without running its download/rewrite path.
- The grounding tools in `lithrim_bench/verification/tools.py` and their actual call paths.
- Existing pack/plugin interfaces for adding a domain-specific verifier.
- `repro/archehr/` for reusable assessment/scoring patterns, without assuming its adapters
  apply to either candidate.

Produce a capability table: capability, implemented entry point and `file:line` evidence,
existing test evidence, live verification status, reuse opportunity, and missing work.

Establish whether Lithrim can currently ingest the artifacts, invoke the intended checks,
emit usable feedback, support a bounded revision cycle, and export enough provenance for
independent scoring. Do not infer that an evaluation harness already trains models.

## Phase 2A: investigate RAGTruth

Primary starting points; verify their current contents and record revisions:

- https://github.com/ParticleMedia/RAGTruth
- https://github.com/ParticleMedia/RAGTruth/tree/main/baseline
- https://aclanthology.org/2024.acl-long.585/

### Research questions

1. What exact task, splits, annotation semantics, evaluation scripts and published baselines
   should we target? Distinguish response-level detection from span localization.
2. Which assets are publicly accessible, under which terms, including underlying source
   content? Is there a current submission/leaderboard mechanism, or primarily paper baselines?
   Do not equate a public dataset with an active leaderboard.
3. How much of the existing five-case integration is reusable for a proper benchmark runner?
4. What verifiable claims can the current floor check, and what remains semantic judgment?
5. What is the smallest useful supervised-learning task for a beginner on available hardware?

### Required experimental design

- Input to the detector: source material and a fixed generated response. Gold labels are
  evaluator/training targets, never detector inputs or runtime grading context.
- Reproduce upstream annotation/scoring conventions, including special label flags, quality
  filters, offset handling and aggregation. Document any deviation as a separate evaluation.
- Preserve original benchmark partitions. Derive validation from training data with grouping
  by source ID; audit source overlap and near duplicates. Do not use test labels for tuning.
- **Prior exposure must be audited:** the local sample README reports test-set analysis that
  informed floor behavior. Verify its scope, disclose it, and distinguish benchmark comparison
  from untouched-holdout evidence. A new split of already-inspected test rows does not erase
  exposure. Identify what independent evaluation would be needed for a stronger claim.
- The five-case queue was selected using labels and floor behavior. It is a demo, not an
  unbiased performance estimate. Replay scores are not fresh model runs.
- Propose staged baselines: a trivial predictor, a simple trained classifier, a suitable
  prompted/learned detector, the council alone, the deterministic floor alone, and selected
  combinations. Identify the minimum subset of these needed for the first credible study.
- Define a matched ablation: hold detector/council outputs and configuration fixed when
  measuring the floor's contribution. Do not change model families and attribute the entire
  change to Lithrim.
- Predefine how PASS/BLOCK/WARN maps to benchmark predictions. Report standard metrics for
  all cases plus coverage, abstentions, false clears and false blocks; abstention is not a
  correct answer. Avoid a composite Lithrim score replacing the official benchmark score.
- A future rewriting experiment needs new labels or an independently validated evaluator:
  RAGTruth's original response spans do not remain gold for newly generated text.

### Learning progression

Specify a beginner baseline that actually fits parameters, followed by an optional small-model
fine-tune and later span detection. Explain what each teaches: leakage, feature construction,
loss, optimization, validation, class imbalance, calibration and error analysis. A lexical
classifier may learn superficial cues; treat that as a baseline limitation, not grounding.
Estimate hardware and cost with assumptions, without downloading weights or launching jobs.

## Phase 2B: investigate MedCalc-Bench Verified

Primary starting points; verify their current contents and record revisions:

- https://github.com/nikhilk7153/MedCalc-Bench-Verified
- https://huggingface.co/datasets/nsk7153/MedCalc-Bench-Verified
- https://github.com/ncbi-nlp/MedCalc-Bench
- https://arxiv.org/abs/2406.12036

### Research questions

1. Which corrected dataset release and evaluator should we pin? Which published results or
   current leaderboard entries use that exact version and protocol?
2. Verify public access, license, provenance, train/test sizes and calculator coverage. Do not
   describe all notes as synthetic; check the provenance categories.
3. What work is needed to wrap existing calculator implementations as Lithrim verifiers?
4. Where do input extraction, unit handling, formula variants, missing information and answer
   parsing introduce uncertainty? Separate arithmetic correctness from source correctness.
5. Which three relatively simple calculator families offer a useful development pilot, chosen
   before inspecting model outcomes? Explain their selection, not just their apparent ease.

### Required experimental design

- Give the system only task inputs allowed by the declared protocol. Keep annotated relevant
  entities, reference answers, answer bounds and reference explanations outside inference and
  runtime feedback. General formula references/tools can be allowed in explicitly declared,
  matched tool-assisted conditions; test-row solutions cannot.
- A correct derived number may be absent from the note. A value-membership check is therefore
  not a drop-in calculation verifier. Specify the missing tool/contract and evidence schema.
- Validate selected calculators against independent test cases/reference definitions and audit
  version changes. Determinism and a name containing “Verified” do not establish correctness.
- Audit evaluator safety. Do not execute model text via `eval` or unrestricted code execution.
  If safe parsing changes upstream behavior, document it and test semantic equivalence before
  claiming comparable scores.
- Minimum comparison arms:
  A. model without calculator tools;
  B. same model with calculator access;
  C. same model, same calculator access, plus Lithrim governance and bounded feedback.
  Match model, inputs, reference access and inference/retry budgets where measuring incremental
  value. Add a matched retry/control arm if C otherwise receives extra opportunities.
- Distinguish detection/blocking from answer repair. A blocked wrong answer is not a correct
  benchmark answer; report overall final-answer accuracy, acceptance coverage, error rate
  among accepted answers, false blocks, successful repairs, regressions, latency and cost.
- Separate closed-book/model-only benchmark reproduction from tool-assisted system results.
  Do not present them as equivalent leaderboard conditions unless the target protocol allows it.
- Start with approximately 60 development cases across the selected calculators, drawn from
  training data with a fixed rule and held-out development validation. This is a pilot, not a
  full-benchmark or leaderboard score. Audit note-ID overlap before any later test evaluation.

### Learning progression

Explain what an evaluation-only pilot teaches and what additional model training would teach.
Assess a small supervised input-extraction task or fine-tune using training annotations, with
held-out extraction and final-answer evaluation. Do not train a model to imitate arithmetic
where a reliable calculator already solves the task without explaining the research purpose.

Evaluate RL only as a later option: define the trainable policy, actions, environment, reward,
update algorithm and independent evaluation. Identify reward hacking and wrong-input/correct-
arithmetic risks. Feedback retries or ordinary fine-tuning must not be labelled RL.

## Phase 3: compare and recommend

Use one evidence-backed scorecard for both candidates. Score each criterion from 1 (poor fit
or substantial unresolved work) to 5 (strong fit with verified supporting assets), attach a
confidence level and cite evidence. Mark unknowns rather than inventing precision.

Default decision weights, explicitly assumptions rather than my confirmed preferences:

| Criterion | Weight |
|---|---:|
| Fit to current Lithrim and ability to isolate its incremental value | 30% |
| Accessible, meaningful hands-on ML learning progression | 25% |
| Benchmark comparability and credible external evaluation | 20% |
| Engineering effort, runtime cost and operational simplicity | 15% |
| Presentation/write-up clarity, including negative findings | 10% |

Show whether the recommendation changes when ML learning or the deterministic-governance demo
is prioritized. Do not compare RAGTruth F1 numerically with MedCalc accuracy to choose a winner.

For each candidate, give ranges for engineering effort and inference/training cost, with
assumptions, prerequisites and uncertainty. Distinguish reusable work from new work. Include
licensing, annotation quality, contamination, evaluator reliability and publication caveats.
Use current official pricing only if estimating monetary costs; do not invent quotations.

Recommend one first experiment, not two full implementations. State the strongest reason
against your recommendation and the evidence that would reverse it. “Neither is ready” is
acceptable if grounded in specific blockers and a practical next step.

## Deliverables and stopping point

Produce:

1. `ASSESSMENT.md`: executive recommendation, verified capability inventory, both candidate
   designs, weighted comparison, risks and an explicit implemented/proposed/unknown distinction.
2. `EXPERIMENT_PLAN.md`: recommended minimum pilot, data contracts, baselines, leakage controls,
   tests-first acceptance criteria, metrics, provenance fields and decision gates for scaling.
3. `LEARNING_PLAN.md`: short milestones with what I should inspect, explain or implement myself
   before proceeding; separate evaluation engineering, supervised ML and possible later RL.
4. `PRESENTATION_AND_WRITEUP.md`: a proposed title and 6–8 slide outline for each candidate,
   planned figures/tables, reproducibility checklist, and claims permitted by positive, mixed
   or negative outcomes. These are outlines, not fabricated results or finished slide decks.
5. `NEXT_IMPLEMENTATION_PROMPT.md`: a paste-ready prompt for the recommended pilot, including
   precise files/interfaces, a fixed scope, failing acceptance tests first, stop conditions
   and the model/budget decisions still requiring my approval.

Every empirical claim must link to repository evidence, a recorded diagnostic or a primary
external source. Include checked dates, upstream revisions and unresolved questions. Report
what was actually inspected/run and what was not. Do not imply publication acceptance or an
available leaderboard submission without verifying it.

In your final answer, lead with: which option first, why, the smallest credible result it can
produce, what ML I will learn, and what we need to authorize next. Stop after assessment and
the handoff; do not begin implementing the recommendation.
