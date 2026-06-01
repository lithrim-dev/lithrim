# Spec-Adherence Critique — `bench-salvage` phase `WS-6c-DSPy`

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-6c-DSPy`
- **Driver bundle:** `bench-salvage-phaseWS-6c-DSPy-judge-rebuild-driver`
- **Commits audited:** `95174c0` (judges_dspy), `997f93a` (judge_metric), `c402010` (tests), `4e1d3cc` (session log) — range `f90d299..HEAD`
- **Spec(s) read against:** `docs/specs/RECOMPOSITION_PLAN_ws6.md` (§3/§6/§7/§Ratification-Q3); `lithrim_bench/runtime/council/__init__.py:38-54` (the seam); driver §2 deliverables + §5 acceptance; `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` frozen-contract rule (via RECOMPOSITION_PLAN:18)
- **Critique mode:** `fresh-critic` (user-elected fresh-critic path on a HARD GATE) — see the discipline self-check for an honesty caveat on context independence
- **Date:** 2026-06-02
- **Reviewer:** `critic (fresh-critic kickoff, continued from the monitor session)`

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The load-bearing HARD-GATE proofs all hold under independent from-source verification: the DSPy judge emits a per-judge dict that satisfies every verdict-determining read of the UNCHANGED `_apply_consensus` (A1), the ported consensus IP is byte-identical to the WS-6c tip including the seam doc (A4, `git diff 6bae3c0..HEAD` = 0 across the full ported set), nothing is wired into the grade seam (A6, the new modules are imported only by their own tests), and confidence is sourced from response logprobs via the ported `extract_verdict_confidence` with no self-report field (D2, the named focus, live-validated at 0.999999 and None-tolerant offline). Four NON-BLOCKING / OPEN-QUESTION findings are recorded; none block closure, and three of them concern criterion/seam-doc wording or evidence reproducibility rather than the shipped behavior.

---

## 1. Surface fidelity

> Does the emitted per-judge dict match the seam exactly (every key the consumer reads, no extra/renamed keys)?

The seam contract (`runtime/council/__init__.py:43-49`) documents 5 keys: `{model, decision, confidence, findings:[{taxonomy_code, evidence_spans}], errors}`. `Judge.forward` (`judges_dspy.py:281-287`) returns exactly those 5 keys.

Key-by-key against what `_apply_consensus` actually reads (independently enumerated across the whole function body, `compliance_council.py:1853-2398`):

| Seam key | `_apply_consensus` read-site | Provided by `Judge.forward`? | Match? |
|---|---|---|---|
| `errors` (required, subscript) | `:1879` `result["errors"]` (the `valid` filter) | `:286` always `[]` or `[msg]` | YES |
| `decision` (required, subscript) | `:1986` `result["decision"]` | `:283` normalized to the 3-value set (`_norm_decision:114`) | YES |
| `findings` | `:1899` `result.get("findings")` | `:285` `_validate_findings` output | YES |
| `findings[].taxonomy_code` | `:1911` `f.get("taxonomy_code") or f.get("type")` | `:145` emits `taxonomy_code` | YES |
| `findings[].evidence_spans` | `:1914` presence-only (`len(spans) > 0`) | `:145` non-empty span list | YES |
| `confidence` (None-tolerant) | `:1979` `result.get("confidence")`, coerced `float|None` | `:284` from `extract_verdict_confidence`, never coerced | YES |
| `model` | `:1985` `result.get("model")` | `:282` `self.role` | YES |

The inner `evidence_spans` shape is opaque to consensus (it is presence-checked only, never indexed for `text`/`quote`), so the impl's `{quote, turn_ids}` span (`judges_dspy.py:119-122`) is conformant; it also matches the council's own span convention (the S29 synthetic span at `compliance_council.py:1965` is `{quote, turn_ids, source}`).

**Findings:**

- `[NON-BLOCKING / OPEN-QUESTION]` **The documented seam under-specifies one key the consumer reads: `citations_used`.** In the findings-first branch, `_apply_consensus` reads `result.get("citations_used")` (`compliance_council.py:1942`) to perform the S29 citation-to-evidence-span merge. This key is NOT in the documented 5-key seam (`__init__.py:43-49`) and is NOT emitted by `Judge.forward` (`judges_dspy.py:281-287`). It is verdict-neutral (the merge is additive — "synthetic spans augment, never replace, judge spans", `compliance_council.py:1958`; it affects only the downstream chunk_id linkback in `pipeline/stages.py`, not any tier/owner/verdict path) and inert this cycle (no grade-wire, no KB, S-BS-31 inert). The session-log A1 "key-by-key vs `_apply_consensus` reads" proof maps the 5 documented keys but does not note `citations_used`. Not blocking: the seam as documented is the verdict-bearing contract and the DSPy judge conforms to it. Recommended disposition for the seam author: document `citations_used` as a deliberate downstream-enrichment-only omission in `__init__.py`, and flag that the DSPy judge layer must emit it when WS-6c-AGENTIC wires KB / HIPAA-transcript cases (otherwise a DSPy judge's regulatory citations, which the signature currently routes into the free-text `reason` field at `judges_dspy.py:195`, never enter the chunk_id linkback stream).

---

## 2. Behavioral fidelity

> Pick 3 key spec-claimed behaviors. For each: trace spec assertion -> test that exercises it -> implementation site.

### Behavior 1: the DSPy judge emits the seam, with a `confidence=None` round-trip that is never coerced (A1)

- **Spec assertion:** `__init__.py:46` "`confidence`: float | None ... None for Mistral (no logprobs) — never coerce to 1.0/0.0"; driver §5 A1 (`driver:135`).
- **Test:** `test_judges_dspy.py:73-87` (asserts `set(seam) == {5 keys}`, finding shape, `confidence == 0.92`) and `:90-93` (`confidence is None` when the response carries no logprobs), both routed through the real `Judge.forward`.
- **Implementation:** `judges_dspy.py:264-290` (`forward`), confidence at `:278/:284` via `extract_verdict_confidence(_raw_response_for(...))`; the offline `_raw_for_conf(None)` fixture (`test_judges_dspy.py:42-43`) returns `{"choices":[{"logprobs":None}]}`, which `extract_verdict_confidence` (`compliance_council.py:430-433`) maps to `None`.
- **Chain closes?** YES.

### Behavior 2: Tier-1 owner one-strike rejects, through the UNCHANGED consensus (A3 + the §6 hybrid)

- **Spec assertion:** RECOMPOSITION_PLAN §5:148 "Tier-1 one-strike (owner OR >=2 evidence-judges)"; §6:197 "the ported `_apply_consensus` takes exactly the ... per-judge dict shape ... DSPy owns the prompts; the tier math stays ported".
- **Test:** `test_judges_dspy.py:132-141` (`risk_judge` rejects `FABRICATED_ALLERGY` -> `decision == "reject"`, `tier1_triggered == ["FABRICATED_ALLERGY"]`, `artifact_verdict == "BLOCK"`), fed through `evaluate_dspy`.
- **Implementation:** `judges_dspy.py:298-319` (`evaluate_dspy` marshals the per-judge list and calls `council._apply_consensus(results, gate_mode=gate_mode)` at `:319`); the consensus itself is the ported, byte-identical code (A4). The `council` fixture is the real `ComplianceCouncil` from the pre-existing WS-6c `conftest.py:21-25`.
- **Chain closes?** YES. The same oracle is exercised by the pre-existing `test_consensus.py` against hand-built dicts; the DSPy path reproduces it via `Judge.forward`, which is the point of A3.

### Behavior 3: the judge metric's hard-accept scores findings against the recipe label within the role's lens (A2)

- **Spec assertion:** driver §2 D2 (`driver:91`) "score a judge's `findings` against ... `expected_safety_flags` (recipe=label) -> precision/recall + a hard-accept (0 false-positive on clean negatives)"; the lens is the role's declared scope, `council_roles/risk_judge.txt:16-25` (CODES YOU MAY / MAY NOT RAISE).
- **Test:** `test_judge_metric.py:40-76` (perfect in-lens judge accepted; clean-negative FP, out-of-lens raise, and missed label each fail the gate).
- **Implementation:** `judge_metric.py:31-39` (`RISK_JUDGE_LENS`) is an exact set-match to `risk_judge.txt:17-21` ("CODES YOU MAY RAISE": MISSED_ESCALATION, SEVERITY_ESCALATION, WRONG_DOSAGE, MEDICATION_NOT_IN_TRANSCRIPT, FABRICATED_ALLERGY), and correctly excludes FABRICATED_HISTORY / HALLUCINATED_DETAIL per `risk_judge.txt:24-25`; scored by `score_judge:91-141` (`accepted = fp_total == 0 and fn_total == 0`, `:132`).
- **Chain closes?** YES for the metric mechanics. See the A2 evidence finding below for the pack-data-source caveat.

**Findings:**

- `[NON-BLOCKING]` **A2's committed test scores against synthetic recipe=label fixtures, not the real pack files; the session-log "vs proof_case.jsonl" pack score is an ad-hoc, non-reproducible run.** `test_judge_metric.py:21-25` defines 3 inline `CASES`; `examples/proof_case.jsonl` (which does carry 1 WRONG_DOSAGE case) is not referenced by any committed council test (verified by grep). The session log asserts "Offline pack score vs `examples/proof_case.jsonl`" (acceptance A2, `session...json:81`; diagnostic_stats, `:117`), which is not reproducible from a committed artifact. A2 is nonetheless SATISFIED: the live smoke on a real `scribe_v1` pack case (`bench_scribe_v1_dosage_drift_84ee8f1e7442` -> reject matching recipe=label) is recorded (`session...json:118`), and the metric mechanics are tested on by-construction recipe=label fixtures. Recommended disposition: commit the proof_case.jsonl score as a small reproducible script/test, or soften the session-log claim to "synthetic recipe=label fixtures + one live pack datapoint."

---

## 3. Out-of-scope intrusion

> Read the diff against the driver's deliverables list. Anything not in the list is intrusion.

Driver §2 deliverables (verbatim intent): (1) `judges_dspy.py` DSPy judge layer; (2) `judge_metric.py` bench-accept metric; (3) the §6 hybrid wiring inside `judges_dspy.py` (`evaluate_dspy`, not a new grade entrypoint); (4) `runtime/council/tests/` offline tests (a-d); (5) the session log.

`git diff --name-status f90d299..HEAD` shows exactly:

```
A  .devloop/sessions/session-bench-salvage-phaseWS-6c-DSPy-2026-06-02.json   (D5)
A  lithrim_bench/runtime/council/judge_metric.py                             (D2)
A  lithrim_bench/runtime/council/judges_dspy.py                              (D1 + D3)
A  lithrim_bench/runtime/council/tests/test_judge_metric.py                  (D4)
A  lithrim_bench/runtime/council/tests/test_judges_dspy.py                   (D4)
```

Every diffed file maps to a deliverable. Independently confirmed against the §4 guardrails:

- **No consensus-math edit (A4):** `git diff 6bae3c0..HEAD` over the full ported set (`compliance_council.py`, `safety_flags.py`, `settings.py`, `llm_provider.py`, `__init__.py`, `phi_redaction.py`, `council_roles/`) = 0 lines. The seam doc `__init__.py` is itself byte-identical (no self-serving edit to make the contract fit the impl).
- **No grade-seam wire (A6):** `grade.py` / `run_eval.py` / `report.py` not in the range; `judges_dspy`/`evaluate_dspy`/`judge_metric` are imported only by their own two tests (the lone external grep hit, `scripts/calibrate_judges.py:118`, is a pre-existing local variable `judge_metrics`, not an import of the new module).
- **No worktree import (A8):** no `council_v2` / `council_dspy` / `dspy_council_smoke` / `agent-adefc36309f77ed1b` reference anywhere in `lithrim_bench/`.
- **No `_TIER1_OWNERS` hand-edit / S-BS-31 touch:** covered by the A4 zero-delta.

No intrusion detected. All diffed files map to deliverables.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: the seam omits `citations_used`

Covered as the Q1 finding above. Implicit decision: the DSPy judge implements the documented 5-key seam and routes citations into free-text `reason`. Question for the seam author: is `citations_used` a permanent downstream-only omission, or a key the DSPy judge must emit once KB is wired (WS-6c-AGENTIC)? Recommended resolution: document the omission now; revisit at AGENTIC.

### Ambiguity 2: A3 lists "NKA" among consensus-oracle scenarios, but NKA is a prompt-level behavior

- **Spec text:** driver §5 A3 (`driver:137`) "DSPy judges + the ported `_apply_consensus` reproduce the WS-6c offline oracle verdicts (Tier-1 one-strike, Tier-2 2+, PHI-FP suppression, **NKA**, llama-veto, artifact-BLOCK, None-confidence) **on fixtured judge outputs**".
- **Implementation decided:** the 13 A3 tests (`test_judges_dspy.py:132-265`) cover every listed scenario EXCEPT NKA, substituting an explicit Tier-1-safety-floor test (`:217-225`); the session-log A3 evidence (`session...json:86`) likewise lists "Tier-1 safety floor" and omits NKA, without flagging the criterion as imprecise.
- **Why this is defensible:** NKA ("do NOT flag FABRICATED_ALLERGY on an AL1 segment containing NKA/NKDA") lives in the role prompt (`risk_judge.txt:1` and `:38`), i.e., it is a judge-emission suppression, not a consensus rule — there is no NKA branch in `_apply_consensus`. With fixtured judge outputs you can only assert "if no FABRICATED_ALLERGY finding is emitted, no Tier-1 strike", which is the clean-negative case, not NKA. So NKA is not reproducible "on fixtured judge outputs" by construction.
- **Question for the spec author:** correct A3 to drop NKA from the consensus-oracle list, and assign NKA coverage to the layer where it is testable (the rebuilt role prompt scored on a real NKA pack case at the live-smoke / pack layer, or at WS-6c-AGENTIC). Recommended resolution: update the criterion (NON-BLOCKING).

### Ambiguity 3: driver §3 dec#1 mis-assigns FABRICATED_HISTORY to risk_judge (RESOLVED at plan-review)

- **Spec text:** driver §3 decision 1 (`driver:106`) default "`risk_judge` — it owns `WRONG_DOSAGE`/`FABRICATED_HISTORY`".
- **Implementation decided:** the executor surfaced this as plan-review deviation D1 (`session...json:24-29`, user-approved), because `risk_judge.txt:24` places FABRICATED_HISTORY in the BEHAVIOR JUDGE's domain; `RISK_JUDGE_LENS` (`judge_metric.py:31-39`) therefore excludes it and the metric credits risk_judge for staying silent on it (`test_judge_metric.py:55-69`).
- **Recommended resolution:** ACCEPT (already documented and resolved). Confirmed correct against `risk_judge.txt:24`. The driver text should be corrected at close so the citation does not re-propagate. No code action.

**Findings:**

- `[OPEN-QUESTION]` Document or relocate `citations_used` (Ambiguity 1).
- `[OPEN-QUESTION]` Correct A3's NKA listing; assign NKA coverage to the prompt/live-smoke layer (Ambiguity 2).
- `[NON-BLOCKING]` Correct driver §3 dec#1 FABRICATED_HISTORY ownership text (Ambiguity 3, already resolved in practice).

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 1 (citations_used; also a NON-BLOCKING note) |
| 2 | Behavioral fidelity | 0 | 1 (A2 pack-data source) | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 1 (driver dec#1 text) | 2 (citations_used, NKA) |

**Total BLOCKING: 0** -> cycle MAY close.

Note: the citations_used finding is counted once under Q1 (it is both the surface-fidelity gap and Q4 Ambiguity 1). Net distinct findings: 4, all NON-BLOCKING or OPEN-QUESTION.

---

## Required actions (if any)

No BLOCKING findings. For the NON-BLOCKING / OPEN-QUESTION findings worth a follow-up but not blocking closure:

1. **Finding:** Seam doc omits `citations_used`, which `_apply_consensus:1942` reads.
   **Proposed disposition:** monitor at close adds a one-line note to `__init__.py` seam doc (downstream-enrichment-only); carry a seam/decision into WS-6c-AGENTIC to decide whether the DSPy judge emits `citations_used` once KB is wired.
2. **Finding:** A2 proof_case.jsonl offline score is not reproducible from a committed artifact.
   **Proposed disposition:** accept for this cycle (live smoke + synthetic recipe=label test satisfy A2); optionally commit a small `score_judge`-over-proof_case script in a follow-up, or soften the session-log wording.
3. **Finding:** A3 lists NKA among consensus-oracle scenarios though NKA is prompt-level.
   **Proposed disposition:** spec author corrects the A3 criterion text; NKA coverage tracked for the prompt/live-smoke layer (or WS-6c-AGENTIC).
4. **Finding:** driver §3 dec#1 mis-assigns FABRICATED_HISTORY to risk_judge.
   **Proposed disposition:** monitor corrects the driver text at close (already resolved in the impl via deviation D1).

---

## Critic discipline self-check (fresh-critic mode)

- [~] **Read the spec without reading the executor's session log first — PARTIAL, disclosed.** This pass was performed by continuing the monitor session that prepared the fresh-critic kickoff, not a genuinely separate clean-context session. During the earlier monitor pass I had already seen the session log's commit list, the self-reported A1-A8 PASS verdicts, the seams, and the next_session_hint. So the "no prior implementation context" property was WEAKER than a clean session would provide, and I knew the executor claimed CLEAN before I began. Mitigations actually applied this pass: I read the spec bodies (RECOMPOSITION_PLAN, the seam, the driver), the two impl modules, the two test files, the consensus code, and the role prompt, and I verified A1 (enumerated every per-judge read in `_apply_consensus` from source, which surfaced the undocumented `citations_used`), A4 (`git diff 6bae3c0..HEAD`), A6 (import grep), and D2 (confidence sourcing) BEFORE re-reading the session-log narrative. I adopted an adversarial stance (hunted for reads not in the seam doc; tested whether NKA is consensus-reproducible; checked the A2 evidence base) specifically to counter the anchoring risk.
- [x] Read the diff via `git show` / `git diff` against commits, not via the executor's summary.
- [x] Each finding cites both spec file:line and implementation file:line.
- [x] Did NOT edit any code, spec, or driver (only this critique file was written).
- [~] **Did NOT confer with monitor or executor before the verdict — PARTIAL.** This session IS the monitor (inline-by-continuation), so strictly this is closer to an inline critique by a monitor that read the spec and diff cold this pass than to a true independent fresh-critic.

**Honesty note for the closing monitor / user:** because two self-check items are PARTIAL, treat this as a strong inline-by-continuation critique rather than a fully clean-room fresh-critic. The technical verifications above (the `_apply_consensus` read enumeration, the byte-diff, the import isolation, the confidence sourcing) are reproducible from source by anyone and do not depend on reviewer independence. If maximal independence is wanted for this HARD GATE, a genuinely separate session (new context, `KICKOFF_CRITIC.md`, range `f90d299..HEAD`) remains the stronger gate and can be run as confirmation; I do not expect it to overturn the verdict, but it would close the independence gap.

---

## Appendix: commits audited

```
4e1d3cc docs(bench-salvage): WS-6c-DSPy session log (A1-A8 PASS; live smoke; S-BS-32)
c402010 test(council-dspy): seam-conformance + DSPy-judges-wrap-ported-consensus + metric (offline)
997f93a feat(council-dspy): bench-accept judge metric over recipe=label packs
95174c0 feat(council-dspy): per-judge DSPy module emitting the §6 seam (findings-first, None-tolerant)
(base: f90d299 docs(bench-salvage): author WS-6c-DSPy driver)
```

## Appendix: files changed

```
A  .devloop/sessions/session-bench-salvage-phaseWS-6c-DSPy-2026-06-02.json
A  lithrim_bench/runtime/council/judge_metric.py        163 ++++
A  lithrim_bench/runtime/council/judges_dspy.py         319 +++++++
A  lithrim_bench/runtime/council/tests/test_judge_metric.py   94 ++
A  lithrim_bench/runtime/council/tests/test_judges_dspy.py   265 +++++
5 files changed, 985 insertions(+)

A4 control: git diff 6bae3c0..HEAD over the full ported council set = 0 lines.
```
