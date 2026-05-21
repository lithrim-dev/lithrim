# §7 — Results (skeleton; awaits Item 4 N=10 sweep)

**Status:** **placeholder**. Numeric cells are not drafted because they require the N=10 sweep at pack size 50 (kickoff Item 4, bench commit `4dd0909`, in-flight at the time of this draft). The reportability gate (§6.5) forbids drafting cells the data does not yet support.

This file pins what the tables will look like and which `out/*.n10.analysis.json` and `out/judge_calibration_n10.json` artifacts each cell will trace to.

---

## 7.1 Per-pack headline (planned)

| Pack | N | Backend | verdict_match_rate (95% CI) | instability_rate | false_block_rate | defects_caught | Source |
|---|---|---|---|---|---|---|---|
| `scribe_v1` | 10 | live council only | TBA | TBA | TBA | TBA | `out/scribe_v1.n10.analysis.json` |
| `scheduling_v1` | 10 | live council + structural | TBA | TBA | TBA | TBA | `out/scheduling_v1.n10.analysis.json` |
| `coding_v1` | 10 | live council + structural | TBA | TBA | TBA | TBA | `out/coding_v1.n10.analysis.json` |
| `triage_v1` | 10 | live council + structural | TBA | TBA | TBA | TBA | `out/triage_v1.n10.analysis.json` |
| `hl7_adt_v1` | 10 | structural-only mapping 26 | TBA | TBA | TBA | TBA | (Item 4 follow-up; HL7 pack not in current sweep) |

The right-most column is the production-relevant metric for the conformance-axis claim. For HL7 we already have the Phase 1 anchor (`defects_caught = 8/28` = 28.6% at N=1, commit `d5b49f2`); the N=10 sweep extends the same metric to the four semantic packs.

## 7.2 Per-judge calibration (planned)

| Judge | n (cases × runs) | accuracy | recall (reject) | precision (reject) | false_block_rate | flag_attach_mean | Source |
|---|---|---|---|---|---|---|---|
| `policy_judge` | 2000 | TBA | TBA | TBA | TBA | TBA | `out/judge_calibration_n10.json` |
| `risk_judge` | 2000 | TBA | TBA | TBA | TBA | TBA | same |
| `behavior_judge` | 2000 | TBA | TBA | TBA | TBA | TBA | same |

Phase 1 anchors at N=1, 32 cases (commit `aff3aa9`, `out/judge_calibration_v3.json`):
- Ensemble (majority vote): 0.8125
- Mean per-judge accuracy: 0.812
- Mean per-judge flag attachment: 0.215
- `behavior_judge` precision (reject): 1.000

The N=10 cells will narrow these to ±0.02 confidence intervals if the per-call variance holds at the levels observed in Phase 1.

## 7.3 The headline contrast (HL7 ADT^A04)

This table is **already populated** from the Phase 1 live measurement (commit `d5b49f2`, [`docs/HEADLINE_CONTRAST_2026-05-21.md`](../HEADLINE_CONTRAST_2026-05-21.md)):

| System | Defects caught | Clean correct | Source |
|---|---|---|---|
| **Tuned-mock alone** (lit-anchor p=0.781, attach=0.167) | **0 / 28** (0.0%) | 12 / 12 (100%) | `out/hl7.A.tuned_only.analysis.json` |
| **Live structural validator** (etlp mapping 26 via Lithrim middleware) | **8 / 28** (28.6%) | 12 / 12 (100%) | `out/hl7.B.struct_only.analysis.json` |
| **Worst-of(tuned-mock, live validator)** | **8 / 28** (28.6%) | 12 / 12 (100%) | `out/hl7.C.worstof.analysis.json` |

**The composition's gain is +28.6 percentage points** of structural-defect catch on this pack. This is the live version; the simulated ceiling at full validator coverage is **+60 pp** ([`docs/HEADLINE_CONTRAST_2026-05-21.md`](../HEADLINE_CONTRAST_2026-05-21.md)) and the gap between the two is named in §7b. The Item 4 N=10 sweep does NOT re-measure the HL7 pack (the structural validator is deterministic; N=10 on a deterministic stage adds no information beyond confirming the mocked semantic side replicates).

## 7.4 Three-layer decomposition (planned, illustrative)

