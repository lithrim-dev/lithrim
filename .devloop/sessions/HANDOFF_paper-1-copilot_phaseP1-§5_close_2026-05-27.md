# HANDOFF — `paper-1-copilot` phase `P1-§5` → next-cycle kickoff

> Written by the monitor on cycle close. Load-bearing context for the
> next monitor session that takes over after compaction or after-hours
> break. Committed alongside the close-out commit.
>
> **This cycle ran much broader than originally scoped.** The §5 expansion
> work uncovered a fundamental architectural finding (the production
> council is a monoculture, not an ensemble) and ended up producing the
> corrective architecture spec end-to-end. Read this doc carefully.

---

## What just landed

- **Closed phase:** `P1-§5` — Silent Confident Certification §5 expansion. Originally scoped as a routine paper-section write-up of the 393-word P1-EXP-0 stub. Closed with substantially more work:
  1. Full corrective §5 paper section (~8K, six subsections) at `docs/paper_draft/05_section_5_silent_confident_certification_v2.md`
  2. N=12 multi-modal pilot validation across scribe / scheduling / coding / triage / HL7 packs
  3. Empirical refutation of the original monoculture council (`gpt-4o × 3` with role-differentiated prompts → all 36 votes at confidence 1.000)
  4. Architectural corrective: cross-provider trio + logprob-derived calibration + llama-veto-approve composition + v3 NKA prompt patch
  5. End-to-end validation: 5/10 silent-confident → 0/10; 2/2 false-positives → 0/2; 9/12 match → 11/12
  6. Council-V2 integration spec for `lithrim-backend` at `docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md`
  7. Bench-side fix: `BackendVerdict.findings_rich` + `structural_findings_rich` preserved through NDJSON
- **Verdict:** PROCEED — corrective claim is empirically grounded; ready for big-N replication post-BRS-2/5 and backend integration.
- **No commits.** All work is in working-tree drift (see S-P1-11). The next monitor must flush this in 3 atomic commits as PRIORITY-0 before any new cycle.

### Headline numbers (paper-load-bearing, locked for §5 corrective)

Original monoculture `gpt-4o × 3` council (N=12, prior P1-EXP-0 pilot baseline `out/pilot_thesis_n12.ndjson`):
- Silent-confident-certification (unanimous-approve on defect at conf 1.000): **5 / 10**
- Confidence ≡ 1.000 across all votes: **36 / 36** (degenerate)
- False positives on clean negatives: **1 / 2** (C2 only)
- Worst-of compliance verdict matches deterministic label: **9 / 12**

Corrective trio (gpt-4.1 + Mistral-Large-3 + Llama-4-Maverick-17B-128E-FP8) with v3 prompt + llama-veto-approve composition (N=12, `out/pilot_thesis_n12_trio_v3.ndjson`):
- **Silent-confident-certification: 0 / 10** (eliminated)
- **Calibrated confidence:** gpt-4.1 mean 0.93 range 0.51–1.00, Llama mean 0.95 range 0.73–1.00, Mistral N/A (Azure HTTP 400 code 3051 on `logprobs:true`)
- **False positives on clean negatives: 0 / 2** (both C1 and C2 correctly approved)
- **Worst-of match: 11 / 12** (single residual: S7 — fine-grained HL7 structural defect; documented limitation, motivates §6)

## What's next

**Next phase decision is open.** The §5 work unlocked multiple parallel paths. Five options, all valid:

- **OPTION A — P1-§6 (composition results)** *(recommended)*. The corrective §5 sets up §6 cleanly. Adapts existing `paper_draft/07_results.md` §7.3 + BRS-0b §7b.8. Routine cycle. ~1 day.
- **OPTION B — P1-§2 (Jute Copilot mechanism, full disclosure)**. HARD GATE per S-P1-3. Requires user confirmation on A2 disclosure boundary BEFORE drafting begins.
- **OPTION C — Other ready sections (P1-§1, §3, §4, §7, §9)**. All ready, lower priority than §6/§2.
- **OPTION D — P1-COUNCIL-V2 (backend integration)**. Blocked on BRS-2 + BRS-5 close per `lithrim-command-center` brs-arc stream. Spec ready; don't kickoff until BRS-2/5 ship.
- **OPTION E — big-N validation (~110 cases, ~$13)** on the new trio + v3 + llama-veto-approve. Useful for camera-ready Table 5.X. Not blocking arXiv-first draft.

