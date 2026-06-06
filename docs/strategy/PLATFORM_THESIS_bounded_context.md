# Platform thesis — the shared bounded context for governed AI

> Where the journey + the proofs lead: Lithrim is not a benchmark tool, it is the **control
> plane where an enterprise's domain expertise becomes executable, auditable, calibratable
> governance over its AI agents** — the shared **bounded context** between the people who own
> the domain (SMEs) and the people who run the agents (Engineering). Healthcare first, because
> it is the hardest and most-regulated bounded context; the same model generalizes.
>
> Status: synthesis 2026-06-06, grounded in this session's live proofs + the open seams.
> Companions: `PITCH_journey_proof.md`, `SPEC_CALIBRATION_TRAINER.md`,
> `SPEC_UNIFIED_AUTHORING_PRODUCT.md`, `SPEC_ONBOARDING_JOURNEY.md`; memory
> `eval-services-venture-thesis`, `gtm-launch-and-journey-thesis`.

---

## 1. The thesis — the ontology *is* the bounded context

In DDD terms, the failure mode of enterprise AI is a **broken bounded context**: the SME knows
what "correct" means in the domain (a clinical note must not fabricate history; consent must
precede PHI disclosure), and Engineering ships the agent — but the *evaluation criteria* live
in nobody's hands. Prompts drift, judges are trusted blindly, "good" is undefined and undefended.

Lithrim's primitive — the **ontology** (flags · tiers · owners · refinement questions ·
verification contracts · grounding checks) — is that bounded context made **explicit, versioned,
and executable**. It is the *ubiquitous language* both sides share:
- **SMEs author + own the criteria** (in domain terms; via conversation + the calibration trainer).
- **Engineering runs the agents** (the SDK route) and the same criteria **execute** as judges +
  deterministic grounding over the agent's outputs.
- Both share one **audit trail** (governance) and one **calibration history** (ops/trust).

That shared, auditable, calibratable artifact is the product. Everything else (judges, the
council, the floor, the trainer, the reports) is the runtime of that contract.

## 2. Why a platform, not a tool

A tool grades outputs. A **platform** is where four enterprise concerns converge on one artifact:
- **Governance / policy** — every criteria change and every verdict is attributed (why/when/who/what)
  and source-grounded → defensible to a regulator.
- **Domain** — the bounded context is the domain's evaluation criteria, owned by its SMEs.
- **Ops** — the calibration loop keeps the criteria *true over time* as agents and reality drift.
- **Calibration** — the deterministic floor is what makes a verdict trustworthy, not a prompt.

Capture those once, per domain, and you have a reusable governance substrate — not a one-off eval.

## 3. The de-risked core — what is already PROVEN

The load-bearing mechanisms are validated live (not promised), which is what makes the platform
*de-riskable* rather than aspirational:
- **Grounding overrules a confidently-wrong judge** (run `8a41ef3e`) — the trust floor is real.
- **Calibration catches its own drift** — a real config drift → `needs_review` → calibration flagged
  it (0.0) → fixed → re-run (`83ec5086`) → 1.0. The ops loop works on itself.
- **Prompt-tweaking is non-monotonic; grounding is the reliable lever** (measured, UAP-4) — the
  calibration thesis is empirical, not a hope.
- **SME-vs-Eng authoring is conversational + audited** — talk → an audited config write → a card
  (UAP-5b/5c), local + BYOK, `$0`. The bridge mechanism exists.

## 4. What must be ADDRESSED to de-risk the platform (gaps → seams)

| # | De-risk gap | Why it blocks the platform | Where it stands |
|---|---|---|---|
| 1 | **SME-authorable bounded context** | The criteria must be *minted + owned by SMEs*, not engineers. Today authoring is edit-only + expert-assuming. | `author_flag` is edit-only (**S-BS-83**); the teaching on-ramp (`SPEC_ONBOARDING_JOURNEY`); cross-turn memory for a real authoring conversation (**S-BS-87**). |
| 2 | **Governance-grade audit** | Every policy-affecting change must carry a *recorded why* and be immutable/exportable. | The audit trail exists, but the UI permits blocking-critical edits with a **blank rationale** (**S-BS-86b**). Require non-empty justification on criteria/severity edits; export. |
| 3 | **Grounding as the reliable, de-risked lever** | Calibration is only trustworthy if a deterministic floor sits under every judge (the withstands-gate). | Proven on structural/presence; the **withstands-gate generalization + the live correction** is owed (**S-BS-74**, the moat). Productize the floor per criterion. |
| 4 | **Multi-domain bounded contexts** | "Any domain" needs bring-your-own-ontology + per-domain taxonomy/snapshot + a grounding-check library. | Proven on `clinical_v1` (one). Domain bootstrapping is designed, not built. |
| 5 | **The SME↔Eng operating model** | Real roles/identity, the SDK ingestion route, and a shared workspace over the ontology + audit + calibration. | An actor model exists (`dev-default` vs `sme@`) but no real RBAC; the SDK route + shared workspace are roadmap (journey P4). |
| 6 | **Trust + deployment** | Regulated buyers need local/airgap + offline license — the trust wedge. | Local-first + BYOK **proven**; Tauri packaging + VPC/airgap + offline license are roadmap (journey P1). |

## 5. Sequencing — de-risk in this order

1. **Make the bounded context SME-ownable** (gaps 1 + the calibration trainer = journey Phase 3).
   This is simultaneously the product *and* the SME↔Eng bridge — highest leverage. Build: the
   onboarding teaching layer → memory (S-BS-87) → conversational *criteria creation* (beyond edit).
2. **Harden governance** (gap 2). Require a rationale on every policy-affecting edit; make the audit
   immutable + exportable. Small, and it converts "we log changes" into "you can defend this."
3. **Productize the grounding floor + withstands-gate** (gap 3). The de-risk moat: every judge sits
   over a deterministic floor; the live-correction demo (S-BS-74) is the visceral proof.
4. **Then scale**: multi-domain bootstrapping (gap 4), the SDK route + RBAC (gap 5), packaging/VPC (gap 6).

Do 1–3 and the platform is de-risked *as a governance claim*; 4–6 scale it across domains + buyers.

## 6. The wedge

Healthcare-first (the hardest, most-regulated bounded context — where hallucination is unacceptable
and audit is mandatory) + **honesty** (verifiable proofs, not a promised win) + the **deterministic
grounding floor** (the de-risk competitors can't match by tuning a judge) + **local/BYOK** (no data
leaves). The result an enterprise buys is not "a better judge" — it is a **shared, auditable,
calibratable definition of correct for their domain**, owned by their SMEs, executed over their
engineers' agents, defensible to their regulator. That is the platform.

## Open strategic questions
- **Services-led vs product-led** (per `eval-services-venture-thesis`): who authors the first bounded
  context per customer — an FDE/SME engagement, or self-serve? The calibration trainer aims at
  self-serve; healthcare may need services first.
- **Where the moat compounds**: the bounded-context corpus + the SME calibration loop + the audit
  history (the flywheel), not the (open-core) bits.
- **The "who calibrates?" gap**: the SME's time is the scarce input; the trainer + teaching layer
  exist to lower it — the compounding-margin bet rides on that working.
