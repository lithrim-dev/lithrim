# DRIVER — PHASE2-B: the create-judge endpoint + roster wire-in (BFF + runtime)

**Read first:** `docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md` · SPEC §8 · the PHASE2-A
return (the `splice_production_judge` signature + its admissibility errors — already merged at the
driver HEAD). **OWNER SIGNED OFF 2026-06-25** on the snapshot-authoring surface.

**Depends on PHASE2-A** (merged): `lithrim_bench/harness/judge_authoring.py`
(`splice_production_judge`, `write_role_prompt`) + the `pack.assert_judges_known` wall-#4 relaxation.

**FROZEN SEAM — NEVER TOUCH:** `compliance_council.py` `_apply_consensus`. **NEVER touch `app.jsx`.**
This is BACKEND-ONLY (`apps/bff/app.py`, `lithrim_bench/runtime/council/judges_dspy.py`,
`scripts/run_eval.py` + tests). A parallel agent owns the frontend — do NOT touch `apps/shell/`.

## DELIVERABLES
### 1. Roster wire-in — make an authored new role VOTE (the param plumbing already exists end-to-end)
- **`runtime/council/judges_dspy.py` `build_trio` (~410-413):** relax the `V2_ROLES` allowlist to the
  active pack's `pack_production_judges()` (lazy import). `selected = tuple(roles) if roles else
  tuple(pack_production_judges())`; validate `unknown = [r for r in selected if r not in
  pack_production_judges()]` → raise on a truly-unknown role. **Byte-identical when production_judges ==
  V2_ROLES** (the `_core`/support default — verify). Keep `V2_ROLES` as the back-compat constant.
  `build_judge_lm` already binds any role via `.get(role, default)` (PROBE Q5) — no map edit needed.
- **Derive + pass `roles=`** at the grade call sites so the authored roster reaches `build_trio`:
  - `apps/bff/app.py` `_grade_case` (~833) AND `scripts/run_eval.py` (CLI `main`, ~608): after building
    `assignments`/`models` from `list_judges()`, compute
    `roles = [r for r in pack_production_judges()] + [r for r in (set(assignments)|set(models)) if r not
    in pack_production_judges()]` (production order first, authored extras appended) and pass `roles=`
    to `run()`. `run()` already threads `roles=` → `build_authored_semantic_stage` → `build_trio`.

### 2. `POST /v1/judges` — the create-judge endpoint (mirror `create_criterion_endpoint`, app.py ~2056)
- Body `CreateJudgeRequest{role, lens_codes: list[str], owned_codes: list[str] = [], model_id: str|None,
  role_prompt: str|None, rationale: str}`.
- Flow (ATOMIC, mirror the criterion endpoint): `splice_production_judge(pack, role, lens_codes,
  owned_codes)` → `write_role_prompt(pack, role, role_prompt or <seed>)` → if `model_id`: bind via the
  existing `models_bind_endpoint` internals (`POST /v1/models/{id}/bind` — reuse, don't duplicate) →
  `save_judge(JudgeConfig(role=role, model=…, assigned_flags=lens_codes, validator_refs=()))` → ONE
  `AuditRecord(target.type="judge", action="author", why={rationale})`. On ANY step failing, roll back
  the snapshot (`restore_snapshot`) and return the error.
- **Map PHASE2-A's admissibility errors → 422** (owned⊄lens, code∉taxonomy, empty lens, collision) and
  the non-core-pack error → 422/403 with the criterion endpoint's shape. NEVER leak a model key.
- Response: `{role, lens_codes, owned_codes, model, bound_roles, audit_id}` (never a key).

## TESTS (RED first) — bare-CE; mock the LM + the probe (patterns: `tests/bff/test_model_registry.py`,
`tests/bff/test_*criterion*.py`, the probe's `predictors=` injection in `test_phase2_arbitrary_judge_probe.py`)
- A: `POST /v1/judges` (valid, tier:core pack) → 200; the snapshot gains the role/lens/owner; a
  `JudgeConfig` is saved; ONE author `AuditRecord`; NO key in the response.
- B: `POST /v1/judges` with `owned_codes ⊄ lens_codes` → 422, snapshot UNCHANGED (atomic).
- C: `POST /v1/judges` with a code ∉ taxonomy → 422.
- D: after create, the EXISTING `PUT /v1/judges/{role}` accepts the new role (the prior 404→200 flip).
- E (roster wire-in unit): `build_trio(ontology=, assignments={new_role:[code]}, roles=[4 roles],
  predictors={…4 mocked…})` returns 4 `Judge`s (no `ValueError`).
- F (4-judge grade): `build_authored_semantic_stage(… roles=4 …)` with injected predictors →
  `_apply_consensus` returns a clean verdict (NOT `insufficient_valid_models`); the new role's vote is in
  `consensus["models"]`. (The frozen consensus is UNCHANGED — you only feed it 4 results.)
- G (roles-derivation unit): the helper unions `pack_production_judges()` with the authored
  assignments/models keys, production order first.
- H (back-compat): `build_trio(roles=None)` with the default roster is byte-identical to before (the 3
  standard roles), so every existing trio/consensus test stays green.

## GATES
- `PYENV_VERSION=debuglithrim python -m pytest -q` → green, ≥ (PHASE2-A count) passed / 0 failed.
  `ruff check .` clean.
- `git diff --name-only` excludes `apps/shell/src/app.jsx` and ALL of `apps/shell/`. Scoped commits.
  DO NOT PUSH. Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + `git show --stat` (no app.jsx / no apps/shell). 3. RED→GREEN
+ full bare-CE count. 4. The `POST /v1/judges` request/response contract (so the parallel UI agent's
`createJudge` matches) + confirmation the 4-judge grade votes through the UNCHANGED `_apply_consensus`.
