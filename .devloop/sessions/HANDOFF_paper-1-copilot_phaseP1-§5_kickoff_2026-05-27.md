# HANDOFF — `paper-1-copilot` phase `P1-EXP-0` → phase `P1-§5` kickoff

> Written by the monitor on cycle close. Load-bearing context for the
> next monitor session that takes over after a compaction or after-hours
> break. Committed alongside the close-out commit.

---

## What just landed

- **Closed phase:** `P1-EXP-0` — Council-confidence experiment on 28 missed HL7 ADT^A04 defects (gating §5). Commits `32d1bf7..7f6858c` (4 atomic deliverable commits) + `4fb93cc` (executor close-out).
- **Critique verdict:** `NON-BLOCKING FINDINGS` ([`.devloop/sessions/critique-paper-1-copilot-phaseP1-EXP-0-2026-05-27.md`](critique-paper-1-copilot-phaseP1-EXP-0-2026-05-27.md))
- **Audit verdict:** `DRIFT (1 substantive, acknowledged)` — `scripts/analyze_council_confidence.py` is not `ruff format`-clean despite session-log A7 sub-claim saying otherwise. User elected to acknowledge and fold into S-P1-4 rather than commit a one-line fix. **Future bench cycles touching that file should re-format it as part of S-P1-4's eventual cleanup.**
- **Session log:** [`.devloop/sessions/session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json`](session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json)

### Headline numbers (paper-load-bearing — locked for §5)

