# DRIVER — CE-PROVIDER-BACKEND (Build A): in-app LLM provider/key config endpoint

**Read first:** `docs/specs/SPEC_COMMUNITY_EDITION.md` §3 + §5.2-A. This is the CE's core build.

**Goal:** let a user configure their LLM provider keys IN-APP (today env-only). Add a BFF endpoint
that test-validates a key, writes it write-only to a gitignored env file, and — the make-or-break —
makes it take effect on the **next grade with NO BFF restart**. Mirror the proven `connector/config`
pattern.

## CONSTRAINTS (hard)
- **Frozen seam UNTOUCHED:** never edit `compliance_council.py` / `_apply_consensus` / consensus
  symbols. This is BFF-edge + the council `settings` singleton only.
- **Config-plane SQL stays Postgres-portable** (the live plane is Postgres) — but this build writes
  to a gitignored ENV FILE + os.environ, not SQL. Key NEVER to SQLite/manifest/response/logs.
- Tests-first (RED→GREEN). Scoped pathspec. **NEVER stage `apps/shell/src/app.jsx`.** No push.
- Run tests in the `debuglithrim` pyenv. bare-CE suite must stay ≥706p/0f.

## DELIVERABLES
1. `POST /v1/provider/config` `{plane:"grading"|"assistant", provider, api_key, endpoint?, model?, role?}`
   — mirror `connector_config_endpoint` (`apps/bff/app.py:3061-3122`) + a request model like
   `ConnectorConfigRequest` (`app.py:416`). Flow: **test-probe** (read-only; a 1-token completion for
   grading via the same litellm/openai path `build_judge_lm` uses; a cheap Anthropic ping for
   assistant) → on fail surface error + write nothing → on pass write-only to gitignored
   repo-root `.provider_env` + audit (key redacted, mirror `app.py:3107-3116`).
2. **Env-reload (SPEC §3.1):** on write — set `os.environ[…]` (covers subprocess grades, which
   inherit `{**os.environ}` at `app.py:623`) **and** refresh the in-process council settings singleton
   (`runtime/council/settings.py:76` — re-instantiate `Settings()` + reassign the module global, or
   set attrs) so `build_judge_lm` picks it up. Load `.provider_env` at BFF startup (mirror
   `_load_live_env`, `app.py:531-546`) BEFORE the council import, for restart persistence.
3. `GET /v1/provider/status` → configured planes + `last_tested` + provider/model, **never the key**.
4. Add `.provider_env` to `.gitignore`.

## TESTS (RED first) — bare-CE, pattern = `tests/bff/test_connector_config.py` (`ws_env` fixture, mock the probe)
- A — POST with a passing (mocked) probe → 200; key written to `.provider_env`; key NOT in response.
- B — POST with a failing probe → 4xx; nothing written.
- C — key NEVER appears in the audit record / SQLite / response / logs.
- D — **the make-or-break:** after a POST, `build_judge_lm` (or a grade) reads the new key/provider
  with **no restart** (assert via the refreshed singleton + an os.environ read; mock the LM).
- E — `GET /v1/provider/status` reflects configured/not, never leaks the key.

## GATES
- `PYENV_VERSION=debuglithrim python -m pytest -q` bare-CE ≥706p/0f. `ruff check .` clean.
- `git diff --name-only` excludes `apps/shell/src/app.jsx`. Scoped commit. Do NOT push.
- Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
