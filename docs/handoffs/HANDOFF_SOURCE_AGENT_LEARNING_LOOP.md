# Review brief: Lithrim's source-agent improvement loop

Status: discussion draft for critical review, not an approved implementation plan.
Prepared: 8 September 2026.

Read this before `docs/handoffs/CLAUDE_CODE_BENCHMARK_SELECTION.md`. It clarifies the
intended learning target and updates the priorities of that earlier comparison. It does
not authorize executing the earlier prompt or starting either experiment.

## 1. What the owner is actually trying to demonstrate

The intended destination is **improving the source agent using evidence from Lithrim**,
not merely training a hallucination detector or showing that LLM judges disagree.

The proposed sequence is:

1. Use an open dataset to supply tasks and source information to a small external agent.
2. Capture its generated artifacts and actual execution telemetry in Lithrim's review queue.
3. Configure a reviewer for the workflow, informed by a knowledge base, requirements and
   available tools. Eventually the system can propose a workflow graph, ontology, reviewer
   responsibilities and tool/verification-contract mappings.
4. Review artifacts using both LLM findings and applicable artifact-level checks. Verify
   bounded claims against appropriate sources; surface what cannot be verified.
5. Accumulate findings, verification evidence, adjudications, corrections and provenance.
6. Use the verified corpus to propose changes to the **source agent's prompt**, run new
   simulations, and independently measure whether its outputs improve.
7. Subsequently use suitable corpus material to **train the source model**, then compare
   that candidate against the original and prompt-improved variants.

Reviewer improvement is a separate, potentially useful branch. It must not silently replace
the source-agent improvement objective.

The longer-term business hypothesis is that teams can produce more acceptable AI-assisted
work without a proportional increase in expert review and rework. The near-term study only
needs to demonstrate a bounded part of the mechanism. It does not need to prove enterprise
compliance, automatic company-wide knowledge discovery, or sustained business savings.

## 2. Proposed architecture and boundaries

### Configuration

KB and workflow requirements + permitted tool catalog
→ proposed reviewer/ontology/contract configuration
→ expert review, positive/negative/boundary tests, and version pinning.

The ontology describes what can go wrong and who reviews it. Contracts specify which claims
can be checked, against which sources, with which inputs and failure/abstention behavior.
A generated graph can organize these relationships; graph construction does not establish
that the represented requirements or evidence are correct.

An automatically generated contract is a proposal. Executability is not proof that it
expresses the right requirement. Tool errors, missing references and ambiguous extraction
must not become silent passes. A successful narrow check does not certify the whole output.

### Execution and review

Task input → source agent → output and trace → configured Lithrim review
→ verified findings, verified rebuttals and explicitly unresolved findings.

Checks need not all wait for a judge signal: applicable artifact-level floors can catch
declared defects that no judge raised. The scope and input evidence of every check matter.

### Improvement

Adjudicated development corpus → candidate prompt changes → validation simulations
→ optional source-model training → independent evaluation → approved candidate selection.

Use one frozen reviewer/contract configuration when comparing source-agent variants. If the
reviewer also changes, measure that in a separate experiment; do not move the grading target
while claiming the producer improved.

## 3. What inspection established in the current repository

These are repository-inspection findings, not a fresh live-service verification or a claim
that tests passed in this session. Re-resolve line references before relying on them.

| Component | Observed support and boundary |
|---|---|
| KB context | Retrieval assistance exists; the inspected KB handler is not an autonomous ontology generator or a verdict oracle. See [KB context handler](/Users/aregee/Workspace/github.com/lithrim-bench/apps/bff/agent/tools.py:989). |
| Assisted contract authoring | Editable contract suggestions exist. One path waits for human Save; a separate agent-composition path can persist through an audited gate. See [contract suggestions](/Users/aregee/Workspace/github.com/lithrim-bench/apps/bff/agent/tools.py:747). |
| Bounded generate/test/pin | An SME-selected tool/call and criterion can drive argument-mapping generation, a bidirectional test gate, preview, and explicit commit. This is not general autonomous KB-to-ontology discovery. See [criterion generation](/Users/aregee/Workspace/github.com/lithrim-bench/apps/bff/app.py:4139). |
| Configuration activation | A saved working ontology can take precedence for the next grade. Do not assume a universal inactive-draft/approval/promotion lifecycle already exists. See [ontology resolution](/Users/aregee/Workspace/github.com/lithrim-bench/apps/bff/app.py:288). |
| Correction records | Records connect judge outputs, contract results, before/after decisions and version provenance. They primarily describe corrections to reviewing, not complete corrected source-agent outputs. See [correction builders](/Users/aregee/Workspace/github.com/lithrim-bench/lithrim_bench/harness/correction.py:33). |
| Corpus projection | A thin, versioned projection links corrections to underlying records. The module explicitly treats it as provenance, not a new label authority. See [corpus projection](/Users/aregee/Workspace/github.com/lithrim-bench/lithrim_bench/harness/corpus.py:64). |
| Reviewer prompt optimization | The existing optimizer compiles few-shot examples for a judge and compares baseline/optimized performance. This is not model-weight training or source-agent prompt optimization. See [compile_judge](/Users/aregee/Workspace/github.com/lithrim-bench/lithrim_bench/runtime/council/judge_optimize.py:255). |
| Current calibration splitting | Workspace cases are sorted by case ID and split by position. This must not be reused unchanged for an external source-grouped benchmark. See [build_calib_rows](/Users/aregee/Workspace/github.com/lithrim-bench/lithrim_bench/harness/calib_corpus.py:25). |

