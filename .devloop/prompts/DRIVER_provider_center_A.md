# DRIVER — PROVIDER-CENTER-A: cross-provider-per-role grading + broader provider types (backend)

**Read first:** the memory `provider-center-cline-style-direction` (the target UX) + the model registry
(MR-1a/1b/1c, `apps/bff/app.py` ~3402-3710) + `build_judge_lm` (`judges_dspy.py:215-299`).

**Goal:** the foundation for Cline-style multi-provider grading — **each judge role can run on ANY
configured provider** (risk→OpenAI, policy→Gemini, faithfulness→Anthropic), and the provider set broadens
to **gemini / bedrock / openai-compatible** (the litellm path already speaks them). This is the
cross-provider-per-role UNLOCK (seam S-BS-MR1a-CROSSPROVIDER) the registry was built toward.

**FROZEN SEAM — NEVER TOUCH:** `runtime/council/compliance_council.py` / `_apply_consensus`. **NEVER touch
`apps/shell/src/app.jsx`.** `build_judge_lm` (`judges_dspy.py`) is the EDITABLE provider seam (BYOC-1
already extended it) — NOT the frozen consensus. UI is PROVIDER-CENTER-B (do NOT touch `apps/shell/`).

## The design (byte-preserving — the global path stays identical)
`build_judge_lm(role)` today: a GLOBAL `settings.LITHRIM_LLM_PROVIDER` picks the branch; per-role varies
only the model/deployment. ADD a **per-role provider override** layered ON TOP, read from config, with the
global path as the untouched fallback:
1. Resolve `role_provider = settings.<per-role provider> or global_provider`.
2. **When a per-role provider IS set** (the new path): build `dspy.LM(f"{prefix}/{model}", api_key=<per-
   role key>, api_base=<per-role base, for azure/openai-compatible>, temperature=0, max_tokens=4096,
   logprobs=<provider supports it>, cache=True)`. `prefix`: openai→`openai`, azure→`azure`,
   anthropic→`anthropic`, gemini→`gemini`, bedrock→`bedrock`, openai_compatible→`openai`(+api_base).
   litellm routes all of these. logprobs ON only for openai/azure (others → off, confidence dark — honest).
3. **When NO per-role provider is set** → fall through to the EXISTING global openai / azure / byo-claude
   branches **byte-identical** (the regression guard). KEEP the byo-claude routing exactly.

## DELIVERABLES
1. **`runtime/council/settings.py`** — per-role provider config + the new provider keys (defaults "" so the
   global path is unchanged): `LITHRIM_LLM_PROVIDER_{RISK,POLICY,FAITHFULNESS}` +
   `LITHRIM_LLM_MODEL_{RISK,POLICY,FAITHFULNESS}` + `LITHRIM_LLM_API_KEY_{RISK,POLICY,FAITHFULNESS}` +
   `LITHRIM_LLM_API_BASE_{RISK,POLICY,FAITHFULNESS}` (a generic per-role binding the registry writes), and
   `GEMINI_API_KEY` / the bedrock + openai-compatible fields litellm needs. (A per-role map keyed by role,
   mirroring `_OPENAI_ROLE_MODEL`, is fine — keep them module constants OUTSIDE the frozen symbol set.)
2. **`runtime/council/judges_dspy.py` `build_judge_lm`** — the per-role override branch above; a
   `_litellm_prefix(provider)` + a `_provider_supports_logprobs(provider)` helper (openai/azure True,
   else False). Byte-identical when no per-role provider set.
3. **`apps/bff/app.py`** — (a) extend `ProviderConfigRequest.provider` Literal to add `gemini`, `bedrock`,
   `openai_compatible`; (b) `_provider_env_vars`: when a `role` is given + a per-role provider, write the
   `LITHRIM_LLM_{PROVIDER,MODEL,API_KEY,API_BASE}_<ROLE>` vars (the per-role binding) — keep the existing
   no-role/global writes byte-identical; (c) `_probe_provider`: route the new types via litellm
   (`litellm.completion(model=f"{prefix}/{model}", ...)`); (d) the registry **bind** (`models_bind_endpoint`)
   carries the entry's `{provider, model, endpoint, key}` into the role's per-role vars so role A→gemini +
   role B→openai coexist. The model key stays WRITE-ONLY; never in a response/log.

## TESTS (RED first) — bare-CE, MOCK `dspy.LM` + `litellm` (no network/$0; patterns: `test_byo_claude*`,
`tests/bff/test_model_registry.py`, `test_provider_config.py`)
- A: a MIXED council — set per-role providers (risk→openai, policy→gemini, faithfulness→anthropic) →
  `build_judge_lm(role)` constructs `dspy.LM` with the model string `openai/…`, `gemini/…`, `anthropic/…`
  respectively (assert the first positional arg + the per-role api_key). Mock `dspy.LM`.
- B (BYTE-IDENTICAL regression): with NO per-role provider set, `build_judge_lm` for each role builds the
  SAME `dspy.LM(...)` as before (global openai + global azure paths unchanged); byo-claude routing intact.
- C: `_provider_supports_logprobs` — openai/azure True, anthropic/gemini/bedrock False (so logprobs is OFF
  in the LM kwargs for those → honest confidence-dark).
- D: `POST /v1/provider/config` with `provider="gemini"` (+ role) → probes via litellm + writes the
  per-role provider env; `POST /v1/models` accepts a gemini/bedrock/openai-compatible model (probe mocked).
- E: `POST /v1/models/{id}/bind {role}` for a gemini entry writes `LITHRIM_LLM_PROVIDER_<ROLE>=gemini` +
  the per-role key/model — and a DIFFERENT role bound to an openai entry coexists (cross-provider council).
- F (secret hygiene, non-vacuous): the per-role key is write-only on `.provider_env`, NEVER in any response.

## GATES
- `PYENV_VERSION=debuglithrim python -m pytest -q` → green, ≥782 passed / 0 failed. `ruff check .` clean.
- `git diff --name-only` excludes `apps/shell/` + `app.jsx` + `compliance_council.py`. Scoped commits.
  DO NOT PUSH. Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## RETURN (structured)
1. Worktree branch + HEAD. 2. Commit SHAs + `git show --stat` (no app.jsx / no frozen seam). 3. RED→GREEN +
full bare-CE count. 4. The per-role env-var contract (the 4 `LITHRIM_LLM_*_<ROLE>` vars) + the provider
Literal + which providers support logprobs — so PROVIDER-CENTER-B's UI + the registry bind match.
