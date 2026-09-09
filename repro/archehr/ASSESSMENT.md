# Initial ArchEHR-QA readiness assessment

Assessment date: 2026-09-08. Repository baseline: `6239d265da47ecc870b1102f2abd85d6050567f0`.

## Executive summary

Lithrim is relevant to an **evidence-grounding feedback experiment**, but its current grade is not
an ArchEHR-QA score. The proposed first study should test whether bounded, auditable feedback improves
a fixed model's evidence alignment on an independently scored benchmark. A positive outcome is a
testable possibility, not an assumption. Training/RL is unnecessary for this first causal question.

The delivered slice is working offline plumbing using one real Lithrim deterministic tool. It is
not yet the full judge-council/feedback/model-revision experiment and produces no clinical performance
claim. The document structure follows the Lithrim analysis conventions; the current repo's code and
capability card take precedence over older command-center positioning/configuration assumptions.

## Scope and evidence

Read the repository orientation/specification/capability/holdout documents, inspected the grounding,
verification and BFF integration surfaces, checked live HTTP endpoints, and inspected the official
2026 scorer. No restricted benchmark records, model weights, secrets or provider credentials were
read. No paid inference, training, publication or deployment occurred.

Observed live evidence:

```text
GET localhost:8787/health -> {"status":"ok"}
GET localhost:5180 -> HTTP 200
GET localhost:8787/v1/workspaces -> active: demo-day
POST /v1/workspaces {name: archehr-initial, pack: _core} -> created
GET /v1/workspaces -> active: demo-day; archehr-initial present
```

The host has Python 3.12.8, pytest 9.0.3, Pydantic 2.13.4 and NumPy 2.4.4. The host Python lacked
the optional `openai` package in the guarded tests; that does not diagnose the separate running BFF
environment. No package installation was needed for the delivered offline tools.

## Findings

| Capability | Evidence | Meaning for the experiment |
|---|---|---|
| Three-state deterministic tools | `lithrim_bench/verification/spec.py`, `VerificationResult` | Reuse real checks and retain inconclusive results. |
| Numeric source membership | `lithrim_bench/verification/tools.py`, `ValueGroundingTool` | Useful bounded diagnostic; matching numbers cannot verify the relationship or claim. |
| Source/evidence suppressors | `lithrim_bench/harness/grounding.py`, `SourceGrounding`, `EvidencePresence` | Token/quote presence is not semantic evidence alignment; no blanket suppression. |
| Authored/injected council seam | `runtime/council/authored_stage.py`, `build_authored_semantic_stage`; `harness/grade.py`, `grade_inprocess` | Real semantic feedback can be added without editing frozen consensus; mocked judges prove only plumbing. |
| Native corpus ingest | `apps/bff/app.py`, `_native_eval_rows`, ingest preview/commit | Prepared unlabeled rows can enter the app without a model-based mapper. |
| Global workspace switch | `apps/bff/app.py`, `switch_workspace_endpoint`; `harness/workspace.py`, `set_active_workspace` | Reserve isolated workspace; don't change active scope during unrelated work. |
| Closed native tool-name set | `verification/spec.py`, `_KNOWN_TOOLS` | A genuinely new citation floor is not automatically manifest-only. Adapter integrity checks remain explicitly outside the native floor. |
| Existing study | `README.md`, `REPRODUCING.md`, `repro/` | Relevant mechanism/calibration evidence, not evidence that feedback improves a generating model on this benchmark. |

This setup does not change the frozen consensus, invent new taxonomy codes, assign constructed labels
to external rows, turn prose into a structured-record oracle, or claim terminology lookup solves
entailment. SNOMED may later be a separately disclosed external-knowledge arm; the initial proposed
run uses only supplied benchmark context.

## Benchmark target and independent outcome

