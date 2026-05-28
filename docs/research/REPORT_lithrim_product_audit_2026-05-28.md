# Lithrim product audit — toward Paper 1 + positioning (2026-05-28)

> **Purpose.** Distill the core product (lithrim-backend + lithrim-sdk + lithrim-bench)
> into an evidence-grounded capability map and evidence ledger that (a) supports the
> chosen Paper-1 framing, (b) establishes trust/credibility honestly, and (c) refines
> the value proposition to clinical-AI builders.
>
> **Chosen paper framing (user decision 2026-05-28):** *copilot spine + product thesis* —
> the Jute Copilot stays the load-bearing research contribution, framed around the
> categorical-blindness → validator-bottleneck → copilot thesis that is the product's
> core, with the honest limitations as the credibility layer. (Locked alternatives
> "ship narrow Paper 1 as-is" and "pull the framework forward" were considered and
> declined — see `PAPER_FRAMING_DECISIONS_2026-05-26.md` amendment.)
>
> **Method.** Three strategic product docs read first-hand (bench README + PAPER_OUTLINE
> + PAPER_FRAMING_DECISIONS + LITHRIM_BENCH_PRODUCT_SPEC + backend LITHRIM_SSOT + SDK
> README); three parallel deep-audit subagents over backend / sdk+examples /
> bench-paper-readiness; five load-bearing claims spot-verified first-hand before
> being stamped CONFIRMED.
>
> **Provenance convention (per CLAUDE.md diagnose-before-edit gate):**
> - **CONFIRMED** — verified first-hand this session (file:line / command output cited).
> - **CONFIRMED·sub** — reported by a deep-audit subagent with a specific file:line
>   citation; not personally re-verified. Treat as strong-INFERRED until spot-checked.
> - **INFERRED** — chain of reasoning from documented sources.
> - **HYPOTHESIS** — untested; falsifier noted.

---

## §1 Executive summary

Lithrim is an **execution-integrity layer for clinical AI**: it verifies the artifact an
agent writes back to a clinical system (SOAP note, ICD code, FHIR/HL7 message) against the
conversation that produced it, and gates it before it reaches the EHR. The verification
pipeline is real and runs in production code; the SDK genuinely supports a "CI/CD for
clinical agents" release-gate workflow.

