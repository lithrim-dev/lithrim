# Driver — `bench-salvage` phase `CRUD-1`: judge + agent DELETE + blank-slate create (guarded, audited)

> **Bundle ID:** `bench-salvage-phaseCRUD-1-judge-agent-delete-blank-slate-driver`
> **Stream:** `bench-salvage` · **Target repo:** `lithrim-bench` · **Branch:** `bench-salvage/ws6c-dspy` (dirty shared — pathspec-only; note: a concurrent session's `apps/shell/src/root.jsx` edit is uncommitted in the tree — do NOT touch/sweep it).
> **Hardness:** **HARD-GATE** — adds new DELETE routes (API-contract change) + a config-plane delete primitive + a conversational delete tool (A-SAFE surface). Fresh-critic at close.
> **Objective served:** user objective #2 — "ability to CRUD on judges, flags… complete CRUD to allow creation and demonstration from a clean state." CRUD-1 = the **judges + agents** half (local, no taxonomy collision). Flags = FLAG-1 (separate, reference-local). User scope decision (2026-06-07): **guarded CRUD + admissibility gates.**

---

## KICKOFF (paste into a fresh executor session)

```
You are the executor for bench-salvage phase CRUD-1 (judge + agent DELETE + blank-slate create).
Read EXECUTOR.md first, then this driver in full:
  .devloop/prompts/bench-salvage_phaseCRUD-1_judge-agent-delete-blank-slate_driver.md

HARD-GATE (new DELETE API + a conversational delete tool = an A-SAFE surface). Fresh-critic at close.
Services up (:8787 BFF, :5180 shell); do NOT autostart — curl /health first. Council/BFF tests run under
PYENV_VERSION=debuglithrim; the default suite is plain python3. Canonical test cmd = `pytest -q` (pyproject
testpaths), NOT `pytest tests/` (a subset — see S-BS-96). The 2 observation-isolation failures are
pre-existing + BYOC-1-independent; don't be alarmed, but don't add new ones.

What you're building:
  D1  harness delete primitives: delete_judge + delete_agent + list_agents, each AUDITED (action="delete").
  D2  BFF: DELETE /v1/judges/{role} + DELETE /v1/agent?name= + GET /v1/agents, guarded (refuse the seed
      default + the last agent) + audited.
  D3  a conversational delete_judge tool (revert a judge to its default lens; audited; A-SAFE-bounded).
      Agent-delete stays HUMAN-ONLY (not an agent tool) — too destructive, mirrors flag-create's human-act posture.
  D4  blank-slate: the shell "New evaluation" creates + switches to a fresh empty agent (extends UX-1's
      remount reset) + a GET /v1/agents rail switcher.
  D5  tests (delete audited + guards + judge-revert + the A-SAFE bound on the new tool) + the :5180 smoke.

Post a plan-review resolving D-A..D-E BEFORE any code. Do not code until I say "go".
Pathspec-only commits; runs/provenance are append-only — do NOT add run-delete.
```

---

## 0. Why
Today the config plane is create/update-only — `PUT /v1/agent` / `PUT /v1/judges/{role}` upsert, but **nothing can be deleted** (no route, no harness primitive, no tool — confirmed: `grep @app.delete` → none) and there's **no `list_agents`**. So a user can author but never clean up, and "demonstrate from a clean state" means starting from the seeded `ws0_default`, not a fresh empty agent. CRUD-1 closes the **D** in CRUD for judges + agents and adds the blank-slate create flow — locally, with no taxonomy-contract collision (that's FLAG-1).

**Invariant note (why this half is safe):** the production judge trio (`risk/policy/faithfulness`) is fixed by `LENS_BY_ROLE` ([judge_metric.py:110](lithrim_bench/runtime/council/judge_metric.py:110)). "Deleting a judge" therefore means **removing its authored `JudgeConfig` so the role reverts to its default lens** — the role never disappears, no flag is orphaned. That's why judge-delete is inherently safe and can be agent-exposed; agent-delete (removing a whole eval profile) is the destructive one and stays human-only.

