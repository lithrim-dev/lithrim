# Spec-Adherence Critique — `bench-salvage` phase `UAP-1`

> Fresh-critic session (HARD GATE). Committed alongside close-out artifacts.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `UAP-1` (config-plane write-path `/v1/agent` + draft→grade loop + audit-record/actor foundation)
- **Driver bundle:** `bench-salvage-phaseUAP-1-config-plane-write-path-driver`
- **Commits audited:** `6bdf975..a7edd25` (8 commits incl. the `c2e01ae` session-log commit); base `f641b05`, HEAD `c2e01ae`
- **Spec(s) read against:** `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §2A/§2B/§3/§4/§5/§6/§7/§8/§12 · `docs/specs/SPEC_PRODUCT_SHELL.md` §10 (ratification) · driver §2/§3/§4/§5
- **Critique mode:** `fresh-critic` (separate session, no prior implementation context)
- **Date:** `2026-06-04`
- **Reviewer:** `critic session-2026-06-04-fresh`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

One sentence: UAP-1 faithfully lands R0+R1+R3 against the locked §2B/§4/§5/§6 contract — surface matches, all three traced behaviors close, the frozen seam + committed seeds are provably 0-delta, and the audit log is genuinely INSERT-only with an honest (never-masquerading) actor — with only one doc-staleness nit and two faithful-minimal-projection open questions; the sole gate not closed is A8 (`:5180` visual smoke), which is user-owed by design, not drift.

---

## 1. Surface fidelity

> Does the public API match spec §4 / §2B exactly?

### BFF route table (spec §4, line 187; ratified into `SPEC_PRODUCT_SHELL §10`)

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| `GET /v1/agent` → load assembled Agent, 404 on unknown | `app.py:275` `get_agent_endpoint(name)` → `agent_to_dict(_load_agent(...))`; 404 via `_load_agent` (`app.py:150`) | exact | — |
| `PUT /v1/agent` → save Agent, 422 on malformed | `app.py:285` `put_agent_endpoint`; `agent_from_dict` round-trip → **422** (`app.py:303-304`); writes config-DB only | exact | — |
| `GET /v1/audit?actor=&target_type=&target_id=&since=` | `app.py:400` `get_audit_endpoint` with those exact 4 query params → `AuditLog.query(...)` | exact | — |
| `GET /v1/runs/{id}/audit` (404 for un-persisted/replay) | `app.py:447` `get_run_audit_endpoint`; `PIPELINE_RUNS.get` is None → **404** (`app.py:461-465`) | exact | — |
| "actor-attributed + audit-logged config writes" | both `PUT /v1/agent` and `PUT /v1/ontology` (`app.py:384`) emit an `AuditRecord` with `_resolve_actor` | exact | — |

**CONFIRMED** — every route name, the query-param set, and the 422/404 taxonomy match spec §4 line-for-line. Independently re-ran `tests/test_ws5_bff.py` + `tests/test_audit.py`: **33 passed, 0 failed** (`PYENV_VERSION=debuglithrim python3 -m pytest`). The 422 path is exercised by `test_agent_put_rejects_malformed` (test_ws5_bff.py:309), the 404 by `test_unknown_agent_get_is_404` (:314) and `test_run_provenance_unpersisted_run_is_404_not_500` (:440).

### `AuditRecord` field set vs §2B (audit.py:76-88)

Spec §2B shape: `ts, actor{type,id}, action, target{type,id}, why, before, after, run_id, case_id`.

```python
# lithrim_bench/harness/audit.py:76-88 — VERBATIM
class AuditRecord(BaseModel):
    ts: str = Field(default_factory=now_iso)
    actor: Actor                       # Actor{type,id}  (audit.py:62-66)
    action: str
    target: Target                     # Target{type,id} (audit.py:69-72)
    why: dict[str, Any] = Field(default_factory=dict)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    run_id: str | None = None
    case_id: str | None = None
