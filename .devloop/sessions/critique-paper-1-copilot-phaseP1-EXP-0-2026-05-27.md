# Spec-Adherence Critique — `paper-1-copilot` phase `P1-EXP-0`

> Inline critique mode (monitor self-audit, bundle hardness `routine`).
> Committed alongside close-out artifacts by `/devloop-close-phase`.

## Metadata

- **Stream:** `paper-1-copilot`
- **Phase:** `P1-EXP-0`
- **Driver bundle:** `paper-1-copilot-phaseP1-EXP-0-council-confidence-driver`
- **Commits audited:** `32d1bf7..7f6858c` (4 deliverable commits) + `4fb93cc` (close-out chore)
- **Base commit:** `956e07c` (BRS-0b close)
- **Spec(s) read against:**
  - `docs/HANDOFF_2026-05-23.md` lines 92–100 (original experiment scope)
  - `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` D2 (reframe headline) + A1 (paper-1 = Jute Copilot paper, §5 = silent confident certification)
  - `docs/PAPER_OUTLINE.md` §5 amendment (post-2026-05-26)
  - `../lithrim-backend/app/services/pipeline/models.py:28-40` (`JudgeVote` API contract)
  - `.devloop/prompts/paper-1-copilot_phaseP1-EXP-0_council_confidence_driver.md` §2 (deliverables), §4 (scope), §5 (acceptance)