The complete source-agent simulation, optimization and weight-training loop was not
established by this inspection. Assess the missing adapters and data contracts rather than
assuming either that everything exists or that the project starts from zero.

## 4. RAGTruth is the current preferred candidate, not a predetermined winner

RAGTruth is currently preferred for the combined reviewer, prompt-improvement and ML-learning
story. MedCalc remains a useful comparison and a possible compact deterministic-contract
demonstration. Assess the fit against the complete intended loop, not just ease of scoring.

RAGTruth supplies original generation prompts, source information, responses, model identity,
temperature and human hallucination annotations. It is not a complete agent tool-call trace
dataset. Instrument new runs to capture real tool activity; mark replays and simulated
events accurately, and never invent missing historical telemetry.

Keep two evaluation tracks distinct:

- **Reviewer benchmark:** score Lithrim on RAGTruth's original fixed responses using the
  original human annotations and an explicitly pinned scoring protocol.
- **Source-agent improvement experiment:** run our agent on task inputs and assess newly
  produced responses with independent adjudication or an appropriately validated evaluator.
  Original hallucination spans do not remain gold for newly generated or rewritten answers.

RAGTruth is not a collection of unique ideal answers or universally deterministic semantic
oracles. Its labels assess faithfulness of particular responses to their sources. A finding
that a span is unsupported does not automatically give the correct replacement response.

The local [RAGTruth sample documentation](/Users/aregee/Workspace/github.com/lithrim-bench/samples/ragtruth/README.md)
reports test-set analysis that informed floor behavior. Audit and disclose this exposure.
The five-case queue was selected using labels and floor behavior; it is not an unbiased
benchmark sample. Do not describe already-inspected rows as a pristine holdout.

For any new split, group related responses by source, audit overlap/near duplicates and
derive development validation from training data. Do not shuffle official benchmark test
rows into training via the existing workspace calibration splitter. Prior exposure is not
erased by renaming a split.

MedCalc should not be rejected on an unqualified claim that it is already solved at 98%.
The examined open-book audit reports 81.5% on a full test run and an optimistic 97.4%
composite estimate involving residual-error recovery and adjudication adjustments, not a
single ordinary full-test run at 98%. Nevertheless, a strong calculator-assisted baseline
is essential before claiming a benefit from model training or Lithrim.

Primary references checked during the discussion:

