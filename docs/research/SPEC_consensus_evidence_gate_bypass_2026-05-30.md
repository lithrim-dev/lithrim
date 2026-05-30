# SPEC: close the legacy `violations_found` per-flag evidence-gate bypass in the compliance council

> Fix spec for the `MEDICATION_NOT_IN_TRANSCRIPT` false positive on `scribe_v1` case 1.
> **Extends** `docs/research/REPORT_council_overfire_convergence_2026-05-28.md` with a
> **second, code-level** over-fire mechanism (the 2026-05-28 report characterized a
> substantive reasoning over-fire on v2; this is a companion-flag aggregation bypass on v1).
> Diagnose-before-edit: evidence is `file:line` + verbatim run JSON; every causal claim
> tagged CONFIRMED / INFERRED / HYPOTHESIS.
>
> **Date:** 2026-05-30 · **Status:** ⛔ **FALSIFIED — DO NOT IMPLEMENT.** The persisted-reasoning enabler (§6) **did** land; the R3(d) fix itself was never coded.

---

> ## ⛔ FALSIFIED 2026-05-30 (COUNCIL-EVIDENCE-GATE pre-check P0)
>
> **The core diagnosis in §2b is empirically false, and the R3(d) fix does not apply to the observed defect.** A `--limit 1` raw-capture pre-check ($0.10, before the $5 sweep) found the `MEDICATION_NOT_IN_TRANSCRIPT` FP is **findings-first, fully-evidenced, and semantically-validated** — all 3 judges emit it with per-code `evidence_spans` (overlap 1.000), symmetric with the true defect on every aggregation-readable signal. The legacy `violations_found` branch (`:1962-1971`) **never executes** on this case (judges return findings-first → the `:1907` selector routes elsewhere). The persisted `spans=[]` that this spec read as "legacy span-less bypass" (§2b, ledger 199–201) was an **NDJSON projection artifact** — `evidence_spans` is dropped by schema and appears 0× in all persisted files.
>
> All three authorized levers (`:1530`, `:1962-1971`, an evidence-aware `:2170`) are inert, and the OMISSION-code corpus-narrowing shortcut also fails (the self-refuting span is transcript text). Root cause is **judge calibration**, not consensus aggregation: the judge cites the transcript line that *contains* zidovudine as proof the med is *absent*. Re-routed to **P1 / P1-VEC** as a per-question presence-check tool (new seam **S-BS-7**, high).
>
> **Authoritative falsification record (verbatim raw evidence + lever table + confidence ledger):** `docs/research/REPORT_r3d_precheck_falsification_2026-05-30.md`. **Raw evidence (tracked):** `docs/research/r3d_precheck_P0_raw_evidence_2026-05-30.ndjson`. The §2b / §3 / §4 fix design below is retained as a record of the original (wrong) diagnosis; do not act on it.

---

## 1. The defect (CONFIRMED)

`scribe_v1` case 1 (`bench_scribe_v1_inject_condition_1bd0f10dc7b5`) carries exactly one
injected defect — a fabricated PMH diagnosis — yet the council emits a second, unwarranted
HIGH flag, `MEDICATION_NOT_IN_TRANSCRIPT`, on a medication that is verbatim in the transcript
and was never mutated.

```
transcript (the entire context the council saw, via _build_context -> case["transcript"]):
  "Dr: I see you're on zidovudine 300 MG Oral Tablet. Continue at 300 MG daily.
   Patient: Got it, 300 MG of the zidovudine, every day."
artifact PLAN: "Continue zidovudine 300 MG Oral Tablet 300 MG daily"
injection_recipes[0].post_value = "Diabetes mellitus type 2 (disorder)"   # the ONLY defect

expected: verdict=reject, flags=[FABRICATED_HISTORY]
actual  : verdict=reject, flags=[FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT]   # FP
```