## 1. Pre-flight (citations re-grepped 2026-06-07 — re-grep before you cite in commits)
- **harness/judges.py:** `JudgeConfig` ([:50](lithrim_bench/harness/judges.py:50)), `save_judge` ([:75](lithrim_bench/harness/judges.py:75)), `load_judge` ([:119](lithrim_bench/harness/judges.py:119)), `list_judges` ([:131](lithrim_bench/harness/judges.py:131)). **No delete_judge** → add it.
- **harness/config.py:** `save_agent` ([:148](lithrim_bench/harness/config.py:148)), `load_agent` ([:198](lithrim_bench/harness/config.py:198)), `_record` (action `"edit" if before else "author"`, [:172](lithrim_bench/harness/config.py:172)). **No delete_agent / no list_agents** → add both.
- **harness/audit.py:** `AuditRecord.action` is an open enum (`author | edit | … | withstand | …`, [:83](lithrim_bench/harness/audit.py:83)) → use `action="delete"`; `AuditLog.record` ([:111](lithrim_bench/harness/audit.py:111)); `upsert_with_audit` ([:179](lithrim_bench/harness/audit.py:179)) — the write+audit one-transaction pattern to MIRROR for a `delete_with_audit` (row removal + the `before=removed-doc, after=None` record in ONE txn).
- **harness/collections.py:** `insert` ([:59](lithrim_bench/harness/collections.py:59)), `list_all` ([:104](lithrim_bench/harness/collections.py:104)) — **no delete, and keep it that way** (runs/provenance are immutable source-of-truth; [[persistence-blob-projection-architecture]]).
- **BFF write-path to MIRROR:** `put_agent_endpoint` ([app.py:438](apps/bff/app.py:438)) + `put_judge_endpoint` ([:608](apps/bff/app.py:608)) + `_validate_judge_assignment` ([:508](apps/bff/app.py:508)) + `_resolve_actor`/`AuditLog` + the `X-Actor`/`rationale` audit args + `get_agent_endpoint` ([:428](apps/bff/app.py:428), 404 pattern).
- **Conversational tools:** `_TOOL_SPECS` ([tools.py:286](apps/bff/agent/tools.py:286)) — the frozen 8; `PAID_KEYS` ([:69](apps/bff/agent/tools.py:69)); `author_judge`/`assemble_agent` handlers as the edit-tool pattern; the ASAFE-1 deny-hook `_deny_non_lithrim` ([loop.py:55](apps/bff/agent/loop.py:55)) — any new tool inherits it + the allowlist-bound + no-paid-knob tests (S-BS-81/90).
- **Shell:** the UX-1 New-eval remount (`app.jsx` `sessionKey` [:75](apps/shell/src/app.jsx:75) / `onNewEval` [:124](apps/shell/src/app.jsx:124)); `bff.js` (`getAgent`/`putAgent`); the LeftRail New-eval button (`panes.jsx:29`).

## 2. Deliverables (file-by-file)

### D1 — harness delete primitives (audited)
- **`lithrim_bench/harness/judges.py`** — `delete_judge(role, *, db_path, actor, audit_log, rationale) -> bool`: remove the `JudgeConfig` row + write an `AuditRecord(action="delete", target.type="judge", before=<the row>, after=None, why=rationale)` in ONE txn (mirror `save_judge` + `upsert_with_audit`). Idempotent (deleting an unauthored role is a no-op that still audits the intent OR returns false — D-A).
- **`lithrim_bench/harness/config.py`** — `delete_agent(name, *, …)` (audited, same pattern) + `list_agents(*, db_path) -> list[str]` (names; for the GET route + the delete-guard).

### D2 — BFF DELETE routes + the agents list
- **`apps/bff/app.py`** —
  - `GET /v1/agents` → `{agents: [names]}` (uses `list_agents`).
  - `DELETE /v1/judges/{role}` → `delete_judge`; the role reverts to its default lens; audited (`X-Actor`+`rationale`); 404 on unknown role (`role not in LENS_BY_ROLE`).
  - `DELETE /v1/agent?name=` → `delete_agent`; **guards (422/409):** refuse deleting `ws0_default` (the seed default) and refuse deleting the **last** remaining agent (non-empty config plane); audited. 404 on unknown name.
  - All three mirror the `put_*` actor/audit pattern; NEVER touch the committed seed JSON.

