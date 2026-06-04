# Critique — bench-salvage UAP-2 (judge authoring via ontology-assignment) — HARD GATE

**Verdict: NON-BLOCKING — 0 BLOCKING / 3 NON-BLOCKING / 2 OPEN-QUESTION.**

Fresh adversarial critic, no prior context, re-derived from source. Commits `86fa1d3..3e89ad5` (7) on `bench-salvage/ws6c-dspy`, parent `14d83fb`. The cycle does what it claims: the prompt↔ontology bridge renders a judge's `role_key_questions` from its assignment with the `.txt` safety prose retained verbatim (byte-parity proven against the *live council loader*, not just itself); GET/PUT `/v1/judges` authors a judge as (role + LENS_BY_ROLE-gated assignment + model + execute-only validator refs) with a correct owner↔emit 422 and an immutable `target=judge` audit row sharing a single-transaction helper; the JudgeEditor wires the $0 assignment→prompt link through `bff.js`. The two approved cuts (S-BS-60 question write-back; the monitor-approved `harness/judges.py` + shared `audit.upsert_with_audit`) are recorded. Frozen seam is 0-delta on all four protected paths. The strongest break I attempted — that the council-light extraction or the validator-ref import secretly re-pulls the heavy deps and so falsifies the A8 "$0, any room, zero creds" claim — **held**: the BFF preview path is genuinely importable on the default core (traced statically below).

**ENV CONSTRAINT (load-bearing for honesty):** this critic ran in a read-only sandbox. `python3`, `pytest`, `npm/vitest`, and file writes to `/tmp` were all denied; only `git`/`grep`/`ls`/`echo` (read-only) executed. **I could NOT re-run any suite or execute the import-isolation probe.** Every "CONFIRMED" below is from source-reading + static import-graph tracing + git diff, NOT from a re-run. The suite counts (default 277/12, council 94/3, BFF 30, Vitest 40) are **READ from the session log, not re-executed** — see Q4 RESULT HONESTY. A monitor with exec access should re-run them; nothing I read contradicts them, and the two independently-checkable diagnostics (per-role question counts; frozen-seam deltas) match the log exactly.

---

## Q1 — SPEC ADHERENCE

**Finding Q1.1 (CONFIRMED) — matches the LOCKED spec §3.1/§4/§5 R2 + the driver §2/§5.** The implementation lands R2 as specified: a judge = role + assigned ontology subset + model + validator refs; `GET /v1/judges` / `GET /v1/judges/{role}` / `PUT /v1/judges/{role}` mirror the §4 route table (`apps/bff/app.py:442-535`); `POST .../optimize` is correctly ABSENT (UAP-4). §10 ratified in-cycle (`docs/specs/SPEC_PRODUCT_SHELL.md`, commit `5d1671f`) — the UAP-2 routes line even records the gate authority is `LENS_BY_ROLE`/`_TIER1_OWNERS` "not the ontology's `owner_roles`" and that optimize is OUT. This closes the S-BS-51 pattern as the driver §5 docs item requires.

**Finding Q1.2 (CONFIRMED) — the two flagged deviations are logged, not silently dropped.**
- Question-text write-back cut (S-BS-60, spec §12.2): recorded in the session log `plan_review.deviations[2]` ("APPROVED-AT-PLAN ... Record it as a deferred seam") and `seams_opened` S-BS-60. Independently verified the cut is real: `PUT /v1/judges/{role}` (`app.py:500-535`) calls only `save_judge` — it never writes the ontology working copy. `grep` for any judge-path ontology/questions write in `app.py` returned empty. Questions stay read-derived (`_judge_summary` reads `ontology.questions_for(role)`, `app.py:384-387`). Consistent with §12.2-deferred.
- New `harness/judges.py` + shared audit machinery: session log `plan_review.deviations[1]` ("APPROVED-AT-PLAN ... must be SHARED ... no copy-paste"). Verified shared: both `config.save_agent` (`harness/config.py:152-184`) and `judges.save_judge` (`harness/judges.py:103-115`) delegate to the SAME `audit.upsert_with_audit` (`harness/audit.py:179-216`) — no copy-pasted transaction dance.

**Finding Q1.3 (NON-BLOCKING, informational) — STREAM state not yet updated; this is workflow ordering, not drift.** `.devloop/state/STREAM_bench-salvage.md:143` still reads "the UAP-2 driver is AUTHORED + READY; next = kickoff" and does not record S-BS-59/60/61 or mark UAP-2 closed. This is expected: the executor writes the session-log JSON (which DOES carry S-BS-59/60/61); the STREAM update + seam-table append is the monitor's `/devloop-close-phase` step that runs AFTER this critique. Not an executor defect — flagging so the monitor doesn't forget the STREAM/seam-table write at close.

