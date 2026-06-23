# DRIVER — BFF-AUTH-1: configurable inbound auth gate (Release Cycle 4)

**Cycle:** Community Release v1 — Cycle 4 (Basic auth). **Plan:** `docs/COMMUNITY_RELEASE_v1_PLAN.md` §Cycle 4.
**Goal:** a **configurable inbound auth gate** on the BFF — OFF for local single-user (zero friction, the
one-command run unchanged), ON for an exposed server. The README/`.env`/one-command-run pieces of Cycle 4
already shipped; this is the one net-new piece.

## CURRENT STATE (verified)

- **No inbound auth exists.** `apps/bff/app.py` `get_actor`/`X-Actor` is audit ATTRIBUTION (the §2B
  "who"), NOT authentication; the `x_api_key` fields are OUTBOUND connector creds. Do not touch those.
- `app = FastAPI(...)` at line 548; `app.add_middleware(CORSMiddleware, ...)` at 549-554; `@app.get("/health")`
  at 565 (the liveness probe — `make health`); 47 `/v1/*` routes declared directly (no central router).
- The BFF process is pack-agnostic; the frozen council is NOWHERE near this (BFF edge). The seam stays
  byte-frozen.

## DESIGN (the cut)

- **Scheme:** a static bearer token via env **`LITHRIM_BFF_TOKEN`** (+ an `X-API-Key: <token>` convenience
  header), **constant-time** compared (`hmac.compare_digest`). NOT HTTP Basic, NOT OAuth — single-user
  self-host.
- **Default OFF:** token unset/empty (`os.environ.get("LITHRIM_BFF_TOKEN","").strip()` falsy) → gate OPEN
  (everything passes, exactly as today). Token set → gate ON.
- **Gate = ONE FastAPI middleware** registered right AFTER the CORS middleware (so it runs per request).
  Read the token PER-REQUEST via a small helper (`_bff_auth_token()`) so tests can toggle env without
  re-instantiating the app.
- **Allow-list (always pass, even when ON):** `request.method == "OPTIONS"` (CORS preflight) and
  `request.url.path == "/health"`. Everything else, when ON, requires a valid token.
- **On reject:** `JSONResponse(status_code=401, {"detail": "missing or invalid API token"})` with a
  `WWW-Authenticate: Bearer` header. Accept the token from `Authorization: Bearer <token>` (preferred) OR
  `X-API-Key: <token>`.

## FILES

1. **`apps/bff/app.py`** —
   - Add `import hmac` (top, alphabetical with the stdlib imports).
   - Add `_bff_auth_token() -> str` helper (reads + strips `LITHRIM_BFF_TOKEN`).
   - Add a `@app.middleware("http")` async `_auth_gate(request, call_next)` after the CORS
     `add_middleware` block (lines 549-554): off when no token; allow-list OPTIONS + `/health`; else
     extract presented token from `Authorization: Bearer …` or `X-API-Key`, `hmac.compare_digest` vs the
     configured token, 401 on miss. Keep it small + dependency-light (use `starlette.responses.JSONResponse`).
   - Docstring: note OFF-by-default preserves the local one-command run; ON gates everything but
     `/health` + preflight.

2. **`apps/shell/src/bff.js`** — in the `call()` wrapper (and the SSE `chatStream` fetch, if it builds its
   own headers), add `Authorization: Bearer ${import.meta.env.VITE_BFF_TOKEN}` ONLY when
   `VITE_BFF_TOKEN` is set (truthy). Unset → no header (unchanged local dev). Hand-compact JSX/JS, no
   prettier; keep the diff to the touched lines (see `[[shell-no-prettier-handcompact-jsx]]`).

3. **`.env.example`** — add a commented line:
   `# LITHRIM_BFF_TOKEN=        # set to require a Bearer token on the BFF (leave unset for local single-user)`

4. **`README.md` / QUICKSTART** — a 2-3 line "Exposing the server" note: set `LITHRIM_BFF_TOKEN`, pass it
   as `Authorization: Bearer <token>` (or `X-API-Key`); unset = open for local single-user. (Find the
   existing run/quickstart section; keep it honest + short.)

## TESTS — RED first (`tests/bff/test_auth.py`)

Use the existing `tests/bff/` TestClient pattern (importorskip fastapi; `apps/bff` on sys.path). Toggle
`LITHRIM_BFF_TOKEN` via `monkeypatch.setenv`/`delenv` per test (the middleware reads it per request).

- **A — OFF by default:** env unset → `GET /health` AND a representative `/v1` route (e.g. `GET /v1/agents`
  or `/v1/meta`) return non-401 (gate open, today's behavior). *(This is the critical non-regression.)*
- **B — ON, no token presented → 401** on a `/v1` route.
- **C — ON, wrong token → 401.**
- **D — ON, correct `Authorization: Bearer <token>` → passes** (non-401).
- **E — ON, correct `X-API-Key: <token>` → passes.**
- **F — `/health` open even when ON** (liveness never gated).
- **G — OPTIONS preflight passes even when ON** (CORS not broken).
- **H — non-vacuous / constant-time intent:** a near-miss token (correct prefix, wrong/extra suffix, and a
  too-short token) → 401 (guards against a partial/`==` match bug; proves `compare_digest` semantics).

## GATES

- `PYENV_VERSION=debuglithrim python -m pytest -q` from repo root → full bare-CE GREEN (baseline **698
  passed / 0 failed**; ADD tests, break nothing — esp. the existing `tests/bff/*` must stay green, proving
  the default-OFF path is transparent). Run the BROADER suite.
- `PYENV_VERSION=debuglithrim ruff check .` → clean.
- `cd apps/shell && npx vitest run` → no new failures (the 1 pre-existing `app.test.jsx` foreign fail is
  expected; everything else green — the bff.js change must not break the shell tests).
- Moat byte-identical (`compliance_council.py` / consensus untouched — this is BFF edge, trivially true;
  confirm `git diff` doesn't touch `runtime/council/`).

## COMMIT

Scoped pathspec, atomic (the auth gate + tests + the doc/.env lines + the bff.js change). Verify scope with
`git show --stat HEAD`. **NEVER stage `apps/shell/src/app.jsx`.** Do NOT push. End the message with
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