- [RAGTruth data schema and project](https://github.com/ParticleMedia/RAGTruth)
- [RAGTruth training/evaluation baseline](https://github.com/ParticleMedia/RAGTruth/tree/main/baseline)
- [RAGTruth paper](https://aclanthology.org/2024.acl-long.585/)
- [MedCalc-Bench Verified](https://github.com/nikhilk7153/MedCalc-Bench-Verified)
- [MedCalc open-book audit, including composite-estimate methodology](https://arxiv.org/html/2603.02222v1)

## 5. What the learning corpus must represent

Proposed minimum information, subject to a current-schema gap analysis:

- Stable task/source/run identity and split membership.
- Source-agent model version, full effective prompt or protected reference, generation
  settings, output, actual tool calls/results and source snapshots.
- Reviewer, ontology, contract and tool/reference versions.
- Findings and evidence spans, including whether their basis is human annotation,
  deterministic verification, a fallible model judgment, or unresolved evidence.
- Adjudicated status and any verified corrected output or preference pair.
- Cost, latency, retries and human intervention when actually measured.

Keep evaluator-only reference labels out of the source agent and runtime reviewer inputs.
Training labels may be used for authorized training on the training partition. Handle
secrets, personal information and retention deliberately; a complete trace is not permission
to log every credential or redistribute source material.

Include clean examples and audited cleared outputs, not only detected failures. Otherwise
the learning corpus reflects the reviewer's blind spots and escalation preferences.

Unresolved findings are not negative labels. An operational approval is not automatically
ground truth. Deterministic execution proves a result only within a correctly specified
contract and correctly grounded inputs. A rule-derived label must retain that limited scope.

## 6. Experimental progression and claims

### Milestone A: trustworthy review

Compare the same fixed outputs using judge-only review, applicable checks alone, and the
combined reviewer. Measure false clears, false accusations, coverage/abstention and cost.
Preserve official benchmark scoring separately from Lithrim's workflow decisions.

### Milestone B: source-agent prompt improvement

Use verified findings from development data to propose a new producer prompt. Compare the
original and revised prompts using the same model, tools, source access and evaluation
conditions. Validate new outputs independently. Include a matched generic-feedback or
judge-only-feedback control to distinguish Lithrim's contribution from ordinary prompt
iteration and extra inference effort.

This is a complete feedback loop, but it is not model-weight training.

### Milestone C: source-model training

Prepare independently checked targets or another justified training signal, select a
trainable source model, and measure whether training adds value beyond the prompt-improved
baseline. Preserve starting checkpoints and match relevant data/compute conditions when
comparing judge-only versus grounded-feedback training.

- Corrected target-response training is supervised fine-tuning.
- Preference-pair training is a separate choice requiring valid preference labels.
- RL requires a defined policy, actions, environment, reward and parameter-update procedure.
- Retrying with feedback or compiling few-shot prompts is not RL.

Do not assume every corpus is suitable for every training method. Training may produce no
benefit or regressions; that is a result, not grounds to loosen the evaluator.

### The meaning of “run the same cases clean”

Previously failed development cases are useful regression tests. Passing them after training
does not prove generalization. Compare all variants on the same independently held-out
evaluation tasks, unseen by training, prompt selection and reviewer/contract development to
the extent claimed. Use validation for iteration and reserve a final test; repeated tuning
against a nominal test set turns it into development data.

Report source-output quality as well as hallucination rate, so refusing everything, omitting
useful information or producing trivial answers cannot masquerade as success. A fallible
reviewer used to optimize the source agent cannot be the sole authority certifying its gains.

### Presentation and eventual business evidence

The presentation can progress from “judges disagree” to “bounded contracts yield traceable
feedback, and we test whether that feedback improves future outputs.” Benchmark novelty,
leaderboard eligibility and publication acceptance must be assessed, not assumed.

Later, a human-review study can test total cost per independently verified acceptable output,
including review time, rework and operating costs at a predefined quality threshold. This is
separate from the initial benchmark claim and is not a prerequisite for the narrow prototype.

## 7. Requested Claude review: assessment first

Critically review this brief against `AGENTS.md`, current repository code and primary
benchmark sources. Treat it as a hypothesis to assess, not a specification to obey blindly.

Please return:

1. Your understanding of the source-agent improvement objective, distinct from reviewer
   optimization, and any material ambiguity.
2. Which statements are supported, overstated, missing or incorrect, with code/source evidence.
3. A verdict on RAGTruth's suitability for the complete proposed loop; explain if a different
   dataset or a narrower first task is needed for a specific stage.
4. The smallest credible first milestone, what existing components it reuses, and the new
   adapters, labels, independent evaluation and permissions it would require.
5. A fair comparison design and go/no-go criteria for prompt optimization followed by actual
   model training, including failure cases that would refute the hypothesis.
6. A proposed presentation/write-up claim and its limits, without invented results.
7. Recommended changes to the earlier benchmark-selection plan, for approval before editing
   that plan or beginning implementation.

Scope: read-only investigation and a response in the conversation. Do not edit project or
application state, start/restart services, change workspaces, run paid inference/training,
install dependencies, download restricted data or model weights, or publish anything.
Preserve all existing work. If live inspection is necessary, follow the repository health
rules and stop that inspection if services are unavailable. Clearly distinguish inspected
code and reviewed tests from live behavior and tests actually executed.

Lead with your recommendation and strongest objection. Stop after the review.