Recommendation: complete the working-tree flush (3 atomic commits), then start P1-§6.

## Open seams for `paper-1-copilot`

| ID | Title | Severity | Status |
|---|---|---|---|
| S-P1-1 | Council-confidence $0 vs $5 path | low | **resolved 2026-05-27** |
| S-P1-2 | Decision-vs-attribution gap as §7 complementary vs co-headline | low | open |
| S-P1-3 | Full Jute Copilot mechanism disclosure (A2) — one-way; confirm before §2 | **medium** | open — confirm before §2 ships |
| S-P1-4 | Driver A7 (`ruff check . clean`) mismatch + `analyze_council_confidence.py` format drift | low | open |
| S-P1-5 | `httpx` not in `pyproject.toml`; live scripts depend on tribal `debuglithrim` pyenv (now compounded — new pilot scripts also depend on this pyenv) | low | open |
| S-P1-6 | Subset definitions (council-layer vs pipeline-layer silent) — codify upfront | medium | open (process) |
| **S-P1-7** | **NEW. Production council is a monoculture; corrective architecture validated; Council-V2 integration queued.** | **high** | open — blocked on BRS-2/5 |
| **S-P1-8** | **NEW. LLM judges cannot reliably catch fine-grained HL7 structural defects. Paper-bearing limitation, handled by §6 composition.** | low (handled) | documented in paper §5.5 |
| **S-P1-9** | **NEW. Mistral on Azure rejects logprobs (HTTP 400 code 3051). Confidence=None must be explicit, never synthesized to 1.0.** | low | open — captured in Council-V2 spec |
| **S-P1-10** | **NEW. Council 4-property ideal-fix: 2/4 realized (cross-provider diversity ✓, calibrated confidence ✓); 2/4 pending (disjoint evidence access, span anchoring).** | medium | open — future-work / paper §8 |
| **S-P1-11** | **NEW. `.devloop/` scaffold + bench-side P1-§5 artifacts (5 scripts, 12 output files, 2 modified base files, 2 new docs) are all uncommitted.** | medium | open — PRIORITY-0 for next monitor |

## Load-bearing context the next monitor MUST know

### 1. The §5 corrective is paper-deployable but conditional on §6 worst-of composition

§5.5 explicitly documents the S7 limitation (HL7 malformed-date — LLM judges of any provider approve at confidence 1.000) and frames it as the §6 motivation. The paper claim is *NOT* "LLM-as-judge councils are reliable" — it's "*cross-provider councils with calibrated confidence + faithfulness-judge-veto composition eliminate silent-confident certification of semantic faithfulness defects at zero false-positive cost; composed with deterministic structural validation, the system handles the structural-defect class LLMs cannot.*" Both layers are necessary; neither is sufficient alone. **§6 cannot be deferred** — without it, §5's claim doesn't ship.

### 2. The v2 prompt is archived as evidence of an attempted over-correction; do NOT resurrect it

`scripts/test_n12_trio_v2.py` was the verbose "conservative default + clinical equivalence list + HL7 conventions" patch. Bench-measured it over-corrects: regressions on S1 (HALLUCINATED_DETAIL silently approved), S2 (WRONG_DOSAGE softened to needs_review across all judges), S7/S8 (structural HL7 approved by Mistral+Llama). The v2 outputs are kept in `out/pilot_thesis_n12_trio_v2.*` as the empirical evidence that prompt-engineering has unintended spillover; they should not become the production prompt. The Council-V2 spec § 3.2 explicitly forbids v2.

### 3. v3 + llama-veto-approve is the production-candidate configuration

