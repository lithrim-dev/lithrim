# §4 — Method

## 4.1 The verification pipeline

The system under test is a two-stage verification pipeline that takes (clinical transcript, structured artifact) as input and emits a `compliance_verdict ∈ {approve, needs_review, reject}`.

```
            ┌──────────────────────────────┐
            │  (transcript, artifact)      │
            └──────────────┬───────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
   ┌──────────▼──────────┐    ┌─────────▼──────────┐
   │   SEMANTIC STAGE    │    │  STRUCTURAL STAGE  │
   │   3-judge council   │    │  Jute conformance  │
   │   gpt-4.1 +         │    │  template (FHIR /  │
   │   criteria-injection│    │  HL7 v2 / SOAP)    │
   │                     │    │                    │
   │ policy_judge        │    │  PASS / WARN /     │
   │ risk_judge          │    │  BLOCK             │
   │ behavior_judge      │    │                    │
   └──────────┬──────────┘    └─────────┬──────────┘
              │ approve / needs_review  │
              │ / reject + flags        │
              │                         │
              └────────┬────────────────┘
                       │
              ┌────────▼────────┐
              │  WORST-OF RULE  │
              │   (§4.2)        │
              └────────┬────────┘
                       │
            ┌──────────▼──────────┐
            │  compliance_verdict │
            └─────────────────────┘
```

The three council judges (`policy_judge`, `risk_judge`, `behavior_judge`) are the same three that run in production; we did not invent or aspirational-spec them. The earlier `_TIER1_OWNERS` map in lithrim-backend referenced a `source_message_judge` that did not run in the production three-judge config (defect D3 in [`docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`](../EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md)). The eval-spec lint (`scripts/lint_golden_against_taxonomy.py`) enforces that every expected_safety_flag in the golden set is owned by a judge that actually runs; commits `2ca28e4` and `e94c49f` on lithrim-backend reconcile the historical golden against the live taxonomy and ownership map.

This methods section describes what runs. The aspirational design is explicitly out of scope; the paper does not pretend the production system has a fourth judge.

## 4.2 The worst-of rule

Given the two stages' outputs, the combined verdict is the max-severity along each axis:

```
artifact_verdict_combined   = worst-of(semantic.artifact_verdict,
                                       structural.artifact_verdict)
                              using {PASS = 0, WARN = 1, BLOCK = 2}

compliance_verdict_combined = worst-of(semantic.compliance_verdict,
                                       lift(structural.artifact_verdict))
                              using {approve = 0, needs_review = 1, reject = 2}
                              where lift maps  BLOCK -> reject
                                               WARN  -> needs_review
                                               PASS  -> approve
```

The rule is the production rule. The canonical implementation lives in `lithrim-backend/app/services/artifact_evaluator.py:37-45` (pinning commit `b9412d1` on lithrim-backend):

```python
# Verdict hierarchy for worst-of logic
_VERDICT_SEVERITY = {"PASS": 0, "WARN": 1, "BLOCK": 2}

def _worst_verdict(verdicts: List[str]) -> str:
    """Return the most severe verdict from a list."""
    if not verdicts:
        return "PASS"
    return max(verdicts, key=lambda v: _VERDICT_SEVERITY.get(v, 0))
```

The bench's analysis-side mirror is in [`lithrim_bench/backends/worst_of.py`](../../lithrim_bench/backends/worst_of.py) (commit `0cf2a5a` on lithrim-bench). The mirror exists so the bench can compose any (semantic, structural) backend pair under the same rule the production pipeline applies, without round-tripping through the live backend for every experiment — useful for the simulated-validator coverage-ceiling experiments in §6.

We chose worst-of (max severity) over a probabilistic combination (e.g. weighted vote, calibrated logistic on judge confidences) for three reasons, listed by importance:

1. **Categorical asymmetry.** A spec violation is a spec violation regardless of the judge's confidence. A semantic judge cannot down-weight a deterministic conformance failure into a less-severe verdict; the spec said it was a failure.
2. **Auditability.** A regulated-domain deployer needs to point to the rule. "We took the max severity along each axis" is one sentence; "we trained a calibrated logistic on a held-out set" is a sentence plus a model card plus drift monitoring.
3. **No additional parameters.** Worst-of has zero tunable parameters. The composition gain we measure cannot be the result of tuning the composition; it can only come from the semantic-vs-structural axis decomposition. This is the cleanest way to test the categorical-blindness claim.

A weighted-vote ablation appears in §6 to confirm worst-of is competitive against the natural-baseline alternative; we report results, not just describe the rule.

## 4.3 The negative audit trail

