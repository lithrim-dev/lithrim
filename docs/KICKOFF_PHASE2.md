# Kickoff — Phase 2

**For:** the next session that picks up `lithrim-bench` from where 2026-05-21 left off.
**Prereqs:** read `docs/HANDOFF_2026-05-21.md` first.

This is a self-contained prompt. Drop into a fresh session, point it at this file, and start executing.

---

## Where we are

Phase 1 is closed. Every claim in `docs/PAPER_OUTLINE.md` has a measured anchor or a documented Phase-2 gap. The bench measured:

- Ensemble accuracy **0.8125** against the live gpt-4.1 council (matches lit anchor)
- Mean per-judge accuracy **0.802**, flag-attachment **0.218** (3.5× decomposition gap)
- Worst-of composition gain **+28.6 pp** on the HL7 pack
- Validator coverage **2 of 5** defect classes (mapping 26 field-presence)

Open Phase-2 items are listed at the end of `HANDOFF_2026-05-21.md`. This kickoff walks through them in priority order with concrete acceptance criteria.

---

## Phase 2 plan, sequenced

### Item 1 — coding_v1 v3 artifact (close the 4/4 needs_review on cleans)

**Why first:** smallest surface, biggest visible improvement to a paper §7 table cell. The current v2 transcript names ICD-10 + CPT codes explicitly, but the FHIR Claim artifact omits required fields (`provider.npi`, `total`, `insurance[]`). Live council reads the Claim and emits Tier-3 INCOMPLETE_DOCUMENTATION on clean cases.

**Files to touch:**
- `lithrim_bench/synthesizers/coding_artifact.py` — extend the emitted Claim to include the missing required fields.
- `lithrim_bench/synthesizers/coding_transcript.py` — mirror in transcript ("billed under NPI 1234567890, total $148, insurance Medicare Part B").

**Acceptance criteria:**
- `coding_v1` clean recall ≥ 3/4 (matches scribe_v1 and scheduling_v1 calibration ceilings)
- Injected recall stays ≥ 4/4 (UPCODE detection must not regress)
- One commit, ~40 lines

**Reproduction:**
```bash
python scripts/generate_pack.py --pack coding_v1 --size 8 --seed 7 \
    --mix clean=0.5,single=0.5,multi=0.0 --out out/coding_v1.live.jsonl
python scripts/run_determinism.py --pack-path out/coding_v1.live.jsonl --n 1 \
    --backend lithrim-pipeline --out out/coding_v1.live.cal3.ndjson
# inspect; should see 4 clean cases as 'approve' instead of 'needs_review'
```

### Item 2 — triage_v1 v3 artifact (close the 4/4 needs_review on cleans)

**Why second:** same pattern as item 1, slightly different fields. The FHIR RiskAssessment needs `prediction.probability` (`{value: 0.85}`), `prediction.period` (assessment window), and `prediction.rationale` (the red-flag enumeration that already exists in `_triage_scenarios.py`).

**Files to touch:**
- `lithrim_bench/synthesizers/triage_artifact.py`
- `lithrim_bench/synthesizers/triage_transcript.py` — mirror the rationale ("based on red flags X, Y, Z, the probability of acute coronary syndrome is high — I'd estimate 80-90%").

**Acceptance criteria:**
- `triage_v1` clean recall ≥ 3/4
- Injected recall stays ≥ 4/4 (MISSED_ESCALATION detection unchanged)

### Item 3 — re-run the 4-pack calibration sweep, update per-judge numbers

**Why third:** items 1+2 should push the mean per-judge accuracy and ensemble accuracy up. If the ensemble moves from 0.81 to 0.85+, that's a paper-grade observation.

**Acceptance criteria:**
- `out/judge_calibration_v3.json` exists
- `docs/JUDGE_CALIBRATION_2026-05-21.md` updated with a v3 section
- `TunedMockBackend(per_member_semantic_accuracy=<v3>, per_member_flag_attachment_rate=<v3>)` suggestion regenerated

**Reproduction:**
```bash
for p in scribe_v1 scheduling_v1 coding_v1 triage_v1; do
    python scripts/run_determinism.py --pack-path "out/$p.live.jsonl" --n 1 \
        --backend lithrim-pipeline --out "out/$p.live.cal3.ndjson"
done
python scripts/calibrate_judges.py \
    --runs out/{scribe,scheduling,coding,triage}_v1.live.cal3.ndjson \
    --packs out/{scribe,scheduling,coding,triage}_v1.live.jsonl \
    --out out/judge_calibration_v3.json
```

Wall clock: ~8 minutes.

### Item 4 — scale to N=10 + larger packs (50 per pack)

**Why fourth:** N=1 gives no CI. The paper §6 requires N≥10 per case for verdict_instability + bootstrap CI. Pack size 50 gives per-defect-class stratification.

**Cost:** 4 packs × 50 cases × 10 runs × ~25s/call = **~14 hours** of council time. Best run overnight in the background.

**Acceptance criteria:**
- 4 NDJSON files with 500 rows each
- `analyze_runs.py` reports `verdict_match_rate_ci95` with width ≤ 0.1 per pack
- `instability_rate` reported per pack (eval spec §2.4 reportability gate)

**Reproduction:**
```bash
for p in scribe_v1 scheduling_v1 coding_v1 triage_v1; do
    python scripts/generate_pack.py --pack "$p" --size 50 --seed 7 \
        --out "out/$p.n10.jsonl"
done
(
    for p in scribe_v1 scheduling_v1 coding_v1 triage_v1; do
        python scripts/run_determinism.py --pack-path "out/$p.n10.jsonl" --n 10 \
            --backend lithrim-pipeline --out "out/$p.n10.ndjson"
    done
) &  # background, ~14 hours

# Once done:
python scripts/calibrate_judges.py \
    --runs out/{scribe,scheduling,coding,triage}_v1.n10.ndjson \
    --packs out/{scribe,scheduling,coding,triage}_v1.n10.jsonl \
    --out out/judge_calibration_n10.json
```

