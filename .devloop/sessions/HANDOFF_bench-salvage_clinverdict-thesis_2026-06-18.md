# HANDOFF — ClinVerdict × Lithrim thesis (cross-repo, monitor/driver)

**Date:** 2026-06-18 · **Owner:** Rahul Gaur · **Root for the next session:** `lithrim-bench`
**What this is:** the single orientation doc to drive the whole ClinVerdict→Lithrim thesis from a fresh session. Self-contained — read this + `/devloop-status bench-salvage` + the two command-center docs cited below and you have the full picture.

---

## The thesis in one paragraph

Lithrim is the **calibration + auditable-conformance layer for regulated (clinical) AI**. A **Calibrator** (a clinician, *not* an engineer) defines what "correct" means, enforces it on 100% of agent outputs via a deterministic floor on top of an LLM-judge council, and produces a **hash-sealed audit trail**. The business is a **three-part flywheel**: an **open-core product** (devs + SMEs adopt) → a **calibration-as-a-service** expert network (ongoing, quarter-over-quarter) → a **compounding audit ledger + golden-case corpus** (the real moat — *not* the judge/floor algorithm). Strategic posture confirmed by external research: a services business is **long** the model-improvement curve where a product moat is short it; the durable claims are metric-blindness, reference-instability, and auditability — *not* "LLM judges are permanently bad."

---

## Verified state — what's DONE (do not re-derive)

**ClinVerdict → lithrim-bench (the proof):**
- `scripts/extract_clinverdict.py` → `out/clinverdict_v1.jsonl` — all 10 ClinVerdict cases extracted to physician-asserted, lithrim-bench-native rows (FHIR DocumentReference artifact shape; top-level `expected_compliance_verdict`/`expected_safety_flags`; transcript + prior Gemini judge + Sharif's gold verdict + failure tags). Source: `../ClinVerdict-Physician-Curated-Clinical-AI-Evals-Suite`.
- Workspaces: **`clinverdict`** (original) + **`clinverdict_clean`** (CURRENT ACTIVE, pack `healthcare`, agent `healthcare_default`, **all 10 ClinVerdict cases loaded + 11 graded runs** as of 2026-06-18 — the shell footage source). `out/workspaces/clinverdict*/`. (Pre-thesis active was `demo-clinical`.)
- **WS-2 done** in `../lithrim-pack-healthcare/healthcare/`: registered `PROXY_MISATTRIBUTION` (Tier-1 never-event, owners faithfulness+risk) + `HISTORY_OMISSION` (Tier-2) in `taxonomy_snapshot.json` + `ontology.json` + faithfulness lens. **LOCAL, not committed/pushed.**
- **Case 9 graded live: WARN → `reject`** after WS-2 (`verdict_match_rate 1.0`; active findings `PROXY_MISATTRIBUTION` + `INCOMPLETE_DOCUMENTATION`; composite "BLOCK (was PASS pre-grounding)"). The council now matches Sharif's physician gold, for the right reason. UI-validated in the shell at `:5180`.
- BFF restarted **with** `LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare` (plain `make restart bff` drops pack discovery — see chip `task_f8a612ac`).

**Silent Drop (a mapped capability — RE-PRIORITIZED 2026-06-18: mostly deferred, see Front A):**
- Audit logged as seams **`S-BS-SD-1`…`S-BS-SD-7`** in `.devloop/state/STREAM_bench-salvage.md` (`## Open seams`). Verdict: of 11 pieces, **6 LIVE/reusable, 2 dormant (just wire), 1 clean port, 3 net-new**. The `source_message` inter-stage mode + `OMISSION_TYPE_CODES` discipline are **vendored-but-dormant** (Phase-1 = un-dormant, ~no new code). Data precondition: skill-1 extraction isn't in the ClinVerdict repo (Phoenix-trace only).

**Strategy + external validation (command-center):**
- North Star spec: `docs/specs/SPEC_lithrim_north_star.md` (Calibrator/Engineering two-sided model; services-first).
- **Research verification:** `docs/research/REPORT_thesis_claim_verification_2026-06-18.md` — claims 2,3 SUPPORTED; claim 1 (judge safety-blindness / the 85.7%) CONTESTED (frontier judges 94–97%, dominant failure is over-flagging not blindness); claims 4,5,6 GAPS (verification was rate-limited on 4–6). **Biggest risk = claim 1's direction; load-bearing gap = claim 6 (regulatory mandate).**
- **Pitch:** `docs/pitch/ZYNG_PITCH_BUNDLES_2026-06-18.md` — 30/60/120s zyng bundles, research-reframed (lead with liability/auditability + the Calibrator, drop "we beat the judge"). zyng-mcp installed + registered in both `lithrim-bench/.mcp.json` and `lithrim-command-center/.mcp.json`; footage `../zyng/out_lithrim_demo/bench_journey_silent.mp4`.

**Memories** (in the ClinVerdict project memory dir, absolute): `/Users/aregee/.claude/projects/-Users-aregee-Workspace-github-com-ClinVerdict-Physician-Curated-Clinical-AI-Evals-Suite/memory/` — `lithrim-north-star.md`, `sharif-calibrator-relationship.md` (Sharif = the archetypal Calibrator; informal/unpaid consultant; Finland visa ~mid-2027; competing PhD; paper-authorship + golden-case licensing unsettled).

---

## Open fronts — the next-move menu

**A · Silent Drop port — RE-PRIORITIZED 2026-06-18 (split + mostly deferred).** Post-research read: Silent Drop is in the *provenance/audit* lane (durable — *"the absence is the signal"*), NOT the de-emphasized "better-judge" lane — so it's not obsolete. BUT claim-4 is externally **unvalidated** (no recognized problem) and there's a skill-1 data precondition (SD-7), so the full inter-stage build is **design-partner-gated**, not near-term. **Split:** the dual-use pieces — un-dormant `source_message` (`backends/local_pipeline.py:105`) + extend `OMISSION_TYPE_CODES` (SD-2) + port `per_claim_regression.py`'s omitted-claims scorer (SD-3) — **fold into Front B** (they're the omission-measurement infra the 10-case ab_harness needs anyway). The inter-stage floor + multi-stage ingest + `SILENT_DROP` code (SD-1/4/5/6) **defer to real design-partner data**. Seams re-tagged accordingly in `STREAM_bench-salvage.md`.

