# SHEPHERD-1c — driver (executor)

> Close the two **pre-existing** seams SHEPHERD-1b surfaced as the A3 honest-loss, so a judge
> authored in-pack is admissible AND ticks the rail's Judges step — making the deferred "rail ticks
> to done" demo beat reproduce. Scope set by the user ("go 1c"); the S-BS-153 fix approach is
> **user-locked: "Roster-add on judge save"** (Option A below).
>
> **The diagnosis here SUPERSEDES the SHEPHERD-1b handoff framing.** A read-fan-out (4 readers + 4
> adversarial verifiers, all CONFIRMED) corrected it. Evidence is in §0 — verbatim, not prose.

---

## §0 — Verbatim evidence (diagnose-before-edit)

### S-BS-154 (CONFIRMED) — offered lens codes come from the **process boot pack**, the gate checks the **active workspace pack**

`apps/bff/app.py` `_judge_summary` builds the editor's offered options from the module-global `LENS_BY_ROLE`:

```python
# app.py ~860 (_judge_summary; served by GET /v1/judges (list ~948) and GET /v1/judges/{role} (~980))
lens = sorted(LENS_BY_ROLE[role])
for code in lens:
    fd = ontology.flag(code)
    available.append({"flag": code, "tier": ..., "when_to_use": ..., "gradeable": ..., "assigned": code in assigned})
...
"available_flags": available,
```

`LENS_BY_ROLE` is resolved **once at import time** → it tracks the BFF *boot* pack (the neutral `_core` default), NOT the per-request active workspace:

```python
# lithrim_bench/runtime/council/judge_metric.py:64-66   <-- FROZEN-SEAM-LOAD-BEARING; DO NOT MAKE LAZY
LENS_BY_ROLE: dict[str, frozenset[str]] = __import__(
    "lithrim_bench.harness.pack", fromlist=["pack_lenses"]
).pack_lenses()
```

The PUT gate runs **two** sequential 422 checks; the owner↔emit check uses the same process-global `LENS_BY_ROLE`, the snapshot check resolves **per-request** against the active workspace:

```python
# app.py:906-924 (_validate_judge_assignment)
lens = LENS_BY_ROLE[role]                                  # process-global (_core)
off_lens = sorted(c for c in assigned_flags if c not in lens)
if off_lens:
    raise HTTPException(status_code=422, detail=f"owner↔emit: {role} may only be assigned codes it owns+emits {sorted(lens)}; offenders: {off_lens}")
snapshot_codes = _active_snapshot_codes()                  # per-request, ACTIVE WORKSPACE pack
off_snapshot = sorted(c for c in assigned_flags if c not in snapshot_codes)
if off_snapshot:
    raise HTTPException(status_code=422, detail=f"assigned flags outside taxonomy snapshot (re-snapshot, do not hand-edit): {off_snapshot}")
```

```python
# app.py:1120-1127 + harness/admissibility.py:43-57  (the per-request resolver — the PATTERN to mirror)
def _active_snapshot_codes() -> frozenset[str]:
    return admissibility.active_snapshot_codes()
# admissibility.active_snapshot_codes():
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness import workspace
    return pack_mod.pack_taxonomy_codes(workspace.get_active_workspace().pack)
```

```python
# harness/pack.py:307 / :339  — pack_lenses + pack_taxonomy_codes read the SAME snapshot file, per pack
def pack_lenses(pack=None):  snap = json.loads(_pack_ref(pack or active_pack(), "flags_ref").read_text()); return {role: frozenset(codes) for role, codes in snap["lenses"].items()}
def pack_taxonomy_codes(pack=None):  return frozenset().union(*pack_tiers(pack).values())
```

Empirical: active workspace `demo-clinical` pins `pack: healthcare`. healthcare `risk_judge` lens =
`{MISSED_ESCALATION, SEVERITY_ESCALATION, WRONG_DOSAGE, MEDICATION_NOT_IN_TRANSCRIPT, FABRICATED_ALLERGY}`;
`_core` `risk_judge` lens = `{UNSUPPORTED_ASSERTION, INTERNAL_INCONSISTENCY}`. The editor (booted `_core`)
offers `INTERNAL_INCONSISTENCY`; the gate (healthcare) rejects it → the **live** `422 … ['INTERNAL_INCONSISTENCY']`
(PROOF SHEPHERD-1b). A `_core` code under a healthcare workspace = the smoking gun.

`JudgeEditor.jsx:147,204-218` binds ONLY to `judge.available_flags` (toggles, no free-form) — so fixing the
**server projection** fixes the editor with zero client guesswork.