Per eval-spec §2.2, the bench's contribution is reporting the three layers separately, not folding them into one number. Cells will fill from `out/<pack>.n10.analysis.json`:

| Pack | Decision-layer kappa | Code-attribution rate | verdict_instability mean | Cases with instability > 0 |
|---|---|---|---|---|
| `scribe_v1` | TBA | TBA | TBA | TBA |
| `scheduling_v1` | TBA | TBA | TBA | TBA |
| `coding_v1` | TBA | TBA | TBA | TBA |
| `triage_v1` | TBA | TBA | TBA | TBA |

Phase 1 anchor (calibration sweep, N=1, 32 cases): decision-vs-attribution gap is **3.78×** (verdict-level 0.812 vs exact-flag 0.215). The N=10 cells will quantify how much of that gap is intrinsic per-judge variance vs the aggregator-routing sensitivity the `hba1c` case exposes.

## 7.5 Confidence-gate dual-config delta (planned)

| Pack | as-shipped accuracy | forced-open accuracy | skipped_council_rate | Δ | Source |
|---|---|---|---|---|---|
| `scribe_v1` | TBA | TBA | TBA | TBA | `out/scribe_v1.n10.dualgate.analysis.json` |
| `scheduling_v1` | TBA | TBA | TBA | TBA | same shape |
| `coding_v1` | TBA | TBA | TBA | TBA | same shape |
| `triage_v1` | TBA | TBA | TBA | TBA | same shape |

If forced-open materially changes accuracy, the gate is part of the system under test and is reported as such; we do not hide it upstream.

## 7.6 Critique-pass on/off arms (planned)

| Pack | critique-off accuracy | critique-on accuracy | findings dropped (true unsupported) | findings dropped (over-prune) | Source |
|---|---|---|---|---|---|
| `scribe_v1` | TBA | TBA | TBA | TBA | `out/scribe_v1.n10.critique_arms.analysis.json` |
| (others) | TBA | TBA | TBA | TBA | same shape |

`purpose="mini"` is excluded per the eval-spec D7 finding (same-model blindspot).

## 7.7 Worst-of recovery summary (planned)

The single-cell summary the paper's headline depends on:

> Across the four semantic packs at N=10 size-50, the worst-of(live council, live structural validator) composition recovered **[TBA pp]** of structural-defect catch relative to live-council alone, at a false-block cost of **[TBA pp]** on clean negatives. On the HL7 ADT^A04 pack the live-validator composition recovered **+28.6 pp** of structural-defect catch (commit `d5b49f2`); a simulated full-coverage validator on the same pack would recover **+60 pp** (commit `d5b49f2`, illustrative).

The first sentence is the §7 row anchor that requires the N=10 sweep. The second is already locked.

## Drafting protocol when Item 4 lands

When `out/scribe_v1.n10.ndjson` and peers exist (4 NDJSONs with 500 rows each):

1. Run `scripts/analyze_runs.py --runs out/<pack>.n10.ndjson --pack out/<pack>.n10.jsonl` for each pack.
2. Run `scripts/calibrate_judges.py` across all 4 NDJSONs (post-run commands in [`docs/N10_SWEEP_FOLLOWUP_2026-05-21.md`](../N10_SWEEP_FOLLOWUP_2026-05-21.md)).
3. Verify each pack passes the reportability gate (§6.5): lint green, full coverage, `instability_rate` reported, pinned block recorded.
4. Fill in the cells above.
5. Tighten the abstract's bracketed results sentence in `01_abstract.md`.

## Word count

Approximately 870 words (skeleton + planned-cells + drafting protocol). Under the 1500-word ceiling.

## Citation provenance

| Claim | Source |
|---|---|
| HL7 +28.6 pp | commit `d5b49f2` → `out/hl7.C.worstof.analysis.json` |
| HL7 simulated +60 pp | commit `d5b49f2` → `docs/HEADLINE_CONTRAST_2026-05-21.md` |
| Phase 1 ensemble 0.8125 | commit `aff3aa9` → `out/judge_calibration_v3.json` |
| `behavior_judge` precision 1.000 | commit `aff3aa9` → same artifact |
| 3.78× decision-vs-attribution | commit `aff3aa9` → same artifact |
| N=10 sweep in flight | commit `4dd0909` → `docs/N10_SWEEP_FOLLOWUP_2026-05-21.md` |