**B · ClinVerdict experiment scale-up** (the paper's core + tests the #1 research risk). Register the remaining failure-mode codes + lenses for all 10 cases → grade all 10 → run `ab_harness` (lithrim vs Sharif vs Gemini). **Critically, disentangle over-flagging vs safety-blindness on the SAME frontier+grounded judge** — that's the research report's top open question and the make-or-break for the paper's claim-1 framing. **Includes (folded from A):** the omitted-claims recall scorer (SD-3) + un-dormant `source_message` / extend `OMISSION_TYPE_CODES` (SD-2) — you need an omission metric to score the council across 10 cases regardless.

**C · Pitch build** (zyng). Reopen where `zyng` connects (bench or command-center), `account` → **`capture_clips` the fresh ClinVerdict cases off `:5180`** (workspace `clinverdict_clean`: Case 9 `reject` + Case 8 `approve` + audit — capture spec in `../lithrim-command-center/docs/pitch/ZYNG_PITCH_BUNDLES_2026-06-18.md` §1) → `publish` the 30s for preview. The fresh shell captures are now the **primary** footage (old scribe-journey mp4 = fallback). **`publish` is billable + external — confirm each render.**

**D · Regulatory verification** (the load-bearing services-durability diligence — claim 6). A dedicated deep-research on EU AI Act high-risk / FDA GMLP / HIPAA continuous-compliance: do they require *auditable conformance evidence* vs accuracy? If yes → the services moat is model-improvement-proof.

**Recommended sequencing for a bench-rooted session:** **B → D** (prove it: the 10-case scorecard + the honest over-flag-vs-blindness measurement; then verify the regulatory mandate that gates services durability). **A is deferred** — its dual-use half (SD-2/SD-3) is absorbed into B; its inter-stage build (SD-1/4/5/6) is design-partner-gated, off critical path. **C** (pitch) when you want the artifact.

---

## Gates & invariants (respect these)
- **MOAT byte-frozen:** `runtime/council/*` + `harness/grounding.py` + `verification/{spec,tools}.py` + `apps/bff/agent/tools.py` = 0-diff unless a cycle explicitly owns them. New floors register via the pack's `FLOOR_EXECUTORS`, not engine edits.
- **`publish` (zyng)** spends credits + uploads to app.zyng.work → treat as a publish action; explicit go each time.
- **WS-2 pack edits are LOCAL** (`../lithrim-pack-healthcare`) — not committed.
- **`.mcp.json` carries a live `ZYNG_API_KEY`** in both repos → ensure gitignored before any commit.
- **Pack discovery** needs `LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare` on BFF start (chip `task_f8a612ac` to persist).
- Narration numbers (3%, 53→92, 85.7%) are **our own measurements** — label as such; don't present as external.

---

## Artifact index
| Artifact | Path |
|---|---|
| This handoff | `lithrim-bench/.devloop/sessions/HANDOFF_bench-salvage_clinverdict-thesis_2026-06-18.md` |
| Silent Drop seams | `lithrim-bench/.devloop/state/STREAM_bench-salvage.md` (`S-BS-SD-*`) |
| ClinVerdict extractor + corpus | `lithrim-bench/scripts/extract_clinverdict.py` · `out/clinverdict_v1.jsonl` |
| WS-2 taxonomy + ontology | `lithrim-pack-healthcare/healthcare/{taxonomy_snapshot,ontology}.json` |
| North Star spec | `lithrim-command-center/docs/specs/SPEC_lithrim_north_star.md` |
| Research verification | `lithrim-command-center/docs/research/REPORT_thesis_claim_verification_2026-06-18.md` |
| Pitch bundles | `lithrim-command-center/docs/pitch/ZYNG_PITCH_BUNDLES_2026-06-18.md` |
| Pitch footage | `zyng/out_lithrim_demo/bench_journey_silent.mp4` |
| Memories | `…/-Users-aregee-…-Evals-Suite/memory/{lithrim-north-star,sharif-calibrator-relationship}.md` |

---

## KICKOFF PROMPT (paste into the fresh lithrim-bench session)

> You are the monitor/driver for the **ClinVerdict × Lithrim thesis**, rooted in `lithrim-bench`. Orient first, then recommend — do NOT auto-run any build/grade/publish without my go.
>
> 1. Read `.devloop/sessions/HANDOFF_bench-salvage_clinverdict-thesis_2026-06-18.md` (full arc, verified state, gates, artifact index).
> 2. Run `/devloop-status bench-salvage` and read the `S-BS-SD-*` Silent Drop seams in `.devloop/state/STREAM_bench-salvage.md`.
> 3. Skim `../lithrim-command-center/docs/research/REPORT_thesis_claim_verification_2026-06-18.md` (what's proven vs gaps) and `../lithrim-command-center/docs/pitch/ZYNG_PITCH_BUNDLES_2026-06-18.md`.
> 4. Read the two memories at `/Users/aregee/.claude/projects/-Users-aregee-Workspace-github-com-ClinVerdict-Physician-Curated-Clinical-AI-Evals-Suite/memory/`.
>
> Then give me: (a) where we are in ≤6 bullets, (b) the A/B/C/D next-move menu with your recommended first move and why — **note Front A (Silent Drop) is re-prioritized: its dual-use half (SD-2/SD-3, the omission scorer) folds into B, its inter-stage build (SD-1/4/5/6) is deferred/design-partner-gated** — (c) any state I should reset first (active workspace is `clinverdict_clean` with the 10 cases loaded + 11 runs; BFF needs `LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare`). Respect the gates in the handoff (moat byte-frozen, `publish` is billable, WS-2 is local). Recommended default: **B (scale ClinVerdict to all 10 + ab_harness + the honest over-flag-vs-blindness measurement on a frontier grounded judge)** — the paper's core; it stress-tests the research's biggest risk and absorbs A's useful half. Await my pick before executing.
