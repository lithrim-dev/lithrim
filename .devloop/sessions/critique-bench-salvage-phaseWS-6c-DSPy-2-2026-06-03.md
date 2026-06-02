# Spec-Adherence Critique — `bench-salvage` phase `WS-6c-DSPy-2`

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-6c-DSPy-2` (complete the DSPy judge trio — policy + faithfulness lenses — + the prompt-vs-DSPy A/B harness)
- **Driver bundle:** `bench-salvage-phaseWS-6c-DSPy-2-complete-trio-and-ab-harness-driver`
- **Commits audited:** `a511012` (lenses + build_trio), `c83dc48` (ab_harness), `69b3505` (tests), `c588904` (session log) — range `17f9f70..HEAD` (HEAD = `c588904`)
- **Spec(s) read against:** `.devloop/prompts/bench-salvage_phaseWS-6c-DSPy-2_complete-trio-and-ab-harness_driver.md` (§2 deliverables, §4 guardrails, §5 acceptance A1–A8); the seam `lithrim_bench/runtime/council/__init__.py:43-49`; `lithrim_bench/runtime/council/compliance_council.py` `_TIER1_OWNERS:232`; `taxonomy/taxonomy_snapshot.json`; the role prompts `council_roles/{risk,policy,faithfulness}_judge.txt`; the prior critique `critique-bench-salvage-phaseWS-6c-DSPy-2026-06-02.md` (house style); STREAM `.devloop/state/STREAM_bench-salvage.md`
- **Critique mode:** `fresh-critic` (separate session, no prior implementation context; adversarial from-source re-derivation)
- **Date:** 2026-06-03
- **Reviewer:** `critic (fresh-critic session, cold read)`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The three load-bearing HARD-GATE proofs hold under independent from-source verification. (1) **Lens owner-consistency is exact:** every code in all three lenses is in `KNOWN_TAXONOMY_CODES` (re-derived from the snapshot tiers — 0 off-snapshot), and every Tier-1 code in the new lenses (`FABRICATED_CONSENT`, `PHI_DISCLOSURE_PRE_VERIFICATION`, `VALUE_MISMATCH`, `MISSING_ALLERGY`) is owner-resident for its role in `_TIER1_OWNERS`. (2) **Consensus IP is byte-identical:** `git diff 17f9f70 HEAD -- compliance_council.py` is EMPTY (A5). (3) **Scope is clean:** the range is exactly the 5 DSPy-2 files + the session log; the 3 staged paper files were NOT swept and remain staged; no concurrent-session file appears. The 24 offline tests pass; the lens/owner guard tests fail loudly on drift; default-deps import isolation and ruff hold. The findings below are all NON-BLOCKING or OPEN-QUESTION: the live A/B arm is **unexercised** (correctly disclosed by the executor, but the session log + one docstring contain over-readable phrasings to tighten), `load_role_prompt` does NOT `.strip()` where the prompt-council does (a real but whitespace-only arm asymmetry contradicting a "SAME prompt text" docstring claim), the new seams **collide with already-assigned IDs S-BS-34/S-BS-35** (must be renumbered S-BS-42/S-BS-43 at close), and the session-log "5 files" close-diff figure is factually 6.

---

## 1. Surface fidelity

> Do the deliverables match driver §2 exactly (the two lenses + `LENS_BY_ROLE` in `judge_metric.py`; `build_trio` in `judges_dspy.py`; `ab_harness.py` with the stated diff schema; the two test files)?

| Spec definition (driver §2) | Implementation | Match? | Severity |
|---|---|---|---|
| D1 `POLICY_JUDGE_LENS` + `FAITHFULNESS_JUDGE_LENS` (`frozenset`s, mirror `RISK_JUDGE_LENS`) | `judge_metric.py:65-105` two `frozenset`s | YES | — |
| D1 `LENS_BY_ROLE = {risk,policy,faithfulness → lens}` | `judge_metric.py:107-112`; keys verified `== V2_ROLES` at runtime | YES | — |
| D1 module docstring: off-snapshot lens code surfaced (S-BS-12), not silently scored | `judge_metric.py:19-41` (docstring note); guard test enforces | YES | — |
| D2 `ab_harness.py` prompt-vs-DSPy with verdict-agreement / per-judge code-set agreement / None-aware calibration / per-arm `score_judge` | `ab_harness.py` `diff_case:78`, `_calibration_deltas:112`, `_score_both_arms:129`, `run_offline_structural:160`, `run_live:200` | YES | — |
| D2 two modes (offline-structural `$0` deterministic + live cost-confirmed); offline-first | `run_offline_structural` (no network) + `run_live` (raises without `confirm_cost`) | YES | — |
| D2 NO new grade entrypoint / no `run_eval`/`grade` import | `ab_harness.py` imports only `judge_metric` at top; `compliance_council`/`judges_dspy` lazy-imported in-fn | YES | — |
| D3 `build_trio()` reading `council_roles/*.txt`, no `Judge`/signature/`evaluate_dspy` change | `judges_dspy.py` `load_role_prompt:110`, `build_trio:310`; diff to `Judge`/`evaluate_dspy`/signature = none (additions only) | YES | — |
| D4 two test files (trio + A/B), offline, `importorskip` | `tests/test_trio_dspy.py` (17 tests), `tests/test_ab_harness.py` (7 tests) | YES | — |
| D5 session log | `session-…WS-6c-DSPy-2-2026-06-03.json` | YES (content caveats → Q2/Q4) | — |

The diff-record schema in `run_offline_structural` (`ab_harness.py:172-184`) matches plan-review #2 verbatim: `{mode, note, n, verdict_agreement_pct, per_case[…], per_role_score, calibration}`, with `per_case` rows of `{case_id, prompt_verdict, dspy_verdict, verdict_agree, per_role:{prompt_codes, dspy_codes, codes_agree, prompt_conf, dspy_conf, conf_delta}}` (`diff_case:78-101`).

**Findings:**

- `[NON-BLOCKING]` **`load_role_prompt` does not `.strip()` the role-prompt text, but its docstring claims it returns "the SAME prompt text the live prompt-council loads via `_load_role_prompts`."** CONFIRMED: `judges_dspy.py:117` returns `path.read_text(encoding="utf-8")` (no strip); the prompt-council it claims parity with applies `.strip()` at `compliance_council.py:527` (`prompts[role_file.stem] = role_file.read_text(...).strip()`). The texts therefore differ by leading/trailing whitespace. This is verdict-neutral for the offline tests (which inject predictors, never reading `role_prompt`), and whitespace-only for the live arm, but (a) the docstring's "SAME prompt text" is an over-claim, and (b) it introduces a (tiny) asymmetry into the not-yet-run live A/B — the comparison's stated purpose is "compares like prompts" (`judges_dspy.py:56-58`). Recommended disposition: `return path.read_text(...).strip()` in `load_role_prompt`, or correct the docstring to "the same prompt FILE… (raw text; the prompt-council strips it)". Not blocking — no shipped behavior depends on it and the live arm is unexercised.

No other surface drift. All public symbols (`POLICY_JUDGE_LENS`, `FAITHFULNESS_JUDGE_LENS`, `LENS_BY_ROLE`, `load_role_prompt`, `build_trio`, `run_offline_structural`, `run_live`, `diff_case`, `ArmCaseResult`, `OFFLINE_NOTE`) match the spec's intent; `build_trio` + the 2-test-file split were blessed at plan-review (driver §2 D3 "optional helper", §3).

---

## 2. Behavioral fidelity

> Three required picks: (a) the owner-consistency guard fails loudly; (b) the policy `confidence=None` round-trip is never coerced; (c) A5 consensus byte-identical.

### Behavior 1 (a): owner-consistency guard fails loudly on out-of-snapshot OR non-owner Tier-1 lens code

- **Spec assertion:** driver §5 A2 "each lens ⊆ `KNOWN_TAXONOMY_CODES` and is **consistent with `_TIER1_OWNERS:232`** for its Tier-1 codes; any lens code outside the snapshot is surfaced (S-BS-12), not silently scored"; §2 D4(d) "a **lens↔snapshot↔owner guard**".
- **Test:** `test_trio_dspy.py:306-311` (`test_every_lens_code_is_in_the_taxonomy_snapshot`) asserts per role `set(lens) - KNOWN_TAXONOMY_CODES` is empty, failing with the offending codes named; `:314-324` (`test_every_tier1_lens_code_is_owner_resident`) asserts, for every lens code `in TIER_1_NEVER_EVENTS`, `role in _TIER1_OWNERS[code]`, failing if not; `:327-331` asserts the 4 invited-but-unowned Tier-1 codes are absent from the faithfulness lens.
- **Implementation:** lenses at `judge_metric.py:65-105`; `KNOWN_TAXONOMY_CODES`/`TIER_1_NEVER_EVENTS`/`_TIER1_OWNERS` imported from `compliance_council` (the live tables, not a copy) at `test_trio_dspy.py:38-42`.
- **Chain closes?** YES. The guard reads the real runtime tables, so it would fire on any future lens or owner-table drift. Independently re-derived (load-bearing check below): 0 off-snapshot codes; all 4 new-lens Tier-1 codes owner-resident.

### Behavior 2 (b): policy_judge `confidence=None` round-trips, never coerced

- **Spec assertion:** driver §5 A1 "incl. the `policy_judge` (Mistral) `confidence=None` round-trip, **never coerced**"; seam `__init__.py:46` "None for Mistral (no logprobs) — never coerce to 1.0/0.0".
- **Test:** `test_trio_dspy.py:123-135` (`test_policy_judge_none_confidence_round_trips_uncoerced`) builds the trio with `policy_judge` predictor `confidence=None`, asserts `seams["policy_judge"]["confidence"] is None` AND `seams["risk_judge"]["confidence"] == 0.9` (proving the `None` is the Mistral path, not a global drop).
- **Implementation:** `build_trio(predictors=…)` → `Judge.forward` → `extract_verdict_confidence`. The offline fixture `_raw_for_conf(None)` returns `{"choices":[{"logprobs":None}]}` (`test_trio_dspy.py:57-63`), the no-logprobs shape `extract_verdict_confidence` maps to `None`. The confidence is sourced from the response payload, not a self-report field (consistent with DSPy-1's D2).
- **Chain closes?** YES. Ran the suite: `test_policy_judge_none_confidence_round_trips_uncoerced` passes. The `run_live` arm reads `_get(prompt_seams.get(role,{}), "confidence")` / `_get(dspy_seams.get(role,{}), "confidence")` (`ab_harness.py`), and the diff/calibration are explicitly `None`-aware (`conf_delta = None if p_conf is None or d_conf is None`, `diff_case:96`; `_calibration_deltas` skips `None`, `:114-117`) — the `None` path survives end-to-end through the harness, asserted by `test_ab_harness.py:162-171`.

### Behavior 3 (c): A5 consensus byte-identical (independently confirmed)

- **Spec assertion:** driver §5 A5 "`_apply_consensus` / the v2 combine / `extract_verdict_confidence` / the tables byte-identical to the DSPy-1 tip (diff-vs-tip = zero logic delta)".
- **Independent confirmation:** `git diff 17f9f70 HEAD -- lithrim_bench/runtime/council/compliance_council.py` returns **EMPTY** (exit 0, no output). `compliance_council.py` is byte-identical across the whole range. The full `git diff 17f9f70 HEAD --name-status` shows `compliance_council.py` is NOT touched (only `ab_harness.py` A, `judge_metric.py` M, `judges_dspy.py` M, the 2 test files A, session log A). `__init__.py` (the seam doc) is also not in the range.
- **Chain closes?** YES. A5 holds by direct byte-diff, not by self-report. The `judge_metric.py`/`judges_dspy.py` diffs are pure additions (no `-` lines outside the `---` file headers — re-read in the full diff). DSPy strictly above the seam: `evaluate_dspy`/`Judge`/the signature are unchanged; `run_live` calls `council._apply_consensus(...)` / `evaluate_dspy(...)` UNCHANGED (`ab_harness.py` `_arm_result_from_seams:71`, `run_live`).

**Findings:**

- `[NON-BLOCKING]` **The lower-bound-precision claim is sound AND tested, but its accompanying "the A/B comparison stays valid… lens applied symmetrically to both arms" is only proven for the offline path; it is asserted, not measured, for the (unexercised) live path.** CONFIRMED at the scoring level: `_score_both_arms` (`ab_harness.py:129-148`) resolves `lens = LENS_BY_ROLE.get(role)` ONCE per role and applies the identical `lens` to every `arm` in the loop, so the lens is literally symmetric across arms by construction — the symmetry argument has no hole at the metric level. The out-of-lens-FP semantics are real: `_score_one` (`judge_metric.py:136-152`) computes `truth = expected & lens`, `fp = raised - truth`, so a corroborating raise of another owner's code (even when correct, i.e. `in expected`) scores as FP — this is exercised by `test_faithfulness_lens_in_scope_perfect_but_corroboration_is_out_of_lens_fp` (`test_trio_dspy.py:269-280`, `fp == 1`). The one residual: the lens is symmetric, but the *inputs* to the two arms are not perfectly symmetric in the live path (the `.strip()` divergence above), so "the A/B comparison stays valid" is contingent on the live arm being run with like inputs — and it has not been run. NON-BLOCKING because the metric-level symmetry is the load-bearing part and it holds; the input-asymmetry is the Q1 whitespace finding.

---

## 3. Out-of-scope intrusion

> Anything in the diff beyond §2 deliverables? Any concurrent-session file staged or committed? Were the 3 staged paper files swept?

Driver §2 deliverables: (D1) `judge_metric.py` lenses + map; (D2) `ab_harness.py`; (D3) `judges_dspy.py` `build_trio` helper; (D4) `tests/`; (D5) session log.

`git diff 17f9f70 HEAD --name-only`:

```
.devloop/sessions/session-bench-salvage-phaseWS-6c-DSPy-2-2026-06-03.json   (D5)
lithrim_bench/runtime/council/ab_harness.py                                 (D2)
lithrim_bench/runtime/council/judge_metric.py                               (D1)
lithrim_bench/runtime/council/judges_dspy.py                                (D3)
lithrim_bench/runtime/council/tests/test_ab_harness.py                      (D4)
lithrim_bench/runtime/council/tests/test_trio_dspy.py                       (D4)
```

Every diffed file maps to a deliverable. Independently confirmed against §4 guardrails:

- **Paper files NOT swept:** `git log 17f9f70..HEAD --name-only --pretty=format: -- docs/PAPER_OUTLINE.md 'docs/research/*semantic*'` returns EMPTY (no commit in the range touched them). `git status --porcelain` shows all 3 still staged (`M  docs/PAPER_OUTLINE.md`, `A  docs/research/REPORT_semantic_moat_proof_2026-06-02.md`, `A  docs/research/SYNTHESIS_clinical_ai_governance_semantic_stability_2026-06-02.md`) — column-1 status = still in the index, intact. The dirty-tree landmine was avoided.
- **No concurrent-session file in the range:** none of `lithrim_bench/verification/*`, `lithrim_bench/harness/grounding.py`, `apps/*`, `docs/specs/SPEC_CALIBRATION_TRAINER.md`, `docs/research/RUN_*`, `tests/verification/test_dosage_floor.py` appears in `--name-only`. They remain uncommitted in the worktree (`git status` shows them `M`/`??`).
- **No consensus-math / grade-wire / persistence / backend edit:** `compliance_council.py` byte-identical (Q2 c); `grade.py`/`run_eval.py`/`report.py`/`harness/*` not in range; `ab_harness.py` imports neither grade nor run_eval (re-read top-of-file + the two lazy in-fn imports are `ComplianceCouncil` and `build_trio`/`evaluate_dspy` only).
- **No pyproject change** (A7) — not in range.

**Findings:**

- No intrusion detected. All diffed files map to deliverables; the 3 staged paper files were not swept; no concurrent-session file was staged or committed.

---

## 4. Spec ambiguity / judgment calls surfaced

### Ambiguity 1: lens (A) owner-consistent vs lens (B) prompt-faithful (RESOLVED at plan-review)

- **Spec text:** driver §3 dec#1 "Resolve `POLICY_JUDGE_LENS` + `FAITHFULNESS_JUDGE_LENS` exactly… cross-checked against `_TIER1_OWNERS:232`… Surface any lens code NOT in the snapshot."
- **Implementation decided:** lens (A) — exclude the 4 Tier-1 codes `faithfulness_judge.txt` invites (`WRONG_DOSAGE:13`, `FABRICATED_ALLERGY:16`, `MISSED_ESCALATION:26`, `SEVERITY_ESCALATION:27`) but does NOT own, so the owner guard holds; consequence: corroborating raises score as out-of-lens FPs → per-judge precision is a documented LOWER BOUND (`judge_metric.py:24-37` docstring; `test_…corroboration_is_out_of_lens_fp`).
- **Recommended resolution:** ACCEPT (user-approved at plan-review, `session…json:24-29`). Correct against `_TIER1_OWNERS` and the prompt text. The co-raise-aware lens is banked for DSPy-3.

### Ambiguity 2: PHI_DISCLOSURE_PRE_VERIFICATION in the policy lens though the prompt never names the code string

- **Spec text:** plan-review seed "policy ≈ `{FABRICATED_CONSENT, …}`"; A2 "consistent with `_TIER1_OWNERS`".
- **Implementation decided:** keep `PHI_DISCLOSURE_PRE_VERIFICATION` in `POLICY_JUDGE_LENS` because policy is its **sole** Tier-1 owner and it is in-snapshot, even though `policy_judge.txt` describes the PHI-pre-verification domain (`:8-11,17`) but never writes the literal code string. CONFIRMED: the string `PHI_DISCLOSURE_PRE_VERIFICATION` does not appear anywhere in `policy_judge.txt` (grep returned no hit); the only code named literally is `FABRICATED_CONSENT` (`policy_judge.txt:19`).
- **Why it is defensible:** the lens is the role's *ownership* scope, not the prompt's verbatim-named codes; dropping a sole-owned Tier-1 code from its owner's lens would mis-score the one role that can one-strike it. The choice is owner-consistent.
- **Honesty caveat (load-bearing check below):** the executor frames the resulting under-raise as "a measurable recall gap the live A/B surfaces" (docstring `judge_metric.py:64-69`; session log `s_bs_12_surfacing`, seam S-BS-34). **Nothing has measured it** — the live A/B is unexercised. The framing is forward-looking and is hedged with "likely UNDER-raises", but "the A/B surfaces" is present-tense for a run that has not happened. Recommended resolution: ACCEPT the lens choice; tighten the wording to "a recall gap a future live A/B would surface". OPEN-QUESTION for the spec author: should a sole-owned-but-prompt-unnamed code be in the lens, or should the prompt be edited to name it first (the S-BS-34/renumbered follow-up)?

### Ambiguity 3: offline-structural output reuse

- **Spec text:** driver §2 D2 "offline-structural … exercises the diff + scoring logic"; §5 A3 "offline-structural mode is deterministic ($0)".
- **Implementation decided:** the offline mode shares `_apply_consensus` across both arms on hand-authored seams, so it carries "zero real prompt-vs-DSPy signal" — explicitly documented in `OFFLINE_NOTE` (`ab_harness.py:38-41`), the `run_offline_structural` docstring (`:160-167`), the module docstring (`:11-22`), and asserted by `test_mode_and_note_are_surfaced` (`test_ab_harness.py:107-110`).
- **Recommended resolution:** ACCEPT. This is exemplary offline-honesty in the *code*; the residual risk is only in the session-log/diagnostic phrasing (see findings).

**Findings:**

- `[OPEN-QUESTION]` Lens (A) owner-consistent choice — ACCEPT (plan-review-resolved); the lower-bound precision is documented and tested. No code action.
- `[OPEN-QUESTION]` PHI inclusion despite prompt not naming the code — ACCEPT the lens; tighten the "the live A/B surfaces" present-tense to conditional; decide prompt-edit-vs-lens at the (renumbered) follow-up seam.
- `[NON-BLOCKING]` **Seam-numbering collision (load-bearing check).** CONFIRMED: the session log opens `S-BS-34` (`session…json:128`) and `S-BS-35` (`:137`), but `.devloop/state/STREAM_bench-salvage.md` already assigns **S-BS-34** ("`ruff check .` is not clean — 865 pre-existing errors", open, STREAM line 106) and **S-BS-35** ("A5 live-evidence hygiene + grade-wire real-council in-suite coverage", CLOSED 2026-06-02, line 107). The highest assigned ID in the STREAM is **S-BS-41**. The two new seams must be renumbered **S-BS-42** (policy PHI prompt-naming) and **S-BS-43** (co-raise-aware lens / lower-bound) at close. The monitor's belief is CONFIRMED. Disposition: monitor renumbers in the STREAM at close; the session log's IDs are stale.
- `[NON-BLOCKING]` **Session-log close-diff figure is off by one and the cited range is stale.** The log asserts "git diff 17f9f70 HEAD --stat = exactly 5 files" (acceptance A8, `session…json:111`; A5 `:96`), but the actual range contains **6** files (the 5 code/test files **+ the session log itself**, committed at `c588904`). The `next_session_hint` cites range `17f9f70..69b3505` (`:154`) — internally consistent with "5 files" (pre-log tip `69b3505`) but inconsistent with the real HEAD `c588904`. INFERRED cause: the executor wrote the "5 files" claim before committing the log. Verdict-neutral and the *code* scope is correct, but it is a factual imprecision in a self-report. Disposition: accept; note that the load-bearing scope claim (only DSPy-2 files, no paper sweep) is independently TRUE.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 1 (`load_role_prompt` no-strip vs "SAME text" docstring) | 0 |
| 2 | Behavioral fidelity | 0 | 1 (symmetry proven offline, asserted-not-measured live) | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity / judgment calls | 0 | 2 (seam-numbering collision; "5 files" off-by-one) | 2 (lens A; PHI inclusion) |

**Total BLOCKING: 0** → cycle MAY close.

Net distinct findings: 6 (4 NON-BLOCKING, 2 OPEN-QUESTION). None block closure. The seam-numbering collision and the "5 files" figure are bookkeeping; the `load_role_prompt` strip + the symmetry caveat are minor fidelity/wording items on an unexercised path.

---

## Required actions (if any)

No BLOCKING findings. NON-BLOCKING / OPEN-QUESTION dispositions:

1. **Finding:** New seams collide with assigned S-BS-34 / S-BS-35.
   **Proposed disposition:** monitor renumbers to **S-BS-42** (policy PHI prompt-naming, INFERRED, low) + **S-BS-43** (co-raise-aware lens / lower-bound precision, CONFIRMED, low) in `STREAM_bench-salvage.md` at close. **Owner:** monitor.
2. **Finding:** `load_role_prompt` does not `.strip()`; docstring claims "SAME prompt text" as the prompt-council (which strips).
   **Proposed disposition:** one-line fix (`.strip()`) or docstring correction in a follow-up; gate it before the live A/B is run so the comparison feeds like inputs. **Owner:** executor (DSPy-2-live or DSPy-3).
3. **Finding:** Session log over-reads the unexercised live A/B ("the A/B surfaces"; "5 files"; stale range).
   **Proposed disposition:** monitor softens the present-tense phrasings to conditional and corrects the file count/range at close. The cycle's CAVEAT ("substrate test-correct but UNVALIDATED against real LLM behavior") is already explicit in `report`/`next_session_hint` — keep it. **Owner:** monitor/spec author.
4. **Finding:** Lens (A) lower-bound precision (OPEN-QUESTION) + PHI inclusion (OPEN-QUESTION).
   **Proposed disposition:** ACCEPT both (plan-review-resolved + owner-consistent); the co-raise-aware lens and the prompt-naming edit are the two renumbered follow-up seams. **Owner:** spec author at DSPy-3.

---

## Load-bearing checks (explicit yes/no for the monitor)

- **Lens owner-consistency holds?** **YES.** Re-derived from `taxonomy_snapshot.json` tiers: all 18 distinct lens codes are in `KNOWN_TAXONOMY_CODES` (0 off-snapshot). New-lens Tier-1 codes and their `_TIER1_OWNERS` owners: `FABRICATED_CONSENT` → `{behavior_judge, policy_judge, source_message_judge}` (policy ✓), `PHI_DISCLOSURE_PRE_VERIFICATION` → `{policy_judge}` (sole, ✓), `VALUE_MISMATCH` → `{behavior_judge, faithfulness_judge}` (✓), `MISSING_ALLERGY` → `{behavior_judge, faithfulness_judge, source_message_judge}` (✓). The remaining FAITHFULNESS lens codes are all Tier-2/Tier-3 (no Tier-1 owner constraint), and the 4 invited-but-unowned Tier-1 codes are correctly excluded.
- **Consensus byte-identical?** **YES.** `git diff 17f9f70 HEAD -- compliance_council.py` is EMPTY; the file is not in the range.
- **Offline honesty sufficient?** **YES in code, MOSTLY in the log.** The code is exemplary: `OFFLINE_NOTE` + three docstrings + an assertion forbid reading offline output as an A/B result; schema names like `verdict_agreement_pct` are scoped by the surfaced `note`. The only over-reads are in the session log/diagnostics ("the A/B surfaces" present-tense; the "5 files" miscount) — NON-BLOCKING, monitor to tighten. The executor correctly told the gate the live arm is unexercised and the comparison is unproven.
- **Seam-numbering collision confirmed?** **YES.** S-BS-34 and S-BS-35 are already assigned (S-BS-34 open, S-BS-35 closed) in `STREAM_bench-salvage.md`; next free IDs are S-BS-42/S-BS-43.

---

## Critic discipline self-check (fresh-critic mode)

- [x] Read the spec (driver §2/§4/§5, the seam, `_TIER1_OWNERS`, the role prompts, the snapshot) and re-derived the lens cross-check from source BEFORE reading the executor's acceptance verdicts.
- [x] Read the diff via `git diff`/`git log` against commits, not via the executor's summary; ran the offline tests (`24 passed`) and the import-isolation/ruff checks myself.
- [x] Each finding cites both spec file:line and implementation file:line (or command output).
- [x] Did NOT edit any code, spec, or driver (only this critique file was written).
- [x] Did NOT confer with monitor or executor before writing the verdict. (This is a genuinely separate session with no prior implementation context; I was told the live arm is unexercised — that is the cycle's disclosed posture, not a producer claim, and I treated all session-log assertions as claims to verify.)

All five hold. This is a clean-room fresh-critic pass.

---

## Appendix: commits audited

```
c588904 docs(bench-salvage): WS-6c-DSPy-2 session log — trio lenses + A/B harness (offline; live deferred)
69b3505 test(council-dspy): trio seam + 3-judge consensus oracle + lens/owner guard + A/B diff (offline)
c83dc48 feat(council-dspy): prompt-vs-DSPy A/B harness (offline-structural + cost-gated live)
a511012 feat(council-dspy): policy + faithfulness lenses + LENS_BY_ROLE + build_trio (snapshot/owner-checked)
(base: 17f9f70 docs(bench-salvage): author WS-6c-DSPy-2 driver)
```

## Appendix: files changed

```
A  .devloop/sessions/session-bench-salvage-phaseWS-6c-DSPy-2-2026-06-03.json   155 ++
A  lithrim_bench/runtime/council/ab_harness.py                                 283 ++
M  lithrim_bench/runtime/council/judge_metric.py                                72 ++
M  lithrim_bench/runtime/council/judges_dspy.py                                 59 ++
A  lithrim_bench/runtime/council/tests/test_ab_harness.py                      176 ++
A  lithrim_bench/runtime/council/tests/test_trio_dspy.py                       331 ++
6 files changed, 1076 insertions(+)

A5 control: git diff 17f9f70 HEAD -- compliance_council.py = EMPTY (byte-identical).
Offline tests: 24 passed (test_trio_dspy 17 + test_ab_harness 7) on debuglithrim.
Import isolation: import lithrim_bench / ab_harness / judge_metric pull no openai/dspy (default python3). ruff: All checks passed (5 files).
```
