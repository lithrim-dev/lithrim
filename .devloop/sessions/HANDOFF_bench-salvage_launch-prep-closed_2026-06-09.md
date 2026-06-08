# HANDOFF — bench-salvage (monitor role) — 2026-06-09 (LAUNCH-PREP closed; A-LIVE owed)

> **For the NEW monitor session.** This session **closed LAUNCH-PREP** (PROCEED-WITH-CAVEATS) — the OSS core now runs **standalone** (in-process council default, no `:8002`/lithrim-backend/Mongo). The single owed item gates the release: the **standalone A-LIVE** (a user-run PAID smoke). After it passes → a proof capsule + the **owner-gated push**.
> **Resume:** `/devloop-resume bench-salvage`, then read this, then hand the user the standalone A-LIVE steps (below).

## 🔴 IMMEDIATE STATE — the standalone A-LIVE is the next action (user-run)
**v1 critical path: CHATBIND-2 ✅ → LAUNCH-PREP ✅ → the standalone A-LIVE (user-run, NEXT) → push/release (owner-gated).**

The A-LIVE is the **load-bearing live proof** that v1 runs standalone AND the **RELEASE pre-push gate** (`docs/RELEASE_v1.md`). The resolver *routing* is proven (5/5 hermetic); the A-LIVE proves a real in-process council run completes with lithrim-backend STOPPED. Hand the user:

```
# 0. ensure lithrim-backend / :8002 is STOPPED (curl http://localhost:8002/health should FAIL)
# 1. BYO key (Azure trio or an authed `claude` CLI) — see docs/QUICKSTART.md §3
# 2. LITHRIM_COUNCIL_BACKEND must be UNSET (the in_process default)
uvicorn app:app --app-dir apps/bff --port 8787      # terminal 1 — the BFF
cd apps/shell && npm run dev                          # terminal 2 — :5180
# 3. open http://localhost:5180 → Shell mode → "Run live" on ws0_default
#    EXPECT: a real verdict renders (reject/BLOCK), an audit blob persists
#    (GET /v1/runs/{id}/audit), and NO :8002 call is made.
```
- **Honest-Δ acceptance:** "a real grounded verdict completed backend-stopped + a persisted audit blob" — **NOT** "verdict == :8002." in_process is ≥-strict (WS-6c-AGENTIC); document any delta, don't assert parity. [[self-asserting-loop-honesty-moat]]
- **On PASS:** a proof capsule (PROOF doc + a zyng video; honest-Δ; reconnect-check the zyng MCP) [[proof-capsule-convention]] → then the **owner-gated push** (the `RELEASE_v1.md` checklist; the executor PREPARED it, the owner runs `git push`/PR/tag). **Do NOT push without explicit owner approval.**
- **On FAIL:** reopen — but the likely cause is env/key, not the resolver (routing is test-proven + self-containment grep-confirmed).
- **Do NOT autostart.** `curl /health` first; if up, ask. The user authorizes the paid run.

## What LAUNCH-PREP landed (3 atomic commits, pathspec-only, NOT pushed)
| Commit | What |
|---|---|
| `84c3c82` | **D1** `_resolve_run_backend(req) → (live_http, in_process)` + `LITHRIM_COUNCIL_BACKEND` (default `in_process`) at `run_eval_endpoint`; "Run live" defaults to the bundled in-process v2 council, `http` opt-in. Shell tooltip + `bff.js` comment backend-agnostic. New hermetic `tests/test_launch_standalone.py` (5 passed). |
| `4dbc417` | **D2/D4** `docs/QUICKSTART.md` (clean-clone product walkthrough, BYO-key, `$0` replay) + `docs/RELEASE_v1.md` (OSS-core scope, airgapped/no-us-hosted framing, owner-executed push checklist, draft notes) + README pointers. |
| `ec526f4` | **D3** the 8-seam triage table in `RELEASE_v1.md` (no HARD launch-blocker). |

Monitor close commit (this session): the critique + session log + STREAM/streams.json sync + the S-BS-109 RELEASE row (pathspec-only).