**Backend rate-limit caveat:** with 2000 council invocations over 14 hours, the live backend's LLM budget may be a concern. Worth checking with whoever pays the bills before kicking off.

### Item 5 — paper drafting from measured anchors

**Why fifth:** items 1-4 produce the numbers the paper needs. After they land, the paper can be drafted top-to-bottom against measurable claims, not aspirational ones.

**Files to produce (in some `paper/` directory or back in `lithrim-bench/docs/paper_draft/`):**
- `01_abstract.md` — abstract minus the results sentence (drafting-ready today)
- `03_related_work.md` — Lail & Markham positioning, "we replicate the strong baseline at 0.81 on our benchmark"
- `04_method.md` — worst-of composition rule, citation to `artifact_evaluator.py:37-45`, the per-pack design matrix
- `05_benchmark.md` — Synthea provenance, 5 packs, 11 injectors, deterministic-by-construction labels, two calibration findings
- `06_experiment_design.md` — N≥10 protocol, three-layer decomposition (eval spec §2.2), reportability gate (§2.4)
- `07_results.md` — the measured tables from items 1-4
- `07b_threats_to_validity.md` — validator coverage gap (2/5 → 5/5 ceiling), calibration limits, ground-truth assumptions

**Acceptance criteria:**
- Each file ≤ 1500 words
- Every cited number traces to a commit hash + `out/*.analysis.json` artifact
- Methods section's code references compile (pytest the bench during paper review)

### Item 6 — stricter HL7 validator (Phase 3 territory; do not block Phase 2 on this)

**Why deferred:** Closes the 3/5 HL7 defect-class coverage gap. Requires either upgrading mapping 26 in `etlp-mapper` OR plumbing a HAPI v2 validator behind the same `LithrimValidateArtifactBackend` socket. Both are out-of-bench work. Track but don't block.

**If pursued in Phase 2:**
- Stand up HAPI v2 validator service alongside etlp-mapper
- Add a `--validator hapi` flag to `LithrimValidateArtifactBackend`
- Re-run the headline contrast on `hl7_adt_v1`; the gain should move from +28.6 pp toward the simulated +60 pp ceiling

## Phase 2 acceptance gate (when to declare done)

Phase 2 is done when:

1. `coding_v1` and `triage_v1` clean recall ≥ 3/4 each (items 1+2 land)
2. N=10 sweep on 4 packs at size 50 completes, CIs reported (item 4 lands)
3. Per-judge accuracy table at N=10 size-50 is the paper's row anchor (item 3 + item 4 combined)
4. Paper §3, §4, §5, §6, §7 drafts exist with measurable claim provenance (item 5 lands)

When all four hold, the paper can be submitted to arXiv. The bench is ready.

## Things to NOT do in Phase 2

- **Do not** regenerate the taxonomy snapshot unless the backend's `compliance_council.py` changes. The snapshot is the contract; drift is caught by the lint script.
- **Do not** add new injectors to the existing packs. The set is calibrated; new ones need their own calibration cycle (1-day minimum).
- **Do not** widen `expected_compliance_verdict` to set-valued unless the rule is spec-borderline per eval-spec §1.4. System flakiness ≠ borderline label.
- **Do not** commit `.live_env` or run JSON outputs (`out/`) — gitignored for a reason.
- **Do not** re-run live sweeps gratuitously. Each costs ~3 minutes of LLM time per pack. Cache `out/*.ndjson` and only re-run when the synthesizer or backend changes.

## First-thing-to-do checklist (cold start)

```bash
# 1. Confirm live stack
curl -s -o /dev/null -w "lithrim: %{http_code}\n" http://localhost:8002/
curl -s -o /dev/null -w "etlp:    %{http_code}\n" http://localhost:3031/

# 2. Refresh the API key if .live_env is missing or stale
#    (login: rahul.nbg@gmail.com / Demo@123 — local dev only)

# 3. Smoke the headline contrast (should hit the values in HANDOFF table)
python scripts/run_determinism.py --pack-path out/hl7_adt_v1.jsonl --n 1 \
    --backend worst-of \
    --worst-of-semantic tuned-mock --tuned-per-member-accuracy 0.802 \
    --tuned-flag-attachment-rate 0.218 \
    --worst-of-structural lithrim-validate-artifact --etlp-mapping-id 26 \
    --out out/sanity.ndjson
python scripts/analyze_runs.py --runs out/sanity.ndjson --pack out/hl7_adt_v1.jsonl
# Expect: ~12/12 clean correct, ~8/28 defects caught (28.6%).

# 4. If sanity check passes, start item 1 (coding artifact v3).
```

## When stuck

- Re-read `docs/HANDOFF_2026-05-21.md` for state.
- Re-read `docs/PAPER_OUTLINE.md` for the claim discipline (one claim, no scope creep).
- Re-read `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md` for the protocol acceptance criteria.
- The diagnose-before-edit gate (CLAUDE.md) is non-negotiable: post evidence in a fenced block before stating a diagnosis. Today's session caught itself once with this discipline (the "live structural validator catches 0%" finding before checking that the validator was mapping 26 not 25 — wrong story until the data was inspected).

## Open invitation to pivot

If Phase 2 surfaces a finding that re-frames the paper, the discipline is to **update PAPER_OUTLINE.md, do not silently shift the claim**. The outline is the contract; shifts get an explicit edit + a session log entry. This is how the bench has stayed coherent across 13 commits in one session without scope creep.