- **Critique mode:** `inline` (monitor self-audit)
- **Date:** 2026-05-27
- **Reviewer:** monitor (this session)

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The cycle delivers what the spec asked for: per-judge confidence is captured end-to-end, the silent subset is measured on the §5 failure-mode population at the council layer (not the pipeline layer, per A1 framing), and the §5 draft cites the summary outputs. One NON-BLOCKING gap (no automated test pins the analyzer's silent-subset filter definition) and three OPEN-QUESTIONs (silent-subset layer choice, N cardinality, broader-finding scope) are documented for follow-up. The Deviation #4 reframe is a *correct interpretation* of the spec, not drift — the driver's literal §2 D3 filter would have measured the §5 failure mode through its own §6 solution and yielded 0 by construction.

---

## 1. Surface fidelity

> Does the public API (function names, signatures, return shapes, error taxonomy, configuration keys, exported namespaces) match the spec exactly?

For each public symbol the driver defines:

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| driver §2 D1: `JudgeOutput` gains `confidence: float = 0.0` | `lithrim_bench/backends/base.py:27` `confidence: float = 0.0` | ✓ EXACT | — |
| driver §2 D1: `_parse` calls `JudgeOutput(..., confidence=float(jv.get("confidence", 0.0)))` | `lithrim_bench/backends/lithrim_pipeline.py:185` `confidence=float(jv.get("confidence", 0.0))` | ✓ EXACT (string-identical) | — |
| driver §2 D1 negative invariant: `BackendVerdict.raw` unchanged (5-scalar pin) | `lithrim_pipeline.py:204-210` byte-stable; diff has zero `raw\s*=` add/remove hits | ✓ EXACT | — |
| driver §2 D2: `scripts/measure_council_confidence_hl7.py` with `--n` (default 1), `--validator-id` (default 93), output to `out/p1_exp_0_council_confidence.ndjson` | `measure_council_confidence_hl7.py:110-117` `--pack-path`, `--out=out/p1_exp_0_council_confidence.ndjson`, `--n=1`, `--validator-id` argparse args present | ✓ EXACT | — |
| driver §2 D3: `scripts/analyze_council_confidence.py` emits `summary.{json,md}` with per-judge mean/median/p25/p75 + histogram + counts | `analyze_council_confidence.py:341-line script`; `_per_judge_stats` returns mean/median/p25/p75/min/max/histogram_0p1_buckets per role; summary.{json,md} present | ✓ EXACT | — |
| driver §2 D3: silent-subset filter = `expected_compliance_verdict=='reject' AND compliance_verdict=='approve' AND every per_judge[*].verdict=='approve'` | `analyze_council_confidence.py:97 _is_pipeline_silent` matches literal filter (yields 0/28); `analyze_council_confidence.py:84 _is_council_silent` drops the `compliance_verdict` clause (yields 10/28) and is the load-bearing measurement | **DEVIATION (documented)** | OPEN-QUESTION (Q4 Ambiguity 1) |
| driver §2 D4: `docs/paper_draft/05_section_5_silent_confident_certification.md` ≤400 words, cites summary outputs | 393 words (`wc -w` evidence in session log A5); 3 grep hits for `p1_exp_0_council_confidence.summary` | ✓ EXACT | — |
| driver §2 D5: `tests/test_lithrim_pipeline_confidence_capture.py` asserts both 0.87-captured and 0.0-default | `test_lithrim_pipeline_confidence_capture.py:28-43` `test_captures_confidence_when_present` + `test_confidence_defaults_to_zero_when_absent` | ✓ EXACT | — |
| driver A3: NDJSON `≥38/40` rows have non-null `per_judge`; `≥1` with non-zero confidence | 40/40 rows non-null `per_judge`; 40/40 non-zero confidence | ✓ EXCEEDS | — |

**Findings:**

- No surface drift detected. All 9 public symbols / artifacts match the spec, with the one filter-definition change documented as Deviation #4 (APPROVED-MID-CYCLE) with user quote `"go with a" 2026-05-27T02:55:00Z` and dual-filter codification in the analyzer. This is handled at Q4 Ambiguity 1, not as surface drift.

---

## 2. Behavioral fidelity

> Pick 3 key spec-claimed behaviors. Trace spec assertion → test that exercises it → implementation site. Does the chain actually demonstrate the behavior?

### Behavior 1: Per-judge confidence captured end-to-end from live council

- **Spec assertion:** HANDOFF_2026-05-23 line 100: *"pull each per-judge `confidence` / equivalent from the response, summarize as 'mean confidence of council on its 28 missed structural defects = X'"* + driver §2 D1: *"capture `jv.get("confidence", 0.0)` into the new field"*
- **Test:** `tests/test_lithrim_pipeline_confidence_capture.py:28-32` synthesizes `_parse` payload with `confidence: 0.87` in a single `judge_votes[i]`, asserts `verdict.per_judge["policy_judge"].confidence == 0.87`. Also `test_confidence_defaults_to_zero_when_absent` covers the backward-compat path.
- **Implementation:** `lithrim_bench/backends/lithrim_pipeline.py:185` `confidence=float(jv.get("confidence", 0.0))`; `lithrim_bench/backends/base.py:27` `confidence: float = 0.0`.
- **Chain closes?** **YES** at the parser layer. The end-to-end wire (live council emits non-null confidence; bench captures it; analyzer reads it) is exercised by the actual sweep output `out/p1_exp_0_council_confidence.ndjson` (40/40 rows non-zero) — an artifact assertion rather than a unit test.
- **Note:** the parser-layer test is sufficient because the wire shape was independently verified during the cycle (Deviation #2 folded the smoke check into sweep case 1; sweep success at case 1 implies the API actually returns the field).

### Behavior 2: Silent-subset measurement scoped to the §5 failure mode (not its §6 solution)

- **Spec assertion:** HANDOFF_2026-05-23 line 92: *"the headline becomes 'the council silently and confidently certifies spec-violating clinical artifacts'"* + PAPER_FRAMING D2: *"measure per-judge confidence on the 28 HL7 defects the live council missed"* + A1 §5 row: *"§5 — Silent confident certification (the failure mode the copilot's output prevents)"*
- **Test:** **none.** No automated test asserts that `_is_council_silent` retains its current shape, or that the analyzer's silent subset uses the council-layer filter rather than the pipeline-layer filter.
- **Implementation:** `scripts/analyze_council_confidence.py:84 _is_council_silent` (drops `compliance_verdict` clause; yields 10/28) is the §5-load-bearing function; `_is_pipeline_silent:97` retains the literal driver clause for audit (yields 0/28). Both reported in `summary.json`.
- **Chain closes?** **PARTIAL.** Spec assertion + implementation match (per Deviation #4's user-approved reframe), but no automated lock exists. If a future cycle re-uses the analyzer (e.g., for N=3 robustness, or for an §5 expansion), a refactor that re-conflates the layers could silently regress the measurement.
- **Note:** Single-use measurement scripts often don't carry filter tests. NON-BLOCKING for this cycle. Worth pinning if §5/§6/§7 future cycles re-call the analyzer.

### Behavior 3: `BackendVerdict.raw` shape byte-stable; BRS-0b §7 invariance preserved

- **Spec assertion:** driver §2 D1 Note: *"Do NOT also persist `confidence` in `BackendVerdict.raw`. `raw` is a 5-scalar pin (lines 204-210); the new field belongs on `per_judge`, not `raw`. Keep the existing `raw` schema byte-stable so BRS-0b's §7 snapshot test does not regress."* + driver A6.
- **Test:** `tests/test_brs_0b_section_7_invariance.py::test_section_7_pack_summary_invariance_against_brs_0b_baseline` re-asserts byte-identical `analyze_pack` output against the locked baseline snapshot.
- **Implementation:** `lithrim_pipeline.py:204-210` `raw` block is byte-identical pre/post; diff produces zero `raw\s*=` add/remove hits.
- **Chain closes?** **YES.** Both the negative invariant (no `raw` shape change) and the positive invariant (§7 snapshot unchanged) are pinned.

**Findings:**

- `[NON-BLOCKING]` **Behavior 2 has no automated lock test on the analyzer's silent-subset filter.** The §5 measurement chain (spec → impl) closes through the deviation, but a future refactor of `scripts/analyze_council_confidence.py:84 _is_council_silent` could silently re-conflate the council-layer and pipeline-layer subsets — exactly the bug Deviation #4 corrected. Recommended disposition: log under S-P1-6's process scope; if §5/§6/§7 future cycles re-call the analyzer, add a unit test that pins both `_is_council_silent` and `_is_pipeline_silent` against a fixture row (e.g., a synthetic case with `expected=reject + compliance=needs_review + all-judges-approve` should be council-silent but not pipeline-silent).

---

## 3. Out-of-scope intrusion

> Read the diff. Anything that isn't in the driver's deliverables list is intrusion.

Driver's deliverables list (verbatim from `paper-1-copilot_phaseP1-EXP-0_council_confidence_driver.md` §2):

1. **D1** — `lithrim_bench/backends/base.py` + `lithrim_bench/backends/lithrim_pipeline.py` (confidence capture)
2. **D2** — `scripts/measure_council_confidence_hl7.py` + `out/p1_exp_0_council_confidence.ndjson`
3. **D3** — `scripts/analyze_council_confidence.py` + `out/p1_exp_0_council_confidence.summary.{json,md}`
4. **D4** — `docs/paper_draft/05_section_5_silent_confident_certification.md`
5. **D5** — `tests/test_lithrim_pipeline_confidence_capture.py` + (re-verify) `tests/test_brs_0b_section_7_invariance.py`

`git diff --stat 956e07c..HEAD` shows these files changed:

```
.devloop/sessions/session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json  | 173 +
.devloop/state/STREAM_paper-1-copilot.md                                  |  97 +
docs/paper_draft/05_section_5_silent_confident_certification.md           |  25 +
lithrim_bench/backends/base.py                                            |   2 +
lithrim_bench/backends/lithrim_pipeline.py                                |   1 +
out/p1_exp_0_council_confidence.ndjson                                    |  40 +
out/p1_exp_0_council_confidence.summary.json                              | 107 +
out/p1_exp_0_council_confidence.summary.md                                |  62 +
scripts/analyze_council_confidence.py                                     | 341 +
scripts/measure_council_confidence_hl7.py                                 | 212 +
tests/test_lithrim_pipeline_confidence_capture.py                         |  43 +
```

Mapping:

- `base.py`, `lithrim_pipeline.py`, `test_lithrim_pipeline_confidence_capture.py` → D1 + D5 ✓
- `measure_council_confidence_hl7.py`, `out/p1_exp_0_council_confidence.ndjson` → D2 ✓
- `analyze_council_confidence.py`, `out/p1_exp_0_council_confidence.summary.{json,md}` → D3 ✓
- `docs/paper_draft/05_section_5_silent_confident_certification.md` → D4 ✓
- `.devloop/sessions/session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json` → required by EXECUTOR.md §3 (session log) + driver §7 checklist
- `.devloop/state/STREAM_paper-1-copilot.md` → driver §7 checklist line 8 ("STREAM updated: S-P1-1 marked resolved; current_phase advanced past P1-EXP-0; P1-§5 unblocked")

Driver §4 NOT-in-scope items (7) verified absent by audit Item 4 (`MockBackend` / `TunedMockBackend` untouched; `run_determinism.py` untouched; no 4-pack semantic sweep re-run; only the new §5 file in `paper_draft/`; `BackendVerdict.raw` byte-stable; no lithrim-backend touches; `worst_of.py` untouched).

**Findings:**

- All diffed files map to deliverables or close-out-anticipated artifacts. **No intrusion detected.**

---

## 4. Spec ambiguity surfaced

> Where did the implementation make a judgment call because the spec was silent or ambiguous?

### Ambiguity 1: Silent-subset layer (council-only vs council∘structural) — load-bearing

- **Spec text:** HANDOFF_2026-05-23 line 100: *"re-run the 28 HL7 defect cases (deterministic structural ones the council already missed at run #1), pull each per-judge `confidence`"* — "missed" is layer-ambiguous. Driver §2 D3 made the layer choice concrete but conflated layers: literal filter requires both `compliance_verdict == "approve"` (pipeline gate) AND `per_judge[*].verdict == "approve"` (council layer). PAPER_FRAMING A1 §5 row: *"§5 — Silent confident certification (the failure mode the copilot's output prevents)"* — implies §5 is the council-layer failure mode that §6's worst-of composition fixes.
- **Implementation decided:** `analyze_council_confidence.py:84 _is_council_silent` drops the `compliance_verdict` clause (council-only filter, yields 10/28). `_is_pipeline_silent:97` retains driver-literal filter (yields 0/28) for audit. Both reported in summary.json.
- **Alternatives that would also be spec-compliant:** (a) keep driver-literal filter, report 0/28 as honest negative — paper would claim "the council never confidently certifies *that the pipeline ships*" (correct but trivial); (b) reframe §5 as pipeline-layer measurement (then 0/28 is the headline and §5 becomes "the composed pipeline never silently certifies" — different and weaker §5); (c) measure both layers (impl).
- **Question for spec author:** §5 framing per A1 = "the failure mode the copilot's output prevents." If the copilot's output (mapping 93) prevents the failure at the pipeline gate via worst-of composition, is "silent confident certification" at the *council layer* (10/28, the failure mode) or at the *pipeline layer* (0/28, the composed surface)?
- **Recommended resolution:** lock §5 = council-layer (matches A1 framing intent + makes §6's "worst-of recovers all 10" the natural successor section). Update future paper-1-copilot driver template (§5/§6/§7 cycles) to require layer-explicit subset definitions. **Already opened as S-P1-6 (medium severity).**

### Ambiguity 2: Run cardinality — N=1 vs N>1 for variance bars on the headline

- **Spec text:** driver §3 plan-review checkpoint: *"Default is N=1 ($5, faster); N=3 ($15) buys variance bars on the headline number. Monitor-recommended default: N=1 for v1."* Spec is explicit about the trade but does not declare which is paper-load-bearing.
- **Implementation decided:** N=1 (per default).
- **Alternatives that would also be spec-compliant:** N=3 (driver-allowed via `--n 3`).
- **Question for spec author:** do the §5 headline numbers — per-judge confidence ≡ 1.000 across all 30 votes — need variance bars in the paper, or is the determinism question moot when stdev is 0 by inspection?
- **Recommended resolution:** accept N=1 for v1. The variance bar is degenerate (sd=0 across all 30 observations means N=3 would produce three identical-to-12-decimals histograms). If a referee challenges, run N=3 then; cost is ~$15.
- **Severity:** OPEN-QUESTION (resolved by data, no follow-up needed unless challenged).

### Ambiguity 3: §5 draft scope — silent-subset-only vs broader confidence-distribution finding

- **Spec text:** HANDOFF_2026-05-23 + D2 both anchor on "confidence on the silent subset." Neither addresses the broader observation that per-judge confidence ≡ 1.000 across **all 40 cases** in the sweep, regardless of correctness, expected verdict, or actual verdict.
- **Implementation decided:** §5 draft (`docs/paper_draft/05_section_5_silent_confident_certification.md`) leads with the 10/28 silent-subset framing per spec; does not surface the broader "confidence is degenerate" observation.
- **Alternatives that would also be spec-compliant:** (a) draft as written, defer the broader observation to a future §5 expansion (impl); (b) frame §5 around the broader finding ("the council emits maximum confidence on every clinical artifact it sees") with the 10/28 subset as the demonstration; (c) split — silent subset in §5, "confidence is degenerate" as §5.X or a separate paragraph in §7.
- **Question for spec author:** does §5 benefit from the category claim ("confidence is not a signal in this stack") or is the silent-subset framing tighter for a v1 arXiv release?
- **Recommended resolution:** this is a P1-§5 expansion task, not a P1-EXP-0 follow-up. The supporting data is in `out/p1_exp_0_council_confidence.ndjson` for the future cycle. **Severity:** OPEN-QUESTION (forward-looking).

**Findings:**

- `[OPEN-QUESTION]` Ambiguity 1 — silent-subset layer choice. Logged as S-P1-6 (medium); analyzer codifies both subsets.
- `[OPEN-QUESTION]` Ambiguity 2 — N cardinality. Resolved by degenerate-variance data; no action.
- `[OPEN-QUESTION]` Ambiguity 3 — §5 draft scope (silent-only vs broader). Forward to P1-§5 cycle.

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 0 | 0 |
| 2 | Behavioral fidelity | 0 | 1 | 0 |
| 3 | Out-of-scope intrusion | 0 | 0 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 3 |
| **TOTAL** | | **0** | **1** | **3** |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions

No BLOCKING findings.

NON-BLOCKING and OPEN-QUESTION findings worth a follow-up but not blocking closure:

1. **NON-BLOCKING (Q2 Behavior 2):** No automated lock test on `analyze_council_confidence.py:_is_council_silent` / `:_is_pipeline_silent`. Future refactor could re-conflate the layers. **Proposed disposition:** roll into S-P1-6's process scope; if a future cycle re-calls the analyzer (P1-§5 expansion, N=3 robustness sweep, §6 / §7 cycles), add a unit test at that point with a synthetic fixture row (`expected_compliance_verdict=reject + compliance_verdict=needs_review + all per_judge[*].verdict=approve` → `_is_council_silent=True`, `_is_pipeline_silent=False`). Owner: future cycle's executor.
2. **OPEN-QUESTION (Q4 Ambiguity 1):** Silent-subset layer = council-layer (10/28) per A1 framing intent. Already opened as **S-P1-6**. **Proposed disposition:** lock the choice in the next monitor edit to PAPER_FRAMING_DECISIONS / PAPER_OUTLINE §5; rephrase future paper-1-copilot drivers to be layer-explicit. Owner: monitor in close-out or P1-§5 planning.
3. **OPEN-QUESTION (Q4 Ambiguity 2):** N=1 sufficient because variance is degenerate. **Proposed disposition:** accept as-is; no S-seam needed. Owner: none.
4. **OPEN-QUESTION (Q4 Ambiguity 3):** §5 draft scope — silent-only vs broader. **Proposed disposition:** log as P1-§5 planning input (the sharper "confidence ≡ 1.000 on all 40 cases" finding is in `out/p1_exp_0_council_confidence.ndjson` and worth surfacing when the §5 expansion cycle launches). Owner: P1-§5 monitor session.

---

## Critic discipline self-check (inline mode)

- [x] Read the spec (HANDOFF, PAPER_FRAMING, PAPER_OUTLINE, JudgeVote contract, driver) before reading the session log's `verdict` / `acceptance[]` for this critique pass
- [x] Each finding cites both spec file:line and implementation file:line
- [x] Did NOT edit any code, spec, or driver during this pass
- [x] Did NOT change the executor's commits or session log

The inline mode allows session-log cross-checking *after* findings are drafted; verified the analyzer's `_is_council_silent` / `_is_pipeline_silent` codification matches the deviation log's claim before finalizing.

---

## Appendix: commits audited

```
4fb93cc chore(devloop): close P1-EXP-0 — session log + STREAM update
7f6858c docs(paper): draft §5 — silent confident certification (P1-EXP-0)
1067078 analysis(bench): aggregate council confidence on silent-confident HL7 subset
246dbde exp(bench): P1-EXP-0 council-confidence sweep on hl7_adt_v1 (N=1, mapping 93)
32d1bf7 feat(bench): capture per-judge confidence in LithrimPipelineBackend._parse
```

## Appendix: files changed

```
 ...n-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json | 173 +++++++++++
 .devloop/state/STREAM_paper-1-copilot.md           |  97 ++++++
 .../05_section_5_silent_confident_certification.md |  25 ++
 lithrim_bench/backends/base.py                     |   2 +
 lithrim_bench/backends/lithrim_pipeline.py         |   1 +
 out/p1_exp_0_council_confidence.ndjson             |  40 +++
 out/p1_exp_0_council_confidence.summary.json       | 107 +++++++
 out/p1_exp_0_council_confidence.summary.md         |  62 ++++
 scripts/analyze_council_confidence.py              | 341 +++++++++++++++++++++
 scripts/measure_council_confidence_hl7.py          | 212 +++++++++++++
 tests/test_lithrim_pipeline_confidence_capture.py  |  43 +++
 11 files changed, 1103 insertions(+)
```