## Audit verdict (monitor 7-item + inline 4-question critique)
**CLEAN → PROCEED-WITH-CAVEATS.** ROUTINE-with-care (NO fresh-critic — D1 doesn't touch the A-SAFE deny-hook, as scoped at GO). Independently re-verified:
- **A-SAFE byte-identical** — `git diff 84c3c82~1 ec526f4 -- apps/bff/agent/loop.py` is **EMPTY**. The plan-review MUST was folded: the chat's `_run_eval_replay` calls `run_eval_endpoint` **directly** (`loop.py:1189`), so the proof is the resolver invariant `live=False,in_process=False → replay` **regardless of env**, pinned by `test_replay_stays_replay` (both env values + unset). The resolver gates the env read inside `if req.live:` — verified as committed.
- **in_process self-containment** — re-ran the `pymongo|motor|MongoClient` + `lithrim_backend|from app.` greps over the in_process chain → empty. CONFIRMED.
- **Green** — monitor re-ran the new test 5/5 on the **real** `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python`; executor full suite 522/2/3 (the 2 = pre-existing S-BS-96, structurally independent — diff touches no `runtime/observation/`; the 3 = cred-gated).

## Open seams (current)
- **NEW: S-BS-109** (low) the eval-pack *live* endpoint (`/v1/eval-pack/run`, `live=true`) still routes to `:8002` — `build_pack` has no in_process param (code-acknowledged follow-on). NOT shell-exposed; the chat's pack op is replay-only; the offline `lithrim-bench-pack` gate is `$0`/standalone. Triaged post-v1 in RELEASE; a standalone *batched* live run needs `LITHRIM_COUNCIL_BACKEND=http`.
- Carried (all post-v1, triaged in `RELEASE_v1.md`): S-BS-98 (med, judge store global-per-role) · S-BS-105 (med, shell can't drive the in_process model-mix ladder — **partly addressed**: "Run live" now drives the in-process council) · S-BS-96/101/102/104/106/107/108 (low). Plus the imported-case-500-on-replay bug logged under the CHATBIND-2 session log (collided label; imported cases are post-v1/CUT — out of scope).

## CITATION-DRIFT (fix the kickoff guidance)
`PYENV_VERSION=debuglithrim python` resolved to **3.12.8** (no openai/dspy → council tests *spuriously skip*). Use the **explicit** interpreter path `~/.pyenv/versions/3.10.15/envs/debuglithrim/bin/python` for the green bar. Memory `council-runtime-test-env` updated with the caveat. [[council-runtime-test-env]]

## Git state (NOT pushed — owner-gated)
- Branch `bench-salvage/ws6c-dspy`. Executor stack `84c3c82`→`4dbc417`→`ec526f4` (+ session log `9b6d3c1`); concurrent `0793a8c` (CHATBIND-2 A-LIVE capsule) interleaved above — pathspec-only kept it out. A **large unpushed stack** (UX-1 → here). **Push/PR/tag is owner-gated** (RELEASE_v1.md = the checklist).
- Working tree: `M apps/shell/src/root.jsx` (concurrent session — LEAVE it) + foreign untracked (`.claude/`, the WS-6c critic kickoff, the FHIR report). **All monitor commits pathspec-only** (`git commit -- <files>`). [[git-commit-pathspec-dirty-index]]

## Standing context
- **The user runs the executor sessions + the paid/live runs.** The monitor audits, gives the go, runs the close, commits close artifacts pathspec-only.
- **Prefs:** no autostart (`curl /health`, halt+ask if down); **no push without explicit owner approval**; LLM-cost-conscious (paid runs authorized explicitly); **honest-Δ only** (an honest loss/non-result is a PASS, documented); **don't digress / launch ASAP** (resist scope creep; park vision as specs).
- **A-SAFE is sacred** for any chat-surface change: deny-hook + allowlist + the replay-only `$0` contract byte-identical; HARD-GATE → fresh-critic. [[conversational-authoring-surface-complete]]

## Pointers
- **Drivers:** `…phaseLAUNCH-PREP…` (shipped) · `…phaseCHATBIND-2…` · `…phaseCHATBIND-1…`. `.devloop/prompts/index.json`.
- **Docs:** `docs/QUICKSTART.md` · `docs/RELEASE_v1.md` (the push checklist + seam-triage) · `docs/specs/SPEC_EVAL_SCENARIOS.md` + `SPEC_PLUGIN_ARCHITECTURE.md` (PARKED post-v1).
- **Closes:** `critique-bench-salvage-LAUNCH-PREP-2026-06-09.md` + `session-bench-salvage-LAUNCH-PREP-2026-06-09.json`.
- **State:** `STREAM_bench-salvage.md` (First-move topped with the A-LIVE-next + the LAUNCH-PREP close) + `streams.json`.
- **Memory:** `conversational-first-core-plugin-line` (the v1 pivot + the CUT), `gtm-launch-and-journey-thesis` (open-core/BYO-key/no-us-hosted), `council-runtime-test-env` (the interpreter caveat), `git-commit-pathspec-dirty-index`, `proof-capsule-convention`.
