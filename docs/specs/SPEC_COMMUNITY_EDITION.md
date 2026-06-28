# SPEC — Lithrim Community Edition (CE) onboarding

> **Status:** DRAFT for owner review (2026-06-24). Plan-review-before-code: this is the build
> contract; the build agents run only on owner "go". **Nothing in here touches the frozen council
> seam** (`compliance_council.py`, `_apply_consensus`, byte-frozen vs `acc4973`).

## 1. Objective (the CE job-to-be-done)

> *A stranger runs `docker compose up`, opens the app, connects their own LLM key, creates a
> workspace, authors a judge by chatting (or by form), loads/​pastes a case, and watches the judge
> grade it — the grounding floor catching a confident-but-wrong verdict — all on their machine,
> their keys, their data.*

**Done = self-serve.** Today the engine + authoring + grading all work and are proven live (judges
grade on real `gpt-4o`; the floor flips PASS→BLOCK). The gap is **onboarding** — the two LLM key
planes are env-file-only, there is no container path, and BYO-data ingest can hang ~2 min. The CE is
**~3 focused edge builds**, not a product rebuild.

## 2. The onboarding flow (owner's 7 steps, annotated with ground-truth status)

| # | Step | Status today | CE work |
|---|------|--------------|---------|
| 1 | Download / `docker compose up` & start | 🔴 `make up` only (pyenv); no container | **Build C** (Docker) |
| 2 | Sign in / identity | 🟢 token gate + login/session menu exist (no accounts) | **Build E** (actor-name; no accounts) |
| 3 | Connect provider (Claude / OpenAI / Azure) | 🔴 env-only, no UI, no endpoint | **Builds A+B** (the core) |
| 4 | Create a workspace | 🟢 workspaces + pack-pin exist | **Build F** (create-workspace affordance) |
| 5 | Chat / guided setup → create judges | 🟢 authoring loop + JudgeEditor + journey | key-gated by step 3 |
| 6 | Load a case / view pack corpus | 🟡 sample seeded; BYO-ingest can hang ~2 min | **Build D** (ingest fast-fail) |
| 7 | Run evaluation / grading | 🟢 $0 replay + live in-process, proven live | key-gated by step 3 |

**Identity decision (owner, 2026-06-24): actor name + optional token gate. No accounts / passwords /
user DB.** A "who are you" name stamps the audit `who`; the existing `LITHRIM_BFF_TOKEN` gate is the
opt-in lock for an exposed server.

## 3. The central build — provider-connect (capability slots, not "pick one provider")

Owner runs the **heterogeneous trio** today (risk→GPT, policy→Mistral-Large-3, faithfulness→Llama-4-
Maverick, all Azure) **+ Claude for chat**. So providers ≠ capabilities; the connect screen is
**capability-oriented** with graceful degradation:

- **Grading engine** *(required)* — **Simple:** one `OPENAI_API_KEY` → all three roles on `gpt-4o`
  (calibrated, logprobs on). **Advanced:** per-role model + provider/endpoint/deployment (the Azure
  trio, or any mix; backed by `_ROLE_DEPLOYMENT` / `_OPENAI_ROLE_MODEL` already in
  `judges_dspy.py:65-79`).
- **Authoring assistant** *(optional)* — Claude/Anthropic API key (`LITHRIM_CHAT_PROVIDER=anthropic`
  + `ANTHROPIC_API_KEY`), or the local `claude` CLI, or skip → forms-only authoring.
- **Graceful degradation:** grade with only the grading engine; chat-author unlocks when the
  assistant connects. (Calibration note: only OpenAI/GPT roles return logprobs → the Simple OpenAI
  path is the *most*-calibrated path; Mistral/Llama roles already show confidence n/a today.)

### 3.1 The env-reload solution (THE technical risk — resolved)

`build_judge_lm` reads the **cached** `settings` singleton (`runtime/council/settings.py:76`,
`env_file=".env"`). Subprocess grades re-import `settings` (read env live); the in-process grade uses
the cached singleton. So on a provider-config write the endpoint MUST:

1. **Test-probe** the supplied key (read-only, e.g. a 1-token completion) — on failure, surface the
   error and write nothing (mirrors `connector/config`).
2. **Write-only** the key to a gitignored repo-root **`.provider_env`** (never SQLite, never the
   manifest, never returned/logged).
3. **`os.environ[…] = value`** in the BFF process → subprocess grades (which inherit
   `{**os.environ}` at spawn, `app.py:623`) pick it up with no restart.
4. **Refresh the in-process council `settings` singleton** (re-instantiate `Settings()` and reassign
   the module global, or set the attributes) → in-process grades pick it up with no restart.