### D3 — the conversational `delete_judge` tool (A-SAFE)
- **`apps/bff/agent/tools.py`** — add `delete_judge` to `_TOOL_SPECS` (now 9): a thin wrapper over the bound `delete_judge` op; **no paid knob** (`PAID_KEYS`-clean), audited, renders an EXISTING card (the `tool-judge_editor` showing the reverted default). It reverts a judge to default — reversible, bounded. **Agent-delete is NOT a tool** (human-only; D-B).
- **`apps/bff/app.py`** — the bound `_delete_judge` inside `_build_tool_context` (mirror `_author_judge`); the new tool inherits the ASAFE-1 deny-hook automatically (it's `mcp__lithrim__*`).

### D4 — blank-slate create + switch (the "from clean state" demo)
- **`apps/shell/src/bff.js`** — `listAgents()` + `createAgent(name)` (PUT a minimal empty `Agent`) + `deleteAgent(name)`.
- **`apps/shell/src/panes.jsx` + `app.jsx`** — the LeftRail "New evaluation" (`panes.jsx:29`) now **creates a fresh empty agent** (name it; default like `eval-N`) + switches `CenterPane` to it (extend the UX-1 `sessionKey` remount to also set the active agent). A rail agent list (from `GET /v1/agents`) to switch/delete. The active agent threads to `run_eval`/`get_agent` (today hardcoded `ws0_default`).

### D5 — tests
- **`tests/test_crud_delete.py`** (new): `delete_judge` reverts to default + writes an `action="delete"` audit row; `delete_agent` audited + the guards (422 on `ws0_default`, 422 on the last agent); `list_agents`. BFF: the DELETE routes + 404s + the guards (TestClient, debuglithrim `[bff]`).
- **A-SAFE (load-bearing):** extend the allowlist-bound test — the tool set is now **9**, all `mcp__lithrim__*`, still no-paid-knob across all 9 (the new `delete_judge` included); the `delete_judge` tool reverts-only (can't delete an agent, can't fire paid). Prove non-vacuous.
- **Vitest:** the rail create/switch/delete + the New-eval-creates-a-new-agent flow.

## 3. Plan-review decisions (resolve ALL before coding)
- **D-A.** Judge-delete semantics: **revert-to-default** (remove the `JudgeConfig`; recommended) — confirm vs any "hard remove." Idempotency on an unauthored role (no-op+audit vs 404).
- **D-B.** Conversational delete scope: `delete_judge` agent-exposed (reversible) **+ agent-delete human-only** (recommended) — confirm the agent gets no agent-delete tool.
- **D-C.** Agent-delete guards: refuse `ws0_default` + the last agent (recommended). Any others (an agent with persisted runs)?
- **D-D.** Blank-slate UX: New-eval **creates a new empty agent + switches** (name prompt vs auto `eval-N`); the rail switcher/list shape.
- **D-E.** The active-agent threading: today the shell hardcodes `ws0_default`; how far to thread the selected agent into `run_eval`/`get_agent`/the chat (scope — keep minimal: the selected agent id in `App` state → the existing props).

## 4. Scope guardrails — NOT in scope
- **Flags** — all flag CRUD is **FLAG-1** (reference-local). Do NOT touch the ontology/taxonomy here.
- **Run / provenance delete** — runs are append-only immutable source-of-truth; do NOT add `collections` delete or a run-delete route.
- **The taxonomy snapshot** + `_validate_*` gates — untouched.
- **`apps/shell/src/journey/*`** (frozen) + the concurrent session's `root.jsx` (uncommitted, not yours).
- **No new paid path.** The new tool is delete-judge-revert only; `_apply_consensus` + the per-judge seam + seeds frozen (0-delta).

## 5. Acceptance
- **A1 — delete works + audited.** `DELETE /v1/judges/{role}` reverts the role to its default lens; `DELETE /v1/agent` removes it; each writes an `action="delete"` `AuditRecord` visible at `GET /v1/audit` (who/when/what/why). LIVE on `:8787`.
- **A2 — guards hold.** `DELETE /v1/agent?name=ws0_default` → 422; deleting the last agent → 422; unknown role/name → 404.
- **A3 — blank-slate from clean.** On `:5180`, "New evaluation" creates a fresh empty agent + switches to it (the chat + config start clean, not `ws0_default`); the rail lists agents + can switch/delete.
- **A-SAFE.** The conversational tool set is 9, all `mcp__lithrim__*`, no-paid-knob across all 9 (non-vacuous); `delete_judge` reverts-only (the agent cannot delete an agent or fire a paid run); the ASAFE-1 deny-hook covers it.
- **A4 — frozen 0-delta.** `_apply_consensus` + the per-judge seam + `judge_metric` + seeds untouched (`git diff`); runs/provenance delete-free.
- **A5 — green bar.** Canonical `pytest -q` (debuglithrim + default) — no NEW failures vs the 2 pre-existing (S-BS-96); Vitest green; ruff clean.
- **A6 — scope.** `git diff --stat` = harness + BFF + shell + tests only; no flag/ontology/taxonomy/run-delete; `root.jsx`/journey untouched.
- **A7 — the load-bearing `:5180` smoke** (light + dark): create→switch→delete an agent; delete a judge → reverts; the audit trail shows the deletes. Screenshot.

## 6. Commit structure (atomic, pathspec-only)
1. `feat(harness): audited delete primitives — delete_judge + delete_agent + list_agents (action="delete")`
2. `feat(bff): DELETE /v1/judges/{role} + DELETE /v1/agent + GET /v1/agents (guarded, audited)`
3. `feat(bff): delete_judge conversational tool (revert-to-default, A-SAFE-bounded; agent-delete stays human-only)`
4. `feat(shell): blank-slate New-evaluation — create+switch a fresh agent + the rail agents list`
5. `test(crud-1): delete audit + guards + judge-revert + the 9-tool A-SAFE bound` (+ session log)

## 7. Verification checklist
- [ ] D-A..D-E resolved; user "go". · A1-A7 met; A7 screenshot. · canonical `pytest -q` (paste counts) + Vitest + ruff. · `git diff --stat` scope clean; runs delete-free; seam 0-delta. · pathspec-only; `root.jsx`/foreign untouched. · session log + `next_session_hint` (monitor: `/devloop-critique` fresh-critic, then FLAG-1).

## 8. First move
1. Read `EXECUTOR.md` + this driver. 2. `curl :8787/health` + `:5180` (no autostart). 3. Skim the `put_*` audited-write pattern + `upsert_with_audit` + `LENS_BY_ROLE`. 4. Resolve D-A (delete semantics) first; post the plan-review.

## 9. References
- The CRUD surface scan + the audited-write pattern (this driver §1).
- Memories: `git-commit-pathspec-dirty-index`, `persistence-blob-projection-architecture` (runs immutable), `conversational-authoring-surface-complete` (the tool-surface posture), `three-objectives-ux-crud-byoc-2026-06`.
- Seam follow-on: **FLAG-1** (reference-flag create/delete; the gradeable path is cross-repo).
