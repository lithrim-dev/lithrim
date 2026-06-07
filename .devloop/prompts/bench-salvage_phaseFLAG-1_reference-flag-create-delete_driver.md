# Driver — `bench-salvage` phase `FLAG-1`: reference-flag create + delete (local, honest), gradeable gated cross-repo

> **Bundle ID:** `bench-salvage-phaseFLAG-1-reference-flag-create-delete-driver`
> **Stream:** `bench-salvage` · **Target repo:** `lithrim-bench` · **Branch:** `bench-salvage/ws6c-dspy` (dirty shared — pathspec-only; concurrent `root.jsx` uncommitted, leave it).
> **Hardness:** **HARD-GATE** — touches the ontology + the **core invariant** (*labels are true by construction* + the taxonomy-snapshot contract). Fresh-critic at close.
> **Objective served:** user objective #2 (flags half). **User scope decision (2026-06-07): "Reference local; gradeable cross-repo."** Runs AFTER CRUD-1 (reuses its audited-delete pattern). Sequenced second.

---

## KICKOFF (paste into a fresh executor session)

```
You are the executor for bench-salvage phase FLAG-1 (reference-flag create + delete, local + honest).
Read EXECUTOR.md first, then this driver in full:
  .devloop/prompts/bench-salvage_phaseFLAG-1_reference-flag-create-delete_driver.md
Also read the invariant (NON-NEGOTIABLE): CLAUDE.md "Core invariant: labels are true by construction" +
"Taxonomy snapshot is the contract."

HARD-GATE (touches the ontology + the core invariant). Fresh-critic at close. Services up; no autostart.
Canonical tests = `pytest -q` (debuglithrim + default); 2 observation-isolation failures are pre-existing (S-BS-96).

THE ONE LAW OF THIS CYCLE: you may create/delete REFERENCE (gradeable=false) flags locally. You may NEVER
create a gradeable (scoreable) flag from clean — the taxonomy snapshot's codes come ONLY from lithrim-backend
(scripts/snapshot_taxonomy.py --backend-path). A locally-invented gradeable flag = manufacturing a label the
contract-of-record hasn't blessed = the exact thing this repo prevents. The create path HARDCODES gradeable=false;
the gradeable path is an explicit, refused-with-a-clear-message precondition (cross-repo).

What you're building:
  D1  reference-flag CREATE (gradeable=false, tier=null, owner_roles=[]) via the audited PUT /v1/ontology path,
      with the definitional fields (category/definition/when_to_use/when_NOT_to_use) author_flag omits.
  D2  a create_flag surface (conv tool + the existing flag-editor card) that CANNOT set gradeable=true.
  D3  flag DELETE (reference flags only) with orphan guards: refuse in-snapshot/gradeable flags, refuse a flag a
      judge is assigned or a case emits; audited (reuse CRUD-1's delete pattern).
  D4  the honest gradeable-create PRECONDITION gate: a clear refusal ("needs a backend re-snapshot") — never faked.
  D5  tests: reference-create round-trips + scores as a reference (skip-logged, never graded); gradeable-from-clean
      is REFUSED (non-vacuous); delete guards; audit on create+delete; the A-SAFE no-gradeable bound.

Post a plan-review resolving D-A..D-E BEFORE any code. Do not code until I say "go". Pathspec-only.
```

---

## 0. Why
`author_flag` is EDIT-ONLY by construction ([tools.py:189](apps/bff/agent/tools.py:189) — 404 on unknown flag; "never creates a flag or invents owners"). The deep-trace (the FLAG-1 scan, agent `ae6ab7f44357c1113`) confirmed **why**: a *gradeable* flag cannot exist without a `taxonomy_snapshot.json` tier entry, and those come **only** from lithrim-backend (`snapshot_taxonomy.py --backend-path`; CLAUDE.md "never hand-edit"). So "create a scoreable flag from clean" is **architecturally cross-repo** (backend `compliance_council.py` edit → re-snapshot → `LENS_BY_ROLE`/council-prompt → re-seed) — not a gap to paper over; the by-construction guarantee.

