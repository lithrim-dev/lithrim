# DRIVER — CE-DOCKER (Build C): `docker compose up` for the local CE — PARALLEL (all new files)

**Read first:** `docs/specs/SPEC_COMMUNITY_EDITION.md` §5.2-C. No existing container artifacts.

**Goal:** a `docker compose up` that boots BFF (:8787) + UI (:5180), auto-seeds the `_core` sample,
runs offline (`make demo` works with no keys), and accepts BYOK via env. All NEW files — no engine
edits.

## CONSTRAINTS (hard)
- No engine/source edits — only new container files (+ a README/quickstart stanza + `.gitignore`/
  `.dockerignore`). Frozen seam untouched. No push.
- The `claude` CLI chat CANNOT containerize → compose documents `LITHRIM_CHAT_PROVIDER=anthropic` +
  `ANTHROPIC_API_KEY` for chat; grading + `make demo` work without it.

## DELIVERABLES
1. `Dockerfile.bff` — `python:3.10-slim`; `pip install -e ".[bff,council]" --no-cache-dir`;
   `HEALTHCHECK` on `/health`; `CMD uvicorn app:app --app-dir apps/bff --host 0.0.0.0 --port 8787`.
2. `Dockerfile.ui` — `node:20`; `npm ci`; `npm run build`; serve on `0.0.0.0:5180`; honors
   `VITE_BFF_URL` (already supported in `vite.config.js`).
3. `docker-compose.yml` — `bff` + `ui` services, a bridge network, `VITE_BFF_URL=http://bff:8787`,
   volumes for `out/` (config DB + runs) + the gitignored `.provider_env`/`.connector_env`, env
   passthrough (`OPENAI_API_KEY`, `AZURE_OPENAI_*`, `ANTHROPIC_API_KEY`, `LITHRIM_LLM_PROVIDER`,
   `LITHRIM_CHAT_PROVIDER`, `LITHRIM_BFF_TOKEN`, `LITHRIM_BENCH_PACKS_DIR`).
4. `.dockerignore` — exclude `.git`, `node_modules`, `out/`, `.env*`, `__pycache__`, caches, `dist`.
5. README/quickstart stanza: `docker compose up` → open `:5180` → connect a key → grade. Note chat
   needs the Anthropic env.

## VALIDATION (agents can't start the Docker daemon)
- In-agent: `docker compose config` (lints the compose) MUST parse; Dockerfiles syntactically valid;
  a dry `docker build` only if the daemon is available — otherwise SKIP and say so.
- **Owner-run manual smoke (documented, not run by the agent):** `docker compose up` → BFF `/health`
  ok → UI loads → `make demo` REJECT. State clearly in the return that the live `up` smoke is
  owner-run.

## GATES
- No Python/JSX source changed → bare-CE suite untouched (note it, don't re-run the whole thing for
  infra-only files). Scoped commit (the new files only). Do NOT push.
- Commit msg ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