5. **Persist for restarts:** load `.provider_env` into `os.environ` at BFF startup (mirror the
   existing `_load_live_env()` at `app.py:531-546`), BEFORE the council settings import.
6. **Audit** the change (actor/why/when) with the key redacted (mirror `connector/config`
   `app.py:3107-3116`).

**Acceptance for the env-reload (the make-or-break test):** a key written via the endpoint takes
effect on the **next** grade (both subprocess and in-process) with **no BFF restart** — proven by a
test that writes a sentinel key and asserts `build_judge_lm` / a grade reads it.

### 3.2 Endpoint surface (mirror `POST /v1/connector/config`, `app.py:3061`)

- `POST /v1/provider/config` `{ plane: "grading"|"assistant", provider: "openai"|"azure"|"anthropic",
  api_key, endpoint?, model?, role? }` → test-probe → write-only → refresh → audit → `{ ok,
  last_tested, plane, provider }` (never the key).
- `GET /v1/provider/status` → which planes are configured + `last_tested` + provider/model (never the
  key) so the UI shows connected/needs-setup.

### 3.3 Frontend host (NEVER `app.jsx` — foreign-modified)

`app.jsx` composes `TopBar`/`ConnectorForm` but defines no components. New surface = a **new exported
component** in a non-`app.jsx` file. **Chosen host: the rail session-menu (`panes.jsx` `LeftRail`
footer)** — already this session's surface, already a "settings/account" affordance → add a
**"Connect AI"** entry that opens a `genui/ProviderSettings.jsx` panel; `bff.js` gains
`configProvider` / `getProviderStatus`. Zero `app.jsx` edits. Reuses the masked-password +
test-then-save idiom from `ConnectorForm` (`app.jsx:203`, read-only reference).

## 4. CE feature checklist (status: ✅ exists · 🟡 partial/fix · 🔴 net-new)

**A. Install & run**
- ✅ one-command `make up`; fresh-clone-green (`make test` 706p/0f, `make lint` clean, `make demo` REJECT)
- ✅ honest README, `.env.example`, Apache-2.0 LICENSE, bare-CE gate
- 🔴 `docker compose up` (Build C) — Dockerfile.bff + Dockerfile.ui + compose + .dockerignore

**B. Identity**
- ✅ optional `LITHRIM_BFF_TOKEN` gate + login/session menu (localStorage)
- 🔴 actor-name → audit `who` (Build E); **no accounts**

**C. Connect provider** *(the core)*
- ✅ env plumbing: per-role binding, OpenAI-direct (Cycle 1), BYOC override, the test-then-write-env pattern
- 🔴 `POST /v1/provider/config` + `GET /v1/provider/status` + env-reload (Build A)
- 🔴 `genui/ProviderSettings.jsx` + rail "Connect AI" entry + `bff.js` helpers (Build B)

**D. Workspace**
- ✅ workspaces, pack-pin, `_core` default, empty-workspace `/v1/judges` fixed (this session)
- 🔴 create-workspace UI affordance + pack pick (Build F)

**E. Chat → create judges**
- ✅ authoring loop (8 audited tools), JudgeEditor (assign lens→live prompt), journey, `PUT /v1/judges`, `POST /v1/criterion`, audit — key-gated by C

**F. Load case / process data**
- ✅ sample seeded, corpus/case surface, $0 replay + live grade (proven live), votes/verdict/floor/audit/report
- 🟡 BYO-data ingest fast-fail (Build D) — the ~2-min DSPy-extractor grind → bounded timeout + clear error
- ℹ️ healthcare pack = separately installed (Pro)

## 5. Multi-agent execution plan

**Vehicle:** the `.devloop` flow per build — driver → `devloop-executor` (tests-first RED→GREEN,
scoped commits) → cold `devloop-critic` (Gate 0 re-run + 4 fidelity Qs, non-vacuity by mutation).
**Isolation:** each build runs in its own **git worktree**; on green+critic-clean it **merges back to
`bench-salvage/ws6c-dspy`**. **Gates (every build):** bare-CE stays green (706p/0f baseline) · scoped
pathspec · **NEVER stage `apps/shell/src/app.jsx`** · moat byte-frozen · **no push**.

### 5.1 Dependency DAG + lanes (what parallelizes)

```
Lane 1 (backend · apps/bff/app.py — SEQUENTIAL, same file):
   A  provider-connect backend  ──►  D  ingest fast-fail
Lane 2 (infra · all new files — PARALLEL):
   C  docker compose path
Lane 3 (frontend · panes.jsx/genui/bff.js — after A):
   B  provider-connect UI  ──►  E  actor-name  ──►  F  create-workspace
```
- **A, C** start together. **D** after A (both edit `app.py` → avoid a self-merge-conflict). **B**
  after A (needs the endpoint). **E, F** after B (small FE, same files as B).