---

## Q2 — DOES IT DO WHAT IT CLAIMS

### (a) BRIDGE — `render_role_questions` + `build_trio` threading (A2/A4)

**Finding Q2a.1 (CONFIRMED) — no-assignment render is byte-identical to `load_role_prompt(role)`, and to the LIVE council loader.** `render_role_questions(ontology, role, assigned_flags=None)` returns `base = load_role_prompt(role)` unchanged (`judge_assignment.py:71-73`). The A4 test asserts byte-equality for all 3 roles:
```
# lithrim_bench/runtime/council/tests/test_judge_bridge.py:52-56
@pytest.mark.parametrize("role", V2_ROLES)
def test_render_default_is_byte_equal_to_txt(ontology, role):
    assert render_role_questions(ontology, role) == load_role_prompt(role)
```
Stronger still — a SEPARATE pre-existing test pins the seed base to what the *running prompt-council* loads, not just to itself:
```
# test_trio_dspy.py:339-358  test_build_trio_role_prompts_byte_match_the_prompt_council
prompt_council = ComplianceCouncil._load_role_prompts()
trio = build_trio(predictors=...)
... assert by_role[role] == prompt_council[role]   # build_trio == the live loader, byte-for-byte
```
`.strip()` parity (S-BS-44) holds: `load_role_prompt` does `.read_text().strip()` (`judge_assignment.py:39`), and the test also asserts `by_role[role] == by_role[role].strip()`. **The A4 parity is byte-equality, not a weaker check.**

**Finding Q2a.2 (CONFIRMED) — the authored lens reaches the judge the in-process council runs.** With an assignment, the refinement section carries the assigned flags' codes+tier+`when_to_use` lens AND the role's ordinal-ordered `questions_for(role)` (`judge_assignment.py:74-97`). `build_trio(ontology=, assignments=)` threads it: `role_prompt = render_role_questions(ontology, role, assigned_flags=assignments.get(role))` (`judges_dspy.py:329-331`), and that `role_prompt` is what `Judge.forward` feeds the signature: `role_key_questions=self.role_prompt` (`judges_dspy.py:278`). So an authored assignment → the exact text the runtime `JudgeSignature.role_key_questions` receives. The A2 test proves this end-to-end on the object `build_trio` returns:
```
# test_judge_bridge.py:94-109  test_build_trio_assignment_feeds_role_key_questions
... build_trio(..., assignments={"policy_judge": ["FABRICATED_CONSENT"]})
policy = judges["policy_judge"].role_prompt
assert "AUTHORED REFINEMENT (ontology assignment)" in policy
assert "FABRICATED_CONSENT" in policy
assert judges["risk_judge"].role_prompt == load_role_prompt("risk_judge")   # no cross-contamination
```
**This genuinely proves A2** (the structural close; the live re-vote is correctly cost-gated and not exercised). The "would re-vote with the authored lens" claim is exactly as strong as advertised — the prompt-binding link (`role_prompt → role_key_questions`) is the same one the live council uses.

### (b) 422 GATE — gating on LENS_BY_ROLE (v2 authority)

**Finding Q2b.1 (CONFIRMED) — the gate uses `LENS_BY_ROLE`, not the stale ontology `owner_roles`.** `_validate_judge_assignment` (`app.py:400-439`): `lens = LENS_BY_ROLE[role]; off_lens = [c for c in assigned_flags if c not in lens] → 422` (`app.py:418-427`). The ontology `owner_roles` are never consulted in the gate.

**The two adversarial cases the brief asked me to construct — the executor already wrote both, and they assert the right outcomes:**
- `faithfulness_judge ← MISSING_ALLERGY` MUST be ACCEPTED: `MISSING_ALLERGY ∈ FAITHFULNESS_JUDGE_LENS` (`judge_metric.py:93-96`) and `faithfulness_judge ∈ _TIER1_OWNERS["MISSING_ALLERGY"]` (`compliance_council.py:241`). Test asserts 200:
```
# test_ws5_bff.py:570-585  test_gate_authority_is_lens_not_stale_ontology_owner_roles
res = client.put("/v1/judges/faithfulness_judge", json={"assigned_flags":["MISSING_ALLERGY","VALUE_MISMATCH"]})
assert res.status_code == 200
```
  I independently confirmed the stale-owner trap: `clinical_v1.json` `MISSING_ALLERGY.owner_roles = ['behavior_judge','source_message_judge']` (no faithfulness) — gating on it would have wrongly 422'd this correct assignment. The CITATION-DRIFT deviation (session log `deviations[0]`, S-BS-59) is real and correctly handled.
