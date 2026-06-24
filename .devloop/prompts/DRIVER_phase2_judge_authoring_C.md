# DRIVER — PHASE2-C: the "Create judge" UI (frontend)

**Read first:** `docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md` · SPEC §8. **OWNER SIGNED
OFF 2026-06-25** on the snapshot-authoring surface.

**The models to MIRROR:** `apps/shell/src/genui/CriterionBuilder.jsx` (the snapshot-write card +
its `onResult` SPINE discipline — the human's Save is the sole write) + `apps/shell/src/genui/
JudgeEditor.jsx` (the owner↔emit inline guard) + `apps/shell/src/genui/ModelRegistry.jsx` (the
pool-pick + the honest inline capability note — MR-1c).

**FRONTEND-ONLY:** `apps/shell/src/genui/JudgeBuilder.jsx` (new), `apps/shell/src/genui/
JudgeBuilder.test.jsx` (new), `apps/shell/src/bff.js`, `apps/shell/src/genui/registry.js`
(register the tool). Do NOT touch `apps/bff/` or any python (a parallel agent owns the backend).
**NEVER touch `apps/shell/src/app.jsx`.** NO prettier (hand-compact JSX — format only your touched
lines; keep `git diff --stat` small). Reuse the inline-style vocabulary already in the genui files
(`--bg/--ink/--muted/--border/--accent/--surface-muted/--teal/--amber`).

## THE BACKEND CONTRACT (PHASE2-B, building in parallel — mock it in vitest)
- `POST /v1/judges` body `{role, lens_codes: string[], owned_codes: string[], model_id?: string,
  role_prompt?: string, rationale: string}` → `{role, lens_codes, owned_codes, model, bound_roles,
  audit_id}` (never a key). 422 on admissibility failure (owned⊄lens / code∉taxonomy / empty lens /
  role collision / non-core pack) with a `detail` string.
- Existing helpers to REUSE (already in `bff.js`): `getModelCatalog`, `listModels`, `bindModel` (MR-1c);
  the active pack's available codes come from the ontology/judge endpoints already wired for `JudgeEditor`.

## DELIVERABLES
1. **`bff.js` helper** `createJudge(body)` → `POST /v1/judges` (mirror `postCriterion`'s doc-comment +
   `call()` body-spread style; spread `model_id`/`role_prompt` only when set).
2. **`apps/shell/src/genui/JudgeBuilder.jsx`** — a self-contained authoring card:
   - **Role id** input (snake/lower; a small inline hint on format).
   - **Lens codes** multiselect (the codes the judge may raise) — from the active pack's available
     codes (the same source `JudgeEditor` uses).
   - **Owned codes** subset — MUST be ⊆ lens (the owner↔emit guard): disable/var-amber any owned code
     not in the lens, mirroring `JudgeEditor`'s inline guard; an empty owned set is allowed
     (corroborate-only).
   - **Model** pick-from-pool (reuse `ModelRegistry`'s pool list + `bindModel`/`listModels`), surfacing
     the **⚠ no-logprobs** hint when the chosen pool model lacks logprobs (MR-1c consistency).
   - **Role-prompt seed** textarea (optional).
   - **The absolute-2 / one-strike HONESTY note** (PROBE Q3/Q4 — non-negotiable, render it inline):
     "Your judge votes and corroborates immediately. A bigger council does not raise the bar —
     corroboration is an absolute 2 votes. Solo one-strike authority for a newly-owned code activates on
     the next graded run." (mirror MR-1c's honest inline-note pattern; do NOT overstate.)
   - **Save → `createJudge`**; on success fire `onResult(...)` (the `CriterionBuilder` SPINE pattern —
     the human's click is the sole write); surface a 422 `detail` inline (don't swallow it).
3. **Register** the component as an authoring tool in `registry.js` (mirror how `CriterionBuilder`/
   `tool-criterion_builder` is registered), so it renders inline as gen-UI (conversational-first holds —
   passive, never drives panes/top-bar to advance).

## TESTS (RED first) — `apps/shell/src/genui/JudgeBuilder.test.jsx` (vitest, `vi.mock("../bff.js", …)`
mirroring `CriterionBuilder.test.jsx`)
- A: renders the fields (role / lens multiselect / owned / model / prompt) + the absolute-2 honesty note.
- B: the owner↔emit guard — selecting an owned code NOT in the lens is blocked/flagged (Save guarded).
- C: Save → `createJudge` called with the entered `{role, lens_codes, owned_codes, model_id?, rationale}`.
- D: a 422 `{detail}` from `createJudge` renders inline (not swallowed); `onResult` NOT fired on failure.
- E: `onResult` fires only on a successful write (the SPINE discipline).
- F: the model pick surfaces the ⚠ no-logprobs hint for a logprobs:false pool entry (MR-1c consistency).
- `bff.test.jsx`: `createJudge` posts the right body/shape.

## GATES
- `cd apps/shell && npx vitest run` → green (JudgeBuilder 100% + the whole shell suite; the ONLY
  acceptable red is the pre-existing `app.test.jsx:14` titlebar test — confirm it's unrelated to your
  diff). `npm run build` succeeds.
- `git diff --name-only` excludes `apps/shell/src/app.jsx`. Scoped commits. DO NOT PUSH. Commit msg ends
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + `git show --stat` (no app.jsx). 3. RED→GREEN + vitest pass
count + `npm run build` result. 4. The JudgeBuilder contract (props/exports) + `createJudge` + how the
owner↔emit guard + the absolute-2 honesty note render.
