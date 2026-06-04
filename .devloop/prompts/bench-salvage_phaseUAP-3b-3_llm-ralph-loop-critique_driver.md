# Driver (STUB) — `bench-salvage` phase `UAP-3b-3`: the LLM Ralph-Loop critique pass over the withstands-gate

> **STUB — split out of UAP-3b-2 (D-A, monitor + user-confirmed 2026-06-04/05). Expand via
> `/devloop-expand-driver bench-salvage UAP-3b-3` before executing.**
>
> **Bundle ID:** `bench-salvage-phaseUAP-3b-3-llm-ralph-loop-critique-driver`
> **Version:** v0-stub
> **Parent:** `bench-salvage-phaseUAP-3b-2-groundingcheck-entity-llm-critique-driver`
> (the LIVE attestation + S-BS-72 provenance blob + GroundingCheck entities landed; the
> DETERMINISTIC moat is proven offline AND live-attested)
> **Authored:** 2026-06-05 (by the UAP-3b-2 executor; expand before running)

---

## Why this phase (the LLM enrichment ON TOP of the proven deterministic floor)

UAP-3b proved THE MOAT **offline/$0** and UAP-3b-2 completed it (live attestation + the
withstands ruling in the run-provenance blob + GroundingChecks as first-class entities).
The withstands-gate today is **purely deterministic**: it reconciles each judge's verdict
against (a) the tagged ontology rules and (b) the validator/grounding outputs, and
corrects a signal-contradicted or out-of-lens finding. That deterministic layer is the
**floor** and it is DONE.

This phase adds the **LLM Ralph-Loop critique** — a reasoned pass that weighs the same
signals to produce a *reasoned* withstands ruling (the §2A "a judge's verdict stands ONLY
IF its reasoning withstands the signals", made LLM-mediated rather than rule-mediated).

**⚠️ The value-add is UNCERTAIN and must be MEASURED, not assumed.** Memory
`critique-pass-precision-not-floor`: a transcript-only self-critique CANNOT flip a
transcript-only blind spot — only the deterministic tool-grounded signal can. So the LLM
critique is **enrichment over the floor, not the floor**. The acceptance must MEASURE
whether the LLM pass improves precision over the deterministic gate alone (it may be null
— that is a valid, honest outcome, per the FHIR-AgentBench replication framing).

---

## Where it plugs in (compose, don't rebuild)

- `lithrim_bench/runtime/council/withstands.py:78 apply_withstands_gate(...)` — **the gate is
  already shaped to admit a `critique=` hook** (docstring `:27-29`; the signature has **no
  `critique=` param yet** — this phase ADDS it). The deterministic reject/suppress logic is
  REUSED, never rewritten; the LLM critique is an additional, optional signal-weigher.
- `signals.py` `JudgeSignals{ontology_rules, validator_outputs}` — the assembled signals the
  critique reasons over (already built per-judge).
- The DSPy critique spike (`critique-pass-precision-not-floor`) — the prior art to re-author
  in-package as the reasoned pass (gpt-4.1, cost-gated).
- `WithstandsDecision` (`withstands.py:49`) — the reasoned ruling extends the existing
  `{signals_weighed, decision, what_failed}` shape (add the LLM's reasoning trace); the
  §2B audit + the run-provenance blob embed (S-BS-72, UAP-3b-2) carry it unchanged.

---

## Scope guardrails (carry from UAP-3b/3b-2)

- **FROZEN:** `compliance_council._apply_consensus` + `judges_dspy` + `judge_metric` + the
  committed seeds (A4 byte-0-delta). The critique lives ABOVE the frozen seam, like the gate.
- The deterministic gate is the **floor** — the LLM critique can ENRICH but must NOT be
  allowed to relabel a by-construction case (the A5 invariant holds; the LLM is a
  down-ranker/corrector gated by the deterministic signals, never an independent relabeler).
- **Cost-gated:** a new paid LLM pass per judge — smoke→cost-go→one-run, cost-confirmed.
- A genuine measured improvement is the prize; **a null result is an honest PASS** (report it).

---

## Open decisions for plan-review (expand first)

- **Locus:** per-judge inside `apply_withstands_gate` (the §13 pre-consensus locus) vs a
  separate post-gate enrichment pass. Lean: extend `apply_withstands_gate(critique=...)`.
- **The measurement:** the held-out set + the metric that decides "the LLM critique improved
  precision over the deterministic gate" (the S-BS-49 exact-accept-gate caveat applies — a
  silent win is not a win; surface the measured Δ honestly).
- **Model + cost envelope:** gpt-4.1 (the spike's model) vs the v2 trio's deployments; name it.
- **Null-result disposition:** if the LLM pass does not beat the deterministic floor, the
  phase still SHIPS the measurement + the honest finding (the floor stands alone).

---

## References
- Spec: `docs/specs/SPEC_UNIFIED_AUTHORING_PRODUCT.md` §2A (the critique-as-verification gate
  :65-71; the `critique-pass-precision-not-floor` caveat is quoted there) · §13 (locus)
- Memory: `critique-pass-precision-not-floor` (the value caveat — self-critique ≠ floor) ·
  `fhir-agentbench-benchmark` (the judge-only vs floor-only vs worst-of measurement framing) ·
  `semantic-eval-equivalence-is-a-contract` (the unproven semantic axis the LLM pass might touch)
- Parent close: `.devloop/sessions/session-bench-salvage-phaseUAP-3b-2-2026-06-05.json`
- The gate to extend: `lithrim_bench/runtime/council/withstands.py` (REUSE; add `critique=`)

## Hardness
- [x] **HARD GATE** — a new paid LLM pass + a measured-improvement claim over the proven floor
  (a null result must be surfaced honestly, not buried). Fresh-critic at close.
