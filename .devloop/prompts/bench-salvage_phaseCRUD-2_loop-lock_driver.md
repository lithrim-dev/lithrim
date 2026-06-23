# Driver — `bench-salvage` phase `CRUD-2`: lock the create→assign→grade loop (BYOK-backed)

> **Bundle ID:** `bench-salvage-phaseCRUD-2-loop-lock-driver`
> **Version:** v1 · **Authored:** 2026-06-23 · **Last re-verified against code:** 2026-06-23 (Phase 1a, monitor)
> Release context: `docs/COMMUNITY_RELEASE_v1_PLAN.md` Cycle 2 (CRUD rewire). The frozen council engine is NEVER touched.

---

## KICKOFF (paste into a fresh executor session — or spawn as the devloop-executor subagent)

```
You are the EXECUTOR for the .devloop/ cycle: bench-salvage phase CRUD-2 (loop-lock).

Read in this order:
  1. .devloop/personas/EXECUTOR.md
  2. .devloop/prompts/bench-salvage_phaseCRUD-2_loop-lock_driver.md   (this doc)
  3. docs/COMMUNITY_RELEASE_v1_PLAN.md  (Cycle 2 section)
  4. apps/bff/app.py:596-700  (run_eval_endpoint + _grade_case: the BFF half of the loop)
  5. scripts/run_eval.py:248-360  (run(): the assignments/models threading + the replay-ignores wrinkle)
  6. tests/test_byoc_provider.py  (the build_trio(models=) seam pattern to mirror)

Then post your plan-review per EXECUTOR.md. Do not write code until I say "go".
```

---

## 0. Why this cycle (the done-bar)

Cycle 2's done-bar: **"create a judge → assign a lens → grade, on the user's key, end-to-end, tested (create → grade loop)."** A read of the surface shows the CRUD plane is already mature — agent/judge/flag/ontology/grounding-contract all have C/R/U/D + admissibility gates + audit + tests. **The one genuine gap is that the create→grade LOOP ITSELF is untested end-to-end**, and BYOK model-threading through that loop is untested. This cycle LOCKS the loop with tests-first acceptance, ties in the Cycle-1 BYOK seam, and fixes any breakage the tests surface (diagnose-before-edit). It is mostly tests — that is correct: the test IS the deliverable that makes the loop a guaranteed contract.

**The load-bearing wrinkle (verified run_eval.py:284):** `assignments`/`models` are **ignored on replay/live** — only the `in_process` authored trio (`build_authored_semantic_stage` → `build_trio(assignments=, models=)`) consumes them. So the loop is proven OFFLINE/$0 in two halves: (a) the BFF persists + threads the authored config into the grade call (spy `run_eval.run`); (b) `build_trio(assignments=/models=)` makes the council consume it (render assertion + the existing ClaudeCliLM binding). No paid grade — the live grade is already attested (`docs/research/PROOF_byok_openai_council_2026-06-23.md`).

---

## 1. Pre-flight reading (ordered)