**What IS locally honest:** a **reference (non-gradeable) flag**. `PUT /v1/ontology` already accepts a new `gradeable=false` flag (it round-trips `from_dict` and passes the snapshot lint, which only fires on *gradeable*-outside-snapshot — [_validate_ontology app.py:709-729](apps/bff/app.py:709)). Reference flags are known-but-out-of-snapshot, grounding-skip-logged, never scored ([ontology.py:116-123](lithrim_bench/harness/ontology.py:116)). They just lack an authoring surface. FLAG-1 builds that surface — and makes the gradeable refusal explicit + honest.

## 1. Pre-flight (citations re-grepped 2026-06-07 — re-grep before commits)
- **The Flag model:** `FlagDefinition` ([ontology.py:41-51](lithrim_bench/harness/ontology.py:41)) — fields `flag, category, definition, when_to_use, when_NOT_to_use, owner_roles, tier, gradeable=False, reliability_pillar`. `is_reference` ([:116](lithrim_bench/harness/ontology.py:116)), `is_gradeable` ([:111](lithrim_bench/harness/ontology.py:111)), `gradeable_flags` ([:107](lithrim_bench/harness/ontology.py:107)), `from_dict` ([:136](lithrim_bench/harness/ontology.py:136), `gradeable` defaults False / `tier` None / `owner_roles` ()), `load_ontology` (mtime-cached, [:182](lithrim_bench/harness/ontology.py:182)).
- **The PUT gate (the admissibility law):** `_validate_ontology` ([app.py:709-729](apps/bff/app.py:709)) = (1) `from_dict` round-trip → 422 malformed; (2) `gradeable_flags_outside_snapshot` → **422 "gradeable flags outside taxonomy snapshot (re-snapshot, do not hand-edit)"**. `put_ontology_endpoint` ([:732](apps/bff/app.py:732)) writes the non-committed working copy + an immutable `AuditRecord` (before/after, why=rationale). `seed_ontology.gradeable_flags_outside_snapshot` ([:~152](scripts/seed_ontology.py)) + `load_snapshot_codes` ([:~139](scripts/seed_ontology.py)).
- **Edit-only enforcement to extend:** the bound `_author_flag` ([app.py:989](apps/bff/app.py:989) — 404 on unknown; never fabricates owners) + `AUTHOR_FLAG_SCHEMA` ([tools.py:47](apps/bff/agent/tools.py:47), fields `flag_code/tier/gradeable/rationale` — **omits** category/definition/when_*). `author_flag_handler` ([:189](apps/bff/agent/tools.py:189)). `PAID_KEYS` ([:69](apps/bff/agent/tools.py:69)). The ASAFE-1 deny-hook ([loop.py:55](apps/bff/agent/loop.py:55)).
- **The by-construction lints (delete must not break them):** `lint_golden_against_taxonomy.py` D1 (every `expected_safety_flags` code ∈ known ∪ structural, [:59](scripts/lint_golden_against_taxonomy.py:59)); `packager.py` `package_case` D1 ([:144](lithrim_bench/packager.py:144)) + D3-owner ([:150](lithrim_bench/packager.py:150), `production_owners_of` non-empty). `taxonomy.known_codes` ([taxonomy.py:27](lithrim_bench/taxonomy.py:27)), `production_owners_of` ([:50](lithrim_bench/taxonomy.py:50)).
- **Owner-residence / lens (why gradeable is cross-repo):** `LENS_BY_ROLE` ([judge_metric.py:110](lithrim_bench/runtime/council/judge_metric.py:110)); `_validate_judge_assignment` owner↔emit ([app.py:508-547](apps/bff/app.py:508)); `tier1_owners` + `production_judges` + `declared_but_not_running` in `taxonomy/taxonomy_snapshot.json`.
- **CRUD-1 delete pattern** (reuse): `delete_with_audit` / the `action="delete"` AuditRecord primitive CRUD-1 lands. **FLAG-1 is sequenced after CRUD-1** so this exists.