- Merge order back to the branch: A → D (Lane 1), C (Lane 2, anytime), B → E → F (Lane 3).

### 5.2 Per-build driver specs (seams from the 2026-06-24 scout pass)

**Build A — provider-connect backend** *(`.devloop/prompts/DRIVER_ce_provider_backend.md`)*
- Add `POST /v1/provider/config` + `GET /v1/provider/status` mirroring `connector_config_endpoint`
  (`app.py:3061-3122`); request model like `ConnectorConfigRequest` (`app.py:416`).
- Env-reload per §3.1: write `.provider_env` (gitignore it) + `os.environ` + refresh the
  `runtime/council/settings.py:76` singleton + load `.provider_env` at startup (mirror
  `_load_live_env`, `app.py:531-546`).
- Test-probe: a bounded read-only call (a 1-token `litellm`/OpenAI completion for grading; a cheap
  Anthropic ping for assistant). Tests (bare-CE, mock the probe; pattern =
  `tests/bff/test_connector_config.py` `ws_env` fixture): key never in response/audit/SQLite; key
  persists to `.provider_env`; **a written key is read by the next grade with no restart**.

**Build B — provider-connect UI** *(`DRIVER_ce_provider_ui.md`)* — **after A**
- `genui/ProviderSettings.jsx`: two capability slots (grading required / assistant optional), masked
  password inputs, provider select, Advanced per-role rows, Test-&-save → `configProvider`, status
  badge ← `getProviderStatus`. Add `bff.js` `configProvider`/`getProviderStatus`.
- Mount via a **"Connect AI"** item in the `panes.jsx` `LeftRail` session-menu (the surface added
  this session). **NEVER touch `app.jsx`.** vitest: slot render, test-then-save call, status badge,
  masked input. Add `configProvider`/`getProviderStatus` to the 3 whole-surface bff mocks.

**Build C — docker path** *(`DRIVER_ce_docker.md`)* — parallel
- `Dockerfile.bff` (`python:3.10-slim`, `pip install -e ".[bff,council]"`, `uvicorn app:app
  --app-dir apps/bff --host 0.0.0.0 --port 8787`), `Dockerfile.ui` (`node:20`, `npm ci`, build,
  serve, `VITE_BFF_URL=http://bff:8787`), `docker-compose.yml` (2 services, bridge net, volume for
  `out/` + `.provider_env`/`.connector_env`, env passthrough), `.dockerignore`.