- A genuine non-owner MUST be rejected: `policy_judge ← WRONG_DOSAGE` (`WRONG_DOSAGE ∉ POLICY_JUDGE_LENS`):
```
# test_ws5_bff.py:545-550
res = client.put("/v1/judges/policy_judge", json={"assigned_flags":["WRONG_DOSAGE"]})
assert res.status_code == 422; assert "owner↔emit" in res.json()["detail"]
```

**Finding Q2b.2 (CONFIRMED) — the gate CANNOT false-accept an inert owner (CLAUDE.md invariant #4).** The role enum is `LENS_BY_ROLE` keys = the v2 production trio only (`test_trio_dspy.py:301-302` pins `set(LENS_BY_ROLE) == set(V2_ROLES)`). `if role not in LENS_BY_ROLE: 404` (`app.py:416-417, 483-484`). So the dormant `behavior_judge`/`source_message_judge` (the inert owners in `_TIER1_OWNERS`) cannot be authored AT ALL:
```
# test_ws5_bff.py:564-567
assert client.get("/v1/judges/behavior_judge", ...).status_code == 404
assert client.put("/v1/judges/behavior_judge", json={"assigned_flags":[]}).status_code == 404
```
Further, every assignable code is genuinely owned-AND-emitted by its v2 role: for the non-Tier-1 faithfulness lens codes (`FABRICATED_HISTORY`, `HALLUCINATED_DETAIL`, `UPCODING_RISK`, `WRONG_CODE`) I checked `faithfulness_judge.txt:10` — the "ARTIFACT-SPECIFIC TAXONOMY CODES (use these in your findings[])" block lists them verbatim, so the prompt actually emits them. **No inert/non-emitting assignment is reachable.**

**Finding Q2b.3 (CONFIRMED) — in-snapshot check (invariant #1).** Defense-in-depth snapshot check: `off_snapshot = [c for c in assigned_flags if c not in seed_ontology.load_snapshot_codes()] → 422` (`app.py:428-433`). And structurally, every lens code is in-snapshot: `test_trio_dspy.py:308-313 test_every_lens_code_is_in_the_taxonomy_snapshot` asserts `set(lens) - KNOWN_TAXONOMY_CODES == ∅` for all roles. So a code can only be assigned if it is both lens-resident and snapshot-blessed.

### (c) AUDIT — append-only, 9-field, same transaction, shared machinery

**Finding Q2c.1 (CONFIRMED) — every judge PUT emits a §2B `AuditRecord` (target.type='judge', honest actor) in the SAME transaction as the judge-row write.** `put_judge_endpoint` calls `save_judge(jc, ..., audit_log=AuditLog(db_path), rationale=...)` (`app.py:527-529`). `save_judge` builds the record with `target=Target(type="judge", id=jc.role)` and `actor = make_actor(actor)` (`harness/judges.py:93-101`), then delegates to `upsert_with_audit`, where the upsert + the audit INSERT ride ONE connection and commit together (`harness/audit.py:204-214` — `conn.execute(upsert_sql); audit_log.record(record_factory(before), conn=conn); conn.commit()`). The 9-field shape is the canonical `AuditRecord` (`audit.py:77-89`: ts/actor/action/target/why/before/after/run_id/case_id). Test asserts the full shape + exactly-one-append + honest actor:
```
# test_ws5_bff.py:537-542
recs = client.get("/v1/audit", params={"target_type":"judge"}).json()["records"]
assert len(recs) == 1
assert recs[0]["actor"] == {"type":"user","id":"sme@acme"}
assert recs[0]["target"] == {"type":"judge","id":"risk_judge"}
assert recs[0]["why"]["rationale"] == "assign dosage lens"
```
Append-only is enforced by absence (`AuditLog` has no update/delete; `audit.py:100-106`). **Honest actor:** `X-Actor` header wins, else `{type:system, id:dev-default}` (`app.py:166-175`) — never silently un-attributed.

**Finding Q2c.2 (CONFIRMED) — the audit machinery is SHARED (`audit.upsert_with_audit`), not copy-pasted.** Both stores call it; `config.save_agent` was refactored ONTO it (this is the monitor-approved deviation). Minor depth note (NON-BLOCKING, not a defect): the tests assert the record lands but do not test rollback-on-write-failure atomicity; the code is structurally atomic (single conn, single commit), so this is acceptable test depth for the cycle.

---

## Q3 — SCOPE + FROZEN SEAM (re-verified)

**Finding Q3.1 (CONFIRMED) — frozen seam 0-delta on all four protected paths.** Ran each:
```
$ git diff 14d83fb..HEAD -- lithrim_bench/runtime/council/compliance_council.py | wc -l   → 0
$ git diff 14d83fb..HEAD -- data/ontology/clinical_v1.json                     | wc -l   → 0
$ git diff 14d83fb..HEAD -- data/config/agents                                 | wc -l   → 0
$ git diff 14d83fb..HEAD -- lithrim_bench/runtime/council/council_roles        | wc -l   → 0
```

**Finding Q3.2 (CONFIRMED) — the per-judge seam dict is UNTOUCHED; `judges_dspy.py` edits are additive above it.** The seam dict is intact at `judges_dspy.py:286-292`:
```
return {"model": self.role, "decision": decision, "confidence": confidence,
        "findings": findings, "errors": errors}
```
The full `git diff 14d83fb..HEAD -- ...judges_dspy.py` shows only: (a) import-line edits (extract `load_role_prompt`/`render_role_questions` to `judge_assignment`, add `Sequence`); (b) the additive `build_trio(ontology=, assignments=)` param + the `if ontology is not None` branch (`:326-333`); (c) ruff-format reflows of unrelated lines (`_validate_findings` span comprehension, the `artifact` InputField wrap, the `evaluate_dspy` `.append` wrap). NO `+`/`-` lines touch the seam dict keys. A5 holds.

**Finding Q3.3 (CONFIRMED) — all files in the driver §2 allowed set; no out-of-scope edit; foreign files NOT swept.** `git diff --stat 14d83fb..HEAD` = 16 files: `apps/bff/app.py`, `apps/shell/src/{bff.js, genui/JudgeEditor.jsx, genui/JudgeEditor.test.jsx, genui/index.js, genui/registry.js, genui/registry.test.jsx}`, `docs/specs/SPEC_PRODUCT_SHELL.md`, `lithrim_bench/harness/{audit.py, config.py, judges.py}`, `lithrim_bench/runtime/council/{judge_assignment.py, judges_dspy.py, tests/test_judge_bridge.py}`, `tests/test_ws5_bff.py`, and the session-log JSON. No backend (`../lithrim-backend`), no committed-seed edit, no `.txt` edit, no journey edit. `config.py`/`audit.py` are the monitor-approved shared-audit refactor (deviation 1). The 3 pre-existing foreign untracked files (`.claude/`, `KICKOFF_CRITIC_*`, `docs/research/REPORT_fhir_agentbench*`) still show as `??` in `git status --porcelain` AND are absent from the 16-file cumulative diff — i.e. never committed. **Not swept. CONFIRMED.** (Note: `git ls-files`/piped greps were sandbox-denied; the `??`-status + absence-from-diff is sufficient proof.)

**Finding Q3.4 (OPEN-QUESTION for the monitor, NOT this cycle's scope) — an uncommitted working-tree edit to a LOCKED spec.** `git status` shows `M docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md`. `git diff 14d83fb..HEAD -- <it>` is EMPTY (not in any UAP-2 commit), but `git diff HEAD` shows an uncommitted addition of a §13/R10/R11 "conversational surface" (UAP-5a/5b) to the LOCKED spec. This is foreign to UAP-2 and is NOT swept into a commit, so it is not a UAP-2 scope violation. But it IS dirty working-tree state on a LOCKED doc, almost certainly from a concurrent planning session (the STREAM banner references "UAP-5a/5b INCORPORATED 2026-06-04"). **Monitor: confirm this working-tree edit is intended/owned elsewhere before the close commit, so the UAP-2 close doesn't accidentally carry it.**

---

## Q4 — SAFETY-CRITICAL + LOAD-BEARING RISKS

**Finding Q4.1 (CONFIRMED) — S-BS-11: the layered design preserves the FULL safety prose for all three roles; faithfulness_judge does NOT get a degraded prompt.** The render is `base + "\n" + refinement` (`judge_assignment.py:97`) with `base = load_role_prompt(role)` (the full `.txt`); the A2 test asserts `out.startswith(load_role_prompt(role))`. I confirmed the prose is substantial and intact in the seeds: `risk_judge.txt` (HL7-NKA exception at line 1 AND the AL1/NKDA EXCEPTION at line 38; 15 safety markers), `policy_judge.txt` (9 markers — consent/PHI/MAY-RAISE), `faithfulness_judge.txt` (164 lines; HL7-NKA at line 1; the ARTIFACT-SPECIFIC TAXONOMY CODES block; FABRICATED_HISTORY scope rules). Because A4 proves byte-equality for all 3 roles (diagnostic `default_render_diff_vs_txt=0`), the CODES-YOU-MAY/MAY-NOT-RAISE, HL7-NKA exception, Tier-1 allergy-fabrication framing, EVIDENCE REQUIREMENTS, and SAFE PATTERNS are carried verbatim. **faithfulness_judge has ZERO ontology questions** (I independently grep'd `clinical_v1.json`: `faithfulness_judge` appears 0 times; the question rows are keyed to v1 roles — `risk_judge`×6, `policy_judge`×5, the dormant `source_message_judge`×5), so its refinement is lens-only and the questions block is omitted, NOT faked — proven by `test_render_lens_only_when_role_has_no_ontology_questions` (`test_judge_bridge.py:112-117`). The full 164-line base is still its prompt. This is precisely WHY the bridge had to be layered (pure-ontology would have degraded faithfulness); the executor's design rationale is verified, not just asserted.

**Finding Q4.2 (CONFIRMED) — the gate-authority drift guard is real and effective.** `test_every_tier1_lens_code_is_owner_resident` (`test_trio_dspy.py:316-326`) iterates every lens code; for any code in `TIER_1_NEVER_EVENTS`, asserts `role in _TIER1_OWNERS[code]`. Since the 422 gate keys off `LENS_BY_ROLE`, this test prevents the gate from silently drifting to claim a Tier-1 code the role doesn't own. Paired with `test_every_lens_code_is_in_the_taxonomy_snapshot` (snapshot residency) and `test_faithfulness_lens_excludes_the_unowned_tier1_codes` (`:329-333`), the lens↔owner↔snapshot triangle is pinned. **The gate cannot drift from the owner table for one-strike codes without a red test.**

**Finding Q4.3 (CONFIRMED) — the mid-cycle refactor (74920df) is behavior-preserving, council-light, and the BFF preview works on default deps.**
- (i) Behavior-preserving move, not a logic change: the `judges_dspy.py` diff shows `load_role_prompt` deleted from `judges_dspy` and re-imported from `judge_assignment` (`judges_dspy.py:59`); the body is identical (same `.read_text().strip()`, same FileNotFoundError). `build_trio` keeps one import surface. A4 byte-parity + A5 seam-0-delta both still hold post-extract (§Q2a, §Q3.2), and the session log records "Render output byte-identical; default suite 277 passed" after the move.
- (ii) `judge_assignment.py` is genuinely council-light. Static import trace: its ONLY imports are `from __future__`, `collections.abc.Sequence`, `pathlib.Path`, `typing.Any` (`judge_assignment.py:16-20`) — stdlib only, and crucially NO `from . import compliance_council`/`judges_dspy`, so it cannot transitively pull `openai`/`dspy`/`tenacity`. (I could not run the `sys.modules`-after-import probe — python exec was sandbox-denied — but the static graph is dispositive: a module that imports only stdlib cannot leak heavy deps.)
- (iii) The BFF prompt-preview path works on the default core. `GET /v1/judges/{role}` calls `render_role_questions` (`app.py:495-496`), imported `from ...judge_assignment` (`app.py:97`, council-light per above) + `LENS_BY_ROLE` from `judge_metric` (`app.py:100`). I traced `judge_metric.py` imports: `collections.abc`, `typing` ONLY (`judge_metric.py:44-47`) — pure, no openai leak (corroborates the honestly-recorded S-BS-61: the gate-authority import is clean). The council package `__init__.py` has NO top-level imports (docstring-only), so importing the council namespace is itself light. The BFF's other top-level imports (`run_eval`, `harness.*`, `seed_ontology`) carry no eager `dspy`/`openai` (grep'd `run_eval.py`, `grade.py`, `ontology.py` — none); the in-process council + `KbRagTool` are lazily imported inside their handlers (`KbRagTool` at `app.py:712`, inside `kb_search_endpoint`). **The A8 "$0 assignment→prompt, any room, zero creds" claim is structurally true.**

**Finding Q4.4 (CONFIRMED) — validator-ref import isolation (driver decision #4) holds.** The BFF imports the `TOOL_*` names `from lithrim_bench.verification.spec` (`app.py:101-108`) — the `.spec` SUBMODULE directly, NOT the `lithrim_bench.verification` package. I traced `verification/spec.py`: imports `dataclasses` + `typing` ONLY (`spec.py:17-20`). Critically, the package `__init__.py` IS heavy (eagerly imports `jute_dspy`, `jute_gen`, `tools.KbRagTool` — `verification/__init__.py:11-54`, which pull dspy/httpx/onnx); by importing from `.spec` directly the BFF bypasses that heavy `__init__`. So importing the validator-ref names does NOT pull `[verification]` heavy deps. (Again, static trace, not a runtime probe — but importing a stdlib-only submodule cannot trigger sibling-module side effects in CPython.)

**Finding Q4.5 (CONFIRMED HONEST) — A8 is marked SKIP/OWED, not PASS.** Session log `acceptance[A8].verdict = "SKIP"`, evidence "OWED — user-run, no-autostart ... Batch with the still-owed UAP-1 A8 :5180 smoke at close." The overall `verdict = "PROCEED-WITH-CAVEATS"`. This is honest — the $0 half is wired+tested (BFF + Vitest), the paid verdict-change finale is correctly deferred. Consistent with the driver's "A8 user-attested" and the WS-5c posture.

**Finding Q4.6 (OPEN-QUESTION) — RESULT HONESTY: suite counts READ, not re-run.** I could NOT re-execute any suite (python/pytest/vitest all sandbox-denied), so I cannot independently confirm default 277/12, council 94/3, BFF 30, Vitest 40. What I CAN corroborate from source matches the log exactly: (a) the two independently-checkable diagnostics — per-role derived-question counts (risk 6 / policy 5 / faithfulness 0) verified against `clinical_v1.json`, and frozen-seam 0-deltas verified via git; (b) the test FILES and test NAMES the log cites all exist and assert what the log claims (I read every one); (c) `+8 BFF / +7 council / +1 Vitest file` matches my count (8 `test_judge*` fns in `test_ws5_bff.py`; 7 fns in `test_judge_bridge.py`; `JudgeEditor.test.jsx` new). **Monitor with exec access: re-run the four suites to close this OQ.** Nothing I read suggests they would fail.

---

## What I tried hardest to break (and why it held)

1. **"The council-light extraction or the validator-ref import secretly re-pulls dspy/openai, so A8's '$0, zero creds' is false."** — Traced all four import heads (`judge_assignment`, `judge_metric`, `verification.spec`, the council `__init__`) to stdlib-only or docstring-only; confirmed the BFF imports `.spec` (light submodule) not the heavy `verification` package, and defers `KbRagTool` into its handler. Held.
2. **"The 422 gate false-accepts an inert owner, violating invariant #4."** — The role enum is the v2 trio only; `behavior_judge`/`source_message_judge` 404 on PUT; every assignable code is owned-AND-emitted (checked faithfulness's non-Tier-1 codes against its `.txt` emit block). Held.
3. **"The layered bridge drops safety prose, or faithfulness (0 questions) gets an empty prompt."** — A4 proves byte-equality for all 3 roles against the live council loader; faithfulness keeps its full 164-line base, questions block omitted-not-faked. Held.
4. **"`config.py`/`judges.py` refactor changed behavior (the dropped `mkdir`, a circular import)."** — `mkdir` moved into `upsert_with_audit:203`; import graph `audit → (nothing local)`, `config → audit`, `judges → config+audit` has no cycle. Held.

## OPEN-QUESTIONs for the monitor
- **OQ-1 (Q3.4):** the uncommitted working-tree edit to the LOCKED `SPEC_UNIFIED_AUTHORING_PRODUCT.md` (§13/R10/R11). Confirm it's owned by a concurrent session and won't be swept into the UAP-2 close.
- **OQ-2 (Q4.6):** re-run the four suites with exec access (this critic was sandbox-blocked from running them). Counts claimed: default 277/12, council 94/3, BFF 30, Vitest 40.
- (Reminder, not blocking) per the workflow, the monitor still owes the STREAM-state update + seam-table append for S-BS-59/60/61 (Q1.3), and the batched UAP-1+UAP-2 A8 `:5180` smoke (Q4.5).