## 2. Deliverables (file-by-file)

### D1 — reference-flag CREATE (audited, gradeable=false by construction)
- **`apps/bff/app.py`** — a bound `_create_flag(flag_code, category, definition, when_to_use, when_NOT_to_use, rationale)` inside `_build_tool_context`: ADD a new flag object to the ontology working copy with **`gradeable=False, tier=None, owner_roles=[]`** (HARDCODED — never from args), 409 if the code already exists (create ≠ edit; edit stays `author_flag`), then PUT through the frozen audited `put_ontology_endpoint` (so `_validate_ontology` + the audit fire). The create can NEVER produce a gradeable flag.

### D2 — the create surface (conv tool + card)
- **`apps/bff/agent/tools.py`** — `CREATE_FLAG_SCHEMA` (the definitional fields — `flag_code/category/definition/when_to_use/when_NOT_to_use/rationale`; **no `gradeable` field at all**) + `create_flag_handler` → `_TOOL_SPECS` (now 9 or 10 with CRUD-1's tool). Renders the EXISTING flag-editor card. No paid knob.
- The human UI path is `PUT /v1/ontology` directly (already works); the conv tool is the demonstrable surface.

### D3 — flag DELETE (reference-only, guarded, audited)
- **`apps/bff/app.py`** — `DELETE /v1/ontology/flags/{flag_code}` (or a bound `_delete_flag`): remove the flag from the working copy + audited (`action="delete"`, reuse CRUD-1). **Guards (422):** refuse if the flag `is_gradeable` or in the snapshot (deleting a contract code desyncs the contract — out of scope; that's a re-snapshot); refuse if any persisted judge has it in `assigned_flags` (orphan — scan `list_judges`); refuse if any `examples/*.jsonl` case lists it in `expected_safety_flags` (corpus orphan — breaks the golden lint). So delete is allowed only for an **unused reference flag**.

### D4 — the honest gradeable-create precondition gate
- Make the refusal explicit + legible: attempting (via the create tool, or a `PUT`/`author_flag` flip) to make a flag `gradeable=true` whose code isn't in the snapshot → the existing `_validate_ontology` 422, with the message sharpened to name the path: *"a gradeable flag requires a lithrim-backend re-snapshot (`scripts/snapshot_taxonomy.py --backend-path …`); it cannot be created from clean locally — labels are true by construction."* Document the cross-repo procedure in `docs/` (the backend `compliance_council.py` edit → re-snapshot → `LENS_BY_ROLE` → re-seed chain). **Never auto-edit the snapshot.**

### D5 — tests (`tests/test_flag_crud.py`)
- Reference-create round-trips: a new `gradeable=false` flag persists via the audited PUT; `is_reference(code)` true; it is **skip-logged, never scored** (grounding/grade treats it as reference).
- **Gradeable-from-clean is REFUSED (load-bearing, non-vacuous):** creating/flipping a flag to `gradeable=true` with an out-of-snapshot code → 422 with the re-snapshot message; prove non-vacuous (a snapshot code stays acceptable).
- Delete guards: refuse gradeable/in-snapshot, refuse judge-assigned, refuse case-emitted; allow an unused reference flag; audited (`action="delete"`).
- A-SAFE: `CREATE_FLAG_SCHEMA` has no `gradeable` field; the bound `_create_flag` hardcodes False (a reverted-scratch removing the hardcode FAILS the test); no-paid-knob across the full tool set.

## 3. Plan-review decisions
- **D-A.** Create surface: a conversational `create_flag` tool (recommended, demonstrable) vs human-UI-only (`PUT /v1/ontology`). If agent-exposed: the new A-SAFE attestation (no `gradeable` field; gradeable=false hardcoded).
- **D-B.** Delete route shape: `DELETE /v1/ontology/flags/{code}` vs an ontology-PUT-with-removal; the guard set (gradeable/in-snapshot + judge-assigned + case-emitted) — confirm all three.
- **D-C.** The gradeable-refusal message + where the cross-repo procedure doc lives.
- **D-D.** owner_roles on a created reference flag: `[]` (recommended — reference flags aren't owned/scored) vs author-supplied (forbidden — can't invent owners).
- **D-E.** Whether `author_flag` (edit) should also be allowed to create-if-missing (NO — keep create/edit split: `create_flag` adds, `author_flag` edits; preserves the 404 edit-only guarantee).

## 4. Scope guardrails — NOT in scope
- **Gradeable/scoreable flag creation** — architecturally cross-repo; this cycle REFUSES it honestly, does not build it. No snapshot edit, no `compliance_council.py`, no `LENS_BY_ROLE` edit, no re-seed.
- **`taxonomy/taxonomy_snapshot.json`** — never hand-edited or written by this code.
- Judges/agents CRUD (CRUD-1); run-delete (immutable); the journey + `root.jsx`.
- `_apply_consensus` + the per-judge seam + seeds (0-delta).

## 5. Acceptance
- **A1 — reference-create from clean (LIVE).** A brand-new `gradeable=false` flag is created via the audited path on `:8787`; appears in the ontology working copy; `GET /v1/audit` shows the create (who/when/what/why); it is `is_reference` + never scored.
- **A2 — gradeable-from-clean REFUSED (LIVE, the invariant).** Creating/flipping a flag to `gradeable=true` (out-of-snapshot) → 422 with the re-snapshot message. Non-vacuous (an in-snapshot code is accepted). **This is the load-bearing honest gate.**
- **A3 — delete guards (LIVE).** Delete refuses a gradeable/in-snapshot flag, a judge-assigned flag, a case-emitted flag; allows an unused reference flag; audited.
- **A-SAFE.** `create_flag` has no `gradeable` field + hardcodes False (non-vacuous); no-paid-knob across the full tool set; the ASAFE-1 deny-hook covers the new tool.
- **A4 — invariant intact.** The golden lint + `package_case` still pass; no snapshot/seed/`_apply_consensus` drift; `git diff` shows no taxonomy-snapshot change.
- **A5 — green bar.** Canonical `pytest -q` — no new failures (S-BS-96 baseline); Vitest; ruff.
- **A6 — `:5180` smoke** — create a reference flag conversationally; try to make it gradeable → see the honest refusal; delete the unused reference flag. Screenshot.

## 6. Commit structure (atomic, pathspec-only)
1. `feat(bff): reference-flag create — _create_flag (gradeable=false by construction, audited PUT)`
2. `feat(bff): create_flag conversational tool (definitional fields; no gradeable knob; A-SAFE)`
3. `feat(bff): flag delete — reference-only, guarded (in-snapshot/judge/corpus orphan), audited`
4. `docs+fix(flag): honest gradeable precondition gate + the cross-repo re-snapshot procedure`
5. `test(flag-1): reference-create + gradeable-refused (non-vacuous) + delete guards + A-SAFE` (+ session log)

## 7. Verification checklist
- [ ] D-A..D-E resolved; "go". · A1-A6 met (A2 the load-bearing honest gate; screenshot). · canonical `pytest -q` + Vitest + ruff. · **taxonomy snapshot byte-untouched**; seam 0-delta; golden lint + package_case green. · pathspec-only; `root.jsx`/journey/foreign untouched. · session log + `next_session_hint`.

## 8. First move
1. Read `EXECUTOR.md` + CLAUDE.md (the invariant) + this driver. 2. `curl :8787/health`/`:5180`. 3. Skim `_validate_ontology` + `_author_flag` (the edit-only enforcement to extend) + `is_reference`/`gradeable_flags`. 4. Resolve D-A; post the plan-review.

## 9. References
- The FLAG-1 invariant deep-trace (this driver §0/§1; agent `ae6ab7f44357c1113`).
- CLAUDE.md "Core invariant" + "Taxonomy snapshot is the contract". Memories: `semantic-eval-equivalence-is-a-contract`, `unified-authoring-product-frozen-journey`, `three-objectives-ux-crud-byoc-2026-06`.
- Predecessor: **CRUD-1** (the audited-delete pattern this reuses).