```

**CONFIRMED** — all 9 §2B fields present, named exactly, with the documented sub-shapes. Pydantic v2 (`BaseModel`/`Field`), per CLAUDE.md "no v1 syntax". Locked by `test_audit_record_carries_the_2b_shape` (test_audit.py:41).

### Agent / EvalProfile shape vs §4 (config.py)

**CONFIRMED** — `EvalProfile` (config.py:45-53) carries `judges, council_config, ontology_ref, ontology_path, tools, kb_bindings, severity_map_ref` and `Agent`/`Dataset` match §4 (lines 160-171). UAP-1 did **not** alter these shapes — `save_agent` gained only keyword args (`actor`, `audit_log`, `rationale`) appended after `*`, preserving the existing signature.

**Findings:**

- No surface drift detected. All public symbols (4 new BFF routes, the `AuditRecord`/`Actor`/`Target` models, the `save_agent` extension, the `run_eval.run(ontology_path=...)` param) match spec §4/§2B exactly. The route additions are documented as a **sanctioned plan-review decision** (driver §3.6 — "ratify in-cycle") and the ratification landed in `a7edd25` (`SPEC_PRODUCT_SHELL §10`, +4/-1), closing S-BS-51 rather than repeating it. Classification: **authorized**.

---

## 2. Behavioral fidelity

### Behavior 1: A2 / R3 draft→grade — a PUT-ed working copy grades, not the committed seed

- **Spec assertion:** §3 Stage-2.NET-NEW.1 — "Close the draft→grade loop (S-BS-26b). A `PUT /v1/ontology` draft does NOT yet feed a run … Stage 3's run must read the agent's working-copy ontology so 'edit the flag → see it grade' actually holds." Driver A2.
- **Test:** `test_ws5_bff.py:321` `test_draft_ontology_grades_not_the_committed_seed` — asserts baseline `verdict=="reject"` + `ontology_source=="committed"`; PUTs a draft with `block_at_or_above=99.0`; then asserts `ontology_source=="draft"` AND `stage_verdict != "BLOCK"` AND `verdict != "reject"` AND `ONTOLOGY_SEED.read_bytes() == seed_before`. Mirrored at the Python level by `test_audit.py:234` + `:249` (override vs no-override **diverge**).
- **Implementation:** `_resolve_ontology_path` (`app.py:133-140`) prefers `workdir/<agent>.json` (returns `"draft"`) else the committed seed (`"committed"`); `run_eval_endpoint` (`app.py:195-203`) passes the resolved path as `run_eval.run(..., ontology_path=...)`; `run_eval.run` (`scripts/run_eval.py:117`) sets `ontology_src = Path(ontology_path) if ontology_path is not None else agent.ontology_abspath()` and threads that ONE variable through BOTH reads (`:118` `load_ontology`, `:151` live-inject `read_text`).
- **Chain closes?** **YES.**
- **Note:** **CONFIRMED** the change is a *real verdict flip driven by the working copy*, not a vacuous file-read assertion: `grounding.py:503` computes `verdict=ontology.severity_map.rescore(active)`, so raising `block_at_or_above` genuinely lifts the BLOCK threshold above the active risk weight. The committed-seed-untouched leg is asserted at both layers. (Executor's "reject→needs_review" landing value is plausible; the test only asserts `!= reject`, which is sufficient and robust.)

### Behavior 2: R0 audit immutability + "no un-attributed write" + N4 atomicity

- **Spec assertion:** §2B Invariant — "Audit records are **immutable + append-only** … No action — authoring or processing — escapes a record; an un-attributed write is a bug, not a silent default." §6 line 221. Driver A3.
- **Test:** `test_audit.py:94` `test_audit_log_has_no_update_or_delete_path` (`not hasattr` update/delete/remove); `:84` append-never-overwrite; `:140` `test_save_agent_emits_audit_in_one_transaction`; `test_ws5_bff.py:348` (2→3 rows append) + `:380` `test_product_write_with_no_actor_is_attributed_not_silent`.
- **Implementation:** `AuditLog` (`audit.py:99-175`) is INSERT-only — independently grepped for `UPDATE|DELETE|DROP|REPLACE INTO` in audit.py: **none** (only the prose "no update/delete method"). N4 atomicity: `save_agent` (`config.py:152-176`) opens ONE `conn`, executes the `agents` upsert (`:159`) AND `audit_log.record(rec, conn=conn)` (`:175`) on that same connection, with a single `conn.commit()` (`:176`); `AuditLog.record(conn=...)` (`audit.py:129-132`) rides the caller's transaction without its own commit.
- **Chain closes?** **YES.**
- **Note:** **CONFIRMED** no config write can occur without an attributed actor. Every actor-construction path resolves to either a real `{type:"user",...}` (only when a handle is supplied — `audit.py:96`) or an honest non-SME default (`{system, dev-default}` at `app.py:125`; `{system, seed}` at `audit.py:95`). There is **no path** where an absent actor masquerades as a `user`-typed SME — directly answers the adversarial "actor defaultable to a fake SME?" question: **no**. `before`/`after` are stored ONCE (top-level); `why={"rationale": ...}` carries no duplicate diff (`config.py:171`, `app.py:389`), and `test_audit.py:57` asserts `"before" not in why and "after" not in why`.

### Behavior 3: A5 frozen seam + back-compat byte-identity

- **Spec assertion:** §6 — "Frozen consensus seam. … `compliance_council._apply_consensus` stays byte-frozen (the whole DSPy track's A1)." Driver A5.
- **Test:** `test_audit.py:228` `test_run_no_override_grades_the_committed_seed` (no-override path still `reject`/`BLOCK`) + the `git diff` checks.
- **Implementation / independent verification:** I ran the exact commanded checks:
  - `git diff f641b05..HEAD -- lithrim_bench/runtime/council/compliance_council.py | wc -l` → **0**
  - `git diff f641b05..HEAD -- data/ontology/clinical_v1.json | wc -l` → **0**
  - `git diff f641b05..HEAD -- data/config/agents/ | wc -l` → **0**
- **Chain closes?** **YES.**
- **Note:** **CONFIRMED** `run_eval.run()` with no `ontology_path` is byte-identical behavior: `ontology_src` collapses to `agent.ontology_abspath()` (the prior expression), and the no-override test asserts the unchanged `reject`/`BLOCK` outcome. The `save_agent` extension is back-compat — absent `audit_log`, no audit table is even created (`test_audit.py:174` `test_save_agent_without_audit_log_records_nothing`).

**Findings:**

- All three traced behavior chains close end-to-end with non-vacuous assertions. **CONFIRMED** via independent test re-run (33 passed) + source tracing + the three `git diff … | wc -l` = 0 checks. No behavioral-fidelity finding.

---

## 3. Out-of-scope intrusion

Driver §2 deliverables: (1) `harness/audit.py` NEW; (2) `config.py` save_agent audit wiring; (3) `run_eval.py` `ontology_path`; (4) `apps/bff/app.py` routes + audit + R3 resolve; (5) `apps/shell/src/…` Agent editor + audit view + `bff.js`; (6) tests (`test_ws5_bff.py` extend, `test_audit.py` NEW, Vitest); (7) §10 ratification (decision §3.6).

`git diff f641b05..HEAD --name-status` (15 files + the session-log):

```
A  .devloop/sessions/session-bench-salvage-phaseUAP-1-2026-06-04.json   ← session log (sanctioned)
M  apps/bff/app.py                          ← deliverable 4
M  apps/shell/src/bff.js                    ← deliverable 5
A  apps/shell/src/genui/AgentEditor.jsx     ← deliverable 5
A  apps/shell/src/genui/AgentEditor.test.jsx← deliverable 6
A  apps/shell/src/genui/AuditView.jsx       ← deliverable 5
M  apps/shell/src/genui/index.js            ← deliverable 5 (barrel)
M  apps/shell/src/genui/registry.js         ← deliverable 5 (KNOWN_TOOLS)
M  apps/shell/src/genui/registry.test.jsx   ← deliverable 6 (N3)
M  apps/shell/src/panes.jsx                 ← deliverable 5 (mount points)
M  docs/specs/SPEC_PRODUCT_SHELL.md         ← deliverable 7 (§10 ratify)
A  lithrim_bench/harness/audit.py           ← deliverable 1
M  lithrim_bench/harness/config.py          ← deliverable 2
M  scripts/run_eval.py                      ← deliverable 3
A  tests/test_audit.py                      ← deliverable 6
M  tests/test_ws5_bff.py                    ← deliverable 6
```

- **`panes.jsx` (+10):** mounts `tool-agent_editor` + `tool-audit_log` into the conversation (panes.jsx:161-164). This is the §3.5 "UI shape" plan-review decision realized; it touches the **shell** (not `apps/shell/src/journey/*`). The journey tree is untouched (`grep "8787" apps/shell/src/ | grep -v journey/` → **none new**; the only `:8787` strings in scope are comments asserting "no hardcoded :8787"). **Within scope.**
- **No** backend edits, **no** paper files, **no** committed-seed edits, **no** `runtime/council/*.txt` or `judges_dspy/judge_metric/judge_optimize` edits (the UAP-2 carve-out is honored), **no** dependency bumps, **no** drive-by formatting (`ruff format --check` on the 4 changed Python files → "4 files already formatted").

**Self-disclosed S-BS-54 (GET/PUT /v1/ontology now 404 on unknown agent):** Independently judged. Sharing `_resolve_ontology_path` made both ontology endpoints call `_load_agent` first (`app.py:326`, `:377`). Previously `GET /v1/ontology` could serve a stray working copy with no agent row; now it 404s. This is **strictly-more-correct sanctioned-refactor fallout** of the §3.2 "factor a shared `_resolve_ontology_path` helper" decision — it tightens an undocumented edge (a working copy without an agent is incoherent), no existing test exercised the old behavior, and it does not alter any documented contract. **Acceptable; not scope drift.**

**Findings:**

- **[NON-BLOCKING]** All 15 diffed files map to driver §2 deliverables (+ the sanctioned session log). No intrusion detected. S-BS-54 is acceptable sanctioned-refactor fallout, not drift. **CONFIRMED** via `--name-status` + targeted greps. Nothing else leaked.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: §2B `why` for a user edit lists `{rationale, before→after}` AND top-level `before`/`after` (S-BS-53)

- **Spec text:** §2B simultaneously declares top-level `"before"` / `"after"` fields (lines 93-94) AND types the user-edit `why` as "`{ rationale, before→after }`" (line 103). The diff could be stored once (top-level) or twice (also nested in `why`).
- **Implementation decided:** top-level `before`/`after` are canonical; `why={"rationale": ...}` only (`config.py:171`, `app.py:389`, audit.py docstring:14-16). Locked by `test_audit.py:54-57`.
- **Alternatives also spec-compliant:** nesting the diff inside `why` (literal reading of line 103); storing in both places.
- **Question for spec author:** Should §2B line 103's "user authoring edit → `{rationale, before→after}`" be reconciled to `{rationale}` (diff lives top-level only)?
- **Recommended resolution:** **accept** the implementation; update §2B to say the diff is the top-level `before`/`after` and `why` carries only the action-typed justification (here `{rationale}`). The executor's resolution is **internally consistent** (single storage, asserted by absence). Tracked as S-BS-53.

### Ambiguity 2: run-provenance per-judge `evidence` projection attaches the STAGE-SHARED evidence to every judge (NEW — critic-found)

- **Spec text:** §2B types a "judge raise" `why` as `{ taxonomy_code, decision, reasoning, evidence_spans[], confidence|null }` — i.e. **per-judge** evidence spans.
- **Implementation decided:** `_run_audit_report` (`app.py:428`) sets each judge's `"evidence"` to `semantic.get("evidence")` — the **stage-level shared** evidence list — identically for every judge in `judge_votes`. The per-judge ground truth (`findings[].evidence_spans`, present in `judges_dspy.py:90`) IS preserved via `v.get("findings")` (`app.py:427`), but the separate top-level `"evidence"` field smears the shared list across all judges.
- **Alternatives also spec-compliant:** read per-judge evidence off the vote entry; or omit the redundant top-level `"evidence"` and rely on `findings[].evidence_spans`.
- **Question for spec author / UAP-3:** In a multi-judge run, should the report's per-judge `evidence` be that judge's own spans rather than the stage-shared list?
- **Recommended resolution:** **accept for UAP-1** — spec §3 Stage-3.NET-NEW and driver §2 explicitly scope this to "a minimal, faithful projection; the richer query/diff views are UAP-3." The single-judge test blob (`test_ws5_bff.py:405`) cannot expose the cross-judge smearing, so it should be a named follow-up so UAP-3 fixes attribution. Note: low impact — the authoritative per-judge spans survive in `findings`.

**Findings:**

- **[OPEN-QUESTION]** S-BS-53 — §2B `why` vs top-level `before/after` duplication; implementation chose single top-level storage, internally consistent. (Already logged by executor; **CONFIRMED** at §2B lines 93-94 vs 103.)
- **[OPEN-QUESTION]** Run-provenance projection attaches stage-shared `evidence` to every judge rather than per-judge spans (`app.py:428`). Faithful-minimal per UAP-1 scope; per-judge truth survives in `findings[]`; refine in UAP-3. (Critic-found; not in the executor's seam list.)

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 1 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 2 |

Plus one cross-cutting **NON-BLOCKING** doc-staleness nit (below), surfaced under Q1/Q3.

**Total BLOCKING: 0** → cycle MAY close (with the listed follow-ups + the user-owed A8 smoke).

---

## Required actions (if any)

No BLOCKING findings — no required corrections.

NON-BLOCKING / OPEN-QUESTION dispositions:

1. **Finding (NON-BLOCKING, doc-staleness):** `apps/bff/app.py` module docstring (lines 26-28) still asserts the working copy "does not feed an eval run, which still reads the committed seed (run_eval.py:118); wiring edits into grading is a later phase" — directly **contradicted by R3 in this very cycle** (`_resolve_ontology_path` → `run_eval.run(ontology_path=...)`, app.py:195-203). The `run_eval.py:118` citation is also stale (the read is now at :118/:151 after the threading). **CONFIRMED** via `grep -n "does not feed an eval run\|run_eval.py:118" apps/bff/app.py`. The executor *self-disclosed* this as a CITATION-DRIFT deviation (session log line 17) and consciously left it as "out-of-scope." Doc-only, zero behavioral impact.
   **Proposed disposition:** accept for close; fix the top-of-file docstring in the next BFF-touching cycle (or as a trivial doc follow-up) so the module header matches its own code. Not worth reopening UAP-1.

2. **Finding (OPEN-QUESTION):** S-BS-53 — §2B diff-storage ambiguity.
   **Proposed disposition:** spec update in a separate docs cycle; reconcile §2B line 103 to single top-level storage. Implementation accepted as-is.

3. **Finding (OPEN-QUESTION):** Run-provenance per-judge `evidence` smearing (`app.py:428`).
   **Proposed disposition:** log as a seam (suggest S-BS-55) bound to UAP-3's richer run-provenance projection; accept the faithful-minimal UAP-1 behavior. Per-judge spans are not lost (preserved in `findings[].evidence_spans`).

**Re: A8 (the load-bearing `:5180` visual smoke).** The session log marks A8 **SKIP / OWED** (user-run, no-autostart). This is **not drift** — it is the explicitly user-attested gate (driver §5 A8, SPEC §7). The cycle's automatable gates A1-A7 are independently confirmed green here; A8 remains the user's to attest, and the run→audit leg requires a cost-confirmed `in_process` run (replay persists no provenance blob — S-BS-52, **CONFIRMED**: `run_eval.py:141` only the `in_process` branch constructs `SqliteProvenanceStore`).

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec (`SPEC_UNIFIED_AUTHORING_PRODUCT.md`) + driver + template BEFORE any code or the executor's session log.
- [x] Read the diff via `git diff`/`git show` against the commits, and read each cited file in full from source — not via the executor's summary.
- [x] Each finding cites both spec file:line/§ and implementation file:line (or a command-output evidence block).
- [x] Did NOT edit any code, spec, or driver — the only write is this critique document.
- [x] Did NOT confer with monitor or executor; formed the verdict independently. The session log was read LAST, purely to cross-check claims, and every executor claim was re-verified from source (the seam list, the `git diff` zeros, the 33-test pass, the actor paths) rather than trusted.
- [x] Did NOT read or weight any monitor audit verdict.

No audit drift.

---

## Appendix: commits audited

```
c2e01ae docs(bench-salvage): session log for phase UAP-1 (config-plane write-path)
a7edd25 docs(spec): ratify the UAP-1 BFF routes in §10 (close S-BS-51 pattern)
0e0ba22 test(uap-1): /v1/agent round-trip + draft→grade + audit records + run-provenance report
5e5d559 feat(shell): Agent editor + minimal audit view, routed through bff.js (UAP-1 R1 UI; S-BS-50)
d5722ea feat(bff): GET /v1/audit + /v1/runs/{id}/audit — why/when/who/what reports (UAP-1 R0)
a33728a feat(bff): GET/PUT /v1/agent + actor-attributed audit on config writes (UAP-1 R1+R0)
7a7b64d feat(harness): run_eval reads a working-copy ontology (UAP-1 R3 / S-BS-26b)
6bdf975 feat(harness): AuditRecord + append-only config-change audit log (UAP-1 R0)
```

## Appendix: files changed

```
 .devloop/sessions/session-bench-salvage-phaseUAP-1-2026-06-04.json | 169 ++++++++++++++
 apps/bff/app.py                                    | 217 ++++++++++++++++-
 apps/shell/src/bff.js                              |  36 ++-
 apps/shell/src/genui/AgentEditor.jsx               | 147 ++++++++++++
 apps/shell/src/genui/AgentEditor.test.jsx          |  70 ++++++
 apps/shell/src/genui/AuditView.jsx                 | 117 ++++++++++
 apps/shell/src/genui/index.js                      |   4 +
 apps/shell/src/genui/registry.js                   |   2 +
 apps/shell/src/genui/registry.test.jsx             |  11 +-
 apps/shell/src/panes.jsx                           |  10 +
 docs/specs/SPEC_PRODUCT_SHELL.md                   |   5 +-
 lithrim_bench/harness/audit.py                     | 175 ++++++++++++++
 lithrim_bench/harness/config.py                    |  40 +++-
 scripts/run_eval.py                                |  15 +-
 tests/test_audit.py                                | 260 +++++++++++++++++++++
 tests/test_ws5_bff.py                              | 175 +++++++++++++-
 16 files changed, 1423 insertions(+), 30 deletions(-)
```

## Appendix: independently-run verification commands

```
$ git diff f641b05..HEAD -- lithrim_bench/runtime/council/compliance_council.py | wc -l   → 0
$ git diff f641b05..HEAD -- data/ontology/clinical_v1.json | wc -l                          → 0
$ git diff f641b05..HEAD -- data/config/agents/ | wc -l                                     → 0
$ grep "8787" apps/shell/src/ -r | grep -v journey/                                         → (none outside journey)
$ PYENV_VERSION=debuglithrim python3 -m pytest -q tests/test_ws5_bff.py tests/test_audit.py → 33 passed, 1 warning
$ node_modules/.bin/vitest run AgentEditor.test.jsx registry.test.jsx                       → 16 passed (2 files)
$ PYENV_VERSION=debuglithrim ruff check <6 deliverables>                                     → All checks passed!
$ PYENV_VERSION=debuglithrim ruff format --check <4 changed .py>                             → 4 files already formatted
$ grep -in "update|delete|drop|replace into" lithrim_bench/harness/audit.py                  → (no mutation SQL; INSERT-only)
```