- The `claude` CLI chat can't containerize → compose documents `LITHRIM_CHAT_PROVIDER=anthropic` +
  `ANTHROPIC_API_KEY` for chat; grading + `make demo` work without it. `vite.config.js` already
  honors `VITE_BFF_URL`. **Validation:** `docker compose config` lints in-agent; a real
  `docker compose up` smoke (BFF `/health`, UI loads, `make demo` REJECT) is an **owner-run manual
  step** (agents don't start the Docker daemon). Document it in `README` + a `docs/` quickstart.

**Build D — ingest fast-fail** *(`DRIVER_ce_ingest_fastfail.md`)* — **after A**
- Wrap `best_of_n_extractor(...)` (`app.py:2885-2886`) in a bounded timeout (default 30s, env
  `LITHRIM_INGEST_TIMEOUT`); on timeout raise the existing `RuntimeError` path (nothing pinned, A3
  invariant) with a clear remediation message (`tools.py:767-777`). Optionally drop `max_iters` 3→2
  and tighten the ingest `EtlpJuteClient` to 15s. No deterministic fallback exists for arbitrary
  BYO-JSON (the `_to_envelope` path is schema-known) → bounded-timeout-then-clear-error IS the fix.
- Test (hermetic): monkeypatch `best_of_n_extractor` to sleep past the timeout → assert a bounded
  error, **nothing pinned, no audit row** (extend `tests/bff/test_ingest_cases_tool.py`).

**Build E — actor-name** *(`DRIVER_ce_actor_name.md`)* — small, after B
- A "who are you" name field (rail/session) that sets the `X-Actor` the audit already consumes; no
  accounts. FE in `panes.jsx`/`bff.js`; BFF already honors `X-Actor`.

**Build F — create-workspace affordance** *(`DRIVER_ce_workspace_create.md`)* — small, after E
- A UI affordance to create a workspace + pick a pack (backed by existing `workspace.create_workspace`
  / the workspace switcher). FE in `panes.jsx`/`bff.js`.

## 6. Acceptance (CE done-bar)

1. `docker compose up` → BFF `/health` ok, UI loads, `make demo` REJECT with no keys (owner-run smoke).
2. From the UI: connect an OpenAI key (test passes, key never round-trips) → it grades the next case
   **with no restart**.
3. With the assistant connected: chat-author a judge (assign a lens) → grade → see the verdict + the
   floor decision + audit.
4. Paste a malformed BYO blob → a **bounded** error (≤ the timeout), nothing pinned — not a 2-min hang.
5. bare-CE suite stays green (≥706p/0f); moat byte-frozen; `app.jsx` never staged; nothing pushed.

## 7. Out of scope / deferred (not v1 CE)

- User accounts / passwords / multi-tenant (identity = actor + optional token gate).
- An OpenAI-backed authoring loop (chat stays Claude-SDK; OpenAI users author via forms or add a
  Claude assistant key). *Tracked as a fast-follow if the forms path proves insufficient.*
- Azure trio as the *default* (it's the Advanced path; Simple-OpenAI is the front door).
- Hosted inference / accounts / the healthcare pack (Pro / separately distributed).
- Per-workspace provider config (v1 = one global grading engine + one assistant; revisit if needed).

## 8. Model registry (CE increment — brainstormed + decided 2026-06-25)

**The reframe:** today provider config is **welded to the judge role** (`POST /v1/provider/config?role=
policy_judge`) — the model is a property of the judge. Decouple them: a **configured model becomes a
first-class, reusable, capability-aware entity** (the LiteLLM `model_list` pattern); a judge *references*
one. This is the diverse-council thesis (GPT/Mistral/Llama catch different errors) handed to the user.

**Owner decision (2026-06-25):** build the **registry FIRST** (it de-risks the judge-scope fork — see
Phase 2 — and cleans up the per-role-config mess); the catalog is **presets + custom + live-fetch**.

**The entity — a configured model:** `{id, provider (openai|azure|anthropic|…), model_or_deployment,
endpoint?, key (write-only), capabilities {logprobs, context_window, cost_tier}}`. Secret →
`.provider_env` (REUSE Build A); non-secret metadata → a registry sidecar (extend `.provider_status.json`).

**The catalog = presets + custom + live (never stale, never a wall):**
- **Presets** — a small curated per-provider list, capability-annotated.
- **Custom** — always-available free-text model/deployment; never blocks an unknown model. **Azure stays
  deployment-name-based** (a model catalog doesn't apply — it's *your* deployments).
- **Live** — fetch the provider's `/models` where supported (OpenAI, Anthropic).
- **Capabilities are the load-bearing part, not names** — esp. **`logprobs`** (OpenAI yes → calibrated
  confidence; Claude / Mistral-via-Azure no → confidence dark). Surface it at pick time; that's the
  differentiated catalog vs. a cosmetic dropdown.

**Reuse, don't re-architect:** the registry is an **authoring layer over Build A's env-var mechanism** —
binding a role→registered-model writes the same `LITHRIM_LLM_PROVIDER` / key / per-role model/deployment
env vars `build_judge_lm` reads (`_provider_env_vars` + `_persist_and_reload_provider`). **Frozen council
untouched.**

**API (as built, MR-1a/1b):** `GET /v1/models/catalog` (presets; `?live=true` merges the provider's live
`/models` for OpenAI/Anthropic, graceful-absent → presets-only, Azure deployment-based — MR-1b) · `POST
/v1/models` (register: test-probe + write-only + capability annotate) · `GET /v1/models` (the pool, never
keys) · `DELETE /v1/models/{id}` · role→model bind is a **dedicated** `POST /v1/models/{id}/bind {role}`
(it internally reuses Build A's `_provider_env_vars` + `_persist_and_reload_provider` — the same env vars
`/v1/provider/config` writes — so `build_judge_lm` re-routes that role with no restart; the earlier
"reuses `/v1/provider/config`" phrasing was the proposal, superseded by the dedicated endpoint in 1a).

**Build status (2026-06-25):** MR-1a (pool + catalog + bind, backend) · MR-1b (live `/models` fetch) ·
MR-1c (the Model pool UI — register, the pool list with a logprobs chip + delete, pick-from-pool role
bind, the ⚠ no-logprobs hint, composed into Connect AI) — **all DONE, merged on `bench-salvage/ws6c-dspy`,
deterministic-green (pytest 745/0, ModelRegistry 8/8).** **SEAM (1a, carried):** `build_judge_lm` reads a
GLOBAL `LITHRIM_LLM_PROVIDER` — a role's bind sets only its per-role *model*/*deployment*, NOT a per-role
*provider*; so binding role A→OpenAI and role B→Azure simultaneously is unsupported (the 1c UI shows an
honest inline note, does not fake it). Cross-provider-per-role is the next backend unlock (a focused
`build_judge_lm` extension, the foundation for Phase 2's arbitrary judges).

**Phase 1 scope:** the registry + catalog + the **3 fixed roles bind to pool entries** (pick-from-pool,
not re-type) — **DELIVERED (MR-1a/1b/1c).** **Phase 2 — DEFERRED (the fork):** *arbitrary* user-created
judges referencing the pool.
**Riskiest assumption, test cheaply BEFORE committing:** does the frozen `_apply_consensus` handle N≠3
votes, AND does every new judge get a **lens + a Tier-1 owner** (the owner↔emit invariant forbids an
inert owner)? Registry-first means we answer this on solid ground, not speculatively.
**Gate DISCHARGED 2026-06-25** (`docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md`): the frozen
`_apply_consensus` is `len(valid)`-driven → N≥2 needs no seam edit; a new judge needs an authored bundle
(roster + lens + optional owner) over the snapshot; corroboration is an ABSOLUTE 2 (frozen). Phase-2 is
in build (owner-signed-off): the audited tier:core-only judge writer + the `build_trio` roster relax + the
`JudgeBuilder` UI.

## 9. The default council — three eval axes (opinionated, generalizable)

**Decision (2026-06-25, owner-affirmed):** ship the `risk_judge` / `policy_judge` / `faithfulness_judge`
triad as the **opinionated, batteries-included default council** — NOT clinical baggage, but **three
generalizable eval axes**. Strong calibrated defaults beat a blank canvas; a stated POV is a selling
point. Lead with the opinion; be explicit that **faithfulness is the grounding anchor**.

**Proven generalizable, not aspirational:** the SAME triad ships in THREE packs with disjoint
taxonomies — only the per-pack codes change, the axes are stable:
- **faithfulness_judge** = *groundedness / faithful-to-source* (the universal RAG-eval axis) — AND the
  v2 **veto judge**, i.e. the structural home of the tool-grounded floor. `_core`: SOURCE_CONTRADICTION,
  MISSING_CONTEXT · support_ticket_qa: CONTRADICTS_THREAD, UNRESOLVED_ISSUE · healthcare: MISSING_ALLERGY.
- **policy_judge** = *rules / claims / required disclosures*. `_core`: FABRICATED_CLAIM · support:
  FABRICATED_POLICY, MISSING_DISCLOSURE · healthcare: fabricated consent / PHI.
- **risk_judge** = *harm / unsupported assertions / inconsistency*. `_core`: UNSUPPORTED_ASSERTION,
  INTERNAL_INCONSISTENCY · support: UNSUPPORTED_COMMITMENT · healthcare: dosage/risk.

The decomposition maps onto the eval literature (faithfulness/groundedness · policy/safety · risk/harm)
and is more actionable than "helpful/harmless/honest" because each axis carries a by-construction
taxonomy + an owner + a lens, not a vibe.

**The opinionated parts we OWN (the brand), not hide:** (1) faithfulness is first-among-equals — the
veto/grounding anchor (the moat thesis: "by-construction + tool-grounded floor, not a better judge"); (2)
the default model diversity (gpt→risk, mistral→policy, llama→faithfulness) is an opinion — "different
families catch different errors" — now **rebind-able** via the model registry (§8); (3) the names carry
mild flavor — Phase-2 (§8) is the escape hatch for domain-specific axes / renames.

**What ships — the honest caveat (docs MUST state):** in `_core` out of the box, **2 of the 5 Tier-1
never-events** (`OUT_OF_SCOPE_ACTION`, `SOURCE_MISATTRIBUTION`) are owned only by *dormant* judges
(the snapshot's `declared_but_not_running` = `behavior_judge`/`source_message_judge`). By design (not a
bug) they rely on **corroboration, not solo one-strike**, out of the box — and authoring a judge that
*owns* them (Phase-2) is exactly how a user arms them. State this so nobody assumes all five are
solo-armed.

## References
- `docs/COMMUNITY_RELEASE_v1_PLAN.md` (the 5 release cycles, all done + clone-validated).
- Scout seams (2026-06-24): `judges_dspy.py:65-79,215-299` · `runtime/council/settings.py:23-76` ·
  `loop.py:335-377` · `app.py:531-546,616-640,3061-3122` · `vite.config.js` · `jute_extractor.py` +
  `app.py:2751-2957` · `tests/bff/test_connector_config.py` · `conftest.py` NEEDS_PACK.