**ArchEHR-QA 2026 Subtask 4, Evidence Alignment** supplies the answer and asks for supporting note
sentence IDs per answer sentence. Do not replace this with answer generation or note summarization.
The [organizer task specification](https://archehr-qa.github.io/#subtask-4-evidence-alignment)
and [pinned official scoring code](https://github.com/soni-sarvesh/archehr-qa-2026/blob/344b67e2f9c5d3c9510a77eb8bfd00b89f505b5b/evaluation/scoring_subtask_4.py)
are the comparison contract. Overall score is micro-F1 over unique answer/evidence links, on a 0–100
scale; macro scores are also emitted. Empty prediction sets yield zero precision/recall under this
scorer, not a perfect safety score.

The [official site](https://archehr-qa.github.io/) lists the extended Subtask 4 deadline as March 4,
2026, already past at assessment time. A public historical comparison may be possible, but current
organizer/Codabench scoring access and test gold availability have not been established. A successful
local evaluation is not an accepted leaderboard submission. Data are credentialed through PhysioNet;
public code does not imply unrestricted clinical-data access or redistribution.

## Proposed first comparison — not yet executed

Primary hypothesis: with the same base model, starting prediction, council signals and revision
budget, adding Lithrim's bounded deterministic feedback improves held-out link micro-F1.

| Arm | Prediction workflow | Purpose |
|---|---|---|
| A | Base model, no revision | Establish the model baseline. |
| B | Same starting output + one self-review revision | Measure benefit from another attempt alone. |
| C | Same starting output + recorded council feedback + one revision | Measure judge-assisted revision. |
| D | Same starting output and council feedback as C + deterministic diagnostics + one revision | Isolate the additional diagnostic contribution with D versus C. |

C and D must reuse identical recorded council signals and matching generator sampling/call limits.
B has no council expense; report all call/token/latency/cost differences instead of calling every
arm compute-matched. The delivered CLI currently prepares A and deterministic-only revision packets;
it does not execute B–D, combine real council signals, or enforce these arm budgets.

Use development data to select criteria and diagnose parsing. Freeze the final model/revision,
prompts, source cohort and all check parameters before any held-out result is inspected. Report full
coverage and failures, micro/macro precision/recall/F1, empty-link rate, invalid-output rate,
cost/latency, and changed links. Estimate paired uncertainty by resampling **cases**, recomputing
micro-F1 from pooled link counts; don't average per-case F1 and call it micro. Repeat model runs and
report variance before publication under the repo's reportability policy. A negative or null delta
is a valid result; do not tune on the test set until a win appears.

## Next decisions / blockers for real measurement

1. Authorized 2026 Task 4 input release and local path; independently controlled scoring key/access.
2. Verify the strict XML adapter on that release. The initial XML contract is inferred from
   [participant primary code](https://github.com/mo-arvan/archehr-qa-2026-uic-aihealth4all/blob/main/src/task.py),
   not a restricted organizer file. No key fallback is permitted.
3. Choose base model/endpoint and acceptable data handling, then approve spending/call limits.
4. Implement/test the real model and authored-council adapters, keeping inference and scoring apart.
5. Freeze a held-out comparison protocol and confirm official scoring/comparison access.

Do not describe the result as a trained company brain, validated clinical governor, employee digital
twin, regulatory certification or completed RL loop. If the controlled feedback experiment succeeds,
the supported claim is narrower: **Lithrim-assisted revision improved evidence alignment for this
model, dataset and protocol**, with the measured cost and limitations.

## Verification outcome for this setup

- Focused experiment + frozen-seam + neutral-pack + plugin + native value/review regression tests:
  **111 passed, 2 skipped**. Skips: optional host `openai` dependency and absent external healthcare pack.
  This was a targeted regression run, not the entire repository suite.
- Ruff lint and formatting checks passed on all new Python files; `git diff --check` passed.
- Smoke output: `out/archehr-initial-20260908/`; official synthetic-score output:
  `out/archehr-initial-20260908/official-smoke/` (ignored local artifacts).
- Native numeric diagnostic accepted the wrong-context matching number while leaving semantic
  support `null`; official fixture F1 was 0. This demonstrates a boundary, not a model improvement.
- No existing tracked files changed. New files are uncommitted; unrelated untracked user files
  were preserved. The only live-app mutation was creating the empty experiment workspace.