### S-BS-153 (the handoff's "field-mapping gap" is REFUTED) — it's a **two-store split**

Rail read — `apps/shell/src/journey.js:37` (ep = `agentCfg.eval_profile`, :56):
```javascript
case "Judges":
  return (ep.judges || []).length > 0;     // tracks the per-agent ROSTER eval_profile.judges
```

Two distinct stores / two save buttons:
```python
# (A) PUT /v1/agent  (AgentEditor "Save agent" putAgent  +  conversational assemble_agent tool, app.py:1692-1714)
current["eval_profile"]["judges"] = judges        # writes the per-agent roster -> ADVANCES the rail
put_agent_endpoint(agent=current, ...)            # audited

# (B) PUT /v1/judges/{role}  (JudgeEditor "Save judge" putJudge, app.py:991 -> save_judge)
#     -> a SEPARATE global JudgeConfig SQLite table (judges.py:42 CREATE TABLE judges) -> does NOT touch eval_profile.judges
```

```python
# config.py:293-303  load_agent reads ONLY the agents table; never merges the judge store
row = conn.execute("SELECT json FROM agents WHERE name = ?", (name,)).fetchone()
```

So configuring a judge via the JudgeEditor (PUT /v1/judges/{role}) leaves `eval_profile.judges` empty and the
rail's Judges step never ticks. **There is no field-name mismatch** — write and read both key on
`eval_profile.judges`; the gap is that the per-role lens-config save doesn't add the judge to the active
agent's roster.

**SEAM REACH (both seams):** every cited symbol is config-plane / BFF projection / authoring-gate. NONE touch
`compliance_council.py`, `_apply_consensus`, `signals.py`, `apps/bff/agent/tools.py`, or `_deny_non_lithrim`.

---

## Work items

### W1 — S-BS-154: pack-aware offered lens, per active workspace (BFF only)

Add an active-workspace lens resolver in `apps/bff/app.py` mirroring the existing `_active_snapshot_codes`
lazy-import pattern, e.g.:

```python
def _active_lens_by_role() -> dict[str, frozenset[str]]:
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness import workspace
    return pack_mod.pack_lenses(workspace.get_active_workspace().pack)
```

Use it consistently in the **three** authoring touch-points so OFFER and GATE agree:

1. `_judge_summary` (`lens = sorted(LENS_BY_ROLE[role])` → the active-workspace lens) so `available_flags`
   reflects the active pack.
2. `_validate_judge_assignment` owner↔emit check (`lens = LENS_BY_ROLE[role]`) → the active-workspace lens,
   so offering healthcare codes does not merely move the 422 from the snapshot-check to the owner↔emit-check.
3. The role enumeration in the GET /v1/judges list (`for role in sorted(LENS_BY_ROLE)`) → the active-workspace
   pack's roles (healthcare `production_judges` = the same trio, so this is a no-op for healthcare but keeps
   the three reads on one source-of-truth). Confirm the unknown-role 404 guards still use a resolver that
   includes the active-pack roles.

**HARD GUARDRAILS for W1:**
- **DO NOT** touch `judge_metric.py:64` `LENS_BY_ROLE`. It is byte-imported by the **byte-frozen** `signals.py`
  (`signals.py:40`, used as the withstands-gate default `lens_by_role` at `signals.py:85/100/132`). Making it
  lazy/per-request changes the **moat's runtime scope-check** — the adversarial verifier explicitly
  **disqualified** this. Confine all per-workspace resolution to `apps/bff/app.py`.
- **KEEP** the snapshot defense-in-depth check (app.py:918-924) — it is the by-construction backstop for a
  future pack whose `lenses` could list a code outside `tiers`. Do not remove it to "simplify".
- `LENS_BY_ROLE` may remain imported at `app.py:113` if still used elsewhere; just stop using it as the
  authority for offer/gate. (If it ends up unused, removing the import is fine — but do not touch `judge_metric`.)

### W2 — S-BS-153: roster-add on judge save (user-locked Option A)

When a judge is saved **for the active agent**, also add that role (idempotent) to that agent's
`eval_profile.judges`, persisted via the **audited** agent PUT — so "author a judge → it's on this agent →
the rail ticks". Prefer the **server-side** locus (atomic + audited + one source of truth):

- Give `PUT /v1/judges/{role}` an **optional `agent`** param. When provided, after `save_judge` succeeds,
  idempotently add `role` to that agent's `eval_profile.judges` and persist via `put_agent_endpoint(...)`
  (the same audited path `_assemble_agent` uses). No-op if already present. Do NOT mutate any other agent.