The corrective claim hinges on three coupled choices that must ship together:
- **v3 prompt**: v1 baseline + ONE appended paragraph addressing HL7 NKA convention. Exact text at `scripts/test_n12_trio_v3.py:build_prompt()`.
- **Cross-provider trio**: `gpt-4.1` + `Mistral-Large-3` + `Llama-4-Maverick-17B-128E-Instruct-FP8` on Azure.
- **Composition: llama-veto-approve**: if faithfulness_judge (Llama) approves and no judge rejects → final approve; else worst-of.

Any one of these alone is insufficient. Don't ship partial.

### 4. Bench fixes that preserve API Finding shape are uncommitted but tested

`lithrim_bench/backends/base.py` got `findings_rich: list[dict]` + `structural_findings_rich: list[dict]` added to `BackendVerdict` (additive, doesn't touch the existing `flags` / `structural_findings` flat-code surfaces). `lithrim_bench/backends/lithrim_pipeline.py:_parse` populates both from `payload.semantic.findings` and `payload.structural.findings`. BRS-0b §7 byte-identical invariance test still passes (verified). These fixes belong in Commit A of the working-tree flush.

### 5. The four scripts form a reusable analysis suite

- `scripts/pilot_thesis_validation.py` — N=12 baseline pilot script (against original gpt-4o council). Reusable for any future "compare this council config against baseline" exercise.
- `scripts/test_n12_trio.py` — Cross-provider trio runner (parameterizable by prompt). Three siblings (`_v2`, `_v3`) hold the three prompt experiments. Don't delete the siblings — they're the empirical record.
- `scripts/analyze_composition_strategies.py` — Offline composition-strategy analyzer (worst-of, majority, llama-tiebreak, llama-veto-approve, conf-gated@0.85). Operates on the NDJSON output of test_n12_trio*.py. Reusable for any future N-case sweep.

### 6. Working-tree drift is now substantial; flush before any new cycle

Counted in S-P1-11:
- 2 modified bench source files (`base.py`, `lithrim_pipeline.py`)
- 5 new scripts in `scripts/`
- 12 new output files in `out/` (NDJSON + summary.json + summary.md × 4 configurations: pilot_thesis_n12, n12_trio, n12_trio_v2, n12_trio_v3)
- 2 new docs (paper §5 v2, Council-V2 spec)
- Plus the prior `.devloop/` scaffold drift (KICKOFF_*.md, README.md, personas/, seams/, spikes/, templates/, tasks/, STREAM_brs-arc.md)
- Plus the doc-side drift from earlier (PAPER_OUTLINE.md modified, label_owner_matrix.md modified, HANDOFF_BRS_0b_2026-05-26.md untracked, PAPER_FRAMING_DECISIONS_2026-05-26.md untracked)

The bench artifacts (Commits A, B, C in the proposed grouping below) are P1-§5 cycle work and should land first. The `.devloop/` scaffold + doc drift are pre-existing S-BRS-2 + ambient drift; flush as separate `chore(devloop):` and `docs:` commits if user wants the scaffold tracked.

### 7. Council-V2 is real engineering, not just a paper finding

`docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md` is a full driver-template document (§1-§9: context, pre-flight, deliverables file-by-file, plan-review checkpoint, scope guardrails, atomic commit structure, acceptance criteria + verification, first-move, references). When BRS-2 + BRS-5 close, this spec becomes the next cycle in line. The next monitor doesn't need to author it from scratch — it's already a paste-ready driver for a `lithrim-backend` exec session.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_paper-1-copilot.md` — especially the P1-§5 cycle row + new seams S-P1-7 through S-P1-11 + updated First Move.
3. Read this handoff.
4. Read the corrective §5 paper section: `docs/paper_draft/05_section_5_silent_confident_certification_v2.md`. This is the deliverable.
5. Read the Council-V2 integration spec: `docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md`. This is the next-when-unblocked cycle.
6. Skim the empirical evidence: `out/pilot_thesis_n12_trio_v3.summary.md` (the head-to-head table is the §5 figure).
7. Run `git log --oneline -8` + `git status --short` to see commit timeline + the working-tree drift you're about to flush.
8. **Don't start P1-§6 until the 3 working-tree commits land.** Stage them in this order: A (bench fixes), B (scripts + outputs), C (docs). Present commit messages to the user; await `go` per the no-auto-commit preference.
9. After the flush, decide between the 5 next-cycle options listed in this handoff's "What's next" section. Recommend P1-§6 unless user signals otherwise.
10. If unsure: ask the user "Working tree drift flushed in 3 commits. Next cycle: P1-§6 (recommended), P1-§2 (HARD GATE), or another? Or hold for BRS-2/5 close + then P1-COUNCIL-V2?"

## Cross-stream context (worth knowing)

- **brs-arc stream is parallel-progressing.** Per the lithrim-command-center monitor's update earlier this session, BRS-1 closed (commit `bb2bb38` in `lithrim-backend` — `verdict_flipped_by_stage` + `structural_template_pin` shipped). BRS-2 (failure-cluster rekey) + BRS-5 (evidence-span surfacing) are in flight. BRS-3 dropped. P1-COUNCIL-V2 is blocked behind BRS-2 + BRS-5 close.
- **Lithrim UI eval-runs visibility was investigated earlier this session** (separate exploration; no cycle opened). Finding: bench's `/v1/pipeline/evaluate` calls don't create `EvalRun` documents, so they're invisible in the UI's per-agent results page. Retro-ingest path documented in conversation but not formalized as a stream — `bench-product-integration` stream was proposed but never spun up. If user wants to revive: register `hl7_adt_a04_v1` pack + retro-ingest the bench's `out/p1_exp_0_council_confidence.ndjson` + curate case IDs.

## References

- Stream state: [`.devloop/state/STREAM_paper-1-copilot.md`](../state/STREAM_paper-1-copilot.md)
- Prior cycle handoff: [`.devloop/sessions/HANDOFF_paper-1-copilot_phaseP1-§5_kickoff_2026-05-27.md`](HANDOFF_paper-1-copilot_phaseP1-§5_kickoff_2026-05-27.md) — the P1-EXP-0 → P1-§5 handoff
- Paper §5 corrective: [`docs/paper_draft/05_section_5_silent_confident_certification_v2.md`](../../docs/paper_draft/05_section_5_silent_confident_certification_v2.md)
- Paper §5 (prior 393-word stub): [`docs/paper_draft/05_section_5_silent_confident_certification.md`](../../docs/paper_draft/05_section_5_silent_confident_certification.md) — superseded but kept as evidence of evolution
- Council-V2 integration spec: [`docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md`](../../docs/specs/COUNCIL_V2_INTEGRATION_SPEC.md)
- N=12 baseline (gpt-4o × 3 monoculture): [`out/pilot_thesis_n12.ndjson`](../../out/pilot_thesis_n12.ndjson), [`out/pilot_thesis_n12.summary.md`](../../out/pilot_thesis_n12.summary.md)
- N=12 v1 trio (worst-of): [`out/pilot_thesis_n12_trio.ndjson`](../../out/pilot_thesis_n12_trio.ndjson)
- N=12 v2 trio (over-correction; archived): [`out/pilot_thesis_n12_trio_v2.ndjson`](../../out/pilot_thesis_n12_trio_v2.ndjson)
- **N=12 v3 trio (production candidate)**: [`out/pilot_thesis_n12_trio_v3.ndjson`](../../out/pilot_thesis_n12_trio_v3.ndjson), [`out/pilot_thesis_n12_trio_v3.summary.md`](../../out/pilot_thesis_n12_trio_v3.summary.md)
- Pilot picklist: `/tmp/pilot_picklist.json` (write-side; should be committed alongside the scripts in Commit B)
- Paper framing authority: [`docs/PAPER_FRAMING_DECISIONS_2026-05-26.md`](../../docs/PAPER_FRAMING_DECISIONS_2026-05-26.md) A1 amendment + D2 + PAPER_OUTLINE §5 amendment
