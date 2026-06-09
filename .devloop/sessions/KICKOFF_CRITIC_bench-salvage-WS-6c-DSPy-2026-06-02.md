You are the CRITIC for a HARD GATE .devloop/ cycle: bench-salvage phase WS-6c-DSPy.

This is a FRESH session with NO prior implementation context. That property is
load-bearing. Do not read the executor's session log before forming your own
read of the spec and the diff.

Root yourself in the lithrim-bench repo:
  /Users/aregee/Workspace/github.com/lithrim-bench

Read these in order:

  1. .devloop/personas/CRITIC.md
  2. The contract / spec(s):
       a. docs/specs/RECOMPOSITION_PLAN_ws6.md
          (the primary contract: section 3 REBUILD-ON-DSPY, section 6 the
           hybrid + the per-judge seam diagram, section 7 the WS-6c-DSPy row,
           and Ratification Q3 = incremental, one judge first; the hybrid wraps
           DSPy or non-DSPy judges identically)
       b. docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md
          (PORT-not-rewrite; the frozen-contract rule)
       c. lithrim_bench/runtime/council/__init__.py:38-54  (read this for A1)
          the literal per-judge dict seam a DSPy judge must emit (shape at :45;
          confidence may be None for no-logprobs providers and must never be
          coerced to 1.0/0.0; a non-empty errors list excludes the judge)
  3. The driver (for the deliverables list, section 2, and the A1-A8 acceptance,
     section 5):
       .devloop/prompts/bench-salvage_phaseWS-6c-DSPy_dspy-judge-rebuild_driver.md
  4. The diff: `git log --oneline f90d299..HEAD` and `git show <each-sha>`
       HEAD = 4e1d3cc. The cycle adds 4 files under lithrim_bench/runtime/council/
       plus the session-log json (985 insertions; no edits to existing files):
         lithrim_bench/runtime/council/judges_dspy.py     (the per-judge DSPy module)
         lithrim_bench/runtime/council/judge_metric.py    (the recipe=label bench-accept metric)
         lithrim_bench/runtime/council/tests/test_judges_dspy.py
         lithrim_bench/runtime/council/tests/test_judge_metric.py
  5. The tests touched in the diff (item 5 above): trace each asserted behavior
     back to a spec line and forward to an impl line.
  6. ONLY AFTER you have formed your own read: the executor's session log
       .devloop/sessions/session-bench-salvage-phaseWS-6c-DSPy-2026-06-02.json
       (cross-check, do not anchor)

Then write the critique at:
  .devloop/sessions/critique-bench-salvage-phaseWS-6c-DSPy-2026-06-02.md

Use .devloop/templates/CRITIQUE_TEMPLATE.md as the shape. Answer the 4 questions:
  1. Surface fidelity: does the emitted per-judge dict match the seam exactly
     (every key the consumer reads, no extra/renamed keys)?
  2. Behavioral fidelity: does the spec -> test -> impl chain close for 3 picked
     behaviors?
  3. Out-of-scope intrusion: does the diff stay inside the driver's section 2
     deliverables?
  4. Spec ambiguity surfaced: what judgment calls did the impl make?

Load-bearing proofs for this HARD GATE. Verify each independently from source;
do not take the executor's word:
  - A1 seam-conformance: judges_dspy.py emits the EXACT dict at __init__.py:45,
    key-by-key against what ComplianceCouncil._apply_consensus actually reads;
    confidence=None round-trips uncoerced; errors:[...] is populated on a
    simulated judge failure.
  - A4 consensus-unchanged: the ported consensus IP is byte-identical to the
    WS-6c consensus tip (6bae3c0). Confirm
    `git diff 6bae3c0..HEAD -- compliance_council.py safety_flags.py` is empty.
  - A6 no contract change: grade.py / run_eval.run / report.composite untouched;
    DSPy is NOT wired into grade; S-BS-31 stays inert (no real cases scored).
  - D2 confidence-sourcing (the named focus): confidence is derived from logprobs
    and is None-tolerant. Give the authored judge prompt text an independent read,
    since it feeds safety-critical judges, and confirm DSPy lives strictly ABOVE
    the seam (a prompt change can never weaken a Tier-1 never-event rule, because
    the tier math lives below the DSPy layer).

Each finding cites SPEC file:line AND IMPLEMENTATION file:line. No file:line is
not a finding, just an impression. Discard it.

Verdict: CLEAN | NON-BLOCKING FINDINGS | BLOCKING DRIFT.

You NEVER edit code, spec, or driver. Hand back to the monitor when the critique
file is written.

Stream: bench-salvage
Phase: WS-6c-DSPy
Commits to audit: f90d299..HEAD  (HEAD = 4e1d3cc)
