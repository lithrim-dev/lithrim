# STREAM — `paper-1-copilot` (Paper 1: Closing the Validator-Authoring Bottleneck)

> **Live monitor state for the Paper 1 stream** (post 2026-05-26 amendment
> reframing Paper 1 from framework paper to Jute Copilot paper per A1–A6 in
> `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md`).
>
> **Stream owner:** monitor
> **Created:** 2026-05-27
> **North star:** ship arXiv-first publication of the Jute Copilot mechanism +
> HL7 ADT^A04 demonstration + silent-confident-certification motivation.
> Paired with framework deck refresh + first outreach wave + LinkedIn
> long-form. Establishes priority date on generative conformance-validator
> composition.

## Authority docs

- `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md` — A1–A6 amendments, Paper 1 = Jute Copilot paper, full mechanism disclosure
- `docs/PAPER_OUTLINE.md` — locked paper outline (preserve verbatim; Paper 1 amendment is layered on top)
- `docs/HANDOFF_2026-05-23.md` — origin of the 1-day council-confidence experiment + cost estimate (~$5 or $0 if recoverable from `out/run1_archive/hl7*`)
- `etlp-mapper/src/etlp_mapper/handler/copilot.clj` + `copilot/engine.clj` — Jute Copilot implementation (full mechanism source for §2)
- `scripts/_gen_strict_hl7_mapping.py` — reproduction script (Paper 1 release artifact)
- `validators/hl7_adt_a04_strict.yaml` — generated validator (Paper 1 release artifact)
- `out/run1_archive/hl7*` — possible $0 source for council-confidence values; check `LithrimPipelineBackend._parse` raw payloads first

---

## Section structure (per A1 — locked)