The verdict is correct (`reject`, on the true `FABRICATED_HISTORY`); the **flag set** is
wrong. Run artifact: `out/scribe_v1.local.ndjson` (M1 baseline) and
`out/scribe_v1.local.guardfix.ndjson` (re-run with reasoning captured). Council: v1
(3x gpt-4.1, BYOK Azure), semantic-only stage (`LocalPipelineBackend`).

---

## 2. Root cause: a two-part failure (CONFIRMED)

### 2a. The judge over-lists the flag (calibration) — CONFIRMED by captured `reason`

The per-judge rationale (now persisted, §6) proves the judges are **not** confused about
transcript presence — they pad the flag list with a fabrication-family companion code:

```
behavior_judge  vote=reject flags=[FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT]
  reason: "...Only sprain and zidovudine WERE MENTIONED; all other history is invented."
policy_judge    vote=reject flags=[FABRICATED_HISTORY, MEDICATION_NOT_IN_TRANSCRIPT]
  reason: "...fabricated medical history and unsupported allergy documentation..."   # NKDA in artifact; no med rationale
risk_judge      vote=reject flags=[FABRICATED_HISTORY]                                # clean: only the true defect
```

`behavior_judge` explicitly states zidovudine **was** mentioned, then flags it as
not-in-transcript anyway. `policy_judge`'s rationale is about history + a phantom allergy,
never a medication. Neither rationale supports a medication-absence finding. The flag is a
**companion code riding on the "this artifact fabricates content" decision** — the same
fabrication-family over-fire the 2026-05-28 report named, observed here as flag-list padding
rather than substantive misjudgment.

### 2b. Consensus does not gate the companion flag per-flag (code) — ⛔ FALSIFIED 2026-05-30 (was CONFIRMED; see top banner + REPORT_r3d_precheck_falsification_2026-05-30.md)