1. `docs/COMMUNITY_RELEASE_v1_PLAN.md` — Cycle 2 done-bar + scope boundaries
2. `apps/bff/app.py:596-700` — `run_eval_endpoint` (596) → `_grade_case` (621) → `list_judges` (639) → `assignments` (640) / `models` (646) → `run_eval.run(assignments=, models=)` (671). **The BFF half of the loop.**
3. `apps/bff/app.py:1418-1620` — `_validate_judge_assignment` (1418, owner↔emit gate), `put_judge_endpoint` (1525), `delete_judge_endpoint` (1597). **The judge-author write-path.**
4. `scripts/run_eval.py:248-360` — `run()` signature (248), `assignments` (255) / `models` (256) params, the docstring's **replay/live-ignores wrinkle (284)**, the `build_authored_semantic_stage` → `build_trio` consumption (305-346).
5. `tests/test_byoc_provider.py` — `build_trio(models={...})` seam pattern (the ClaudeCliLM binding is already proven here — reuse, don't duplicate).
6. `tests/test_byok_openai.py` — the Cycle-1 BYOK seam (per-role openai model binding) — context for "on the user's key".
7. `lithrim_bench/harness/config.py` — `JudgeConfig` (role, model, assigned_flags, validator_refs) + `list_judges`/`save`.
8. `.devloop/state/STREAM_bench-salvage.md` — stream state + open seams.

> **Citation drift:** the line numbers above were grepped 2026-06-23. If any have shifted on read, HALT and surface (per EXECUTOR.md). app.py is large and concurrent sessions touch it.

---

## 2. Deliverables (file-by-file — TESTS FIRST)

1. **`tests/bff/test_crud_grade_loop.py`** (NEW) — the acceptance tests, written first, RED before any code:
   - **A1a** `test_authored_lens_threads_from_put_judge_to_the_grade` — via a BFF `TestClient` + temp config DB: `PUT /v1/judges/{role}` with a chosen `assigned_flags` subset → `POST /v1/run-eval` with `run_eval.run` SPIED (monkeypatched, $0, no real grade) → assert the spy received `assignments={role: <authored_flags>}` (the persisted JudgeConfig threaded into the grade call). Mirror the `bff_client` fixture in `tests/test_byoc_provider.py` / `tests/bff/`.
   - **A1b** `test_build_trio_consumes_the_authored_lens_in_the_rendered_prompt` — OFFLINE ($0): `build_trio(ontology=<ont>, assignments={role: <lens>})` → assert that role's rendered judge prompt (`render_role_questions` / the bound `JudgeSignature.role_key_questions`) reflects the authored lens (the council CONSUMES the assignment). If an equivalent assertion already exists, EXTEND it / cite it rather than duplicate.
   - **A2a** `test_authored_model_threads_from_put_judge_to_the_grade` — `PUT /v1/judges/{role}` with `model="byo-claude"` → `POST /v1/run-eval` (spy) → assert the spy received `models={role: "byo-claude"}` (the persisted model selector threaded).
   - **A2b** `test_build_trio_binds_the_authored_model` — reuse/cite the existing `tests/test_byoc_provider.py::test_build_trio_models_*` that proves `build_trio(models={role:"byo-claude"})` binds `ClaudeCliLM`. If it already fully covers A2b, A2b is a citation in the session log, not a new test (no duplication).
   - Each must fail meaningfully before the loop is verified/fixed (RED). If the loop already works (likely), A1b/A2b may be GREEN on write — that is fine; the NEW gate is A1a/A2a (the BFF-threading half), which must be RED-then-GREEN if any wiring is missing, or GREEN-as-characterization if already wired (note which in the session log).

2. **`apps/bff/app.py`** — ONLY if a test surfaces a real threading gap in `_grade_case` (assignments/models not correctly read from the persisted JudgeConfig). Diagnose-before-edit: post the failing assertion + the line before editing. Likely NO change needed (the map says the loop works) — in which case this cycle is tests-only, which is a valid loop-lock.

> **Expectation:** this is a tests-dominant cycle. If A1a/A2a pass on first write, the deliverable is the locked contract + the session-log characterization. If they fail, fix the minimal threading bug (scoped, diagnosed).

---

## 3. Plan-review checkpoint (non-negotiable)

Post: understanding (1 para) · the exact test bodies you'll write (the spy mechanism for A1a/A2a; the render assertion for A1b) · which of A1b/A2b are NEW vs CITE-EXISTING · risks · any proposed deviation. Wait for "go".

---

## 4. Scope guardrails — NOT in scope (defer to a follow-up cycle)

- **Shell DELETE UI** (JudgeEditor/FlagEditor/AgentEditor delete buttons + modals) — the "exposed in the shell" done-bar item is a **separate Cycle 2b (shell, React/Vitest)**. Do not touch `apps/shell/`.
- **`PATCH /v1/agent`** roster add/remove endpoint — follow-up.
- **Workspace-isolation tests** (agents/judges scoped per workspace) — follow-up.
- **Error-shape standardization** across routes — follow-up (low value).
- **Criterion-writer UI** (`POST /v1/criterion` in the shell) — follow-up.
- **`validator_refs` execution** (the withstands-gate) — UAP-3b, deferred.
- **The frozen council engine** (`compliance_council.py`, `_apply_consensus`, the `judges_dspy.py` consensus seam) — NEVER touch; the seam-freeze guard must stay 0-delta.
- **No live/paid grade** — the loop is proven offline; the live BYOK grade is already attested.

If something feels load-bearing-but-unlisted, HALT and surface in plan-review.

---

## 5. Acceptance criteria (each a test written first)

- **A1.** The authored lens travels create→grade: `PUT /v1/judges` persists `assigned_flags` and `POST /v1/run-eval` threads them into the grade call — test `tests/bff/test_crud_grade_loop.py::test_authored_lens_threads_from_put_judge_to_the_grade` (A1a) + the council consumes them — `...::test_build_trio_consumes_the_authored_lens_in_the_rendered_prompt` (A1b).
- **A2.** BYOK model travels create→grade: `PUT /v1/judges` with `model="byo-claude"` threads into the grade call — `...::test_authored_model_threads_from_put_judge_to_the_grade` (A2a) + `build_trio(models=)` binds the provider — cite `tests/test_byoc_provider.py::test_build_trio_models_assembles_a_mixed_provider_council` (A2b).
- **A3 (Gate 0).** Full bare-CE suite GREEN + lint clean + the seam-freeze guard 0-delta (`tests/test_6bclean_seam_guard.py`). Run with `PYENV_VERSION=debuglithrim` (the `[council]`+`[bff]` env); the foreign-`spec.py` `test_pack_layer3` red is a known concurrent-session artifact (verify it's the ONLY pre-existing red, attributable to uncommitted `lithrim_bench/verification/spec.py`).

### Diagnostic stats (NOT gates)
- Whether A1a/A2a were RED-then-GREEN (a real wiring fix) or GREEN-on-write (characterization) — report in the session log.

---

## 6. Commit structure (atomic; tests commit first; SCOPED PATHSPEC)

**Critical — dirty index:** a concurrent session leaves `lithrim_bench/verification/spec.py` (staged) + `apps/shell/src/app.jsx` (unstaged) foreign-modified. **NEVER bare-commit.** Every commit uses an explicit scoped pathspec listing only this cycle's files. Verify with `git show --stat HEAD` after each.

1. **`test(crud): create→assign→grade loop + BYOK threading — red`** — the new acceptance tests.
2. **`fix(crud): <threading gap>`** — ONLY if a test surfaced a real bug (diagnosed, evidence block in the body).
   - If tests-only, skip the fix commit; the test commit is the deliverable.

Each body ends with: `Executed per bench-salvage-phaseCRUD-2-loop-lock-driver by session-2026-06-23-N.` + the Co-Authored-By trailer (`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`).

---

## 7. Verification checklist (before the session log)

- [ ] A1a/A1b/A2a pass; A2b cited to an existing green test
- [ ] `test(...)` commit precedes any `fix(...)` it covers (RED→GREEN if a fix landed)
- [ ] Full bare-CE suite GREEN + lint clean (re-run from clean; record the exact commands)
- [ ] Seam-freeze guard 0-delta
- [ ] No file in the diff outside §2 (no `apps/shell/`, no frozen council, no foreign `spec.py`/`app.jsx`)
- [ ] No services autostarted; no pushes/tags; no paid grade
- [ ] Session log at `.devloop/sessions/session-bench-salvage-CRUD-2-2026-06-23.json`

---

## 8. First move

1. Read `.devloop/personas/EXECUTOR.md`.
2. Read §1 pre-flight in order (re-verify the cited line ranges; HALT on drift).
3. Post plan-review per §3.

---

## 9. References

- Plan: `docs/COMMUNITY_RELEASE_v1_PLAN.md` (Cycle 2)
- BYOK A-LIVE proof (context for "on the user's key"): `docs/research/PROOF_byok_openai_council_2026-06-23.md`
- Stream state: `.devloop/state/STREAM_bench-salvage.md`

## Hardness
- [x] Routine cycle — monitor performs inline critique at close (cold devloop-critic subagent for Gate 0 + fidelity, since it touches the BFF grade path).