Because every benchmark defect is _injected_ via the bench's defect-injector framework, the contradicting or absent source span is known by construction. The injection recipe carries the exact field/span that was mutated:

```python
@dataclass
class InjectionRecipe:
    defect_type: str            # e.g. "upcode", "downgrade_disposition"
    safety_flag: str            # e.g. "UPCODING_RISK"
    mutated_projection: str     # "artifact_structured" | "transcript" | "both"
    mutated_field_or_span: str  # e.g. "Claim.diagnosis[0]...coding[0].code"
    pre_value: str
    post_value: str
    params: dict
```

(Source: `lithrim_bench/injectors/base.py`, commit `bedbbfd`.)

This makes the negative-audit-trail signal — "an asserted claim in the artifact has no supporting span in the transcript" — mechanically measurable. The judge's grounding output names a span; we check it against the known mutated_field_or_span. There is no annotator-floor on the metric because there is no annotator.

The injectors are typed and modality-aware:

| Injector | Mutates | Target safety_flag | Tier |
|---|---|---|---|
| `WrongDosageInjector` | transcript | `WRONG_DOSAGE` | 1 |
| `MissingAllergyInjector` | transcript | `MISSING_ALLERGY` | 1 |
| `FabricatedHistoryInjector` | both | `FABRICATED_HISTORY` | 2 |
| `HallucinatedDetailInjector` | both | `HALLUCINATED_DETAIL` | 2 |
| `ValueMismatchInjector` | both | `VALUE_MISMATCH` | 1 |
| `PhiDisclosurePreVerificationInjector` | transcript | `PHI_DISCLOSURE_PRE_VERIFICATION` | 1 |
| `UpcodingRiskInjector` | artifact_structured | `UPCODING_RISK` | 2 |
| `MissedEscalationInjector` | artifact_structured | `MISSED_ESCALATION` | 1 |
| `Hl7MalformedDateInjector` | hl7_text | `STRUCTURAL_MALFORMED_DATE` | structural |
| `Hl7MissingSegmentInjector` | hl7_text | `STRUCTURAL_MISSING_REQUIRED_SEGMENT` | structural |
| `Hl7InvalidFieldFormatInjector` | hl7_text | `STRUCTURAL_INVALID_FIELD_FORMAT` | structural |
| `Hl7MissingRequiredFieldInjector` | hl7_text | `STRUCTURAL_MISSING_REQUIRED_FIELD` | structural |
| `Hl7TriggerEventMismatchInjector` | hl7_text | `STRUCTURAL_TRIGGER_EVENT_MISMATCH` | structural |

Eleven typed injectors total across the five packs; the five HL7-structural injectors are what surface the categorical-blindness claim most cleanly because they're outside the semantic axis by construction.

## 4.4 The drop-only critique pass

We retain (and report on) the production critique pass, which is a drop-only post-hoc step over the council's findings — a critique-pass model reviews each finding the council emitted and drops findings the critique deems unsupported. Importantly, it is _drop-only_: it cannot add findings. This preserves faithfulness (no new claim invented downstream) while letting the system reduce over-attribution.

The critique pass is part of the system under test (per defect D7 in [`EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`](../EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md)). We describe it here for completeness because it runs in the production pipeline, but **evaluating it (the critique-off/critique-on arms) is deferred to future work** — `/v1/pipeline/evaluate` exposes no critique toggle, and adding one is a backend API change out of scope for v1 (see `PAPER_OUTLINE.md` Phase-2 scope change, and §7b). All §7 numbers are with the critique pass in its production-default configuration.

## 4.5 The two-line composition is the contribution

The method's load-bearing observation is small: a two-line composition rule over a two-axis system materially changes what the pipeline catches. The size of the change depends on what fraction of real failures live on each axis. The claim that conformance-sensitive domains have substantial structural-axis failure mass — and therefore stand to benefit from this composition — is the empirical scope we test in §7. The method itself is one rule, deliberately.

## Word count

Approximately 1150 words. Under the 1500-word ceiling.

## Citation provenance

| Claim | Source |
|---|---|
| Worst-of rule (canonical) | lithrim-backend `app/services/artifact_evaluator.py:37-45` @ commit `b9412d1` |
| Worst-of rule (bench mirror) | bench `lithrim_bench/backends/worst_of.py` @ commit `0cf2a5a` |
| D3 reconciliation | bench `docs/EVAL_BENCHMARK_AND_DETERMINISM_SPEC.md`; lithrim-backend commits `2ca28e4` + `e94c49f` |
| InjectionRecipe schema | bench `lithrim_bench/injectors/base.py` @ commit `bedbbfd` |
| Eleven-injector inventory | bench `lithrim_bench/injectors/__init__.py` @ commit `0f03f04` |