- Defect-bearing HL7 ADT^A04 cases: **28** (of 40 in `out/hl7_adt_v1.jsonl`; 12 clean negatives held out)
- **Council-silent subset** (every per_judge[*].verdict == approve on a defect-bearing case): **10 / 28 (35.7%)**
- Per-judge confidence on the silent subset: **mean = median = min = max = 1.000** across all three judges (policy, risk, behavior); 30 / 30 votes in the `0.9–1.0` histogram bucket
- Council agreement breakdown on the 28 defects: 10 unanimous-approve / 15 split / 3 unanimous-reject
- At-least-one-judge-approves on **25 / 28 = 89%** of defects
- Mapping 93 (Jute Copilot strict HL7) structural verdict on the 28: **21 WARN + 7 BLOCK = 28/28 detected**
- Pipeline-gate disposition on the 10 council-silent cases: **compliance_verdict=needs_review on 10/10** (worst-of composition with structural WARN drags the gate off council's unanimous approval — this is the §6 story)
- Driver §2 D3 literal filter (council-silent AND `compliance_verdict==approve`): **0 / 28** by construction (the §6 solution prevents the §5 failure at the pipeline gate). Reported as `pipeline_silent_subset_size` in `summary.json` for audit trail; NOT the §5 headline.

## What's next

- **Next phase:** `P1-§5` — Expand the 393-word draft at [`docs/paper_draft/05_section_5_silent_confident_certification.md`](../../docs/paper_draft/05_section_5_silent_confident_certification.md) into the full §5 in the paper draft. Pressure-test against §6 (worst-of recovery).
- **Driver bundle:** *not yet drafted* — `paper-1-copilot-phaseP1-§5-silent-confident-certification-driver` doesn't exist in `prompts/index.json` yet.
- **Driver path (to be created):** `.devloop/prompts/paper-1-copilot_phaseP1-§5_silent_confident_certification_driver.md`
- **Blocked by:** none. P1-EXP-0 produced all the source material P1-§5 needs.
- **Hardness:** routine (no spec edits, no public API changes, no launch touched — §5 is a paper section expansion).
- **Parallel ready alternative:** `P1-§2` (Jute Copilot mechanism — full disclosure). HARD GATE per S-P1-3; requires explicit user confirmation on A2 (full mechanism disclosure boundary) BEFORE drafting begins.

## Open seams for `paper-1-copilot`

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-P1-1 | Council-confidence $0 vs $5 path | low | — | P1-EXP-0 planning | **resolved 2026-05-27** ($0 path unavailable; $5 path executed) |
| S-P1-2 | A6 framing: prominence of decision-vs-attribution gap | low | drafting decision | A6 | open |
| S-P1-3 | Full Jute Copilot mechanism disclosure (A2) — one-way; confirm with user before §2 | **medium** | §2 disclosure boundary | A2 amendment | open — confirm before §2 ships |
| S-P1-4 | Driver A7 (`ruff check . clean`) mismatch — 20 pre-existing errors + 63 unformatted; **+ analyze_council_confidence.py not format-clean (P1-EXP-0 close-out audit addendum)** | low | future bench drivers (rephrase A7 as files-touched-clean) OR one-shot cleanup cycle including `analyze_council_confidence.py` | P1-EXP-0 close-out | open |
| S-P1-5 | `httpx` not in `pyproject.toml`; live scripts depend on tribal `debuglithrim` pyenv | low | `pyproject.toml` `[live]` extras OR `CLAUDE.md` Stack note | P1-EXP-0 close-out | open |
| S-P1-6 | Subset definitions (council-layer vs pipeline-layer silent) — codify upfront in future §5/§6/§7 cycles | **medium** | process; codified in `scripts/analyze_council_confidence.py:_is_council_silent` + `:_is_pipeline_silent` | P1-EXP-0 close-out | open (process) |

## Load-bearing context the next monitor MUST know

### 1. The §5 measurement is council-layer, not pipeline-layer — this was a real spec ambiguity, now locked

The driver's §2 D3 literal filter required both `compliance_verdict == "approve"` (pipeline gate) AND `per_judge[*].verdict == "approve"` (council layer). Filtering the §5 failure-mode population through its own §6 solution yields 0 by construction, because mapping 93's WARN drags the worst-of composition to `needs_review` on every case where the council unanimously approves a real defect. The §5 framing per PAPER_FRAMING_DECISIONS_2026-05-26.md A1 — "the failure mode the copilot's output prevents" — implies the council-layer subset is load-bearing for §5 (10/28), and the pipeline-layer near-zero result is the §6 story (worst-of recovers all of them). The executor surfaced this mid-cycle as Deviation #4; the user approved option A; the analyzer now exposes both subsets explicitly via `_is_council_silent` and `_is_pipeline_silent`. **This is now S-P1-6 (medium severity, process)** — when P1-§5 and P1-§6 cycles are drafted, the driver template should be layer-explicit upfront so the same conflation cannot recur.

### 2. The sharpest finding is broader than the §5 headline currently captures

Per-judge confidence is **1.000 across all 40 cases in the sweep** — not just the 10 council-silent ones. Every council vote (clean negative + defect, approve + reject) came back at maximum confidence. This means the council's confidence signal is **degenerate** in the production stack: confidence carries no information about correctness. Two implications worth surfacing in P1-§5:
- The §5 thesis can be a **category claim** ("the council emits maximum confidence on every clinical artifact it sees") with the 10/28 silent subset as the demonstration, not just an observation about the missed defects.
- `lithrim-backend/app/services/compliance_council.py:248` ships `"fallback_on_low_confidence": False` — but even if it were True, no row would ever trigger it, because no row has low confidence. This is upstream context for any reader who asks "why isn't there a confidence gate?" The data is in `out/p1_exp_0_council_confidence.ndjson`; aggregation across all 40 rows takes ~10 lines of additional analyzer code.

This was logged as Q4 Ambiguity 3 in the critique — forwarded to P1-§5 expansion rather than retroactively edited into the P1-EXP-0 §5 draft.

### 3. The user prefers acknowledged-drift to fix-and-recommit for audit-trail nicks

User chose option B in close-phase (acknowledge the `analyze_council_confidence.py` ruff-format drift, fold into S-P1-4, no commit) over option A (apply the one-line fix + re-close). The pattern this establishes for future cycles: small audit-trail inaccuracies caught in close-out audit can be folded into the appropriate existing seam if a cleanup cycle is already in the queue for that area. Don't churn the git history for one-line cosmetic fixes if the cleanup is going to happen anyway under an existing seam. **If the inaccuracy is substantive (wrong numbers, wrong claim) — different story; commit the fix.** This was a sub-claim wording issue ("touched files individually clean") that fails for 1/5 files; the cycle's load-bearing claims (10/28 silent, confidence 1.000, mapping 93 catches all 10) are all unaffected.

## How to resume

1. Read `.devloop/personas/MONITOR.md`.
2. Read `.devloop/state/STREAM_paper-1-copilot.md` (especially the closed P1-EXP-0 row, the open seams, and the updated First move).
3. Read this handoff doc.
4. Read the most recent session log: [`session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json`](session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json).
5. Read the critique: [`critique-paper-1-copilot-phaseP1-EXP-0-2026-05-27.md`](critique-paper-1-copilot-phaseP1-EXP-0-2026-05-27.md).
6. Run `git log --oneline -10` in `lithrim-bench` to see commit timeline.
7. Wait for user input. Don't autonomously start P1-§5 or P1-§2.

## References

- Stream state: [`.devloop/state/STREAM_paper-1-copilot.md`](../state/STREAM_paper-1-copilot.md)
- Prior cycle session log: [`.devloop/sessions/session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json`](session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json)
- Prior cycle critique: [`.devloop/sessions/critique-paper-1-copilot-phaseP1-EXP-0-2026-05-27.md`](critique-paper-1-copilot-phaseP1-EXP-0-2026-05-27.md)
- Driver (shipped): [`.devloop/prompts/paper-1-copilot_phaseP1-EXP-0_council_confidence_driver.md`](../prompts/paper-1-copilot_phaseP1-EXP-0_council_confidence_driver.md)
- §5 draft (393 words, expansion target): [`docs/paper_draft/05_section_5_silent_confident_certification.md`](../../docs/paper_draft/05_section_5_silent_confident_certification.md)
- Headline numbers source: [`out/p1_exp_0_council_confidence.summary.{json,md}`](../../out/p1_exp_0_council_confidence.summary.json) + raw NDJSON [`out/p1_exp_0_council_confidence.ndjson`](../../out/p1_exp_0_council_confidence.ndjson)
- Paper framing authority: [`docs/PAPER_FRAMING_DECISIONS_2026-05-26.md`](../../docs/PAPER_FRAMING_DECISIONS_2026-05-26.md) A1 amendment + D2 + PAPER_OUTLINE §5 amendment