The council advertises a per-flag evidence gate ("A finding WITHOUT evidence_spans is INVALID
and will be discarded", `build_prompt` ~`:685`), but that gate exists **only on the
findings-first path**. The v1 judges surfaced this flag through the **legacy
`violations_found` path**, where evidence is judge-level and shared across all of a judge's
flags:

- `_normalize_result` (`compliance_council.py:1466`, `:1555`): `violations_found` passes
  through ungated. The spans-discard (`:1518-1525`) applies only to the structured
  `findings[]` array; the derive-from-findings rebuild (`:1530`) fires **only when
  `violations_found` is empty** (`if findings and not violations_found`). A judge that emits
  a flat `violations_found` keeps it verbatim.
- `_apply_consensus` (`compliance_council.py:1907`) selects the findings-first branch only
  when `raw_findings` is non-empty; otherwise the **legacy branch** (`:1962-1971`) runs:
  `violations = set(result["violations_found"])`, `has_evidence = bool(primary_evidence or
  supporting_context)` — one judge-level flag for **all** violations
  ("Old format: same evidence flag for all violations", "carries no per-violation spans").

So `MEDICATION_NOT_IN_TRANSCRIPT` inherits the judge's `FABRICATED_HISTORY` evidence and
survives consensus into `evidence_summary.violation_judges`. The persisted row confirms the
legacy branch fired: `findings_rich` shows `MEDICATION_NOT_IN_TRANSCRIPT (judges=2)` with
**empty** spans, not the per-finding spans the findings-first branch would carry.

**Which output format the v1 judges emitted per-judge is HYPOTHESIS** (pure legacy
`violations_found` vs findings-first that got fully discarded) — the council does not persist
each judge's raw LLM JSON, only the mapped `JudgeVote` + consensus findings. Cheap test:
log the raw per-judge `findings[]`/`violations_found` on one re-run. The CONFIRMED part is
that the flag surfaced via the **judge-level-evidence legacy path**, which has no per-flag gate.

---

## 3. Relationship to REPORT_council_overfire_convergence_2026-05-28

Same family (`FABRICATED_*` / companion over-fire), **different layer and config** — this is
additive, not a duplicate:

| | 2026-05-28 report | This spec |
|---|---|---|
| Council | v2 (cross-provider: Mistral / Llama / gpt-4.1) | v1 (3x gpt-4.1) |
| Surface | clean artifacts (C1, FHIR-A) | a **defective** artifact (true FABRICATED_HISTORY + FP companion) |
| Mechanism | judge **reasons** fabrication from structured-detail asymmetry (substantive) | judge **pads** an un-evidenced companion flag that the **aggregation layer** fails to gate (structural) |
| Over-firer | varies by artifact type (judge-agnostic) | the **consensus legacy path** (judge-agnostic by construction) |
| Fix shape proposed | R3(a) pre-stage normalization / R3(b) shared coaching / R3(c) paper pivot | **R3(d): close the per-flag evidence-gate bypass in consensus** (new) |

Both reports converge on "do not single-judge-scope a code." This spec's fix is inherently
judge-agnostic (it lives in `_apply_consensus`), so it composes with R3(a). **Open question
(HYPOTHESIS):** whether the v2 over-fires in the 2026-05-28 report also ride the legacy path
(companion-padded, un-evidenced) or are genuinely evidenced substantive findings — a cheap
check now that per-judge `reason` + consensus spans are persisted (§6). If the v2 flags are
also span-less, R3(d) partially fixes both; if they carry real spans, R3(a) is still required
for the asymmetry class.

---

## 4. Proposed fix — R3(d): per-flag evidence in consensus

**Principle:** a taxonomy code counts toward the verdict **only if the judge supplied
evidence specifically for that code.** The legacy format cannot express per-code evidence, so
the fix is to make the **evidenced `findings[]` the authoritative violation set** and retire
the legacy path's ability to introduce un-evidenced codes.

Two coordinated changes:

1. **Output contract (prompt).** Require findings-first: every flag MUST be a
   `findings[]` entry with its own `evidence_spans`; state that bare `violations_found` is
   derived from `findings[]`, not authoritative. The prompt currently requests **both**
   shapes (`build_prompt` ~`:742` `"violations_found": [...]` alongside the evidence_spans
   instruction ~`:749`), which is the ambiguity that lets a judge return a padded flat list.

2. **Aggregation (`_normalize_result` + `_apply_consensus`).** When a judge emits validated
   `findings[]`, make those codes authoritative — drop any `violations_found` code lacking an
   evidenced finding (change `:1530` from `if findings and not violations_found` to always
   reconcile: `violations_found = [c for c in violations_found if c in evidenced_codes]`).
   For a judge that emits **only** legacy output, a code with no per-code evidence does not
   pass the gate (it surfaces as flag-only / non-decision-driving at most, never a BLOCK
   vote — mirrors the 2026-05-28 Finding-2 nuance: "structured-detail asymmetry must not
   drive a BLOCK vote").

**Why not prompt-only (the carryforward guard, tested and rejected):** a behavior-judge
prompt guard ("clinical incongruity is not transcript absence") was added and re-run on
2026-05-30. The FP **persisted** — because the judge already knows the med is present (§2a);
the flag is a padding/aggregation artifact, not a presence-reasoning error. The guard was
reverted. A prompt-only fix cannot close a gate that lives in the aggregation code.

**Blast radius (why this needs a batch run, not a 1-case check):** making findings
authoritative changes the flag set on **every** case. It will (correctly) drop un-evidenced
companion flags, but if any v1 judge emits legitimate flags only via legacy `violations_found`
with no `findings[]`, those drop too. Must verify no true-defect regression before landing.

---

## 5. Validation protocol (the deferred run)

Mirror the 2026-05-28 reverify path. On a multi-case batch (the full 30-case `scribe_v1`, or a
stratified subset = the two cleans + S1/S3 true-FABRICATED_HISTORY + this case):

- **FP suppressed:** case 1 `MEDICATION_NOT_IN_TRANSCRIPT` gone; `FABRICATED_HISTORY` retained;
  verdict stays `reject`.
- **No true-defect regression:** `FABRICATED_HISTORY` emission stays high where genuinely
  warranted (do not over-correct into missing real fabrication on S1/S3); per-defect
  recall unchanged within tolerance.
- **False-block on cleans:** unchanged or improved (this is the metric the FP most affects).
- **Determinism preserved:** per-(case, judge) seed is `sha256(case_id|judge_role)`
  (`compliance_council.py:63`), independent of prompt/consensus code, so the run is a clean A/B.
- Reproducibility bar = verdict + flag-set + confidence, not byte-identical reasoning.

This run doubles as the deferred pack-level `scribe_v1` sweep (verdict accuracy, flag
precision/recall, false-block rate).

---

## 6. Enabler shipped this session: persisted judge reasoning

The 2026-05-28 report had to inspect raw per-judge NDJSON by hand. This diagnosis was only
possible because the runner now persists the reasoning surface — a no-regrets change that
landed this session (38/38 tests green):

- `backends/base.py`: `JudgeOutput.reason` field added.
- `backends/local_pipeline.py`: `_map_result` captures `JudgeVote.reason`.
- `eval_runner.py`: `_verdict_row` persists per-judge `{verdict, flags, confidence, reason}` + `findings_rich`
  + `structural_findings_rich`.

`per_judge[*].reason` + `findings_rich[*].detail` are now the offline root-cause surface: a
calibration miss can be diagnosed from the standard NDJSON row **without** re-issuing a paid
council call. (It was `behavior_judge.reason` — "zidovudine were mentioned" — that disproved
the prompt-guard hypothesis and pinned the aggregation cause.)

---

## 7. Confidence ledger

| Claim | Tag | Basis |
|---|---|---|
| `MEDICATION_NOT_IN_TRANSCRIPT` on case 1 is a true FP | CONFIRMED | med verbatim in transcript; `injection_recipes[0]` is the diabetes PMH only (§1) |
| Not a payload/transcript-dropping bug | CONFIRMED | `_build_context` returns `case["transcript"]` with the med; FABRICATED_HISTORY required the transcript (§1) |
| Judges over-list the flag without supporting rationale | CONFIRMED | captured per-judge `reason` (§2a) |
| ~~The flag surfaced via the legacy judge-level-evidence path~~ | ⛔ FALSIFIED 2026-05-30 | findings-first; `:1962-1971` never runs (REPORT_r3d_precheck §2a) |
| Per-flag evidence gate exists only on findings-first | CONFIRMED | `:1518-1525`, `:1907-1925` vs `:1962-1971` (§2b) — true, but moot: MED IS findings-first + evidenced |
| ~~The v1 judges emitted pure-legacy (no `findings[]`)~~ | ⛔ FALSIFIED 2026-05-30 | raw capture: all 3 judges findings-first w/ per-code spans (REPORT_r3d_precheck §2) |
| Prompt-only guard cannot fix it | CONFIRMED | guard added + re-run 2026-05-30; FP persisted; reverted (§4) |
| Same legacy bypass explains the v2 over-fires | HYPOTHESIS | not yet checked against the 2026-05-28 v2 NDJSON (§3) |

---

## 8. References

- `docs/research/REPORT_council_overfire_convergence_2026-05-28.md` (the v2 substantive over-fire; R1-R4)
- `docs/HANDOFF_BENCH_SALVAGE_2026-05-29.md` (M1 spine; open question #3 = this FP, now diagnosed)
- Council aggregation: `lithrim_bench/runtime/council/compliance_council.py:1461` (`_normalize_result`), `:1853` (`_apply_consensus`), `:1907` (format selector), `:1962` (legacy branch)
- Run artifacts: `out/scribe_v1.local.ndjson` (M1 baseline), `out/scribe_v1.local.guardfix.ndjson` (reasoning-captured re-run)
- Persistence enabler: `lithrim_bench/{backends/base.py, backends/local_pipeline.py, eval_runner.py}`