The audit surfaced a **gap between the marketed story ("four independent verification
pillars") and the code (two axes, one of them off by default)**, and a set of **recent,
honestly-measured failures of the product against its own benchmark** (council over-fires
on clean structured records; worst-of composition does not generalize past HL7; the
"0/2 false positives on cleans" headline is falsified at N=5). These are not liabilities
to hide — for a verification product selling to clinical-AI safety officers, *the team's
benchmark catching the team's own product's failures is the single strongest trust
differentiator,* and no competitor in the product's own competitive table does adversarial
self-evaluation with by-construction labels.

The one genuinely novel, defensible, priority-dateable contribution is the **Jute Copilot**
— generating conformance validators from spec text (HL7 ADT^A04 coverage 2/5 → 5/5 in one
call). That is the correct research spine, and the product thesis that makes it matter is
*"LLM-as-judge is categorically blind to machine-checkable spec violations; the deployable
fix is a deterministic structural floor; that floor was gated by validator-authoring cost;
we close that bottleneck."*

---

## §2 The core product, as actually built

### §2.1 The verification pipeline (the real flow)

For `(transcript + artifact)` submitted via `POST /v1/analyze` (async Celery → observation
workflow → `artifact_evaluator.evaluate_artifacts`):

```
(transcript + artifact)
  → structural stage   etlp-mapper /mappings/:id/apply (Jute), {resource: <data>} wrapper;
                       HL7 parse-before-validate first. Verdict from fail ratio:
                       0 fail → PASS, ≤30% → WARN, >30% → BLOCK
  → semantic stage     LLM-judge council; deterministic verdict mapping
                       faithfulness <0.70 → BLOCK, <0.90 → WARN, else PASS;
                       Tier-1 never-event flag forces BLOCK
  → worst-of(structural, semantic) with the artifact-WARN-suppressed rule
  → verdict + gate_decision (allow / regenerate / escalate)
```

- **Worst-of composition rule** — `_VERDICT_RANK = {"PASS":0,"WARN":1,"BLOCK":2}`
  (CONFIRMED `lithrim-backend/app/services/pipeline/orchestrator.py:56`); the combined
  verdict is `_worst_of_with_artifact(structural, semantic, artifact)` (CONFIRMED `:272`),
  where **the artifact stage only contributes on BLOCK; its WARN is informational**
  (CONFIRMED docstring `orchestrator.py:77-86`). This is the "worst-of" the paper's §6 / the
  deck's moat refers to.
- **gate_decision** — PASS→allow, WARN→regenerate, BLOCK→escalate (if HIGH-severity finding)
  (CONFIRMED·sub `orchestrator.py:140-151`).
- Verdict vocabulary maps `approve→PASS, needs_review→WARN, reject→BLOCK`
  (CONFIRMED·sub `pipeline/models.py:19-23`).

### §2.2 Four pillars × five layers — claimed vs in-code

The marketing model (LITHRIM_SSOT §1; PAPER_FRAMING_DECISIONS) is **four pillars
(Faithfulness, Completeness, Safety, Structural Validity) × five layers**. The code says:

| Claim | Reality | Tag |
|---|---|---|
| Four *independent* pillars | **Two axes.** Faithfulness + Completeness + Safety are all the *same LLM-judge axis* — `faithfulness_score` and `completeness_score` are copied verbatim from one `artifact_judge` output (`artifact_evaluator.py:182-191`, `:520-521`). Structural Validity is the one genuinely independent, deterministic axis. | **CONFIRMED** |
| Structural Validity is a shipped pillar / the moat | **OFF by default** — `ETLP_MAPPER_ENABLED: bool = False` (`config.py:242`); the validator service defaults to a remote box (`ETLP_MAPPER_URL = "http://192.168.1.21:3031"`, `config.py:232`). The headline 4th pillar is gated behind dev/pilot config. | **CONFIRMED** |
| Cross-provider council (the silent-confident-cert fix) is the council | **v1 ships by default** — `COMPLIANCE_COUNCIL_VERSION: Literal["v1","v2"] = "v1"` (`config.py:211`). v1 = 3× gpt-4.1 same-provider monoculture (policy/risk/behavior). The v2 cross-provider trio (the fix for silent-confident-certification) is `.env`-override only. Corroborated by the SDK's own failing test fixture, whose `judge_votes` keys are exactly `{policy, risk, behavior}` (the v1 council). | **CONFIRMED** |
| Jute Copilot is a product layer (L5) | **Pilot/playground-wired** — the agentic generation loop (`validation_council/service.py`, `phase4_loop_orchestrator.py`) is real and calls etlp-mapper `/mappings/generate`, but is wired only to `playground`/`admin_playground` routes, not `/v1/analyze` and not a GA developer endpoint. Actual template generation lives in the separate etlp-mapper Clojure service. | **CONFIRMED·sub** |
| Tier-1 safety owners route to running judges | **Declarative drift** — `_TIER1_OWNERS` references `source_message_judge` for WRONG_DOSAGE / MISSING_ALLERGY / FABRICATED_CONSENT (`compliance_council.py:232-249`), but that judge is in **no** default council tuple (`:499-503`). The PAPER_OUTLINE §4 already flags this as a methods-section disclosure requirement. | **CONFIRMED·sub** |

**Five layers status (subagent audit):** L1 verification primitive — CONFIRMED real
(`/v1/pipeline/evaluate`). L2 release-gate eval primitives — CONFIRMED (eval packs, runs,
compare, promote). L3 trace audit + attestation — PARTIAL (rich audit-view + provenance
persistence + "eight-link evidence chain"; **no cryptographic signing/attestation found** —
"attestation" = provenance, not crypto). L4 domain taxonomy + remediation — PARTIAL
(taxonomy + deterministic failure-clustering + patch templates real). L5 Jute Copilot —
PILOT (see above).

### §2.3 The developer surface (SDK)

The SDK is the strongest, most builder-legible surface. `evaluate(...)` is the in-turn gate
primitive (CONFIRMED·sub `client.py:593-653`) returning `EvaluateResult` with `verdict`,
`gate_decision` (allow/regenerate/escalate), `findings[]`, structural+semantic stage
results, `provenance`, and a client-side `rebuild_prompt_hints()`. The release-gate
primitives (`eval.run / compare / promote / finalize`, CONFIRMED·sub `client.py:191-451`)
genuinely support gate + baseline-regression + provenance retrieval — the "CI/CD for
clinical agents" story is real, not stubbed. **Smallest viable integration:** write one
`agent_callable`, call `client.eval.run(pack_id=..., agent_callable=..., thresholds=...)`,
`sys.exit(run.report.threshold_result.recommended_exit_code)` (CONFIRMED·sub
`docs/CI_INTEGRATION.md:6-29`).

**The `evidence_spans` > `safety_flags` split is the load-bearing trust feature** (SDK
README:43-58): `evidence_spans` are direct quotes the model anchored on; `safety_flags`
are best-effort tags. The split exists *because* of the 5.73× decision-vs-attribution gap
(see §3). This is the most concrete, builder-legible reason to trust the output and should
lead the pitch.

---

## §3 Empirical evidence ledger

| Result | Headline | Status | Source |
|---|---|---|---|
| Categorical blindness (HL7) | LLM council 0/28 spec violations vs strict validator 28/28 | **publication-ready** (distribution-independent; N=1 but deterministic by construction) | `07_results.md:69-75`; `STRICT_HL7_VALIDATOR_2026-05-22.md` |
| **Jute Copilot** | HL7 ADT^A04 coverage **2/5 → 5/5 in one call** from public spec text (`confidence: partial`, 2 retries, +3 format/value-set/consistency checks) | **publication-ready** (single-shot, honestly framed; an injector bug `msh[9]` vs `msh[8]` was found+fixed during validation — disclose it) | `STRICT_HL7_VALIDATOR_2026-05-22.md:12-100` |
| Decision-vs-attribution gap | verdict accuracy 0.722 vs exact-flag attribution 0.126 = **5.73×** | **publication-ready** (N=10 test split, 4,140 reject opportunities) | `07_results.md:90-96` |
| Verdict-layer determinism | 12/12 canonical cases verdict-deterministic at 5/5 (temp=0); finding-codes NOT deterministic (7/12 <5/5) | **publication-ready** (N=5×12=60) | `REPORT_p1_canonical_n5_pilot_2026-05-28.md:21-24` |
| Silent confident certification | gpt-4o×3 monoculture unanimously approved 5/10 defects at confidence 1.000; cross-provider trio → 0/10 | **direction-only** (N=12, qualitative; big-N ~$13 unrun) | `05_section_5..._v2.md:15,52,96` |
| **"0/2 false positives on cleans" (§5.5 headline)** | — | **❌ FALSIFIED at N=5** — C1 BLOCKs 5/5 deterministically. Must become "1/2, characterized." | `REPORT_council_overfire_convergence_2026-05-28.md:20,114`; `REPORT_p1_canonical_n5_pilot_2026-05-28.md:24` |
| §6.5 worst-of generalizes to FHIR | — | **❌ NO-GO** — council over-fires on clean FHIR Patient; structural status=WARN-not-BLOCK (S-P1-15) | `REPORT_p1_fhir_mini_2026-05-28.md:1-31` |
| Council over-fire convergence | `FABRICATED_HISTORY` fires 11/12 cases incl. **both** clean negatives — a "wash code" with near-zero attribution signal; over-firing judge changes by artifact type (Mistral on DocumentReference, Llama on Patient) → not a single-judge fix | **CONFIRMED at aggregate finding level**; the per-judge "differs by judge" claim is **INFERRED** (per-judge role/vote are NOT persisted — verified this session: `pipeline_runs.stage_results.semantic.judge_votes` has `role=undefined, verdict=undefined`; `judge_rationale` is aggregate-only) | `REPORT_council_overfire_convergence_2026-05-28.md`; verified live this session |

The 4-pack semantic sweep (`07_results.md`) is **baseline characterization, not thesis
validation** (locked by `PAPER_OUTLINE.md:15`). The scheduling "+71 pp recovery" is the
FP-prone single `artifact_judge`, **not** the structural axis — owned honestly
(`07b_threats_to_validity.md:56-74`).

---

## §4 Credibility gaps + honest limitations (assets if owned)

For a verification product, these disclosed-honestly *are* the marketing:

1. **The council over-fires fabrication codes on clean structured artifacts** —
   deterministic false positive (C1 BLOCKs 5/5). A real product-quality defect, not just a
   bench artifact. Directly falsifies the §5.5 "0/2 FP" headline. (CONFIRMED)
2. **The worst-of composition does not generalize beyond HL7** — §6.5 NO-GO on FHIR;
   structural `severity=HIGH` does not translate to backend `status=BLOCK` (S-P1-15);
   council noise dominates attribution. (CONFIRMED this session)
3. **The grading methodology can't establish attribution** — `FABRICATED_HISTORY` is a wash
   code that fires on clean and defective alike; per-case set-membership grading certifies
   "catches" that didn't happen. Fix = contrastive (defect-vs-clean-twin) grading +
   per-judge capture (currently unpersisted). (CONFIRMED this session)
4. **Declarative-vs-operational drift** — Tier-1 owner map cites a judge that doesn't run
   (§2.2). (CONFIRMED·sub)
5. **Verdict-propagation defects** — engine-vs-UI verdict can disagree
   (`07b:48-50`); structural findings serialize `code:null` (S-P1-16). (CONFIRMED·sub)
6. **Small N** — N=10/12/5; some packs miss the ≤0.10 CI gate (`07b:20`). (CONFIRMED·sub)
7. **Zero signed design partners / zero customer logos** (`PAPER_FRAMING_DECISIONS:11`).
   (CONFIRMED·sub)
8. **SDK suite is currently red** — `tests/test_evaluate.py`: **4 failed, 10 passed**
   (CONFIRMED this session). Root cause: commit `49e8a56` changed
   `PipelineStageResult.judge_votes` from `Optional[dict]` to `Optional[list[JudgeVote]]`
   (`lithrim-sdk/lithrim/models.py:191`) without updating the test fixture, which still
   feeds the legacy dict `{policy, risk, behavior}`. Per-judge role/vote *are* now modeled
   but the contract changed under the suite. Also: stale `User-Agent: lithrim-python/0.3.1a0`
   vs `__version__ 0.4.0`; CI exit-code documented two ways (3-code in `ci_integration.py`
   vs 4-code in `MIGRATION_0_2_to_0_3.md`). (CONFIRMED·sub + this session)

The existing `07b_threats_to_validity.md` is strong but **predates** the three 2026-05-28
reports — it does not yet mention #1, #2, or #3 above. Folding them in is the single
highest-credibility edit available.

---

## §5 Implications for Paper 1 (copilot spine + product thesis)

The chosen framing keeps the Jute Copilot as the load-bearing contribution but frames the
whole paper around the product's actual core thesis:

> *LLM-as-judge is categorically blind to machine-checkable specification violations, and
> this blindness does not close with judge accuracy. The deployable fix is a deterministic
> structural floor composed under worst-of — but that floor was historically gated by the
> cost of hand-authoring conformance validators. We close that bottleneck by generating the
> validators from spec text, and we hold the whole system to a synthetic benchmark built to
> be true by construction, including where it fails.*

How the audit supports it:

- **Defensible spine.** The copilot (2/5→5/5), the categorical-blindness contrast (0/28 vs
  28/28), and the 5.73× gap are all publication-ready (§3). They carry the paper without
  touching the unproven pillars.
- **Honesty as the credibility engine.** §4 #1–#3 are the differentiator. Recommend a
  dedicated subsection ("We evaluated our own composition and it failed on FHIR") rather
  than burying them in threats-to-validity. This is what a clinical-AI safety officer will
  remember.
- **Hard constraints the draft must respect:**
  - The §5.5 "0/2 FP on cleans" sentence **must** be corrected to "1/2, characterized"
    before any external citation (it is falsified at N=5).
  - Worst-of claims must be scoped **to HL7 explicitly**; the FHIR NO-GO means the
    cross-standard generalization is future work, not a result.
  - The "four pillars" language should not appear as four independent detectors; describe
    "a deterministic structural floor under an LLM-judge council" (true) instead.
  - The per-judge "over-firer differs by judge" claim in the convergence report is INFERRED
    (per-judge votes unpersisted); if the paper uses it, either re-run with per-judge
    capture or tag it INFERRED.

What stays out of Paper 1 (per the locked staged-disclosure plan, `PAPER_FRAMING_DECISIONS`
A3/A4): the four-pillar framework (Paper 2, gated on design partners), trace-level audit
(Paper 3), the eight-link hashing scheme, the full safety taxonomy, the failure-clustering
algorithm, the agent-KPI weighting.

---

## §6 Pitch / value-proposition refinement (for clinical-AI builders)

Fallout of the audit, concrete:

- **Stop saying** "four independent verification pillars" — it's two axes and a buyer's
  engineer will find that out. **Say** "a deterministic structural floor under an LLM-judge
  council."
- **Stop leading with** "structural validation" (a $50M-niche feature description per
  `PAPER_FRAMING_DECISIONS:82`). **Lead with** the bottleneck removed: *conformance
  validators that took weeks to hand-author, generated from spec text in one call.*
- **Lead the trust story with** the 5.73× gap → *"we surface the quote, not just a flag"*
  (already shipped as `evidence_spans`). Most concrete builder-legible trust signal.
- **Own the limitations as proof of method:** *"our benchmark caught our own council
  over-firing on clean FHIR records — here's the fix in flight."* Sells better to a safety
  officer than any green dashboard.
- **Umbrella positioning** (already locked, `PAPER_FRAMING_DECISIONS:83`, D9): *"Lithrim
  makes clinical AI deployable, defensible, and insurable."* The paper is the credibility
  proof behind the "defensible" claim; the 9-procurement-question framework
  (`command-center/.../RESEARCH_SYNTHESIS_enterprise_rfp_packaging`) is the closest thing to
  a category claim — Lithrim answers 7/9 today.

---

## §7 Pre-publication fix list (prioritized)

Builders integrate the SDK first; the first thing they hit must work.

1. **SDK red suite** — update `tests/test_evaluate.py` fixtures to the `list[JudgeVote]`
   shape (the S-P1-12 follow-up that shipped without its test). Bump `User-Agent` to 0.4.0.
   Reconcile the CI exit-code contract (3-code vs 4-code) across `ci_integration.py`,
   `CI_INTEGRATION.md`, `MIGRATION_0_2_to_0_3.md`.
2. **Falsified headline** — correct §5.5 "0/2 FP on cleans" → "1/2, characterized"
   everywhere it appears (abstract, §5, results).
3. **Threats-to-validity refresh** — fold the council over-fire (S-P1-20/21), the FHIR §6.5
   NO-GO, and the grading-attribution gap into `07b_threats_to_validity.md`.
4. **Methods disclosure** — state the v1-default council (3× gpt-4.1), the
   `source_message_judge` declarative drift, and that structural validity is config-gated,
   in the methods section (the PAPER_OUTLINE already requires the first).

---

## §8 Confidence ledger

| Claim | Tag | Basis |
|---|---|---|
| ETLP_MAPPER_ENABLED defaults False; council defaults v1 | CONFIRMED | `config.py:242,211` read this session |
| Faithfulness+Completeness are one judge axis | CONFIRMED | `artifact_evaluator.py:182-191,520-521` read this session |
| Worst-of with artifact-WARN suppression | CONFIRMED | `orchestrator.py:56,72-95,272` read this session |
| SDK evaluate suite red (4/14) | CONFIRMED | `pytest tests/test_evaluate.py` run this session |
| Per-judge role/vote unpersisted | CONFIRMED | Mongo `pipeline_runs` + SDK ndjson inspected this session |
| Copilot pilot-only wiring; L3 has no crypto attestation; declarative drift | CONFIRMED·sub | backend deep-audit subagent file:line citations, not personally re-verified |
| Evidence ledger numbers (0/28, 2/5→5/5, 5.73×, N=5 determinism) | CONFIRMED·sub | bench paper-readiness subagent + bench docs read first-hand |
| §5.5 "0/2 FP" falsified; §6.5 FHIR NO-GO; over-fire wash code | CONFIRMED | this session's REPORTs (FHIR-MINI authored by me; convergence cross-checked) |
| "over-firer differs by judge" | INFERRED | per-judge votes unpersisted; convergence report tags it CONFIRMED but committed artifacts only support aggregate-level |

---

## §9 Source artifacts + subagent provenance

**Read first-hand:** `lithrim-bench/README.md`, `docs/PAPER_OUTLINE.md`,
`docs/PAPER_FRAMING_DECISIONS_2026-05-26.md`, `docs/LITHRIM_BENCH_PRODUCT_SPEC.md`,
`lithrim-backend/LITHRIM_SSOT.md`, `lithrim-sdk/README.md`; spot-verified
`config.py`, `artifact_evaluator.py`, `pipeline/orchestrator.py`, `tests/test_evaluate.py`,
Mongo `pipeline_runs`.

**Subagent audits (full transcripts available; agent IDs):** backend capability map
(`a568badfc25e37b07`), sdk+examples (`a49f833f3e68903d5`), bench paper-readiness +
positioning (`a9cdd441ebccdb5a5`). Note: the positioning material (`strategy/`, `pitch/`,
`sales-outreach/`) lives in `lithrim-command-center/docs/`, not `lithrim-backend/docs/`.

**This session's source reports (credibility-relevant, post-date `07b`):**
`REPORT_p1_fhir_mini_2026-05-28.md`, `REPORT_council_overfire_convergence_2026-05-28.md`,
`REPORT_canonical_12_validation_2026-05-28.md`, `REPORT_paper_v1_n12_canonical_pack.md`,
`REPORT_p1_canonical_n5_pilot_2026-05-28.md`.