| § | Title | Source material | Status |
|---|---|---|---|
| §1 | The validator-authoring bottleneck (motivation) | drafting fresh | not started |
| §2 | Generative validator composition: the Jute Copilot mechanism (full disclosure) | `etlp-mapper/src/etlp_mapper/handler/copilot.clj` + `copilot/engine.clj`, `STRICT_HL7_VALIDATOR_2026-05-22.md` | not started |
| §3 | Benchmark + evaluation protocol (Synthea, 5 packs, deterministic labels, N=10 test-split) | existing `paper_draft/05_benchmark.md` post BRS-0b | adapt from existing |
| §4 | Demonstration: mapping 25 → mapping 93 in one call | `scripts/_gen_strict_hl7_mapping.py` + `validators/hl7_adt_a04_strict.yaml` + `STRICT_HL7_VALIDATOR_2026-05-22.md` | not started |
| §5 | Silent confident certification (the failure mode the copilot's output prevents) | **gated on 1-day council-confidence experiment (P1-EXP-0)** | blocked on P1-EXP-0 |
| §6 | Composition results: worst-of recovers 28/28 at 12/12 clean correctness | existing `paper_draft/07_results.md` §7.3 + BRS-0b §7b.8 framing | adapt from existing |
| §7 | Complementary finding: decision-vs-attribution gap (5.73×) | existing measurement | adapt from existing |
| §8 | Threats to validity | existing `paper_draft/07b_threats_to_validity.md` post BRS-0b | adapt |
| §9 | Release: benchmark + reproduction script + generated validator YAML | scripts + YAML already exist | bundling task |

---

## Current cycle

| Cycle | Title | Status | Blocked by |
|---|---|---|---|
| **P1-EXP-0** | Council-confidence experiment on the 28 missed HL7 ADT^A04 defects (gating §5) — bench plumbing + N=1 live council sweep + aggregation. Driver: `.devloop/prompts/paper-1-copilot_phaseP1-EXP-0_council_confidence_driver.md`. **SHIPPED 2026-05-27** (commits 32d1bf7 → 7f6858c, verdict PROCEED-WITH-CAVEATS — A7 caveat is pre-existing repo lint debt, see S-P1-4). Headline: council unanimous-approve on 10/28 (35%) of HL7 defects at per-judge confidence 1.000; mapping 93 caught all 10 via WARN. Session log: `.devloop/sessions/session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json`. | **shipped** | — |
| **P1-§2** | Write §2 — Jute Copilot mechanism (full disclosure: generate→test→refine + merge mode + confidence-graded retry + system prompt + Jute DSL spec injection) | ready (parallel with P1-EXP-0) | none |
| **P1-§4** | Write §4 — mapping 25 → mapping 93 demonstration | ready (parallel) | none |
| **P1-§1** | Write §1 — validator-authoring bottleneck motivation | ready (parallel) | none |
| **P1-§5** | Write §5 — silent confident certification. **UNBLOCKED by P1-EXP-0** (headline numbers in `out/p1_exp_0_council_confidence.summary.{json,md}`; draft already lives at `docs/paper_draft/05_section_5_silent_confident_certification.md` per P1-EXP-0 Deliverable 4 — next cycle is to expand to the full §5 in the paper draft and pressure-test against §6's worst-of result). | ready | — |
| **P1-§3** | Adapt §3 — benchmark + evaluation protocol from existing post-BRS-0b paper draft | ready (parallel) | none |
| **P1-§6** | Adapt §6 — composition results from existing §7.3 | ready (parallel) | none |
| **P1-§7** | Adapt §7 — decision-vs-attribution complementary finding | ready (parallel) | none |
| **P1-§8** | Adapt §8 — threats to validity from existing §7b post-BRS-0b | blocked on P1-§2 + §4 + §5 (threats follow the rest) |
| **P1-§9** | Bundle §9 release artifacts (script + YAML + benchmark generator) | ready (parallel) | none |
| **P1-ABSTRACT** | Abstract rewrite (lead with Jute Copilot per A1's lead argument) | blocked on §1+§5+§6 (abstract follows) |
| **P1-FINAL** | arXiv submission + paired distribution (framework deck refresh + first outreach wave + LinkedIn long-form) | blocked on all sections | — |

---

## Open seams

| ID | Title | Severity | Fix loc | Opened in | Status |
|---|---|---|---|---|---|
| S-P1-1 | ~~Council-confidence values may already be persisted in `out/run1_archive/hl7*` and `LithrimPipelineBackend._parse` — if so, the 1-day experiment is $0 not $5; need to check FIRST~~ **RESOLVED 2026-05-27:** $0 path unavailable. No HL7 NDJSON in `out/run1_archive/`; no `out/hl7*.ndjson` produced by `LithrimPipelineBackend`; `JudgeOutput`/`_parse` drop `confidence` at capture time. API contract DOES emit `confidence` (`lithrim-backend/app/services/pipeline/models.py:28-40`), so re-run path works. Cost is firmly ~$5 + ~30 min plumbing. See driver §0. | low | `out/run1_archive/`, `lithrim_bench/backends/lithrim_pipeline.py:181-185`, `lithrim_bench/backends/base.py:21-25` | P1-EXP-0 planning | **resolved — drives P1-EXP-0 scope to 3 deliverables (plumbing + run + writeup)** |
| S-P1-2 | Open framing question (A6): how prominent is the decision-vs-attribution gap in Paper 1 — §7 complementary finding (monitor's lean) vs co-headline. Decision needed at abstract-rewrite time | low | drafting decision | A6 | open |
| S-P1-3 | Full Jute Copilot mechanism disclosure (per A2) is a one-way disclosure. Once §2 is drafted and arXiv-posted, the priority claim lands but the implementation surface is public. Verify with user before §2 commit. | medium | §2 disclosure boundary | A2 amendment | open — confirm with user before §2 ships |
| S-P1-4 | Driver acceptance criterion A7 (`ruff check . clean`) doesn't match repo state — 20 pre-existing errors + 63 unformatted files. Future executors will spuriously fail A7 or have to add the same caveat. | low | future bench drivers (rephrase A7 as files-touched-clean) OR one-shot ruff cleanup cycle | P1-EXP-0 close-out 2026-05-27 | open |
| S-P1-5 | `httpx` is not in `lithrim-bench/pyproject.toml` deps but required for any LithrimPipelineBackend / live script. User maintains pyenv virtualenvs (`debuglithrim`/`lithrim`/`lit`) with the full live-stack dep set; that knowledge is tribal. | low | `lithrim-bench/pyproject.toml` `[project.optional-dependencies]` `live = ["httpx>=0.28"]` OR `CLAUDE.md` "Stack" section note about the pyenv name | P1-EXP-0 close-out 2026-05-27 | open |
| S-P1-6 | Silent-confident-certification subset definition: the driver §2 D3 literal filter requires `compliance_verdict == "approve"` but that's the pipeline gate AFTER composition (the §6 solution), yielding 0/28 by construction. The §5 framing per A1 is council-layer; council-only filter yields 10/28. Resolved by user-approved option A this cycle; recorded as a process finding so future §5/§6/§7 cycles distinguish council-layer vs pipeline-layer subsets up front. | medium | process; analyzer codifies both subsets at `scripts/analyze_council_confidence.py:_is_council_silent` + `_is_pipeline_silent` | P1-EXP-0 close-out 2026-05-27 | open (process) |

---

## First move (next monitor action)

1. ~~**Verify S-P1-1.**~~ Done 2026-05-27. Resolved.
2. ~~**Draft the P1-EXP-0 driver.**~~ Done 2026-05-27 (v1, routine hardness).
3. ~~**Run P1-EXP-0.**~~ **Shipped 2026-05-27** (4 commits 32d1bf7 → 7f6858c; verdict PROCEED-WITH-CAVEATS; session log `session-paper-1-copilot-phaseP1-EXP-0-2026-05-27.json`). Headline: 10/28 (35%) council unanimous-approve on HL7 defects at confidence 1.000; mapping 93 caught all 10.
4. **Run `/devloop-audit paper-1-copilot P1-EXP-0`** to mechanically check the 7-item audit on the shipped cycle. The A7 caveat (repo-wide ruff debt) should audit as benign — pre-existing per git-stash verification. The mid-cycle scope deviation (council-only vs pipeline-literal silent subset) was user-approved option A and is fully logged in the session log under plan_review.deviations.
5. **Then `/devloop-close-phase paper-1-copilot P1-EXP-0`** to roll into the STREAM update + advance `streams.json` `current_phase` past P1-EXP-0.
6. **Decide cycle ordering for the unblocked sections.** P1-§5 is now unblocked; §1, §2, §3, §4, §6, §7, §9 are all parallelizable doc work. Recommended: P1-§5 (expand the existing 393-word draft into the full §5 in the paper draft, cite §6 worst-of result) + P1-§2 (Jute Copilot mechanism — HARD GATE per S-P1-3, requires user confirmation on full disclosure before drafting).
7. **For P1-§2 specifically, confirm with the user** before drafting that full mechanism disclosure (A2) is still the call. S-P1-3, medium severity, still open.
8. **For S-P1-5 (httpx not in pyproject):** consider either pinning httpx in a `[live]` extras_require on lithrim-bench/pyproject.toml or adding a "Stack — live scripts run under `PYENV_VERSION=debuglithrim`" line to CLAUDE.md. The session log captures the tribal knowledge; this would surface it.

---

## References

- Persona: `.devloop/personas/MONITOR.md`
- Task pack: `.devloop/tasks/TASK_PACK_paper-1-copilot.json`
- Paper framing decisions: `docs/PAPER_FRAMING_DECISIONS_2026-05-26.md`
- Paper outline: `docs/PAPER_OUTLINE.md`
- Current paper draft: `docs/paper_draft/` (post-BRS-0b state)
- Jute Copilot source: `../etlp-mapper/src/etlp_mapper/handler/copilot.clj` (resolve as needed)
- Reproduction script: `scripts/_gen_strict_hl7_mapping.py`
- Generated validator artifact: `validators/hl7_adt_a04_strict.yaml`
