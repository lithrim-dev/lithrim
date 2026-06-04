# Spec-Adherence Critique — `bench-salvage` phase `UAP-3b`

> Fresh-critic mode (separate session, cold read). HARD GATE.
> Committed alongside close-out artifacts as
> `.devloop/sessions/critique-bench-salvage-phaseUAP-3b-2026-06-04.md`.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `UAP-3b` — THE MOAT: the §2A signals bus + the per-judge, PRE-consensus withstands-gate
- **Driver bundle:** `bench-salvage-phaseUAP-3b-withstands-gate-driver`
- **Commits audited:** `8cb388b..9eadf39` (parent `acc4973`): `8cb388b` (D1 signals), `d9a5bb0` (D2 withstands), `a9dc899` (D4 audit), `5da98b8` (D5 tests), `f18399e` (D6 docs), `9eadf39` (session log)
- **Spec(s) read against:** `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §2A (lines 56-74), §2B (78-115), §12 (264-269), §13 (273-289); driver §2/§3/§4/§5
- **Critique mode:** `fresh-critic`
- **Date:** `2026-06-04`
- **Reviewer:** `critic session (cold)`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

One sentence: The moat exhibit is **genuinely gate-attributable** (the reject→approve flip rides the frozen consensus's own off-domain-Tier-1 downgrade in the baseline and is stripped pre-consensus by the gate, with `apply_gate=False` a faithful no-gate baseline whose only behavioral delta is the gate block), A3 frozen-seam delta is **0 lines (measured)**, the full suite is **273 passed**, A5 "cannot relabel a true case" **holds** under my worst adversarial case, and the on-by-default gate + the S-BS-72 provenance-blob split are both **principled and honestly logged** — no BLOCKING issue; safe to close as PROCEED-WITH-CAVEATS.

---

## 1. Surface fidelity

> Do the new modules + wiring + audit/correction additions match spec §2A + driver §2?

| Spec / driver definition | Implementation | Match? | Severity |
|---|---|---|---|
| Driver §2A.D1 `signals.py`: `JudgeSignals{ontology_rules, validator_outputs}`, ontology-rule signals = `tier/owner_roles/when/when_NOT/severity`, validator signals reuse `grounding`'s executors, pure no-LLM | `signals.py:42-201` — `OntologyRuleSignal`/`ValidatorOutputSignal`/`JudgeSignals`; `build_judge_signals` reuses `grounding._build_contract`+`_CONTRACT_EXECUTORS` (`:182-185`); module import-clean | YES | — |
| Driver §2A.D2 `withstands.py`: `apply_withstands_gate(results, *, ontology, signals_by_role, …) -> (corrected_results, decisions)`; `WithstandsDecision{role, signals_weighed:[ontology_rules,validator_outputs], decision, what_failed}` (SPEC §2B :102) | `withstands.py:78-189` — signature is `(results, *, ontology, case, lens_by_role, assignments, http_client)` (builds signals internally, not `signals_by_role=`); `WithstandsDecision` (`:48-68`) carries all spec keys + `decision_before/after`; `to_audit_why()` emits exactly `{signals_weighed, decision, what_failed}` | YES (signature shape differs from the driver's illustrative `signals_by_role=`; semantically identical — builds per-judge signals inline) | NON-BLOCKING (driver §2 said "…") |
| Driver §2 D2.3: wire into `authored_stage._evaluator` between `results=[…]` (`:83`) and `_apply_consensus` (`:87`); corrected results feed consensus UNCHANGED; thread decisions to the envelope | `authored_stage.py:98-128` — gate runs between `results = [j.forward…]` (`:98`) and `council._apply_consensus(results,…)` (`:123`); corrected `results` reassigned; `decisions_sink.extend` (`:117-118`) | YES | — |
| SPEC §2B :89 — add `withstand` to the action enum | `audit.py:83` comment now lists `… suppress \| flip \| withstand \| …` | YES | — |
| Driver §2 D4 — record AuditRecord (action withstand/flip) + a correction record | `run_eval.py:266-301` — `AuditLog.record(AuditRecord(action=withstand\|flip, actor.type=critique, why=ruling, run_id, case_id))` + `build_withstands_correction` (`correction.py:157-209`) per corrected decision | YES | — |
| Driver §2 D4 — "into the **processing-provenance** chain (the `SqliteProvenanceStore` blob, SPEC §2B :107)" | NOT landed — the run-PROVENANCE-blob embedding is split to UAP-3b-2 (logged S-BS-72); the AuditLog/config_audit + corrections NDJSON landed | PARTIAL — logged plan-review deviation (APPROVED-MID-CYCLE) | NON-BLOCKING |
| Driver §2 D3 / A6 — GroundingChecks first-class config-authored entities at the post-consensus locus | NOT landed — split to UAP-3b-2 (pre-authorized D-E) | DEFERRED — logged | NON-BLOCKING |

**Findings:**

- `[NON-BLOCKING]` The `apply_withstands_gate` signature takes `ontology, case` and builds signals internally rather than the driver's illustrative `signals_by_role=` param. This is a strict improvement (the gate owns signal assembly so the caller can't pass stale signals), and the gate's *interface* still admits an LLM `critique` hook later without a reshape (docstring `withstands.py:27-29`). Classify: **unauthorized-but-benign surface choice**, semantically faithful to §2A.
- `[NON-BLOCKING]` D4 uses `AuditLog.record` not `upsert_with_audit`. **Logged plan-review deviation** (APPROVED-AT-PLAN). Correct call: `upsert_with_audit` is the config-write primitive (before→after upsert); a withstands ruling is a processing *event* carrying `run_id`/`case_id`/`actor.type=critique` — `AuditLog.record` is the right primitive. Faithful to §2B's universal-record shape (`audit.py:77-97`).
- `[NON-BLOCKING]` The moat exhibit was reframed from the driver's "MED-FP validator-disprove" (D-C candidate 1) to an **ontology-rule out-of-lens rejection**. **Logged plan-review deviation** (APPROVED-AT-PLAN), and I independently confirmed the *reason it was necessary*: `composite()` (`report.py:29-34`) re-scores from `grounded.active` via `severity_map.rescore` and **never reads `consensus["decision"]`**; `ground()` (`grounding.py:436-472`) already runs the *same* suppress contracts (`_CONTRACT_EXECUTORS`) post-consensus, so a validator-disprove would be corrected by `ground()` with or without the gate → no *gate-attributable* composite flip. Only the ontology-rule mode (no contract exists for the code) yields a flip uniquely owned by the gate. This deviation is not drift; it is what makes A2 honest.
- `[NON-BLOCKING]` D3/A6 + the LLM Ralph-Loop critique + the live attestation split to UAP-3b-2. **Pre-authorized** (driver §3 D-E; §4). Stub driver `bench-salvage_phaseUAP-3b-2_groundingcheck-entity-llm-critique_driver.md` written (deferred-not-dropped).

No surface drift that is *un*-logged. All 4 deviations are logged plan-review decisions.

---

## 2. Behavioral fidelity

### Behavior 1: the moat exhibit — a deterministic signal corrects a wrong judge → the composite flips, gate-attributably (A2)

- **Spec assertion:** §2A :71 "The deterministic layer can correct the LLM layer … now per-judge and critique-mediated." Driver A2: "a confidently-wrong judge finding is **corrected by a deterministic signal pre-consensus → the composite verdict CHANGES** (offline/$0)."
- **Test:** `tests/test_uap3b_withstands.py:250-300` `test_MOAT_EXHIBIT_gate_flips_composite_and_ground_alone_does_not` — SAME clean-negative case (`bench_scribe_v1_clean_negative_aaecd73c3bcf`, `expected_compliance_verdict==approve`) + SAME `risk_judge`-PHI-FP predictor, graded twice: `apply_gate=False` → `comp_off["verdict"]=="reject"` with `PHI_DISCLOSURE_PRE_VERIFICATION` in `active_findings`; `apply_gate=True` → `comp_on["verdict"]=="approve"` with the code gone. Only the gate flag differs.
- **Implementation:** `authored_stage.py:105-118` (the gate block) + `withstands.py:144-164` (the out-of-lens reject) + `signals.py` (the lens authority).
- **Chain closes?** **YES — and I traced *why the baseline rejects*, which is the load-bearing crux.** In the gate-OFF path the corrected-results path is identical to feeding the raw results; the FP flows into `_apply_consensus`. `PHI_DISCLOSURE_PRE_VERIFICATION` is **not** in `PHI_FALSE_POSITIVE_TYPES` (`compliance_council.py:222` — only `IMPLICIT_CONFIRMATION_OF_RECORD`; the comment at :220-221 notes PHI_DISCLOSURE moved to Tier-1), so the PHI-FP suppress at :2044-2052 does **not** fire. It hits the Tier-1 single-judge-with-evidence branch (`:2084`); `_TIER1_OWNERS["PHI_DISCLOSURE_PRE_VERIFICATION"]={"policy_judge"}` (`judge_metric`-adjacent table, `compliance_council.py:255`) and the firing judge is `risk_judge` ∉ owners → it down-ranks to `tier2_flagged` (the off-domain single-judge downgrade `:2107-2115`) → `_findings_from_evidence_summary._mk("MEDIUM", tier2_flagged)` (`stages.py:396`) → a MEDIUM finding → `severity_map.rescore` blocks → composite `reject`. The gate-ON path strips the FP from `risk_judge`'s seam dict **before** `_apply_consensus`, so it never enters `evidence_summary` → never a `Finding` → never in `active` → composite `approve` = the by-construction truth. The flip is owned by the gate; the baseline rejects via the **frozen seam's own logic**, not test rigging.
- **Is `apply_gate=False` a faithful no-gate baseline?** **YES.** I read `authored_stage._evaluator` in full: the ONLY behavioral difference between the two paths is the `if apply_gate:` block (`:105-118`); `results` flows to `council._apply_consensus(results, gate_mode=gate_mode)` identically otherwise, and `predictors`/`assignments`/`ontology` are the same object in both `build_authored_semantic_stage` calls. No hidden second difference. The double-assertion holds.

### Behavior 2: the gate CANNOT relabel a by-construction case (§2A invariant; A5)

- **Spec assertion:** §2A :74 "The critique can **down-rank or correct** a judge's reasoning but **cannot relabel a by-construction case**." `CLAUDE.md` core invariant.
- **Test:** `test_by_construction_guard_in_lens_true_finding_withstands` (`:125-137` — `risk_judge` raises its own Tier-1 `WRONG_DOSAGE`; kept, verdict stays `reject`, decision `withstand`) + `test_by_construction_guard_corroborated_owner_not_dropped` (`:140-152` — an out-of-lens raise CORROBORATED by the owning judge is kept on BOTH judges).
- **Implementation:** `withstands.py:144-164` — the reject fires ONLY when `code not in lens` AND `not owner_corroborates`; an owning co-raiser protects it. The validator-suppress (`:131-140`) fires ONLY when `code in disproved` and `PresenceCheck` (`grounding.py:146-175`) returns `disproved=True` **only on a positive verbatim presence match** (conservative; a genuinely-true "not in transcript" returns `disproved=False`).
- **Chain closes?** **YES** — see §"INDEPENDENTLY VERIFIED / A5" below for the adversarial probe. The exhibit's restored verdict (`approve`) **matches the case's `expected_compliance_verdict`** — restoring truth, never inventing it.

### Behavior 3: above the frozen seam, byte-0-delta (A3)

- **Spec assertion:** §2A :73-74 "All of this lives **above the frozen consensus seam** (`_apply_consensus` stays byte-frozen)." Driver A3: `git diff` over the frozen set == 0 lines.
- **Test:** `test_frozen_seam_zero_delta` (`:206-224`) asserts `git diff acc4973 HEAD -- <frozen set incl. council_roles/, clinical_v1.json, ws0_default.json>` stdout `== ""`.
- **Implementation:** `authored_stage.py:123` calls `council._apply_consensus(results, gate_mode=gate_mode)` (CALLED-only); the gate writes NEW dicts (`withstands.py:168 corrected = dict(r)`), never mutating the seam dict definition.
- **Chain closes?** **YES — measured independently: 0 lines** (see below). The test pins it in CI too.

**Findings:**

- `[NON-BLOCKING]` Behavior 1's baseline-reject mechanism (the off-domain Tier-1 → tier2_flagged → MEDIUM block) is **implicit** in the test (the test asserts the outcome, not the path). It is robust because it rides frozen consensus logic, but a future change to `_TIER1_OWNERS` or the off-domain-downgrade branch could silently change the baseline from `reject` to something else and the exhibit could degrade without the *gate* being at fault. Suggest a one-line code comment in the test naming the dependency. Disposition: optional polish.

---

## 3. Out-of-scope intrusion

Driver's §2 deliverables: D1 `signals.py` · D2 `withstands.py` + `authored_stage` wire · D3 GroundingCheck surface (SPLIT) · D4 `audit.py`+`correction.py`+provenance (blob half SPLIT) · D5 `tests/test_uap3b_withstands.py` · D6 `SPEC_PRODUCT_SHELL.md §10` note + UAP-3b-2 stub.

`git diff --stat acc4973..HEAD`:

```
.devloop/prompts/...UAP-3b-2_..._driver.md          |  65 ++   (D-E split stub — D6, expected)
.devloop/sessions/session-...UAP-3b-2026-06-04.json |  79 ++   (session log — expected)
docs/specs/SPEC_PRODUCT_SHELL.md                    |   1 +    (D6 §10 note)
lithrim_bench/harness/audit.py                      |   2 +-   (D4 — one comment line)
lithrim_bench/harness/correction.py                 |  57 ++   (D4 — build_withstands_correction)
lithrim_bench/runtime/council/authored_stage.py     |  36 ++   (D2 wire)
lithrim_bench/runtime/council/signals.py            | 201 ++   (D1)
lithrim_bench/runtime/council/withstands.py         | 189 ++   (D2)
scripts/run_eval.py                                 |  51 ++   (D4 emit)
tests/test_uap3b_withstands.py                      | 330 ++   (D5)
```

**Findings:**

- All diffed files map to deliverables (D1/D2/D4/D5/D6 + the pre-authorized split stub + the session log). **No intrusion detected.** No drive-by formatting, no dep bumps, no "while I was here". The `SPEC_PRODUCT_SHELL.md` change is a single additive `§10` note (the BFF surface is unchanged, as required — the gate runs in-process).
- **FROZEN set untouched — measured 0 (see below).** `compliance_council.py`, `judges_dspy.py`, `judge_metric.py`, `council_roles/*.txt`, `clinical_v1.json`, `ws0_default.json` are byte-identical to `acc4973`.
- **Scope/contamination clean:** `git status --porcelain` shows only the three foreign untracked files (`.claude/`, `.devloop/sessions/KICKOFF_CRITIC_bench-salvage-WS-6c-DSPy-2026-06-02.md`, `docs/research/REPORT_fhir_agentbench_2026-06-04.md`) — NOT swept into any commit (`git-commit-pathspec-dirty-index` honored).

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: the gate's ownership authority — `LENS_BY_ROLE` vs the ontology `owner_roles` vs `_TIER1_OWNERS`

- **Spec text (or absence):** §2A :66-69 says a raise "outside its assigned lens/owner" is rejected, but does NOT name *which* owner table is authoritative. Three exist: the committed ontology's `owner_roles` (stale v1, no `faithfulness_judge` — S-BS-59), `LENS_BY_ROLE` (the production v2-trio lens), and `_TIER1_OWNERS` (the consensus one-strike table, which includes dormant `behavior_judge`/`source_message_judge`).
- **Implementation decided:** the gate uses `LENS_BY_ROLE` (`signals.py:81-107`, `withstands.py:121,144-152`), explicitly NOT the stale ontology `owner_roles` (docstring `signals.py:9-13`). This is consistent with the spec's own §13/§10 authority note ("authority = `LENS_BY_ROLE`/`_TIER1_OWNERS`, *not* the ontology's `owner_roles`").
- **Alternatives that would also be spec-compliant:** using `_TIER1_OWNERS` as the corroboration authority (would *widen* who counts as an owner to include dormant judges — but those judges never run under v2, so it would never protect a real raise; functionally equivalent given the trio).
- **Question for spec author:** Should §2A name `LENS_BY_ROLE` as the gate's lens/owner authority explicitly (it currently only does so for the BFF in §10)? And should it state that a code whose **only** owner is a dormant/non-trio judge has no in-trio owner, so a trio raise of it is treated out-of-lens?
- **Recommended resolution:** accept (the choice is correct + already implied by the spec's owner-authority note); lock the wording in a doc pass.

### Ambiguity 2: down-rank-to-`approve` when all blocking findings are stripped

- **Spec text:** §2A :74 "down-rank or correct a judge's reasoning". The spec does not specify *what* a judge's decision becomes when the gate strips its last blocking finding.
- **Implementation decided:** `withstands.py:172-175` — when `what_failed and not kept and decision_before in {"reject"}`, set `decision_after="approve"`. Note: `_BLOCKING_DECISIONS={"reject"}` only — a judge at `needs_review` is NOT down-ranked even if emptied.
- **Alternatives that would also be spec-compliant:** down-rank to `needs_review` instead of `approve`; or leave the decision and rely on consensus re-deriving from the emptied findings (consensus uses `result["findings"]`, so an emptied judge contributes no violation regardless of its `decision` string — the down-rank is *belt-and-suspenders*, not load-bearing for the composite).
- **Question for spec author:** Is "strip all blocking findings → judge decision becomes `approve`" the intended semantics, and is excluding `needs_review` from down-rank deliberate?
- **Recommended resolution:** accept; the composite verdict derives from `active` findings (not the judge `decision` string), so this choice is cosmetic for the verdict and only affects the per-judge audit legibility. Worth a one-line spec note.

### Ambiguity 3: severity-weight fallback for an unmapped code (`signals.py:156-159`)

- **Spec text:** silent on how `OntologyRuleSignal.severity_weight` is computed when a flag's tier isn't `TIER_1`.
- **Implementation decided:** `TIER_1 → max weight`, else `MEDIUM` weight; `decl is None → 0.0`. This `severity_weight` is **informational only** in the signals bus this cycle (the gate's reject/suppress logic does not branch on it), so the fallback cannot misfire a correction.
- **Question for spec author:** none load-bearing — flag only if a future LLM-critique pass starts *weighing* severity to decide withstands.
- **Recommended resolution:** accept.

**Findings:**

- `[OPEN-QUESTION]` Lock `LENS_BY_ROLE` as the gate's named owner authority in §2A (Ambiguity 1).
- `[OPEN-QUESTION]` Confirm the down-rank-to-`approve` semantics + the `needs_review` exclusion in §2A (Ambiguity 2).
- `[OPEN-QUESTION]` Note that `severity_weight` is informational this cycle; revisit if the LLM critique weighs it (Ambiguity 3).

---

## INDEPENDENTLY VERIFIED (commands I ran myself)

**A3 frozen-seam 0-delta (load-bearing):**
```
git diff acc4973..HEAD -- compliance_council.py judges_dspy.py judge_metric.py council_roles/ clinical_v1.json ws0_default.json | wc -l
→ 0
```
**0 — PASS. Not BLOCKING.** Pinned in CI by `test_frozen_seam_zero_delta`.

**UAP-3b suite (re-run myself, debuglithrim):**
```
PYENV_VERSION=debuglithrim python -m pytest tests/test_uap3b_withstands.py -q  →  9 passed in 1.90s
```
including the load-bearing `test_MOAT_EXHIBIT_gate_flips_composite_and_ground_alone_does_not` and `test_consensus_decision_flips_with_validator_disprove` (the gate flips the FROZEN `_apply_consensus` output reject→approve at the consensus level via a 2-judge validator-disprove — a mode `ground()` structurally cannot touch).

**Broader regression (the on-by-default concern):**
```
PYENV_VERSION=debuglithrim python -m pytest tests/ -q -k "uap or council or grade or authored"  →  34 passed, 239 deselected
PYENV_VERSION=debuglithrim python -m pytest tests/ -q                                            →  273 passed, 2 warnings
```
**No existing test regressed** despite `apply_gate=True` default.

**Default-deps import-cleanliness (A5):**
```
import signals, withstands → LEAKED heavy deps: NONE  (no dspy/openai/httpx/fastapi)
ruff check <7 changed .py> → All checks passed!
```

**The moat exhibit is GENUINE, not theater:** verified (i) `composite()` (`report.py:29-90`) derives the verdict purely from `grounded.verdict = ontology.severity_map.rescore(grounded.active)` and `_STAGE_TO_COMPLIANCE` — it **never reads `consensus["decision"]`**; (ii) `ground()` (`grounding.py:440-472,497-508`) builds `active` from `result["findings"]` + `result["semantic"]["evidence"]`, which flow from `_apply_consensus`'s `evidence_summary` (built from the **corrected** per-judge `findings`, `compliance_council.py:1910-1937`); (iii) the test grades the SAME case + SAME predictor with only `apply_gate` toggled, and `apply_gate=False` is a faithful no-gate baseline (the sole behavioral delta is the `if apply_gate:` block in `authored_stage.py:105-118`). **The flip is truly gate-attributable; no hidden second difference.**

**A5 — can the gate EVER relabel a TRUE case? (adversarial worst case):**
- *(a) dormant/non-trio sole-owner:* I constructed it. `_TIER1_OWNERS` contains dormant owners (`behavior_judge`, `source_message_judge`), but the **gate** uses `LENS_BY_ROLE` (3 trio roles), and `owner_corroborates` (`withstands.py:145-152`) iterates only `raised_by_role` (the actual results). So if a code's only owner is a non-trio judge, a trio raise of it is rejected as out-of-lens. **Is this a relabel?** No — under the v2 trio that code has **no judge that can legitimately raise it**, so any trio raise of it is by-definition out-of-its-lens noise. The analogous live concern is a Tier-1 code with an *in-trio* owner who stays silent while another trio judge raises it true (e.g. `faithfulness_judge` raises a true `MISSED_ESCALATION`, `risk_judge` silent). The gate would reject it. **But this is exactly the existing owner-consistency model (S-BS-12):** `MISSED_ESCALATION`/`SEVERITY_ESCALATION`/`FABRICATED_ALLERGY` are *deliberately excluded* from `FAITHFULNESS_JUDGE_LENS` (`judge_metric.py:86-90` — "their corroborating raises score as out-of-lens FPs"), so a faithfulness solo-raise of them is *already* scored as a false positive by the production metric. The gate suppressing it is **consistent with the by-construction owner model, not a novel relabel** — and the executor logged this exact residual as S-BS-73 (a SOLO out-of-lens raise is now rejected; validate on the live attestation). It is a **defensible coverage choice**, not a true-case relabel: the by-construction labels in `examples/*.jsonl` only credit a code to its owner, so the gate cannot strip a finding the *label* would have credited.
- *(b) down-rank-to-approve on a case that SHOULD block:* fires only when `what_failed and not kept` (every blocking finding was either validator-disproved or out-of-lens-uncorroborated). A SHOULD-block case has at least one in-lens, owner-corroborated, validator-undisproved finding → it is `kept` → `not kept` is False → no down-rank. Cannot misfire.
- *(c) validator-disprove on a TRUE finding (mis-scoped contract):* `PresenceCheck.check` (`grounding.py:146-175`) returns `disproved=True` ONLY on a verbatim positive presence match of a record-resolved med token in the transcript; a genuinely-true "not in transcript" returns `disproved=False`. The gate keys suppress on `disproved` (`withstands.py:132`). A mis-scoped *contract declaration* is an ontology-authoring concern outside this cycle's surface (the gate reuses, never rewrites, the executors). Within scope, the suppress cannot fire on a true finding.

**A5 holds** under every worst case I could construct: the gate corrects only signal-contradicted or out-of-(trio)-lens-uncorroborated findings, and the restored verdict matches the by-construction `expected_compliance_verdict`.

**The S-BS-72 split honesty:** verified `grade.py:162-170` — `grade_inprocess` does `LocalPipelineBackend(...).evaluate_pipeline(case)` which **builds + saves provenance internally** and returns a dict "byte-identical with the store on or off" (`:159-160`); `run_eval` (`run_eval.py`) gets the result *after* the save, with no pre-save provenance handle. Embedding the withstands ruling **into** the blob therefore requires an orchestrator/`LocalPipelineBackend` edit — which sits above/adjacent to the frozen consensus and would risk A3. **The split is principled, not a dodge.** The *certain* audit DID land: `AuditLog.record` (`run_eval.py:271-280`) + the `build_withstands_correction` NDJSON (`:288-301`), test-pinned by `test_withstands_decision_audited`. The interim home is the `config_audit` stream (a slight stream-1/stream-2 mix) — honestly disclosed as S-BS-72, low severity.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 4 | 0 |
| 2 | Behavioral fidelity | 0 | 1 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 3 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (if any)

No BLOCKING findings — no required correction.

NON-BLOCKING / OPEN-QUESTION dispositions (none gate closure):

1. **Finding:** D4 provenance-blob embedding not landed. **Disposition:** already logged S-BS-72 → UAP-3b-2 (accept).
2. **Finding:** D3/A6 GroundingChecks + LLM critique + live attestation split. **Disposition:** pre-authorized D-E split → UAP-3b-2 stub written (accept).
3. **Finding:** S-BS-73 — on-by-default gate rejects a SOLO out-of-(trio)-lens raise on live trio runs. **Disposition:** logged; validate on the UAP-3b-2 live attestation before treating the authored live path as a verdict source (accept; consistent with the S-BS-12 owner model).
4. **Finding:** the moat baseline-reject path (off-domain Tier-1 → MEDIUM block) is an implicit test dependency. **Disposition:** optional — add a one-line comment in `test_MOAT_EXHIBIT…` naming the `_TIER1_OWNERS`/off-domain-downgrade dependency (NON-BLOCKING polish).
5. **Findings (OQ 1-3):** lock `LENS_BY_ROLE` as the gate's named owner authority; confirm the down-rank-to-`approve`/`needs_review`-exclusion semantics; note `severity_weight` is informational this cycle. **Disposition:** a §2A doc pass in a separate cycle (not blocking).

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec (§2A/§2B/§13) + driver before reading the executor's session log
- [x] Read the diff via `git diff`/`git show` against `acc4973..HEAD`, not via the executor's summary
- [x] Each finding cites both spec/driver and implementation file:line
- [x] Did NOT edit any code, spec, test, or driver (only this critique file)
- [x] Did NOT confer with monitor or executor; re-ran the tests + A3 wc-l + import/ruff checks independently before writing the verdict; read the session log LAST

---

## Appendix: commits audited

```
9eadf39 docs(bench-salvage): UAP-3b executor session log (PROCEED-WITH-CAVEATS)
f18399e docs(spec): note the withstands-gate landed + the `withstand` action + the UAP-3b-2 split (UAP-3b D6)
5da98b8 test(uap-3b): the moat exhibit (grounding corrects a wrong judge -> flip) + withstand-admit + frozen 0-delta + by-construction guard
a9dc899 feat(audit): withstands-decision audit + correction records; add `withstand` action (UAP-3b D4)
d9a5bb0 feat(withstands): pre-consensus per-judge withstands-gate, above the frozen seam (UAP-3b D2)
8cb388b feat(signals): per-judge signals bus — ontology rules + validator/grounding outputs (UAP-3b D1)
```

## Appendix: files changed

```
.devloop/prompts/...UAP-3b-2_groundingcheck-entity-llm-critique_driver.md |  65 ++
.devloop/sessions/session-bench-salvage-phaseUAP-3b-2026-06-04.json       |  79 ++
docs/specs/SPEC_PRODUCT_SHELL.md                                          |   1 +
lithrim_bench/harness/audit.py                                            |   2 +-
lithrim_bench/harness/correction.py                                       |  57 ++
lithrim_bench/runtime/council/authored_stage.py                          |  36 ++
lithrim_bench/runtime/council/signals.py                                 | 201 ++
lithrim_bench/runtime/council/withstands.py                              | 189 ++
scripts/run_eval.py                                                       |  51 ++
tests/test_uap3b_withstands.py                                           | 330 ++
10 files changed, 1009 insertions(+), 2 deletions(-)
```
