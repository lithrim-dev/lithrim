# Spec-Adherence Critique — `bench-salvage` phase `WS-2`

> Fresh-critic mode (HARD GATE). Cold read of the spec + diff with no prior
> implementation context; executor's session log read only after forming the
> independent read.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-2` (generalize `:8002` config injection — domain-agnostic)
- **Driver bundle:** `bench-salvage-phaseWS-2-generalize-backend-config-injection-driver`
- **Commits audited:** `3e7f7f7..5ba1bec` (bench-side only; the 7 commits
  `8b396d3 e6c7032 2fbbbb8 01e2adc 289ed15 d434eef 5ba1bec`. Backend half
  D1/D2/D4 NOT started — confirmed: no `../lithrim-backend/` file in range.)
- **Spec(s) read against:**
  - `.devloop/tasks/TASK_PACK_bench-salvage.json` → task `WS-2`
    (deliverables / acceptance / guardrails)
  - `.devloop/prompts/bench-salvage_phaseWS-2_generalize_backend_config_injection_driver.md`
    §2 (D0–D4), §5 (A1–A5), §4 (guardrails)
  - `.devloop/state/STREAM_bench-salvage.md` seams S-BS-10 (DECIDED, Option A) + S-BS-11 (locked D2 scope)
  - `CLAUDE.md` §"Taxonomy snapshot is the contract" + §"Core invariant: labels are true by construction"
- **Critique mode:** `fresh-critic` (separate session)
- **Date:** `2026-05-31`
- **Reviewer:** `critic session-2026-05-31-critic`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The bench-side WS-2 scope (D0/S-BS-10 + D3 + D4) is implemented faithfully and
stays strictly additive; the snapshot lint gate is enforced (proven on a
fixture), the gradeable/reference partition is correct (19/4), reference
findings are skip-logged-not-scored, the `None`/absent path is byte-identical to
the WS-0/WS-1 body, and the deferred D2 prose rewrite (S-BS-11) was **not**
pre-empted (no `build_prompt`/backend file is touched). Findings are two
spec-vs-impl judgment calls (the `gradeable` membership *source* and the
reference-finding active-set treatment) plus one surface note — all
NON-BLOCKING / OPEN-QUESTION. **Backend acceptance A2/A3 are correctly SKIP'd
(HARD-GATE-paused), not failed.** Cycle MAY close on the bench-side scope.

---

## 1. Surface fidelity

> Public symbols the spec (driver §2 D0/D3/D4) defines or implies.

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| D0.0 — `FlagDefinition` gains `gradeable: bool`, default such that out-of-snapshot flags are `gradeable=false` | `ontology.py:50` `gradeable: bool = False`; `from_dict` `ontology.py:147` `bool(f.get("gradeable", False))` | exact (safe default = `False`) | — |
| D0.0 — "Query helpers (`flag`/`owners_of`/`contract_for`) … should be able to filter to gradeable-only" | `ontology.py:107` `gradeable_flags()`, `:111` `is_gradeable()`, `:116` `is_reference()` — **new predicates added; `flag`/`owners_of`/`contract_for` unchanged (still all-flags)** | intent met via new symbols, not by extending the named helpers | NON-BLOCKING |
| D0.1 — `load_snapshot_codes()` + pure lint over the 19-code tier union | `seed_ontology.py:139` `load_snapshot_codes` (reads `data["tiers"].values()` → 19), `:160` `gradeable_flags_outside_snapshot` (pure) | exact | — |
| D0.3 — `GroundedResult` carries the skip-logged reference bucket | `grounding.py:71` `skipped_non_gradeable: list = field(default_factory=list)`; `report.py:56` `skipped_non_gradeable_count` | exact (additive field, defaulted) | — |
| D3 — `grade_live` carries the Agent's stored `council_config`/`ontology` | `grade.py:115-118` two `Optional[...]=None` kwargs; `grade.py:50` new `build_request_body(...)` factored out for offline inspection | exact (extracting `build_request_body` is the natural way to satisfy D4 "mock/inspect the request") | — |

**Findings:**

- `[NON-BLOCKING]` D0.0 (driver §2 D0.0, `…driver.md:175-179`) says the existing
  query helpers "`flag`/`owners_of`/`contract_for` … should be able to filter to
  gradeable-only." The impl instead adds three **new** predicates
  (`ontology.py:107/111/116`) and leaves `owners_of`/`contract_for`/`flag`
  operating over all flags. The intent (obtain the gradeable-only set / classify
  a code) is fully met, and grounding correctly routes through `is_reference`
  (`grounding.py:204`). No caller is left able to silently score a reference
  flag. Noted only because the surface differs from the literal wording.

- No blocking surface drift. The 5 new/extended public symbols
  (`gradeable`, `gradeable_flags`, `is_gradeable`, `is_reference`,
  `skipped_non_gradeable`, `load_snapshot_codes`, `gradeable_flags_outside_snapshot`,
  `build_request_body`) are all additive and defaulted; no existing signature
  changed shape, no rename, no error-taxonomy change.

---

## 2. Behavioral fidelity

### Behavior 1: the seed lint FAILS on a gradeable flag outside the snapshot

- **Spec assertion:** A1 (`…driver.md:299-304`) — "`seed_ontology.py`
  cross-checks against `taxonomy_snapshot.json` and the lint **FAILS** if a
  gradeable flag is outside the snapshot (prove with a fixture)." Also
  CLAUDE.md §"Taxonomy snapshot is the contract" (the fix is to re-snapshot,
  never hand-edit).
- **Test:** `tests/test_ws2.py:96` `test_lint_fails_on_gradeable_outside_snapshot`
  asserts `gradeable_flags_outside_snapshot([... "INVENTED_OFFENDER" gradeable
  ...], {"WRONG_DOSAGE","MISSING_ALLERGY"}) == ["INVENTED_OFFENDER"]`; and
  `:86` `test_seed_gradeable_set_matches_snapshot` asserts the committed seed
  yields `== []`.
- **Implementation:** `scripts/seed_ontology.py:160` (pure lint) + `:301`
  (`main()` `raise SystemExit("S-BS-10 LINT FAIL: …")` before serialize, so the
  gate fires on every build **and** `--check`). Verified live: `python
  scripts/seed_ontology.py --check` → `OK … (23 flags)`, exit 0.
- **Chain closes?** YES.
- **Note:** the gate is *one-directional* — see Behavior 2 / Ambiguity 1.

### Behavior 2: reference (out-of-snapshot) findings are skip-logged, never scored

- **Spec assertion:** D0.3 (`…driver.md:189-192`) — "grounding / re-score operate
  on **gradeable-only** findings (out-of-snapshot codes are skip-logged like the
  S-BS-8 null-code path, never silently scored)." A1 — "reference flags
  skip-logged, never scored."
- **Test:** `tests/test_ws2.py:118`
  `test_reference_finding_is_skip_logged_never_scored` — a lone
  `WRONG_PATIENT_INFO` HIGH finding lands in `skipped_non_gradeable`,
  `active == []`, and `verdict == "PASS"` (it would have BLOCK'd if scored);
  `:131` `test_gradeable_finding_still_scores` confirms a gradeable
  `FABRICATED_HISTORY` HIGH still BLOCKs (skip is targeted, not blanket).
- **Implementation:** `grounding.py:204-207` — `if ontology.is_reference(code):
  skipped_non_gradeable.append(finding); continue` (removed from `active` before
  `severity_map.rescore(active)` at `:229`).
- **Chain closes?** YES.
- **Note:** the impl removes reference findings from `active`, whereas the
  S-BS-8 null-code path (`grounding.py:202-204`) keeps null-code findings *in*
  `active`. The spec's "like the S-BS-8 null-code path" reads ambiguously, but
  *removal* is the only treatment that satisfies "never scored" (rescore reads
  `active`). The divergence is correct and the executor surfaced it in the
  commit body. See Ambiguity 2.

### Behavior 3: absent config ⇒ byte-identical to the WS-0/WS-1 request body

- **Spec assertion:** A4 (`…driver.md:312-315`) — "`grade_live` sends the
  Agent's stored `council_config` + `ontology` … **when present**"; A2 framing
  (`:305-307`) — default/absent = current behavior. Driver §2 D1 — "Default
  `None` = exactly current behavior."
- **Test:** `tests/test_ws2.py:140`
  `test_build_request_body_omits_config_when_absent` (`"council_config" not in
  body`, `"ontology" not in body`); `:149`
  `test_build_request_body_injects_config_when_present`; `:160`
  `test_run_eval_passes_agent_config_to_live_grade` (monkeypatched `grade_live`,
  captured `council_config == {"disposition": "compose-over-live-v2"}`,
  `ontology["domain"]=="clinical"`, `len(ontology["flags"])==23` — no paid call).
- **Implementation:** `grade.py:79-82` (`if council_config: … if ontology: …` —
  truthy-gated); `grade.py:127` `grade_live` delegates to `build_request_body`;
  `scripts/run_eval.py:98-101` threads `agent.eval_profile.council_config or
  None` + the ontology JSON dict on the `--live` path only. The body
  construction is an exact extract of the prior inline block (`_build_context`
  call preserved), so the replay path is unchanged.
- **Chain closes?** YES. (Verified `tests/test_ws2.py` 8/8 green.)

**Findings:**

- No behavioral drift on the bench-side scope. All three spec→test→impl chains
  close. **A2/A3 (backend backward-compat + injected-ontology drives live
  tier/owner lookup) are not demonstrated here — correctly, because the backend
  half is HARD-GATE-paused and marked SKIP, not PASS, in the session log.** A
  monitor closing the *full* WS-2 must not treat A2/A3 as met.

---

## 3. Out-of-scope intrusion

Driver's bench-side deliverables (driver §2):

1. D0.0 — `ontology.FlagDefinition.gradeable` + query helpers
2. D0.1 — `seed_ontology.py` snapshot cross-check + lint gate
3. D0.2 — re-seed `data/ontology/clinical_v1.json` (byte-deterministic)
4. D0.3 — `grounding.py` `ground()` operates gradeable-only
5. D3 — `grade.py` `grade_live` + `scripts/run_eval.py` inject stored config
6. D4 — `tests/test_ws2.py`

`git diff --stat 8b396d3^..5ba1bec` files changed:

```
.devloop/.../session-bench-salvage-phaseWS-2-2026-05-31.json | 144 +++  (session log; chores d434eef/5ba1bec)
data/ontology/clinical_v1.json                               |  26 ++-  (D0.2)
lithrim_bench/harness/grade.py                               |  68 +++-  (D3)
lithrim_bench/harness/grounding.py                           |  28 +++  (D0.3)
lithrim_bench/harness/ontology.py                            |  27 +++  (D0.0)
lithrim_bench/harness/report.py                              |   5 +-   (D0.3 — surface the skip bucket)
scripts/run_eval.py                                          |  12 +-   (D3)
scripts/seed_ontology.py                                     |  68 +++  (D0.1)
tests/test_ws2.py                                            | 176 +++   (D4)
```

**Findings:**

- All diffed files map to a bench-side deliverable. `report.py:38/56` is the
  reporting half of D0.3 (surface `skipped_non_gradeable_count` + a reasoning
  line) — in-scope per D0.3's "never silently scored … surfaced in the report."
  No intrusion detected.
- **Working-tree drift correctly excluded.** The repo's dirty tree at session
  start (`backends/*.py`, `eval_runner.py`, `tests/test_structural_backend.py`,
  the `.devloop/` scaffold, several docs) is **not** in the committed range —
  `git diff --stat` of the range shows only the 9 files above. Driver §7 named
  these as not-the-executor's; they were not swept in. CLEAN.
- **Deferred D2 prose rewrite NOT pre-empted.** No `../lithrim-backend/` file,
  no `compliance_council.py`, no `build_prompt` edit appears in the range. The
  D2 scope (S-BS-11) lives only as a *recorded seam* in the session-log chore
  `5ba1bec` (documentation, not code). The locked "additive-block-only / full
  prose rewrite deferred" boundary (STREAM S-BS-11) is respected on the
  bench side by construction — the backend half has not started. CLEAN.

All diffed files map to deliverables. No intrusion detected.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: `gradeable` membership **source** — `bool(tier)` gated by the snapshot, vs the spec's "gradeable = in-snapshot"

- **Spec text:** D0.1 (`…driver.md:182-185`) — "Partition: **gradeable** =
  in-snapshot (carry `tier` + owner); **reference** = out-of-snapshot." S-BS-10
  decision (`STREAM…:70`) — "ontology gradeable set = the 19 tiered snapshot
  codes … **snapshot-authoritative**."
- **Implementation decided:** `seed_ontology.py:230` sets `"gradeable":
  bool(tier_of.get(d.flag))` — i.e. gradeable iff the **runtime council** tiers
  the flag (parsed from `compliance_council.py` TIER_1/2/3). The snapshot is then
  used only as a **one-directional gate** (`gradeable_flags_outside_snapshot`,
  `seed_ontology.py:160`): it fails if a gradeable flag is *outside* the
  snapshot, but it does **not** flag a snapshot code the runtime fails to tier
  (that flag would silently become `gradeable=false` → treated as reference →
  skip-logged, **with no lint**). In steady state runtime-tier and the snapshot
  agree (verified: 19 == 19), so today the two definitions coincide and the
  committed partition is correct.
- **Alternatives that would also be spec-compliant:** (a) define
  `gradeable = (flag in snapshot_codes)` directly (literal "snapshot-
  authoritative"), making the snapshot the *source* not just the *gate*; (b)
  make the lint bidirectional (also fail if a snapshot code is not gradeable),
  catching backend-tier vs snapshot divergence in *both* directions.
- **Question for spec author:** Is the asymmetric gate intended? The current
  shape catches "runtime tiers a flag the snapshot has not blessed" but **not**
  "the snapshot blesses a code the runtime no longer tiers" — the latter would
  silently drop a contract-of-record code from scoring. Given CLAUDE.md makes
  the snapshot the contract, a code the snapshot carries but the runtime drops
  is arguably the more dangerous divergence (a true defect could go unscored).
- **Recommended resolution:** ACCEPT for WS-2 (behavior correct today; executor
  documented the equivalence in the commit body + the seed `gradeable_note`
  provenance), but lock the intended source-of-truth in the spec and consider a
  bidirectional lint as a follow-up seam.

### Ambiguity 2: reference findings removed from `active` vs S-BS-8 null-code findings retained in `active`

- **Spec text:** D0.3 (`…driver.md:189-192`) — "skip-logged **like** the S-BS-8
  null-code path, never silently scored." S-BS-8 null-code findings are
  explicitly *retained* in `active` (STREAM S-BS-8: "skip-logged … retained in
  active, surfaced in report — never dropped").
- **Implementation decided:** `grounding.py:204-207` — reference findings are
  appended to `skipped_non_gradeable` **and removed from `active`** (no
  fall-through), whereas null-code findings (`:202-204`) are appended to
  `ungrounded` **and kept in `active`**. The two "skip-logged" buckets behave
  differently w.r.t. the verdict re-score.
- **Alternatives that would also be spec-compliant:** keeping reference findings
  in `active` (literal "like the S-BS-8 path") — but that would let a HIGH
  reference finding drive BLOCK, violating "never scored." So removal is the
  only treatment consistent with the dominant clause.
- **Question for spec author:** Confirm the intended semantics: "skip-logged like
  S-BS-8 for *surfacing/never-dropped*, but unlike S-BS-8 *removed from the
  scored set*." The impl chose this and the executor surfaced it
  (`grounding.py:23-27` docstring + commit body).
- **Recommended resolution:** ACCEPT; the spec wording "like the S-BS-8 path" is
  the ambiguity, the impl resolved it in favour of the "never scored" mandate.
  Tighten the spec phrasing in a doc-only pass.

### Ambiguity 3: the lint gates only the 19-code tier union, not the 5 structural codes

- **Spec text:** D0.1 names "the 19-code tier union"; driver §9 (`:418-420`)
  notes "the de-facto known set is 19 tier-union + 5 structural."
- **Implementation decided:** `load_snapshot_codes` (`seed_ontology.py:139`)
  unions only `data["tiers"]` (→ 19); the 5 `structural_codes` are not part of
  the gate. A *coded* structural finding (non-null code, not one of the 23
  ontology flags) would be an "unknown code" → left in `active` (`grounding.py`
  fall-through) → scored. In practice structural findings return `code=None`
  (S-BS-8) so this is latent, not live.
- **Question for spec author:** Is excluding structural codes from the gradeable
  gate intended (they are a separate S-BS-8 path), or should coded structural
  findings be classified explicitly rather than falling through as "unknown"?
- **Recommended resolution:** ACCEPT for WS-2 (matches the literal "19-code tier
  union" spec text and is S-BS-8 territory); note as a WS-3 grounding-coverage
  question.

**Findings:**

- `[OPEN-QUESTION]` Ambiguity 1 — `gradeable` source = runtime-tier with a
  one-directional snapshot gate; the spec says "snapshot-authoritative." Behavior
  correct today; lock the source-of-truth and consider a bidirectional lint.
- `[OPEN-QUESTION]` Ambiguity 2 — reference findings removed from `active`
  (unlike S-BS-8 null-code, which is retained). Correct per "never scored";
  tighten spec phrasing.
- `[OPEN-QUESTION]` Ambiguity 3 — lint covers the 19-code tier union only, not
  the 5 structural codes. Matches spec text; flag as WS-3 coverage.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 1 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 3 |

**Total BLOCKING: 0** → cycle MAY close (on the bench-side scope).

---

## Required actions (if any)

No BLOCKING findings. For the NON-BLOCKING / OPEN-QUESTION items worth a
follow-up but not blocking closure:

1. **Finding (Q1, NON-BLOCKING):** query helpers `flag`/`owners_of`/`contract_for`
   were not extended to filter gradeable-only; new predicates added instead.
   **Proposed disposition:** accept as-is (intent met; grounding routes through
   `is_reference`). Optional doc-only spec wording fix.
2. **Finding (Q4 Ambiguity 1, OPEN-QUESTION):** `gradeable=bool(tier)` + a
   one-directional snapshot gate vs literal "snapshot-authoritative."
   **Proposed disposition:** spec author locks the source-of-truth; consider a
   bidirectional lint (also fail on in-snapshot-but-untiered) as a new seam —
   the more dangerous divergence (a contract-of-record code silently unscored)
   is currently uncaught.
3. **Finding (Q4 Ambiguity 2, OPEN-QUESTION):** reference-removed-from-`active`
   vs S-BS-8 null-code-retained. **Proposed disposition:** accept (correct per
   "never scored"); tighten spec phrasing ("skip-logged for surfacing, removed
   from the scored set").
4. **Finding (Q4 Ambiguity 3, OPEN-QUESTION):** lint covers the 19-code tier
   union only. **Proposed disposition:** accept for WS-2; carry as a WS-3
   grounding-coverage question for coded structural findings.

**Carry-forward to the backend half (gated, NOT this critique's scope):** A2
(additive `PipelineRequest`, `None`==byte-identical) and A3 (injected ontology
drives the live tier/owner/question lookup) remain SKIP. The HARD-GATE close
must re-run a fresh critic over the backend D1/D2/D4 commits (which will touch
`models.py`/`stages.py`/`compliance_council.py`) before they land, per the
driver §Hardness. The locked D2 scope (S-BS-11: instance-resolvable
tier/owner/known-code LOOKUP + model selection + **additive-block-only** prompt
threading; full prose rewrite deferred) is the boundary that next critic must
police.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec (task pack + driver + STREAM seams + CLAUDE.md) without
      reading the executor's session log first
- [x] Read the diff via `git show` against each commit, not via the executor's
      summary; verified base `3e7f7f7 == 8b396d3^` and no backend file in range
- [x] Each finding cites both spec `file:line` and implementation `file:line`
- [x] Did NOT edit any code, spec, or driver (critique file only)
- [x] Did NOT confer with monitor or executor before writing the verdict

Cross-check note: after forming the read I read the session log
(`session-bench-salvage-phaseWS-2-2026-05-31.json`). It is consistent with the
independent read — bench-side D0/D3/D4 landed, A2/A3 SKIP (gated), the
`gradeable=bool(tier)` choice and the reference-removed-from-`active` divergence
were both self-disclosed in the commit bodies and docstrings. The one item the
log does not itself raise — the *asymmetry* of the snapshot gate (Ambiguity 1) —
is this critique's independent contribution.

---

## Appendix: commits audited

```
5ba1bec chore(ws2): record locked D2 seam scope + live-smoke timing in session log
d434eef chore(ws2): session log — bench-salvage WS-2 (INTERIM, bench-side closed)
289ed15 test(ws2): D0 lint gate + harness injection (offline)
01e2adc feat(ws2): grade_live + run_eval inject stored council_config/ontology
2fbbbb8 refactor(ws2): grounding/re-score operate on gradeable-only (S-BS-10)
e6c7032 chore(ws2): re-seed clinical_v1 with gradeable/reference partition
8b396d3 feat(ws2): snapshot-authoritative flag membership + lint gate (S-BS-10)
```

## Appendix: files changed

```
.devloop/sessions/session-bench-salvage-phaseWS-2-2026-05-31.json | 144 +++
data/ontology/clinical_v1.json                                    |  26 ++-
lithrim_bench/harness/grade.py                                    |  68 +++--
lithrim_bench/harness/grounding.py                                |  28 +++-
lithrim_bench/harness/ontology.py                                 |  27 +++-
lithrim_bench/harness/report.py                                   |   5 +-
scripts/run_eval.py                                               |  12 +-
scripts/seed_ontology.py                                          |  68 +++++-
tests/test_ws2.py                                                 | 176 +++++
9 files changed, 522 insertions(+), 32 deletions(-)
```

## Appendix: verification commands run by the critic (read-only)

```
python3 -m pytest tests/test_ws2.py -q          → 8 passed
python3 scripts/seed_ontology.py --check        → OK … (23 flags), exit 0
python3 (snapshot inspect)                      → tiers union = 19; 4 fork flags absent
git rev-parse 8b396d3^                           → 3e7f7f7… (base confirmed)
git show --stat 8b396d3..5ba1bec | grep backend → no backend file in range
```