- Shell `JudgeEditor` "Save judge" passes the **active agent** (it already fetches via `getJudge(role,{agent})`,
  so it has the context). Wire `putJudge` to send the active agent.
- Conversational path: confirm the `author_judge` SDK-MCP tool has/sets the active-agent context so it benefits
  too; if it does not currently know the active agent, the shepherd's existing `assemble_agent` add_judge tool
  already advances the rail — note this in the plan-review rather than expanding tool scope.

**Constraints:** idempotent; only the **active/named** agent's roster changes; editing an existing judge's lens
must not remove it from rosters; the roster add must go through the audited `put_agent_endpoint` (an AuditRecord
for the roster change). Do NOT change `journey.js` `deriveSteps`/`isDone` (the predicate is correct — keep it pure).

### W3 — refresh wiring (make the tick visible)

After a judge save (+ roster add), the shell must re-fetch `GET /v1/agent` and re-derive the rail so Judges
visibly ticks. The S-BS-153 verifier noted neither editor passes `onConfigSaved`. Confirm the JudgeEditor save
triggers the existing `refreshJourney`/`onConfigSaved` loop (the SHEPHERD-1 W3 path); if not, wire it minimally.
No `journey.js` logic change.

### W4 — tests (non-vacuous, network-free, fixture-based)

- **S-BS-154 (BFF, debuglithrim):** with the **healthcare** workspace active, `GET /v1/judges/{role}` offers
  healthcare lens codes (asserts a healthcare code present, asserts `INTERNAL_INCONSISTENCY` absent); `PUT
  /v1/judges/{role}` with a healthcare lens code (e.g. `MISSED_ESCALATION` for `risk_judge`) returns 200; with
  a `_core` code (`INTERNAL_INCONSISTENCY`) still 422s. Assert `judge_metric.LENS_BY_ROLE` is **unchanged**
  (still the boot-pack value) — proving the fix lives in the projection/gate, not the frozen module global.
- **S-BS-153 (BFF):** `PUT /v1/judges/{role}?agent=X` adds `role` to `X`'s `eval_profile.judges` (idempotent on
  repeat), writes an AuditRecord, and does not touch other agents.
- **S-BS-153 (shell, vitest, pure):** `deriveSteps` flips the Judges step done once `eval_profile.judges` is
  non-empty (extend the existing journey test).
- **Guard (unchanged trio):** moat byte-frozen (`compliance_council.py`, `_apply_consensus`, `signals.py`),
  `tools.py` + `_deny_non_lithrim` byte-stable, `judge_metric.py` `LENS_BY_ROLE` untouched.

---

## Guardrails (carry verbatim)

- **MOAT byte-frozen:** `lithrim_bench/runtime/council/compliance_council.py`, `_apply_consensus`,
  `lithrim_bench/runtime/council/signals.py`. Zero diff.
- **A-SAFE byte-stable:** `apps/bff/agent/tools.py` + the `_deny_non_lithrim` deny hook. Zero diff.
- **`judge_metric.py:64` `LENS_BY_ROLE` byte-unchanged** (see W1 guardrail — it is moat-load-bearing via `signals.py`).
- **No prettier** on `apps/shell` JSX — hand-compact; format only touched lines; keep `git diff --stat` small.
- **Commit pathspec-only:** `git commit -m <msg> -- <files>` (the `-m`/`-F` BEFORE the `--`). Never bare-commit
  (concurrent .devloop sessions stage foreign files). Verify scope with `git diff <parent> HEAD --stat`.
- **honest-Δ:** no manufactured win. If the A-LIVE re-drive's "rail ticks" beat does not reproduce, report it
  as an honest loss — the commercial moat is that we never manufacture a pass.
- **Run tests** in pyenv `debuglithrim` (BFF/TestClient uses the `[bff]` extra); shell tests via vitest.

## HARD GATE

Before close, a **fresh-critic** pass (independent context) must confirm: moat + `tools.py` + `_deny_non_lithrim`
+ `judge_metric.LENS_BY_ROLE` byte-untouched; the W1 per-workspace resolution is confined to `app.py` and does
not re-enter the frozen council import; the snapshot defense-in-depth check is retained; W2 roster-add is
idempotent + audited + active-agent-only; tests are non-vacuous (they fail if the fix is reverted); honest-Δ
clean. 0 BLOCKING required to close.

## A-LIVE (monitor)

Re-drive demo-clinical, $0: the shepherd guides authoring a judge → it is admissible in-pack (no 422) → the
rail ticks Judges to done. If it reproduces, capture the deferred A3 demo beat (proof-capsule convention:
PROOF doc + zyng-narrated video, honest-Δ only). If not, honest loss + new seam.
